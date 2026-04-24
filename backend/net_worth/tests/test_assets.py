from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.exceptions import ValidationError as DRFValidationError

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from accounting.services_ledger import build_net_worth_opening_balance_note
from core.models import InflationIndex
from core.services import adjust_for_inflation as core_adjust_for_inflation
from ..models import (
    Asset,
    AssetImprovement,
    AssetValuation,
    InvestmentContributionInterval,
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
    build_inflation_adjuster,
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
from ..services_summaries import (
    build_net_worth_summary,
    serialize_net_worth_summary,
)
from ..services_timelines import (
    _build_position_data_cache,
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

    def test_validate_liability_payload_rejects_payment_start_date_before_start_date(self):
        with self.assertRaises(DRFValidationError):
            validate_liability_payload(
                tracking_mode=Liability.TrackingMode.MANUAL,
                accounting_account_id=None,
                category=Liability.Category.PERSONAL_LOAN,
                annual_interest_tae=Decimal("5.00"),
                start_date=date(2024, 2, 1),
                payment_start_date=date(2024, 1, 31),
                expected_end_date=date(2026, 2, 1),
            )

    def test_estimate_liability_outstanding_amount_simple_uses_payment_start_date_when_present(
        self,
    ):
        liability = Liability(
            user=self.user,
            name="ATRIO",
            category=Liability.Category.OTHER,
            currency="EUR",
            start_date=date(2024, 2, 1),
            payment_start_date=date(2024, 9, 21),
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
            liability=liability, as_of_date=date(2024, 10, 20)
        )
        # Primera cuota exactamente en 2024-09-21: a 2024-10-20 solo hay una cuota pagada.
        self.assertEqual(outstanding, Decimal("23000.00000000"))

    @patch("net_worth.services_assets_core.convert_currency", return_value=Decimal("90.50"))
    def test_get_amount_base_value_success(self, _convert_mock):
        value = get_amount_base_value(
            amount=Decimal("100.00"),
            currency="USD",
            base_currency="EUR",
            as_of_date=date(2026, 2, 18),
        )
        self.assertEqual(value, "90.50")

    @patch("net_worth.services_assets_core.convert_currency_cached", return_value=Decimal("90.40"))
    def test_get_amount_base_value_uses_fx_cache_when_available(self, _convert_cached_mock):
        value = get_amount_base_value(
            amount=Decimal("100.00"),
            currency="USD",
            base_currency="EUR",
            as_of_date=date(2026, 2, 18),
            fx_cache={},
        )
        self.assertEqual(value, "90.40")

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

    def test_create_asset_liability_and_financed_queryset(self):
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
        financed_qs = get_financed_asset_queryset_for_user(user=self.user)

        self.assertEqual(liability.financed_asset_id, asset.id)
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

    def test_get_effective_asset_amount_cash_anchors_to_opening_balance_when_present(self):
        account = LedgerAccount.objects.create(
            user=self.user,
            name="Kutxa Bank",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        expense = LedgerAccount.objects.create(
            user=self.user,
            name="Gasto",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )
        equity = LedgerAccount.objects.create(
            user=self.user,
            name="Patrimonio",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
        )
        asset = Asset.objects.create(
            user=self.user,
            name="Kutxa",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            accounting_account_id=account.id,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("0.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )

        historical_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 1),
            value_date=date(2026, 2, 1),
            description="Movimiento historico",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=historical_tx,
            account=account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("2400.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=historical_tx,
            account=expense,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("2400.00"),
            currency="EUR",
        )

        opening_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 18),
            value_date=date(2026, 3, 18),
            description="Saldo inicial Kutxa",
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.SYSTEM,
            notes=build_net_worth_opening_balance_note(position_kind="asset", position_id=asset.id),
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("10000.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=equity,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("10000.00"),
            currency="EUR",
        )

        self.assertEqual(
            get_effective_asset_amount(asset=asset, as_of_date=date(2026, 3, 31)),
            Decimal("10000.00"),
        )

    def test_get_effective_asset_amount_cash_anchors_even_with_legacy_opening_note(self):
        account = LedgerAccount.objects.create(
            user=self.user,
            name="Kutxa Compartida",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        expense = LedgerAccount.objects.create(
            user=self.user,
            name="Gasto",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )
        equity = LedgerAccount.objects.create(
            user=self.user,
            name="Patrimonio",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
        )
        asset = Asset.objects.create(
            user=self.user,
            name="Kutxa Compartida",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            accounting_account_id=account.id,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("0.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )

        historical_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 1),
            value_date=date(2026, 2, 1),
            description="Movimiento historico Kutxa",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=historical_tx,
            account=account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("2400.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=historical_tx,
            account=expense,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("2400.00"),
            currency="EUR",
        )

        legacy_opening_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 18),
            value_date=date(2026, 3, 18),
            description="Saldo inicial Kutxa Compartida",
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.SYSTEM,
            notes="net_worth_opening_balance:asset:999999",
        )
        LedgerEntry.objects.create(
            transaction=legacy_opening_tx,
            account=account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("10000.00"),
            currency="EUR",
            asset=asset,
        )
        LedgerEntry.objects.create(
            transaction=legacy_opening_tx,
            account=equity,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("10000.00"),
            currency="EUR",
        )

        position_cache = _build_position_data_cache([asset], [])
        self.assertEqual(
            get_effective_asset_amount(
                asset=asset,
                as_of_date=date(2026, 3, 31),
                position_cache=position_cache,
            ),
            Decimal("10000.00"),
        )
        self.assertEqual(
            get_effective_asset_amount(asset=asset, as_of_date=date(2026, 3, 31)),
            Decimal("10000.00"),
        )

    def test_get_effective_asset_amount_cash_anchors_with_system_opening_description_without_note(
        self,
    ):
        account = LedgerAccount.objects.create(
            user=self.user,
            name="Deposito MyInvestor",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        expense = LedgerAccount.objects.create(
            user=self.user,
            name="Gasto",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )
        equity = LedgerAccount.objects.create(
            user=self.user,
            name="Patrimonio",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
        )
        asset = Asset.objects.create(
            user=self.user,
            name="Deposito 1 mes",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.SHORT_TERM_DEPOSIT,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            accounting_account_id=account.id,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("0.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )

        historical_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 1),
            value_date=date(2026, 2, 1),
            description="Movimiento historico deposito",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=historical_tx,
            account=account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("16533.40"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=historical_tx,
            account=expense,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("16533.40"),
            currency="EUR",
        )

        opening_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 18),
            value_date=date(2026, 3, 18),
            description="Saldo inicial contable: Deposito 1 mes",
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.SYSTEM,
            notes="",
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("6533.40"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=equity,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("6533.40"),
            currency="EUR",
        )

        self.assertEqual(
            get_effective_asset_amount(asset=asset, as_of_date=date(2026, 3, 31)),
            Decimal("6533.40"),
        )

    def test_get_effective_asset_amount_cash_anchors_with_legacy_saldo_inicial_description(self):
        account = LedgerAccount.objects.create(
            user=self.user,
            name="Kutxa legacy",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        expense = LedgerAccount.objects.create(
            user=self.user,
            name="Gasto",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )
        equity = LedgerAccount.objects.create(
            user=self.user,
            name="Patrimonio",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
        )
        asset = Asset.objects.create(
            user=self.user,
            name="Kutxa Compartida",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            accounting_account_id=account.id,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("0.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )

        historical_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 1),
            value_date=date(2026, 2, 1),
            description="Movimiento historico Kutxa legacy",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=historical_tx,
            account=account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("2400.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=historical_tx,
            account=expense,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("2400.00"),
            currency="EUR",
        )

        opening_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 18),
            value_date=date(2026, 3, 18),
            description="Saldo inicial Kutxa Compartida",
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.SYSTEM,
            notes="",
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("10000.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=equity,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("10000.00"),
            currency="EUR",
        )

        self.assertEqual(
            get_effective_asset_amount(asset=asset, as_of_date=date(2026, 3, 31)),
            Decimal("10000.00"),
        )

    def test_get_effective_asset_amount_ignores_non_opening_system_saldo_inicial_candidates(self):
        account = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta liquidez",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        expense = LedgerAccount.objects.create(
            user=self.user,
            name="Gasto",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )
        equity = LedgerAccount.objects.create(
            user=self.user,
            name="Patrimonio",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
        )
        asset = Asset.objects.create(
            user=self.user,
            name="Cuenta liquidez",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            accounting_account_id=account.id,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("0.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )

        opening_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 18),
            value_date=date(2026, 3, 18),
            description="Saldo inicial contable: Cuenta liquidez",
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.SYSTEM,
            notes=build_net_worth_opening_balance_note(position_kind="asset", position_id=asset.id),
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("10000.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=equity,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("10000.00"),
            currency="EUR",
        )

        # Candidate with legacy description but not a real opening shape
        # (counterpart is expense, not equity) must be ignored.
        wrong_candidate = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 28),
            value_date=date(2026, 2, 28),
            description="Saldo inicial ajuste manual",
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.SYSTEM,
            notes="",
        )
        LedgerEntry.objects.create(
            transaction=wrong_candidate,
            account=account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("500.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=wrong_candidate,
            account=expense,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("500.00"),
            currency="EUR",
        )

        self.assertEqual(
            get_effective_asset_amount(asset=asset, as_of_date=date(2026, 3, 31)),
            Decimal("10000.00"),
        )

    def test_get_effective_asset_amount_investment_keeps_historical_balance(self):
        account = LedgerAccount.objects.create(
            user=self.user,
            name="Cartera fondos",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        expense = LedgerAccount.objects.create(
            user=self.user,
            name="Gasto",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )
        equity = LedgerAccount.objects.create(
            user=self.user,
            name="Patrimonio",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
        )
        asset = Asset.objects.create(
            user=self.user,
            name="Fondo global",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            accounting_account_id=account.id,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("0.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )

        historical_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 1),
            value_date=date(2026, 2, 1),
            description="Movimiento historico inversion",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=historical_tx,
            account=account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("5000.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=historical_tx,
            account=expense,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("5000.00"),
            currency="EUR",
        )

        opening_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 18),
            value_date=date(2026, 3, 18),
            description="Saldo inicial inversion",
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.SYSTEM,
            notes=build_net_worth_opening_balance_note(position_kind="asset", position_id=asset.id),
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("10000.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=equity,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("10000.00"),
            currency="EUR",
        )

        self.assertEqual(
            get_effective_asset_amount(asset=asset, as_of_date=date(2026, 3, 31)),
            Decimal("15000.00"),
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

    def test_get_effective_asset_amount_accumulates_multiple_intervals(self):
        asset = Asset.objects.create(
            user=self.user,
            name="ETF multi-intervalo",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.ETFS,
            currency="EUR",
            start_date=date(2025, 1, 1),
            investment_contribution_mode=Asset.InvestmentContributionMode.PERIODIC_CONTRIBUTION,
            monthly_contribution_amount=Decimal("1.00"),
            amount=Decimal("1000.00"),
            initial_purchase_value=Decimal("1000.00"),
            is_active=True,
        )
        InvestmentContributionInterval.objects.create(
            asset=asset,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 1),
            amount=Decimal("100.00"),
            frequency=Asset.InvestmentContributionFrequency.MONTHLY,
            currency="EUR",
        )
        InvestmentContributionInterval.objects.create(
            asset=asset,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 1),
            amount=Decimal("50.00"),
            frequency=Asset.InvestmentContributionFrequency.MONTHLY,
            currency="EUR",
        )
        effective = get_effective_asset_amount(asset=asset, as_of_date=date(2026, 3, 1))
        self.assertEqual(effective.quantize(Decimal("0.01")), Decimal("2350.00"))

    def test_get_effective_asset_amount_skips_intervals_with_currency_mismatch(self):
        asset = Asset.objects.create(
            user=self.user,
            name="ETF USD",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.ETFS,
            currency="EUR",
            start_date=date(2026, 1, 1),
            investment_contribution_mode=Asset.InvestmentContributionMode.PERIODIC_CONTRIBUTION,
            amount=Decimal("1000.00"),
            initial_purchase_value=Decimal("1000.00"),
            is_active=True,
        )
        InvestmentContributionInterval.objects.create(
            asset=asset,
            start_date=date(2026, 1, 1),
            end_date=None,
            amount=Decimal("100.00"),
            frequency=Asset.InvestmentContributionFrequency.MONTHLY,
            currency="USD",
        )
        effective = get_effective_asset_amount(asset=asset, as_of_date=date(2026, 3, 1))
        self.assertEqual(effective, Decimal("1000.00"))

    @patch(
        "net_worth.services_assets_core._build_investment_contribution_schedule",
        return_value=[(date(2026, 1, 1), Decimal("100.00"))],
    )
    def test_periodic_investment_schedule_uses_position_cache(self, schedule_mock):
        asset = Asset.objects.create(
            user=self.user,
            name="ETF cache",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.ETFS,
            currency="EUR",
            start_date=date(2026, 1, 1),
            investment_contribution_mode=Asset.InvestmentContributionMode.PERIODIC_CONTRIBUTION,
            investment_contribution_frequency=Asset.InvestmentContributionFrequency.MONTHLY,
            monthly_contribution_amount=Decimal("100.00"),
            amount=Decimal("1000.00"),
            initial_purchase_value=Decimal("1000.00"),
            is_active=True,
        )
        position_cache = _build_position_data_cache([asset], [])
        get_effective_asset_amount(
            asset=asset,
            as_of_date=date(2026, 2, 28),
            position_cache=position_cache,
        )
        get_effective_asset_amount(
            asset=asset,
            as_of_date=date(2026, 2, 28),
            position_cache=position_cache,
        )
        self.assertEqual(schedule_mock.call_count, 1)

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

    def test_get_effective_liability_amount_anchors_to_opening_balance_when_present(self):
        liability_account = LedgerAccount.objects.create(
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
        equity_account = LedgerAccount.objects.create(
            user=self.user,
            name="Patrimonio neto",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
        )
        liability = Liability.objects.create(
            user=self.user,
            name="Hipoteca",
            category=Liability.Category.MORTGAGE,
            tracking_mode=Liability.TrackingMode.ACCOUNTING,
            accounting_account_id=liability_account.id,
            currency="EUR",
            start_date=date(2024, 1, 1),
            annual_interest_tae=Decimal("2.00"),
            amount=Decimal("1000.00"),
            is_active=True,
        )

        historical_payment = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 10),
            value_date=date(2026, 2, 10),
            description="Pago historico importado",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=historical_payment,
            account=liability_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("900.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=historical_payment,
            account=asset_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("900.00"),
            currency="EUR",
        )

        opening_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 18),
            value_date=date(2026, 3, 18),
            description="Saldo inicial contable: Hipoteca",
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.SYSTEM,
            notes=build_net_worth_opening_balance_note(
                position_kind="liability", position_id=liability.id
            ),
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=liability_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=equity_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )

        self.assertEqual(
            get_effective_liability_amount(liability=liability, as_of_date=date(2026, 3, 31)),
            Decimal("1000.00"),
        )

    def test_get_effective_asset_amount_accounting_matches_with_position_cache(self):
        account = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta contable activo",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        equity_account = LedgerAccount.objects.create(
            user=self.user,
            name="Patrimonio neto",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
        )
        asset = Asset.objects.create(
            user=self.user,
            name="Cuenta banco",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            accounting_account_id=account.id,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("100.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 10),
            value_date=date(2026, 2, 10),
            description="Saldo cuenta",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("800.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=equity_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("800.00"),
            currency="EUR",
        )
        position_cache = _build_position_data_cache([asset], [])
        self.assertEqual(
            get_effective_asset_amount(
                asset=asset, as_of_date=date(2026, 2, 28), position_cache=position_cache
            ),
            get_effective_asset_amount(asset=asset, as_of_date=date(2026, 2, 28)),
        )

    def test_get_effective_liability_amount_accounting_matches_with_position_cache(self):
        liability_account = LedgerAccount.objects.create(
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
        equity_account = LedgerAccount.objects.create(
            user=self.user,
            name="Patrimonio neto",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
        )
        liability = Liability.objects.create(
            user=self.user,
            name="Hipoteca",
            category=Liability.Category.MORTGAGE,
            tracking_mode=Liability.TrackingMode.ACCOUNTING,
            accounting_account_id=liability_account.id,
            currency="EUR",
            start_date=date(2024, 1, 1),
            annual_interest_tae=Decimal("2.00"),
            amount=Decimal("1000.00"),
            is_active=True,
        )

        historical_payment = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 10),
            value_date=date(2026, 2, 10),
            description="Pago historico",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=historical_payment,
            account=liability_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("900.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=historical_payment,
            account=asset_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("900.00"),
            currency="EUR",
        )

        opening_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 18),
            value_date=date(2026, 3, 18),
            description="Saldo inicial contable: Hipoteca",
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.SYSTEM,
            notes=build_net_worth_opening_balance_note(
                position_kind="liability", position_id=liability.id
            ),
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=liability_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=equity_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )
        position_cache = _build_position_data_cache([], [liability])
        self.assertEqual(
            get_effective_liability_amount(
                liability=liability,
                as_of_date=date(2026, 3, 31),
                position_cache=position_cache,
            ),
            get_effective_liability_amount(liability=liability, as_of_date=date(2026, 3, 31)),
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

    def test_build_inflation_adjuster_matches_core_adjustment_formula(self):
        InflationIndex.objects.create(
            region="ES",
            period=date(2026, 1, 1),
            index=Decimal("100.0000"),
        )
        InflationIndex.objects.create(
            region="ES",
            period=date(2026, 2, 1),
            index=Decimal("103.0000"),
        )
        adjuster = build_inflation_adjuster(
            region="ES",
            date_value=date(2026, 2, 18),
            base_period=date(2026, 1, 1),
        )
        self.assertEqual(
            adjuster(Decimal("300.00")),
            core_adjust_for_inflation(
                Decimal("300.00"),
                date=date(2026, 2, 18),
                region="ES",
                base_period=date(2026, 1, 1),
            ),
        )

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
