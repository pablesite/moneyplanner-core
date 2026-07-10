from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from budget.models import AnnualExpenseEntry, AnnualIncomeEntry
from memberships.models import FamilyMember
from net_worth.models import Asset, Liability

from plan.models import (
    AssumptionSet,
    FinancialPlan,
    PlanAssetFunction,
    PlanEvent,
    ProjectionSnapshot,
    Scenario,
)
from plan.services_classification import AssetClassificationService
from plan.services_projection import ProjectionService, get_assumption_set
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
            ).exists()
        )

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
