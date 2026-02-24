from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.test import APITestCase
from rest_framework.test import APIRequestFactory

from accounts.models import UserSettings
from budget.models import AnnualExpenseEntry
from core.models import InflationIndex
from .models import Asset, Liability
from .serializers import (
    AssetSerializer,
    EmptySerializer,
    LiabilitySerializer,
    NetWorthSnapshotSerializer,
)
from .services import (
    NetWorthTotals,
    build_net_worth_summary,
    calculate_totals,
    create_asset_for_user,
    create_liability_for_user,
    create_or_update_snapshot_from_current,
    create_snapshot_for_user,
    estimate_liability_monthly_payment_simple,
    estimate_liability_outstanding_amount_simple,
    get_base_currency_for_user,
    get_financed_asset_queryset_for_user,
    get_inflation_base_period,
    get_amount_base_value,
    infer_liability_is_asset_backed,
    serialize_net_worth_summary,
    validate_asset_payload,
    validate_liability_payload,
    validate_snapshot_payload,
)
from .views import NetWorthSnapshotViewSet


class NetWorthServicesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="nw_user", password="pass1234")

    def test_validate_asset_payload_rejects_accounting_without_account(self):
        with self.assertRaises(DRFValidationError):
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

    def test_validate_liability_payload_rejects_accounting_without_account(self):
        with self.assertRaises(DRFValidationError):
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

    @patch("net_worth.services.convert_currency", return_value=Decimal("90.50"))
    def test_get_amount_base_value_success(self, _convert_mock):
        value = get_amount_base_value(
            amount=Decimal("100.00"),
            currency="USD",
            base_currency="EUR",
            as_of_date=date(2026, 2, 18),
        )
        self.assertEqual(value, "90.50")

    @patch("net_worth.services.convert_currency", side_effect=Exception("fx error"))
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

    def test_get_base_currency_and_inflation_base_period(self):
        base = get_base_currency_for_user(user=self.user)
        self.assertEqual(base, "EUR")

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
    @patch("net_worth.services.get_inflation_base_period", return_value=date(2026, 1, 1))
    @patch("net_worth.services.adjust_for_inflation", side_effect=lambda amount, **_: amount)
    def test_build_net_worth_summary_with_inflation(
        self, _adj_mock, _period_mock, _base_mock, _totals_mock, _date_mock
    ):
        summary = build_net_worth_summary(user=self.user)
        self.assertEqual(summary["inflation_region"], "ES")
        self.assertEqual(summary["net_worth"], Decimal("180.00"))
        self.assertEqual(summary["net_worth_real"], Decimal("180.00"))
        self.assertEqual(summary["liabilities_unbacked_real"], Decimal("40.00"))

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

    def test_liability_create_rejects_accounting_without_account(self):
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
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

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
        self.assertEqual(row_2026.cashflow_role, AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT)
        self.assertEqual(row_2026.term_end_year, 2026)
        # 9 cuotas (ene-sep 2026) de 1375.44 -> 12378.96
        self.assertEqual(row_2026.amount_annual, Decimal("12378.96"))

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
        generated_2026.name = "Compromiso ATRIO personalizado"
        generated_2026.amount_annual = Decimal("12000.00")
        generated_2026.notes = "Editado manualmente por usuario"
        generated_2026.save(update_fields=["name", "amount_annual", "notes"])

        update_response = self.client.patch(
            f"/api/net-worth/liabilities/{liability_id}/",
            {
                "notes": "Cambio en pasivo",
                "amount": "20000.00",
            },
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK, update_response.data)

        generated_2026.refresh_from_db()
        self.assertEqual(generated_2026.name, "Compromiso ATRIO personalizado")
        self.assertEqual(generated_2026.amount_annual, Decimal("12000.00"))
        self.assertEqual(generated_2026.notes, "Editado manualmente por usuario")

    def test_snapshot_from_current_and_delete(self):
        Asset.objects.create(
            user=self.user,
            name="Cuenta",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("100.00"),
            is_active=True,
        )
        create_res = self.client.post("/api/net-worth/snapshots/from-current/", format="json")
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        snapshot_id = create_res.data["snapshot"]["id"]

        update_res = self.client.post("/api/net-worth/snapshots/from-current/", format="json")
        self.assertEqual(update_res.status_code, status.HTTP_200_OK)

        delete_res = self.client.delete(f"/api/net-worth/snapshots/{snapshot_id}/")
        self.assertEqual(delete_res.status_code, status.HTTP_204_NO_CONTENT)

    def test_summary_returns_400_without_inflation_index_for_eur(self):
        response = self.client.get("/api/net-worth/summary/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

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

    @patch(
        "net_worth.views.create_or_update_snapshot_from_current", side_effect=ValidationError("x")
    )
    def test_snapshot_from_current_returns_400_on_validation_error(self, _mock_create):
        response = self.client.post("/api/net-worth/snapshots/from-current/", format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class NetWorthSerializerUnitTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="serializer_user", password="pass1234"
        )
        self.factory = APIRequestFactory()
        self.request = self.factory.post("/api/net-worth/assets/")
        self.request.user = self.user

    def test_asset_serializer_create_and_validate(self):
        serializer = AssetSerializer(
            data={
                "name": "Cuenta",
                "category": Asset.Category.CASH,
                "subcategory": Asset.Subcategory.BANK_ACCOUNT,
                "tracking_mode": Asset.TrackingMode.MANUAL,
                "currency": "EUR",
                "annual_interest_tae": "0.50",
                "amount": "100.00",
            },
            context={"request": self.request, "base_currency": "EUR"},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        asset = serializer.save()
        self.assertEqual(asset.user_id, self.user.id)

    def test_snapshot_serializer_validate_and_create(self):
        serializer = NetWorthSnapshotSerializer(
            data={
                "snapshot_date": "2026-02-18",
                "base_currency": "EUR",
                "total_assets": "100.00",
                "total_liabilities": "30.00",
                "net_worth": "70.00",
            },
            context={"request": self.request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        snapshot = serializer.save()
        self.assertEqual(snapshot.user_id, self.user.id)

        invalid = NetWorthSnapshotSerializer(
            data={
                "snapshot_date": "2026-02-19",
                "base_currency": "EUR",
                "total_assets": "100.00",
                "total_liabilities": "30.00",
                "net_worth": "75.00",
            },
            context={"request": self.request},
        )
        self.assertFalse(invalid.is_valid())

    def test_liability_serializer_context_queryset_and_validate(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Casa",
            category=Asset.Category.REAL_ESTATE,
            subcategory=Asset.Subcategory.PRIMARY_HOME,
            currency="EUR",
            amount=Decimal("200000.00"),
            is_active=True,
        )
        serializer = LiabilitySerializer(
            data={
                "name": "Hipoteca",
                "category": Liability.Category.MORTGAGE,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "annual_interest_tae": "2.50",
                "amount": "150000.00",
                "financed_asset_id": asset.id,
            },
            context={
                "request": self.request,
                "base_currency": "EUR",
                "financed_asset_queryset": Asset.objects.filter(user=self.user),
            },
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        liability = serializer.save()
        self.assertTrue(liability.is_asset_backed)

    def test_liability_serializer_exposes_estimated_monthly_payment_amount(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo coche",
            category=Liability.Category.PERSONAL_LOAN,
            currency="EUR",
            annual_interest_tae=Decimal("6.00"),
            amount=Decimal("10000.00"),
            term_months=24,
            rate_type=Liability.RateType.FIXED,
            payment_frequency=Liability.PaymentFrequency.MONTHLY,
            amortization_system=Liability.AmortizationSystem.FRENCH,
            is_active=True,
        )
        serializer = LiabilitySerializer(
            liability,
            context={
                "request": self.request,
                "base_currency": "EUR",
                "financed_asset_queryset": Asset.objects.filter(user=self.user),
            },
        )
        self.assertIsNotNone(serializer.data["estimated_monthly_payment_amount"])

    def test_snapshot_viewset_serializer_class_switch(self):
        view = NetWorthSnapshotViewSet()
        view.action = "from_current"
        self.assertIs(view.get_serializer_class(), EmptySerializer)
