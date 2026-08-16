from decimal import Decimal

from django.db import migrations


def import_ledger_revaluation_history(apps, schema_editor):
    LedgerEntry = apps.get_model("accounting", "LedgerEntry")
    PortfolioPosition = apps.get_model("portfolio", "PortfolioPosition")
    PositionValuation = apps.get_model("portfolio", "PositionValuation")

    positions = PortfolioPosition.objects.exclude(ledger_account_id=None).select_related(
        "ledger_account"
    )
    for position in positions:
        entries = (
            LedgerEntry.objects.filter(
                account_id=position.ledger_account_id,
                transaction__status="posted",
            )
            .select_related("transaction")
            .order_by("transaction__booking_date", "transaction_id", "id")
        )
        balance = Decimal("0")
        current_transaction = None

        def persist_revaluation(transaction, current_balance):
            if (
                transaction is None
                or transaction.quick_entry_kind != "revaluation"
                or current_balance < 0
            ):
                return
            PositionValuation.objects.update_or_create(
                position_id=position.id,
                valuation_date=transaction.booking_date,
                source="legacy_ledger",
                defaults={
                    "value": current_balance,
                    "currency": position.ledger_account.currency,
                    "legacy_asset_valuation_id": None,
                    "legacy_ledger_transaction_id": transaction.id,
                    "note": "Derivada del saldo tras revalorización; el ledger no se modifica.",
                },
            )

        for entry in entries:
            if current_transaction is not None and entry.transaction_id != current_transaction.id:
                persist_revaluation(current_transaction, balance)
            current_transaction = entry.transaction
            if entry.side == "debit":
                balance += entry.amount
            else:
                balance -= entry.amount
        persist_revaluation(current_transaction, balance)


class Migration(migrations.Migration):
    dependencies = [
        (
            "portfolio",
            "0006_remove_positionvaluation_portfolio_position_valuation_source_valid_and_more",
        )
    ]

    operations = [
        migrations.RunPython(import_ledger_revaluation_history, migrations.RunPython.noop),
    ]
