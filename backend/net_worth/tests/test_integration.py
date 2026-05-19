from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from accounts.models import UserSettings
from budget.models import AnnualExpenseEntry
from core.models import InflationIndex
from memberships.models import FamilyMember, Ownership, OwnershipSplit
from ..models import (
    Asset,
    AssetImprovement,
    InvestmentContributionInterval,
    Liability,
    LiabilityValuation,
    LiquidityMonthlyCheckin,
)
from ..services_assets_budget import sync_generated_budget_commitments_for_asset
from ..services_assets_core import get_effective_asset_amount
from ..services_liabilities_core import get_effective_liability_amount


class NetWorthApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="api_nw_user", password="pass1234"
        )
        self.client.force_authenticate(user=self.user)

    def test_asset_create_rejects_invalid_subcategory(self):
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "Cuenta",
                "category": Asset.Category.CASH,
                "subcategory": Asset.Subcategory.ETFS,
                "currency": "EUR",
                "amount": "100.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_asset_create_rejects_missing_tae_for_remunerated_liquidity(self):
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "Cuenta remunerada",
                "category": Asset.Category.CASH,
                "subcategory": Asset.Subcategory.BANK_ACCOUNT,
                "currency": "EUR",
                "amount": "100.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("annual_interest_tae", response.data["error"]["details"])

    def test_asset_create_rejects_missing_duration_for_short_term_deposit(self):
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "Deposito sin plazo",
                "category": Asset.Category.CASH,
                "subcategory": Asset.Subcategory.SHORT_TERM_DEPOSIT,
                "currency": "EUR",
                "annual_interest_tae": "2.50",
                "amount": "1000.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("deposit_term_months", response.data["error"]["details"])

    def test_asset_create_auto_links_accounting_without_account(self):
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "Cuenta contable",
                "category": Asset.Category.CASH,
                "subcategory": Asset.Subcategory.BANK_ACCOUNT,
                "tracking_mode": Asset.TrackingMode.ACCOUNTING,
                "currency": "EUR",
                "annual_interest_tae": "0.00",
                "amount": "500.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertIsNotNone(response.data["accounting_account_id"])
        self.assertEqual(response.data["accounting_integration_state"], "auto_created")
        asset_account = LedgerAccount.objects.get(id=response.data["accounting_account_id"])
        equity_account = LedgerAccount.objects.get(
            user=self.user,
            account_type=LedgerAccount.AccountType.EQUITY,
            origin=LedgerAccount.Origin.SYSTEM,
            currency="EUR",
        )
        opening_tx = LedgerTransaction.objects.get(
            user=self.user,
            origin=LedgerTransaction.Origin.SYSTEM,
            notes=f"net_worth_opening_balance:asset:{response.data['id']}",
        )
        self.assertEqual(opening_tx.description, "Saldo inicial contable: Cuenta contable")
        self.assertEqual(opening_tx.entries.count(), 2)
        self.assertTrue(
            LedgerEntry.objects.filter(
                transaction=opening_tx,
                account=asset_account,
                side=LedgerEntry.Side.DEBIT,
                amount=Decimal("500.00"),
                asset_id=response.data["id"],
            ).exists()
        )
        self.assertTrue(
            LedgerEntry.objects.filter(
                transaction=opening_tx,
                account=equity_account,
                side=LedgerEntry.Side.CREDIT,
                amount=Decimal("500.00"),
            ).exists()
        )

    def test_liability_create_auto_links_accounting_without_account(self):
        response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Hipoteca",
                "category": Liability.Category.MORTGAGE,
                "tracking_mode": Liability.TrackingMode.ACCOUNTING,
                "currency": "EUR",
                "annual_interest_tae": "2.50",
                "amount": "50.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertIsNotNone(response.data["accounting_account_id"])
        self.assertEqual(response.data["accounting_integration_state"], "auto_created")
        liability_account = LedgerAccount.objects.get(id=response.data["accounting_account_id"])
        equity_account = LedgerAccount.objects.get(
            user=self.user,
            account_type=LedgerAccount.AccountType.EQUITY,
            origin=LedgerAccount.Origin.SYSTEM,
            currency="EUR",
        )
        opening_tx = LedgerTransaction.objects.get(
            user=self.user,
            origin=LedgerTransaction.Origin.SYSTEM,
            notes=f"net_worth_opening_balance:liability:{response.data['id']}",
        )
        self.assertEqual(opening_tx.entries.count(), 2)
        self.assertTrue(
            LedgerEntry.objects.filter(
                transaction=opening_tx,
                account=liability_account,
                side=LedgerEntry.Side.CREDIT,
                amount=Decimal("50.00"),
                liability_id=response.data["id"],
            ).exists()
        )
        self.assertTrue(
            LedgerEntry.objects.filter(
                transaction=opening_tx,
                account=equity_account,
                side=LedgerEntry.Side.DEBIT,
                amount=Decimal("50.00"),
            ).exists()
        )

    def test_asset_update_to_accounting_creates_opening_balance_against_equity(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Cuenta manual",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            tracking_mode=Asset.TrackingMode.MANUAL,
            currency="EUR",
            annual_interest_tae=Decimal("0.50"),
            amount=Decimal("1200.00"),
            is_active=True,
        )

        response = self.client.patch(
            f"/api/net-worth/assets/{asset.id}/",
            {"tracking_mode": Asset.TrackingMode.ACCOUNTING},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        asset.refresh_from_db()
        self.assertEqual(asset.tracking_mode, Asset.TrackingMode.ACCOUNTING)
        self.assertIsNotNone(asset.accounting_account_id)
        self.assertEqual(get_effective_asset_amount(asset=asset), Decimal("1200.00"))
        self.assertTrue(
            LedgerTransaction.objects.filter(
                user=self.user,
                origin=LedgerTransaction.Origin.SYSTEM,
                notes=f"net_worth_opening_balance:asset:{asset.id}",
            ).exists()
        )

    def test_asset_update_to_accounting_handles_duplicated_system_equity_accounts(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Cuenta manual duplicados",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            tracking_mode=Asset.TrackingMode.MANUAL,
            currency="EUR",
            annual_interest_tae=Decimal("0.50"),
            amount=Decimal("300.00"),
            is_active=True,
        )
        LedgerAccount.objects.create(
            user=self.user,
            name="Patrimonio neto",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
            origin=LedgerAccount.Origin.SYSTEM,
            is_active=True,
        )
        LedgerAccount.objects.create(
            user=self.user,
            name="Patrimonio neto",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
            origin=LedgerAccount.Origin.SYSTEM,
            is_active=True,
        )

        response = self.client.patch(
            f"/api/net-worth/assets/{asset.id}/",
            {"tracking_mode": Asset.TrackingMode.ACCOUNTING},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        opening_tx = LedgerTransaction.objects.get(
            user=self.user,
            origin=LedgerTransaction.Origin.SYSTEM,
            notes=f"net_worth_opening_balance:asset:{asset.id}",
        )
        self.assertEqual(opening_tx.entries.count(), 2)
        self.assertEqual(
            opening_tx.entries.filter(
                account__account_type=LedgerAccount.AccountType.EQUITY
            ).count(),
            1,
        )

    def test_liability_update_to_accounting_creates_opening_balance_against_equity(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo manual",
            category=Liability.Category.PERSONAL_LOAN,
            tracking_mode=Liability.TrackingMode.MANUAL,
            currency="EUR",
            annual_interest_tae=Decimal("5.00"),
            amount=Decimal("900.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )

        response = self.client.patch(
            f"/api/net-worth/liabilities/{liability.id}/",
            {"tracking_mode": Liability.TrackingMode.ACCOUNTING},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        liability.refresh_from_db()
        self.assertEqual(liability.tracking_mode, Liability.TrackingMode.ACCOUNTING)
        self.assertIsNotNone(liability.accounting_account_id)
        self.assertEqual(get_effective_liability_amount(liability=liability), Decimal("900.00"))
        self.assertTrue(
            LedgerTransaction.objects.filter(
                user=self.user,
                origin=LedgerTransaction.Origin.SYSTEM,
                notes=f"net_worth_opening_balance:liability:{liability.id}",
            ).exists()
        )

    def test_liability_accounting_opening_balance_is_resynced_on_edit(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo manual",
            category=Liability.Category.PERSONAL_LOAN,
            tracking_mode=Liability.TrackingMode.MANUAL,
            currency="EUR",
            annual_interest_tae=Decimal("5.00"),
            amount=Decimal("900.00"),
            start_date=date(2026, 3, 18),
            is_active=True,
        )

        to_accounting_res = self.client.patch(
            f"/api/net-worth/liabilities/{liability.id}/",
            {"tracking_mode": Liability.TrackingMode.ACCOUNTING},
            format="json",
        )
        self.assertEqual(to_accounting_res.status_code, status.HTTP_200_OK, to_accounting_res.data)

        opening_note = f"net_worth_opening_balance:liability:{liability.id}"
        opening_tx = LedgerTransaction.objects.get(
            user=self.user,
            origin=LedgerTransaction.Origin.SYSTEM,
            notes=opening_note,
        )
        self.assertEqual(opening_tx.booking_date, date(2026, 3, 18))

        update_res = self.client.patch(
            f"/api/net-worth/liabilities/{liability.id}/",
            {
                "start_date": "2020-01-01",
                "amount": "1200.00",
            },
            format="json",
        )
        self.assertEqual(update_res.status_code, status.HTTP_200_OK, update_res.data)

        self.assertEqual(
            LedgerTransaction.objects.filter(
                user=self.user,
                origin=LedgerTransaction.Origin.SYSTEM,
                notes=opening_note,
            ).count(),
            1,
        )
        opening_tx.refresh_from_db()
        self.assertEqual(opening_tx.booking_date, date(2020, 1, 1))

    def test_liability_create_rejects_missing_tae_for_mortgage(self):
        response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Hipoteca",
                "category": Liability.Category.MORTGAGE,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "amount": "50.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("annual_interest_tae", response.data["error"]["details"])

    def test_liability_create_rejects_negative_tae(self):
        response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Tarjeta",
                "category": Liability.Category.CREDIT_CARD,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "annual_interest_tae": "-1.00",
                "amount": "300.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("annual_interest_tae", response.data["error"]["details"])

    def test_asset_and_liability_create_accept_explicit_start_date(self):
        asset_res = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "Cuenta",
                "category": Asset.Category.CASH,
                "subcategory": Asset.Subcategory.BANK_ACCOUNT,
                "currency": "EUR",
                "start_date": "2020-01-01",
                "annual_interest_tae": "0.80",
                "amount": "100.00",
            },
            format="json",
        )
        self.assertEqual(asset_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(asset_res.data["start_date"], "2020-01-01")

        liability_res = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Prestamo",
                "category": Liability.Category.PERSONAL_LOAN,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "start_date": "2021-06-15",
                "annual_interest_tae": "5.20",
                "amount": "12000.00",
            },
            format="json",
        )
        self.assertEqual(liability_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(liability_res.data["start_date"], "2021-06-15")
        self.assertIsNone(liability_res.data["payment_start_date"])

    def test_liability_create_accepts_payment_start_date_after_contratacion(self):
        liability_res = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Prestamo con carencia",
                "category": Liability.Category.PERSONAL_LOAN,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "start_date": "2024-02-01",
                "payment_start_date": "2024-09-21",
                "annual_interest_tae": "5.20",
                "amount": "12000.00",
                "term_months": 24,
            },
            format="json",
        )
        self.assertEqual(liability_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(liability_res.data["payment_start_date"], "2024-09-21")

    def test_asset_create_no_longer_backfills_fx_history_inline(self):
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "Cuenta USD",
                "category": Asset.Category.CASH,
                "subcategory": Asset.Subcategory.BANK_ACCOUNT,
                "currency": "USD",
                "start_date": "2025-03-03",
                "annual_interest_tae": "0.00",
                "amount": "1000.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["currency"], "USD")

    def test_liability_create_no_longer_backfills_fx_history_inline(self):
        response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Tarjeta USD",
                "category": Liability.Category.CREDIT_CARD,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "USD",
                "start_date": "2025-03-03",
                "annual_interest_tae": "18.00",
                "amount": "300.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["currency"], "USD")

    def test_asset_create_accepts_short_term_deposit_duration(self):
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "Deposito 6 meses",
                "category": Asset.Category.CASH,
                "subcategory": Asset.Subcategory.SHORT_TERM_DEPOSIT,
                "currency": "EUR",
                "start_date": "2026-02-01",
                "annual_interest_tae": "3.00",
                "deposit_term_months": 6,
                "amount": "10000.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["deposit_term_months"], 6)

    def test_asset_create_accepts_initial_purchase_and_amortization_fields(self):
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "Portatil",
                "category": Asset.Category.FURNISHINGS,
                "subcategory": Asset.Subcategory.TECHNOLOGY,
                "currency": "EUR",
                "start_date": "2024-03-01",
                "initial_purchase_value": "1800.00",
                "amortization_method": Asset.AmortizationMethod.STRAIGHT_LINE,
                "amortization_term_years": 4,
                "amount": "1200.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["initial_purchase_value"], "1800.00000000")
        self.assertEqual(response.data["amortization_method"], "straight_line")
        self.assertEqual(response.data["amortization_term_years"], 4)

    def test_asset_create_uses_amount_as_initial_purchase_when_amortization_is_defined(self):
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "Monitor",
                "category": Asset.Category.FURNISHINGS,
                "subcategory": Asset.Subcategory.TECHNOLOGY,
                "currency": "EUR",
                "start_date": "2024-03-01",
                "amortization_method": Asset.AmortizationMethod.STRAIGHT_LINE,
                "amortization_term_years": 4,
                "amount": "900.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["initial_purchase_value"], "900.00000000")
        self.assertEqual(response.data["amortization_method"], "straight_line")
        self.assertEqual(response.data["amortization_term_years"], 4)

    def test_asset_create_returns_amortized_effective_amount_for_straight_line_assets(self):
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "Cama",
                "category": Asset.Category.FURNISHINGS,
                "subcategory": Asset.Subcategory.HOME_FURNISHINGS,
                "currency": "EUR",
                "start_date": "2016-02-01",
                "amortization_method": Asset.AmortizationMethod.STRAIGHT_LINE,
                "amortization_term_years": 10,
                "amount": "10000.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Decimal(response.data["effective_amount"]), Decimal("0"))

    @patch("net_worth.services_assets_core.timezone.localdate", return_value=date(2026, 2, 1))
    def test_asset_create_returns_ipc_adjusted_effective_amount_for_furnishings(
        self, _mock_localdate
    ):
        InflationIndex.objects.create(
            region="ES",
            period=date(2016, 2, 1),
            index=Decimal("100.0000"),
        )
        InflationIndex.objects.create(
            region="ES",
            period=date(2026, 2, 1),
            index=Decimal("120.0000"),
        )
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "Sofa",
                "category": Asset.Category.FURNISHINGS,
                "subcategory": Asset.Subcategory.HOME_FURNISHINGS,
                "currency": "EUR",
                "start_date": "2016-02-01",
                "amortization_method": Asset.AmortizationMethod.STRAIGHT_LINE,
                "amortization_term_years": 20,
                "amount": "10000.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(
            Decimal(response.data["effective_amount"]).quantize(Decimal("0.01")),
            Decimal("6000.00"),
        )

    @patch("net_worth.services_assets_core.timezone.localdate", return_value=date(2056, 2, 1))
    def test_asset_create_returns_residual_floor_effective_amount_for_vehicle(
        self, _mock_localdate
    ):
        InflationIndex.objects.create(
            region="ES",
            period=date(2016, 2, 1),
            index=Decimal("100.0000"),
        )
        InflationIndex.objects.create(
            region="ES",
            period=date(2056, 2, 1),
            index=Decimal("120.0000"),
        )
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "Coche",
                "category": Asset.Category.FURNISHINGS,
                "subcategory": Asset.Subcategory.VEHICLES,
                "currency": "EUR",
                "start_date": "2016-02-01",
                "amortization_method": Asset.AmortizationMethod.STRAIGHT_LINE,
                "amount": "10000.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(
            Decimal(response.data["effective_amount"]).quantize(Decimal("0.01")),
            Decimal("1800.00"),
        )
        self.assertEqual(response.data["amortization_term_years"], 20)

    def test_asset_create_primary_home_auto_valuation(self):
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "Casa",
                "category": Asset.Category.REAL_ESTATE,
                "subcategory": Asset.Subcategory.PRIMARY_HOME,
                "currency": "EUR",
                "start_date": "2025-01-01",
                "amount": "100000.00",
                "valuation_model": Asset.ValuationModel.REAL_ESTATE_AUTO,
                "land_value_share_percent": "30.00",
                "land_annual_appreciation_percent": "4.000",
                "building_annual_depreciation_percent": "1.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["valuation_model"], Asset.ValuationModel.REAL_ESTATE_AUTO)
        self.assertEqual(response.data["initial_purchase_value"], "100000.00000000")
        self.assertIn("effective_amount", response.data)

    def test_asset_create_primary_home_auto_valuation_with_improvements(self):
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "Casa reformada",
                "category": Asset.Category.REAL_ESTATE,
                "subcategory": Asset.Subcategory.PRIMARY_HOME,
                "currency": "EUR",
                "start_date": "2025-01-01",
                "amount": "100000.00",
                "valuation_model": Asset.ValuationModel.REAL_ESTATE_AUTO,
                "land_value_share_percent": "30.00",
                "land_annual_appreciation_percent": "4.000",
                "building_annual_depreciation_percent": "1.00",
                "improvements": [
                    {
                        "name": "Reforma cocina",
                        "reform_date": "2025-06-01",
                        "amount": "15000.00",
                        "amortization_method": "straight_line",
                        "amortization_term_years": 15,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(len(response.data["improvements"]), 1)
        self.assertEqual(response.data["improvements"][0]["name"], "Reforma cocina")

    def test_asset_create_second_home_auto_valuation_with_improvements(self):
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "Atico",
                "category": Asset.Category.REAL_ESTATE,
                "subcategory": Asset.Subcategory.SECOND_HOME,
                "currency": "EUR",
                "start_date": "2020-01-01",
                "amount": "100000.00",
                "valuation_model": Asset.ValuationModel.REAL_ESTATE_AUTO,
                "land_value_share_percent": "40.00",
                "land_annual_appreciation_percent": "8.000",
                "building_annual_depreciation_percent": "0.20",
                "improvements": [
                    {
                        "name": "Reforma integral",
                        "reform_date": "2021-06-01",
                        "amount": "15000.00",
                        "amortization_method": "straight_line",
                        "amortization_term_years": 15,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["valuation_model"], Asset.ValuationModel.REAL_ESTATE_AUTO)
        self.assertEqual(len(response.data["improvements"]), 1)
        self.assertEqual(response.data["improvements"][0]["name"], "Reforma integral")

    def test_asset_update_syncs_improvements_list(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Casa",
            category=Asset.Category.REAL_ESTATE,
            subcategory=Asset.Subcategory.PRIMARY_HOME,
            currency="EUR",
            start_date=date(2025, 1, 1),
            amount=Decimal("100000.00"),
            valuation_model=Asset.ValuationModel.REAL_ESTATE_AUTO,
            land_value_share_percent=Decimal("30.00"),
            land_annual_appreciation_percent=Decimal("4.000"),
            building_annual_depreciation_percent=Decimal("1.00"),
            initial_purchase_value=Decimal("100000.00"),
            is_active=True,
        )
        kept = AssetImprovement.objects.create(
            asset=asset,
            name="Suelo radiante",
            reform_date=date(2025, 5, 1),
            amount=Decimal("9000.00"),
            amortization_method=AssetImprovement.AmortizationMethod.STRAIGHT_LINE,
            amortization_term_years=20,
        )
        deleted = AssetImprovement.objects.create(
            asset=asset,
            name="Pintura inicial",
            reform_date=date(2025, 4, 1),
            amount=Decimal("1000.00"),
            amortization_method=AssetImprovement.AmortizationMethod.NONE,
        )

        response = self.client.patch(
            f"/api/net-worth/assets/{asset.id}/",
            {
                "improvements": [
                    {
                        "id": kept.id,
                        "name": "Suelo radiante premium",
                        "reform_date": "2025-05-01",
                        "amount": "9500.00",
                        "amortization_method": "straight_line",
                        "amortization_term_years": 20,
                    },
                    {
                        "name": "Aerotermia",
                        "reform_date": "2026-01-10",
                        "amount": "12000.00",
                        "amortization_method": "none",
                    },
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(len(response.data["improvements"]), 2)
        kept.refresh_from_db()
        self.assertEqual(kept.name, "Suelo radiante premium")
        self.assertEqual(kept.amount, Decimal("9500.00"))
        self.assertFalse(AssetImprovement.objects.filter(id=deleted.id).exists())

    def test_asset_update_primary_home_auto_valuation_syncs_initial_purchase_value_from_amount(
        self,
    ):
        asset = Asset.objects.create(
            user=self.user,
            name="Casa",
            category=Asset.Category.REAL_ESTATE,
            subcategory=Asset.Subcategory.PRIMARY_HOME,
            currency="EUR",
            start_date=date(2025, 1, 1),
            amount=Decimal("100000.00"),
            valuation_model=Asset.ValuationModel.REAL_ESTATE_AUTO,
            land_value_share_percent=Decimal("30.00"),
            land_annual_appreciation_percent=Decimal("4.000"),
            building_annual_depreciation_percent=Decimal("1.00"),
            initial_purchase_value=Decimal("100000.00"),
            is_active=True,
        )

        response = self.client.patch(
            f"/api/net-worth/assets/{asset.id}/",
            {"amount": "91000.00"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["amount"], "91000.00000000")
        self.assertEqual(response.data["initial_purchase_value"], "91000.00000000")

        asset.refresh_from_db()
        self.assertEqual(asset.amount, Decimal("91000.00"))
        self.assertEqual(asset.initial_purchase_value, Decimal("91000.00"))

    def test_periodic_investment_asset_generates_financial_investment_commitments(self):
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "Fondo entrada vivienda",
                "category": Asset.Category.INVESTMENTS,
                "subcategory": Asset.Subcategory.FUNDS,
                "currency": "EUR",
                "start_date": "2026-01-15",
                "amount": "5000.00",
                "initial_purchase_value": "5000.00",
                "contribution_intervals": [
                    {
                        "start_date": "2026-01-15",
                        "end_date": "2027-12-15",
                        "amount": "300.00",
                        "frequency": "monthly",
                        "currency": "EUR",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        asset_id = response.data["id"]

        generated = AnnualExpenseEntry.objects.filter(
            user=self.user,
            source_asset_id=asset_id,
            is_system_generated=True,
        ).order_by("fiscal_year")
        self.assertEqual(list(generated.values_list("fiscal_year", flat=True)), [2026, 2027])
        row_2026 = generated.get(fiscal_year=2026)
        self.assertEqual(row_2026.category, AnnualExpenseEntry.Category.FINANCIAL_INVESTMENTS)
        self.assertEqual(row_2026.subcategory, "index_funds")
        self.assertEqual(row_2026.time_profile, AnnualExpenseEntry.TimeProfile.TERM_RECURRENT)
        self.assertEqual(
            row_2026.cashflow_role, AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT
        )
        self.assertEqual(row_2026.amount_annual, Decimal("3600.00"))

    def test_investment_asset_accepts_nested_contribution_intervals(self):
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "Fondo por tramos",
                "category": Asset.Category.INVESTMENTS,
                "subcategory": Asset.Subcategory.FUNDS,
                "currency": "EUR",
                "start_date": "2026-01-15",
                "amount": "5000.00",
                "initial_purchase_value": "5000.00",
                "contribution_intervals": [
                    {
                        "start_date": "2026-01-15",
                        "end_date": "2026-06-15",
                        "amount": "100.00",
                        "frequency": "monthly",
                        "currency": "EUR",
                    },
                    {
                        "start_date": "2026-07-15",
                        "end_date": "2026-12-15",
                        "amount": "200.00",
                        "frequency": "monthly",
                        "currency": "EUR",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        asset = Asset.objects.get(id=response.data["id"])
        intervals = list(asset.contribution_intervals.order_by("start_date"))
        self.assertEqual(len(intervals), 2)
        self.assertEqual(intervals[0].amount, Decimal("100.00"))
        self.assertEqual(intervals[1].amount, Decimal("200.00"))
        generated = AnnualExpenseEntry.objects.get(
            user=self.user,
            source_asset=asset,
            is_system_generated=True,
            fiscal_year=2026,
        )
        self.assertEqual(generated.amount_annual, Decimal("1800.00"))

    def test_investment_asset_rejects_overlapping_contribution_intervals(self):
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "Fondo solapado",
                "category": Asset.Category.INVESTMENTS,
                "subcategory": Asset.Subcategory.FUNDS,
                "currency": "EUR",
                "start_date": "2026-01-15",
                "amount": "5000.00",
                "initial_purchase_value": "5000.00",
                "contribution_intervals": [
                    {
                        "start_date": "2026-01-01",
                        "end_date": "2026-06-01",
                        "amount": "100.00",
                        "frequency": "monthly",
                    },
                    {
                        "start_date": "2026-06-01",
                        "end_date": "2026-12-01",
                        "amount": "200.00",
                        "frequency": "monthly",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("contribution_intervals", response.data["error"]["details"])

    def test_investment_asset_patch_uses_set_pattern_for_contribution_intervals(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Fondo editable",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            start_date=date(2026, 1, 15),
            amount=Decimal("5000.00"),
            initial_purchase_value=Decimal("5000.00"),
            is_active=True,
        )
        InvestmentContributionInterval.objects.create(
            asset=asset,
            start_date=date(2026, 1, 15),
            end_date=date(2026, 12, 15),
            amount=Decimal("100.00"),
            frequency=Asset.InvestmentContributionFrequency.MONTHLY,
            currency="EUR",
        )

        response = self.client.patch(
            f"/api/net-worth/assets/{asset.id}/",
            {
                "contribution_intervals": [
                    {
                        "start_date": "2026-01-15",
                        "end_date": "2026-06-15",
                        "amount": "150.00",
                        "frequency": "monthly",
                    },
                    {
                        "start_date": "2026-07-15",
                        "end_date": None,
                        "amount": "50.00",
                        "frequency": "monthly",
                    },
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        asset.refresh_from_db()
        intervals = list(asset.contribution_intervals.order_by("start_date"))
        self.assertEqual(len(intervals), 2)
        self.assertEqual(intervals[0].amount, Decimal("150.00"))
        self.assertIsNone(intervals[1].end_date)

    def test_periodic_investment_asset_sync_is_atomic_when_budget_row_creation_fails(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Fondo atomico",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            start_date=date(2026, 1, 15),
            amount=Decimal("5000.00"),
            initial_purchase_value=Decimal("5000.00"),
            is_active=True,
        )
        InvestmentContributionInterval.objects.create(
            asset=asset,
            start_date=date(2026, 1, 15),
            end_date=date(2027, 2, 15),
            amount=Decimal("300.00"),
            frequency=Asset.InvestmentContributionFrequency.MONTHLY,
            currency="EUR",
        )
        original_create = AnnualExpenseEntry.objects.create
        call_count = {"value": 0}

        def create_side_effect(*args, **kwargs):
            if call_count["value"] == 0:
                call_count["value"] += 1
                return original_create(*args, **kwargs)
            raise RuntimeError("boom")

        with patch.object(
            AnnualExpenseEntry.objects,
            "create",
            side_effect=create_side_effect,
        ):
            with self.assertRaises(RuntimeError):
                sync_generated_budget_commitments_for_asset(asset=asset)

        self.assertFalse(
            AnnualExpenseEntry.objects.filter(
                user=self.user,
                source_asset_id=asset.id,
                is_system_generated=True,
            ).exists()
        )

    def test_periodic_investment_asset_requires_purchase_value_with_intervals(self):
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "Reserva ATRIO",
                "category": Asset.Category.INVESTMENTS,
                "subcategory": Asset.Subcategory.FUNDS,
                "currency": "EUR",
                "start_date": "2026-01-15",
                "contribution_intervals": [
                    {
                        "start_date": "2026-01-15",
                        "end_date": None,
                        "amount": "300.00",
                        "frequency": "monthly",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("amount", response.data["error"]["details"])

    def test_periodic_investment_asset_supports_indefinite_end_date(self):
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "ETF indefinido",
                "category": Asset.Category.INVESTMENTS,
                "subcategory": Asset.Subcategory.ETFS,
                "currency": "EUR",
                "start_date": "2026-01-15",
                "amount": "1000.00",
                "initial_purchase_value": "1000.00",
                "contribution_intervals": [
                    {
                        "start_date": "2026-01-15",
                        "end_date": None,
                        "amount": "100.00",
                        "frequency": "weekly",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        asset_id = response.data["id"]
        generated = AnnualExpenseEntry.objects.filter(
            user=self.user,
            source_asset_id=asset_id,
            is_system_generated=True,
        ).order_by("fiscal_year")
        self.assertEqual(list(generated.values_list("fiscal_year", flat=True)), [2026, 2027])
        first_row = generated.first()
        self.assertIsNotNone(first_row)
        assert first_row is not None
        self.assertEqual(
            first_row.time_profile, AnnualExpenseEntry.TimeProfile.STRUCTURAL_RECURRENT
        )
        self.assertIsNone(first_row.term_end_year)

    def test_periodic_investment_asset_supports_contribution_currency(self):
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "Bitcoin DCA USD",
                "category": Asset.Category.INVESTMENTS,
                "subcategory": Asset.Subcategory.CRYPTOCURRENCIES,
                "currency": "BTC",
                "start_date": "2026-01-01",
                "amount": "0.03725777",
                "initial_purchase_value": "0.03725777",
                "contribution_intervals": [
                    {
                        "start_date": "2026-01-01",
                        "end_date": None,
                        "amount": "25.00",
                        "frequency": "weekly",
                        "currency": "USD",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["effective_amount"], "0.03725777")
        generated = AnnualExpenseEntry.objects.filter(
            user=self.user,
            source_asset_id=response.data["id"],
            is_system_generated=True,
        )
        self.assertTrue(generated.exists())
        first_row = generated.order_by("fiscal_year").first()
        self.assertIsNotNone(first_row)
        assert first_row is not None
        self.assertEqual(first_row.currency, "USD")

    def test_periodic_investment_asset_manual_market_value_overrides_effective_amount(self):
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "ETF valorado a mercado",
                "category": Asset.Category.INVESTMENTS,
                "subcategory": Asset.Subcategory.ETFS,
                "currency": "EUR",
                "start_date": "2026-01-15",
                "amount": "1000.00",
                "initial_purchase_value": "1000.00",
                "investment_contribution_mode": "periodic_contribution",
                "investment_contribution_frequency": "weekly",
                "monthly_contribution_amount": "30.00",
                "market_value_override": "1450.35",
                "market_value_override_date": "2026-03-01",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["effective_amount"], "1450.35000000")
        self.assertEqual(response.data["market_value_override"], "1450.35000000")
        self.assertEqual(response.data["market_value_override_date"], "2026-03-01")

        detail = self.client.get(f"/api/net-worth/assets/{response.data['id']}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK, detail.data)
        self.assertEqual(detail.data["effective_amount"], "1450.35000000")

    def test_periodic_investment_asset_manual_market_value_requires_date(self):
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "ETF sin fecha de valoracion",
                "category": Asset.Category.INVESTMENTS,
                "subcategory": Asset.Subcategory.ETFS,
                "currency": "EUR",
                "start_date": "2026-01-15",
                "amount": "1000.00",
                "initial_purchase_value": "1000.00",
                "investment_contribution_mode": "periodic_contribution",
                "investment_contribution_frequency": "weekly",
                "monthly_contribution_amount": "30.00",
                "market_value_override": "1450.35",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("market_value_override_date", response.data["error"]["details"])

    def test_periodic_investment_asset_update_recalculates_generated_amount_for_current_year(self):
        current_year = timezone.localdate().year
        create_response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "ETF semanal editable",
                "category": Asset.Category.INVESTMENTS,
                "subcategory": Asset.Subcategory.ETFS,
                "currency": "EUR",
                "start_date": f"{current_year}-03-01",
                "amount": "1000.00",
                "initial_purchase_value": "1000.00",
                "contribution_intervals": [
                    {
                        "start_date": f"{current_year}-03-01",
                        "end_date": None,
                        "amount": "30.00",
                        "frequency": "weekly",
                        "currency": "EUR",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED, create_response.data)
        asset_id = create_response.data["id"]

        row = AnnualExpenseEntry.objects.get(
            user=self.user,
            source_asset_id=asset_id,
            is_system_generated=True,
            fiscal_year=current_year,
        )
        amount_before = row.amount_annual
        row.notes = "Nota personalizada legacy"
        row.save(update_fields=["notes"])

        update_response = self.client.patch(
            f"/api/net-worth/assets/{asset_id}/",
            {
                "start_date": f"{current_year}-01-01",
                "contribution_intervals": [
                    {
                        "start_date": f"{current_year}-01-01",
                        "end_date": None,
                        "amount": "30.00",
                        "frequency": "weekly",
                        "currency": "USD",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK, update_response.data)

        row.refresh_from_db()
        self.assertGreater(row.amount_annual, amount_before)
        self.assertEqual(row.currency, "USD")
        self.assertEqual(row.notes, "Nota personalizada legacy")

    def test_periodic_investment_asset_delete_removes_generated_commitments(self):
        create_response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "Reserva vivienda",
                "category": Asset.Category.INVESTMENTS,
                "subcategory": Asset.Subcategory.FUNDS,
                "currency": "EUR",
                "start_date": "2026-01-15",
                "amount": "5000.00",
                "initial_purchase_value": "5000.00",
                "contribution_intervals": [
                    {
                        "start_date": "2026-01-15",
                        "end_date": "2027-12-15",
                        "amount": "300.00",
                        "frequency": "monthly",
                        "currency": "EUR",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED, create_response.data)
        asset_id = create_response.data["id"]
        self.assertTrue(
            AnnualExpenseEntry.objects.filter(
                user=self.user, source_asset_id=asset_id, is_system_generated=True
            ).exists()
        )

        delete_response = self.client.delete(f"/api/net-worth/assets/{asset_id}/")
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            AnnualExpenseEntry.objects.filter(
                user=self.user, source_asset_id=asset_id, is_system_generated=True
            ).exists()
        )

    def test_periodic_investment_generated_commitments_owner_name_follows_ownership_link(self):
        response = self.client.post(
            "/api/net-worth/assets/",
            {
                "name": "Reserva vivienda ownership",
                "category": Asset.Category.INVESTMENTS,
                "subcategory": Asset.Subcategory.FUNDS,
                "currency": "EUR",
                "start_date": "2026-01-15",
                "amount": "5000.00",
                "initial_purchase_value": "5000.00",
                "contribution_intervals": [
                    {
                        "start_date": "2026-01-15",
                        "end_date": "2027-12-15",
                        "amount": "300.00",
                        "frequency": "monthly",
                        "currency": "EUR",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        asset_id = response.data["id"]

        generated_before = AnnualExpenseEntry.objects.filter(
            user=self.user,
            source_asset_id=asset_id,
            is_system_generated=True,
        ).order_by("fiscal_year")
        self.assertTrue(generated_before.exists())
        self.assertEqual(generated_before.first().owner_name, "")

        ana = FamilyMember.objects.create(
            user=self.user,
            name="Ana",
            role=FamilyMember.Role.ADULT,
            is_active=True,
        )
        pablo = FamilyMember.objects.create(
            user=self.user,
            name="Pablo",
            role=FamilyMember.Role.ADULT,
            is_active=True,
        )
        shared = Ownership.objects.create(user=self.user, kind=Ownership.Kind.SHARED, member=None)
        OwnershipSplit.objects.create(ownership=shared, member=ana, percent=Decimal("50.00"))
        OwnershipSplit.objects.create(ownership=shared, member=pablo, percent=Decimal("50.00"))

        sync_response = self.client.post(
            "/api/ownership-links/sync/",
            {
                "target_type": "asset",
                "target_id": asset_id,
                "ownership_id": shared.id,
            },
            format="json",
        )
        self.assertEqual(sync_response.status_code, status.HTTP_200_OK, sync_response.data)

        generated_after = AnnualExpenseEntry.objects.filter(
            user=self.user,
            source_asset_id=asset_id,
            is_system_generated=True,
        )
        self.assertTrue(generated_after.exists())
        for row in generated_after:
            self.assertEqual(row.category, AnnualExpenseEntry.Category.FINANCIAL_INVESTMENTS)
            self.assertEqual(row.subcategory, "index_funds")
            self.assertIn("Compartido", row.owner_name)
            self.assertIn("Ana", row.owner_name)
            self.assertIn("Pablo", row.owner_name)
            self.assertIn("50%", row.owner_name)

    def test_liability_create_rejects_expected_end_date_before_start_date(self):
        response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Hipoteca",
                "category": Liability.Category.MORTGAGE,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "start_date": "2026-06-01",
                "expected_end_date": "2026-05-01",
                "annual_interest_tae": "2.50",
                "amount": "150000.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expected_end_date", response.data["error"]["details"])

    def test_liability_create_with_financed_asset_sets_asset_backed(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Casa",
            category=Asset.Category.REAL_ESTATE,
            subcategory=Asset.Subcategory.PRIMARY_HOME,
            currency="EUR",
            amount=Decimal("200000.00"),
            is_active=True,
        )
        response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Hipoteca",
                "category": Liability.Category.MORTGAGE,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "annual_interest_tae": "2.50",
                "amount": "150000.00",
                "financed_asset_id": asset.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["is_asset_backed"])
        self.assertEqual(response.data["financed_asset_ref"], asset.id)

    def test_liability_create_generates_budget_commitment_entries_by_year(self):
        response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Compra vivienda ATRIO",
                "category": Liability.Category.OTHER,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "start_date": "2024-09-01",
                "annual_interest_tae": "0.00",
                "amount": "33010.56",
                "principal_amount": "33010.56",
                "term_months": 24,
                "rate_type": "fixed",
                "payment_frequency": "monthly",
                "amortization_system": "french",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        liability_id = response.data["id"]
        rows = AnnualExpenseEntry.objects.filter(
            user=self.user, source_liability_id=liability_id, is_system_generated=True
        ).order_by("fiscal_year")
        self.assertEqual(list(rows.values_list("fiscal_year", flat=True)), [2024, 2025, 2026])
        row_2026 = rows.get(fiscal_year=2026)
        self.assertEqual(row_2026.category, AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES)
        self.assertEqual(row_2026.subcategory, "financial_commitments")
        self.assertEqual(row_2026.time_profile, AnnualExpenseEntry.TimeProfile.TERM_RECURRENT)
        self.assertEqual(
            row_2026.cashflow_role, AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT
        )
        self.assertEqual(row_2026.term_end_year, 2026)
        # 9 cuotas (ene-sep 2026) de 1375.44 -> 12378.96
        self.assertEqual(row_2026.amount_annual, Decimal("12378.96"))

    def test_unbacked_liability_can_override_generated_expense_subcategory(self):
        response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "FIV IVI",
                "category": Liability.Category.PERSONAL_LOAN,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "start_date": "2026-01-15",
                "annual_interest_tae": "0.00",
                "amount": "9000.00",
                "principal_amount": "9000.00",
                "term_months": 12,
                "rate_type": "fixed",
                "payment_frequency": "monthly",
                "amortization_system": "french",
                "expense_subcategory_override": "family_childcare",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        row = AnnualExpenseEntry.objects.filter(
            user=self.user,
            source_liability_id=response.data["id"],
            is_system_generated=True,
        ).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.category, AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES)
        self.assertEqual(row.subcategory, "family_childcare")

    def test_liability_create_with_financed_real_estate_generates_temporary_commitment_expense(
        self,
    ):
        asset = Asset.objects.create(
            user=self.user,
            name="Entrada casa",
            category=Asset.Category.REAL_ESTATE,
            subcategory=Asset.Subcategory.PRIMARY_HOME,
            currency="EUR",
            amount=Decimal("100000.00"),
            is_active=True,
        )
        response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Prestamo entrada vivienda",
                "category": Liability.Category.PERSONAL_LOAN,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "start_date": "2026-01-15",
                "annual_interest_tae": "0.00",
                "amount": "12000.00",
                "principal_amount": "12000.00",
                "term_months": 12,
                "rate_type": "fixed",
                "payment_frequency": "monthly",
                "amortization_system": "french",
                "financed_asset_id": asset.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        generated = AnnualExpenseEntry.objects.filter(
            user=self.user,
            source_liability_id=response.data["id"],
            is_system_generated=True,
        ).order_by("fiscal_year")
        self.assertTrue(generated.exists())
        row = generated.first()
        self.assertEqual(row.category, AnnualExpenseEntry.Category.REAL_ESTATE_ASSETS)
        self.assertEqual(row.subcategory, "property_purchase")
        self.assertEqual(row.cashflow_role, AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT)

    def test_financed_liability_clears_expense_subcategory_override(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Entrada casa",
            category=Asset.Category.REAL_ESTATE,
            subcategory=Asset.Subcategory.PRIMARY_HOME,
            currency="EUR",
            amount=Decimal("100000.00"),
            is_active=True,
        )
        response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Prestamo entrada vivienda",
                "category": Liability.Category.PERSONAL_LOAN,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "start_date": "2026-01-15",
                "annual_interest_tae": "0.00",
                "amount": "12000.00",
                "principal_amount": "12000.00",
                "term_months": 12,
                "rate_type": "fixed",
                "payment_frequency": "monthly",
                "amortization_system": "french",
                "financed_asset_id": asset.id,
                "expense_subcategory_override": "family_childcare",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertIsNone(response.data["expense_subcategory_override"])

    def test_mortgage_liability_generates_mortgage_principal_temporary_recurrent_expense(self):
        response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Hipoteca vivienda habitual",
                "category": Liability.Category.MORTGAGE,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "start_date": "2026-01-15",
                "annual_interest_tae": "2.50",
                "amount": "180000.00",
                "principal_amount": "180000.00",
                "term_months": 360,
                "rate_type": "fixed",
                "payment_frequency": "monthly",
                "amortization_system": "french",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        generated = AnnualExpenseEntry.objects.filter(
            user=self.user,
            source_liability_id=response.data["id"],
            is_system_generated=True,
        ).order_by("fiscal_year")
        self.assertTrue(generated.exists())
        row = generated.first()
        self.assertEqual(row.category, AnnualExpenseEntry.Category.REAL_ESTATE_ASSETS)
        self.assertEqual(row.subcategory, "mortgage_principal")
        self.assertEqual(row.time_profile, AnnualExpenseEntry.TimeProfile.TERM_RECURRENT)
        self.assertEqual(row.cashflow_role, AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT)

    def test_mortgage_with_cancellation_forecast_truncates_recurrent_and_generates_one_offs(self):
        response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Hipoteca cancelacion prevista",
                "category": Liability.Category.MORTGAGE,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "start_date": "2026-01-15",
                "annual_interest_tae": "2.50",
                "amount": "120000.00",
                "principal_amount": "120000.00",
                "term_months": 360,
                "rate_type": "fixed",
                "payment_frequency": "monthly",
                "amortization_system": "french",
                "early_repayment_fee_percent": "0.50",
                "cancellation_forecast_enabled": True,
                "cancellation_date": "2027-06-15",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        liability_id = response.data["id"]

        generated = AnnualExpenseEntry.objects.filter(
            user=self.user,
            source_liability_id=liability_id,
            is_system_generated=True,
        )
        recurrent = generated.filter(event_group=f"liability_{liability_id}").order_by(
            "fiscal_year"
        )
        self.assertTrue(recurrent.exists())
        # La deuda se cancela en 2027-06, por lo que no deben existir compromisos recurrentes en 2028+.
        self.assertEqual(set(recurrent.values_list("fiscal_year", flat=True)), {2026, 2027})

        principal_row = generated.get(
            event_group=f"liability_{liability_id}_cancellation_principal"
        )
        self.assertEqual(principal_row.expense_type, AnnualExpenseEntry.ExpenseType.ONE_OFF)
        self.assertEqual(principal_row.time_profile, AnnualExpenseEntry.TimeProfile.ONE_OFF)
        self.assertEqual(principal_row.target_month, 6)
        self.assertGreater(principal_row.amount_annual, Decimal("0.00"))

        fee_row = generated.get(event_group=f"liability_{liability_id}_cancellation_fee")
        self.assertEqual(fee_row.expense_type, AnnualExpenseEntry.ExpenseType.ONE_OFF)
        self.assertEqual(fee_row.time_profile, AnnualExpenseEntry.TimeProfile.ONE_OFF)
        self.assertEqual(fee_row.target_month, 6)
        self.assertGreater(fee_row.amount_annual, Decimal("0.00"))

    def test_mortgage_cancellation_can_omit_installment_for_cancellation_month(self):
        response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Hipoteca sin cuota del mes de cancelacion",
                "category": Liability.Category.MORTGAGE,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "start_date": "2026-01-15",
                "annual_interest_tae": "2.50",
                "amount": "120000.00",
                "principal_amount": "120000.00",
                "term_months": 360,
                "rate_type": "fixed",
                "payment_frequency": "monthly",
                "amortization_system": "french",
                "cancellation_forecast_enabled": True,
                "cancellation_date": "2027-06-15",
                "cancellation_include_payment_month": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        liability_id = response.data["id"]

        recurrent_2027 = AnnualExpenseEntry.objects.get(
            user=self.user,
            source_liability_id=liability_id,
            is_system_generated=True,
            fiscal_year=2027,
            event_group=f"liability_{liability_id}",
        )
        principal_row = AnnualExpenseEntry.objects.get(
            user=self.user,
            source_liability_id=liability_id,
            is_system_generated=True,
            fiscal_year=2027,
            event_group=f"liability_{liability_id}_cancellation_principal",
        )

        monthly_installment = Decimal(response.data["estimated_monthly_payment_amount"])
        self.assertEqual(recurrent_2027.term_end_month, 5)
        self.assertEqual(
            recurrent_2027.amount_annual,
            (monthly_installment * Decimal("5")).quantize(Decimal("0.01")),
        )
        self.assertGreater(principal_row.amount_annual, Decimal("0.00"))

    def test_generated_mortgage_recurrent_amount_still_recalculates_when_only_notes_were_edited(
        self,
    ):
        response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Hipoteca notas editadas",
                "category": Liability.Category.MORTGAGE,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "start_date": "2026-01-15",
                "annual_interest_tae": "2.50",
                "amount": "120000.00",
                "principal_amount": "120000.00",
                "term_months": 360,
                "rate_type": "fixed",
                "payment_frequency": "monthly",
                "amortization_system": "french",
                "cancellation_forecast_enabled": True,
                "cancellation_date": "2027-06-15",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        liability_id = response.data["id"]
        recurrent = AnnualExpenseEntry.objects.get(
            user=self.user,
            source_liability_id=liability_id,
            is_system_generated=True,
            fiscal_year=2027,
            event_group=f"liability_{liability_id}",
        )
        recurrent.notes = "Editado por el usuario para dejar contexto."
        recurrent.save(update_fields=["notes"])

        patch_response = self.client.patch(
            f"/api/net-worth/liabilities/{liability_id}/",
            {"cancellation_include_payment_month": False},
            format="json",
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK, patch_response.data)

        recurrent.refresh_from_db()
        monthly_installment = Decimal(patch_response.data["estimated_monthly_payment_amount"])
        self.assertEqual(recurrent.notes, "Editado por el usuario para dejar contexto.")
        self.assertEqual(recurrent.term_end_month, 5)
        self.assertEqual(
            recurrent.amount_annual,
            (monthly_installment * Decimal("5")).quantize(Decimal("0.01")),
        )

    def test_mortgage_with_cancellation_fee_amount_uses_fixed_fee(self):
        response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Hipoteca cancelacion con comision fija",
                "category": Liability.Category.MORTGAGE,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "start_date": "2026-01-15",
                "annual_interest_tae": "2.50",
                "amount": "120000.00",
                "principal_amount": "120000.00",
                "term_months": 360,
                "rate_type": "fixed",
                "payment_frequency": "monthly",
                "amortization_system": "french",
                "early_repayment_fee_percent": "0.50",
                "cancellation_forecast_enabled": True,
                "cancellation_date": "2027-06-15",
                "cancellation_fee_amount": "321.99",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        fee_row = AnnualExpenseEntry.objects.get(
            user=self.user,
            source_liability_id=response.data["id"],
            is_system_generated=True,
            event_group=f"liability_{response.data['id']}_cancellation_fee",
        )
        self.assertEqual(fee_row.amount_annual, Decimal("321.99"))

    def test_liability_generated_expense_owner_name_follows_ownership_link(self):
        response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Hipoteca titularidad",
                "category": Liability.Category.MORTGAGE,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "start_date": "2026-01-15",
                "annual_interest_tae": "2.50",
                "amount": "180000.00",
                "principal_amount": "180000.00",
                "term_months": 360,
                "rate_type": "fixed",
                "payment_frequency": "monthly",
                "amortization_system": "french",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        liability_id = response.data["id"]

        generated_before = AnnualExpenseEntry.objects.filter(
            user=self.user,
            source_liability_id=liability_id,
            is_system_generated=True,
        ).order_by("fiscal_year")
        self.assertTrue(generated_before.exists())
        self.assertEqual(generated_before.first().owner_name, "")

        ana = FamilyMember.objects.create(
            user=self.user,
            name="Ana",
            role=FamilyMember.Role.ADULT,
            is_active=True,
        )
        pablo = FamilyMember.objects.create(
            user=self.user,
            name="Pablo",
            role=FamilyMember.Role.ADULT,
            is_active=True,
        )
        shared = Ownership.objects.create(user=self.user, kind=Ownership.Kind.SHARED, member=None)
        OwnershipSplit.objects.create(ownership=shared, member=ana, percent=Decimal("50.00"))
        OwnershipSplit.objects.create(ownership=shared, member=pablo, percent=Decimal("50.00"))

        sync_response = self.client.post(
            "/api/ownership-links/sync/",
            {
                "target_type": "liability",
                "target_id": liability_id,
                "ownership_id": shared.id,
            },
            format="json",
        )
        self.assertEqual(sync_response.status_code, status.HTTP_200_OK, sync_response.data)

        generated_after = AnnualExpenseEntry.objects.filter(
            user=self.user,
            source_liability_id=liability_id,
            is_system_generated=True,
        )
        self.assertTrue(generated_after.exists())
        for row in generated_after:
            self.assertIn("Compartido", row.owner_name)
            self.assertIn("Ana", row.owner_name)
            self.assertIn("Pablo", row.owner_name)
            self.assertIn("50%", row.owner_name)

    def test_liability_create_quarterly_generates_budget_commitment_entries(self):
        response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Prestamo trimestral",
                "category": Liability.Category.PERSONAL_LOAN,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "start_date": "2026-01-15",
                "annual_interest_tae": "12.00",
                "amount": "1200.00",
                "principal_amount": "1200.00",
                "term_months": 12,
                "rate_type": "fixed",
                "payment_frequency": "quarterly",
                "amortization_system": "french",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        rows = AnnualExpenseEntry.objects.filter(
            user=self.user,
            source_liability_id=response.data["id"],
            is_system_generated=True,
        ).order_by("fiscal_year")
        self.assertEqual(list(rows.values_list("fiscal_year", flat=True)), [2026, 2027])
        self.assertGreater(rows.get(fiscal_year=2026).amount_annual, Decimal("900.00"))

    def test_liability_create_quarterly_rejects_term_not_multiple_of_three(self):
        response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Prestamo trimestral invalido",
                "category": Liability.Category.PERSONAL_LOAN,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "start_date": "2026-01-15",
                "annual_interest_tae": "12.00",
                "amount": "1200.00",
                "principal_amount": "1200.00",
                "term_months": 10,
                "rate_type": "fixed",
                "payment_frequency": "quarterly",
                "amortization_system": "french",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("term_months", response.data["error"]["details"])

    def test_liability_delete_removes_generated_budget_commitments_for_all_years(self):
        create_response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Hipoteca prueba borrado",
                "category": Liability.Category.MORTGAGE,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "start_date": "2024-09-01",
                "annual_interest_tae": "2.50",
                "amount": "180000.00",
                "principal_amount": "180000.00",
                "term_months": 36,
                "rate_type": "fixed",
                "payment_frequency": "monthly",
                "amortization_system": "french",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED, create_response.data)
        liability_id = create_response.data["id"]

        generated_before = AnnualExpenseEntry.objects.filter(
            user=self.user,
            source_liability_id=liability_id,
            is_system_generated=True,
        )
        self.assertTrue(generated_before.exists())
        self.assertGreaterEqual(generated_before.count(), 2)

        delete_response = self.client.delete(f"/api/net-worth/liabilities/{liability_id}/")
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Liability.objects.filter(user=self.user, id=liability_id).exists())
        self.assertFalse(
            AnnualExpenseEntry.objects.filter(
                user=self.user,
                source_liability_id=liability_id,
                is_system_generated=True,
            ).exists()
        )

    def test_liability_delete_removes_generated_budget_commitments_by_event_group_fallback(self):
        create_response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Prestamo fallback event group",
                "category": Liability.Category.PERSONAL_LOAN,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "start_date": "2026-01-15",
                "annual_interest_tae": "2.50",
                "amount": "12000.00",
                "principal_amount": "12000.00",
                "term_months": 24,
                "rate_type": "fixed",
                "payment_frequency": "monthly",
                "amortization_system": "french",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED, create_response.data)
        liability_id = create_response.data["id"]
        event_group = f"liability_{liability_id}"

        generated = AnnualExpenseEntry.objects.filter(
            user=self.user,
            source_liability_id=liability_id,
            is_system_generated=True,
        )
        self.assertTrue(generated.exists())
        generated.update(source_liability=None)

        delete_response = self.client.delete(f"/api/net-worth/liabilities/{liability_id}/")
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            AnnualExpenseEntry.objects.filter(
                user=self.user,
                is_system_generated=True,
                event_group=event_group,
            ).exists()
        )

    def test_liability_update_does_not_overwrite_generated_budget_commitment_if_user_edits_it(self):
        create_response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Compra vivienda ATRIO",
                "category": Liability.Category.OTHER,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "start_date": "2024-09-01",
                "annual_interest_tae": "0.00",
                "amount": "33010.56",
                "principal_amount": "33010.56",
                "term_months": 24,
                "rate_type": "fixed",
                "payment_frequency": "monthly",
                "amortization_system": "french",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED, create_response.data)
        liability_id = create_response.data["id"]

        generated_2026 = AnnualExpenseEntry.objects.get(
            user=self.user,
            source_liability_id=liability_id,
            is_system_generated=True,
            fiscal_year=2026,
        )
        generated_2025 = AnnualExpenseEntry.objects.get(
            user=self.user,
            source_liability_id=liability_id,
            is_system_generated=True,
            fiscal_year=2025,
        )
        generated_2026.name = "Compromiso ATRIO personalizado"
        generated_2026.amount_annual = Decimal("12000.00")
        generated_2026.notes = "Editado manualmente por usuario"
        generated_2026.save(update_fields=["name", "amount_annual", "notes"])

        update_response = self.client.patch(
            f"/api/net-worth/liabilities/{liability_id}/",
            {
                "notes": "Cambio en pasivo",
                "term_months": 36,
            },
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK, update_response.data)

        generated_2025.refresh_from_db()
        generated_2026.refresh_from_db()
        self.assertEqual(generated_2025.amount_annual, Decimal("11003.52"))
        self.assertEqual(generated_2026.name, "Compromiso ATRIO personalizado")
        self.assertEqual(generated_2026.amount_annual, Decimal("12000.00"))
        self.assertEqual(generated_2026.notes, "Editado manualmente por usuario")
        generated_2027 = AnnualExpenseEntry.objects.get(
            user=self.user,
            source_liability_id=liability_id,
            is_system_generated=True,
            fiscal_year=2027,
        )
        self.assertEqual(generated_2027.amount_annual, Decimal("8252.64"))

    def test_liability_update_refreshes_generated_budget_commitments_when_not_edited(self):
        create_response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Prestamo reforma",
                "category": Liability.Category.OTHER,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "start_date": "2024-09-01",
                "annual_interest_tae": "0.00",
                "amount": "33010.56",
                "principal_amount": "33010.56",
                "term_months": 24,
                "rate_type": "fixed",
                "payment_frequency": "monthly",
                "amortization_system": "french",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED, create_response.data)
        liability_id = create_response.data["id"]

        update_response = self.client.patch(
            f"/api/net-worth/liabilities/{liability_id}/",
            {"term_months": 36},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK, update_response.data)

        rows = AnnualExpenseEntry.objects.filter(
            user=self.user,
            source_liability_id=liability_id,
            is_system_generated=True,
        )
        self.assertEqual(
            list(rows.order_by("fiscal_year").values_list("fiscal_year", flat=True)),
            [2024, 2025, 2026, 2027],
        )
        self.assertEqual(rows.get(fiscal_year=2025).amount_annual, Decimal("11003.52"))
        self.assertEqual(rows.get(fiscal_year=2026).amount_annual, Decimal("11003.52"))
        self.assertEqual(rows.get(fiscal_year=2027).amount_annual, Decimal("8252.64"))

    def test_liability_update_deletes_obsolete_generated_budget_commitment_years(self):
        create_response = self.client.post(
            "/api/net-worth/liabilities/",
            {
                "name": "Prestamo temporal",
                "category": Liability.Category.OTHER,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "start_date": "2024-09-01",
                "annual_interest_tae": "0.00",
                "amount": "33010.56",
                "principal_amount": "33010.56",
                "term_months": 36,
                "rate_type": "fixed",
                "payment_frequency": "monthly",
                "amortization_system": "french",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED, create_response.data)
        liability_id = create_response.data["id"]

        rows_before = AnnualExpenseEntry.objects.filter(
            user=self.user,
            source_liability_id=liability_id,
            is_system_generated=True,
        )
        self.assertEqual(
            list(rows_before.order_by("fiscal_year").values_list("fiscal_year", flat=True)),
            [2024, 2025, 2026, 2027],
        )

        update_response = self.client.patch(
            f"/api/net-worth/liabilities/{liability_id}/",
            {"term_months": 12},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK, update_response.data)

        rows_after = AnnualExpenseEntry.objects.filter(
            user=self.user,
            source_liability_id=liability_id,
            is_system_generated=True,
        )
        self.assertEqual(
            list(rows_after.order_by("fiscal_year").values_list("fiscal_year", flat=True)),
            [2024, 2025],
        )

    def test_summary_returns_200_without_real_values_when_inflation_is_missing(self):
        response = self.client.get("/api/net-worth/summary/")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["inflation_region"], "ES")
        self.assertIsNone(response.data["inflation_base_period"])
        self.assertFalse(response.data["inflation_available"])
        self.assertEqual(response.data["inflation_status"], "missing")
        self.assertIsNone(response.data["net_worth_real"])

    def test_summary_returns_200_with_inflation_index(self):
        InflationIndex.objects.create(
            region="ES", period=date(2026, 1, 1), index=Decimal("100.0000")
        )
        Asset.objects.create(
            user=self.user,
            name="Cuenta",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("100.00"),
            is_active=True,
        )
        response = self.client.get("/api/net-worth/summary/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["base_currency"], "EUR")
        self.assertIn("total_assets", response.data)

    def test_summary_returns_200_without_inflation_when_base_currency_not_eur(self):
        settings, _created = UserSettings.objects.get_or_create(user=self.user)
        settings.base_currency = "USD"
        settings.save(update_fields=["base_currency"])
        self.user.refresh_from_db()
        Asset.objects.create(
            user=self.user,
            name="Cuenta",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="USD",
            amount=Decimal("100.00"),
            is_active=True,
        )
        response = self.client.get("/api/net-worth/summary/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["inflation_region"])

    def test_liquidity_checkin_create_rejects_non_cash_asset(self):
        asset = Asset.objects.create(
            user=self.user,
            name="ETF World",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.ETFS,
            currency="EUR",
            amount=Decimal("1000.00"),
            is_active=True,
        )
        response = self.client.post(
            "/api/net-worth/liquidity-checkins/",
            {
                "asset_id": asset.id,
                "fiscal_year": 2026,
                "month": 2,
                "status": "confirmed",
                "closing_balance_real": "1000.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("asset_id", response.data["error"]["details"])

    def test_liquidity_checkin_create_and_monthly_summary(self):
        bank = Asset.objects.create(
            user=self.user,
            name="Cuenta nomina",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("1500.00"),
            annual_interest_tae=Decimal("0.50"),
            is_active=True,
        )
        Asset.objects.create(
            user=self.user,
            name="ETF World",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.ETFS,
            currency="EUR",
            amount=Decimal("2000.00"),
            is_active=True,
        )
        create_res = self.client.post(
            "/api/net-worth/liquidity-checkins/",
            {
                "asset_id": bank.id,
                "fiscal_year": 2026,
                "month": 2,
                "status": "adjusted",
                "closing_balance_real": "1420.50",
                "note": "Saldo real fin de mes",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)
        self.assertEqual(create_res.data["asset_ref"], bank.id)
        self.assertEqual(create_res.data["status"], "adjusted")
        self.assertEqual(create_res.data["closing_balance_real"], "1420.50000000")

        summary_res = self.client.get("/api/net-worth/liquidity/monthly-summary/?year=2026&month=2")
        self.assertEqual(summary_res.status_code, status.HTTP_200_OK, summary_res.data)
        self.assertEqual(summary_res.data["checkins_expected"], 1)
        self.assertEqual(summary_res.data["checkins_confirmed"], 1)
        self.assertEqual(summary_res.data["planned_total"], "1500.00")
        self.assertEqual(summary_res.data["executed_total"], "1420.50")
        self.assertEqual(summary_res.data["deviation_total"], "-79.50")
        self.assertEqual(len(summary_res.data["rows"]), 1)
        row = summary_res.data["rows"][0]
        self.assertEqual(row["asset_id"], bank.id)
        self.assertEqual(row["planned_closing_balance"], "1500.00")
        self.assertEqual(row["executed_closing_balance"], "1420.50")
        self.assertEqual(row["deviation"], "-79.50")
        self.assertEqual(row["annual_interest_tae"], "0.50")
        self.assertEqual(row["coverage_source"], "checkin")
        self.assertEqual(row["checkin"]["status"], "adjusted")

    def test_liquidity_monthly_summary_subtracts_credit_card_liabilities_from_net_total(self):
        bank = Asset.objects.create(
            user=self.user,
            name="Cuenta nomina",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("1000.00"),
            annual_interest_tae=Decimal("0.00"),
            is_active=True,
        )
        credit_card = Liability.objects.create(
            user=self.user,
            name="Tarjeta Visa",
            category=Liability.Category.CREDIT_CARD,
            currency="EUR",
            amount=Decimal("200.00"),
            annual_interest_tae=Decimal("0.00"),
            is_active=True,
        )
        LiquidityMonthlyCheckin.objects.create(
            user=self.user,
            asset=bank,
            fiscal_year=2026,
            month=2,
            status=LiquidityMonthlyCheckin.Status.CONFIRMED,
            closing_balance_real=Decimal("950.00"),
        )

        response = self.client.get("/api/net-worth/liquidity/monthly-summary/?year=2026&month=2")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["gross_asset_executed_total"], "950.00")
        self.assertEqual(response.data["liquid_liability_executed_total"], "200.00")
        self.assertEqual(response.data["executed_total"], "750.00")
        rows = {row["asset_name"]: row for row in response.data["rows"]}
        self.assertEqual(rows["Cuenta nomina"]["row_type"], "asset")
        self.assertEqual(rows["Tarjeta Visa"]["row_type"], "liability")
        self.assertEqual(rows["Tarjeta Visa"]["liability_id"], credit_card.id)
        self.assertEqual(rows["Tarjeta Visa"]["executed_closing_balance"], "200.00")
        self.assertEqual(rows["Tarjeta Visa"]["executed_closing_balance_base"], "-200.00")

    def test_liquidity_monthly_summary_includes_interest_bearing_investments_in_perimeter(self):
        investment = Asset.objects.create(
            user=self.user,
            name="Urbanitae",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.REAL_ESTATE_CROWD,
            currency="EUR",
            amount=Decimal("2000.00"),
            annual_interest_tae=Decimal("8.00"),
            is_active=True,
        )
        non_interest_investment = Asset.objects.create(
            user=self.user,
            name="ETF World",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.ETFS,
            currency="EUR",
            amount=Decimal("3000.00"),
            annual_interest_tae=Decimal("0.00"),
            is_active=True,
        )
        expense_account = LedgerAccount.objects.create(
            user=self.user,
            name="Inversiones",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )
        transaction = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 10),
            value_date=date(2026, 2, 10),
            description="Aportacion Urbanitae",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=expense_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("100.00"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.EXPENSE,
            category_key="financial_investments",
            subcategory_key="crowdfunding_real_estate",
            asset=investment,
        )

        response = self.client.get("/api/net-worth/liquidity/monthly-summary/?year=2026&month=2")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        rows = {row["asset_name"]: row for row in response.data["rows"]}
        self.assertIn("Urbanitae", rows)
        self.assertNotIn("ETF World", rows)
        self.assertEqual(rows["Urbanitae"]["asset_id"], investment.id)
        self.assertEqual(rows["Urbanitae"]["annual_interest_tae"], "8.00")
        self.assertEqual(response.data["perimeter_internal_expense_total"], "100.00")
        self.assertNotIn(
            non_interest_investment.id,
            [row["asset_id"] for row in response.data["rows"]],
        )

    def test_liquidity_monthly_summary_uses_credit_card_manual_checkpoint(self):
        bank = Asset.objects.create(
            user=self.user,
            name="Cuenta nomina",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("1000.00"),
            annual_interest_tae=Decimal("0.00"),
            is_active=True,
        )
        credit_card = Liability.objects.create(
            user=self.user,
            name="Tarjeta Visa",
            category=Liability.Category.CREDIT_CARD,
            currency="EUR",
            amount=Decimal("200.00"),
            annual_interest_tae=Decimal("0.00"),
            is_active=True,
        )
        valuation = LiabilityValuation.objects.create(
            user=self.user,
            liability=credit_card,
            valuation_date=date(2026, 2, 28),
            value=Decimal("125.40"),
            source=LiabilityValuation.Source.MANUAL_CHECKPOINT,
            note="Ajuste cierre",
        )
        LiquidityMonthlyCheckin.objects.create(
            user=self.user,
            asset=bank,
            fiscal_year=2026,
            month=2,
            status=LiquidityMonthlyCheckin.Status.CONFIRMED,
            closing_balance_real=Decimal("1000.00"),
        )

        response = self.client.get("/api/net-worth/liquidity/monthly-summary/?year=2026&month=2")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        rows = {row["asset_name"]: row for row in response.data["rows"]}
        self.assertEqual(rows["Tarjeta Visa"]["coverage_source"], "checkin")
        self.assertEqual(rows["Tarjeta Visa"]["executed_closing_balance"], "125.40")
        self.assertEqual(rows["Tarjeta Visa"]["executed_closing_balance_base"], "-125.40")
        self.assertEqual(rows["Tarjeta Visa"]["checkin"]["id"], valuation.id)
        self.assertEqual(rows["Tarjeta Visa"]["checkin"]["closing_balance_real"], "125.40")
        self.assertEqual(response.data["executed_total"], "874.60")

    def test_liquidity_monthly_summary_uses_ledger_for_accounting_assets_and_keeps_fallback(self):
        ledger_account = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta operativa",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        income_account = LedgerAccount.objects.create(
            user=self.user,
            name="Ingresos",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )
        Asset.objects.create(
            user=self.user,
            name="Cuenta ledger",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            accounting_account_id=ledger_account.id,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("1000.00"),
            is_active=True,
        )
        fallback_asset = Asset.objects.create(
            user=self.user,
            name="Cuenta fallback",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("800.00"),
            annual_interest_tae=Decimal("0.00"),
            is_active=True,
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 27),
            value_date=date(2026, 2, 27),
            description="Cobro fin de mes",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=ledger_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("950.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("950.00"),
            currency="EUR",
        )
        LiquidityMonthlyCheckin.objects.create(
            user=self.user,
            asset=fallback_asset,
            fiscal_year=2026,
            month=2,
            status=LiquidityMonthlyCheckin.Status.CONFIRMED,
            closing_balance_real=Decimal("780.00"),
        )

        response = self.client.get("/api/net-worth/liquidity/monthly-summary/?year=2026&month=2")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["checkins_confirmed"], 1)
        self.assertEqual(response.data["coverage_confirmed"], 2)
        self.assertEqual(response.data["ledger_rows_confirmed"], 1)
        self.assertEqual(response.data["fallback_rows_confirmed"], 1)
        self.assertTrue(response.data["has_ledger_data"])
        rows = {row["asset_name"]: row for row in response.data["rows"]}
        self.assertEqual(rows["Cuenta ledger"]["executed_closing_balance"], "950.00")
        self.assertEqual(rows["Cuenta ledger"]["coverage_source"], "ledger")
        self.assertTrue(rows["Cuenta ledger"]["ledger_available"])
        self.assertEqual(rows["Cuenta fallback"]["executed_closing_balance"], "780.00")
        self.assertEqual(rows["Cuenta fallback"]["coverage_source"], "checkin")
        self.assertFalse(rows["Cuenta fallback"]["ledger_available"])

    def test_liquidity_monthly_summary_allows_manual_override_on_ledger_covered_asset(self):
        ledger_account = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta operativa override",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        income_account = LedgerAccount.objects.create(
            user=self.user,
            name="Ingresos override",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )
        ledger_asset = Asset.objects.create(
            user=self.user,
            name="Cuenta ledger override",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            accounting_account_id=ledger_account.id,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("1000.00"),
            is_active=True,
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 27),
            value_date=date(2026, 2, 27),
            description="Cobro fin de mes override",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=ledger_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("950.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("950.00"),
            currency="EUR",
        )
        LiquidityMonthlyCheckin.objects.create(
            user=self.user,
            asset=ledger_asset,
            fiscal_year=2026,
            month=2,
            status=LiquidityMonthlyCheckin.Status.ADJUSTED,
            closing_balance_real=Decimal("910.00"),
        )

        response = self.client.get("/api/net-worth/liquidity/monthly-summary/?year=2026&month=2")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        rows = {row["asset_name"]: row for row in response.data["rows"]}
        self.assertEqual(rows["Cuenta ledger override"]["coverage_source"], "checkin")
        self.assertTrue(rows["Cuenta ledger override"]["ledger_available"])
        self.assertEqual(rows["Cuenta ledger override"]["executed_closing_balance"], "910.00")
        self.assertEqual(response.data["ledger_rows_confirmed"], 0)
        self.assertEqual(response.data["fallback_rows_confirmed"], 1)
        self.assertTrue(response.data["has_ledger_data"])

    def test_liquidity_monthly_summary_exposes_ledger_available_for_linked_checkin_asset(self):
        ledger_account = LedgerAccount.objects.create(
            user=self.user,
            name="Deposito MyInvestor 3 meses",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        ledger_asset = Asset.objects.create(
            user=self.user,
            name="Deposito MyInvestor 3 meses",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.SHORT_TERM_DEPOSIT,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            accounting_account_id=ledger_account.id,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("0.00"),
            is_active=True,
        )
        LiquidityMonthlyCheckin.objects.create(
            user=self.user,
            asset=ledger_asset,
            fiscal_year=2026,
            month=2,
            status=LiquidityMonthlyCheckin.Status.CONFIRMED,
            closing_balance_real=Decimal("0.00"),
        )

        response = self.client.get("/api/net-worth/liquidity/monthly-summary/?year=2026&month=2")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        row = response.data["rows"][0]
        self.assertEqual(row["coverage_source"], "checkin")
        self.assertTrue(row["ledger_available"])
        self.assertEqual(row["executed_closing_balance"], "0.00")
        self.assertTrue(response.data["has_ledger_data"])

    def test_liquidity_monthly_summary_uses_effective_balance_for_linked_asset_without_checkin(
        self,
    ):
        ledger_account = LedgerAccount.objects.create(
            user=self.user,
            name="Deposito MyInvestor sin checkin",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        Asset.objects.create(
            user=self.user,
            name="Deposito MyInvestor sin checkin",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.SHORT_TERM_DEPOSIT,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            accounting_account_id=ledger_account.id,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("10000.00"),
            is_active=True,
        )

        response = self.client.get("/api/net-worth/liquidity/monthly-summary/?year=2026&month=2")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        row = response.data["rows"][0]
        self.assertEqual(row["coverage_source"], "ledger")
        self.assertTrue(row["ledger_available"])
        self.assertEqual(row["executed_closing_balance"], "10000.00")
        self.assertEqual(response.data["ledger_rows_confirmed"], 1)

    def test_liquidity_checkin_update_does_not_trigger_liability_sync_and_updates_row(self):
        bank = Asset.objects.create(
            user=self.user,
            name="Cuenta nomina",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("1500.00"),
            annual_interest_tae=Decimal("0.00"),
            is_active=True,
        )
        create_res = self.client.post(
            "/api/net-worth/liquidity-checkins/",
            {
                "asset_id": bank.id,
                "fiscal_year": 2026,
                "month": 2,
                "status": "confirmed",
                "closing_balance_real": "1500.00",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)
        checkin_id = create_res.data["id"]

        patch_res = self.client.patch(
            f"/api/net-worth/liquidity-checkins/{checkin_id}/",
            {
                "status": "adjusted",
                "closing_balance_real": "1420.50",
                "note": "Ajuste por saldo real",
            },
            format="json",
        )
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK, patch_res.data)
        self.assertEqual(patch_res.data["status"], "adjusted")
        self.assertEqual(patch_res.data["closing_balance_real"], "1420.50000000")
        self.assertEqual(patch_res.data["note"], "Ajuste por saldo real")
        self.assertIsNotNone(patch_res.data["confirmed_at"])

        checkin = LiquidityMonthlyCheckin.objects.get(id=checkin_id, user=self.user)
        self.assertEqual(checkin.status, LiquidityMonthlyCheckin.Status.ADJUSTED)
        self.assertEqual(checkin.closing_balance_real, Decimal("1420.50000000"))
        self.assertEqual(checkin.note, "Ajuste por saldo real")
        self.assertIsNotNone(checkin.confirmed_at)

    def test_liquidity_checkin_duplicate_post_updates_existing_row(self):
        bank = Asset.objects.create(
            user=self.user,
            name="Cuenta duplicada",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("1500.00"),
            annual_interest_tae=Decimal("0.00"),
            is_active=True,
        )
        first_res = self.client.post(
            "/api/net-worth/liquidity-checkins/",
            {
                "asset_id": bank.id,
                "fiscal_year": 2026,
                "month": 1,
                "status": "confirmed",
                "closing_balance_real": "1500.00",
            },
            format="json",
        )
        self.assertEqual(first_res.status_code, status.HTTP_201_CREATED, first_res.data)

        second_res = self.client.post(
            "/api/net-worth/liquidity-checkins/",
            {
                "asset_id": bank.id,
                "fiscal_year": 2026,
                "month": 1,
                "status": "adjusted",
                "closing_balance_real": "10000.00",
            },
            format="json",
        )
        self.assertEqual(second_res.status_code, status.HTTP_200_OK, second_res.data)
        self.assertEqual(second_res.data["id"], first_res.data["id"])
        self.assertEqual(second_res.data["status"], "adjusted")
        self.assertEqual(second_res.data["closing_balance_real"], "10000.00000000")
        self.assertEqual(
            LiquidityMonthlyCheckin.objects.filter(
                user=self.user, asset=bank, fiscal_year=2026, month=1
            ).count(),
            1,
        )

    def test_liquidity_checkin_belongs_to_user_and_can_be_deleted(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Cuenta ahorro",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("500.00"),
            annual_interest_tae=Decimal("0.00"),
            is_active=True,
        )
        checkin = LiquidityMonthlyCheckin.objects.create(
            user=self.user,
            asset=asset,
            fiscal_year=2026,
            month=3,
            status=LiquidityMonthlyCheckin.Status.CONFIRMED,
            closing_balance_real=Decimal("500.00"),
            confirmed_at=timezone.make_aware(datetime(2026, 3, 31)),
        )
        delete_res = self.client.delete(f"/api/net-worth/liquidity-checkins/{checkin.id}/")
        self.assertEqual(delete_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            LiquidityMonthlyCheckin.objects.filter(id=checkin.id, user=self.user).exists()
        )

    def test_liquidity_monthly_summary_rejects_invalid_month(self):
        response = self.client.get("/api/net-worth/liquidity/monthly-summary/?year=2026&month=13")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(response.data["error"]["code"], "validation_error")

    def test_liquidity_monthly_summary_rejects_non_integer_params_with_canonical_error_shape(self):
        response = self.client.get("/api/net-worth/liquidity/monthly-summary/?year=x&month=y")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(response.data["error"]["code"], "validation_error")
        self.assertEqual(
            response.data["error"]["details"]["detail"],
            "year y month deben ser enteros.",
        )

    def test_assets_and_liabilities_lists_are_user_scoped(self):
        other_user = get_user_model().objects.create_user(username="nw_other", password="pass1234")

        Asset.objects.create(
            user=other_user,
            name="Cuenta ajena",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("1.00"),
            is_active=True,
        )
        Liability.objects.create(
            user=other_user,
            name="Prestamo ajeno",
            category=Liability.Category.OTHER,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("1.00"),
            is_active=True,
        )

        own_asset = Asset.objects.create(
            user=self.user,
            name="Cuenta propia",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("100.00"),
            is_active=True,
        )
        own_liability = Liability.objects.create(
            user=self.user,
            name="Prestamo propio",
            category=Liability.Category.OTHER,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("10.00"),
            is_active=True,
        )

        assets_res = self.client.get("/api/net-worth/assets/")
        self.assertEqual(assets_res.status_code, status.HTTP_200_OK, assets_res.data)
        self.assertEqual([row["id"] for row in assets_res.data], [own_asset.id])

        liabilities_res = self.client.get("/api/net-worth/liabilities/")
        self.assertEqual(liabilities_res.status_code, status.HTTP_200_OK, liabilities_res.data)
        self.assertEqual([row["id"] for row in liabilities_res.data], [own_liability.id])

    def test_asset_valuation_create_and_asset_timeline_endpoint(self):
        asset = Asset.objects.create(
            user=self.user,
            name="ETF World",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.ETFS,
            currency="EUR",
            amount=Decimal("1000.00"),
            start_date=date(2026, 1, 15),
            is_active=True,
        )

        create_res = self.client.post(
            "/api/net-worth/asset-valuations/",
            {
                "asset_id": asset.id,
                "valuation_date": "2026-02-28",
                "value": "1150.00",
                "source": "manual_checkpoint",
                "note": "Cierre mensual",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)
        self.assertEqual(create_res.data["asset_ref"], asset.id)

        timeline_res = self.client.get(
            f"/api/net-worth/assets/{asset.id}/timeline/?end_date=2026-03-31"
        )
        self.assertEqual(timeline_res.status_code, status.HTTP_200_OK, timeline_res.data)
        self.assertEqual(timeline_res.data["rows"][-1]["value"], "1150.00")

    def test_investment_event_create_and_asset_timeline_endpoint(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Fondo global",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=Decimal("1000.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )

        create_res = self.client.post(
            "/api/net-worth/investment-events/",
            {
                "asset_id": asset.id,
                "event_date": "2026-02-15",
                "event_type": "contribution",
                "amount": "200.00",
                "note": "Aportacion extra",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)
        self.assertEqual(create_res.data["asset_ref"], asset.id)

        timeline_res = self.client.get(
            f"/api/net-worth/assets/{asset.id}/timeline/?end_date=2026-02-28"
        )
        self.assertEqual(timeline_res.status_code, status.HTTP_200_OK, timeline_res.data)
        self.assertEqual(timeline_res.data["rows"][-1]["value"], "1200.00")

    def test_investment_event_create_rejects_non_investment_asset(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Cuenta",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("500.00"),
            annual_interest_tae=Decimal("0.00"),
            is_active=True,
        )

        response = self.client.post(
            "/api/net-worth/investment-events/",
            {
                "asset_id": asset.id,
                "event_date": "2026-02-15",
                "event_type": "contribution",
                "amount": "200.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("asset_id", response.data["error"]["details"])

    def test_liquidity_event_create_and_asset_timeline_endpoint(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Cuenta corriente",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("1000.00"),
            annual_interest_tae=Decimal("0.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )

        create_res = self.client.post(
            "/api/net-worth/liquidity-events/",
            {
                "asset_id": asset.id,
                "event_date": "2026-02-15",
                "event_type": "outflow",
                "amount": "120.00",
                "note": "Recibo",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)
        self.assertEqual(create_res.data["asset_ref"], asset.id)

        timeline_res = self.client.get(
            f"/api/net-worth/assets/{asset.id}/timeline/?end_date=2026-02-28"
        )
        self.assertEqual(timeline_res.status_code, status.HTTP_200_OK, timeline_res.data)
        self.assertEqual(timeline_res.data["rows"][-1]["value"], "880.00")

    def test_liquidity_event_create_rejects_non_cash_asset(self):
        asset = Asset.objects.create(
            user=self.user,
            name="ETF",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.ETFS,
            currency="EUR",
            amount=Decimal("500.00"),
            is_active=True,
        )

        response = self.client.post(
            "/api/net-worth/liquidity-events/",
            {
                "asset_id": asset.id,
                "event_date": "2026-02-15",
                "event_type": "inflow",
                "amount": "200.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("asset_id", response.data["error"]["details"])

    def test_liability_event_create_and_liability_timeline_endpoint(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Visa",
            category=Liability.Category.CREDIT_CARD,
            currency="EUR",
            annual_interest_tae=Decimal("18.00"),
            amount=Decimal("500.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )

        create_res = self.client.post(
            "/api/net-worth/liability-events/",
            {
                "liability_id": liability.id,
                "event_date": "2026-02-15",
                "event_type": "charge",
                "amount": "120.00",
                "note": "Compra",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)
        self.assertEqual(create_res.data["liability_ref"], liability.id)

        timeline_res = self.client.get(
            f"/api/net-worth/liabilities/{liability.id}/timeline/?end_date=2026-02-28"
        )
        self.assertEqual(timeline_res.status_code, status.HTTP_200_OK, timeline_res.data)
        self.assertEqual(timeline_res.data["rows"][-1]["value"], "620.00")

    def test_liability_valuation_create_and_liability_timeline_endpoint(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo",
            category=Liability.Category.OTHER,
            currency="EUR",
            amount=Decimal("500.00"),
            start_date=date(2026, 1, 10),
            is_active=True,
        )

        create_res = self.client.post(
            "/api/net-worth/liability-valuations/",
            {
                "liability_id": liability.id,
                "valuation_date": "2026-02-28",
                "value": "420.00",
                "source": "manual_checkpoint",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)
        self.assertEqual(create_res.data["liability_ref"], liability.id)

        timeline_res = self.client.get(
            f"/api/net-worth/liabilities/{liability.id}/timeline/?end_date=2026-03-31"
        )
        self.assertEqual(timeline_res.status_code, status.HTTP_200_OK, timeline_res.data)
        self.assertEqual(timeline_res.data["rows"][-1]["value"], "420.00")

    def test_net_worth_timeline_endpoint_filters_asset_category(self):
        Asset.objects.create(
            user=self.user,
            name="Cuenta",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("500.00"),
            annual_interest_tae=Decimal("0.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )
        Asset.objects.create(
            user=self.user,
            name="ETF",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.ETFS,
            currency="EUR",
            amount=Decimal("1000.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )

        response = self.client.get(
            "/api/net-worth/timeline/?start_date=2026-01-01&end_date=2026-02-28&asset_category=investments"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(len(response.data["rows"]), 2)
        self.assertEqual(response.data["rows"][0]["total_assets"], "1000.00")
