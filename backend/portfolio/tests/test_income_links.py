from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from net_worth.models import Asset
from portfolio.models import (
    ContainerCashAccount,
    Instrument,
    InvestmentContainer,
    Portfolio,
    PortfolioPosition,
    PortfolioTrade,
)


class PositionIncomeLinkTests(APITestCase):
    """A dividend paid into an account outside the portfolio is income of its position."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="income_links", password="x")
        self.client.force_authenticate(self.user)
        self.portfolio = Portfolio.objects.create(user=self.user, base_currency="EUR")
        container = InvestmentContainer.objects.create(
            portfolio=self.portfolio,
            name="Broker",
            container_type=InvestmentContainer.ContainerType.BROKER,
        )
        self.bank = self.account("Cuenta corriente", LedgerAccount.AccountType.ASSET)
        self.container_cash = self.account("Efectivo broker", LedgerAccount.AccountType.ASSET)
        ContainerCashAccount.objects.create(
            container=container, ledger_account=self.container_cash, currency="EUR"
        )
        self.dividends = self.account("Dividendos", LedgerAccount.AccountType.INCOME)
        asset = Asset.objects.create(
            user=self.user,
            name="Acciones",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.STOCKS,
            currency="EUR",
            amount=Decimal("0"),
            start_date=date(2025, 1, 1),
        )
        self.position_account = LedgerAccount.objects.create(
            user=self.user,
            name="Acciones",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=asset,
        )
        instrument = Instrument.objects.create(
            user=self.user,
            identity_kind=Instrument.IdentityKind.CUSTOM,
            name="Acciones",
            asset_class=Instrument.AssetClass.EQUITY,
            instrument_type=Instrument.InstrumentType.STOCK,
            quote_currency="EUR",
        )
        self.position = PortfolioPosition.objects.create(
            portfolio=self.portfolio,
            container=container,
            instrument=instrument,
            asset=asset,
            ledger_account=self.position_account,
            tracking_style=PortfolioPosition.TrackingStyle.VALUE_BASED,
            status=PortfolioPosition.Status.ACTIVE,
            opened_on=date(2025, 1, 1),
        )
        self.book(
            date(2025, 1, 10),
            "Compra acciones",
            LedgerTransaction.QuickEntryKind.INVESTMENT,
            debit=self.position_account,
            credit=self.bank,
            amount="300",
            investment_direction=LedgerTransaction.InvestmentDirection.INFLOW,
        )
        self.dividend = self.book(
            date(2025, 3, 1),
            "Dividendos Sysco",
            LedgerTransaction.QuickEntryKind.INCOME,
            debit=self.bank,
            credit=self.dividends,
            amount="10",
        )

    def account(self, name, account_type):
        return LedgerAccount.objects.create(
            user=self.user, name=name, account_type=account_type, currency="EUR"
        )

    def book(self, on, description, kind, *, debit, credit, amount, **extra):
        transaction = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=on,
            value_date=on,
            description=description,
            quick_entry_kind=kind,
            status=LedgerTransaction.Status.POSTED,
            **extra,
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=debit,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal(amount),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=credit,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal(amount),
            currency="EUR",
            flow_family="income" if credit.account_type == "income" else "",
            category_key="passive_income" if credit.account_type == "income" else "",
            subcategory_key="dividends" if credit.account_type == "income" else "",
        )
        return transaction

    def url(self, suffix=""):
        return f"/api/portfolio/positions/{self.position.id}/income-links/{suffix}"

    def performance(self):
        response = self.client.get(
            "/api/portfolio/positions/performance/",
            {"date_from": "2025-01-01", "date_to": "2025-12-31"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return next(
            row for row in response.data["results"] if row["position_id"] == self.position.id
        )

    def test_linked_dividend_paid_outside_counts_as_position_income(self):
        before = self.performance()["performance"]
        self.assertEqual(Decimal(before["income"]), Decimal("0"))
        self.assertEqual(Decimal(before["monetary_result"]), Decimal("0"))

        listed = self.client.get(self.url())
        self.assertEqual(
            [row["transaction_id"] for row in listed.data["candidates"]], [self.dividend.id]
        )

        linked = self.client.post(
            self.url("link/"),
            {"transaction_ids": [self.dividend.id], "operation_type": "dividend"},
            format="json",
        )
        self.assertEqual(linked.status_code, status.HTTP_201_CREATED, linked.data)
        self.assertEqual(linked.data["candidates"], [])
        self.assertEqual(linked.data["linked"][0]["transaction_id"], self.dividend.id)

        row = self.performance()
        self.assertEqual(Decimal(row["native_value"]), Decimal("300"))
        self.assertEqual(Decimal(row["performance"]["income"]), Decimal("10"))
        self.assertEqual(Decimal(row["performance"]["monetary_result"]), Decimal("10"))

    def test_income_already_inside_the_portfolio_cannot_be_linked(self):
        inside = self.book(
            date(2025, 4, 1),
            "Dividendos en broker",
            LedgerTransaction.QuickEntryKind.INCOME,
            debit=self.container_cash,
            credit=self.dividends,
            amount="5",
        )

        listed = self.client.get(self.url())
        self.assertNotIn(inside.id, [row["transaction_id"] for row in listed.data["candidates"]])
        rejected = self.client.post(
            self.url("link/"), {"transaction_ids": [inside.id]}, format="json"
        )
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(PortfolioTrade.objects.exists())

    def test_unlinking_keeps_the_ledger_movement(self):
        self.client.post(self.url("link/"), {"transaction_ids": [self.dividend.id]}, format="json")

        response = self.client.post(
            self.url("unlink/"), {"transaction_id": self.dividend.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["linked"], [])
        self.assertTrue(LedgerTransaction.objects.filter(id=self.dividend.id).exists())
        self.assertEqual(Decimal(self.performance()["performance"]["income"]), Decimal("0"))
