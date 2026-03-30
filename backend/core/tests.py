from datetime import date
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
from net_worth.models import Asset, Liability
from .services import (
    _get_inflation_index,
    _normalize_month_start,
    adjust_for_inflation,
    convert_currency,
    get_latest_inflation_period,
    normalize_currency_code,
    validate_fx_currency_pair,
    validate_inflation_period_start,
)
from .market_data import (
    MarketDataSyncError,
    ensure_market_history,
    sync_inflation_history,
    sync_market_data,
    sync_market_history,
)


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
        fetch_json_mock.side_effect = [
            {
                "amount": 1.0,
                "base": "USD",
                "rates": {
                    "2025-03-03": {"EUR": 0.92},
                },
            },
            [
                {
                    "Nombre": "Total Nacional. Indice general. Indice.",
                    "MetaData": [{"T3_Variable": "Totales Territoriales", "Nombre": "Nacional"}],
                    "Data": [{"Fecha": "2025-03-01T00:00:00.000+01:00", "Valor": 99.024}],
                }
            ],
        ]
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
        self.assertEqual(fx_state.required_start_date, date(2025, 3, 3))
        self.assertEqual(fx_state.covered_until, date(2025, 3, 3))
        inflation_state = MarketDataSyncState.objects.get(dataset="inflation", scope="ES")
        self.assertEqual(inflation_state.required_start_date, date(2025, 3, 1))


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
                                    "annual_income_entry_id": 10,
                                    "annual_expense_entry_id": None,
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
                                    "annual_income_entry_id": None,
                                    "annual_expense_entry_id": None,
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
        linked_account = LedgerAccount.objects.get(user=self.user, id=imported_asset.accounting_account_id)
        self.assertEqual(linked_account.account_type, LedgerAccount.AccountType.ASSET)
        self.assertEqual(AnnualIncomeEntry.objects.filter(user=self.user).count(), 1)
        self.assertEqual(AnnualExpenseEntry.objects.filter(user=self.user).count(), 1)
        self.assertEqual(FamilyMember.objects.filter(user=self.user).count(), 1)
        self.assertEqual(OwnershipLink.objects.filter(user=self.user).count(), 1)
        self.assertEqual(UserSettings.objects.get(user=self.user).base_currency, "USD")

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


class CoreApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="core_api_user",
            password="pass1234",
        )

    def test_fx_rates_requires_auth_with_canonical_error_shape(self):
        response = self.client.get("/api/core/fx-rates/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"]["code"], "unauthorized")
        self.assertIn("message", response.data["error"])
        self.assertIn("details", response.data["error"])

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
        self.client.force_authenticate(user=self.user)
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
        self.assertEqual(len(list_response.data), 1)

    def test_fx_rates_rejects_invalid_currency_with_canonical_error_shape(self):
        self.client.force_authenticate(user=self.user)
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
        self.client.force_authenticate(user=self.user)
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
