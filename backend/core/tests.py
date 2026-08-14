from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import UserSettings
from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from budget.models import AnnualExpenseEntry, AnnualIncomeEntry
from memberships.models import FamilyMember, Ownership, OwnershipLink
from .models import FxRate, InflationIndex, MarketDataSyncState
from net_worth.models import (
    Asset,
    AssetValuation,
    InvestmentAssetEvent,
    Liability,
    LiabilityEvent,
    LiabilityValuation,
    LiquidityAssetEvent,
    LiquidityMonthlyCheckin,
)
from .services import (
    FxConversion,
    _get_inflation_index,
    _normalize_month_start,
    adjust_for_inflation,
    convert_currency,
    convert_currency_detailed,
    get_latest_inflation_period,
    normalize_currency_code,
    validate_fx_currency_pair,
    validate_inflation_period_start,
)
from .market_data import (
    _build_fx_scope_requests,
    MarketDataSyncError,
    ensure_market_history,
    sync_inflation_history,
    sync_market_data,
    sync_market_history,
)
from net_worth.services_assets_core import get_effective_asset_amount
from net_worth.services_liabilities_core import get_effective_liability_amount


class CoreServicesTests(TestCase):
    def test_normalize_currency_code(self):
        self.assertEqual(normalize_currency_code(" eur "), "EUR")
        self.assertEqual(normalize_currency_code(None), "")

    def test_validate_fx_currency_pair_rejects_invalid_codes(self):
        with self.assertRaises(ValidationError):
            validate_fx_currency_pair(from_currency="EU", to_currency="USD")

    def test_validate_inflation_period_start_rejects_non_first_day(self):
        with self.assertRaises(ValidationError):
            validate_inflation_period_start(period=date(2026, 2, 2))

    def test_normalize_month_start_from_string_and_invalid_type(self):
        self.assertEqual(_normalize_month_start("2026-02-18"), date(2026, 2, 1))
        with self.assertRaises(ValidationError):
            _normalize_month_start(123)

    def test_get_inflation_index_requires_region_and_has_fallback(self):
        with self.assertRaises(ValidationError):
            _get_inflation_index("", date(2026, 2, 1))

        InflationIndex.objects.create(
            region=InflationIndex.Region.ES,
            period=date(2026, 3, 1),
            index=Decimal("102.0000"),
        )
        # Querying earlier than first known period should fallback to first row.
        self.assertEqual(_get_inflation_index("ES", date(2026, 1, 1)), Decimal("102.0000"))

    def test_convert_currency_direct_rate(self):
        FxRate.objects.create(
            from_currency="USD",
            to_currency="EUR",
            rate=Decimal("0.90"),
            rate_date=date(2026, 2, 1),
        )

        amount = convert_currency(Decimal("100"), "USD", "EUR", date=date(2026, 2, 15))
        self.assertEqual(amount, Decimal("90.00"))

    def test_convert_currency_inverse_rate(self):
        FxRate.objects.create(
            from_currency="EUR",
            to_currency="USD",
            rate=Decimal("1.25"),
            rate_date=date(2026, 2, 1),
        )

        amount = convert_currency(Decimal("125"), "USD", "EUR", date=date(2026, 2, 15))
        self.assertEqual(amount, Decimal("100.00"))

    def test_convert_currency_falls_back_to_first_available_rate_when_date_is_too_old(self):
        FxRate.objects.create(
            from_currency="USD",
            to_currency="EUR",
            rate=Decimal("0.80"),
            rate_date=date(2020, 1, 1),
        )

        amount = convert_currency(Decimal("100"), "USD", "EUR", date=date(2016, 2, 21))
        self.assertEqual(amount, Decimal("80.00"))

    @override_settings()
    def test_convert_currency_uses_pivot_triangulation(self):
        FxRate.objects.create(
            from_currency="EUR",
            to_currency="USD",
            rate=Decimal("1.10"),
            rate_date=date(2026, 2, 1),
        )
        FxRate.objects.create(
            from_currency="USD",
            to_currency="JPY",
            rate=Decimal("150"),
            rate_date=date(2026, 2, 1),
        )

        amount = convert_currency(Decimal("2"), "EUR", "JPY", date=date(2026, 2, 10))
        self.assertEqual(amount, Decimal("330.00"))

    def test_convert_currency_raises_when_pair_missing(self):
        with self.assertRaises(ValidationError):
            convert_currency(Decimal("10"), "EUR", "GBP", date=date(2026, 2, 10))

    def test_convert_currency_validates_amount_and_code(self):
        with self.assertRaises(ValidationError):
            convert_currency(None, "EUR", "USD", date=date(2026, 2, 10))
        with self.assertRaises(ValidationError):
            convert_currency(Decimal("10"), "EU", "USD", date=date(2026, 2, 10))

    def test_convert_currency_same_currency_shortcut(self):
        amount = convert_currency(Decimal("10.126"), "EUR", "EUR", date=date(2026, 2, 10))
        self.assertEqual(amount, Decimal("10.13"))

    def test_convert_currency_inverse_zero_rate_raises(self):
        FxRate.objects.create(
            from_currency="EUR",
            to_currency="USD",
            rate=Decimal("0"),
            rate_date=date(2026, 2, 1),
        )
        with self.assertRaises(ValidationError):
            convert_currency(Decimal("10"), "USD", "EUR", date=date(2026, 2, 10))

    @override_settings(FX_PIVOT="EUR")
    def test_convert_currency_raises_when_pivot_matches_pair(self):
        with self.assertRaises(ValidationError):
            convert_currency(Decimal("10"), "EUR", "JPY", date=date(2026, 2, 10))

    @override_settings(FX_PIVOT="USD")
    def test_convert_currency_triangulation_with_inverse_legs(self):
        FxRate.objects.create(
            from_currency="USD",
            to_currency="EUR",
            rate=Decimal("0.80"),
            rate_date=date(2026, 2, 1),
        )
        FxRate.objects.create(
            from_currency="JPY",
            to_currency="USD",
            rate=Decimal("0.01"),
            rate_date=date(2026, 2, 1),
        )
        amount = convert_currency(Decimal("10"), "EUR", "JPY", date=date(2026, 2, 10))
        self.assertEqual(amount, Decimal("1250.00"))

    @override_settings(FX_PIVOT="USD")
    def test_convert_currency_triangulation_zero_leg_raises(self):
        FxRate.objects.create(
            from_currency="EUR",
            to_currency="USD",
            rate=Decimal("0"),
            rate_date=date(2026, 2, 1),
        )
        FxRate.objects.create(
            from_currency="USD",
            to_currency="JPY",
            rate=Decimal("100"),
            rate_date=date(2026, 2, 1),
        )
        with self.assertRaises(ValidationError):
            convert_currency(Decimal("10"), "EUR", "JPY", date=date(2026, 2, 10))

    def test_adjust_for_inflation_uses_latest_period_by_default(self):
        InflationIndex.objects.create(
            region=InflationIndex.Region.ES,
            period=date(2026, 1, 1),
            index=Decimal("100.0000"),
        )
        InflationIndex.objects.create(
            region=InflationIndex.Region.ES,
            period=date(2026, 2, 1),
            index=Decimal("110.0000"),
        )

        adjusted = adjust_for_inflation(
            Decimal("110"),
            date=date(2026, 1, 15),
            region=InflationIndex.Region.ES,
        )
        self.assertEqual(adjusted, Decimal("121.00"))

    def test_adjust_for_inflation_raises_when_index_is_zero(self):
        InflationIndex.objects.create(
            region=InflationIndex.Region.ES,
            period=date(2026, 1, 1),
            index=Decimal("0.0000"),
        )
        InflationIndex.objects.create(
            region=InflationIndex.Region.ES,
            period=date(2026, 2, 1),
            index=Decimal("100.0000"),
        )

        with self.assertRaises(ValidationError):
            adjust_for_inflation(
                Decimal("100"),
                date=date(2026, 1, 15),
                region=InflationIndex.Region.ES,
                base_period=date(2026, 2, 1),
            )

    def test_get_latest_inflation_period_returns_latest(self):
        InflationIndex.objects.create(
            region=InflationIndex.Region.ES,
            period=date(2026, 1, 1),
            index=Decimal("99.0000"),
        )
        InflationIndex.objects.create(
            region=InflationIndex.Region.ES,
            period=date(2026, 3, 1),
            index=Decimal("101.0000"),
        )

        self.assertEqual(get_latest_inflation_period(), date(2026, 3, 1))

    def test_get_latest_inflation_period_raises_when_missing(self):
        with self.assertRaises(ValidationError):
            get_latest_inflation_period(region="ES")

    def test_adjust_for_inflation_validates_amount_and_missing_base(self):
        with self.assertRaises(ValidationError):
            adjust_for_inflation(None, date=date(2026, 2, 1), region="ES")

        with self.assertRaises(ValidationError):
            adjust_for_inflation(Decimal("10"), date=date(2026, 2, 1), region="ES")

    @patch(
        "core.market_data._fetch_json",
        return_value={
            "amount": 1.0,
            "base": "USD",
            "rates": {
                "2025-03-03": {"EUR": 0.92},
                "2025-03-04": {"EUR": 0.93},
            },
        },
    )
    def test_sync_market_history_imports_fiat_rows(self, _fetch_json_mock):
        inserted = sync_market_history(
            from_currency="USD",
            to_currency="EUR",
            start_date=date(2025, 3, 3),
            end_date=date(2025, 3, 4),
        )

        self.assertEqual(inserted, 2)
        self.assertEqual(
            FxRate.objects.get(
                from_currency="USD",
                to_currency="EUR",
                rate_date=date(2025, 3, 3),
            ).rate,
            Decimal("0.92"),
        )

    @patch(
        "core.market_data._fetch_json",
        return_value={
            "prices": [
                [1740960000000, 82000.0],
                [1741000000000, 82500.5],
                [1741046400000, 83010.25],
            ]
        },
    )
    def test_sync_market_history_imports_crypto_rows_grouped_by_day(self, _fetch_json_mock):
        inserted = sync_market_history(
            from_currency="BTC",
            to_currency="EUR",
            start_date=date(2025, 3, 3),
            end_date=date(2025, 3, 4),
        )

        self.assertEqual(inserted, 2)
        self.assertEqual(
            FxRate.objects.get(
                from_currency="BTC",
                to_currency="EUR",
                rate_date=date(2025, 3, 3),
            ).rate,
            Decimal("82500.5"),
        )

    @patch("core.market_data._fetch_json")
    def test_sync_market_history_falls_back_to_cryptocompare_when_coingecko_fails(
        self, fetch_json_mock
    ):
        fetch_json_mock.side_effect = [
            MarketDataSyncError("coingecko unauthorized"),
            {
                "Response": "Success",
                "Data": {
                    "Data": [
                        {"time": 1740960000, "close": 82000.0},
                        {"time": 1741046400, "close": 83010.25},
                    ]
                },
            },
        ]

        inserted = sync_market_history(
            from_currency="BTC",
            to_currency="EUR",
            start_date=date(2025, 3, 3),
            end_date=date(2025, 3, 4),
        )

        self.assertEqual(inserted, 2)
        row = FxRate.objects.get(
            from_currency="BTC",
            to_currency="EUR",
            rate_date=date(2025, 3, 3),
        )
        self.assertEqual(row.rate, Decimal("82000.0"))
        self.assertEqual(row.source, "cryptocompare")

    @patch("core.market_data.sync_market_history", return_value=31)
    def test_ensure_market_history_backfills_only_when_earliest_row_is_missing(
        self, sync_market_history_mock
    ):
        FxRate.objects.create(
            from_currency="USD",
            to_currency="EUR",
            rate=Decimal("0.90"),
            rate_date=date(2025, 5, 1),
        )

        inserted = ensure_market_history(
            from_currency="USD",
            to_currency="EUR",
            start_date=date(2025, 3, 3),
            end_date=date(2025, 6, 1),
        )

        self.assertEqual(inserted, 31)
        sync_market_history_mock.assert_called_once_with(
            from_currency="USD",
            to_currency="EUR",
            start_date=date(2025, 3, 3),
            end_date=date(2025, 4, 30),
        )

    @patch(
        "core.market_data._fetch_json",
        return_value=[
            {
                "Nombre": "Total Nacional. Indice general. Indice.",
                "MetaData": [{"T3_Variable": "Totales Territoriales", "Nombre": "Nacional"}],
                "Data": [
                    {"Fecha": "2025-01-01T00:00:00.000+01:00", "Valor": 98.579},
                    {"Fecha": "2025-02-01T00:00:00.000+01:00", "Valor": 98.966},
                ],
            },
            {
                "Nombre": "Madrid, Comunidad de. Indice general. Indice.",
                "MetaData": [
                    {
                        "T3_Variable": "Comunidades y Ciudades Autónomas",
                        "Nombre": "Madrid, Comunidad de",
                    }
                ],
                "Data": [
                    {"Fecha": "2025-01-01T00:00:00.000+01:00", "Valor": 99.100},
                    {"Fecha": "2025-02-01T00:00:00.000+01:00", "Valor": 99.400},
                ],
            },
        ],
    )
    def test_sync_inflation_history_imports_region_rows(self, _fetch_json_mock):
        inserted = sync_inflation_history(
            region=InflationIndex.Region.ES_MD,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 2, 1),
        )

        self.assertEqual(inserted, 2)
        row = InflationIndex.objects.get(
            region=InflationIndex.Region.ES_MD, period=date(2025, 1, 1)
        )
        self.assertEqual(row.index, Decimal("99.1"))
        self.assertEqual(row.source, "ine")

    @patch("core.market_data._fetch_json")
    def test_sync_market_data_updates_sync_state(self, fetch_json_mock):
        _ine_payload = [
            {
                "Nombre": "Total Nacional. Indice general. Indice.",
                "MetaData": [{"T3_Variable": "Totales Territoriales", "Nombre": "Nacional"}],
                "Data": [{"Fecha": "2025-03-01T00:00:00.000+01:00", "Valor": 99.024}],
            }
        ]

        def _side_effect(*, url: str) -> object:
            if "frankfurter" in url:
                return {"amount": 1.0, "base": "USD", "rates": {"2025-03-03": {"EUR": 0.92}}}
            return _ine_payload

        fetch_json_mock.side_effect = _side_effect
        user = get_user_model().objects.create_user(username="sync_user", password="pass1234")
        UserSettings.objects.update_or_create(
            user=user,
            defaults={"base_currency": "EUR", "inflation_region": "ES"},
        )
        Asset.objects.create(
            user=user,
            name="Cuenta USD",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="USD",
            start_date=date(2025, 3, 3),
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("1000.00"),
            is_active=True,
        )

        summary = sync_market_data(datasets=["fx", "inflation"], mode="reconcile")

        self.assertEqual(summary["fx"], 1)
        self.assertEqual(summary["inflation"], 1)
        fx_state = MarketDataSyncState.objects.get(dataset="fx", scope="USD->EUR")
        self.assertEqual(fx_state.required_start_date, date.today() - timedelta(days=365 * 5))
        self.assertEqual(fx_state.covered_until, date(2025, 3, 3))
        inflation_state = MarketDataSyncState.objects.get(dataset="inflation", scope="ES")
        self.assertEqual(inflation_state.required_start_date, date(2025, 3, 1))

    def test_build_fx_scope_requests_flips_fiat_to_crypto_pairs(self):
        user = get_user_model().objects.create_user(username="eth_user", password="pass1234")
        UserSettings.objects.update_or_create(
            user=user,
            defaults={"base_currency": "ETH", "inflation_region": "ES"},
        )
        Asset.objects.create(
            user=user,
            name="Cuenta EUR",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            start_date=date(2021, 3, 31),
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("1000.00"),
            is_active=True,
        )
        Asset.objects.create(
            user=user,
            name="Wallet BTC",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.CRYPTOCURRENCIES,
            currency="BTC",
            start_date=date(2021, 3, 31),
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("1.00"),
            is_active=True,
        )

        requests = _build_fx_scope_requests()
        scopes = {request.scope for request in requests}
        self.assertIn("ETH->EUR", scopes)
        self.assertIn("BTC->ETH", scopes)
        self.assertNotIn("EUR->ETH", scopes)


