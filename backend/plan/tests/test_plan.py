import dataclasses
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.test import APITestCase

from budget.models import AnnualExpenseEntry, AnnualIncomeEntry
from memberships.models import FamilyMember
from net_worth.models import Asset, InvestmentContributionInterval, Liability

from plan.models import (
    AssumptionSet,
    FinancialPlan,
    Finding,
    PlanAssetFunction,
    PlanEvent,
    ProjectionSnapshot,
    Recommendation,
    Scenario,
)
from plan.services_classification import AssetClassificationService
from plan.services_findings import FindingService
from plan.services_foundations import FoundationService, health_grade, health_status
from plan.services_quality import DataQualityService
from plan.services_events import (
    close_plan_event,
    register_occurred_event,
    register_planned_decision,
    release_occurred_event,
)
from plan.services_inputs import ExpenseBucket, expense_bucket, one_off_flows, plan_fiscal_year
from plan.services_lifecycle import cancel_plan_event, materialize_plan_event
from plan.services_projection import (
    ProjectionService,
    build_projection_inputs,
    capital_requirements,
    debt_annual_payment,
    decision_debt_service_for_year,
    earliest_sustainable_retirement_year,
    free_operating_surplus,
    get_assumption_set,
    plan_event_payloads,
    planned_contribution_amount,
    serialize_assumptions,
    target_capital_for_year,
)
from plan.services_scenarios import ScenarioService


def create_plan(user, **overrides):
    data = {
        "user": user,
        "household_type": FinancialPlan.HouseholdType.SINGLE,
        "target_date": date(2040, 1, 1),
        "target_monthly_income_today_eur": Decimal("2000.00"),
        "projection_end_date": date(2065, 1, 1),
        "profile": FinancialPlan.Profile.BALANCED,
    }
    data.update(overrides)
    return FinancialPlan.objects.create(**data)


def create_investment(user, amount=Decimal("100000.00"), name="ETF"):
    return Asset.objects.create(
        user=user,
        name=name,
        category=Asset.Category.INVESTMENTS,
        subcategory=Asset.Subcategory.ETFS,
        amount=amount,
        currency="EUR",
    )


def create_income(user, amount=Decimal("36000.00")):
    return AnnualIncomeEntry.objects.create(
        user=user,
        name="Salario",
        category=AnnualIncomeEntry.Category.SALARY,
        subcategory="salary",
        amount_annual=amount,
        fiscal_year=2026,
    )


def create_operating_expense(user, amount=Decimal("24000.00"), name="Vida"):
    return AnnualExpenseEntry.objects.create(
        user=user,
        name=name,
        category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
        subcategory="living_expenses",
        cashflow_role=AnnualExpenseEntry.CashflowRole.OPERATING,
        amount_annual=amount,
        fiscal_year=2026,
    )


class AssumptionSetSeedTests(TestCase):
    def test_seeded_assumption_sets_match_mvp_decision(self):
        expected = AssumptionSet.objects.get(name="expected")
        self.assertTrue(expected.is_default)
        self.assertEqual(expected.inflation_rate, Decimal("0.0250"))
        self.assertEqual(expected.productive_return_rate, Decimal("0.0500"))
        self.assertEqual(expected.non_productive_appreciation_rate, Decimal("0.0150"))
        self.assertEqual(expected.income_growth_rate, Decimal("0.0200"))
        self.assertEqual(expected.contribution_growth_rate, Decimal("0.0200"))
        self.assertEqual(expected.withdrawal_rate, Decimal("0.0350"))
        self.assertEqual(expected.default_liability_rate, Decimal("0.0450"))


class AssetClassificationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="plan_class", password="pass1234")

    def test_infers_override_and_subtracts_associated_debt(self):
        investment = create_investment(self.user, Decimal("50000.00"))
        home = Asset.objects.create(
            user=self.user,
            name="Casa",
            category=Asset.Category.REAL_ESTATE,
            subcategory=Asset.Subcategory.PRIMARY_HOME,
            amount=Decimal("200000.00"),
            currency="EUR",
        )
        Liability.objects.create(
            user=self.user,
            name="Hipoteca",
            category=Liability.Category.MORTGAGE,
            amount=Decimal("120000.00"),
            currency="EUR",
            financed_asset=home,
            is_asset_backed=True,
        )
        PlanAssetFunction.objects.create(
            user=self.user,
            asset=home,
            function=PlanAssetFunction.Function.PRODUCTIVE,
        )

        summary = AssetClassificationService().summarize(user=self.user, base_currency="EUR")

        self.assertEqual(summary.productive_capital, Decimal("130000.00000000"))
        self.assertEqual(summary.associated_liabilities, Decimal("120000.00000000"))
        self.assertEqual(summary.net_worth, Decimal("130000.00000000"))
        home_row = next(row for row in summary.assets if row.asset_id == home.id)
        self.assertEqual(home_row.inferred_function, PlanAssetFunction.Function.FAMILY_USE)
        self.assertEqual(home_row.function, PlanAssetFunction.Function.PRODUCTIVE)
        self.assertEqual(home_row.net_value, Decimal("80000.00000000"))
        investment_row = next(row for row in summary.assets if row.asset_id == investment.id)
        self.assertEqual(investment_row.function, PlanAssetFunction.Function.PRODUCTIVE)

    def test_uses_effective_value_not_raw_amount(self):
        # Activos con tracking contable guardan amount=0; el valor real llega
        # por market_value_override o saldos. La clasificación debe verlo.
        etf = Asset.objects.create(
            user=self.user,
            name="ETF contable",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.ETFS,
            amount=Decimal("0"),
            currency="EUR",
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            market_value_override=Decimal("1500.00"),
            market_value_override_date=timezone.localdate(),
        )

        summary = AssetClassificationService().summarize(user=self.user, base_currency="EUR")

        self.assertEqual(summary.productive_capital, Decimal("1500.00"))
        etf_row = next(row for row in summary.assets if row.asset_id == etf.id)
        self.assertEqual(etf_row.gross_value, Decimal("1500.00"))


class ProjectionFinancialCasesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="plan_projection", password="pass1234"
        )

    def calculate(self, plan):
        return ProjectionService().calculate(
            plan=plan,
            assumption_set=get_assumption_set(name="expected"),
        )

    def test_case_1_person_without_assets(self):
        plan = create_plan(self.user)

        result = self.calculate(plan)

        self.assertEqual(result["summary"]["productive_capital"]["value"], "0.00")
        self.assertGreater(Decimal(result["summary"]["target_capital"]["value"]), Decimal("0"))
        self.assertIsNone(result["summary"]["projected_year"]["value"])

    def test_case_2_investments_without_debt_project_a_date(self):
        create_investment(self.user, Decimal("900000.00"))
        plan = create_plan(self.user)

        result = self.calculate(plan)

        self.assertEqual(result["summary"]["productive_capital"]["value"], "900000.00")
        self.assertIsNotNone(result["summary"]["projected_year"]["value"])

    def test_case_3_primary_home_mortgage_stays_out_of_productive_capital(self):
        home = Asset.objects.create(
            user=self.user,
            name="Vivienda",
            category=Asset.Category.REAL_ESTATE,
            subcategory=Asset.Subcategory.PRIMARY_HOME,
            amount=Decimal("250000.00"),
            currency="EUR",
        )
        Liability.objects.create(
            user=self.user,
            name="Hipoteca",
            category=Liability.Category.MORTGAGE,
            amount=Decimal("150000.00"),
            currency="EUR",
            financed_asset=home,
            term_months=300,
        )
        plan = create_plan(self.user)

        result = self.calculate(plan)

        self.assertEqual(result["summary"]["productive_capital"]["value"], "0.00")
        self.assertEqual(result["classification"]["family_use_capital"], "100000.00")

    def test_case_4_couple_with_two_pensions_uses_future_income(self):
        plan = create_plan(self.user, household_type=FinancialPlan.HouseholdType.FAMILY)
        member_1 = FamilyMember.objects.create(
            user=self.user,
            name="Adulto 1",
            role=FamilyMember.Role.ADULT,
            pension_start_date=date(2045, 1, 1),
            estimated_monthly_pension_today_eur=Decimal("1200.00"),
        )
        member_2 = FamilyMember.objects.create(
            user=self.user,
            name="Adulto 2",
            role=FamilyMember.Role.ADULT,
            pension_start_date=date(2047, 1, 1),
            estimated_monthly_pension_today_eur=Decimal("800.00"),
        )
        plan.members.set([member_1, member_2])

        result = self.calculate(plan)

        self.assertLess(
            Decimal(result["summary"]["target_capital"]["value"]),
            Decimal("900000.00"),
        )

    def test_case_5_retirement_before_pension_creates_bridge_capital(self):
        plan = create_plan(self.user, target_date=date(2035, 1, 1))
        member = FamilyMember.objects.create(
            user=self.user,
            name="Adulto",
            role=FamilyMember.Role.ADULT,
            pension_start_date=date(2045, 1, 1),
            estimated_monthly_pension_today_eur=Decimal("1000.00"),
        )
        plan.members.add(member)

        target = Decimal(self.calculate(plan)["summary"]["target_capital"]["value"])
        no_bridge_plan = create_plan(
            get_user_model().objects.create_user(username="plan_no_bridge", password="pass1234"),
            target_date=date(2046, 1, 1),
        )
        no_bridge_member = FamilyMember.objects.create(
            user=no_bridge_plan.user,
            name="Adulto",
            role=FamilyMember.Role.ADULT,
            pension_start_date=date(2045, 1, 1),
            estimated_monthly_pension_today_eur=Decimal("1000.00"),
        )
        no_bridge_plan.members.add(no_bridge_member)
        no_bridge_target = Decimal(
            self.calculate(no_bridge_plan)["summary"]["target_capital"]["value"]
        )

        self.assertGreater(target, no_bridge_target)

    def test_case_6_high_emergency_fund_counts_as_security_capital(self):
        Asset.objects.create(
            user=self.user,
            name="Fondo emergencia",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            amount=Decimal("30000.00"),
            currency="EUR",
        )
        plan = create_plan(self.user)

        result = self.calculate(plan)

        self.assertEqual(result["summary"]["security_capital"]["value"], "30000.00")

    def test_case_7_car_purchase_as_existing_base_data(self):
        car = Asset.objects.create(
            user=self.user,
            name="Coche",
            category=Asset.Category.VEHICLE,
            subcategory=Asset.Subcategory.VEHICLES,
            amount=Decimal("20000.00"),
            currency="EUR",
        )
        Liability.objects.create(
            user=self.user,
            name="Prestamo coche",
            category=Liability.Category.PERSONAL_LOAN,
            amount=Decimal("12000.00"),
            currency="EUR",
            financed_asset=car,
            term_months=60,
        )
        plan = create_plan(self.user)

        result = self.calculate(plan)

        self.assertEqual(result["classification"]["family_use_capital"], "8000.00")

    def test_case_8_second_home_as_existing_base_data_is_productive(self):
        home = Asset.objects.create(
            user=self.user,
            name="Segunda vivienda",
            category=Asset.Category.REAL_ESTATE,
            subcategory=Asset.Subcategory.SECOND_HOME,
            amount=Decimal("180000.00"),
            currency="EUR",
        )
        Liability.objects.create(
            user=self.user,
            name="Hipoteca segunda vivienda",
            category=Liability.Category.MORTGAGE,
            amount=Decimal("100000.00"),
            currency="EUR",
            financed_asset=home,
            term_months=240,
        )
        plan = create_plan(self.user)

        result = self.calculate(plan)

        self.assertEqual(result["summary"]["productive_capital"]["value"], "80000.00")

    def test_case_9_sabbatical_as_base_income_drop(self):
        Asset.objects.create(
            user=self.user,
            name="Caja",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            amount=Decimal("5000.00"),
            currency="EUR",
        )
        create_income(self.user, Decimal("0.00"))
        create_operating_expense(self.user)
        plan = create_plan(self.user)

        result = self.calculate(plan)

        self.assertEqual(result["quality_level"], "medium")
        self.assertEqual(result["summary"]["productive_capital"]["value"], "0.00")

    def test_case_10_incompatible_preservation_target_blocks_projected_year(self):
        create_investment(self.user, Decimal("900000.00"))
        plan = create_plan(self.user, preservation_target_eur=Decimal("9000000.00"))

        result = self.calculate(plan)

        self.assertIsNone(result["summary"]["projected_year"]["value"])

    def test_preservation_target_adds_untouchable_capital_to_the_requirement(self):
        create_investment(self.user, Decimal("900000.00"))
        base_plan = create_plan(self.user)
        base = self.calculate(base_plan)

        preserving_user = get_user_model().objects.create_user(
            username="plan_preserving", password="pass1234"
        )
        create_investment(preserving_user, Decimal("900000.00"))
        preserving_plan = create_plan(preserving_user, preservation_target_eur=Decimal("100000.00"))
        preserving = self.calculate(preserving_plan)

        # El bloque preservado no financia la renta: se exige encima del objetivo.
        self.assertEqual(
            Decimal(preserving["summary"]["target_capital"]["value"]),
            Decimal(base["summary"]["target_capital"]["value"]) + Decimal("100000.00"),
        )
        # Y con el mismo capital, alcanzar la fecha cuesta más (nunca menos).
        base_year = base["summary"]["projected_year"]["value"]
        preserving_year = preserving["summary"]["projected_year"]["value"]
        if base_year is not None and preserving_year is not None:
            self.assertGreaterEqual(preserving_year, base_year)

    def test_determinism_same_inputs_same_hash_and_result(self):
        create_investment(self.user, Decimal("100000.00"))
        plan = create_plan(self.user)
        service = ProjectionService()

        result_1 = service.calculate(plan=plan, assumption_set=get_assumption_set(name="expected"))
        result_2 = service.calculate(plan=plan, assumption_set=get_assumption_set(name="expected"))

        self.assertEqual(result_1["input_hash"], result_2["input_hash"])
        self.assertEqual(result_1["summary"], result_2["summary"])
        self.assertEqual(result_1["trajectory"], result_2["trajectory"])

    def test_three_scenarios_share_schema(self):
        plan = create_plan(self.user)

        result = ProjectionService().calculate_all_scenarios(plan=plan)

        self.assertEqual(set(result), {"favorable", "prudent", "expected"})
        self.assertEqual(
            set(result["expected"]["summary"]),
            set(result["prudent"]["summary"]),
        )


class ProjectionInputCorrectnessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="plan_inputs", password="pass1234"
        )
        self.plan = create_plan(self.user)

    def test_foundations_only_use_active_fiscal_year(self):
        year = plan_fiscal_year(self.plan)
        create_income(self.user, Decimal("60000.00"))
        current = create_operating_expense(self.user, Decimal("12000.00"))
        current.fiscal_year = year
        current.save(update_fields=["fiscal_year"])
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Prestamo extinguido",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="loans",
            cashflow_role=AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT,
            time_profile=AnnualExpenseEntry.TimeProfile.TERM_RECURRENT,
            amount_annual=Decimal("90000.00"),
            fiscal_year=year - 1,
        )

        cash_flow = FoundationService().calculate(plan=self.plan)["cash_flow"]

        self.assertEqual(cash_flow["committed_surplus"], "48000.00")

    def test_committed_surplus_excludes_contributions_and_one_off_movements(self):
        """El superavit comprometido solo mide flujos recurrentes: ni las
        aportaciones de inversion ni los movimientos de balance puntuales (una
        cancelacion anticipada) deben restar. Ademas, la aportacion espejo no debe
        duplicarse en la aportacion planificada de la proyeccion."""
        year = plan_fiscal_year(self.plan)
        income = create_income(self.user, Decimal("60000.00"))
        income.fiscal_year = year
        income.save(update_fields=["fiscal_year"])
        operating = create_operating_expense(self.user, Decimal("12000.00"))
        operating.fiscal_year = year
        operating.save(update_fields=["fiscal_year"])

        asset = create_investment(self.user, name="Fondo aportado")
        InvestmentContributionInterval.objects.create(
            asset=asset,
            start_date=date(year, 1, 15),
            end_date=None,
            amount=Decimal("100.00"),
            frequency=Asset.InvestmentContributionFrequency.MONTHLY,
            currency="EUR",
        )
        # Espejo generado por el sistema de esa aportacion periodica (rol INVESTMENT).
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Aportacion inversion: Fondo aportado",
            category=AnnualExpenseEntry.Category.FINANCIAL_INVESTMENTS,
            subcategory="index_funds",
            cashflow_role=AnnualExpenseEntry.CashflowRole.INVESTMENT,
            time_profile=AnnualExpenseEntry.TimeProfile.STRUCTURAL_RECURRENT,
            amount_annual=Decimal("1300.00"),
            fiscal_year=year,
            is_system_generated=True,
            source_asset=asset,
        )
        # Cancelacion anticipada de principal: movimiento de balance puntual.
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Cancelacion anticipada principal: Hipoteca",
            category=AnnualExpenseEntry.Category.REAL_ESTATE_ASSETS,
            subcategory="mortgage_principal",
            cashflow_role=AnnualExpenseEntry.CashflowRole.TRANSFER,
            time_profile=AnnualExpenseEntry.TimeProfile.ONE_OFF,
            amount_annual=Decimal("15000.00"),
            fiscal_year=year,
            is_system_generated=True,
            event_group="liability_1_cancellation_principal",
        )

        cash_flow = FoundationService().calculate(plan=self.plan)["cash_flow"]
        self.assertEqual(cash_flow["committed_surplus"], "48000.00")

        # La aportacion se cuenta una sola vez (via el interval), no tambien via el espejo.
        self.assertEqual(planned_contribution_amount(plan=self.plan), Decimal("1200.00"))

    def test_committed_squeeze_transient_downgrades_finding_to_warning(self):
        """Base operativa positiva + compromiso temporal que vence pronto:
        esfuerzo temporal (recupera el año siguiente), finding a WARNING."""
        year = plan_fiscal_year(self.plan)
        income = create_income(self.user, Decimal("60000.00"))
        income.fiscal_year = year
        income.save(update_fields=["fiscal_year"])
        operating = create_operating_expense(self.user, Decimal("12000.00"))
        operating.fiscal_year = year
        operating.save(update_fields=["fiscal_year"])
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Cuota temporal",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="financial_commitments",
            cashflow_role=AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT,
            time_profile=AnnualExpenseEntry.TimeProfile.TERM_RECURRENT,
            term_end_year=year,
            amount_annual=Decimal("60000.00"),
            fiscal_year=year,
        )

        cash_flow = FoundationService().calculate(plan=self.plan)["cash_flow"]
        self.assertEqual(cash_flow["committed_status"], "transient")
        self.assertEqual(cash_flow["committed_recovery_year"], year + 1)

        finding = next(
            f
            for f in FindingService().evaluate(plan=self.plan)
            if f.code == Finding.Code.NEGATIVE_CASH_FLOW
        )
        self.assertEqual(finding.severity, Finding.Severity.WARNING)

    def test_committed_squeeze_structural_keeps_finding_critical(self):
        """Base operativa negativa (los gastos permanentes ya no caben): déficit
        estructural, sin año de recuperación, finding CRITICAL."""
        year = plan_fiscal_year(self.plan)
        income = create_income(self.user, Decimal("30000.00"))
        income.fiscal_year = year
        income.save(update_fields=["fiscal_year"])
        operating = create_operating_expense(self.user, Decimal("42000.00"))
        operating.fiscal_year = year
        operating.save(update_fields=["fiscal_year"])

        cash_flow = FoundationService().calculate(plan=self.plan)["cash_flow"]
        self.assertEqual(cash_flow["committed_status"], "structural")
        self.assertIsNone(cash_flow["committed_recovery_year"])

        finding = next(
            f
            for f in FindingService().evaluate(plan=self.plan)
            if f.code == Finding.Code.NEGATIVE_CASH_FLOW
        )
        self.assertEqual(finding.severity, Finding.Severity.CRITICAL)

    def test_foundations_expose_status_bands_for_scores(self):
        """Cada bloque puntuado publica su banda para que el frontend no invente umbrales."""
        year = plan_fiscal_year(self.plan)
        income = create_income(self.user, Decimal("60000.00"))
        income.fiscal_year = year
        income.save(update_fields=["fiscal_year"])
        expense = create_operating_expense(self.user, Decimal("12000.00"))
        expense.fiscal_year = year
        expense.save(update_fields=["fiscal_year"])

        payload = FoundationService().calculate(plan=self.plan)

        for block in ("cash_flow", "emergency_fund", "debt", "net_worth_health", "data_quality"):
            section = payload[block]
            self.assertIn(section["status"], {"good", "warning", "critical"}, block)
            expected = (
                "good"
                if section["score"] >= 70
                else "warning"
                if section["score"] >= 40
                else "critical"
            )
            self.assertEqual(section["status"], expected, block)

    def test_one_off_income_is_not_projected_and_labor_income_stops_at_target(self):
        year = plan_fiscal_year(self.plan)
        recurring = create_income(self.user, Decimal("36000.00"))
        recurring.fiscal_year = year
        recurring.save(update_fields=["fiscal_year"])
        AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Venta",
            category=AnnualIncomeEntry.Category.CAPITAL_GAINS,
            subcategory="capital_gains",
            time_profile=AnnualIncomeEntry.TimeProfile.ONE_OFF,
            income_type=AnnualIncomeEntry.IncomeType.ONE_OFF,
            amount_annual=Decimal("150000.00"),
            fiscal_year=year,
        )
        member = FamilyMember.objects.create(
            user=self.user,
            name="Adulto",
            role=FamilyMember.Role.ADULT,
            employment_income_end_date=date(year + 1, 12, 31),
        )
        self.plan.members.add(member)

        inputs, _, _ = build_projection_inputs(plan=self.plan)
        result = ProjectionService().calculate(
            plan=self.plan, assumption_set=get_assumption_set(name="expected")
        )

        self.assertEqual(inputs.annual_income, Decimal("36000.00"))
        row_at_target = next(
            row for row in result["trajectory"] if row["year"] == self.plan.target_date.year
        )
        self.assertEqual(row_at_target["future_income"], "0.00")

    def test_expense_taxonomy_is_exhaustive_for_declared_roles(self):
        for role, _label in AnnualExpenseEntry.CashflowRole.choices:
            for time_profile, _label in AnnualExpenseEntry.TimeProfile.choices:
                entry = AnnualExpenseEntry(cashflow_role=role, time_profile=time_profile)
                self.assertNotEqual(expense_bucket(entry), ExpenseBucket.UNCLASSIFIABLE)

    def test_projection_respects_target_and_configured_pension_dates(self):
        member = FamilyMember.objects.create(
            user=self.user,
            name="Adulto",
            role=FamilyMember.Role.ADULT,
            birth_date=date(1982, 2, 28),
            employment_income_end_date=date(2040, 1, 1),
            pension_start_date=date(2041, 1, 1),
        )
        self.plan.members.add(member)

        inputs, _, _ = build_projection_inputs(plan=self.plan)

        self.assertEqual(inputs.employment_income_end_date, self.plan.target_date)
        self.assertEqual(inputs.earliest_pension_start_date, date(2041, 1, 1))

    def test_projection_net_worth_reconciles_with_real_when_debt_is_asset_backed(self):
        """La deuda asociada se netea en los buckets; la proyección no debe
        restarla otra vez (si no, el patrimonio proyectado arranca por debajo del real)."""
        home = Asset.objects.create(
            user=self.user,
            name="Segunda vivienda",
            category=Asset.Category.REAL_ESTATE,
            subcategory=Asset.Subcategory.SECOND_HOME,
            amount=Decimal("200000.00"),
            currency="EUR",
        )
        Liability.objects.create(
            user=self.user,
            name="Hipoteca",
            category=Liability.Category.MORTGAGE,
            amount=Decimal("120000.00"),
            currency="EUR",
            financed_asset=home,
            is_asset_backed=True,
        )
        classification = AssetClassificationService().summarize(user=self.user, base_currency="EUR")
        self.assertEqual(classification.associated_liabilities, Decimal("120000.00000000"))

        result = ProjectionService().calculate(
            plan=self.plan, assumption_set=get_assumption_set(name="expected")
        )
        first_year = result["trajectory"][0]
        self.assertEqual(Decimal(first_year["net_worth"]), classification.net_worth)

    def test_sustainable_retirement_is_now_when_capital_is_ample(self):
        # Mucho capital productivo y nivel de vida bajo: se puede parar ya.
        create_investment(self.user, Decimal("5000000.00"))
        inputs, _, _ = build_projection_inputs(plan=self.plan)
        assumptions = serialize_assumptions(get_assumption_set(name="expected"))

        year = earliest_sustainable_retirement_year(inputs=inputs, assumptions=assumptions)

        self.assertEqual(year, date.today().year)

    def test_sustainable_retirement_is_none_when_never_feasible(self):
        # Sin capital ni ingresos, con nivel de vida objetivo, no hay retiro sostenible.
        inputs, _, _ = build_projection_inputs(plan=self.plan)
        assumptions = serialize_assumptions(get_assumption_set(name="expected"))

        year = earliest_sustainable_retirement_year(inputs=inputs, assumptions=assumptions)

        self.assertIsNone(year)

    def test_retirement_year_override_drives_projection_without_mutating_plan(self):
        create_investment(self.user, Decimal("500000.00"))
        result = ProjectionService().calculate(
            plan=self.plan,
            assumption_set=get_assumption_set(name="expected"),
            retirement_year=2050,
        )

        self.assertEqual(result["summary"]["target_year"]["value"], 2050)
        # No se muta la aspiración del usuario.
        self.assertEqual(self.plan.target_date, date(2040, 1, 1))


class PlanApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="plan_api", password="pass1234")
        self.other = get_user_model().objects.create_user(
            username="plan_other", password="pass1234"
        )
        self.client.force_authenticate(self.user)

    def payload(self, **overrides):
        data = {
            "household_type": "single",
            "target_date": "2040-01-01",
            "target_monthly_income_today_eur": "2000.00",
            "projection_end_date": "2065-01-01",
            "profile": "balanced",
        }
        data.update(overrides)
        return data

    def test_post_is_idempotent(self):
        response_1 = self.client.post(reverse("financial-plan"), self.payload(), format="json")
        response_2 = self.client.post(
            reverse("financial-plan"),
            self.payload(target_monthly_income_today_eur="2500.00"),
            format="json",
        )

        self.assertEqual(response_1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response_2.status_code, status.HTTP_200_OK)
        self.assertEqual(FinancialPlan.objects.filter(user=self.user).count(), 1)
        self.assertEqual(response_2.data["target_monthly_income_today_eur"], "2500.00")

    def test_recalculate_persists_snapshot(self):
        create_plan(self.user)

        response = self.client.post(reverse("financial-plan-recalculate"), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(ProjectionSnapshot.objects.filter(plan__user=self.user).count(), 1)
        self.assertIn("assumptions", response.data)

    def test_member_linking_is_user_scoped(self):
        other_member = FamilyMember.objects.create(
            user=self.other,
            name="Otro",
            role=FamilyMember.Role.ADULT,
        )

        response = self.client.post(
            reverse("financial-plan"),
            self.payload(member_ids=[other_member.id]),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_asset_function_override_is_user_scoped(self):
        own_asset = create_investment(self.user, Decimal("1000.00"))
        other_asset = create_investment(self.other, Decimal("1000.00"))

        response = self.client.put(
            reverse("financial-plan-asset-functions"),
            [
                {"asset_id": own_asset.id, "function": "security"},
                {"asset_id": other_asset.id, "function": "productive"},
            ],
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            PlanAssetFunction.objects.filter(user=self.user, asset=other_asset).exists()
        )

    def test_member_retirement_is_saved_from_birth_date(self):
        create_plan(self.user)

        response = self.client.post(
            reverse("financial-plan-members"),
            {
                "name": "Adulto",
                "role": "adult",
                "is_active": True,
                "birth_date": "1980-06-15",
                "employment_end_age": 60,
                "pension_start_age": 65,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["employment_income_end_date"], "2040-06-15")
        self.assertEqual(response.data["pension_start_date"], "2045-06-15")

    def test_member_update_reuses_existing_adult_identity(self):
        plan = create_plan(self.user)
        canonical = FamilyMember.objects.create(
            user=self.user,
            name="Pablo",
            role=FamilyMember.Role.ADULT,
        )
        draft = FamilyMember.objects.create(
            user=self.user,
            name="Pablo Test",
            role=FamilyMember.Role.ADULT,
        )
        plan.members.add(draft)

        response = self.client.patch(
            reverse("financial-plan-member-detail", args=[draft.id]),
            {
                "name": "Pablo",
                "birth_date": "1980-06-15",
                "employment_end_age": 60,
                "pension_start_age": 65,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], canonical.id)
        self.assertEqual(response.data["employment_income_end_date"], "2040-06-15")
        self.assertEqual(response.data["pension_start_date"], "2045-06-15")
        self.assertEqual(list(plan.members.values_list("id", flat=True)), [canonical.id])
        self.assertTrue(FamilyMember.objects.filter(id=draft.id, name="Pablo Test").exists())


class ScenarioServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="plan_scenario", password="pass1234"
        )
        create_investment(self.user, Decimal("100000.00"))
        Asset.objects.create(
            user=self.user,
            name="Caja",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            amount=Decimal("6000.00"),
            currency="EUR",
        )
        self.plan = create_plan(self.user)

    def create_vehicle_scenario(self):
        scenario = Scenario.objects.create(
            plan=self.plan,
            name="Comprar coche",
            template_type=Scenario.TemplateType.VEHICLE,
        )
        scenario.events.create(
            start_date=date(2028, 3, 1),
            initial_outflow=Decimal("10000.00"),
            monthly_expense_delta=Decimal("250.00"),
            new_asset_value=Decimal("25000.00"),
            new_asset_type=PlanAssetFunction.Function.FAMILY_USE,
            new_debt_principal=Decimal("15000.00"),
            new_debt_interest_rate=Decimal("0.0700"),
            new_debt_term_months=60,
        )
        return scenario

    def test_comparison_creates_only_non_official_snapshot_and_does_not_mutate_plan(self):
        scenario = self.create_vehicle_scenario()

        result = ScenarioService().compare(scenario=scenario)

        self.assertEqual(result["scenario"]["id"], scenario.id)
        self.assertEqual(PlanEvent.objects.count(), 0)
        self.assertEqual(AnnualExpenseEntry.objects.count(), 0)
        snapshot = ProjectionSnapshot.objects.get(scenario=scenario)
        self.assertFalse(snapshot.is_official)

    def test_comparison_reports_the_sustainable_retirement_year(self):
        # La tabla compara la misma fecha que titula el plan. `projected_year` responde
        # a otra pregunta y en un plan que aún no llega se queda clavada, así que la
        # comparación decía "sin variación" mientras el resto de métricas se movían.
        scenario = self.create_vehicle_scenario()

        result = ScenarioService().compare(scenario=scenario)

        self.assertIn("sustainable_year", result)
        self.assertEqual(set(result["sustainable_year"]), {"current", "simulated"})
        current = result["sustainable_year"]["current"]
        simulated = result["sustainable_year"]["simulated"]
        if current is not None and simulated is not None:
            self.assertEqual(result["delta"]["sustainable_year"], simulated - current)
        else:
            self.assertIsNone(result["delta"]["sustainable_year"])

    def test_accept_creates_plan_event_official_snapshot_and_budget_entries(self):
        scenario = self.create_vehicle_scenario()

        result = ScenarioService().accept(scenario=scenario)

        scenario.refresh_from_db()
        self.assertEqual(scenario.status, Scenario.Status.ACCEPTED)
        self.assertEqual(PlanEvent.objects.filter(plan=self.plan).count(), 1)
        self.assertGreaterEqual(result["budget_entries_created"], 3)
        self.assertTrue(
            ProjectionSnapshot.objects.filter(plan=self.plan, is_official=True).exists()
        )
        self.assertTrue(
            AnnualExpenseEntry.objects.filter(
                user=self.user,
                fiscal_year=2028,
                category=AnnualExpenseEntry.Category.TANGIBLE_ASSETS,
                subcategory="vehicle_purchase",
                amount_annual=Decimal("10000.00"),
            ).exists()
        )
        self.assertTrue(
            AnnualExpenseEntry.objects.filter(
                user=self.user,
                category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
                subcategory="personal_loan_repayment",
                term_start_month=3,
            ).exists()
        )

    def test_accept_keeps_multiple_one_off_expenses_separate(self):
        scenario = Scenario.objects.create(
            plan=self.plan,
            name="Comprar casa",
            template_type=Scenario.TemplateType.HOUSING,
        )
        scenario.events.create(
            start_date=date(2028, 5, 1),
            initial_outflow=Decimal("45000.00"),
            metadata_json={
                "one_off_items": [
                    {"name": "Entrada", "amount": "30000.00"},
                    {"name": "Impuestos", "amount": "10000.00"},
                    {"name": "Muebles", "amount": "5000.00"},
                ]
            },
        )

        result = ScenarioService().accept(scenario=scenario)

        expenses = AnnualExpenseEntry.objects.filter(
            event_group=f"plan_event:{result['event'].id}"
        ).order_by("name")
        self.assertEqual(expenses.count(), 3)
        self.assertEqual(
            sum((row.amount_annual for row in expenses), Decimal("0")), Decimal("45000")
        )
        self.assertEqual(
            set(expenses.values_list("name", flat=True)),
            {"Comprar casa - Entrada", "Comprar casa - Impuestos", "Comprar casa - Muebles"},
        )
        self.assertTrue(
            all(
                expense_bucket(entry) != ExpenseBucket.UNCLASSIFIABLE
                for entry in AnnualExpenseEntry.objects.filter(user=self.user)
            )
        )

    def test_accept_clips_budget_line_terms_to_their_fiscal_year(self):
        scenario = self.create_vehicle_scenario()

        ScenarioService().accept(scenario=scenario)

        financing = AnnualExpenseEntry.objects.filter(
            user=self.user, subcategory="personal_loan_repayment"
        ).order_by("fiscal_year")
        # 60 meses desde 2028-03 -> fin 2033-02: una línea por año, sin solaparse.
        self.assertEqual(
            list(financing.values_list("fiscal_year", flat=True)),
            [2028, 2029, 2030, 2031, 2032, 2033],
        )
        for entry in financing:
            self.assertEqual(entry.term_end_year, entry.fiscal_year)
            self.assertEqual(entry.time_profile, AnnualExpenseEntry.TimeProfile.TERM_RECURRENT)
        first, last = financing.first(), financing.last()
        self.assertEqual((first.term_start_month, first.term_end_month), (3, 12))
        self.assertEqual((last.term_start_month, last.term_end_month), (1, 2))

    def test_vehicle_recurring_expense_is_indefinite_without_end_date(self):
        scenario = self.create_vehicle_scenario()

        ScenarioService().accept(scenario=scenario)

        recurring = AnnualExpenseEntry.objects.filter(
            user=self.user, subcategory="transport_mobility"
        ).order_by("fiscal_year")
        # El coste de uso no termina con el préstamo: año parcial + estructural.
        self.assertEqual(recurring.count(), 2)
        partial, structural = recurring.first(), recurring.last()
        self.assertEqual(partial.fiscal_year, 2028)
        self.assertEqual((partial.term_start_month, partial.term_end_year), (3, 2028))
        self.assertEqual(partial.amount_annual, Decimal("2500.00"))
        self.assertEqual(structural.fiscal_year, 2029)
        self.assertEqual(
            structural.time_profile, AnnualExpenseEntry.TimeProfile.STRUCTURAL_RECURRENT
        )
        self.assertIsNone(structural.term_end_year)
        self.assertEqual(structural.amount_annual, Decimal("3000.00"))

    def test_accept_indefinite_recurring_creates_structural_line(self):
        scenario = Scenario.objects.create(
            plan=self.plan,
            name="Aportar mas",
            template_type=Scenario.TemplateType.GENERIC,
        )
        scenario.events.create(
            start_date=date(2028, 3, 1),
            monthly_contribution_delta=Decimal("100.00"),
        )

        ScenarioService().accept(scenario=scenario)

        contributions = AnnualExpenseEntry.objects.filter(
            user=self.user, subcategory="other_financial_investments"
        ).order_by("fiscal_year")
        self.assertEqual(contributions.count(), 2)
        partial, structural = contributions.first(), contributions.last()
        # Año inicial parcial: término mar-dic del propio año.
        self.assertEqual(partial.fiscal_year, 2028)
        self.assertEqual(partial.time_profile, AnnualExpenseEntry.TimeProfile.TERM_RECURRENT)
        self.assertEqual((partial.term_start_month, partial.term_end_year), (3, 2028))
        self.assertEqual(partial.amount_annual, Decimal("1000.00"))
        # Desde el siguiente año completo: estructural indefinida.
        self.assertEqual(structural.fiscal_year, 2029)
        self.assertEqual(
            structural.time_profile, AnnualExpenseEntry.TimeProfile.STRUCTURAL_RECURRENT
        )
        self.assertIsNone(structural.term_end_year)
        self.assertEqual(structural.amount_annual, Decimal("1200.00"))

    def test_accepted_plan_event_affects_future_projection(self):
        scenario = self.create_vehicle_scenario()
        before = ProjectionService().calculate(
            plan=self.plan,
            assumption_set=get_assumption_set(name="expected"),
        )

        ScenarioService().accept(scenario=scenario)

        after = ProjectionService().calculate(
            plan=self.plan,
            assumption_set=get_assumption_set(name="expected"),
        )
        before_2028 = next(row for row in before["trajectory"] if row["year"] == 2028)
        after_2028 = next(row for row in after["trajectory"] if row["year"] == 2028)
        self.assertGreater(
            Decimal(after_2028["liabilities"]),
            Decimal(before_2028["liabilities"]),
        )

    def test_close_event_retires_budget_lines_and_stops_future_deltas(self):
        scenario = self.create_vehicle_scenario()
        accepted = ScenarioService().accept(scenario=scenario)
        event = accepted["event"]
        financing_before = AnnualExpenseEntry.objects.get(
            event_group=f"plan_event:{event.id}",
            fiscal_year=2030,
            subcategory="personal_loan_repayment",
        ).amount_annual

        result = close_plan_event(
            event=event,
            effective_date=date(2030, 7, 1),
            disposal_note="Venta del coche",
        )

        event.refresh_from_db()
        self.assertEqual(event.effective_end_date, date(2030, 7, 1))
        self.assertEqual(event.actual_impact_json["closure"]["note"], "Venta del coche")
        self.assertTrue(result["budget_changes"]["changed"])
        self.assertTrue(result["budget_changes"]["deleted"])
        self.assertFalse(
            AnnualExpenseEntry.objects.filter(
                event_group=f"plan_event:{event.id}", fiscal_year__gt=2030
            ).exists()
        )
        partial = AnnualExpenseEntry.objects.get(
            event_group=f"plan_event:{event.id}",
            fiscal_year=2030,
            subcategory="transport_mobility",
        )
        self.assertEqual(partial.term_end_month, 6)
        self.assertEqual(partial.amount_annual, Decimal("1500.00"))
        financing_after = AnnualExpenseEntry.objects.get(
            event_group=f"plan_event:{event.id}",
            fiscal_year=2030,
            subcategory="personal_loan_repayment",
        )
        self.assertEqual(financing_after.term_end_month, 6)
        self.assertEqual(financing_after.amount_annual, financing_before / 2)
        self.assertTrue(
            AnnualExpenseEntry.objects.filter(
                event_group=f"plan_event:{event.id}", fiscal_year=2028
            ).exists()
        )
        payload = next(item for item in result["projection"]["trajectory"] if item["year"] == 2031)
        baseline = ProjectionService().calculate(
            plan=self.plan,
            assumption_set=get_assumption_set(name="expected"),
            include_plan_events=False,
        )
        baseline_row = next(item for item in baseline["trajectory"] if item["year"] == 2031)
        self.assertEqual(payload["annual_target_income"], baseline_row["annual_target_income"])

        with self.assertRaisesMessage(Exception, "ya está cerrado"):
            close_plan_event(event=event, effective_date=date(2031, 1, 1))


class ScenarioApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="plan_scenario_api", password="pass1234"
        )
        self.other = get_user_model().objects.create_user(
            username="plan_scenario_other", password="pass1234"
        )
        self.plan = create_plan(self.user)
        self.other_plan = create_plan(self.other)
        self.client.force_authenticate(self.user)

    def scenario_payload(self):
        return {
            "name": "Comprar coche",
            "template_type": "vehicle",
            "events": [
                {
                    "start_date": "2028-03-01",
                    "initial_outflow": "10000.00",
                    "monthly_expense_delta": "250.00",
                    "new_asset_value": "25000.00",
                    "new_asset_type": "family_use",
                    "new_debt_principal": "15000.00",
                    "new_debt_interest_rate": "0.0700",
                    "new_debt_term_months": 60,
                    "metadata_json": {},
                }
            ],
        }

    def test_create_compare_and_accept_scenario(self):
        create_response = self.client.post(
            reverse("financial-plan-scenarios"),
            self.scenario_payload(),
            format="json",
        )
        scenario_id = create_response.data["id"]

        compare_response = self.client.get(
            reverse("financial-plan-scenario-comparison", kwargs={"pk": scenario_id})
        )
        accept_response = self.client.post(
            reverse("financial-plan-scenario-accept", kwargs={"pk": scenario_id}),
            {},
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(compare_response.status_code, status.HTTP_200_OK)
        self.assertIn("simulated", compare_response.data)
        self.assertEqual(accept_response.status_code, status.HTTP_200_OK)
        self.assertEqual(accept_response.data["event"]["event_type"], "vehicle")

    def test_one_off_items_define_the_canonical_initial_outflow(self):
        payload = self.scenario_payload()
        payload["events"][0]["initial_outflow"] = "1.00"
        payload["events"][0]["metadata_json"] = {
            "one_off_items": [
                {"name": "Entrada", "amount": "10000.00"},
                {"name": "Impuestos", "amount": "2500.00"},
            ]
        }

        response = self.client.post(reverse("financial-plan-scenarios"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["events"][0]["initial_outflow"], "12500.00")

    def test_scenarios_are_user_scoped(self):
        other_scenario = Scenario.objects.create(
            plan=self.other_plan,
            name="Otro",
            template_type=Scenario.TemplateType.GENERIC,
        )

        response = self.client.get(
            reverse("financial-plan-scenario-detail", kwargs={"pk": other_scenario.id})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_plan_budget_lines_are_traceable_and_protected(self):
        create_response = self.client.post(
            reverse("financial-plan-scenarios"), self.scenario_payload(), format="json"
        )
        accept_response = self.client.post(
            reverse("financial-plan-scenario-accept", kwargs={"pk": create_response.data["id"]}),
            {},
            format="json",
        )
        event_id = accept_response.data["event"]["id"]
        trace = self.client.get(
            reverse("financial-plan-event-budget-lines", kwargs={"pk": event_id})
        )
        expense = AnnualExpenseEntry.objects.filter(event_group=f"plan_event:{event_id}").first()

        self.assertEqual(trace.status_code, status.HTTP_200_OK)
        self.assertEqual(trace.data["event"], {"id": event_id, "name": "Comprar coche"})
        self.assertEqual(
            len(trace.data["expenses"]),
            AnnualExpenseEntry.objects.filter(event_group=f"plan_event:{event_id}").count(),
        )
        self.assertTrue(trace.data["expenses"][0]["is_plan_managed"])
        self.assertEqual(trace.data["expenses"][0]["plan_event_id"], event_id)

        update = self.client.patch(
            reverse("annual-expense-detail", kwargs={"pk": expense.id}),
            {"amount_annual": "1.00"},
            format="json",
        )
        delete = self.client.delete(reverse("annual-expense-detail", kwargs={"pk": expense.id}))
        self.assertEqual(update.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(update.data["error"]["code"], "plan_managed_entry")
        self.assertEqual(delete.status_code, status.HTTP_403_FORBIDDEN)

    def test_budget_line_trace_is_user_scoped(self):
        event = PlanEvent.objects.create(
            plan=self.other_plan,
            name="Privado",
            event_type=Scenario.TemplateType.GENERIC,
            planned_date=date.today(),
        )

        response = self.client.get(
            reverse("financial-plan-event-budget-lines", kwargs={"pk": event.id})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_close_event_endpoint_is_user_scoped(self):
        event = PlanEvent.objects.create(
            plan=self.other_plan,
            name="Privado",
            event_type=Scenario.TemplateType.GENERIC,
            planned_date=date(2028, 1, 1),
        )

        response = self.client.post(
            reverse("financial-plan-event-close", kwargs={"pk": event.id}),
            {"effective_date": "2030-01-01"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class FindingsRecommendationsApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="plan_findings_api", password="pass1234"
        )
        self.client.force_authenticate(self.user)
        self.plan = create_plan(self.user)
        create_income(self.user, Decimal("30000.00"))
        create_operating_expense(self.user, Decimal("36000.00"))
        Liability.objects.create(
            user=self.user,
            name="Tarjeta",
            category=Liability.Category.CREDIT_CARD,
            amount=Decimal("2500.00"),
            currency="EUR",
            annual_interest_tae=Decimal("19.00"),
            is_asset_backed=False,
        )

    def test_foundations_findings_and_recommendations_are_exposed(self):
        foundations = self.client.get(reverse("financial-plan-foundations"))
        findings = self.client.get(reverse("financial-plan-findings"))
        recommendations = self.client.get(reverse("financial-plan-recommendations"))

        self.assertEqual(foundations.status_code, status.HTTP_200_OK)
        self.assertIn("cash_flow", foundations.data)
        self.assertEqual(findings.status_code, status.HTTP_200_OK)
        self.assertTrue(
            any(item["code"] == Finding.Code.NEGATIVE_CASH_FLOW for item in findings.data)
        )
        self.assertEqual(recommendations.status_code, status.HTTP_200_OK)
        self.assertTrue(
            any(
                item["code"] == Recommendation.Code.RESTORE_CASH_FLOW
                for item in recommendations.data
            )
        )

    def test_recommendation_simulate_creates_draft_scenario_for_same_user(self):
        recommendations = self.client.get(reverse("financial-plan-recommendations"))
        recommendation_id = next(
            item["id"] for item in recommendations.data if item["action_json"].get("scenario_event")
        )

        response = self.client.post(
            reverse("financial-plan-recommendation-simulate", kwargs={"pk": recommendation_id}),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], Scenario.Status.DRAFT)
        scenario = Scenario.objects.get(id=response.data["id"])
        self.assertEqual(scenario.plan, self.plan)
        self.assertEqual(scenario.source_recommendation_id, recommendation_id)

    def test_refresh_preserves_dismissed_recommendation(self):
        recommendations = self.client.get(reverse("financial-plan-recommendations"))
        recommendation_id = recommendations.data[0]["id"]
        self.client.post(
            reverse(
                "financial-plan-recommendation-dismiss",
                kwargs={"pk": recommendation_id},
            )
        )

        self.client.get(reverse("financial-plan-recommendations"))

        self.assertEqual(
            Recommendation.objects.get(id=recommendation_id).status,
            Recommendation.Status.DISMISSED,
        )

    def test_preview_has_no_side_effects(self):
        recommendations = self.client.get(reverse("financial-plan-recommendations"))
        recommendation_id = next(
            item["id"] for item in recommendations.data if item["action_json"].get("scenario_event")
        )
        before = (
            Scenario.objects.count(),
            ProjectionSnapshot.objects.count(),
            AnnualExpenseEntry.objects.count(),
        )

        response = self.client.get(
            reverse(
                "financial-plan-recommendation-preview",
                kwargs={"pk": recommendation_id},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["actionable"])
        self.assertIn("before", response.data)
        self.assertIn("after", response.data)
        self.assertEqual(
            (
                Scenario.objects.count(),
                ProjectionSnapshot.objects.count(),
                AnnualExpenseEntry.objects.count(),
            ),
            before,
        )

    def test_snooze_is_persistent_and_user_scoped(self):
        recommendations = self.client.get(reverse("financial-plan-recommendations"))
        recommendation_id = recommendations.data[0]["id"]
        until = timezone.localdate() + timedelta(days=30)

        response = self.client.post(
            reverse(
                "financial-plan-recommendation-snooze",
                kwargs={"pk": recommendation_id},
            ),
            {"snoozed_until": until.isoformat()},
            format="json",
        )
        self.client.get(reverse("financial-plan-recommendations"))

        recommendation = Recommendation.objects.get(id=recommendation_id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(recommendation.status, Recommendation.Status.SNOOZED)
        self.assertEqual(recommendation.snoozed_until, until)

    def test_overview_uses_profile_default_and_returns_guidance(self):
        self.plan.profile = FinancialPlan.Profile.SECURITY
        self.plan.save(update_fields=["profile"])

        response = self.client.get(reverse("financial-plan-overview"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["scenario"], "prudent")
        self.assertIn(
            response.data["status"],
            {
                "on_track",
                "off_track",
                "unreachable",
                "incomplete",
            },
        )
        self.assertIn("range", response.data)
        self.assertIn("desired_year", response.data)
        self.assertIn("sustainable_year", response.data)
        self.assertIn("sustainable_range", response.data)
        self.assertIn("gap_years", response.data)
        self.assertIn("foundations", response.data)
        self.assertIn("next_action", response.data)


class OccurredEventTests(TestCase):
    """Decisiones ya tomadas: registrar sin duplicar presupuesto ni proyeccion."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="plan_occurred", password="pass1234"
        )
        create_investment(self.user, Decimal("100000.00"))
        create_income(self.user)
        create_operating_expense(self.user)
        self.plan = create_plan(self.user)
        self.line = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Tratamiento - cuota",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="family_childcare",
            cashflow_role=AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT,
            expense_type=AnnualExpenseEntry.ExpenseType.RECURRENT,
            time_profile=AnnualExpenseEntry.TimeProfile.TERM_RECURRENT,
            term_start_month=1,
            term_end_year=2027,
            term_end_month=1,
            amount_annual=Decimal("7297.56"),
            fiscal_year=2026,
        )

    def register(self, **overrides):
        payload = {
            "plan": self.plan,
            "name": "Clinica",
            "event_type": Scenario.TemplateType.GENERIC,
            "decision_date": date(2024, 2, 5),
            "expense_entry_ids": [self.line.id],
        }
        payload.update(overrides)
        return register_occurred_event(**payload)

    def test_registers_event_as_occurred_and_adopts_existing_lines(self):
        event = self.register(note="Decidido en febrero")

        self.line.refresh_from_db()
        self.assertEqual(event.status, PlanEvent.Status.OCCURRED)
        self.assertEqual(event.actual_date, date(2024, 2, 5))
        self.assertEqual(self.line.event_group, f"plan_event:{event.id}")
        adopted = event.actual_impact_json["registration"]["adopted_lines"]
        self.assertEqual([line["id"] for line in adopted], [self.line.id])
        self.assertEqual(adopted[0]["previous_event_group"], "")

    def test_does_not_create_budget_entries(self):
        before = AnnualExpenseEntry.objects.filter(user=self.user).count()

        self.register()

        self.assertEqual(AnnualExpenseEntry.objects.filter(user=self.user).count(), before)

    def test_is_excluded_from_the_projection(self):
        service = ProjectionService()
        assumptions = get_assumption_set(name="expected")
        before = service.calculate(plan=self.plan, assumption_set=assumptions)

        self.register()

        after = service.calculate(plan=self.plan, assumption_set=assumptions)
        self.assertEqual(after["input_hash"], before["input_hash"])
        self.assertEqual(after["trajectory"], before["trajectory"])
        self.assertEqual(after["summary"], before["summary"])

    def test_rejects_a_future_decision_date(self):
        with self.assertRaises(DRFValidationError):
            self.register(decision_date=date.today() + timedelta(days=1))

    def test_rejects_lines_already_owned_by_another_event(self):
        self.register()

        with self.assertRaises(DRFValidationError):
            self.register(name="Otra decision")

    def test_rejects_lines_from_another_user(self):
        other = get_user_model().objects.create_user(username="plan_other", password="pass1234")
        foreign = create_operating_expense(other, name="Ajena")

        with self.assertRaises(DRFValidationError):
            self.register(expense_entry_ids=[foreign.id])

    def test_rejects_lines_generated_by_a_liability(self):
        """Adoptarlas rompería la sincronizacion del pasivo, que busca por su event_group."""
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo",
            category=Liability.Category.PERSONAL_LOAN,
            amount=Decimal("10000.00"),
            currency="EUR",
        )
        generated = AnnualExpenseEntry.objects.create(
            user=self.user,
            source_liability=liability,
            is_system_generated=True,
            name="Compromiso pasivo: Prestamo",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="personal_loan_repayment",
            cashflow_role=AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT,
            event_group=f"liability_{liability.id}",
            amount_annual=Decimal("2400.00"),
            fiscal_year=2026,
        )

        with self.assertRaises(DRFValidationError):
            self.register(expense_entry_ids=[generated.id])

        generated.refresh_from_db()
        self.assertEqual(generated.event_group, f"liability_{liability.id}")

    def test_links_assets_and_liabilities_without_touching_their_budget_lines(self):
        """Enlazar, no adoptar: Patrimonio sigue generando (y gobernando) sus lineas."""
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo FIV",
            category=Liability.Category.PERSONAL_LOAN,
            amount=Decimal("14000.00"),
            currency="EUR",
        )
        generated = AnnualExpenseEntry.objects.create(
            user=self.user,
            source_liability=liability,
            is_system_generated=True,
            name="Compromiso pasivo: Prestamo FIV",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="financial_commitments",
            cashflow_role=AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT,
            event_group=f"liability_{liability.id}",
            amount_annual=Decimal("7297.56"),
            fiscal_year=2026,
        )

        event = self.register(liability_ids=[liability.id])

        generated.refresh_from_db()
        self.assertEqual(list(event.linked_liabilities.all()), [liability])
        self.assertEqual(generated.event_group, f"liability_{liability.id}")
        linked = event.actual_impact_json["registration"]["linked"]
        self.assertEqual(linked["liabilities"], [{"id": liability.id, "name": "Prestamo FIV"}])

    def test_rejects_net_worth_from_another_user(self):
        other = get_user_model().objects.create_user(username="plan_nw_other", password="pass1234")
        foreign = create_investment(other, name="Ajeno")

        with self.assertRaises(DRFValidationError):
            self.register(asset_ids=[foreign.id])

    def test_release_restores_the_previous_group_and_deletes_the_event(self):
        self.line.event_group = "compra_atrio"
        self.line.save(update_fields=["event_group"])
        event = self.register()

        result = release_occurred_event(event=event)

        self.line.refresh_from_db()
        self.assertEqual(self.line.event_group, "compra_atrio")
        self.assertEqual(len(result["released_lines"]), 1)
        self.assertFalse(PlanEvent.objects.filter(id=event.id).exists())

    def test_release_refuses_a_planned_event(self):
        event = PlanEvent.objects.create(
            plan=self.plan,
            name="Coche",
            event_type=Scenario.TemplateType.VEHICLE,
            planned_date=date(2028, 3, 1),
            status=PlanEvent.Status.PLANNED,
        )

        with self.assertRaises(DRFValidationError):
            release_occurred_event(event=event)


class OccurredEventApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="plan_occurred_api", password="pass1234"
        )
        self.other = get_user_model().objects.create_user(
            username="plan_occurred_other", password="pass1234"
        )
        self.plan = create_plan(self.user)
        create_plan(self.other)
        self.line = create_operating_expense(self.user, name="Cuota clinica")
        self.client.force_authenticate(self.user)

    def test_registers_an_occurred_decision(self):
        response = self.client.post(
            reverse("financial-plan-event-occurred"),
            {
                "name": "Clinica",
                "event_type": "generic",
                "decision_date": "2024-02-05",
                "expense_entry_ids": [self.line.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], PlanEvent.Status.OCCURRED)
        self.line.refresh_from_db()
        self.assertEqual(self.line.event_group, f"plan_event:{response.data['id']}")

    def test_cannot_adopt_a_line_from_another_user(self):
        foreign = create_operating_expense(self.other, name="Ajena")

        response = self.client.post(
            reverse("financial-plan-event-occurred"),
            {
                "name": "Clinica",
                "event_type": "generic",
                "decision_date": "2024-02-05",
                "expense_entry_ids": [foreign.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        foreign.refresh_from_db()
        self.assertEqual(foreign.event_group, "")

    def test_delete_releases_the_adopted_lines(self):
        created = self.client.post(
            reverse("financial-plan-event-occurred"),
            {
                "name": "Clinica",
                "event_type": "generic",
                "decision_date": "2024-02-05",
                "expense_entry_ids": [self.line.id],
            },
            format="json",
        )

        response = self.client.delete(
            reverse("financial-plan-event-detail", args=[created.data["id"]])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.line.refresh_from_db()
        self.assertEqual(self.line.event_group, "")
        self.assertFalse(PlanEvent.objects.filter(id=created.data["id"]).exists())


class PlannedEventBaselineTests(TestCase):
    """Un evento aceptado cuyo año ya llegó vive en el presupuesto: no puede sumarse dos veces."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="plan_baseline", password="pass1234"
        )
        create_investment(self.user, Decimal("100000.00"))
        create_income(self.user)
        create_operating_expense(self.user)
        self.plan = create_plan(self.user)
        self.this_year = date.today().year

    def project(self):
        return ProjectionService().calculate(
            plan=self.plan, assumption_set=get_assumption_set(name="expected")
        )

    def accept_contribution_scenario(self):
        scenario = Scenario.objects.create(
            plan=self.plan,
            name="Mas aportacion",
            template_type=Scenario.TemplateType.GENERIC,
        )
        scenario.events.create(
            start_date=date(self.this_year, 1, 1),
            monthly_contribution_delta=Decimal("500.00"),
        )
        ScenarioService().accept(scenario=scenario)

    def test_accepted_contribution_is_not_counted_twice_once_its_year_arrived(self):
        """Aceptar el escenario debe dar lo mismo que tener ya esa aportacion en presupuesto."""
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Aportacion equivalente",
            category=AnnualExpenseEntry.Category.FINANCIAL_INVESTMENTS,
            subcategory="other_financial_investments",
            cashflow_role=AnnualExpenseEntry.CashflowRole.INVESTMENT,
            amount_annual=Decimal("6000.00"),
            fiscal_year=self.this_year,
        )
        reality = self.project()["trajectory"]
        AnnualExpenseEntry.objects.filter(user=self.user, name="Aportacion equivalente").delete()

        self.accept_contribution_scenario()

        with_event = self.project()["trajectory"]
        self.assertEqual(
            [row["productive_capital"] for row in with_event],
            [row["productive_capital"] for row in reality],
        )


class PlanEventLifecycleTests(TestCase):
    """Previsto -> materializado (la verdad se muda a Patrimonio) o -> cancelado."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="plan_lifecycle", password="pass1234"
        )
        create_investment(self.user, Decimal("100000.00"))
        create_income(self.user)
        create_operating_expense(self.user)
        self.plan = create_plan(self.user)
        self.next_year = date.today().year + 1

    def accept_vehicle_scenario(self):
        scenario = Scenario.objects.create(
            plan=self.plan,
            name="Coche",
            template_type=Scenario.TemplateType.VEHICLE,
        )
        scenario.events.create(
            start_date=date(self.next_year, 6, 1),
            initial_outflow=Decimal("10000.00"),
            monthly_expense_delta=Decimal("400.00"),
            new_asset_value=Decimal("25000.00"),
            new_asset_type=PlanAssetFunction.Function.FAMILY_USE,
            new_debt_principal=Decimal("20000.00"),
            new_debt_interest_rate=Decimal("0.0800"),
            new_debt_term_months=48,
        )
        result = ScenarioService().accept(scenario=scenario)
        return scenario, result["event"]

    def event_lines(self, event):
        return AnnualExpenseEntry.objects.filter(
            user=self.user, event_group=f"plan_event:{event.id}"
        )

    def test_materializing_creates_the_real_asset_and_liability_from_the_scenario(self):
        _scenario, event = self.accept_vehicle_scenario()

        result = materialize_plan_event(event=event, actual_date=date.today())

        event.refresh_from_db()
        asset = result["created_assets"][0]
        liability = result["created_liabilities"][0]
        self.assertEqual(event.status, PlanEvent.Status.OCCURRED)
        self.assertEqual(event.actual_date, date.today())
        self.assertEqual(asset.amount, Decimal("25000.00"))
        self.assertEqual(liability.principal_amount, Decimal("20000.00"))
        self.assertEqual(liability.annual_interest_tae, Decimal("8.00"))
        self.assertEqual(liability.term_months, 48)
        self.assertEqual(liability.financed_asset, asset)
        # La funcion simulada manda sobre la inferida por categoria.
        self.assertEqual(
            PlanAssetFunction.objects.get(user=self.user, asset=asset).function,
            PlanAssetFunction.Function.FAMILY_USE,
        )

    def test_materializing_drops_the_forecast_financing_and_hands_the_rest_back(self):
        _scenario, event = self.accept_vehicle_scenario()
        planned_names = {line.name for line in self.event_lines(event)}
        self.assertIn("Coche - financiación", planned_names)

        result = materialize_plan_event(event=event, actual_date=date.today())

        # La financiacion prevista se borra: el pasivo real regenera sus cuotas.
        dropped = {line["name"] for line in result["budget_lines_dropped"]}
        self.assertEqual(dropped, {"Coche - financiación"})
        # El resto vuelve al usuario: son gastos reales suyos, editables en Presupuesto.
        released = {line["name"] for line in result["budget_lines_released"]}
        self.assertIn("Coche - entrada", released)
        self.assertIn("Coche - gasto recurrente", released)
        self.assertEqual(self.event_lines(event).count(), 0)
        self.assertTrue(
            AnnualExpenseEntry.objects.filter(
                user=self.user, name="Coche - gasto recurrente", event_group=""
            ).exists()
        )
        liability = result["created_liabilities"][0]
        self.assertTrue(
            AnnualExpenseEntry.objects.filter(
                user=self.user, event_group=f"liability_{liability.id}"
            ).exists()
        )

    def test_materialized_event_stops_feeding_the_projection_as_a_forecast(self):
        _scenario, event = self.accept_vehicle_scenario()

        materialize_plan_event(event=event, actual_date=date.today())

        event.refresh_from_db()
        self.assertEqual(event.status, PlanEvent.Status.OCCURRED)
        payloads = plan_event_payloads(plan=self.plan)
        self.assertEqual(payloads, [])

    def test_materializing_refuses_an_event_that_already_occurred(self):
        _scenario, event = self.accept_vehicle_scenario()
        materialize_plan_event(event=event, actual_date=date.today())

        with self.assertRaises(DRFValidationError):
            materialize_plan_event(event=event, actual_date=date.today())

    def test_cancelling_deletes_the_forecast_and_restores_the_projection(self):
        before = ProjectionService().calculate(
            plan=self.plan, assumption_set=get_assumption_set(name="expected")
        )
        scenario, event = self.accept_vehicle_scenario()
        after_accept = ProjectionService().calculate(
            plan=self.plan, assumption_set=get_assumption_set(name="expected")
        )
        self.assertNotEqual(after_accept["trajectory"], before["trajectory"])

        result = cancel_plan_event(event=event)

        scenario.refresh_from_db()
        self.assertFalse(PlanEvent.objects.filter(id=event.id).exists())
        self.assertEqual(scenario.status, Scenario.Status.DRAFT)
        self.assertIsNone(scenario.accepted_at)
        self.assertGreater(len(result["budget_lines_deleted"]), 0)
        self.assertEqual(
            AnnualExpenseEntry.objects.filter(
                user=self.user, event_group=f"plan_event:{event.id}"
            ).count(),
            0,
        )
        restored = ProjectionService().calculate(
            plan=self.plan, assumption_set=get_assumption_set(name="expected")
        )
        self.assertEqual(restored["trajectory"], before["trajectory"])

    def test_cancelling_refuses_an_event_that_already_happened(self):
        _scenario, event = self.accept_vehicle_scenario()
        materialize_plan_event(event=event, actual_date=date.today())

        with self.assertRaises(DRFValidationError):
            cancel_plan_event(event=event)


class CapitalRequirementsTests(APITestCase):
    """El capital por necesidad usa la misma matemática que el denominador."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="capreq", password="pass1234")
        self.client.force_authenticate(self.user)
        self.plan = create_plan(self.user)

    def test_requirement_for_plan_income_matches_projection_denominator(self):
        result = capital_requirements(
            plan=self.plan,
            assumption_name="expected",
            monthly_amounts=[Decimal("2000.00")],
        )
        projection = ProjectionService().calculate(
            plan=self.plan, assumption_set=get_assumption_set(name="expected")
        )
        self.assertEqual(
            result["requirements"][0]["capital_required_eur"],
            projection["summary"]["target_capital"]["value"],
        )

    def test_lower_need_requires_less_capital(self):
        result = capital_requirements(
            plan=self.plan,
            assumption_name="expected",
            monthly_amounts=[Decimal("800.00"), Decimal("2000.00")],
        )
        self.assertLess(
            Decimal(result["requirements"][0]["capital_required_eur"]),
            Decimal(result["requirements"][1]["capital_required_eur"]),
        )

    def test_pensions_reduce_required_capital_below_perpetuity(self):
        member = FamilyMember.objects.create(
            user=self.user,
            name="Adulto",
            role=FamilyMember.Role.ADULT,
            pension_start_date=date(2039, 1, 1),
            estimated_monthly_pension_today_eur=Decimal("1000.00"),
        )
        self.plan.members.add(member)
        result = capital_requirements(
            plan=self.plan,
            assumption_name="expected",
            monthly_amounts=[Decimal("2000.00")],
        )
        perpetuity = Decimal("2000.00") * 12 / Decimal("0.0350")
        self.assertLess(
            Decimal(result["requirements"][0]["capital_required_eur"]),
            perpetuity,
        )

    def test_event_deltas_do_not_leak_into_requirements(self):
        inputs, _, _ = build_projection_inputs(plan=self.plan)
        event_payload = {"start_year": 2030, "monthly_expense_delta": "500.00"}
        with_events = dataclasses.replace(inputs, plan_events=(event_payload,))
        assumptions = {
            "inflation_rate": "0.0250",
            "productive_return_rate": "0.0500",
            "withdrawal_rate": "0.0350",
        }
        kwargs = {
            "assumptions": assumptions,
            "candidate_year": 2040,
            "start_year": 2026,
            "annual_need_today": Decimal("12000.00"),
            "include_event_deltas": False,
        }
        self.assertEqual(
            target_capital_for_year(inputs=with_events, **kwargs),
            target_capital_for_year(inputs=inputs, **kwargs),
        )
        # Con deltas activos, el mismo evento sí mueve el resultado (comportamiento base).
        self.assertNotEqual(
            target_capital_for_year(
                inputs=with_events,
                assumptions=assumptions,
                candidate_year=2040,
                start_year=2026,
            ),
            target_capital_for_year(
                inputs=inputs,
                assumptions=assumptions,
                candidate_year=2040,
                start_year=2026,
            ),
        )

    def test_target_year_matches_the_projection_that_uses_that_horizon(self):
        """El Resumen proyecta el retiro sostenible, no la fecha objetivo: pedir los
        hitos en ese año es lo que hace comparables denominador y tramos."""
        retirement_year = self.plan.target_date.year + 6
        result = capital_requirements(
            plan=self.plan,
            assumption_name="expected",
            monthly_amounts=[Decimal("2000.00")],
            target_year=retirement_year,
        )
        projection = ProjectionService().calculate(
            plan=self.plan,
            assumption_set=get_assumption_set(name="expected"),
            retirement_year=retirement_year,
        )
        self.assertEqual(
            result["target_year"],
            retirement_year,
        )
        self.assertEqual(
            result["requirements"][0]["capital_required_eur"],
            projection["summary"]["target_capital"]["value"],
        )

    def test_api_accepts_and_validates_target_year(self):
        url = reverse("financial-plan-capital-requirements")
        response = self.client.get(url, {"monthly_amounts": "2000", "target_year": "2050"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["target_year"], 2050)
        self.assertEqual(
            self.client.get(url, {"monthly_amounts": "2000", "target_year": "ayer"}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.get(url, {"monthly_amounts": "2000", "target_year": "1200"}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_api_returns_requirements_per_amount(self):
        response = self.client.get(
            reverse("financial-plan-capital-requirements"),
            {"monthly_amounts": "1000,1800", "scenario": "expected"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["scenario"], "expected")
        self.assertEqual(len(response.data["requirements"]), 2)
        self.assertEqual(response.data["requirements"][0]["monthly_amount_today_eur"], "1000.00")

    def test_api_validates_amounts(self):
        url = reverse("financial-plan-capital-requirements")
        self.assertEqual(
            self.client.get(url).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.get(url, {"monthly_amounts": "abc"}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.get(url, {"monthly_amounts": "-5"}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.get(url, {"monthly_amounts": ",".join(["100"] * 9)}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )


class FoundationGradeTests(TestCase):
    """Nota A-E por cimiento y nota global del bloque."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="foundations_grade", password="pass1234"
        )
        self.plan = create_plan(self.user)
        create_income(self.user)
        create_operating_expense(self.user, Decimal("24000.00"))

    def test_grade_bands_never_contradict_the_status_band(self):
        """A y B son `good`, C y D `warning`, E `critical`: la letra afina dentro de
        la banda, no discute con el color."""
        for value, expected in ((100, "A"), (85, "A"), (84, "B"), (70, "B"), (69, "C")):
            self.assertEqual(health_grade(value), expected)
        for value in (100, 85, 84, 70):
            self.assertEqual(health_status(value), "good")
        for value, expected in ((69, "C"), (55, "C"), (54, "D"), (40, "D")):
            self.assertEqual(health_grade(value), expected)
            self.assertEqual(health_status(value), "warning")
        for value in (39, 0):
            self.assertEqual(health_grade(value), "E")
            self.assertEqual(health_status(value), "critical")

    def test_every_block_carries_its_grade_and_the_block_has_an_overall(self):
        payload = FoundationService().calculate(plan=self.plan)
        keys = (
            "cash_flow",
            "emergency_fund",
            "debt",
            "planned_contribution",
            "net_worth_health",
            "data_quality",
        )
        for key in keys:
            block = payload[key]
            self.assertIn(block["grade"], set("ABCDE"), key)
            self.assertEqual(block["grade"], health_grade(block["score"]), key)
            self.assertEqual(block["status"], health_status(block["score"]), key)

        overall = payload["overall"]
        self.assertEqual(overall["grade"], health_grade(overall["score"]))
        # La global es una media ponderada: nunca cae fuera del rango de sus partes.
        scores = [payload[key]["score"] for key in keys]
        self.assertGreaterEqual(overall["score"], min(scores))
        self.assertLessEqual(overall["score"], max(scores))

    def test_quality_only_looks_at_the_plan_adults(self):
        """Las identidades sueltas de la familia no cuentan: el setup deja adultos
        provisionales sin vincular y penalizaban unos datos que sí estaban completos."""
        member = FamilyMember.objects.create(
            user=self.user,
            name="Adulto del plan",
            role=FamilyMember.Role.ADULT,
            birth_date=date(1985, 1, 1),
            employment_income_end_date=date(2045, 1, 1),
            pension_start_date=date(2052, 1, 1),
        )
        self.plan.members.add(member)
        FamilyMember.objects.create(
            user=self.user,
            name="Identidad provisional",
            role=FamilyMember.Role.ADULT,
        )

        factors = DataQualityService().evaluate(user=self.user).factors

        self.assertTrue(factors["employment_income_end_dates"])
        self.assertTrue(factors["pensions"])

    def test_debt_service_counts_only_liability_commitments(self):
        """El esfuerzo de deuda son cuotas de pasivos, no cualquier compromiso con
        fecha de fin: una compra a plazos o un tratamiento no son deuda."""
        liability = Liability.objects.create(
            user=self.user,
            name="Préstamo coche",
            category=Liability.Category.PERSONAL_LOAN,
            amount=Decimal("6000.00"),
            currency="EUR",
            annual_interest_tae=Decimal("3.00"),
        )
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Compromiso pasivo: Préstamo coche",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="living_expenses",
            cashflow_role=AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT,
            amount_annual=Decimal("3600.00"),
            fiscal_year=2026,
            source_liability=liability,
        )
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Cuotas de la reforma",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="living_expenses",
            cashflow_role=AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT,
            amount_annual=Decimal("9000.00"),
            fiscal_year=2026,
        )

        payload = FoundationService().calculate(plan=self.plan)

        # 3.600 € de cuota sobre 36.000 € de ingresos = 10 %, no 35 % con la reforma.
        self.assertEqual(payload["debt"]["annual_debt_service"], "3600.00")
        self.assertEqual(payload["debt"]["debt_payment_to_income"], "0.1000")

    def test_planned_contribution_is_scored_by_savings_rate(self):
        """Antes era el único bloque sin nota: solo enseñaba el importe."""
        # 36.000 € de ingresos y 7.200 € aportados = 20 % de tasa de ahorro.
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Aportación",
            category=AnnualExpenseEntry.Category.FINANCIAL_INVESTMENTS,
            subcategory="other_financial_investments",
            cashflow_role=AnnualExpenseEntry.CashflowRole.INVESTMENT,
            amount_annual=Decimal("7200.00"),
            fiscal_year=2026,
        )
        payload = FoundationService().calculate(plan=self.plan)

        block = payload["planned_contribution"]
        self.assertEqual(block["savings_rate"], "0.2000")
        self.assertEqual(block["target_savings_rate"], "0.2000")
        self.assertEqual(block["grade"], "A")


class FoundationCriteriaTests(TestCase):
    """Criterios revisados en julio 2026: emergencia clásica y calidad real."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="foundations_criteria", password="pass1234"
        )
        self.plan = create_plan(self.user)
        create_income(self.user)
        create_operating_expense(self.user, Decimal("24000.00"))

    def test_emergency_liquidity_counts_only_cash_and_deposits(self):
        Asset.objects.create(
            user=self.user,
            name="Cuenta",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            amount=Decimal("10000.00"),
            currency="EUR",
        )
        Asset.objects.create(
            user=self.user,
            name="Depósito",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.DEPOSITS,
            amount=Decimal("2000.00"),
            currency="EUR",
        )
        # La cartera es vendible pero no es el colchón: no cuenta como emergencia.
        create_investment(self.user, Decimal("50000.00"))

        payload = FoundationService().calculate(plan=self.plan)

        self.assertEqual(payload["emergency_fund"]["eligible_liquidity"], "12000.00")
        # 12.000 € / 2.000 €/mes de gasto estructural = 6 meses, no 31.
        self.assertEqual(payload["emergency_fund"]["coverage_months_base"], "6.0000")

    def _cash(self, amount: Decimal) -> None:
        Asset.objects.create(
            user=self.user,
            name="Cuenta",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            amount=amount,
            currency="EUR",
        )

    def test_emergency_fund_is_scored_against_its_own_target(self):
        """Casi en el objetivo no es crítico, y alcanzarlo no puede quedarse corto.

        Con la escala anterior (3→12 meses) tener los 6 meses objetivo puntuaba 33 y
        el cimiento salía en rojo; 5,5 meses ("casi conseguido") también.
        """
        # Gasto operativo 24.000 €/año = 2.000 €/mes → 11.000 € son 5,5 meses.
        # La banda exacta depende del resto de factores del score compuesto; lo que
        # se fija aquí es que estar a medio mes del objetivo no puede ser crítico.
        self._cash(Decimal("11000.00"))
        payload = FoundationService().calculate(plan=self.plan)
        self.assertEqual(payload["emergency_fund"]["coverage_months_base"], "5.5000")
        self.assertNotEqual(payload["emergency_fund"]["status"], "critical")

        Asset.objects.filter(user=self.user).delete()
        self._cash(Decimal("12000.00"))  # 6 meses: el objetivo
        payload = FoundationService().calculate(plan=self.plan)
        self.assertEqual(payload["emergency_fund"]["target_months"], "6.0000")
        self.assertEqual(payload["emergency_fund"]["status"], "good")

        Asset.objects.filter(user=self.user).delete()
        self._cash(Decimal("4000.00"))  # 2 meses: por debajo del suelo
        payload = FoundationService().calculate(plan=self.plan)
        self.assertEqual(payload["emergency_fund"]["status"], "critical")

    def test_data_quality_uses_engine_factors_not_shallow_checklist(self):
        Asset.objects.create(
            user=self.user,
            name="Cuenta",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            amount=Decimal("10000.00"),
            currency="EUR",
        )

        payload = FoundationService().calculate(plan=self.plan)
        quality = payload["data_quality"]

        # El checklist antiguo daba 100 con ingresos+gastos+activos y cero
        # pasivos; la medida real penaliza contabilidad, pensiones, etc.
        self.assertLess(quality["score"], 100)
        self.assertIn("accounting_history", quality["flags"])
        self.assertFalse(quality["flags"]["accounting_history"])
        expected = DataQualityService().evaluate(user=self.user).factors
        self.assertEqual(quality["flags"], expected)


class OneOffFlowsInProjectionTests(TestCase):
    """Fase 1: los movimientos puntuales del presupuesto (no gobernados por una
    Decisión) entran en la proyección, en su año, en todo el horizonte."""

    def setUp(self):
        self.user = get_user_model().objects.create_user("oneoff-user", password="x")
        self.plan = create_plan(self.user)
        create_investment(self.user, Decimal("300000.00"))
        create_income(self.user, Decimal("40000.00"))
        self.next_year = date.today().year + 1

    def _project(self):
        return ProjectionService().calculate(
            plan=self.plan, assumption_set=get_assumption_set(name="expected")
        )

    def _row(self, result, year):
        return next(row for row in result["trajectory"] if row["year"] == year)

    def _prod(self, year):
        return Decimal(self._row(self._project(), year)["productive_capital"])

    def _expense(self, *, role, amount, year, month=12, **extra):
        return AnnualExpenseEntry.objects.create(
            user=self.user,
            name=extra.pop("name", "Puntual gasto"),
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="misc",
            time_profile=AnnualExpenseEntry.TimeProfile.ONE_OFF,
            expense_type=AnnualExpenseEntry.ExpenseType.ONE_OFF,
            cashflow_role=role,
            amount_annual=amount,
            fiscal_year=year,
            target_month=month,
            **extra,
        )

    def _income(self, *, role, amount, year, month=12, **extra):
        return AnnualIncomeEntry.objects.create(
            user=self.user,
            name=extra.pop("name", "Puntual ingreso"),
            category=AnnualIncomeEntry.Category.OTHER_INCOME,
            subcategory="misc",
            time_profile=AnnualIncomeEntry.TimeProfile.ONE_OFF,
            income_type=AnnualIncomeEntry.IncomeType.ONE_OFF,
            cashflow_role=role,
            amount_annual=amount,
            fiscal_year=year,
            target_month=month,
            **extra,
        )

    def test_future_one_off_outflow_reduces_productive_capital(self):
        baseline = self._prod(self.next_year)
        self._expense(
            role=AnnualExpenseEntry.CashflowRole.TAX_FEE,
            amount=Decimal("50000.00"),
            year=self.next_year,
        )
        self.assertEqual(baseline - self._prod(self.next_year), Decimal("50000.00"))

    def test_future_one_off_income_increases_productive_capital(self):
        baseline = self._prod(self.next_year)
        self._income(
            role=AnnualIncomeEntry.CashflowRole.OTHER,
            amount=Decimal("50000.00"),
            year=self.next_year,
        )
        self.assertEqual(self._prod(self.next_year) - baseline, Decimal("50000.00"))

    def test_asset_purchase_moves_productive_to_non_productive(self):
        base = self._row(self._project(), self.next_year)
        self._expense(
            role=AnnualExpenseEntry.CashflowRole.ASSET_PURCHASE,
            amount=Decimal("50000.00"),
            year=self.next_year,
        )
        after = self._row(self._project(), self.next_year)
        self.assertEqual(
            Decimal(base["productive_capital"]) - Decimal(after["productive_capital"]),
            Decimal("50000.00"),
        )
        self.assertEqual(
            Decimal(after["non_productive_assets"]) - Decimal(base["non_productive_assets"]),
            Decimal("50000.00"),
        )
        # El patrimonio neto se conserva en el año de la compra (caja → activo).
        self.assertEqual(after["net_worth"], base["net_worth"])

    def test_one_off_governed_by_a_decision_is_excluded(self):
        baseline = self._prod(self.next_year)
        self._expense(
            role=AnnualExpenseEntry.CashflowRole.TAX_FEE,
            amount=Decimal("50000.00"),
            year=self.next_year,
            event_group="plan_event:99",
        )
        self.assertEqual(self._prod(self.next_year), baseline)

    def test_system_generated_asset_sale_and_past_year_are_excluded(self):
        self._expense(
            role=AnnualExpenseEntry.CashflowRole.TAX_FEE,
            amount=Decimal("50000.00"),
            year=self.next_year,
            is_system_generated=True,
        )
        self._income(
            role=AnnualIncomeEntry.CashflowRole.ASSET_SALE,
            amount=Decimal("50000.00"),
            year=self.next_year,
        )
        self._expense(
            role=AnnualExpenseEntry.CashflowRole.TAX_FEE,
            amount=Decimal("50000.00"),
            year=date.today().year - 1,
        )
        self.assertEqual(one_off_flows(self.plan), [])

    def test_asset_sale_group_costs_wait_for_the_sale_decision(self):
        group = "venta_vivienda"
        self._income(
            role=AnnualIncomeEntry.CashflowRole.ASSET_SALE,
            amount=Decimal("150000.00"),
            year=self.next_year,
            event_group=group,
        )
        self._expense(
            role=AnnualExpenseEntry.CashflowRole.TAX_FEE,
            amount=Decimal("2000.00"),
            year=self.next_year,
            event_group=group,
        )

        self.assertEqual(one_off_flows(self.plan), [])

    def test_current_year_one_off_respects_occurrence_month(self):
        today = date.today()
        if today.month > 1:
            self._expense(
                role=AnnualExpenseEntry.CashflowRole.TAX_FEE,
                amount=Decimal("11111.00"),
                year=today.year,
                month=1,
                name="ya pasado",
            )
        if today.month < 12:
            self._expense(
                role=AnnualExpenseEntry.CashflowRole.TAX_FEE,
                amount=Decimal("22222.00"),
                year=today.year,
                month=12,
                name="futuro",
            )
        total_outflow = sum(Decimal(flow["outflow"]) for flow in one_off_flows(self.plan))
        expected = Decimal("22222.00") if today.month < 12 else Decimal("0.00")
        self.assertEqual(total_outflow, expected)


class AssetDisposalInProjectionTests(TestCase):
    """Fase 2a: una Decisión de venta retira el activo enlazado del patrimonio
    proyectado (sin doble conteo) y sus ingresos netos entran como capital."""

    def setUp(self):
        self.user = get_user_model().objects.create_user("disposal-user", password="x")
        self.plan = create_plan(self.user)
        create_investment(self.user, Decimal("100000.00"))
        self.sale_year = date.today().year + 3

    def _home(self, amount=Decimal("200000.00")):
        return Asset.objects.create(
            user=self.user,
            name="Vivienda a vender",
            category=Asset.Category.REAL_ESTATE,
            subcategory=Asset.Subcategory.PRIMARY_HOME,
            amount=amount,
            currency="EUR",
        )

    def _sale_event(self, **event):
        return PlanEvent.objects.create(
            plan=self.plan,
            name="Venta vivienda",
            event_type=Scenario.TemplateType.HOUSING,
            planned_date=date(self.sale_year, 1, 1),
            status=PlanEvent.Status.PLANNED,
            planned_impact_json={"events": [{"start_year": self.sale_year, **event}]},
        )

    def _project(self):
        return ProjectionService().calculate(
            plan=self.plan, assumption_set=get_assumption_set(name="expected")
        )

    def _row(self, result, year):
        return next(row for row in result["trajectory"] if row["year"] == year)

    def test_future_sale_removes_asset_and_adds_proceeds(self):
        self._home(Decimal("200000.00"))
        before = self._row(self._project(), self.sale_year)
        self._sale_event(
            disposed_asset_value="200000.00",
            disposed_asset_type="family_use",
            proceeds="220000.00",
        )
        after = self._row(self._project(), self.sale_year)
        # El activo desaparece del bucket no-productivo en el año de la venta.
        self.assertEqual(after["non_productive_assets"], "0.00")
        # Los ingresos netos entran como capital productivo.
        self.assertEqual(
            Decimal(after["productive_capital"]) - Decimal(before["productive_capital"]),
            Decimal("220000.00"),
        )
        # Se vende por encima del valor en libros → el patrimonio neto sube (plusvalía).
        self.assertGreater(Decimal(after["net_worth"]), Decimal(before["net_worth"]))

    def test_sale_cancels_linked_liability(self):
        home = self._home(Decimal("200000.00"))
        Liability.objects.create(
            user=self.user,
            name="Hipoteca",
            category=Liability.Category.MORTGAGE,
            amount=Decimal("150000.00"),
            currency="EUR",
            financed_asset=home,
            term_months=300,
        )
        before = self._row(self._project(), self.sale_year)
        self.assertGreater(Decimal(before["liabilities"]), Decimal("0"))
        self._sale_event(
            disposed_asset_value="200000.00",
            disposed_asset_type="family_use",
            proceeds="50000.00",
            disposed_liability_value="150000.00",
        )
        after = self._row(self._project(), self.sale_year)
        self.assertEqual(after["non_productive_assets"], "0.00")
        # La hipoteca desaparece del saldo de deuda proyectado.
        self.assertEqual(after["liabilities"], "0.00")

    def test_past_sale_decision_is_not_reapplied_in_horizon(self):
        self._home(Decimal("200000.00"))
        this_year = date.today().year
        before = self._row(self._project(), this_year)
        PlanEvent.objects.create(
            plan=self.plan,
            name="Venta pasada",
            event_type=Scenario.TemplateType.HOUSING,
            planned_date=date(this_year - 2, 1, 1),
            status=PlanEvent.Status.PLANNED,
            planned_impact_json={
                "events": [
                    {
                        "start_year": this_year - 2,
                        "disposed_asset_value": "200000.00",
                        "disposed_asset_type": "family_use",
                        "proceeds": "200000.00",
                    }
                ]
            },
        )
        after = self._row(self._project(), this_year)
        self.assertEqual(after["non_productive_assets"], before["non_productive_assets"])


class PlannedDecisionMigrationTests(APITestCase):
    """Fase 2b: agrupar partidas puntuales existentes en una Decisión planificada
    (compra/venta) las saca de la vía de Fase 1 y les da impacto vía la Decisión."""

    def setUp(self):
        self.user = get_user_model().objects.create_user("migration-user", password="x")
        self.plan = create_plan(self.user)
        create_investment(self.user, Decimal("100000.00"))
        self.transaction_year = date.today().year + 2

    def _home(self):
        return Asset.objects.create(
            user=self.user,
            name="Vivienda",
            category=Asset.Category.REAL_ESTATE,
            subcategory=Asset.Subcategory.PRIMARY_HOME,
            amount=Decimal("200000.00"),
            currency="EUR",
        )

    def _sale_income(self, amount=Decimal("220000.00")):
        return AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Venta vivienda",
            category=AnnualIncomeEntry.Category.CAPITAL_GAINS,
            subcategory="misc",
            time_profile=AnnualIncomeEntry.TimeProfile.ONE_OFF,
            income_type=AnnualIncomeEntry.IncomeType.ONE_OFF,
            cashflow_role=AnnualIncomeEntry.CashflowRole.OTHER,
            amount_annual=amount,
            fiscal_year=self.transaction_year,
        )

    def _reform_expense(self, amount=Decimal("40000.00")):
        return AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Reforma",
            category=AnnualExpenseEntry.Category.TANGIBLE_ASSETS,
            subcategory="misc",
            time_profile=AnnualExpenseEntry.TimeProfile.ONE_OFF,
            expense_type=AnnualExpenseEntry.ExpenseType.ONE_OFF,
            cashflow_role=AnnualExpenseEntry.CashflowRole.ASSET_PURCHASE,
            amount_annual=amount,
            fiscal_year=self.transaction_year,
            target_month=12,
        )

    def _row(self, year):
        result = ProjectionService().calculate(
            plan=self.plan, assumption_set=get_assumption_set(name="expected")
        )
        return next(row for row in result["trajectory"] if row["year"] == year)

    def test_sale_decision_disposes_asset_and_adopts_income_line(self):
        home = self._home()
        income = self._sale_income(Decimal("220000.00"))
        event = register_planned_decision(
            plan=self.plan,
            name="Venta vivienda",
            event_type=Scenario.TemplateType.HOUSING,
            decision_date=date(date.today().year, 1, 1),
            transaction_year=self.transaction_year,
            income_entry_ids=[income.id],
            asset_ids=[home.id],
            impact={
                "disposed_asset_value": Decimal("200000.00"),
                "disposed_asset_type": "family_use",
                "proceeds": Decimal("220000.00"),
            },
        )
        income.refresh_from_db()
        self.assertEqual(income.event_group, f"plan_event:{event.id}")
        self.assertIn(home, list(event.linked_assets.all()))
        # La proyección da de baja el activo en el año de la venta.
        self.assertEqual(self._row(self.transaction_year)["non_productive_assets"], "0.00")
        # La línea la gobierna la Decisión: no se cuenta también por la vía de Fase 1.
        self.assertEqual(one_off_flows(self.plan), [])

    def test_purchase_decision_takes_expense_lines_out_of_phase_1(self):
        reform = self._reform_expense(Decimal("40000.00"))
        # Antes de agrupar, la reforma cuenta como flujo puntual de Fase 1.
        self.assertTrue(
            any(Decimal(flow["asset_purchase"]) > 0 for flow in one_off_flows(self.plan))
        )
        event = register_planned_decision(
            plan=self.plan,
            name="Compra Atrio",
            event_type=Scenario.TemplateType.HOUSING,
            decision_date=date(date.today().year, 1, 1),
            transaction_year=self.transaction_year,
            expense_entry_ids=[reform.id],
            impact={
                "initial_outflow": Decimal("40000.00"),
                "new_asset_value": Decimal("250000.00"),
                "new_asset_type": "family_use",
            },
        )
        reform.refresh_from_db()
        self.assertEqual(reform.event_group, f"plan_event:{event.id}")
        # Ya no se cuenta por Fase 1 (la gobierna la Decisión).
        self.assertEqual(one_off_flows(self.plan), [])

    def test_endpoint_creates_planned_sale_decision(self):
        home = self._home()
        income = self._sale_income(Decimal("220000.00"))
        self.client.force_authenticate(self.user)
        response = self.client.post(
            reverse("financial-plan-event-planned-decision"),
            {
                "name": "Venta vivienda",
                "event_type": Scenario.TemplateType.HOUSING,
                "decision_date": f"{date.today().year}-01-15",
                "transaction_year": self.transaction_year,
                "transaction_month": 11,
                "income_entry_ids": [income.id],
                "asset_ids": [home.id],
                "impact": {
                    "disposed_asset_value": "200000.00",
                    "disposed_asset_type": "family_use",
                    "proceeds": "220000.00",
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        income.refresh_from_db()
        self.assertTrue(income.event_group.startswith("plan_event:"))
        self.assertEqual(
            response.data["planned_impact_json"]["events"][0]["start_date"],
            f"{self.transaction_year}-11-01",
        )

    def test_new_debt_without_term_is_rejected(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            reverse("financial-plan-event-planned-decision"),
            {
                "name": "Compra",
                "event_type": Scenario.TemplateType.HOUSING,
                "decision_date": f"{date.today().year}-01-15",
                "transaction_year": self.transaction_year,
                "impact": {
                    "new_asset_value": "300000.00",
                    "new_asset_type": "family_use",
                    "new_debt_principal": "200000.00",
                    # sin new_debt_term_years → debe rechazarse
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_debt_term_years", str(response.data))

    def test_endpoint_updates_planned_decision_without_releasing_its_lines(self):
        reform = self._reform_expense(Decimal("40000.00"))
        self.client.force_authenticate(self.user)
        event = register_planned_decision(
            plan=self.plan,
            name="Compra Atrio",
            event_type=Scenario.TemplateType.HOUSING,
            decision_date=date(date.today().year, 2, 1),
            transaction_year=self.transaction_year,
            transaction_month=10,
            expense_entry_ids=[reform.id],
            impact={
                "initial_outflow": Decimal("40000.00"),
                "new_asset_value": Decimal("250000.00"),
                "new_asset_type": "family_use",
            },
            note="Estimación inicial",
        )
        registration_before = event.actual_impact_json["registration"]
        snapshot_count = ProjectionSnapshot.objects.filter(plan=self.plan, is_official=True).count()

        response = self.client.patch(
            reverse("financial-plan-event-planned-decision-detail", args=[event.id]),
            {
                "name": "Compra Atrio actualizada",
                "event_type": Scenario.TemplateType.HOUSING,
                "decision_date": f"{date.today().year}-02-15",
                "transaction_year": self.transaction_year,
                "transaction_month": 11,
                "impact": {
                    "initial_outflow": "80420.00",
                    "new_asset_value": "322176.00",
                    "new_asset_type": "family_use",
                    "new_debt_principal": "239200.00",
                    "new_debt_interest_rate": "0.0250",
                    "new_debt_term_years": 30,
                },
                "note": "Valor de mercado revisado",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["event"]["name"], "Compra Atrio actualizada")
        updated = response.data["event"]["planned_impact_json"]["events"][0]
        self.assertEqual(updated["start_date"], f"{self.transaction_year}-11-01")
        self.assertEqual(updated["new_asset_value"], "322176.00")
        self.assertIn("projection", response.data)
        event.refresh_from_db()
        registration_after = event.actual_impact_json["registration"]
        self.assertEqual(registration_after["adopted_lines"], registration_before["adopted_lines"])
        self.assertEqual(registration_after["linked"], registration_before["linked"])
        self.assertEqual(registration_after["note"], "Valor de mercado revisado")
        reform.refresh_from_db()
        self.assertEqual(reform.event_group, f"plan_event:{event.id}")
        self.assertEqual(
            ProjectionSnapshot.objects.filter(plan=self.plan, is_official=True).count(),
            snapshot_count + 1,
        )

    def test_endpoint_rejects_editing_an_occurred_decision_as_planned(self):
        self.client.force_authenticate(self.user)
        event = register_occurred_event(
            plan=self.plan,
            name="Compra ya realizada",
            event_type=Scenario.TemplateType.HOUSING,
            decision_date=date.today(),
        )

        response = self.client.patch(
            reverse("financial-plan-event-planned-decision-detail", args=[event.id]),
            {
                "name": "No debe cambiar",
                "event_type": Scenario.TemplateType.HOUSING,
                "decision_date": date.today().isoformat(),
                "transaction_year": self.transaction_year,
                "transaction_month": 11,
                "impact": {"new_asset_value": "300000.00"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        event.refresh_from_db()
        self.assertEqual(event.name, "Compra ya realizada")

    def test_cancelling_decision_releases_adopted_lines_without_deleting(self):
        # Partida real del usuario, con su propio grupo manual.
        reform = self._reform_expense(Decimal("40000.00"))
        reform.event_group = "compra_atrio"
        reform.save(update_fields=["event_group"])
        event = register_planned_decision(
            plan=self.plan,
            name="Compra Atrio",
            event_type=Scenario.TemplateType.HOUSING,
            decision_date=date(date.today().year, 1, 1),
            transaction_year=self.transaction_year,
            expense_entry_ids=[reform.id],
            impact={"new_asset_value": Decimal("250000.00"), "new_asset_type": "family_use"},
        )
        reform.refresh_from_db()
        self.assertEqual(reform.event_group, f"plan_event:{event.id}")
        # Cancelar NO debe borrar la partida adoptada: se libera a su grupo previo.
        cancel_plan_event(event=event)
        reform.refresh_from_db()  # lanzaría DoesNotExist si se hubiera borrado
        self.assertEqual(reform.event_group, "compra_atrio")
        self.assertTrue(reform.is_active)


class CashFlowReconciliationTests(TestCase):
    """La aportación efectiva de cada año se limita al superávit libre real (caja):
    ingreso − operativos − compromisos que vencen − servicio de deuda de Decisiones.
    Un déficit consume capital (seguridad primero, luego productivo)."""

    def setUp(self):
        self.user = get_user_model().objects.create_user("cashflow-user", password="x")
        self.plan = create_plan(self.user)
        create_investment(self.user, Decimal("100000.00"))
        self.year = date.today().year
        self.next_year = self.year + 1

    def _income(self, amount):
        return AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Salario",
            category=AnnualIncomeEntry.Category.SALARY,
            subcategory="salary",
            amount_annual=amount,
            fiscal_year=self.year,
        )

    def _operating(self, amount):
        return AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Vida",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="living_expenses",
            cashflow_role=AnnualExpenseEntry.CashflowRole.OPERATING,
            amount_annual=amount,
            fiscal_year=self.year,
        )

    def _investment(self, amount):
        return AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Aportación ETF",
            category=AnnualExpenseEntry.Category.FINANCIAL_INVESTMENTS,
            subcategory="etf",
            cashflow_role=AnnualExpenseEntry.CashflowRole.INVESTMENT,
            amount_annual=amount,
            fiscal_year=self.year,
        )

    def _commitment(self, amount, end_year):
        return AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Esfuerzo temporal",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="misc",
            cashflow_role=AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT,
            time_profile=AnnualExpenseEntry.TimeProfile.TERM_RECURRENT,
            term_end_year=end_year,
            amount_annual=amount,
            fiscal_year=self.year,
        )

    def _debt_event(self, principal, *, rate="0.0250", term=30):
        return PlanEvent.objects.create(
            plan=self.plan,
            name="Hipoteca nueva",
            event_type=Scenario.TemplateType.HOUSING,
            planned_date=date(self.year, 1, 1),
            status=PlanEvent.Status.PLANNED,
            planned_impact_json={
                "events": [
                    {
                        "start_year": self.year,
                        "new_debt_principal": str(principal),
                        "new_debt_interest_rate": rate,
                        "new_debt_term_years": term,
                    }
                ]
            },
        )

    def _prod(self, year):
        result = ProjectionService().calculate(
            plan=self.plan, assumption_set=get_assumption_set(name="expected")
        )
        row = next(row for row in result["trajectory"] if row["year"] == year)
        return Decimal(row["productive_capital"])

    def test_decision_debt_service_amortizes_and_ends(self):
        events = (
            {
                "start_year": self.next_year,
                "start_month": 1,
                "new_debt_principal": "200000.00",
                "new_debt_interest_rate": "0.0250",
                "new_debt_term_years": 30,
            },
        )
        service = decision_debt_service_for_year(events=events, year=self.next_year)
        # 200k al 2,5% a 30 años ≈ 790 €/mes ≈ 9.485 €/año (banda amplia, no frágil).
        self.assertGreater(service, Decimal("9000"))
        self.assertLess(service, Decimal("10000"))
        # Cuando el préstamo ya está amortizado, deja de pesar en la caja.
        self.assertEqual(
            decision_debt_service_for_year(events=events, year=self.next_year + 30), Decimal("0")
        )

    def test_current_year_uses_only_months_after_the_current_snapshot(self):
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Cuotas Atrio",
            category=AnnualExpenseEntry.Category.TANGIBLE_ASSETS,
            subcategory="property_purchase",
            cashflow_role=AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT,
            time_profile=AnnualExpenseEntry.TimeProfile.TERM_RECURRENT,
            amount_input_period=AnnualExpenseEntry.AmountInputPeriod.MONTHLY,
            amount_annual=Decimal("16488.00"),
            fiscal_year=self.year,
            term_end_year=self.year,
            term_end_month=9,
        )

        inputs, _, _ = build_projection_inputs(plan=self.plan)

        expected_months = max(0, 9 - date.today().month)
        self.assertEqual(
            inputs.current_year_remaining_temporary_commitments,
            Decimal("1374.00") * Decimal(expected_months),
        )

    def test_future_system_commitment_uses_its_explicit_fiscal_slice(self):
        for fiscal_year, amount in (
            (self.year, Decimal("7297.56")),
            (self.next_year, Decimal("1216.26")),
        ):
            AnnualExpenseEntry.objects.create(
                user=self.user,
                name="Compromiso pasivo: FIV",
                category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
                subcategory="misc",
                cashflow_role=AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT,
                time_profile=AnnualExpenseEntry.TimeProfile.TERM_RECURRENT,
                amount_annual=amount,
                fiscal_year=fiscal_year,
                term_end_year=self.next_year,
                term_end_month=1,
                is_system_generated=True,
            )

        inputs, _, _ = build_projection_inputs(plan=self.plan)

        next_year = next(
            item for item in inputs.temporary_commitments if item["year"] == self.next_year
        )
        self.assertEqual(Decimal(next_year["amount"]), Decimal("1216.26"))

    def test_unfunded_outflow_uses_remaining_year_surplus_before_staying_negative(self):
        self._income(Decimal("90000.00"))
        self._operating(Decimal("20000.00"))
        PlanEvent.objects.create(
            plan=self.plan,
            name="Compra sin financiación cerrada",
            event_type=Scenario.TemplateType.HOUSING,
            planned_date=date(self.year, 1, 1),
            status=PlanEvent.Status.PLANNED,
            planned_impact_json={
                "events": [
                    {
                        "start_year": self.year,
                        "start_month": min(12, date.today().month + 1),
                        "initial_outflow": "150000.00",
                        "new_asset_value": "150000.00",
                        "new_asset_type": "family_use",
                    }
                ]
            },
        )

        assumption_set = get_assumption_set(name="expected")
        inputs, _, _ = build_projection_inputs(plan=self.plan)
        assumptions = serialize_assumptions(assumption_set)
        remaining_surplus = free_operating_surplus(
            inputs=inputs,
            assumptions=assumptions,
            year=self.year,
            start_year=self.year,
        )
        projection = ProjectionService().calculate(plan=self.plan, assumption_set=assumption_set)
        current = next(row for row in projection["trajectory"] if row["year"] == self.year)
        following = next(row for row in projection["trajectory"] if row["year"] == self.next_year)

        expected_gap = (
            inputs.productive_capital
            + inputs.security_capital
            + remaining_surplus
            - Decimal("150000.00")
        ).quantize(Decimal("0.01"))
        self.assertEqual(Decimal(current["financing_gap"]), expected_gap)
        self.assertLess(Decimal(current["financing_gap"]), Decimal("0"))
        self.assertEqual(following["financing_gap"], "0.00")

    def test_debt_service_caps_effective_contribution(self):
        # Superávit operativo 15k, aportación planificada 12k: sin deuda cabe entera.
        self._income(Decimal("40000.00"))
        self._operating(Decimal("25000.00"))
        self._investment(Decimal("12000.00"))
        before = self._prod(self.next_year)
        # La cuota de la hipoteca nueva se come el superávit y capa la aportación.
        self._debt_event(Decimal("200000.00"))
        after = self._prod(self.next_year)
        self.assertLess(after, before)

    def test_expiring_commitment_raises_free_surplus(self):
        self._income(Decimal("40000.00"))
        self._operating(Decimal("20000.00"))
        self._commitment(Decimal("15000.00"), end_year=self.next_year)
        inputs, _, _ = build_projection_inputs(plan=self.plan)
        assumptions = serialize_assumptions(get_assumption_set(name="expected"))
        active = free_operating_surplus(
            inputs=inputs, assumptions=assumptions, year=self.next_year, start_year=self.year
        )
        after = free_operating_surplus(
            inputs=inputs, assumptions=assumptions, year=self.next_year + 1, start_year=self.year
        )
        # Al vencer el compromiso de 15k, el superávit libre se recupera.
        self.assertGreater(after, active + Decimal("10000"))

    def test_ample_income_keeps_full_contribution(self):
        # Ingreso holgado: el superávit libre supera a la aportación → no se capa.
        self._income(Decimal("90000.00"))
        self._operating(Decimal("20000.00"))
        self._investment(Decimal("10000.00"))
        inputs, _, _ = build_projection_inputs(plan=self.plan)
        assumptions = serialize_assumptions(get_assumption_set(name="expected"))
        free_cash = free_operating_surplus(
            inputs=inputs, assumptions=assumptions, year=self.next_year, start_year=self.year
        )
        self.assertGreater(free_cash, inputs.annual_planned_contributions)

    def test_deficit_draws_down_capital(self):
        # Sin holgura de caja (operativos > ingreso) el déficit consume capital cada año.
        self._income(Decimal("20000.00"))
        self._operating(Decimal("35000.00"))
        first = self._prod(self.next_year)
        second = self._prod(self.next_year + 1)
        self.assertLess(second, first)


class FinancedDecisionCashFlowTests(TestCase):
    """Una Decisión con financiación y gasto de uso toca la caja por tres vías que no
    pueden pisarse: el desembolso inicial (una vez), la cuota del préstamo (una vez,
    servida desde el propio préstamo) y el gasto recurrente, que recorta lo que se
    puede ahorrar mientras dure."""

    def setUp(self):
        self.user = get_user_model().objects.create_user("financed-decision", password="x")
        self.plan = create_plan(self.user)
        create_investment(self.user, Decimal("100000.00"))
        self.year = date.today().year
        self.next_year = self.year + 1
        AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Salario",
            category=AnnualIncomeEntry.Category.SALARY,
            subcategory="salary",
            amount_annual=Decimal("40000.00"),
            fiscal_year=self.year,
        )
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Vida",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="living_expenses",
            cashflow_role=AnnualExpenseEntry.CashflowRole.OPERATING,
            amount_annual=Decimal("20000.00"),
            fiscal_year=self.year,
        )

    def _decision(
        self,
        *,
        start_year,
        start_month=1,
        principal="0",
        term=4,
        rate="0.0700",
        monthly_expense="0",
        end_year=None,
        status=PlanEvent.Status.PLANNED,
    ):
        return PlanEvent.objects.create(
            plan=self.plan,
            name="Coche",
            event_type=Scenario.TemplateType.VEHICLE,
            planned_date=date(start_year, start_month, 1),
            status=status,
            planned_impact_json={
                "events": [
                    {
                        "start_year": start_year,
                        "start_month": start_month,
                        "end_year": end_year,
                        "new_debt_principal": principal,
                        "new_debt_interest_rate": rate,
                        "new_debt_term_years": term,
                        "debt_end_year": start_year + term - 1,
                        "monthly_expense_delta": monthly_expense,
                    }
                ]
            },
        )

    def _decision_commitment(self, event, amount, fiscal_year):
        """Partida que la Decisión crea en el presupuesto para su cuota."""
        return AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Coche - financiación",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="personal_loan_repayment",
            cashflow_role=AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT,
            time_profile=AnnualExpenseEntry.TimeProfile.TERM_RECURRENT,
            term_start_month=1,
            term_end_year=fiscal_year,
            term_end_month=12,
            amount_annual=amount,
            fiscal_year=fiscal_year,
            event_group=f"plan_event:{event.id}",
            is_system_generated=True,
        )

    def _surplus(self, year):
        inputs, _, _ = build_projection_inputs(plan=self.plan)
        return free_operating_surplus(
            inputs=inputs,
            assumptions=serialize_assumptions(get_assumption_set(name="expected")),
            year=year,
            start_year=self.year,
        )

    def test_instalment_of_a_financed_decision_is_charged_once(self):
        baseline = self._surplus(self.next_year)

        event = self._decision(start_year=self.next_year, principal="20000.00")
        with_decision = self._surplus(self.next_year)
        instalment = debt_annual_payment(
            principal=Decimal("20000.00"), annual_rate=Decimal("0.0700"), term_years=4
        )
        self.assertAlmostEqual(baseline - with_decision, instalment, delta=Decimal("1.00"))

        # Las partidas que la Decisión escribe en el presupuesto describen esa misma
        # cuota: sumarlas como compromiso temporal la cobraría dos veces.
        self._decision_commitment(event, Decimal("5853.12"), self.next_year)
        self.assertEqual(self._surplus(self.next_year), with_decision)

    def test_commitment_adopted_by_an_occurred_decision_still_weighs(self):
        baseline = self._surplus(self.next_year)
        # Una Decisión ya ocurrida no aporta préstamo a la proyección: sus cuotas solo
        # se conocen por el presupuesto y tienen que seguir restando.
        event = self._decision(start_year=self.year, status=PlanEvent.Status.OCCURRED)
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Cuota en curso",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="misc",
            cashflow_role=AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT,
            time_profile=AnnualExpenseEntry.TimeProfile.TERM_RECURRENT,
            term_end_year=self.next_year,
            amount_annual=Decimal("6000.00"),
            fiscal_year=self.year,
            event_group=f"plan_event:{event.id}",
        )

        self.assertAlmostEqual(
            baseline - self._surplus(self.next_year), Decimal("6000.00"), delta=Decimal("1.00")
        )

    def test_recurring_expense_reduces_saving_capacity(self):
        baseline = self._surplus(self.next_year)

        self._decision(start_year=self.next_year, monthly_expense="400.00")

        self.assertEqual(baseline - self._surplus(self.next_year), Decimal("4800.00"))

    def test_recurring_expense_outlives_its_loan(self):
        after_loan = self.next_year + 3  # el préstamo a 2 años ya está amortizado
        baseline = self._surplus(after_loan)

        self._decision(
            start_year=self.next_year, principal="20000.00", term=2, monthly_expense="400.00"
        )

        # Solo pesa el gasto de uso: la cuota ya no existe, pero el coche sigue costando.
        self.assertEqual(baseline - self._surplus(after_loan), Decimal("4800.00"))

    def test_recurring_expense_ends_with_a_dated_decision(self):
        baseline = self._surplus(self.next_year + 2)

        self._decision(
            start_year=self.next_year, monthly_expense="400.00", end_year=self.next_year + 1
        )

        self.assertEqual(self._surplus(self.next_year + 2), baseline)

    def test_recurring_expense_already_in_the_budget_is_not_charged_twice(self):
        baseline = self._surplus(self.next_year)

        # Decisión del año en curso: sus partidas ya viven en el presupuesto vigente,
        # que es de donde sale `annual_operating_expense`.
        self._decision(start_year=self.year, monthly_expense="400.00")

        self.assertEqual(self._surplus(self.next_year), baseline)

    def test_start_year_only_counts_the_months_after_the_purchase(self):
        baseline = self._surplus(self.next_year)

        self._decision(start_year=self.next_year, start_month=7, monthly_expense="400.00")

        self.assertEqual(baseline - self._surplus(self.next_year), Decimal("2400.00"))
