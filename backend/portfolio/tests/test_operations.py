from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from accounting.services_ledger import get_account_balance
from net_worth.models import Asset
from memberships.models import FamilyMember, Ownership
from portfolio.models import (
    AllocationStrategy,
    ContainerCashAccount,
    ContributionBasket,
    ContributionBasketLine,
    Instrument,
    InvestmentContainer,
    Portfolio,
    PortfolioImportBatch,
    PortfolioPosition,
    PortfolioTrade,
    PositionValuation,
)


class PortfolioOperationApiTests(APITestCase):
    fixtures_path = Path(__file__).parent / "fixtures"

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="portfolio_operations", password="pass1234"
        )
        self.client.force_authenticate(self.user)
        self.portfolio = Portfolio.objects.create(user=self.user, base_currency="EUR")
        self.container = InvestmentContainer.objects.create(
            portfolio=self.portfolio,
            name="Broker",
            container_type=InvestmentContainer.ContainerType.BROKER,
        )
        cash_asset = Asset.objects.create(
            user=self.user,
            name="Efectivo broker",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("1000"),
        )
        self.cash_account = LedgerAccount.objects.create(
            user=self.user,
            name="Efectivo broker",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=cash_asset,
        )
        self.cash_link = ContainerCashAccount.objects.create(
            container=self.container,
            ledger_account=self.cash_account,
            currency="EUR",
        )
        equity = LedgerAccount.objects.create(
            user=self.user,
            name="Apertura",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
        )
        opening = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2025, 1, 1),
            value_date=date(2025, 1, 1),
            description="Saldo inicial",
        )
        LedgerEntry.objects.create(
            transaction=opening,
            account=self.cash_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1000"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=opening,
            account=equity,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1000"),
            currency="EUR",
        )
        investment_asset = Asset.objects.create(
            user=self.user,
            name="Fondo Global",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=Decimal("0"),
            start_date=date(2025, 1, 1),
        )
        self.position_account = LedgerAccount.objects.create(
            user=self.user,
            name="Fondo Global",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=investment_asset,
        )
        instrument = Instrument.objects.create(
            user=self.user,
            identity_kind=Instrument.IdentityKind.CUSTOM,
            name="Fondo Global",
            asset_class=Instrument.AssetClass.EQUITY,
            instrument_type=Instrument.InstrumentType.FUND,
            quote_currency="EUR",
        )
        self.position = PortfolioPosition.objects.create(
            portfolio=self.portfolio,
            container=self.container,
            instrument=instrument,
            asset=investment_asset,
            ledger_account=self.position_account,
            tracking_style=PortfolioPosition.TrackingStyle.VALUE_BASED,
            status=PortfolioPosition.Status.ACTIVE,
            opened_on=date(2025, 1, 1),
        )

    def operation_payload(self, **overrides):
        payload = {
            "operation_type": "buy",
            "position_id": self.position.id,
            "cash_account_id": self.cash_link.id,
            "booking_date": "2025-02-01",
            "amount": "100.00",
            "fee": "2.00",
            "description": "Compra Fondo Global",
        }
        payload.update(overrides)
        return payload

    def test_buy_requires_preview_and_reconciles_cash_position_and_metadata(self):
        payload = self.operation_payload()
        rejected = self.client.post("/api/portfolio/operations/confirm/", payload, format="json")
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)

        preview = self.client.post("/api/portfolio/operations/preview/", payload, format="json")
        self.assertEqual(preview.status_code, status.HTTP_200_OK, preview.data)
        payload["preview_token"] = preview.data["preview_token"]
        confirmed = self.client.post("/api/portfolio/operations/confirm/", payload, format="json")

        self.assertEqual(confirmed.status_code, status.HTTP_201_CREATED, confirmed.data)
        trade = PortfolioTrade.objects.get(id=confirmed.data["trade_id"])
        self.assertEqual(trade.gross_amount, Decimal("100"))
        self.assertEqual(trade.fee, Decimal("2"))
        self.assertIsNotNone(trade.fee_transaction_id)
        self.assertEqual(get_account_balance(account=self.cash_account), Decimal("898"))
        self.assertEqual(get_account_balance(account=self.position_account), Decimal("100"))

        duplicate = self.client.post("/api/portfolio/operations/confirm/", payload, format="json")
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(PortfolioTrade.objects.count(), 1)

    def test_changed_payload_after_preview_does_not_create_ledger_entries(self):
        payload = self.operation_payload()
        preview = self.client.post("/api/portfolio/operations/preview/", payload, format="json")
        before = LedgerEntry.objects.count()
        payload["amount"] = "200.00"
        payload["preview_token"] = preview.data["preview_token"]

        rejected = self.client.post("/api/portfolio/operations/confirm/", payload, format="json")

        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(LedgerEntry.objects.count(), before)
        self.assertFalse(PortfolioTrade.objects.exists())

    def test_manual_valuation_updates_same_day_without_duplicate_history(self):
        payload = self.operation_payload(
            operation_type="valuation", amount="1234.56", currency="EUR", fee=""
        )
        payload.pop("cash_account_id")
        preview = self.client.post("/api/portfolio/operations/preview/", payload, format="json")
        payload["preview_token"] = preview.data["preview_token"]
        first = self.client.post("/api/portfolio/operations/confirm/", payload, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)

        payload["amount"] = "1300"
        payload.pop("preview_token")
        preview = self.client.post("/api/portfolio/operations/preview/", payload, format="json")
        payload["preview_token"] = preview.data["preview_token"]
        second = self.client.post("/api/portfolio/operations/confirm/", payload, format="json")
        self.assertEqual(second.status_code, status.HTTP_201_CREATED, second.data)
        self.assertEqual(PositionValuation.objects.count(), 1)
        self.assertEqual(PositionValuation.objects.get().value, Decimal("1300"))

    def valuation_payload(self, **overrides):
        payload = self.operation_payload(
            operation_type="valuation", amount="1234.56", currency="EUR", fee=""
        )
        payload.pop("cash_account_id")
        payload.update(overrides)
        return payload

    def confirm_valuation(self, payload):
        preview = self.client.post("/api/portfolio/operations/preview/", payload, format="json")
        self.assertEqual(preview.status_code, status.HTTP_200_OK, preview.data)
        payload = {**payload, "preview_token": preview.data["preview_token"]}
        confirmed = self.client.post("/api/portfolio/operations/confirm/", payload, format="json")
        self.assertEqual(confirmed.status_code, status.HTTP_201_CREATED, confirmed.data)
        return preview.data["preview"], confirmed.data

    def test_manual_valuation_syncs_accounting_with_revaluation_entry(self):
        preview, confirmed = self.confirm_valuation(self.valuation_payload())

        self.assertTrue(preview["ledger_effect"]["syncs_accounting"])
        self.assertEqual(Decimal(preview["ledger_effect"]["balance_before"]), Decimal("0"))
        self.assertEqual(Decimal(preview["ledger_effect"]["delta"]), Decimal("1234.56"))
        self.assertIsNotNone(confirmed["ledger_transaction_id"])

        revaluation = LedgerTransaction.objects.get(id=confirmed["ledger_transaction_id"])
        self.assertEqual(revaluation.quick_entry_kind, LedgerTransaction.QuickEntryKind.REVALUATION)
        self.assertEqual(revaluation.booking_date, date(2025, 2, 1))
        self.assertEqual(get_account_balance(account=self.position_account), Decimal("1234.56"))
        self.assertTrue(
            LedgerAccount.objects.filter(
                user=self.user,
                name="Revalorizaciones",
                account_type=LedgerAccount.AccountType.EXPENSE,
                currency="EUR",
            ).exists()
        )

    def test_manual_valuation_posts_only_the_delta_and_is_idempotent(self):
        self.confirm_valuation(self.valuation_payload())

        _, corrected = self.confirm_valuation(self.valuation_payload(amount="1300"))
        self.assertIsNotNone(corrected["ledger_transaction_id"])
        delta_entry = LedgerEntry.objects.get(
            transaction_id=corrected["ledger_transaction_id"], account=self.position_account
        )
        self.assertEqual(delta_entry.amount, Decimal("65.44"))
        self.assertEqual(get_account_balance(account=self.position_account), Decimal("1300"))

        preview, repeated = self.confirm_valuation(self.valuation_payload(amount="1300"))
        self.assertNotIn("E", preview["ledger_effect"]["delta"])
        self.assertEqual(Decimal(preview["ledger_effect"]["delta"]), Decimal("0"))
        self.assertIsNone(repeated["ledger_transaction_id"])
        self.assertEqual(get_account_balance(account=self.position_account), Decimal("1300"))
        self.assertEqual(
            LedgerTransaction.objects.filter(
                quick_entry_kind=LedgerTransaction.QuickEntryKind.REVALUATION
            ).count(),
            2,
        )

    def test_manual_valuation_without_ledger_account_stays_analytic(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Plan de pensiones",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=Decimal("0"),
            start_date=date(2025, 1, 1),
        )
        instrument = Instrument.objects.create(
            user=self.user,
            identity_kind=Instrument.IdentityKind.CUSTOM,
            name="Plan de pensiones",
            asset_class=Instrument.AssetClass.PRIVATE_EQUITY,
            instrument_type=Instrument.InstrumentType.PENSION_PLAN,
            quote_currency="EUR",
        )
        position = PortfolioPosition.objects.create(
            portfolio=self.portfolio,
            container=self.container,
            instrument=instrument,
            asset=asset,
            ledger_account=None,
            tracking_style=PortfolioPosition.TrackingStyle.VALUE_BASED,
            status=PortfolioPosition.Status.ACTIVE,
            opened_on=date(2025, 1, 1),
        )
        before = LedgerTransaction.objects.count()

        preview, confirmed = self.confirm_valuation(self.valuation_payload(position_id=position.id))

        self.assertFalse(preview["ledger_effect"]["syncs_accounting"])
        self.assertIn("cuenta contable", preview["ledger_effect"]["reason"])
        self.assertIsNone(confirmed["ledger_transaction_id"])
        self.assertEqual(LedgerTransaction.objects.count(), before)
        self.assertEqual(PositionValuation.objects.get(position=position).value, Decimal("1234.56"))

    def post_accounting_revaluation(self, amount, booking_date="2025-03-01"):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/accounting/transactions/quick-entry/",
                {
                    "movement_type": "revaluation",
                    "booking_date": booking_date,
                    "value_date": booking_date,
                    "description": "Revalorización desde Movimientos",
                    "amount": amount,
                    "account_id": self.position_account.id,
                },
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response.data["id"]

    def test_accounting_revaluation_syncs_portfolio_without_bootstrap(self):
        self.post_accounting_revaluation("250.00")

        derived = PositionValuation.objects.get(
            position=self.position, source=PositionValuation.Source.LEGACY_LEDGER
        )
        self.assertEqual(derived.valuation_date, date(2025, 3, 1))
        self.assertEqual(derived.value, Decimal("250"))
        self.assertEqual(get_account_balance(account=self.position_account), Decimal("250"))

    def test_further_accounting_revaluations_keep_portfolio_aligned(self):
        self.post_accounting_revaluation("250.00")
        self.post_accounting_revaluation("100.00", booking_date="2025-04-01")

        latest = PositionValuation.objects.filter(
            position=self.position, source=PositionValuation.Source.LEGACY_LEDGER
        ).order_by("-valuation_date")[0]
        self.assertEqual(latest.valuation_date, date(2025, 4, 1))
        self.assertEqual(latest.value, Decimal("350"))

    def test_deleting_accounting_revaluation_drops_its_derived_valuation(self):
        transaction_id = self.post_accounting_revaluation("250.00")
        self.assertTrue(
            PositionValuation.objects.filter(legacy_ledger_transaction_id=transaction_id).exists()
        )

        with self.captureOnCommitCallbacks(execute=True):
            deleted = self.client.delete(f"/api/accounting/transactions/{transaction_id}/")

        self.assertIn(
            deleted.status_code, {status.HTTP_200_OK, status.HTTP_204_NO_CONTENT}, deleted.data
        )
        self.assertFalse(
            PositionValuation.objects.filter(legacy_ledger_transaction_id=transaction_id).exists()
        )
        self.assertEqual(get_account_balance(account=self.position_account), Decimal("0"))

    def test_position_funded_only_by_accounting_reports_its_ledger_balance(self):
        payload = self.operation_payload(amount="300.00", fee="0")
        preview = self.client.post("/api/portfolio/operations/preview/", payload, format="json")
        payload["preview_token"] = preview.data["preview_token"]
        self.client.post("/api/portfolio/operations/confirm/", payload, format="json")
        self.assertFalse(PositionValuation.objects.filter(position=self.position).exists())

        resolved = self.client.get(f"/api/portfolio/positions/{self.position.id}/valuation/")

        self.assertEqual(resolved.status_code, status.HTTP_200_OK, resolved.data)
        self.assertEqual(Decimal(resolved.data["value"]), Decimal("300"))
        self.assertEqual(resolved.data["currency"], "EUR")
        self.assertEqual(resolved.data["provenance"]["kind"], "ledger_balance")
        # A balance is current by definition, so it is never stale and never pending
        # review; what the position lacks is a valuation.
        self.assertEqual(resolved.data["status"], "at_cost")

        quality = self.client.get("/api/portfolio/quality/")
        self.assertEqual(quality.data["positions"]["at_cost"], 1)
        self.assertEqual(quality.data["positions"]["stale"], 0)
        self.assertEqual(quality.data["positions"]["missing"], 0)

    def test_position_funded_only_by_accounting_appears_in_performance_reads(self):
        payload = self.operation_payload(amount="300.00", fee="0")
        preview = self.client.post("/api/portfolio/operations/preview/", payload, format="json")
        payload["preview_token"] = preview.data["preview_token"]
        self.client.post("/api/portfolio/operations/confirm/", payload, format="json")

        response = self.client.get(
            "/api/portfolio/positions/performance/",
            {"date_from": "2025-01-01", "date_to": "2025-12-31"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        row = next(r for r in response.data["results"] if r["position_id"] == self.position.id)
        self.assertEqual(Decimal(row["native_value"]), Decimal("300"))
        self.assertNotEqual(row["value_status"], "missing")

    def test_period_starting_before_a_position_opened_counts_zero_not_unknown(self):
        payload = self.operation_payload(amount="100.00", fee="0")
        preview = self.client.post("/api/portfolio/operations/preview/", payload, format="json")
        payload["preview_token"] = preview.data["preview_token"]
        self.client.post("/api/portfolio/operations/confirm/", payload, format="json")

        response = self.client.get(
            "/api/portfolio/overview/",
            {"date_from": "2024-01-01", "date_to": "2025-12-31"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["coverage"]["value"], "complete")
        self.assertIsNotNone(response.data["value"])

    def test_divested_position_reports_zero_instead_of_its_last_valuation(self):
        buy = self.operation_payload(amount="300.00", fee="0")
        preview = self.client.post("/api/portfolio/operations/preview/", buy, format="json")
        buy["preview_token"] = preview.data["preview_token"]
        self.client.post("/api/portfolio/operations/confirm/", buy, format="json")
        self.confirm_valuation(self.valuation_payload(amount="300.00", booking_date="2025-02-02"))

        sell = self.operation_payload(
            operation_type="sell", amount="300.00", fee="0", booking_date="2025-03-01"
        )
        preview = self.client.post("/api/portfolio/operations/preview/", sell, format="json")
        sell["preview_token"] = preview.data["preview_token"]
        sold = self.client.post("/api/portfolio/operations/confirm/", sell, format="json")
        self.assertEqual(sold.status_code, status.HTTP_201_CREATED, sold.data)
        self.assertEqual(get_account_balance(account=self.position_account), Decimal("0"))

        resolved = self.client.get(f"/api/portfolio/positions/{self.position.id}/valuation/")
        self.assertEqual(Decimal(resolved.data["value"]), Decimal("0"))
        self.assertEqual(resolved.data["provenance"]["kind"], "divested")

        reads = self.client.get(
            "/api/portfolio/positions/performance/",
            {"date_from": "2025-01-01", "date_to": "2025-12-31"},
        )
        row = next(r for r in reads.data["results"] if r["position_id"] == self.position.id)
        self.assertEqual(Decimal(row["native_value"]), Decimal("0"))

    def test_archived_positions_are_left_out_of_the_review_counters(self):
        self.post_accounting_revaluation("250.00")
        before = self.client.get("/api/portfolio/quality/")
        self.assertEqual(before.data["positions"]["total"], 1)

        self.client.post(f"/api/portfolio/positions/{self.position.id}/archive/")

        after = self.client.get("/api/portfolio/quality/")
        self.assertEqual(after.data["positions"]["total"], 0)
        self.assertEqual(after.data["ownership_missing"], 0)

    def test_contribution_after_the_last_valuation_is_not_read_as_a_loss(self):
        """Regression: a flat carry-forward made added money look like a loss.

        The value stayed at the last valuation while the contribution counted as a flow,
        so the subperiod read as negative. Chained over a full history those false
        negatives took the portfolio TWR to -87%, and no test covered it.
        """
        funding = self.operation_payload(amount="600.00", fee="0", booking_date="2025-02-01")
        preview = self.client.post("/api/portfolio/operations/preview/", funding, format="json")
        funding["preview_token"] = preview.data["preview_token"]
        self.client.post("/api/portfolio/operations/confirm/", funding, format="json")
        self.confirm_valuation(self.valuation_payload(amount="600.00", booking_date="2025-02-01"))

        # Contribute again and never revalue: the only boundary left is the period end.
        more = self.operation_payload(amount="300.00", fee="0", booking_date="2025-03-01")
        preview = self.client.post("/api/portfolio/operations/preview/", more, format="json")
        more["preview_token"] = preview.data["preview_token"]
        self.client.post("/api/portfolio/operations/confirm/", more, format="json")

        reads = self.client.get(
            "/api/portfolio/positions/performance/",
            {"date_from": "2025-01-01", "date_to": "2025-12-31"},
        )

        row = next(r for r in reads.data["results"] if r["position_id"] == self.position.id)
        self.assertEqual(Decimal(row["native_value"]), Decimal("900"))
        # 900 contributed and worth 900: neither gain nor loss.
        self.assertEqual(Decimal(row["performance"]["monetary_result"]), Decimal("0"))
        self.assertEqual(Decimal(row["performance"]["return"]["twr"]), Decimal("0"))

    def test_units_based_position_never_reports_units_as_value(self):
        self.position.tracking_style = PortfolioPosition.TrackingStyle.UNITS_BASED
        self.position.save(update_fields=["tracking_style", "updated_at"])
        payload = self.operation_payload(amount="300.00", fee="0", units="12")
        preview = self.client.post("/api/portfolio/operations/preview/", payload, format="json")
        payload["preview_token"] = preview.data["preview_token"]
        self.client.post("/api/portfolio/operations/confirm/", payload, format="json")

        resolved = self.client.get(f"/api/portfolio/positions/{self.position.id}/valuation/")

        self.assertEqual(resolved.data["status"], "missing")
        self.assertIsNone(resolved.data["value"])

    def test_resync_endpoint_recovers_valuations_written_under_the_orm(self):
        transaction_id = self.post_accounting_revaluation("250.00")
        # Simulate data that reached the database without firing signals, as a restore does.
        PositionValuation.objects.filter(legacy_ledger_transaction_id=transaction_id).delete()

        response = self.client.post("/api/portfolio/positions/resync-valuations/")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["positions_checked"], 1)
        self.assertEqual(response.data["valuations_created"], 1)
        derived = PositionValuation.objects.get(
            position=self.position, source=PositionValuation.Source.LEGACY_LEDGER
        )
        self.assertEqual(derived.value, Decimal("250"))

    def test_resync_also_picks_up_an_asset_that_never_became_a_position(self):
        # El boton prometia actualizar la cartera y no descubria activos nuevos: un activo
        # creado en Patrimonio con sus movimientos ya contabilizados no salia de ninguna
        # manera. Se comprueba aqui ademas del signal porque es la via de reparacion para
        # los que ya se quedaron fuera.
        orphan = Asset.objects.create(
            user=self.user,
            name="Cripto - Bitcoin (Pionex)",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.CRYPTOCURRENCIES,
            currency="BTC",
            amount=Decimal("100"),
            start_date=date(2024, 1, 1),
        )
        PortfolioPosition.objects.filter(asset=orphan).delete()

        response = self.client.post("/api/portfolio/positions/resync-valuations/")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["positions_created"], 1)
        self.assertTrue(PortfolioPosition.objects.filter(asset=orphan).exists())

    def test_an_etf_can_be_paid_straight_from_a_bank_account(self):
        # En un banco no hay monedero de inversion: compras el ETF y el dinero sale de tu
        # cuenta corriente. Exigir efectivo de contenedor obligaba a inventarse una
        # cuenta que no existe, y a meter en la cartera el dinero del gasto corriente.
        bank = LedgerAccount.objects.create(
            user=self.user,
            name="Banco",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        equity = LedgerAccount.objects.get(user=self.user, name="Apertura")
        opening = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2025, 1, 1),
            value_date=date(2025, 1, 1),
            description="Saldo banco",
        )
        LedgerEntry.objects.create(
            transaction=opening,
            account=bank,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1000"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=opening,
            account=equity,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1000"),
            currency="EUR",
        )
        payload = {
            "operation_type": "buy",
            "position_id": self.position.id,
            "source_account_id": bank.id,
            "booking_date": "2024-06-01",
            "amount": "300.00",
            "fee": "0",
        }

        preview = self.client.post("/api/portfolio/operations/preview/", payload, format="json")
        payload["preview_token"] = preview.data["preview_token"]
        confirm = self.client.post("/api/portfolio/operations/confirm/", payload, format="json")

        self.assertEqual(preview.status_code, status.HTTP_200_OK, preview.data)
        self.assertEqual(confirm.status_code, status.HTTP_201_CREATED, confirm.data)
        self.assertEqual(get_account_balance(account=bank, status="posted"), Decimal("700"))

    def test_an_operation_must_say_where_the_money_comes_from(self):
        payload = {
            "operation_type": "buy",
            "position_id": self.position.id,
            "booking_date": "2024-06-01",
            "amount": "300.00",
        }

        response = self.client.post("/api/portfolio/operations/preview/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)

    def test_setup_reassigns_container_and_asset_class(self):
        other = InvestmentContainer.objects.create(
            portfolio=self.portfolio,
            name="Banco",
            container_type=InvestmentContainer.ContainerType.BANK,
        )

        response = self.client.post(
            f"/api/portfolio/positions/{self.position.id}/confirm-setup/",
            {
                "tracking_style": "value_based",
                "history_mode": "reconstructed",
                "container_id": other.id,
                "asset_class": Instrument.AssetClass.FIXED_INCOME,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.position.refresh_from_db()
        self.assertEqual(self.position.container_id, other.id)
        self.assertEqual(self.position.effective_asset_class, Instrument.AssetClass.FIXED_INCOME)
        # The instrument keeps its own class: it may be shared with other portfolios.
        self.assertEqual(self.position.instrument.asset_class, Instrument.AssetClass.EQUITY)

    def test_a_shared_canonical_instrument_is_classified_per_position(self):
        """Regression: crypto could not be classified at all.

        Canonical instruments carry shared market prices and belong to no user, so writing
        the class there would reclassify other portfolios. Refusing outright left the
        position stuck; the choice now lives on the position and the instrument keeps its
        own class as the default for everyone else.
        """
        instrument = self.position.instrument
        instrument.identity_kind = Instrument.IdentityKind.CANONICAL
        instrument.user = None
        instrument.isin = "IE00B4L5Y983"
        instrument.save()

        response = self.client.post(
            f"/api/portfolio/positions/{self.position.id}/confirm-setup/",
            {"asset_class": Instrument.AssetClass.COMMODITIES},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.position.refresh_from_db()
        instrument.refresh_from_db()
        self.assertEqual(self.position.effective_asset_class, Instrument.AssetClass.COMMODITIES)
        self.assertEqual(instrument.asset_class, Instrument.AssetClass.EQUITY)

    def test_position_archive_and_reopen_preserve_history(self):
        archived = self.client.post(f"/api/portfolio/positions/{self.position.id}/archive/")
        self.assertEqual(archived.status_code, status.HTTP_200_OK)
        self.position.refresh_from_db()
        self.assertEqual(self.position.status, PortfolioPosition.Status.ARCHIVED)
        self.assertFalse(self.position.asset.is_active)

        reopened = self.client.post(f"/api/portfolio/positions/{self.position.id}/reopen/")
        self.assertEqual(reopened.status_code, status.HTTP_200_OK)
        self.position.refresh_from_db()
        self.assertEqual(self.position.status, PortfolioPosition.Status.ACTIVE)
        self.assertTrue(self.position.asset.is_active)

    def test_position_setup_declares_cutoff_without_mutating_ledger(self):
        before = list(
            LedgerEntry.objects.order_by("id").values_list(
                "id", "transaction_id", "account_id", "side", "amount"
            )
        )

        invalid = self.client.post(
            f"/api/portfolio/positions/{self.position.id}/confirm-setup/",
            {"tracking_style": "units_based", "history_mode": "cutoff"},
            format="json",
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)

        confirmed = self.client.post(
            f"/api/portfolio/positions/{self.position.id}/confirm-setup/",
            {
                "tracking_style": "units_based",
                "history_mode": "cutoff",
                "history_start_date": "2025-01-15",
            },
            format="json",
        )
        self.assertEqual(confirmed.status_code, status.HTTP_200_OK, confirmed.data)
        self.position.refresh_from_db()
        self.assertEqual(self.position.history_start_date, date(2025, 1, 15))
        self.assertIsNotNone(self.position.setup_confirmed_at)
        self.assertEqual(
            list(
                LedgerEntry.objects.order_by("id").values_list(
                    "id", "transaction_id", "account_id", "side", "amount"
                )
            ),
            before,
        )

        options = self.client.get("/api/portfolio/operations/options/")
        self.assertEqual(options.status_code, status.HTTP_200_OK)
        row = options.data["positions"][0]
        self.assertTrue(row["setup_confirmed"])
        self.assertEqual(row["history_mode"], "cutoff")
        self.assertIn("performance_coverage", row)
        self.assertIn("position_detail_coverage", row)

    def test_moving_a_container_cash_to_another_platform_changes_the_account(self):
        # Mudar el efectivo de Binance a Pionex es cambiar la cuenta del contenedor, no
        # desenlazar y volver a enlazar: desenlazar choca con las cestas que ya apuntan a
        # ese efectivo, y volver a enlazar choca con el unico enlace por moneda.
        other_asset = Asset.objects.create(
            user=self.user,
            name="Efectivo Pionex",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("50"),
        )
        other = LedgerAccount.objects.create(
            user=self.user,
            name="Efectivo Pionex",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=other_asset,
        )

        response = self.client.patch(
            f"/api/portfolio/cash-accounts/{self.cash_link.id}/",
            {"ledger_account_id": other.id, "currency": "EUR"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.cash_link.refresh_from_db()
        self.assertEqual(self.cash_link.ledger_account_id, other.id)
        self.assertEqual(self.cash_link.container_id, self.container.id)

    def test_unlinking_cash_used_by_a_saved_basket_explains_itself(self):
        # Antes salia como un 500 sin mensaje: una condicion prevista leida como averia.
        strategy = AllocationStrategy.objects.create(
            portfolio=self.portfolio,
            ownership=Ownership.objects.create(
                user=self.user,
                kind=Ownership.Kind.INDIVIDUAL,
                member=FamilyMember.objects.create(
                    user=self.user, name="Pablo", role=FamilyMember.Role.ADULT
                ),
            ),
            effective_from=date(2025, 1, 1),
        )
        basket = ContributionBasket.objects.create(
            portfolio=self.portfolio,
            ownership=strategy.ownership,
            strategy=strategy,
            booking_date=date(2025, 3, 1),
            amount=Decimal("100"),
            reserved_cash=Decimal("0"),
            leftover=Decimal("0"),
        )
        ContributionBasketLine.objects.create(
            basket=basket, cash_account=self.cash_link, amount=Decimal("100")
        )

        response = self.client.delete(f"/api/portfolio/cash-accounts/{self.cash_link.id}/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("cambia la cuenta del contenedor", response.data["error"]["message"])

    def test_the_options_offer_every_own_cash_account_as_a_funding_source(self):
        # Enlazar una cuenta como efectivo de un contenedor la sacaba de la lista de
        # enlazables, que es justo la que se usaba para elegir de donde sale el dinero:
        # no se podia pagar una compra desde el monedero de la propia plataforma.
        options = self.client.get("/api/portfolio/operations/options/")

        self.assertEqual(options.status_code, status.HTTP_200_OK, options.data)
        funding = {row["id"]: row for row in options.data["funding_accounts"]}
        self.assertIn(self.cash_account.id, funding)
        self.assertNotIn(
            self.cash_account.id,
            {row["id"] for row in options.data["linkable_cash_accounts"]},
        )
        self.assertEqual(Decimal(funding[self.cash_account.id]["balance"]), Decimal("1000"))

    def test_csv_requires_preview_and_reimport_is_idempotent(self):
        csv_content = self.fixture("broker_standard.csv")
        upload = self.client.post(
            "/api/portfolio/imports/upload/",
            {"file": SimpleUploadedFile("broker.csv", csv_content, content_type="text/csv")},
            format="multipart",
        )
        self.assertEqual(upload.status_code, status.HTTP_201_CREATED, upload.data)
        batch_id = upload.data["id"]
        premature = self.client.post(
            f"/api/portfolio/imports/{batch_id}/confirm/", {}, format="json"
        )
        self.assertEqual(premature.status_code, status.HTTP_400_BAD_REQUEST)

        mapping = {
            key: key
            for key in [
                "operation_type",
                "booking_date",
                "position_id",
                "cash_account_id",
                "amount",
            ]
        }
        mapping["external_id"] = "external_id"
        preview = self.client.post(
            f"/api/portfolio/imports/{batch_id}/preview/", {"mapping": mapping}, format="json"
        )
        self.assertEqual(preview.status_code, status.HTTP_200_OK, preview.data)
        self.assertEqual(preview.data["rows"][0]["status"], "valid")
        self.assertEqual(preview.data["rows"][1]["status"], "error")
        confirmed = self.client.post(
            f"/api/portfolio/imports/{batch_id}/confirm/", {}, format="json"
        )
        self.assertEqual(confirmed.status_code, status.HTTP_200_OK, confirmed.data)
        self.assertEqual(confirmed.data["status"], "partial")
        self.assertEqual(PortfolioTrade.objects.filter(source="csv").count(), 1)

        duplicate_upload = self.client.post(
            "/api/portfolio/imports/upload/",
            {"file": SimpleUploadedFile("again.csv", csv_content, content_type="text/csv")},
            format="multipart",
        )
        self.assertEqual(duplicate_upload.status_code, status.HTTP_200_OK)
        self.assertTrue(duplicate_upload.data["duplicate_file"])
        self.assertEqual(PortfolioImportBatch.objects.count(), 1)

    def test_second_anonymized_csv_format_maps_spanish_bank_columns(self):
        csv_content = self.fixture("bank_spanish.csv")
        upload = self.client.post(
            "/api/portfolio/imports/upload/",
            {"file": SimpleUploadedFile("banco.csv", csv_content, content_type="text/csv")},
            format="multipart",
        )
        mapping = {
            "operation_type": "tipo",
            "booking_date": "fecha",
            "position_id": "posicion",
            "cash_account_id": "efectivo",
            "amount": "importe",
            "external_id": "referencia",
            "description": "concepto",
        }

        preview = self.client.post(
            f"/api/portfolio/imports/{upload.data['id']}/preview/",
            {"mapping": mapping},
            format="json",
        )
        self.assertEqual(preview.status_code, status.HTTP_200_OK, preview.data)
        self.assertEqual(preview.data["rows"][0]["status"], "valid")
        self.assertEqual(preview.data["rows"][0]["normalized_data"]["amount"], "12.75")
        confirmed = self.client.post(
            f"/api/portfolio/imports/{upload.data['id']}/confirm/", {}, format="json"
        )
        self.assertEqual(confirmed.status_code, status.HTTP_200_OK, confirmed.data)
        trade = PortfolioTrade.objects.get(source="csv")
        self.assertEqual(trade.operation_type, "dividend")
        self.assertEqual(trade.gross_amount, Decimal("12.75"))

    def test_class_breakdown_splits_a_mixed_position_and_must_add_up(self):
        # Una cartera de roboadvisor no es de una sola clase: contarla entera en la
        # dominante hace desaparecer del gráfico toda su renta fija.
        response = self.client.post(
            f"/api/portfolio/positions/{self.position.id}/confirm-setup/",
            {
                "tracking_style": "value_based",
                "history_mode": "reconstructed",
                "class_breakdown": [
                    {"asset_class": "equity", "percent": "60"},
                    {"asset_class": "fixed_income", "percent": "40"},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(self.position.class_breakdown.count(), 2)

        partial = self.client.post(
            f"/api/portfolio/positions/{self.position.id}/confirm-setup/",
            {
                "tracking_style": "value_based",
                "history_mode": "reconstructed",
                "class_breakdown": [{"asset_class": "equity", "percent": "60"}],
            },
            format="json",
        )

        self.assertEqual(partial.status_code, status.HTTP_400_BAD_REQUEST, partial.data)
        self.assertEqual(self.position.class_breakdown.count(), 2)

        cleared = self.client.post(
            f"/api/portfolio/positions/{self.position.id}/confirm-setup/",
            {
                "tracking_style": "value_based",
                "history_mode": "reconstructed",
                "class_breakdown": [],
            },
            format="json",
        )

        self.assertEqual(cleared.status_code, status.HTTP_200_OK, cleared.data)
        self.assertEqual(self.position.class_breakdown.count(), 0)

    def book_investment(self, **overrides):
        payload = {
            "movement_type": "investment",
            "investment_direction": "inflow",
            "booking_date": "2025-02-01",
            "value_date": "2025-02-01",
            "description": "Compra Fondo Global",
            "amount": "100.00",
            "account_id": self.cash_account.id,
            "counterparty_account_id": self.position_account.id,
        }
        payload.update(overrides)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/accounting/transactions/quick-entry/", payload, format="json"
            )
        return response

    def test_investment_booked_in_accounting_leaves_the_portfolio_operation_record(self):
        # Registrar dinero es cosa de Contabilidad, así que un aporte hecho allí tiene que
        # dejar el mismo rastro de operación que dejaba el formulario de la cartera: sin
        # esto, una posición seguida por unidades pierde cuántas movió cada compra.
        response = self.book_investment(
            investment_units="1.250000000000",
            investment_unit_price="80.000000000000",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        trade = PortfolioTrade.objects.get(ledger_transaction_id=response.data["id"])
        self.assertEqual(trade.position_id, self.position.id)
        self.assertEqual(trade.operation_type, PortfolioTrade.OperationType.BUY)
        self.assertEqual(trade.units, Decimal("1.250000000000"))
        self.assertEqual(trade.unit_price, Decimal("80.000000000000"))
        self.assertEqual(trade.gross_amount, Decimal("100.00"))

    def test_withdrawal_booked_in_accounting_is_recorded_as_a_sale(self):
        response = self.book_investment(
            investment_direction="outflow",
            booking_date="2025-03-01",
            value_date="2025-03-01",
            description="Venta parcial",
            amount="40.00",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        trade = PortfolioTrade.objects.get(ledger_transaction_id=response.data["id"])
        self.assertEqual(trade.operation_type, PortfolioTrade.OperationType.SELL)
        self.assertIsNone(trade.units)

    def test_investment_between_accounts_outside_the_portfolio_records_nothing(self):
        outside = LedgerAccount.objects.create(
            user=self.user,
            name="Otro broker",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )

        response = self.book_investment(
            counterparty_account_id=outside.id, description="Aporte fuera de cartera"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertFalse(
            PortfolioTrade.objects.filter(ledger_transaction_id=response.data["id"]).exists()
        )

    def fixture(self, filename: str) -> bytes:
        content = (self.fixtures_path / filename).read_text(encoding="utf-8")
        return (
            content.replace("POSITION_ID", str(self.position.id))
            .replace("CASH_ACCOUNT_ID", str(self.cash_link.id))
            .encode()
        )
