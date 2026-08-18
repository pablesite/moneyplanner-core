from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from core.market_data import sync_market_data
from core.models import MarketDataSyncState
from memberships.models import FamilyMember, Ownership, OwnershipLink
from net_worth.models import Asset, AssetValuation, InvestmentAssetEvent
from portfolio.models import (
    Instrument,
    InstrumentPrice,
    InstrumentProviderMapping,
    Portfolio,
    PortfolioMigrationIssue,
    PortfolioPosition,
    PositionValuation,
    PositionOwnershipPeriod,
    PositionOwnershipShare,
)
from portfolio.services import bootstrap_portfolio_for_user, build_portfolio_readiness
from portfolio.valuations import (
    build_valuation_health,
    import_legacy_position_valuations,
    resolve_position_valuation,
)


class PortfolioBootstrapTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="portfolio_bootstrap", password="pass1234"
        )
        self.member = FamilyMember.objects.create(user=self.user, name="Pablo")
        self.ownership = Ownership.objects.create(
            user=self.user,
            kind=Ownership.Kind.INDIVIDUAL,
            member=self.member,
        )

    def create_asset(
        self,
        *,
        name: str,
        currency: str = "EUR",
        subcategory: str = Asset.Subcategory.FUNDS,
        is_active: bool = True,
        with_ownership: bool = True,
    ) -> Asset:
        asset = Asset.objects.create(
            user=self.user,
            name=name,
            category=Asset.Category.INVESTMENTS,
            subcategory=subcategory,
            currency=currency,
            amount=Decimal("1000"),
            start_date=date(2020, 1, 1),
            is_active=is_active,
        )
        if with_ownership:
            OwnershipLink.objects.create(
                user=self.user,
                ownership=self.ownership,
                target_type=OwnershipLink.TargetType.ASSET,
                target_id=asset.id,
            )
        return asset

    def test_bootstrap_is_idempotent_and_includes_archived_assets(self):
        active = self.create_asset(name="Fondo activo")
        archived = self.create_asset(name="Fondo cerrado", is_active=False)
        for asset in (active, archived):
            LedgerAccount.objects.create(
                user=self.user,
                name=asset.name,
                account_type=LedgerAccount.AccountType.ASSET,
                currency=asset.currency,
                asset=asset,
            )

        first = bootstrap_portfolio_for_user(user=self.user)
        second = bootstrap_portfolio_for_user(user=self.user)

        self.assertEqual(first.created_positions, 2)
        self.assertEqual(second.created_positions, 0)
        self.assertEqual(second.existing_positions, 2)
        self.assertEqual(Portfolio.objects.filter(user=self.user).count(), 1)
        self.assertEqual(PortfolioPosition.objects.filter(portfolio__user=self.user).count(), 2)
        self.assertEqual(Instrument.objects.filter(user=self.user).count(), 2)
        self.assertEqual(
            PortfolioPosition.objects.get(asset=archived).status,
            PortfolioPosition.Status.ARCHIVED,
        )
        period = PositionOwnershipPeriod.objects.get(position__asset=active)
        share = PositionOwnershipShare.objects.get(period=period)
        self.assertEqual(share.member, self.member)
        self.assertEqual(share.percent, Decimal("100"))

    def test_bootstrap_only_classifies_unambiguous_crypto_units(self):
        crypto_units = self.create_asset(
            name="Bitcoin",
            currency="BTC",
            subcategory=Asset.Subcategory.CRYPTOCURRENCIES,
        )
        crypto_valued = self.create_asset(
            name="Cesta crypto EUR",
            currency="EUR",
            subcategory=Asset.Subcategory.CRYPTOCURRENCIES,
        )

        bootstrap_portfolio_for_user(user=self.user)

        self.assertEqual(
            PortfolioPosition.objects.get(asset=crypto_units).tracking_style,
            PortfolioPosition.TrackingStyle.UNITS_BASED,
        )
        self.assertEqual(
            PortfolioPosition.objects.get(asset=crypto_valued).tracking_style,
            PortfolioPosition.TrackingStyle.VALUE_BASED,
        )
        units_position = PortfolioPosition.objects.get(asset=crypto_units)
        self.assertEqual(units_position.instrument.identity_kind, Instrument.IdentityKind.CANONICAL)
        mapping = units_position.instrument.provider_mappings.get()
        self.assertTrue(mapping.is_confirmed)
        self.assertEqual(mapping.provider_symbol, "bitcoin")
        self.assertEqual(mapping.quote_currency, "EUR")

    def test_bootstrap_imports_legacy_valuations_without_modifying_source(self):
        asset = self.create_asset(name="Fondo histórico")
        legacy = AssetValuation.objects.create(
            user=self.user,
            asset=asset,
            valuation_date=date(2024, 12, 31),
            value=Decimal("1234.56"),
        )

        bootstrap_portfolio_for_user(user=self.user)
        bootstrap_portfolio_for_user(user=self.user)

        derived = PositionValuation.objects.get(legacy_asset_valuation=legacy)
        self.assertEqual(derived.source, PositionValuation.Source.LEGACY_ASSET)
        self.assertEqual(derived.value, Decimal("1234.56"))
        self.assertEqual(PositionValuation.objects.filter(legacy_asset_valuation=legacy).count(), 1)
        legacy.refresh_from_db()
        self.assertEqual(legacy.value, Decimal("1234.56"))

    def test_ambiguous_ledger_is_not_linked_and_is_reported(self):
        asset = self.create_asset(name="Broker duplicado")
        for suffix in ("A", "B"):
            LedgerAccount.objects.create(
                user=self.user,
                name=f"Broker {suffix}",
                account_type=LedgerAccount.AccountType.ASSET,
                currency="EUR",
                asset=asset,
            )

        bootstrap_portfolio_for_user(user=self.user)

        self.assertIsNone(PortfolioPosition.objects.get(asset=asset).ledger_account_id)
        self.assertTrue(
            PortfolioMigrationIssue.objects.filter(
                asset=asset,
                code=PortfolioMigrationIssue.Code.LEDGER_ACCOUNT_AMBIGUOUS,
                status=PortfolioMigrationIssue.Status.OPEN,
            ).exists()
        )
        readiness = build_portfolio_readiness(user=self.user)
        self.assertEqual(readiness["covered_asset_count"], 1)
        self.assertEqual(readiness["uncovered_asset_ids"], [])
        self.assertEqual(readiness["status"], "needs_review")

    def test_performance_and_detail_coverage_are_independent(self):
        asset = self.create_asset(
            name="Ethereum",
            currency="ETH",
            subcategory=Asset.Subcategory.CRYPTOCURRENCIES,
        )
        account = LedgerAccount.objects.create(
            user=self.user,
            name="Ethereum",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="ETH",
            asset=asset,
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2021, 2, 1),
            value_date=date(2021, 2, 1),
            description="Compra ETH",
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=account,
            asset=asset,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1"),
            currency="ETH",
        )
        AssetValuation.objects.create(
            user=self.user,
            asset=asset,
            valuation_date=date(2021, 3, 1),
            value=Decimal("1500"),
        )
        InvestmentAssetEvent.objects.create(
            user=self.user,
            asset=asset,
            event_date=date(2021, 1, 1),
            event_type=InvestmentAssetEvent.EventType.CONTRIBUTION,
            amount=Decimal("1000"),
        )

        bootstrap_portfolio_for_user(user=self.user)
        row = build_portfolio_readiness(user=self.user)["positions"][0]

        self.assertEqual(row["performance_coverage"]["status"], "complete")
        self.assertEqual(row["performance_coverage"]["start_date"], "2021-01-01")
        self.assertEqual(row["position_detail_coverage"]["status"], "complete")
        self.assertEqual(row["position_detail_coverage"]["start_date"], "2021-02-01")

    def test_historical_ownership_rows_only_admit_closing_the_stretch(self):
        # Cerrar un tramo abierto no es reescribir la historia sino terminar de
        # registrarla, y es lo que ocurre cuando algo deja de ser compartido. Cambiar el
        # resto sigue prohibido, porque de la titularidad pasada dependen las cifras.
        asset = self.create_asset(name="Fondo")
        bootstrap_portfolio_for_user(user=self.user)
        period = PositionOwnershipPeriod.objects.get(position__asset=asset)
        share = PositionOwnershipShare.objects.get(period=period)

        period.end_date = date(2024, 1, 1)
        period.full_clean()
        period.save(update_fields=["end_date"])

        period.refresh_from_db()
        self.assertEqual(period.end_date, date(2024, 1, 1))

        period.start_date = date(2019, 6, 1)
        with self.assertRaises(ValidationError):
            period.full_clean()
        with self.assertRaises(ValidationError):
            share.delete()

    def test_commodities_are_rescued_from_the_real_assets_drawer_by_name(self):
        # `real_assets` metía inmobiliario y materias primas en el mismo cajón, y al
        # deshacerlo todo fue a inmobiliario: por tipo de instrumento un ETF de oro y uno
        # de REITs son iguales. El nombre sí los separa, pero el patrón tiene que ser
        # estrecho o se lleva por delante cualquier "Goldman".
        from importlib import import_module

        from django.apps import apps as live_apps

        cases = {
            "ETF - Physical Gold USD (Acc)": Instrument.AssetClass.OTHER,
            "Fondo - ING PIMCO GIS Commodity": Instrument.AssetClass.REAL_ESTATE,
            "Fondo Oro Físico": Instrument.AssetClass.OTHER,
            "Goldman Sachs Real Estate": Instrument.AssetClass.REAL_ESTATE,
            "ETF - REIT Real Global Real State": Instrument.AssetClass.REAL_ESTATE,
            "ETF - Water": Instrument.AssetClass.EQUITY,
        }
        for name, asset_class in cases.items():
            Instrument.objects.create(
                user=self.user,
                name=name,
                identity_kind=Instrument.IdentityKind.CUSTOM,
                asset_class=asset_class,
                instrument_type=Instrument.InstrumentType.ETF,
                quote_currency="EUR",
            )

        migration = import_module("portfolio.migrations.0015_reclassify_commodities_from_name")
        migration.forwards(live_apps, None)

        moved = {name: Instrument.objects.get(name=name).asset_class for name in cases}
        self.assertEqual(moved["ETF - Physical Gold USD (Acc)"], "commodities")
        self.assertEqual(moved["Fondo - ING PIMCO GIS Commodity"], "commodities")
        self.assertEqual(moved["Fondo Oro Físico"], "commodities")
        # "Goldman" no es oro, y un REIT sigue siendo inmobiliario.
        self.assertEqual(moved["Goldman Sachs Real Estate"], "real_estate")
        self.assertEqual(moved["ETF - REIT Real Global Real State"], "real_estate")
        self.assertEqual(moved["ETF - Water"], "equity")

    def test_canonical_instrument_requires_confirmed_identity(self):
        instrument = Instrument(
            identity_kind=Instrument.IdentityKind.CANONICAL,
            name="Instrumento sin confirmar",
            asset_class=Instrument.AssetClass.OTHER,
            instrument_type=Instrument.InstrumentType.FUND,
            quote_currency="EUR",
        )

        with self.assertRaises(ValidationError):
            instrument.full_clean()


class PortfolioApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="portfolio_api", password="pass1234"
        )
        self.other_user = get_user_model().objects.create_user(
            username="portfolio_other", password="pass1234"
        )
        self.client.force_authenticate(user=self.user)

    def create_investment(self, *, user, name: str) -> Asset:
        return Asset.objects.create(
            user=user,
            name=name,
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=Decimal("100"),
        )

    def test_bootstrap_and_readiness_are_user_scoped(self):
        own_asset = self.create_investment(user=self.user, name="Propio")
        other_asset = self.create_investment(user=self.other_user, name="Ajeno")

        response = self.client.post("/api/portfolio/bootstrap/", format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(PortfolioPosition.objects.filter(asset=own_asset).exists())
        self.assertFalse(PortfolioPosition.objects.filter(asset=other_asset).exists())

        readiness = self.client.get("/api/portfolio/readiness/")
        self.assertEqual(readiness.status_code, status.HTTP_200_OK, readiness.data)
        self.assertEqual(readiness.data["asset_count"], 1)
        self.assertEqual(readiness.data["covered_asset_count"], 1)

    def test_position_create_rejects_cross_user_asset(self):
        bootstrap_portfolio_for_user(user=self.user)
        other_asset = self.create_investment(user=self.other_user, name="Ajeno")
        portfolio = Portfolio.objects.get(user=self.user)
        container = portfolio.containers.get()
        instrument = Instrument.objects.create(
            user=self.user,
            identity_kind=Instrument.IdentityKind.CUSTOM,
            name="Manual",
            asset_class=Instrument.AssetClass.PRIVATE_EQUITY,
            instrument_type=Instrument.InstrumentType.FUND,
            quote_currency="EUR",
        )

        response = self.client.post(
            "/api/portfolio/positions/",
            {
                "container_id": container.id,
                "instrument_id": instrument.id,
                "asset_id": other_asset.id,
                "tracking_style": PortfolioPosition.TrackingStyle.VALUE_BASED,
                "status": PortfolioPosition.Status.ACTIVE,
                "opened_on": "2026-01-01",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)

    def test_lists_never_expose_another_users_records(self):
        self.create_investment(user=self.user, name="Propio")
        self.create_investment(user=self.other_user, name="Ajeno")
        bootstrap_portfolio_for_user(user=self.user)
        bootstrap_portfolio_for_user(user=self.other_user)

        positions = self.client.get("/api/portfolio/positions/")
        instruments = self.client.get("/api/portfolio/instruments/")

        self.assertEqual(positions.status_code, status.HTTP_200_OK, positions.data)
        self.assertEqual(instruments.status_code, status.HTTP_200_OK, instruments.data)
        self.assertEqual(len(positions.data), 1)
        self.assertEqual(len(instruments.data), 1)

    def test_manual_valuation_create_and_health_are_user_scoped(self):
        asset = self.create_investment(user=self.user, name="Fondo manual")
        other_asset = self.create_investment(user=self.other_user, name="Fondo ajeno")
        bootstrap_portfolio_for_user(user=self.user)
        bootstrap_portfolio_for_user(user=self.other_user)
        position = PortfolioPosition.objects.get(asset=asset)
        other_position = PortfolioPosition.objects.get(asset=other_asset)

        response = self.client.post(
            "/api/portfolio/valuations/",
            {
                "position_id": position.id,
                "valuation_date": timezone.localdate().isoformat(),
                "value": "250.00",
                "currency": "EUR",
                "note": "Cierre manual",
            },
            format="json",
        )
        cross_user = self.client.post(
            "/api/portfolio/valuations/",
            {
                "position_id": other_position.id,
                "valuation_date": timezone.localdate().isoformat(),
                "value": "999.00",
                "currency": "EUR",
            },
            format="json",
        )
        health = self.client.get("/api/portfolio/valuation-health/")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["source"], PositionValuation.Source.MANUAL)
        self.assertEqual(cross_user.status_code, status.HTTP_400_BAD_REQUEST, cross_user.data)
        self.assertEqual(health.status_code, status.HTTP_200_OK, health.data)
        self.assertEqual(health.data["position_count"], 1)
        self.assertEqual(health.data["counts"]["fresh"], 1)


class PortfolioValuationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="portfolio_valuation", password="pass1234"
        )
        asset = Asset.objects.create(
            user=self.user,
            name="Bitcoin",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.CRYPTOCURRENCIES,
            currency="BTC",
            amount=Decimal("2"),
            start_date=date(2025, 1, 1),
        )
        self.account = LedgerAccount.objects.create(
            user=self.user,
            name="Bitcoin",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="BTC",
            asset=asset,
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2025, 1, 1),
            value_date=date(2025, 1, 1),
            description="Compra BTC",
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.account,
            asset=asset,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("2"),
            currency="BTC",
        )
        bootstrap_portfolio_for_user(user=self.user)
        self.position = PortfolioPosition.objects.select_related(
            "portfolio", "asset", "instrument", "ledger_account"
        ).get(asset=asset)
        self.mapping = InstrumentProviderMapping.objects.get(instrument=self.position.instrument)

    def create_price(self, *, on_date: date, close: str = "50000") -> InstrumentPrice:
        return InstrumentPrice.objects.create(
            instrument=self.position.instrument,
            provider_mapping=self.mapping,
            price_date=on_date,
            close=Decimal(close),
            currency="EUR",
            source="coingecko",
            source_key="bitcoin",
            fetched_at=timezone.now(),
        )

    def test_units_position_uses_ledger_units_times_confirmed_close(self):
        self.create_price(on_date=date(2025, 1, 3))

        result = resolve_position_valuation(
            position=self.position,
            as_of_date=date(2025, 1, 3),
        )

        self.assertEqual(result["value"], "100000.00000000000000000000")
        self.assertEqual(result["provenance"]["calculation"], "ledger_units_x_close")
        self.assertEqual(result["provenance"]["source"], "coingecko")

    def test_newer_manual_total_is_safe_fallback(self):
        self.create_price(on_date=date(2025, 1, 2))
        PositionValuation.objects.create(
            position=self.position,
            valuation_date=date(2025, 1, 4),
            value=Decimal("110000"),
            currency="EUR",
            source=PositionValuation.Source.MANUAL,
        )

        result = resolve_position_valuation(
            position=self.position,
            as_of_date=date(2025, 1, 4),
        )

        self.assertEqual(result["value"], "110000.00000000")
        self.assertEqual(result["provenance"]["kind"], "total_valuation")
        self.assertEqual(result["provenance"]["source"], "manual")

    def test_ledger_revaluation_is_imported_from_transaction_order_without_mutation(self):
        revaluation = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2025, 1, 2),
            value_date=date(2025, 1, 2),
            description="Revalorización BTC",
            quick_entry_kind=LedgerTransaction.QuickEntryKind.REVALUATION,
        )
        entry = LedgerEntry.objects.create(
            transaction=revaluation,
            account=self.account,
            asset=self.position.asset,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1"),
            currency="BTC",
        )

        import_legacy_position_valuations(position=self.position)
        derived = PositionValuation.objects.get(
            position=self.position,
            source=PositionValuation.Source.LEGACY_LEDGER,
        )

        self.assertEqual(derived.value, Decimal("3"))
        self.assertEqual(derived.legacy_ledger_transaction, revaluation)
        entry.refresh_from_db()
        self.assertEqual(entry.amount, Decimal("1"))

    def test_health_marks_old_values_stale_and_missing_prices_explicitly(self):
        self.create_price(on_date=date(2025, 1, 1))

        with patch("portfolio.valuations.timezone.localdate", return_value=date(2025, 1, 10)):
            health = build_valuation_health(user=self.user)

        self.assertEqual(health["counts"]["stale"], 1)
        self.assertEqual(health["positions"][0]["valuation"]["stale_after_days"], 3)

    @patch("portfolio.market_data.fetch_crypto_daily_closes")
    def test_provider_failure_does_not_delete_last_valid_price(self, fetch_mock):
        from core.market_data import MarketDataSyncError
        from portfolio.market_data import sync_instrument_mapping

        existing = self.create_price(on_date=date(2025, 1, 2))
        fetch_mock.side_effect = MarketDataSyncError("provider down")

        with self.assertRaises(MarketDataSyncError):
            sync_instrument_mapping(
                mapping=self.mapping,
                start_date=date(2025, 1, 3),
                end_date=date(2025, 1, 4),
            )

        self.assertTrue(InstrumentPrice.objects.filter(id=existing.id).exists())

    @patch("portfolio.market_data.fetch_crypto_daily_closes")
    def test_market_data_registry_syncs_confirmed_instrument_mapping(self, fetch_mock):
        today = timezone.localdate()
        fetch_mock.return_value = ("coingecko", [(today, Decimal("60000"))])

        summary = sync_market_data(datasets=["instrument_prices"], mode="reconcile")

        self.assertEqual(summary["instrument_prices"], 1)
        price = InstrumentPrice.objects.get(instrument=self.position.instrument)
        self.assertEqual(price.close, Decimal("60000"))
        state = MarketDataSyncState.objects.get(
            dataset=MarketDataSyncState.Dataset.INSTRUMENT_PRICES,
            scope=f"mapping:{self.mapping.id}",
        )
        self.assertEqual(state.covered_until, today)
        self.assertEqual(state.last_error, "")