class ConvertCurrencyDetailedTests(TestCase):
    def test_same_currency_keeps_full_precision_and_marks_same(self):
        result = convert_currency_detailed(Decimal("10.12345678"), "EUR", "EUR")
        self.assertEqual(result.resolution, "same")
        self.assertEqual(result.rate, Decimal("1"))
        self.assertIsNone(result.rate_date)
        self.assertEqual(result.converted, Decimal("10.12345678"))

    def test_exact_inverse_rate_preserves_crypto_precision(self):
        # 1 BTC = 90000 EUR el 2026-06-16; 45 EUR -> 0.0005 BTC (8 decimales).
        FxRate.objects.create(
            from_currency="BTC",
            to_currency="EUR",
            rate=Decimal("90000"),
            rate_date=date(2026, 6, 16),
        )
        result = convert_currency_detailed(
            Decimal("45"), "EUR", "BTC", on_date=date(2026, 6, 16), allow_sync=False
        )
        self.assertEqual(result.resolution, "exact")
        self.assertEqual(result.rate_date, date(2026, 6, 16))
        self.assertEqual(result.converted, Decimal("0.00050000"))

    def test_falls_back_to_nearest_earlier_rate(self):
        FxRate.objects.create(
            from_currency="BTC",
            to_currency="EUR",
            rate=Decimal("90000"),
            rate_date=date(2026, 6, 10),
        )
        result = convert_currency_detailed(
            Decimal("45"), "EUR", "BTC", on_date=date(2026, 6, 16), allow_sync=False
        )
        self.assertEqual(result.resolution, "fallback")
        self.assertEqual(result.rate_date, date(2026, 6, 10))
        self.assertEqual(result.converted, Decimal("0.00050000"))

    def test_missing_rate_without_sync_raises(self):
        with self.assertRaises(ValidationError):
            convert_currency_detailed(
                Decimal("45"), "EUR", "BTC", on_date=date(2026, 6, 16), allow_sync=False
            )

    def test_sync_is_attempted_then_resolves_exact(self):
        def _fake_sync(*, from_currency, to_currency, start_date, end_date):
            FxRate.objects.create(
                from_currency=from_currency,
                to_currency=to_currency,
                rate=Decimal("90000"),
                rate_date=start_date,
            )
            return 1

        with patch("core.market_data.sync_crypto_history", side_effect=_fake_sync):
            result = convert_currency_detailed(
                Decimal("45"), "EUR", "BTC", on_date=date(2026, 6, 16), allow_sync=True
            )
        self.assertEqual(result.resolution, "synced")
        self.assertEqual(result.rate_date, date(2026, 6, 16))
        self.assertEqual(result.converted, Decimal("0.00050000"))


class FxConvertEndpointTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="fx_convert_user",
            password="pass1234",
        )

    def test_requires_auth(self):
        response = self.client.get("/api/core/fx/convert/?amount=45&from=EUR&to=BTC")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_converts_with_exact_rate(self):
        FxRate.objects.create(
            from_currency="BTC",
            to_currency="EUR",
            rate=Decimal("90000"),
            rate_date=date(2026, 6, 16),
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            "/api/core/fx/convert/?amount=45&from=EUR&to=BTC&date=2026-06-16"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["converted"], "0.00050000")
        self.assertEqual(response.data["resolution"], "exact")
        self.assertEqual(response.data["rate_date"], "2026-06-16")

    def test_missing_params_returns_400(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/core/fx/convert/?amount=45&from=EUR")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PortableDataImportAPITests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="portable_user",
            password="pass1234",
        )
        self.client.force_authenticate(self.user)

    def _build_bundle(self, **overrides):
        bundle = {
            "schema_version": 1,
            "exported_at": "2026-03-10T10:00:00.000Z",
            "source_app": "core",
            "exported_app_version": "0.18.15",
            "settings": {"base_currency": "USD"},
            "data": {
                "annual_income": [
                    {
                        "id": 10,
                        "name": "Nomina",
                        "category": "salary",
                        "subcategory": "employee_salary",
                        "owner_name": "Pablo",
                        "income_type": "recurrent",
                        "time_profile": "structural_recurrent",
                        "cashflow_role": "operating",
                        "event_group": "",
                        "target_month": None,
                        "term_end_month": None,
                        "term_end_year": None,
                        "amount_input_period": "annual",
                        "amount_annual": "30000.00",
                        "fiscal_year": 2026,
                        "currency": "EUR",
                        "notes": "",
                        "is_active": True,
                    }
                ],
                "annual_expense": [
                    {
                        "id": 11,
                        "name": "Vivienda",
                        "category": "consumption_expenses",
                        "subcategory": "housing_home",
                        "owner_name": "Pablo",
                        "expense_type": "recurrent",
                        "time_profile": "structural_recurrent",
                        "cashflow_role": "operating",
                        "event_group": "",
                        "target_month": None,
                        "term_end_month": None,
                        "term_end_year": None,
                        "amount_input_period": "annual",
                        "amount_annual": "12000.00",
                        "fiscal_year": 2026,
                        "currency": "EUR",
                        "notes": "",
                        "is_active": True,
                    }
                ],
                "assets": [
                    {
                        "id": 20,
                        "name": "Cuenta",
                        "category": "cash",
                        "subcategory": "bank_account",
                        "tracking_mode": "accounting",
                        "accounting_account_id": 70,
                        "currency": "EUR",
                        "start_date": "2026-01-01",
                        "amount": "1000.00",
                        "annual_interest_tae": "0.50",
                        "is_active": True,
                        "notes": "",
                    }
                ],
                "liabilities": [
                    {
                        "id": 30,
                        "name": "Hipoteca",
                        "category": "mortgage",
                        "tracking_mode": "manual",
                        "accounting_account_id": None,
                        "currency": "EUR",
                        "start_date": "2026-01-01",
                        "expected_end_date": "2036-01-01",
                        "term_months": 120,
                        "rate_type": "fixed",
                        "payment_frequency": "monthly",
                        "amortization_system": "french",
                        "annual_interest_tae": "1.50",
                        "principal_amount": "80000.00",
                        "amount": "80000.00",
                        "is_active": True,
                        "notes": "",
                        "financed_asset_ref": 20,
                    }
                ],
                "accounting": {
                    "accounts": [
                        {
                            "id": 70,
                            "name": "Cuenta corriente",
                            "account_type": "asset",
                            "currency": "EUR",
                            "origin": "user",
                            "asset_id": 20,
                            "liability_id": None,
                            "is_active": True,
                            "notes": "",
                        },
                        {
                            "id": 71,
                            "name": "Ingresos sistema",
                            "account_type": "income",
                            "currency": "EUR",
                            "origin": "system",
                            "asset_id": None,
                            "liability_id": None,
                            "is_active": True,
                            "notes": "",
                        },
                    ],
                    "transactions": [
                        {
                            "id": 80,
                            "booking_date": "2026-02-10",
                            "value_date": "2026-02-10",
                            "description": "Nomina importada",
                            "status": "posted",
                            "origin": "manual",
                            "notes": "",
                            "ownership_id": 60,
                            "quick_entry_kind": "income",
                            "investment_direction": "",
                            "entries": [
                                {
                                    "id": 90,
                                    "account_id": 70,
                                    "side": "debit",
                                    "amount": "1000.00",
                                    "currency": "EUR",
                                    "flow_family": "income",
                                    "category_key": "salary",
                                    "subcategory_key": "employee_salary",
                                    "asset_id": 20,
                                    "liability_id": None,
                                    "notes": "",
                                },
                                {
                                    "id": 91,
                                    "account_id": 71,
                                    "side": "credit",
                                    "amount": "1000.00",
                                    "currency": "EUR",
                                    "flow_family": "income",
                                    "category_key": "salary",
                                    "subcategory_key": "employee_salary",
                                    "asset_id": None,
                                    "liability_id": None,
                                    "notes": "",
                                },
                            ],
                        }
                    ],
                },
            },
            "premium": {
                "family_members": [{"id": 50, "name": "Pablo", "role": "adult", "is_active": True}],
                "ownerships": [
                    {
                        "id": 60,
                        "kind": "individual",
                        "member": {"id": 50, "name": "Pablo", "role": "adult"},
                        "splits": [],
                    }
                ],
                "ownership_links": [{"target_type": "asset", "target_id": 20, "ownership_id": 60}],
            },
        }
        bundle.update(overrides)
        return bundle

    def test_portable_data_meta_returns_current_version(self):
        response = self.client.get("/api/core/portable-data/meta/")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["app_version"], "0.19.0")

    def test_portable_import_append_creates_all_blocks(self):
        response = self.client.post(
            "/api/core/portable-data/import/",
            {"mode": "append", "bundle": self._build_bundle()},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data["ok"])
        self.assertEqual(response.data["counts"]["assets"], 1)
        self.assertEqual(response.data["counts"]["ownership_links"], 1)
        self.assertEqual(response.data["counts"]["accounting_accounts"], 2)
        self.assertEqual(response.data["counts"]["accounting_transactions"], 1)
        self.assertEqual(Asset.objects.filter(user=self.user).count(), 1)
        self.assertEqual(Liability.objects.filter(user=self.user).count(), 1)
        self.assertEqual(LedgerAccount.objects.filter(user=self.user).count(), 2)
        self.assertEqual(LedgerTransaction.objects.filter(user=self.user).count(), 1)
        self.assertEqual(LedgerEntry.objects.filter(transaction__user=self.user).count(), 2)
        imported_asset = Asset.objects.get(user=self.user)
        self.assertEqual(imported_asset.tracking_mode, Asset.TrackingMode.ACCOUNTING)
        linked_account = LedgerAccount.objects.get(
            user=self.user, id=imported_asset.accounting_account_id
        )
        self.assertEqual(linked_account.account_type, LedgerAccount.AccountType.ASSET)
        self.assertEqual(AnnualIncomeEntry.objects.filter(user=self.user).count(), 1)
        self.assertEqual(AnnualExpenseEntry.objects.filter(user=self.user).count(), 1)
        self.assertEqual(FamilyMember.objects.filter(user=self.user).count(), 1)
        self.assertEqual(OwnershipLink.objects.filter(user=self.user).count(), 1)
        self.assertEqual(UserSettings.objects.get(user=self.user).base_currency, "USD")

    def test_portable_import_appends_net_worth_events_and_valuations(self):
        bundle = self._build_bundle()
        bundle["data"]["assets"][0]["estimated_average_balance_for_interest"] = "1200.00"
        bundle["data"]["assets"].append(
            {
                "id": 21,
                "name": "Fondo indexado",
                "category": "investments",
                "subcategory": "funds",
                "tracking_mode": "manual",
                "accounting_account_id": None,
                "currency": "EUR",
                "start_date": "2026-01-01",
                "investment_contribution_mode": "periodic_contribution",
                "investment_contribution_frequency": "monthly",
                "investment_contribution_currency": "EUR",
                "monthly_contribution_amount": "250.00",
                "contribution_intervals": [
                    {
                        "start_date": "2026-01-01",
                        "end_date": None,
                        "amount": "250.00",
                        "frequency": "monthly",
                        "currency": "EUR",
                    }
                ],
                "amount": "1000.00",
                "is_active": True,
                "notes": "",
            }
        )
        bundle["data"]["asset_valuations"] = [
            {
                "id": 1,
                "asset_ref": 21,
                "valuation_date": "2026-03-01",
                "value": "125000.00",
                "source": "manual_checkpoint",
                "note": "Checkpoint activo",
            }
        ]
        bundle["data"]["investment_events"] = [
            {
                "id": 5,
                "asset_ref": 21,
                "event_date": "2026-02-10",
                "event_type": "contribution",
                "amount": "250.00",
                "is_reinvested": True,
                "note": "",
            }
        ]
        bundle["data"]["liquidity_events"] = [
            {
                "id": 2,
                "asset_ref": 20,
                "event_date": "2026-02-01",
                "event_type": "inflow",
                "amount": "500.00",
                "note": "Aporte liquidez",
            }
        ]
        bundle["data"]["liquidity_checkins"] = [
            {
                "id": 9,
                "asset_ref": 20,
                "fiscal_year": 2026,
                "month": 3,
                "status": "confirmed",
                "closing_balance_real": "6891.16",
                "note": "Saldo real cierre mes",
            }
        ]
        bundle["data"]["liabilities"][0]["payment_start_date"] = "2026-02-01"
        bundle["data"]["liability_events"] = [
            {
                "id": 3,
                "liability_ref": 30,
                "event_date": "2026-03-01",
                "event_type": "payment",
                "amount": "600.00",
                "note": "Pago extraordinario",
            }
        ]
        bundle["data"]["liability_valuations"] = [
            {
                "id": 4,
                "liability_ref": 30,
                "valuation_date": "2026-03-01",
                "value": "79000.00",
                "source": "manual_checkpoint",
                "note": "Checkpoint pasivo",
            }
        ]

        response = self.client.post(
            "/api/core/portable-data/import/",
            {"mode": "append", "bundle": bundle},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["counts"]["asset_valuations"], 1)
        self.assertEqual(response.data["counts"]["investment_events"], 1)
        self.assertEqual(response.data["counts"]["liquidity_events"], 1)
        self.assertEqual(response.data["counts"]["liquidity_checkins"], 1)
        self.assertEqual(response.data["counts"]["liability_events"], 1)
        self.assertEqual(response.data["counts"]["liability_valuations"], 1)

        imported_investment = Asset.objects.get(user=self.user, name="Fondo indexado")
        self.assertEqual(imported_investment.contribution_intervals.count(), 1)
        self.assertEqual(AssetValuation.objects.filter(user=self.user).count(), 1)
        self.assertEqual(InvestmentAssetEvent.objects.filter(user=self.user).count(), 1)
        self.assertEqual(LiquidityAssetEvent.objects.filter(user=self.user).count(), 1)
        self.assertEqual(LiquidityMonthlyCheckin.objects.filter(user=self.user).count(), 1)
        self.assertEqual(LiabilityEvent.objects.filter(user=self.user).count(), 1)
        self.assertEqual(LiabilityValuation.objects.filter(user=self.user).count(), 1)

    def test_portable_import_rejects_clearly_invalid_payload_with_validation_error(self):
        response = self.client.post(
            "/api/core/portable-data/import/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(response.data["error"]["code"], "validation_error")

    def test_portable_import_replace_is_atomic_on_validation_error(self):
        Asset.objects.create(
            user=self.user,
            name="Cuenta previa",
            category="cash",
            subcategory="bank_account",
            currency="EUR",
            annual_interest_tae=Decimal("0.10"),
            amount=Decimal("10.00"),
            is_active=True,
        )
        invalid_bundle = self._build_bundle()
        invalid_bundle["data"]["assets"][0]["category"] = "invalid_category"

        response = self.client.post(
            "/api/core/portable-data/import/",
            {"mode": "replace", "bundle": invalid_bundle},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(response.data["error"]["code"], "validation_error")
        self.assertEqual(Asset.objects.filter(user=self.user).count(), 1)
        self.assertTrue(Asset.objects.filter(user=self.user, name="Cuenta previa").exists())

    def test_portable_import_replace_rejects_newer_bundle_version(self):
        bundle = self._build_bundle(exported_app_version="0.19.1")
        response = self.client.post(
            "/api/core/portable-data/import/",
            {"mode": "replace", "bundle": bundle},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(response.data["error"]["code"], "validation_error")
        details = response.data["error"]["details"]["bundle"]["exported_app_version"]
        self.assertIn("version mas nueva", details)

    def test_portable_import_replace_rejects_legacy_bundle_without_version(self):
        bundle = self._build_bundle()
        bundle.pop("exported_app_version")
        response = self.client.post(
            "/api/core/portable-data/import/",
            {"mode": "replace", "bundle": bundle},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(response.data["error"]["code"], "validation_error")
        details = response.data["error"]["details"]["bundle"]["exported_app_version"]
        self.assertIn("solo admite bundles con version", details)

    def test_portable_import_replace_recreates_existing_data(self):
        Asset.objects.create(
            user=self.user,
            name="Cuenta previa",
            category="cash",
            subcategory="bank_account",
            currency="EUR",
            annual_interest_tae=Decimal("0.10"),
            amount=Decimal("10.00"),
            is_active=True,
        )
        member = FamilyMember.objects.create(user=self.user, name="Viejo", role="adult")
        ownership = Ownership.objects.create(user=self.user, kind="individual", member=member)
        OwnershipLink.objects.create(
            user=self.user,
            ownership=ownership,
            target_type="asset",
            target_id=999,
        )

        response = self.client.post(
            "/api/core/portable-data/import/",
            {"mode": "replace", "bundle": self._build_bundle()},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(Asset.objects.filter(user=self.user).count(), 1)
        self.assertEqual(LedgerAccount.objects.filter(user=self.user).count(), 2)
        self.assertEqual(LedgerTransaction.objects.filter(user=self.user).count(), 1)
        self.assertFalse(Asset.objects.filter(user=self.user, name="Cuenta previa").exists())
        self.assertEqual(FamilyMember.objects.filter(user=self.user).count(), 1)
        self.assertEqual(OwnershipLink.objects.filter(user=self.user).count(), 1)

    def test_portable_import_accepts_multicurrency_investment_transaction(self):
        bundle = self._build_bundle()
        bundle["data"]["accounting"]["accounts"].append(
            {
                "id": 72,
                "name": "Broker USD",
                "account_type": "asset",
                "currency": "USD",
                "origin": "user",
                "asset_id": None,
                "liability_id": None,
                "is_active": True,
                "notes": "",
            }
        )
        bundle["data"]["accounting"]["transactions"].append(
            {
                "id": 81,
                "booking_date": "2026-02-12",
                "value_date": "2026-02-12",
                "description": "Compra ETF USD",
                "status": "posted",
                "origin": "manual",
                "notes": "",
                "ownership_id": None,
                "quick_entry_kind": "investment",
                "investment_direction": "inflow",
                "entries": [
                    {
                        "id": 92,
                        "account_id": 70,
                        "side": "credit",
                        "amount": "1.00",
                        "currency": "EUR",
                        "flow_family": "expense",
                        "category_key": "financial_investments",
                        "subcategory_key": "stocks_etf",
                        "asset_id": None,
                        "liability_id": None,
                        "notes": "",
                    },
                    {
                        "id": 93,
                        "account_id": 72,
                        "side": "debit",
                        "amount": "1.16",
                        "currency": "USD",
                        "flow_family": "expense",
                        "category_key": "financial_investments",
                        "subcategory_key": "stocks_etf",
                        "asset_id": None,
                        "liability_id": None,
                        "notes": "",
                    },
                ],
            }
        )

        response = self.client.post(
            "/api/core/portable-data/import/",
            {"mode": "append", "bundle": bundle},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["counts"]["accounting_transactions"], 2)

    def test_portable_import_accepts_multicurrency_legacy_transaction_without_kind(self):
        bundle = self._build_bundle()
        bundle["data"]["accounting"]["accounts"].append(
            {
                "id": 73,
                "name": "Broker USD legacy",
                "account_type": "asset",
                "currency": "USD",
                "origin": "user",
                "asset_id": None,
                "liability_id": None,
                "is_active": True,
                "notes": "",
            }
        )
        bundle["data"]["accounting"]["transactions"].append(
            {
                "id": 82,
                "booking_date": "2026-02-13",
                "value_date": "2026-02-13",
                "description": "Legacy FX transfer",
                "status": "posted",
                "origin": "manual",
                "notes": "",
                "ownership_id": None,
                "quick_entry_kind": "",
                "investment_direction": "",
                "entries": [
                    {
                        "id": 94,
                        "account_id": 70,
                        "side": "credit",
                        "amount": "1.00",
                        "currency": "EUR",
                        "flow_family": "",
                        "category_key": "",
                        "subcategory_key": "",
                        "asset_id": None,
                        "liability_id": None,
                        "notes": "",
                    },
                    {
                        "id": 95,
                        "account_id": 73,
                        "side": "debit",
                        "amount": "1.16",
                        "currency": "USD",
                        "flow_family": "",
                        "category_key": "",
                        "subcategory_key": "",
                        "asset_id": None,
                        "liability_id": None,
                        "notes": "",
                    },
                ],
            }
        )

        response = self.client.post(
            "/api/core/portable-data/import/",
            {"mode": "append", "bundle": bundle},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["counts"]["accounting_transactions"], 2)

    def test_portable_import_clears_partial_entry_classification(self):
        bundle = self._build_bundle()
        bundle["data"]["accounting"]["transactions"] = [
            {
                "id": 84,
                "booking_date": "2026-02-15",
                "value_date": "2026-02-15",
                "description": "Legacy partial classification",
                "status": "posted",
                "origin": "manual",
                "notes": "",
                "ownership_id": None,
                "quick_entry_kind": "",
                "investment_direction": "",
                "entries": [
                    {
                        "id": 97,
                        "account_id": 70,
                        "side": "debit",
                        "amount": "10.00",
                        "currency": "EUR",
                        "flow_family": "",
                        "category_key": "",
                        "subcategory_key": "employee_salary",
                        "asset_id": None,
                        "liability_id": None,
                        "notes": "",
                    },
                    {
                        "id": 98,
                        "account_id": 71,
                        "side": "credit",
                        "amount": "10.00",
                        "currency": "EUR",
                        "flow_family": "",
                        "category_key": "",
                        "subcategory_key": "",
                        "asset_id": None,
                        "liability_id": None,
                        "notes": "",
                    },
                ],
            }
        ]

        response = self.client.post(
            "/api/core/portable-data/import/",
            {"mode": "append", "bundle": bundle},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        transaction = LedgerTransaction.objects.get(
            user=self.user, description="Legacy partial classification"
        )
        rows = list(transaction.entries.all().order_by("id"))
        self.assertEqual(rows[0].flow_family, "")
        self.assertEqual(rows[0].category_key, "")
        self.assertEqual(rows[0].subcategory_key, "")

    def test_portable_import_autobalances_legacy_multicurrency_entries(self):
        bundle = self._build_bundle()
        bundle["data"]["accounting"]["accounts"].append(
            {
                "id": 74,
                "name": "Wallet ETH",
                "account_type": "asset",
                "currency": "ETH",
                "origin": "user",
                "asset_id": None,
                "liability_id": None,
                "is_active": True,
                "notes": "",
            }
        )
        bundle["data"]["accounting"]["transactions"] = [
            {
                "id": 85,
                "booking_date": "2026-02-16",
                "value_date": "2026-02-16",
                "description": "Legacy unbalanced by currency",
                "status": "posted",
                "origin": "manual",
                "notes": "",
                "ownership_id": None,
                "quick_entry_kind": "",
                "investment_direction": "",
                "entries": [
                    {
                        "id": 99,
                        "account_id": 74,
                        "side": "debit",
                        "amount": "8.75000000",
                        "currency": "ETH",
                        "flow_family": "",
                        "category_key": "",
                        "subcategory_key": "",
                        "asset_id": None,
                        "liability_id": None,
                        "notes": "",
                    },
                    {
                        "id": 100,
                        "account_id": 71,
                        "side": "credit",
                        "amount": "15000.00",
                        "currency": "EUR",
                        "flow_family": "",
                        "category_key": "",
                        "subcategory_key": "",
                        "asset_id": None,
                        "liability_id": None,
                        "notes": "",
                    },
                ],
            }
        ]

        response = self.client.post(
            "/api/core/portable-data/import/",
            {"mode": "append", "bundle": bundle},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        transaction = LedgerTransaction.objects.get(
            user=self.user, description="Legacy unbalanced by currency"
        )
        entries = list(transaction.entries.all())
        self.assertEqual(len(entries), 4)
        self.assertEqual(
            sum(1 for row in entries if "balancear la transaccion por moneda" in str(row.notes)),
            2,
        )

    def test_portable_import_ignores_legacy_improvement_ids(self):
        bundle = self._build_bundle()
        bundle["data"]["assets"] = [
            {
                "id": 20,
                "name": "Casa reformada",
                "category": "real_estate",
                "subcategory": "primary_home",
                "tracking_mode": "manual",
                "accounting_account_id": None,
                "currency": "EUR",
                "start_date": "2026-01-01",
                "amount": "100000.00",
                "valuation_model": "real_estate_auto",
                "land_value_share_percent": "30.00",
                "land_annual_appreciation_percent": "4.000",
                "building_annual_depreciation_percent": "1.00",
                "improvements": [
                    {
                        "id": 2,
                        "name": "Reforma cocina",
                        "reform_date": "2026-06-01",
                        "amount": "15000.00",
                        "amortization_method": "straight_line",
                        "amortization_term_years": 15,
                    }
                ],
                "is_active": True,
                "notes": "",
            }
        ]

        response = self.client.post(
            "/api/core/portable-data/import/",
            {"mode": "append", "bundle": bundle},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        asset = Asset.objects.get(user=self.user, name="Casa reformada")
        self.assertEqual(asset.improvements.count(), 1)
        self.assertEqual(asset.improvements.first().name, "Reforma cocina")

    def test_portable_import_autocompletes_single_entry_transaction(self):
        bundle = self._build_bundle()
        bundle["data"]["accounting"]["transactions"] = [
            {
                "id": 83,
                "booking_date": "2026-02-14",
                "value_date": "2026-02-14",
                "description": "Legacy single entry row",
                "status": "posted",
                "origin": "manual",
                "notes": "",
                "ownership_id": None,
                "quick_entry_kind": "",
                "investment_direction": "",
                "entries": [
                    {
                        "id": 96,
                        "account_id": 70,
                        "side": "debit",
                        "amount": "10.00",
                        "currency": "EUR",
                        "flow_family": "",
                        "category_key": "",
                        "subcategory_key": "",
                        "asset_id": None,
                        "liability_id": None,
                        "notes": "",
                    }
                ],
            }
        ]

        response = self.client.post(
            "/api/core/portable-data/import/",
            {"mode": "append", "bundle": bundle},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        transaction = LedgerTransaction.objects.get(
            user=self.user, description="Legacy single entry row"
        )
        self.assertEqual(transaction.entries.count(), 2)

    def test_portable_import_remaps_opening_balance_note_for_accounting_liabilities(self):
        bundle = self._build_bundle()
        bundle["data"]["liabilities"][0]["tracking_mode"] = "accounting"
        bundle["data"]["liabilities"][0]["accounting_account_id"] = 72
        bundle["data"]["accounting"]["accounts"].extend(
            [
                {
                    "id": 72,
                    "name": "Tarjeta Kutxa",
                    "account_type": "liability",
                    "currency": "EUR",
                    "origin": "user",
                    "asset_id": None,
                    "liability_id": 30,
                    "is_active": True,
                    "notes": "",
                },
                {
                    "id": 73,
                    "name": "Patrimonio neto test",
                    "account_type": "equity",
                    "currency": "EUR",
                    "origin": "system",
                    "asset_id": None,
                    "liability_id": None,
                    "is_active": True,
                    "notes": "",
                },
            ]
        )
        bundle["data"]["accounting"]["transactions"] = [
            {
                "id": 1001,
                "booking_date": "2025-12-31",
                "value_date": "2025-12-31",
                "description": "Movimiento previo",
                "status": "posted",
                "origin": "manual",
                "notes": "",
                "ownership_id": None,
                "quick_entry_kind": "transfer",
                "investment_direction": "",
                "entries": [
                    {
                        "account_id": 73,
                        "side": "debit",
                        "amount": "500.00",
                        "currency": "EUR",
                        "flow_family": "",
                        "category_key": "",
                        "subcategory_key": "",
                        "asset_id": None,
                        "liability_id": None,
                        "notes": "",
                    },
                    {
                        "account_id": 72,
                        "side": "credit",
                        "amount": "500.00",
                        "currency": "EUR",
                        "flow_family": "",
                        "category_key": "",
                        "subcategory_key": "",
                        "asset_id": None,
                        "liability_id": 30,
                        "notes": "",
                    },
                ],
            },
            {
                "id": 1002,
                "booking_date": "2026-01-01",
                "value_date": "2026-01-01",
                "description": "Saldo inicial Tarjeta",
                "status": "posted",
                "origin": "system",
                "notes": "net_worth_opening_balance:liability:30",
                "ownership_id": None,
                "quick_entry_kind": "",
                "investment_direction": "",
                "entries": [
                    {
                        "account_id": 73,
                        "side": "debit",
                        "amount": "1000.00",
                        "currency": "EUR",
                        "flow_family": "",
                        "category_key": "",
                        "subcategory_key": "",
                        "asset_id": None,
                        "liability_id": None,
                        "notes": "",
                    },
                    {
                        "account_id": 72,
                        "side": "credit",
                        "amount": "1000.00",
                        "currency": "EUR",
                        "flow_family": "",
                        "category_key": "",
                        "subcategory_key": "",
                        "asset_id": None,
                        "liability_id": 30,
                        "notes": "",
                    },
                ],
            },
        ]

        response = self.client.post(
            "/api/core/portable-data/import/",
            {"mode": "append", "bundle": bundle},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        imported_liability = Liability.objects.get(user=self.user, name="Hipoteca")
        opening_tx = LedgerTransaction.objects.get(
            user=self.user, description="Saldo inicial Tarjeta"
        )
        self.assertEqual(
            opening_tx.notes,
            f"net_worth_opening_balance:liability:{imported_liability.id}",
        )
        self.assertEqual(
            get_effective_liability_amount(liability=imported_liability),
            Decimal("1000.00"),
        )

    def test_portable_import_remaps_opening_balance_note_for_accounting_assets(self):
        bundle = self._build_bundle()
        bundle["data"]["assets"][0]["tracking_mode"] = "accounting"
        bundle["data"]["assets"][0]["accounting_account_id"] = 70
        bundle["data"]["accounting"]["transactions"] = [
            {
                "id": 1101,
                "booking_date": "2025-12-31",
                "value_date": "2025-12-31",
                "description": "Movimiento previo Kutxa",
                "status": "posted",
                "origin": "manual",
                "notes": "",
                "ownership_id": None,
                "quick_entry_kind": "transfer",
                "investment_direction": "",
                "entries": [
                    {
                        "account_id": 70,
                        "side": "debit",
                        "amount": "500.00",
                        "currency": "EUR",
                        "flow_family": "",
                        "category_key": "",
                        "subcategory_key": "",
                        "asset_id": 20,
                        "liability_id": None,
                        "notes": "",
                    },
                    {
                        "account_id": 71,
                        "side": "credit",
                        "amount": "500.00",
                        "currency": "EUR",
                        "flow_family": "",
                        "category_key": "",
                        "subcategory_key": "",
                        "asset_id": None,
                        "liability_id": None,
                        "notes": "",
                    },
                ],
            },
            {
                "id": 1102,
                "booking_date": "2026-01-01",
                "value_date": "2026-01-01",
                "description": "Saldo inicial Kutxa",
                "status": "posted",
                "origin": "system",
                "notes": "net_worth_opening_balance:asset:20",
                "ownership_id": None,
                "quick_entry_kind": "",
                "investment_direction": "",
                "entries": [
                    {
                        "account_id": 70,
                        "side": "debit",
                        "amount": "1000.00",
                        "currency": "EUR",
                        "flow_family": "",
                        "category_key": "",
                        "subcategory_key": "",
                        "asset_id": 20,
                        "liability_id": None,
                        "notes": "",
                    },
                    {
                        "account_id": 71,
                        "side": "credit",
                        "amount": "1000.00",
                        "currency": "EUR",
                        "flow_family": "",
                        "category_key": "",
                        "subcategory_key": "",
                        "asset_id": None,
                        "liability_id": None,
                        "notes": "",
                    },
                ],
            },
        ]

        response = self.client.post(
            "/api/core/portable-data/import/",
            {"mode": "append", "bundle": bundle},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        imported_asset = Asset.objects.get(user=self.user, name="Cuenta")
        opening_tx = LedgerTransaction.objects.get(
            user=self.user, description="Saldo inicial Kutxa"
        )
        self.assertEqual(
            opening_tx.notes,
            f"net_worth_opening_balance:asset:{imported_asset.id}",
        )
        self.assertEqual(get_effective_asset_amount(asset=imported_asset), Decimal("1000.00"))


class CoreApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="core_api_user",
            password="pass1234",
        )
        self.admin_user = get_user_model().objects.create_user(
            username="core_api_admin",
            password="pass1234",
            is_staff=True,
        )

    def test_fx_rates_requires_auth_with_canonical_error_shape(self):
        response = self.client.get("/api/core/fx-rates/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"]["code"], "unauthorized")
        self.assertIn("message", response.data["error"])
        self.assertIn("details", response.data["error"])

    def test_fx_refresh_requires_auth_with_canonical_error_shape(self):
        response = self.client.post(
            "/api/core/fx/refresh/", {"from": "USD", "to": "EUR"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"]["code"], "unauthorized")

    @patch("core.views.refresh_currency_rate")
    def test_fx_refresh_updates_one_current_pair(self, refresh_mock):
        self.client.force_authenticate(user=self.user)
        refresh_mock.return_value = FxConversion(
            amount=Decimal("1"),
            from_currency="USD",
            to_currency="EUR",
            converted=Decimal("0.91000000"),
            rate=Decimal("0.91"),
            rate_date=date(2026, 8, 14),
            resolution="exact",
        )

        response = self.client.post(
            "/api/core/fx/refresh/", {"from": "usd", "to": "eur"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        refresh_mock.assert_called_once_with("usd", "eur")
        self.assertEqual(response.data["rate"], "0.91")
        self.assertEqual(response.data["rate_date"], "2026-08-14")

    def test_inflation_requires_auth_with_canonical_error_shape(self):
        response = self.client.get("/api/core/inflation/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"]["code"], "unauthorized")
        self.assertIn("message", response.data["error"])
        self.assertIn("details", response.data["error"])

    def test_market_data_status_requires_auth_with_canonical_error_shape(self):
        response = self.client.get("/api/core/market-data/status/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"]["code"], "unauthorized")

    def test_market_data_status_returns_empty_states_when_no_sync_state_exists(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/core/market-data/status/")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIn("datasets", response.data)
        self.assertEqual(response.data["datasets"]["fx"]["states"], [])
        self.assertEqual(response.data["datasets"]["inflation"]["states"], [])

    def test_fx_rates_create_and_list(self):
        self.client.force_authenticate(user=self.admin_user)
        create_response = self.client.post(
            "/api/core/fx-rates/",
            {
                "rate_date": "2026-02-01",
                "from_currency": "usd",
                "to_currency": "eur",
                "rate": "0.90",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED, create_response.data)
        self.assertEqual(create_response.data["from_currency"], "USD")
        self.assertEqual(create_response.data["to_currency"], "EUR")

        list_response = self.client.get("/api/core/fx-rates/")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data["results"]), 1)

    def test_fx_rates_rejects_invalid_currency_with_canonical_error_shape(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            "/api/core/fx-rates/",
            {
                "rate_date": "2026-02-01",
                "from_currency": "EU",
                "to_currency": "USD",
                "rate": "1.10",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(response.data["error"]["code"], "validation_error")
        self.assertIn("non_field_errors", response.data["error"]["details"])

    def test_inflation_rejects_non_month_start_period_with_canonical_error_shape(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            "/api/core/inflation/",
            {
                "region": "ES",
                "period": "2026-02-02",
                "index": "101.1234",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(response.data["error"]["code"], "validation_error")
        self.assertIn("period", response.data["error"]["details"])

    def test_market_data_status_returns_supported_regions_and_states(self):
        self.client.force_authenticate(user=self.user)
        MarketDataSyncState.objects.create(dataset="fx", scope="USD->EUR")

        response = self.client.get("/api/core/market-data/status/")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIn("supported_inflation_regions", response.data)
        self.assertIn("datasets", response.data)
        self.assertEqual(response.data["datasets"]["fx"]["states"][0]["scope"], "USD->EUR")

    def test_market_data_sync_requires_admin_permissions(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/core/market-data/sync/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["error"]["code"], "forbidden")

    @patch("core.views.sync_market_data", return_value={"inflation": 42})
    def test_market_data_sync_runs_manual_inflation_sync(self, sync_mock):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post("/api/core/market-data/sync/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        sync_mock.assert_called_once_with(
            datasets=["inflation"], mode="reconcile", fx_history_floor_years=5
        )
        self.assertEqual(response.data["summary"]["inflation"], 42)

    @patch("core.views.sync_market_data", side_effect=MarketDataSyncError("boom"))
    def test_market_data_sync_maps_provider_failures(self, sync_mock):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post("/api/core/market-data/sync/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY, response.data)
        sync_mock.assert_called_once_with(
            datasets=["inflation"], mode="reconcile", fx_history_floor_years=5
        )
        self.assertEqual(response.data["detail"], "boom")

    @patch("core.views.sync_market_data", return_value={"fx": 100})
    def test_market_data_sync_supports_full_fx_history_mode(self, sync_mock):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            "/api/core/market-data/sync/",
            {"datasets": ["fx"], "mode": "reconcile", "fx_full_history": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        sync_mock.assert_called_once_with(
            datasets=["fx"], mode="reconcile", fx_history_floor_years=None
        )
        self.assertEqual(response.data["summary"]["fx"], 100)
