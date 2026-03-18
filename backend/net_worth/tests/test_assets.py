from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.exceptions import ValidationError as DRFValidationError

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from core.models import InflationIndex
from ..models import (
    Asset,
    AssetImprovement,
    AssetValuation,
    InvestmentAssetEvent,
    Liability,
    LiabilityEvent,
    LiabilityValuation,
    LiquidityAssetEvent,
    LiquidityMonthlyCheckin,
)
from ..services import (
    NetWorthTotals,
    calculate_totals,
    get_base_currency_for_user,
    get_financed_asset_queryset_for_user,
    get_inflation_base_period,
    get_inflation_region_for_user,
)
from ..services_assets_core import (
    AccountingIntegrationState as AssetAccountingIntegrationState,
    create_asset_for_user,
    ensure_asset_accounting_account,
    get_amount_base_value,
    get_effective_asset_amount,
    get_investment_asset_events_delta,
    get_liquidity_asset_events_delta,
    validate_asset_payload,
)
from ..services_liabilities_core import (
    AccountingIntegrationState as LiabilityAccountingIntegrationState,
    create_liability_for_user,
    ensure_liability_accounting_account,
    estimate_liability_monthly_payment_simple,
    estimate_liability_outstanding_amount_simple,
    get_effective_liability_amount,
    get_liability_events_delta,
    infer_liability_is_asset_backed,
    validate_liability_payload,
)
from ..services_snapshots import (
    create_or_update_snapshot_from_current,
    create_snapshot_for_user,
    validate_snapshot_payload,
)
from ..services_summaries import (
    build_net_worth_summary,
    serialize_net_worth_summary,
)
from ..services_timelines import (
    build_asset_timeline,
    build_liability_timeline,
    build_net_worth_timeline,
)


class NetWorthServicesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="nw_user", password="pass1234")

    def test_validate_asset_payload_accepts_accounting_without_account(self):
        validate_asset_payload(
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            accounting_account_id=None,
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            annual_interest_tae=Decimal("1.00"),
            amortization_method=Asset.AmortizationMethod.NONE,
            amortization_term_years=None,
            initial_purchase_value=None,
        )

    def test_validate_asset_payload_rejects_invalid_subcategory(self):
        with self.assertRaises(DRFValidationError):
            validate_asset_payload(
                tracking_mode=Asset.TrackingMode.MANUAL,
                accounting_account_id=None,
                category=Asset.Category.CASH,
                subcategory=Asset.Subcategory.ETFS,
                annual_interest_tae=None,
                amortization_method=Asset.AmortizationMethod.NONE,
                amortization_term_years=None,
                initial_purchase_value=None,
            )

    def test_validate_liability_payload_accepts_accounting_without_account(self):
        validate_liability_payload(
            tracking_mode=Liability.TrackingMode.ACCOUNTING,
            accounting_account_id=None,
            category=Liability.Category.MORTGAGE,
            annual_interest_tae=Decimal("2.50"),
            start_date=date(2026, 1, 1),
            expected_end_date=date(2030, 1, 1),
        )

    def test_validate_asset_and_liability_payload_accept_valid_values(self):
        validate_asset_payload(
            tracking_mode=Asset.TrackingMode.MANUAL,
            accounting_account_id=None,
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            annual_interest_tae=Decimal("0.00"),
            amortization_method=Asset.AmortizationMethod.NONE,
            amortization_term_years=None,
            initial_purchase_value=None,
        )
        validate_asset_payload(
            tracking_mode=Asset.TrackingMode.MANUAL,
            accounting_account_id=None,
            category=None,
            subcategory=None,
            annual_interest_tae=None,
            amortization_method=Asset.AmortizationMethod.NONE,
            amortization_term_years=None,
            initial_purchase_value=None,
        )
        validate_liability_payload(
            tracking_mode=Liability.TrackingMode.MANUAL,
            accounting_account_id=None,
            category=Liability.Category.OTHER,
            annual_interest_tae=None,
            start_date=date(2026, 1, 1),
            expected_end_date=None,
        )

    def test_validate_asset_payload_accepts_owned_accounting_account(self):
        account = LedgerAccount.objects.create(
            user=self.user,
            name="Banco contable",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )

        validate_asset_payload(
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            accounting_account_id=account.id,
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            annual_interest_tae=Decimal("0.00"),
            amortization_method=Asset.AmortizationMethod.NONE,
            amortization_term_years=None,
            initial_purchase_value=None,
            user_id=self.user.id,
            currency="EUR",
        )

    def test_validate_liability_payload_rejects_foreign_accounting_account(self):
        other_user = get_user_model().objects.create_user(
            username="nw_other",
            password="pass1234",
        )
        account = LedgerAccount.objects.create(
            user=other_user,
            name="Pasivo ajeno",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
        )

        with self.assertRaises(DRFValidationError):
            validate_liability_payload(
                tracking_mode=Liability.TrackingMode.ACCOUNTING,
                accounting_account_id=account.id,
                category=Liability.Category.MORTGAGE,
                annual_interest_tae=Decimal("2.50"),
                start_date=date(2026, 1, 1),
                expected_end_date=date(2030, 1, 1),
                user_id=self.user.id,
                currency="EUR",
            )

    def test_ensure_asset_accounting_account_auto_creates_and_links_missing_account(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Cuenta puente",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            accounting_account_id=None,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("100.00"),
            is_active=True,
        )

        state = ensure_asset_accounting_account(asset=asset)

        self.assertEqual(state, AssetAccountingIntegrationState.AUTO_CREATED)
        asset.refresh_from_db()
        self.assertIsNotNone(asset.accounting_account_id)
        self.assertTrue(
            LedgerAccount.objects.filter(
                id=asset.accounting_account_id,
                user=self.user,
                account_type=LedgerAccount.AccountType.ASSET,
                currency="EUR",
                asset_id=asset.id,
            ).exists()
        )

    def test_ensure_asset_accounting_account_marks_needs_review_for_invalid_candidate(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Cuenta con enlace roto",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            accounting_account_id=999_999,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("100.00"),
            is_active=True,
        )

        state = ensure_asset_accounting_account(asset=asset)

        self.assertEqual(state, AssetAccountingIntegrationState.NEEDS_REVIEW)

    def test_ensure_liability_accounting_account_auto_creates_and_links_missing_account(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Hipoteca auto",
            category=Liability.Category.MORTGAGE,
            tracking_mode=Liability.TrackingMode.ACCOUNTING,
            accounting_account_id=None,
            currency="EUR",
            start_date=date(2026, 1, 1),
            annual_interest_tae=Decimal("2.50"),
            amount=Decimal("100000.00"),
            is_active=True,
        )

        state = ensure_liability_accounting_account(liability=liability)

        self.assertEqual(state, LiabilityAccountingIntegrationState.AUTO_CREATED)
        liability.refresh_from_db()
        self.assertIsNotNone(liability.accounting_account_id)
        self.assertTrue(
            LedgerAccount.objects.filter(
                id=liability.accounting_account_id,
                user=self.user,
                account_type=LedgerAccount.AccountType.LIABILITY,
                currency="EUR",
                liability_id=liability.id,
            ).exists()
        )

    def test_ensure_liability_accounting_account_marks_needs_review_for_invalid_candidate(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Hipoteca enlace roto",
            category=Liability.Category.MORTGAGE,
            tracking_mode=Liability.TrackingMode.ACCOUNTING,
            accounting_account_id=999_998,
            currency="EUR",
            start_date=date(2026, 1, 1),
            annual_interest_tae=Decimal("2.50"),
            amount=Decimal("100000.00"),
            is_active=True,
        )

        state = ensure_liability_accounting_account(liability=liability)

        self.assertEqual(state, LiabilityAccountingIntegrationState.NEEDS_REVIEW)

    def test_validate_liability_payload_requires_tae_for_financial_debt(self):
        with self.assertRaises(DRFValidationError):
            validate_liability_payload(
                tracking_mode=Liability.TrackingMode.MANUAL,
                accounting_account_id=None,
                category=Liability.Category.CREDIT_CARD,
                annual_interest_tae=None,
                start_date=date(2026, 1, 1),
                expected_end_date=None,
            )

    def test_validate_asset_payload_requires_tae_for_remunerated_liquidity(self):
        with self.assertRaises(DRFValidationError):
            validate_asset_payload(
                tracking_mode=Asset.TrackingMode.MANUAL,
                accounting_account_id=None,
                category=Asset.Category.CASH,
                subcategory=Asset.Subcategory.BANK_ACCOUNT,
                annual_interest_tae=None,
                amortization_method=Asset.AmortizationMethod.NONE,
                amortization_term_years=None,
                initial_purchase_value=None,
            )

    def test_validate_asset_payload_requires_deposit_term_for_short_term_deposit(self):
        with self.assertRaises(DRFValidationError):
            validate_asset_payload(
                tracking_mode=Asset.TrackingMode.MANUAL,
                accounting_account_id=None,
                category=Asset.Category.CASH,
                subcategory=Asset.Subcategory.SHORT_TERM_DEPOSIT,
                annual_interest_tae=Decimal("2.50"),
                amortization_method=Asset.AmortizationMethod.NONE,
                amortization_term_years=None,
                initial_purchase_value=None,
                deposit_term_months=None,
            )

    def test_validate_asset_payload_rejects_invalid_deposit_term_range(self):
        with self.assertRaises(DRFValidationError):
            validate_asset_payload(
                tracking_mode=Asset.TrackingMode.MANUAL,
                accounting_account_id=None,
                category=Asset.Category.CASH,
                subcategory=Asset.Subcategory.SHORT_TERM_DEPOSIT,
                annual_interest_tae=Decimal("2.50"),
                amortization_method=Asset.AmortizationMethod.NONE,
                amortization_term_years=None,
                initial_purchase_value=None,
                deposit_term_months=13,
            )

    def test_validate_asset_payload_requires_initial_value_and_term_for_amortization(self):
        with self.assertRaises(DRFValidationError):
            validate_asset_payload(
                tracking_mode=Asset.TrackingMode.MANUAL,
                accounting_account_id=None,
                category=Asset.Category.FURNISHINGS,
                subcategory=Asset.Subcategory.TECHNOLOGY,
                annual_interest_tae=None,
                amortization_method=Asset.AmortizationMethod.STRAIGHT_LINE,
                amortization_term_years=None,
                initial_purchase_value=None,
            )

    def test_validate_asset_payload_accepts_amount_as_fallback_purchase_value_for_amortization(
        self,
    ):
        validate_asset_payload(
            tracking_mode=Asset.TrackingMode.MANUAL,
            accounting_account_id=None,
            category=Asset.Category.FURNISHINGS,
            subcategory=Asset.Subcategory.TECHNOLOGY,
            annual_interest_tae=None,
            amortization_method=Asset.AmortizationMethod.STRAIGHT_LINE,
            amortization_term_years=4,
            initial_purchase_value=None,
            amount=Decimal("1800.00"),
        )

    def test_validate_asset_payload_allows_missing_term_for_vehicle_profile(self):
        validate_asset_payload(
            tracking_mode=Asset.TrackingMode.MANUAL,
            accounting_account_id=None,
            category=Asset.Category.FURNISHINGS,
            subcategory=Asset.Subcategory.VEHICLES,
            annual_interest_tae=None,
            amortization_method=Asset.AmortizationMethod.STRAIGHT_LINE,
            amortization_term_years=None,
            initial_purchase_value=Decimal("15000.00"),
        )

    def test_validate_asset_payload_allows_manual_without_term(self):
        validate_asset_payload(
            tracking_mode=Asset.TrackingMode.MANUAL,
            accounting_account_id=None,
            category=Asset.Category.FURNISHINGS,
            subcategory=Asset.Subcategory.HOME_FURNISHINGS,
            annual_interest_tae=None,
            amortization_method=Asset.AmortizationMethod.MANUAL,
            amortization_term_years=None,
            initial_purchase_value=None,
            amount=Decimal("5000.00"),
        )

    def test_validate_asset_payload_requires_home_parameters_for_auto_valuation(self):
        with self.assertRaises(DRFValidationError):
            validate_asset_payload(
                tracking_mode=Asset.TrackingMode.MANUAL,
                accounting_account_id=None,
                category=Asset.Category.REAL_ESTATE,
                subcategory=Asset.Subcategory.PRIMARY_HOME,
                annual_interest_tae=None,
                amortization_method=Asset.AmortizationMethod.NONE,
                amortization_term_years=None,
                initial_purchase_value=Decimal("100000.00"),
                valuation_model=Asset.ValuationModel.REAL_ESTATE_AUTO,
            )

    def test_validate_liability_payload_rejects_end_date_before_start_date(self):
        with self.assertRaises(DRFValidationError):
            validate_liability_payload(
                tracking_mode=Liability.TrackingMode.MANUAL,
                accounting_account_id=None,
                category=Liability.Category.MORTGAGE,
                annual_interest_tae=Decimal("2.50"),
                start_date=date(2026, 2, 1),
                expected_end_date=date(2026, 1, 1),
            )

    def test_validate_liability_payload_rejects_quarterly_term_not_multiple_of_three(self):
        with self.assertRaises(DRFValidationError):
            validate_liability_payload(
                tracking_mode=Liability.TrackingMode.MANUAL,
                accounting_account_id=None,
                category=Liability.Category.PERSONAL_LOAN,
                annual_interest_tae=Decimal("5.00"),
                start_date=date(2026, 1, 1),
                expected_end_date=None,
                payment_frequency=Liability.PaymentFrequency.QUARTERLY,
                term_months=10,
            )

    def test_validate_liability_payload_requires_cancellation_date_when_forecast_enabled(self):
        with self.assertRaises(DRFValidationError):
            validate_liability_payload(
                tracking_mode=Liability.TrackingMode.MANUAL,
                accounting_account_id=None,
                category=Liability.Category.MORTGAGE,
                annual_interest_tae=Decimal("2.50"),
                start_date=date(2026, 2, 1),
                expected_end_date=None,
                cancellation_forecast_enabled=True,
                cancellation_date=None,
            )

    def test_validate_liability_payload_rejects_cancellation_forecast_for_non_mortgage(self):
        with self.assertRaises(DRFValidationError):
            validate_liability_payload(
                tracking_mode=Liability.TrackingMode.MANUAL,
                accounting_account_id=None,
                category=Liability.Category.PERSONAL_LOAN,
                annual_interest_tae=Decimal("5.00"),
                start_date=date(2026, 2, 1),
                expected_end_date=None,
                cancellation_forecast_enabled=True,
                cancellation_date=date(2027, 1, 1),
            )

    def test_infer_liability_is_asset_backed(self):
        self.assertTrue(infer_liability_is_asset_backed(financed_asset=object()))
        self.assertFalse(infer_liability_is_asset_backed(financed_asset=None))

    def test_estimate_liability_monthly_payment_simple_fixed_french(self):
        value = estimate_liability_monthly_payment_simple(
            amount=Decimal("120000"),
            annual_interest_tae=Decimal("3.60"),
            term_months=240,
            payment_frequency=Liability.PaymentFrequency.MONTHLY,
            rate_type=Liability.RateType.FIXED,
            amortization_system=Liability.AmortizationSystem.FRENCH,
        )
        self.assertIsNotNone(value)
        assert value is not None
        self.assertGreater(value, Decimal("500"))
        self.assertLess(value, Decimal("900"))

    def test_estimate_liability_monthly_payment_simple_returns_none_for_non_monthly(self):
        value = estimate_liability_monthly_payment_simple(
            amount=Decimal("10000"),
            annual_interest_tae=Decimal("5.00"),
            term_months=24,
            payment_frequency=Liability.PaymentFrequency.YEARLY,
            rate_type=Liability.RateType.FIXED,
            amortization_system=Liability.AmortizationSystem.FRENCH,
        )
        self.assertIsNone(value)

    def test_estimate_liability_outstanding_amount_simple_uses_next_month_first_due(self):
        liability = Liability(
            user=self.user,
            name="ATRIO",
            category=Liability.Category.OTHER,
            currency="EUR",
            start_date=date(2024, 9, 1),
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("24000.00"),
            principal_amount=Decimal("24000.00"),
            term_months=24,
            rate_type=Liability.RateType.FIXED,
            payment_frequency=Liability.PaymentFrequency.MONTHLY,
            amortization_system=Liability.AmortizationSystem.FRENCH,
            is_active=True,
        )
        outstanding = estimate_liability_outstanding_amount_simple(
            liability=liability, as_of_date=date(2026, 2, 24)
        )
        # 24 cuotas, primera en oct-2024; a 24-feb-2026 se consideran pagadas hasta feb-2026 (17 cuotas)
        # quedan 7 cuotas -> 7000 con principal 24000 a 0%.
        self.assertEqual(outstanding, Decimal("7000.00000000"))

    def test_validate_snapshot_payload_computes_or_validates_net_worth(self):
        computed = validate_snapshot_payload(
            total_assets=Decimal("100.00"),
            total_liabilities=Decimal("30.00"),
            net_worth=None,
        )
        self.assertEqual(computed, Decimal("70.00"))

        valid = validate_snapshot_payload(
            total_assets=Decimal("100.00"),
            total_liabilities=Decimal("30.00"),
            net_worth=Decimal("70.00"),
        )
        self.assertEqual(valid, Decimal("70.00"))

        with self.assertRaises(ValidationError):
            validate_snapshot_payload(
                total_assets=Decimal("100.00"),
                total_liabilities=Decimal("30.00"),
                net_worth=Decimal("80.00"),
            )

    def test_validate_snapshot_payload_returns_net_worth_when_totals_missing(self):
        value = validate_snapshot_payload(
            total_assets=None,
            total_liabilities=Decimal("30.00"),
            net_worth=Decimal("10.00"),
        )
        self.assertEqual(value, Decimal("10.00"))

    @patch("net_worth.services_assets_core.convert_currency", return_value=Decimal("90.50"))
    def test_get_amount_base_value_success(self, _convert_mock):
        value = get_amount_base_value(
            amount=Decimal("100.00"),
            currency="USD",
            base_currency="EUR",
            as_of_date=date(2026, 2, 18),
        )
        self.assertEqual(value, "90.50")

    @patch("net_worth.services_assets_core.convert_currency", side_effect=Exception("fx error"))
    def test_get_amount_base_value_returns_none_on_conversion_error(self, _convert_mock):
        value = get_amount_base_value(
            amount=Decimal("100.00"),
            currency="USD",
            base_currency="EUR",
            as_of_date=date(2026, 2, 18),
        )
        self.assertIsNone(value)

    def test_get_amount_base_value_returns_none_without_base_currency(self):
        value = get_amount_base_value(
            amount=Decimal("100.00"),
            currency="USD",
            base_currency=None,
            as_of_date=date(2026, 2, 18),
        )
        self.assertIsNone(value)

    def test_serialize_net_worth_summary_serializes_decimals_and_dates(self):
        payload = serialize_net_worth_summary(
            {
                "base_currency": "EUR",
                "total_assets": Decimal("100.00"),
                "total_liabilities": Decimal("30.00"),
                "net_worth": Decimal("70.00"),
                "assets_by_category": {"cash": Decimal("50.00")},
                "assets_by_subcategory": {"cash:bank_account": Decimal("50.00")},
                "liabilities_by_category": {"mortgage": Decimal("30.00")},
                "inflation_region": "ES",
                "inflation_base_period": date(2026, 1, 1),
                "inflation_available": True,
                "inflation_status": "available",
                "total_assets_real": Decimal("101.00"),
                "total_liabilities_real": Decimal("29.00"),
                "net_worth_real": Decimal("72.00"),
                "assets_by_category_real": {"cash": Decimal("51.00")},
                "liabilities_by_category_real": {"mortgage": Decimal("29.00")},
                "liabilities_asset_backed": Decimal("30.00"),
                "liabilities_unbacked": Decimal("0.00"),
                "liabilities_asset_backed_real": Decimal("29.00"),
                "liabilities_unbacked_real": Decimal("0.00"),
            }
        )

        self.assertEqual(payload["total_assets"], "100.00")
        self.assertEqual(payload["inflation_base_period"], "2026-01-01")
        self.assertEqual(payload["assets_by_category"]["cash"], "50.00")

    def test_create_asset_liability_snapshot_and_financed_queryset(self):
        asset = create_asset_for_user(
            user=self.user,
            validated_data={
                "name": "Cuenta",
                "category": Asset.Category.CASH,
                "subcategory": Asset.Subcategory.BANK_ACCOUNT,
                "currency": "EUR",
                "amount": Decimal("100.00"),
                "is_active": True,
            },
        )
        liability = create_liability_for_user(
            user=self.user,
            validated_data={
                "name": "Hipoteca",
                "category": Liability.Category.MORTGAGE,
                "currency": "EUR",
                "amount": Decimal("50.00"),
                "is_active": True,
                "financed_asset": asset,
            },
        )
        snapshot = create_snapshot_for_user(
            user=self.user,
            validated_data={
                "snapshot_date": date(2026, 2, 18),
                "base_currency": "EUR",
                "total_assets": Decimal("100.00"),
                "total_liabilities": Decimal("50.00"),
                "net_worth": Decimal("50.00"),
            },
        )
        financed_qs = get_financed_asset_queryset_for_user(user=self.user)

        self.assertEqual(liability.financed_asset_id, asset.id)
        self.assertEqual(snapshot.net_worth, Decimal("50.00"))
        self.assertEqual(financed_qs.count(), 1)

    def test_calculate_totals_groups_assets_and_liabilities(self):
        asset_a = Asset.objects.create(
            user=self.user,
            name="Cuenta",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("100.00"),
            is_active=True,
        )
        Asset.objects.create(
            user=self.user,
            name="ETF",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.ETFS,
            currency="EUR",
            amount=Decimal("200.00"),
            is_active=True,
        )
        Liability.objects.create(
            user=self.user,
            name="Hipoteca",
            category=Liability.Category.MORTGAGE,
            currency="EUR",
            annual_interest_tae=Decimal("2.10"),
            amount=Decimal("50.00"),
            financed_asset=asset_a,
            is_active=True,
        )
        Liability.objects.create(
            user=self.user,
            name="Tarjeta",
            category=Liability.Category.CREDIT_CARD,
            currency="EUR",
            annual_interest_tae=Decimal("22.50"),
            amount=Decimal("20.00"),
            financed_asset=None,
            is_active=True,
        )

        totals = calculate_totals(
            assets_qs=Asset.objects.filter(user=self.user, is_active=True),
            liabilities_qs=Liability.objects.filter(user=self.user, is_active=True),
            base_currency="EUR",
            as_of_date=date(2026, 2, 18),
        )

        self.assertEqual(totals.total_assets, Decimal("300.00"))
        self.assertEqual(totals.total_liabilities, Decimal("70.00"))
        self.assertEqual(totals.liabilities_asset_backed, Decimal("50.00"))
        self.assertEqual(totals.liabilities_unbacked, Decimal("20.00"))
        self.assertIn("cash:bank_account", totals.assets_by_subcategory)

    def test_calculate_totals_uses_effective_liability_amount_when_schedule_available(self):
        Liability.objects.create(
            user=self.user,
            name="Compromiso ATRIO",
            category=Liability.Category.OTHER,
            currency="EUR",
            start_date=date(2024, 9, 1),
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("24000.00"),
            principal_amount=Decimal("24000.00"),
            term_months=24,
            rate_type=Liability.RateType.FIXED,
            payment_frequency=Liability.PaymentFrequency.MONTHLY,
            amortization_system=Liability.AmortizationSystem.FRENCH,
            is_active=True,
        )
        totals = calculate_totals(
            assets_qs=Asset.objects.filter(user=self.user, is_active=True),
            liabilities_qs=Liability.objects.filter(user=self.user, is_active=True),
            base_currency="EUR",
            as_of_date=date(2026, 2, 24),
        )
        self.assertEqual(totals.total_liabilities, Decimal("7000.00000000"))

    def test_get_effective_asset_amount_for_primary_home_auto_valuation(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Vivienda",
            category=Asset.Category.REAL_ESTATE,
            subcategory=Asset.Subcategory.PRIMARY_HOME,
            currency="EUR",
            start_date=date(2025, 1, 1),
            initial_purchase_value=Decimal("100.00"),
            valuation_model=Asset.ValuationModel.REAL_ESTATE_AUTO,
            land_value_share_percent=Decimal("30.00"),
            land_annual_appreciation_percent=Decimal("24.000"),
            building_annual_depreciation_percent=Decimal("0.00"),
            amount=Decimal("100.00"),
            is_active=True,
        )
        effective = get_effective_asset_amount(asset=asset, as_of_date=date(2026, 1, 1))
        self.assertEqual(effective.quantize(Decimal("0.0001")), Decimal("108.0473"))

    def test_get_effective_asset_amount_applies_straight_line_amortization(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Cama",
            category=Asset.Category.FURNISHINGS,
            subcategory=Asset.Subcategory.HOME_FURNISHINGS,
            currency="EUR",
            start_date=date(2016, 2, 1),
            initial_purchase_value=Decimal("10000.00"),
            amortization_method=Asset.AmortizationMethod.STRAIGHT_LINE,
            amortization_term_years=10,
            amount=Decimal("10000.00"),
            is_active=True,
        )
        effective = get_effective_asset_amount(asset=asset, as_of_date=date(2026, 2, 1))
        self.assertEqual(effective.quantize(Decimal("0.0001")), Decimal("0.0000"))

    def test_get_effective_asset_amount_uses_linked_ledger_balance_for_accounting_tracking(self):
        account = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta contable",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        income = LedgerAccount.objects.create(
            user=self.user,
            name="Ingresos",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )
        asset = Asset.objects.create(
            user=self.user,
            name="Banco",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            accounting_account_id=account.id,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("5.00"),
            is_active=True,
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 10),
            value_date=date(2026, 2, 10),
            description="Nomina",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1250.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=income,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1250.00"),
            currency="EUR",
        )

        self.assertEqual(get_effective_asset_amount(asset=asset), Decimal("1250.00"))

    def test_get_effective_asset_amount_respects_as_of_date_for_accounting_tracking(self):
        account = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta contable",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        income = LedgerAccount.objects.create(
            user=self.user,
            name="Ingresos",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )
        asset = Asset.objects.create(
            user=self.user,
            name="Banco",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            accounting_account_id=account.id,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("5.00"),
            is_active=True,
        )
        for booking_date, amount in (
            (date(2026, 2, 10), Decimal("1250.00")),
            (date(2026, 3, 3), Decimal("300.00")),
        ):
            tx = LedgerTransaction.objects.create(
                user=self.user,
                booking_date=booking_date,
                value_date=booking_date,
                description=f"Movimiento {booking_date.isoformat()}",
            )
            LedgerEntry.objects.create(
                transaction=tx,
                account=account,
                side=LedgerEntry.Side.DEBIT,
                amount=amount,
                currency="EUR",
            )
            LedgerEntry.objects.create(
                transaction=tx,
                account=income,
                side=LedgerEntry.Side.CREDIT,
                amount=amount,
                currency="EUR",
            )

        self.assertEqual(
            get_effective_asset_amount(asset=asset, as_of_date=date(2026, 2, 28)),
            Decimal("1250.00"),
        )

    def test_get_effective_asset_amount_applies_ipc_growth_for_furnishings(self):
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
        asset = Asset.objects.create(
            user=self.user,
            name="Sofa",
            category=Asset.Category.FURNISHINGS,
            subcategory=Asset.Subcategory.HOME_FURNISHINGS,
            currency="EUR",
            start_date=date(2016, 2, 1),
            initial_purchase_value=Decimal("10000.00"),
            amortization_method=Asset.AmortizationMethod.STRAIGHT_LINE,
            amortization_term_years=20,
            amount=Decimal("10000.00"),
            is_active=True,
        )
        effective = get_effective_asset_amount(asset=asset, as_of_date=date(2026, 2, 1))
        self.assertEqual(effective.quantize(Decimal("0.01")), Decimal("6000.00"))

    def test_get_effective_asset_amount_applies_residual_floor_for_vehicles_and_sports(self):
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
        vehicle = Asset.objects.create(
            user=self.user,
            name="Coche",
            category=Asset.Category.FURNISHINGS,
            subcategory=Asset.Subcategory.VEHICLES,
            currency="EUR",
            start_date=date(2016, 2, 1),
            initial_purchase_value=Decimal("10000.00"),
            amortization_method=Asset.AmortizationMethod.STRAIGHT_LINE,
            amortization_term_years=40,
            amount=Decimal("10000.00"),
            is_active=True,
        )
        bike = Asset.objects.create(
            user=self.user,
            name="Bici carretera",
            category=Asset.Category.FURNISHINGS,
            subcategory=Asset.Subcategory.SPORTS_EQUIPMENT,
            currency="EUR",
            start_date=date(2016, 2, 1),
            initial_purchase_value=Decimal("10000.00"),
            amortization_method=Asset.AmortizationMethod.STRAIGHT_LINE,
            amortization_term_years=40,
            amount=Decimal("10000.00"),
            is_active=True,
        )

        vehicle_effective = get_effective_asset_amount(asset=vehicle, as_of_date=date(2056, 2, 1))
        bike_effective = get_effective_asset_amount(asset=bike, as_of_date=date(2056, 2, 1))

        self.assertEqual(vehicle_effective.quantize(Decimal("0.01")), Decimal("1800.00"))
        self.assertEqual(bike_effective.quantize(Decimal("0.01")), Decimal("2400.00"))

    def test_get_effective_asset_amount_uses_amount_as_purchase_base_for_furnishings(self):
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
        asset = Asset.objects.create(
            user=self.user,
            name="Sofa legacy",
            category=Asset.Category.FURNISHINGS,
            subcategory=Asset.Subcategory.HOME_FURNISHINGS,
            currency="EUR",
            start_date=date(2016, 2, 1),
            initial_purchase_value=Decimal("20000.00"),
            amortization_method=Asset.AmortizationMethod.STRAIGHT_LINE,
            amortization_term_years=20,
            amount=Decimal("10000.00"),
            is_active=True,
        )
        effective = get_effective_asset_amount(asset=asset, as_of_date=date(2026, 2, 1))
        self.assertEqual(effective.quantize(Decimal("0.01")), Decimal("6000.00"))

    def test_get_effective_asset_amount_for_auto_home_valuation_includes_improvements(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Vivienda",
            category=Asset.Category.REAL_ESTATE,
            subcategory=Asset.Subcategory.PRIMARY_HOME,
            currency="EUR",
            start_date=date(2025, 1, 1),
            initial_purchase_value=Decimal("100.00"),
            valuation_model=Asset.ValuationModel.REAL_ESTATE_AUTO,
            land_value_share_percent=Decimal("30.00"),
            land_annual_appreciation_percent=Decimal("24.000"),
            building_annual_depreciation_percent=Decimal("0.00"),
            amount=Decimal("100.00"),
            is_active=True,
        )
        AssetImprovement.objects.create(
            asset=asset,
            name="Reforma cocina",
            reform_date=date(2025, 1, 1),
            amount=Decimal("12.00"),
            amortization_method=AssetImprovement.AmortizationMethod.STRAIGHT_LINE,
            amortization_term_years=3,
        )
        AssetImprovement.objects.create(
            asset=asset,
            name="Aislamiento termico",
            reform_date=date(2025, 7, 1),
            amount=Decimal("6.00"),
            amortization_method=AssetImprovement.AmortizationMethod.NONE,
            annual_interest_tae=Decimal("12.00"),
            capitalize_interest=True,
        )
        effective = get_effective_asset_amount(asset=asset, as_of_date=date(2026, 1, 1))
        self.assertEqual(effective.quantize(Decimal("0.0001")), Decimal("122.4164"))

    def test_get_effective_asset_amount_accumulates_periodic_investment_contributions(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Reserva Atrio",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.OTHER,
            currency="EUR",
            start_date=date(2025, 3, 5),
            expected_end_date=date(2027, 3, 5),
            investment_contribution_mode=Asset.InvestmentContributionMode.PERIODIC_CONTRIBUTION,
            monthly_contribution_amount=Decimal("1374.00"),
            amount=Decimal("8800.00"),
            initial_purchase_value=Decimal("8800.00"),
            is_active=True,
        )
        effective = get_effective_asset_amount(asset=asset, as_of_date=date(2026, 3, 5))
        # 13 cuotas (de 2025-03 a 2026-03 inclusive) + importe inicial.
        self.assertEqual(effective.quantize(Decimal("0.01")), Decimal("26662.00"))

    def test_get_effective_asset_amount_accumulates_weekly_periodic_contributions(self):
        asset = Asset.objects.create(
            user=self.user,
            name="ETF semanal",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.ETFS,
            currency="EUR",
            start_date=date(2026, 1, 1),
            investment_contribution_mode=Asset.InvestmentContributionMode.PERIODIC_CONTRIBUTION,
            investment_contribution_frequency=Asset.InvestmentContributionFrequency.WEEKLY,
            monthly_contribution_amount=Decimal("100.00"),
            amount=Decimal("1000.00"),
            initial_purchase_value=Decimal("1000.00"),
            is_active=True,
        )
        effective = get_effective_asset_amount(asset=asset, as_of_date=date(2026, 1, 29))
        # Cuotas semanales en: 01, 08, 15, 22 y 29 de enero.
        self.assertEqual(effective.quantize(Decimal("0.01")), Decimal("1500.00"))

    def test_get_effective_asset_amount_does_not_accumulate_when_contribution_currency_differs(
        self,
    ):
        asset = Asset.objects.create(
            user=self.user,
            name="BTC con cuota USD",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.CRYPTOCURRENCIES,
            currency="BTC",
            start_date=date(2026, 1, 1),
            investment_contribution_mode=Asset.InvestmentContributionMode.PERIODIC_CONTRIBUTION,
            investment_contribution_frequency=Asset.InvestmentContributionFrequency.WEEKLY,
            investment_contribution_currency="USD",
            monthly_contribution_amount=Decimal("25.00"),
            amount=Decimal("0.03725777"),
            initial_purchase_value=Decimal("0.03725777"),
            is_active=True,
        )
        effective = get_effective_asset_amount(asset=asset, as_of_date=date(2026, 3, 1))
        self.assertEqual(effective, Decimal("0.03725777"))

    def test_get_effective_asset_amount_uses_latest_asset_valuation_checkpoint(self):
        asset = Asset.objects.create(
            user=self.user,
            name="ETF World",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.ETFS,
            currency="EUR",
            amount=Decimal("1000.00"),
            is_active=True,
        )
        AssetValuation.objects.create(
            user=self.user,
            asset=asset,
            valuation_date=date(2026, 2, 28),
            value=Decimal("1125.00"),
        )

        self.assertEqual(
            get_effective_asset_amount(asset=asset, as_of_date=date(2026, 3, 31)),
            Decimal("1125.00"),
        )

    def test_get_effective_asset_amount_investment_applies_events_after_manual_checkpoint(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Fondo indexado",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=Decimal("1000.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )
        AssetValuation.objects.create(
            user=self.user,
            asset=asset,
            valuation_date=date(2026, 2, 28),
            value=Decimal("1200.00"),
        )
        InvestmentAssetEvent.objects.create(
            user=self.user,
            asset=asset,
            event_date=date(2026, 3, 10),
            event_type=InvestmentAssetEvent.EventType.CONTRIBUTION,
            amount=Decimal("100.00"),
        )
        InvestmentAssetEvent.objects.create(
            user=self.user,
            asset=asset,
            event_date=date(2026, 3, 20),
            event_type=InvestmentAssetEvent.EventType.FEE,
            amount=Decimal("10.00"),
        )

        self.assertEqual(
            get_effective_asset_amount(asset=asset, as_of_date=date(2026, 3, 31)),
            Decimal("1290.00"),
        )

    def test_get_investment_asset_events_delta_skips_non_reinvested_passive_income(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Dividendos",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.STOCKS,
            currency="EUR",
            amount=Decimal("1000.00"),
            is_active=True,
        )
        InvestmentAssetEvent.objects.create(
            user=self.user,
            asset=asset,
            event_date=date(2026, 2, 1),
            event_type=InvestmentAssetEvent.EventType.PASSIVE_INCOME,
            amount=Decimal("20.00"),
            is_reinvested=False,
        )
        InvestmentAssetEvent.objects.create(
            user=self.user,
            asset=asset,
            event_date=date(2026, 2, 2),
            event_type=InvestmentAssetEvent.EventType.PASSIVE_INCOME,
            amount=Decimal("15.00"),
            is_reinvested=True,
        )

        self.assertEqual(
            get_investment_asset_events_delta(asset=asset, as_of_date=date(2026, 2, 28)),
            Decimal("15.00"),
        )

    def test_get_effective_asset_amount_uses_liquidity_checkin_as_monthly_checkpoint(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Cuenta nomina",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("1500.00"),
            annual_interest_tae=Decimal("0.00"),
            is_active=True,
        )
        LiquidityMonthlyCheckin.objects.create(
            user=self.user,
            asset=asset,
            fiscal_year=2026,
            month=2,
            status=LiquidityMonthlyCheckin.Status.CONFIRMED,
            closing_balance_real=Decimal("1420.00"),
        )

        self.assertEqual(
            get_effective_asset_amount(asset=asset, as_of_date=date(2026, 3, 31)),
            Decimal("1420.00"),
        )

    def test_get_effective_asset_amount_cash_applies_liquidity_events_after_checkin(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Cuenta operativa",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("1000.00"),
            annual_interest_tae=Decimal("0.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )
        LiquidityMonthlyCheckin.objects.create(
            user=self.user,
            asset=asset,
            fiscal_year=2026,
            month=2,
            status=LiquidityMonthlyCheckin.Status.CONFIRMED,
            closing_balance_real=Decimal("1200.00"),
        )
        LiquidityAssetEvent.objects.create(
            user=self.user,
            asset=asset,
            event_date=date(2026, 3, 10),
            event_type=LiquidityAssetEvent.EventType.OUTFLOW,
            amount=Decimal("50.00"),
        )
        LiquidityAssetEvent.objects.create(
            user=self.user,
            asset=asset,
            event_date=date(2026, 3, 20),
            event_type=LiquidityAssetEvent.EventType.INTEREST,
            amount=Decimal("2.00"),
        )

        self.assertEqual(
            get_effective_asset_amount(asset=asset, as_of_date=date(2026, 3, 31)),
            Decimal("1152.00"),
        )

    def test_get_liquidity_asset_events_delta_applies_signs(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Cuenta ahorro",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("500.00"),
            annual_interest_tae=Decimal("0.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )
        LiquidityAssetEvent.objects.create(
            user=self.user,
            asset=asset,
            event_date=date(2026, 2, 1),
            event_type=LiquidityAssetEvent.EventType.INFLOW,
            amount=Decimal("100.00"),
        )
        LiquidityAssetEvent.objects.create(
            user=self.user,
            asset=asset,
            event_date=date(2026, 2, 2),
            event_type=LiquidityAssetEvent.EventType.FEE,
            amount=Decimal("5.00"),
        )

        self.assertEqual(
            get_liquidity_asset_events_delta(asset=asset, as_of_date=date(2026, 2, 28)),
            Decimal("95.00"),
        )

    def test_get_effective_liability_amount_uses_latest_liability_valuation_checkpoint(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo",
            category=Liability.Category.PERSONAL_LOAN,
            currency="EUR",
            annual_interest_tae=Decimal("5.00"),
            amount=Decimal("9000.00"),
            principal_amount=Decimal("10000.00"),
            term_months=24,
            rate_type=Liability.RateType.FIXED,
            payment_frequency=Liability.PaymentFrequency.MONTHLY,
            amortization_system=Liability.AmortizationSystem.FRENCH,
            is_active=True,
        )
        LiabilityValuation.objects.create(
            user=self.user,
            liability=liability,
            valuation_date=date(2026, 2, 28),
            value=Decimal("8765.00"),
        )

        self.assertEqual(
            get_effective_liability_amount(liability=liability, as_of_date=date(2026, 3, 31)),
            Decimal("8765.00"),
        )

    def test_get_effective_liability_amount_credit_card_applies_events(self):
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
        LiabilityEvent.objects.create(
            user=self.user,
            liability=liability,
            event_date=date(2026, 2, 1),
            event_type=LiabilityEvent.EventType.CHARGE,
            amount=Decimal("100.00"),
        )
        LiabilityEvent.objects.create(
            user=self.user,
            liability=liability,
            event_date=date(2026, 2, 10),
            event_type=LiabilityEvent.EventType.PAYMENT,
            amount=Decimal("40.00"),
        )
        LiabilityEvent.objects.create(
            user=self.user,
            liability=liability,
            event_date=date(2026, 2, 28),
            event_type=LiabilityEvent.EventType.INTEREST,
            amount=Decimal("5.00"),
        )

        self.assertEqual(
            get_effective_liability_amount(liability=liability, as_of_date=date(2026, 2, 28)),
            Decimal("565.00"),
        )

    def test_get_effective_liability_amount_uses_linked_ledger_balance_for_accounting_tracking(
        self,
    ):
        account = LedgerAccount.objects.create(
            user=self.user,
            name="Hipoteca contable",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
        )
        asset_account = LedgerAccount.objects.create(
            user=self.user,
            name="Banco",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        liability = Liability.objects.create(
            user=self.user,
            name="Hipoteca",
            category=Liability.Category.MORTGAGE,
            tracking_mode=Liability.TrackingMode.ACCOUNTING,
            accounting_account_id=account.id,
            currency="EUR",
            start_date=date(2026, 1, 1),
            annual_interest_tae=Decimal("2.00"),
            amount=Decimal("50.00"),
            is_active=True,
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 10),
            value_date=date(2026, 2, 10),
            description="Disposicion deuda",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=asset_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("80000.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("80000.00"),
            currency="EUR",
        )

        self.assertEqual(get_effective_liability_amount(liability=liability), Decimal("80000.00"))

    def test_get_effective_liability_amount_respects_as_of_date_for_accounting_tracking(self):
        account = LedgerAccount.objects.create(
            user=self.user,
            name="Hipoteca contable",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
        )
        asset_account = LedgerAccount.objects.create(
            user=self.user,
            name="Banco",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        liability = Liability.objects.create(
            user=self.user,
            name="Hipoteca",
            category=Liability.Category.MORTGAGE,
            tracking_mode=Liability.TrackingMode.ACCOUNTING,
            accounting_account_id=account.id,
            currency="EUR",
            start_date=date(2026, 1, 1),
            annual_interest_tae=Decimal("2.00"),
            amount=Decimal("50.00"),
            is_active=True,
        )
        for booking_date, amount in (
            (date(2026, 2, 10), Decimal("80000.00")),
            (date(2026, 3, 10), Decimal("500.00")),
        ):
            tx = LedgerTransaction.objects.create(
                user=self.user,
                booking_date=booking_date,
                value_date=booking_date,
                description=f"Movimiento {booking_date.isoformat()}",
            )
            LedgerEntry.objects.create(
                transaction=tx,
                account=asset_account,
                side=LedgerEntry.Side.DEBIT,
                amount=amount,
                currency="EUR",
            )
            LedgerEntry.objects.create(
                transaction=tx,
                account=account,
                side=LedgerEntry.Side.CREDIT,
                amount=amount,
                currency="EUR",
            )

        self.assertEqual(
            get_effective_liability_amount(liability=liability, as_of_date=date(2026, 2, 28)),
            Decimal("80000.00"),
        )

    def test_get_liability_events_delta_applies_signs(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Mastercard",
            category=Liability.Category.CREDIT_CARD,
            currency="EUR",
            annual_interest_tae=Decimal("18.00"),
            amount=Decimal("300.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )
        LiabilityEvent.objects.create(
            user=self.user,
            liability=liability,
            event_date=date(2026, 2, 1),
            event_type=LiabilityEvent.EventType.CHARGE,
            amount=Decimal("80.00"),
        )
        LiabilityEvent.objects.create(
            user=self.user,
            liability=liability,
            event_date=date(2026, 2, 2),
            event_type=LiabilityEvent.EventType.PAYMENT,
            amount=Decimal("25.00"),
        )

        self.assertEqual(
            get_liability_events_delta(liability=liability, as_of_date=date(2026, 2, 28)),
            Decimal("55.00"),
        )

    def test_build_asset_and_liability_timeline_return_monthly_rows(self):
        asset = Asset.objects.create(
            user=self.user,
            name="ETF World",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.ETFS,
            currency="EUR",
            amount=Decimal("1000.00"),
            start_date=date(2026, 1, 10),
            is_active=True,
        )
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo",
            category=Liability.Category.OTHER,
            currency="EUR",
            amount=Decimal("400.00"),
            start_date=date(2026, 1, 5),
            is_active=True,
        )
        AssetValuation.objects.create(
            user=self.user,
            asset=asset,
            valuation_date=date(2026, 2, 28),
            value=Decimal("1100.00"),
        )
        LiabilityValuation.objects.create(
            user=self.user,
            liability=liability,
            valuation_date=date(2026, 2, 28),
            value=Decimal("350.00"),
        )

        asset_timeline = build_asset_timeline(asset=asset, end_date=date(2026, 3, 31))
        liability_timeline = build_liability_timeline(
            liability=liability, end_date=date(2026, 3, 31)
        )

        self.assertEqual(
            [row["date"] for row in asset_timeline["rows"]],
            ["2026-01-31", "2026-02-28", "2026-03-31"],
        )
        self.assertEqual(asset_timeline["rows"][-1]["value"], "1100.00")
        self.assertEqual(liability_timeline["rows"][-1]["value"], "350.00")

    def test_build_net_worth_timeline_filters_by_category(self):
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

        timeline = build_net_worth_timeline(
            user=self.user,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 28),
            asset_category=Asset.Category.INVESTMENTS,
        )

        self.assertEqual(len(timeline["rows"]), 2)
        self.assertEqual(timeline["rows"][0]["total_assets"], "1000.00")

    def test_calculate_totals_uses_effective_asset_amount_for_auto_home_valuation(self):
        Asset.objects.create(
            user=self.user,
            name="Vivienda",
            category=Asset.Category.REAL_ESTATE,
            subcategory=Asset.Subcategory.PRIMARY_HOME,
            currency="EUR",
            start_date=date(2025, 1, 1),
            initial_purchase_value=Decimal("100.00"),
            valuation_model=Asset.ValuationModel.REAL_ESTATE_AUTO,
            land_value_share_percent=Decimal("30.00"),
            land_annual_appreciation_percent=Decimal("24.000"),
            building_annual_depreciation_percent=Decimal("0.00"),
            amount=Decimal("100.00"),
            is_active=True,
        )
        totals = calculate_totals(
            assets_qs=Asset.objects.filter(user=self.user, is_active=True),
            liabilities_qs=Liability.objects.filter(user=self.user, is_active=True),
            base_currency="EUR",
            as_of_date=date(2026, 1, 1),
        )
        self.assertEqual(totals.total_assets.quantize(Decimal("0.01")), Decimal("108.05"))

    def test_get_base_currency_and_inflation_base_period(self):
        base = get_base_currency_for_user(user=self.user)
        self.assertEqual(base, "EUR")
        self.assertEqual(get_inflation_region_for_user(user=self.user), "ES")

        with self.assertRaises(ValidationError):
            get_inflation_base_period(region="ES")

        InflationIndex.objects.create(
            region="ES",
            period=date(2026, 1, 1),
            index=Decimal("100.0000"),
        )
        self.assertEqual(get_inflation_base_period(region="ES"), date(2026, 1, 1))

    @patch("net_worth.services.timezone.localdate", return_value=date(2026, 2, 18))
    @patch(
        "net_worth.services.calculate_totals",
        return_value=NetWorthTotals(
            total_assets=Decimal("100.00"),
            total_liabilities=Decimal("40.00"),
            liabilities_asset_backed=Decimal("40.00"),
            liabilities_unbacked=Decimal("0.00"),
            assets_by_category={"cash": Decimal("100.00")},
            assets_by_subcategory={"cash:bank_account": Decimal("100.00")},
            liabilities_by_category={"mortgage": Decimal("40.00")},
        ),
    )
    @patch("net_worth.services.get_base_currency_for_user", return_value="EUR")
    def test_create_or_update_snapshot_from_current_upserts_snapshot(
        self, _base_mock, _totals_mock, _date_mock
    ):
        snapshot, created = create_or_update_snapshot_from_current(user=self.user)
        self.assertTrue(created)
        self.assertEqual(snapshot.net_worth, Decimal("60.00"))

        snapshot_2, created_2 = create_or_update_snapshot_from_current(user=self.user)
        self.assertFalse(created_2)
        self.assertEqual(snapshot_2.id, snapshot.id)

    @patch("net_worth.services.timezone.localdate", return_value=date(2026, 2, 18))
    @patch(
        "net_worth.services.calculate_totals",
        return_value=NetWorthTotals(
            total_assets=Decimal("300.00"),
            total_liabilities=Decimal("120.00"),
            liabilities_asset_backed=Decimal("80.00"),
            liabilities_unbacked=Decimal("40.00"),
            assets_by_category={"cash": Decimal("300.00")},
            assets_by_subcategory={"cash:bank_account": Decimal("300.00")},
            liabilities_by_category={"mortgage": Decimal("120.00")},
        ),
    )
    @patch("net_worth.services.get_base_currency_for_user", return_value="EUR")
    @patch("net_worth.services.get_inflation_region_for_user", return_value="ES-MD")
    @patch("net_worth.services.get_inflation_base_period", return_value=date(2026, 1, 1))
    @patch("net_worth.services.adjust_for_inflation", side_effect=lambda amount, **_: amount)
    def test_build_net_worth_summary_with_inflation(
        self, _adj_mock, _period_mock, _region_mock, _base_mock, _totals_mock, _date_mock
    ):
        summary = build_net_worth_summary(user=self.user)
        self.assertEqual(summary["inflation_region"], "ES-MD")
        self.assertEqual(summary["net_worth"], Decimal("180.00"))
        self.assertEqual(summary["net_worth_real"], Decimal("180.00"))
        self.assertEqual(summary["liabilities_unbacked_real"], Decimal("40.00"))
        self.assertTrue(summary["inflation_available"])
        self.assertEqual(summary["inflation_status"], "available")

    @patch("net_worth.services.timezone.localdate", return_value=date(2026, 2, 18))
    @patch(
        "net_worth.services.calculate_totals",
        return_value=NetWorthTotals(
            total_assets=Decimal("300.00"),
            total_liabilities=Decimal("120.00"),
            liabilities_asset_backed=Decimal("80.00"),
            liabilities_unbacked=Decimal("40.00"),
            assets_by_category={"cash": Decimal("300.00")},
            assets_by_subcategory={"cash:bank_account": Decimal("300.00")},
            liabilities_by_category={"mortgage": Decimal("120.00")},
        ),
    )
    @patch("net_worth.services.get_base_currency_for_user", return_value="USD")
    def test_build_net_worth_summary_without_inflation_for_non_eur(
        self, _base_mock, _totals_mock, _date_mock
    ):
        summary = build_net_worth_summary(user=self.user)
        self.assertIsNone(summary["inflation_region"])
        self.assertIsNone(summary["net_worth_real"])
        self.assertIsNone(summary["assets_by_category_real"])
        self.assertFalse(summary["inflation_available"])
        self.assertEqual(summary["inflation_status"], "disabled")

    @patch("net_worth.services.timezone.localdate", return_value=date(2026, 2, 18))
    @patch(
        "net_worth.services.calculate_totals",
        return_value=NetWorthTotals(
            total_assets=Decimal("300.00"),
            total_liabilities=Decimal("120.00"),
            liabilities_asset_backed=Decimal("80.00"),
            liabilities_unbacked=Decimal("40.00"),
            assets_by_category={"cash": Decimal("300.00")},
            assets_by_subcategory={"cash:bank_account": Decimal("300.00")},
            liabilities_by_category={"mortgage": Decimal("120.00")},
        ),
    )
    @patch("net_worth.services.get_base_currency_for_user", return_value="EUR")
    @patch("net_worth.services.get_inflation_region_for_user", return_value="ES-MD")
    @patch("net_worth.services.get_inflation_base_period", side_effect=ValidationError("missing"))
    def test_build_net_worth_summary_handles_missing_inflation_coverage(
        self, _period_mock, _region_mock, _base_mock, _totals_mock, _date_mock
    ):
        summary = build_net_worth_summary(user=self.user)
        self.assertEqual(summary["inflation_region"], "ES-MD")
        self.assertIsNone(summary["inflation_base_period"])
        self.assertIsNone(summary["net_worth_real"])
        self.assertFalse(summary["inflation_available"])
        self.assertEqual(summary["inflation_status"], "missing")
