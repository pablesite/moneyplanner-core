"""Regresiones monetarias: origen, perímetro y evidencia antes de decidir."""

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from accounting.services_ledger import get_account_balance
from memberships.models import OwnershipLink
from portfolio.allocation import (
    build_allocation,
    build_contribution,
    build_scopes,
    confirm_basket,
    create_basket,
)
from portfolio.exposure import build_exposure
from portfolio.models import (
    ContainerCashAccount,
    PositionClassBreakdown,
    PositionHolding,
    PositionValuation,
)

from .test_allocation import AllocationFixture, TODAY


class DecisionDataTests(AllocationFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.position = self.create_position("Global", Decimal("9000"))
        self.strategy(
            self.mine, date(2024, 1, 1), {"equity": ("90", None, None), "cash": ("10", None, None)}
        )

    def account(
        self, balance="0", *, internal=False, ownership=None, currency="EUR", container=None
    ):
        account = LedgerAccount.objects.create(
            user=self.user,
            name=f"Cuenta {LedgerAccount.objects.count()}",
            account_type="asset",
            currency=currency,
        )
        if internal:
            self.own_cash(account)
            if ownership:
                OwnershipLink.objects.filter(target_id=account.asset_id, user=self.user).update(
                    ownership=ownership
                )
            ContainerCashAccount.objects.create(
                container=container or self.container, ledger_account=account, currency=currency
            )
        if Decimal(balance):
            opening = LedgerTransaction.objects.create(
                user=self.user, booking_date=TODAY, value_date=TODAY, description="Apertura"
            )
            equity = LedgerAccount.objects.create(
                user=self.user, name="Apertura", account_type="equity", currency=currency
            )
            for target, side in ((account, "debit"), (equity, "credit")):
                LedgerEntry.objects.create(
                    transaction=opening,
                    account=target,
                    side=side,
                    amount=Decimal(balance),
                    currency=currency,
                )
        return account

    def solve(self, amount="1000", source=None):
        return build_contribution(
            portfolio=self.portfolio,
            ownership=self.mine,
            on_date=TODAY,
            amount=Decimal(amount),
            source_account_id=source.id if source else None,
        )

    def codes(self, result):
        return {row["code"] for row in result["quality"]["issues"]}

    def test_existing_cash_and_ownership_match_all_three_reads(self):
        self.account("2000", internal=True)
        from portfolio.models import InvestmentContainer

        other_container = InvestmentContainer.objects.create(
            portfolio=self.portfolio,
            name="Otro broker",
            container_type=InvestmentContainer.ContainerType.BROKER,
        )
        self.account("7000", internal=True, ownership=self.his, container=other_container)
        result = self.solve()
        allocation = build_allocation(portfolio=self.portfolio, ownership=self.mine, on_date=TODAY)
        exposure = build_exposure(portfolio=self.portfolio, ownership=self.mine, on_date=TODAY)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(Decimal(result["liquidity"]["portfolio_before"]), Decimal("11000"))
        self.assertEqual(Decimal(allocation["total_value"]), Decimal("11000"))
        self.assertEqual(Decimal(exposure["composition_total"]), Decimal("11000"))
        self.assertEqual(exposure["classes"]["percent_basis"], "positions_and_cash")
        self.assertEqual(Decimal(result["reserved_cash"]), Decimal("0"))
        self.assertEqual(Decimal(result["lines"][0]["amount"]), Decimal("1000"))
        self.assertEqual(
            {r["asset_class"]: Decimal(r["value"]) for r in exposure["classes"]["rows"]},
            {r["asset_class"]: Decimal(r["value"]) for r in allocation["by_class"]},
        )

    def test_internal_money_is_not_added_again_and_reserve_stays_in_source(self):
        source = self.account("2000", internal=True)
        result = self.solve(source=source)
        self.assertEqual(result["funding"]["kind"], "internal")
        self.assertEqual(Decimal(result["liquidity"]["portfolio_after"]), Decimal("11000"))
        self.assertEqual(Decimal(result["reserved_cash"]), Decimal("100"))
        self.assertEqual(Decimal(result["lines"][0]["amount"]), Decimal("900"))
        self.assertEqual(result["liquidity"]["reserve_movement"], "retain")
        self.assertEqual(result["liquidity"]["reserve_destination"], source.name)

    def test_external_reserve_has_a_real_destination_and_is_only_booked_on_confirmation(self):
        source = self.account("2000")
        destination = self.account(internal=True)
        before = LedgerTransaction.objects.count()
        basket = create_basket(
            portfolio=self.portfolio,
            ownership=self.mine,
            on_date=TODAY,
            amount=Decimal("1000"),
            source_account_id=source.id,
        )
        self.assertEqual(LedgerTransaction.objects.count(), before)
        line = basket.lines.get()
        self.assertEqual(line.reason, "tactical_reserve")
        self.assertEqual(line.cash_account.ledger_account_id, destination.id)
        confirm_basket(basket=basket)
        self.assertEqual(get_account_balance(account=destination, status="posted"), Decimal("1000"))
        self.assertEqual(get_account_balance(account=source, status="posted"), Decimal("1000"))

    def test_reserve_without_destination_cannot_be_saved(self):
        result = self.solve()
        self.assertEqual(result["status"], "blocked")
        self.assertIn("reserve_destination", self.codes(result))
        with self.assertRaises(ValidationError):
            create_basket(
                portfolio=self.portfolio, ownership=self.mine, on_date=TODAY, amount=Decimal("1000")
            )

    def test_other_ownership_source_is_not_external_new_money(self):
        source = self.account("2000", internal=True, ownership=self.his)
        self.assertIn("source_ownership", self.codes(self.solve(source=source)))

    def test_missing_cash_ownership_is_visible(self):
        source = self.account("2000", internal=True)
        OwnershipLink.objects.filter(user=self.user, target_id=source.asset_id).delete()
        result = self.solve()
        self.assertEqual(result["status"], "blocked")
        self.assertIn("cash_ownership", self.codes(result))

    def test_cash_only_scope_is_discoverable(self):
        self.account("2000", internal=True, ownership=self.his)
        self.assertIn(
            self.his.id,
            {r["ownership_id"] for r in build_scopes(portfolio=self.portfolio, on_date=TODAY)},
        )

    def test_insufficient_source_balance_blocks_preview(self):
        source = self.account("500")
        self.assertIn("source_balance", self.codes(self.solve(source=source)))

    def test_foreign_currency_source_is_not_spent_as_base_currency(self):
        source = self.account("2000", currency="USD")
        self.assertIn("source_currency", self.codes(self.solve(source=source)))

    def test_cash_without_fx_is_not_silently_zero(self):
        self.account("2000", internal=True, currency="JPY")
        result = self.solve()
        self.assertEqual(result["status"], "blocked")
        self.assertIn("cash_fx", self.codes(result))
        self.assertIsNone(result["cash"]["accounts"][0]["value"])

    def test_stale_price_blocks_with_date_and_correction(self):
        PositionValuation.objects.filter(position=self.position, valuation_date=TODAY).delete()
        result = self.solve()
        self.assertIn("valuation_stale", self.codes(result))
        row = next(r for r in result["quality"]["issues"] if r["code"] == "valuation_stale")
        self.assertEqual(row["observed_on"], "2024-01-31")
        self.assertTrue(row["action"])
        self.assertEqual(result["lines"], [])

    def test_missing_value_does_not_turn_into_zero(self):
        PositionValuation.objects.filter(position=self.position).delete()
        self.assertIn("valuation_missing", self.codes(self.solve()))

    def test_missing_position_fx_blocks(self):
        PositionValuation.objects.filter(position=self.position, valuation_date=TODAY).update(
            currency="JPY"
        )
        self.assertIn("valuation_fx", self.codes(self.solve()))

    def test_partial_classification_blocks_even_with_a_known_primary_class(self):
        PositionClassBreakdown.objects.create(
            position=self.position, asset_class="equity", percent=Decimal("70")
        )
        self.assertIn("class_coverage", self.codes(self.solve()))

    def test_old_holdings_block_independently_of_fresh_prices(self):
        PositionHolding.objects.create(
            position=self.position,
            underlying_name="Global",
            asset_class="equity",
            percent=Decimal("100"),
            observed_on=date(2024, 1, 1),
        )
        self.assertIn("holdings_stale", self.codes(self.solve()))

    def test_quality_is_rechecked_before_confirming_and_failure_is_atomic(self):
        source = self.account("2000")
        self.account(internal=True)
        basket = create_basket(
            portfolio=self.portfolio,
            ownership=self.mine,
            on_date=TODAY,
            amount=Decimal("1000"),
            source_account_id=source.id,
        )
        PositionValuation.objects.filter(position=self.position, valuation_date=TODAY).delete()
        before = LedgerTransaction.objects.count()
        with self.assertRaises(ValidationError):
            confirm_basket(basket=basket)
        self.assertEqual(LedgerTransaction.objects.count(), before)
        self.assertEqual(basket.lines.get().status, "pending")

    def test_confirmation_cannot_swap_external_for_internal_funding(self):
        source = self.account("2000")
        inside = self.account("2000", internal=True)
        basket = create_basket(
            portfolio=self.portfolio,
            ownership=self.mine,
            on_date=TODAY,
            amount=Decimal("1000"),
            source_account_id=source.id,
        )
        with self.assertRaisesMessage(ValidationError, "perímetro"):
            confirm_basket(basket=basket, source_account_id=inside.id)
