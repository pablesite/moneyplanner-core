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
from net_worth.models import Asset, Liability

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
from plan.services_foundations import FoundationService
from plan.services_quality import DataQualityService
from plan.services_events import (
    close_plan_event,
    register_occurred_event,
    release_occurred_event,
)
from plan.services_inputs import ExpenseBucket, expense_bucket, plan_fiscal_year
from plan.services_lifecycle import cancel_plan_event, materialize_plan_event
from plan.services_projection import (
    ProjectionService,
    build_projection_inputs,
    capital_requirements,
    get_assumption_set,
    plan_event_payloads,
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

    def test_one_off_income_is_not_projected_and_labor_income_stops(self):
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
        row_after_end = next(row for row in result["trajectory"] if row["year"] == year + 2)
        self.assertEqual(row_after_end["future_income"], "0.00")

    def test_expense_taxonomy_is_exhaustive_for_declared_roles(self):
        for role, _label in AnnualExpenseEntry.CashflowRole.choices:
            for time_profile, _label in AnnualExpenseEntry.TimeProfile.choices:
                entry = AnnualExpenseEntry(cashflow_role=role, time_profile=time_profile)
                self.assertNotEqual(expense_bucket(entry), ExpenseBucket.UNCLASSIFIABLE)

    def test_retirement_dates_are_derived_from_birth_date(self):
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

        self.assertEqual(inputs.employment_income_end_date, date(2049, 2, 28))
        self.assertEqual(inputs.earliest_pension_start_date, date(2049, 2, 28))


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
                "employment_income_end_date": "2040-01-01",
                "pension_start_date": "2041-01-01",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["employment_income_end_date"], "2047-06-15")
        self.assertEqual(response.data["pension_start_date"], "2047-06-15")


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
                item["code"] == Recommendation.Code.INCREASE_CONTRIBUTION
                for item in recommendations.data
            )
        )

    def test_recommendation_simulate_creates_draft_scenario_for_same_user(self):
        recommendations = self.client.get(reverse("financial-plan-recommendations"))
        recommendation_id = recommendations.data[0]["id"]

        response = self.client.post(
            reverse("financial-plan-recommendation-simulate", kwargs={"pk": recommendation_id}),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], Scenario.Status.DRAFT)
        self.assertEqual(Scenario.objects.get(id=response.data["id"]).plan, self.plan)


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
