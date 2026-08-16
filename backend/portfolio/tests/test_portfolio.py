from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from memberships.models import FamilyMember, Ownership, OwnershipLink
from net_worth.models import Asset, AssetValuation, InvestmentAssetEvent
from portfolio.models import (
    Instrument,
    Portfolio,
    PortfolioMigrationIssue,
    PortfolioPosition,
    PositionOwnershipPeriod,
    PositionOwnershipShare,
)
from portfolio.services import bootstrap_portfolio_for_user, build_portfolio_readiness


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

    def test_historical_ownership_rows_are_immutable(self):
        asset = self.create_asset(name="Fondo")
        bootstrap_portfolio_for_user(user=self.user)
        period = PositionOwnershipPeriod.objects.get(position__asset=asset)
        share = PositionOwnershipShare.objects.get(period=period)

        period.end_date = date(2024, 1, 1)
        with self.assertRaises(ValidationError):
            period.full_clean()
        with self.assertRaises(ValidationError):
            share.delete()

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
            asset_class=Instrument.AssetClass.MIXED,
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
