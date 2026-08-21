"""Registro de decisiones: lo que se propuso, lo que se hizo y como quedo."""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from portfolio.allocation import confirm_basket, create_basket, discard_basket
from portfolio.decisions import build_decision_log
from portfolio.models import ContributionBasket

from .test_allocation import AllocationFixture

TODAY = date(2024, 12, 31)


class DecisionLogTests(AllocationFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.bank = LedgerAccount.objects.create(
            user=self.user,
            name="Banco",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        equity_account = LedgerAccount.objects.create(
            user=self.user,
            name="Apertura",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
        )
        opening = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2024, 1, 1),
            value_date=date(2024, 1, 1),
            description="Saldo inicial",
        )
        LedgerEntry.objects.create(
            transaction=opening,
            account=self.bank,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("5000"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=opening,
            account=equity_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("5000"),
            currency="EUR",
        )
        self.position = self.create_position("Fondo global", Decimal("10000"))
        self.position.ledger_account = LedgerAccount.objects.create(
            user=self.user,
            name="Fondo global",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        self.position.save(update_fields=["ledger_account"])
        self.strategy(self.mine, date(2024, 1, 1), {"equity": ("100", None, None)})

    def basket(self, amount: str = "1000") -> ContributionBasket:
        return create_basket(
            portfolio=self.portfolio,
            ownership=self.mine,
            amount=Decimal(amount),
            on_date=TODAY,
            source_account_id=self.bank.id,
        )

    def log(self) -> dict:
        return build_decision_log(portfolio=self.portfolio, ownership=self.mine, on_date=TODAY)

    def test_a_pending_proposal_is_recorded_as_not_decided_yet(self):
        self.basket()

        entry = self.log()["entries"][0]

        self.assertEqual(entry["status"], ContributionBasket.Status.DRAFT)
        self.assertEqual(entry["did"]["followed"], "not_yet")
        self.assertEqual(entry["did"]["executed_amount"], "0")
        self.assertEqual(entry["recommended"]["amount"], "1000.00")

    def test_following_a_proposal_is_recorded_with_what_was_executed(self):
        basket = self.basket()

        confirm_basket(basket=basket)

        entry = self.log()["entries"][0]
        self.assertEqual(entry["did"]["followed"], "fully")
        self.assertEqual(Decimal(entry["did"]["executed_amount"]), Decimal("1000"))
        self.assertEqual(self.log()["summary"]["followed"], 1)

    def test_discarding_a_proposal_is_recorded_as_not_followed(self):
        basket = self.basket()

        discard_basket(basket=basket)

        entry = self.log()["entries"][0]
        self.assertEqual(entry["did"]["followed"], "no")
        self.assertEqual(self.log()["summary"]["ignored"], 1)

    def test_the_outcome_carries_the_drift_then_and_now_without_simulating(self):
        # Ni backtest ni comparacion contra DCA: la desviacion de entonces y la de ahora.
        self.basket()

        log = self.log()

        outcome = log["entries"][0]["outcome"]
        self.assertIn("worst_drift_at_decision", outcome)
        self.assertIn("worst_drift_now", outcome)
        self.assertEqual(log["method"]["kind"], "observed")
        self.assertIn("no se compara contra dca", log["method"]["note"].lower())

    def test_every_proposed_line_travels_with_what_happened_to_it(self):
        basket = self.basket()
        confirm_basket(basket=basket)

        lines = self.log()["entries"][0]["recommended"]["lines"]

        self.assertTrue(lines)
        for line in lines:
            self.assertEqual(line["status"], "confirmed")
            self.assertIsNotNone(line["ledger_transaction_id"])
            self.assertTrue(line["target"])
