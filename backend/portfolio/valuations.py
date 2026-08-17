from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

from django.db.models import Case, F, IntegerField, Value, When
from django.utils import timezone

from accounting.models import LedgerEntry, LedgerTransaction
from accounting.services_ledger import get_account_balance
from net_worth.models import AssetValuation

from .models import (
    Instrument,
    InstrumentPrice,
    InstrumentProviderMapping,
    PortfolioPosition,
    PositionValuation,
)

STALE_DAYS_BY_INSTRUMENT_TYPE = {
    Instrument.InstrumentType.STOCK: 3,
    Instrument.InstrumentType.ETF: 3,
    Instrument.InstrumentType.CRYPTO: 3,
    Instrument.InstrumentType.FUND: 10,
    Instrument.InstrumentType.PENSION_PLAN: 45,
    Instrument.InstrumentType.DEPOSIT: 35,
    Instrument.InstrumentType.CROWDFUNDING: 90,
    Instrument.InstrumentType.CASH: 3,
    Instrument.InstrumentType.OTHER: 30,
}


def stale_days_for_position(position: PortfolioPosition) -> int:
    return int(STALE_DAYS_BY_INSTRUMENT_TYPE.get(position.instrument.instrument_type, 30))


def import_legacy_position_valuations(*, position: PortfolioPosition) -> int:
    created = 0
    valuations = AssetValuation.objects.filter(
        user=position.portfolio.user,
        asset=position.asset,
    ).order_by("valuation_date", "id")
    for valuation in valuations:
        _, was_created = PositionValuation.objects.get_or_create(
            legacy_asset_valuation=valuation,
            defaults={
                "position": position,
                "valuation_date": valuation.valuation_date,
                "value": valuation.value,
                "currency": position.asset.currency,
                "source": PositionValuation.Source.LEGACY_ASSET,
                "note": "Derivada de AssetValuation; la fuente legacy no se modifica.",
            },
        )
        created += int(was_created)
    if position.ledger_account_id:
        entries = (
            LedgerEntry.objects.filter(
                account_id=position.ledger_account_id,
                transaction__user=position.portfolio.user,
                transaction__status=cast(str, LedgerTransaction.Status.POSTED),
            )
            .select_related("transaction")
            .order_by("transaction__booking_date", "transaction_id", "id")
        )

        balance = Decimal("0")
        current_transaction = None

        def persist_revaluation(ledger_transaction) -> None:
            nonlocal created
            if (
                ledger_transaction is None
                or ledger_transaction.quick_entry_kind
                != LedgerTransaction.QuickEntryKind.REVALUATION
                or balance < 0
            ):
                return
            _, was_created = PositionValuation.objects.update_or_create(
                position=position,
                valuation_date=ledger_transaction.booking_date,
                source=PositionValuation.Source.LEGACY_LEDGER,
                defaults={
                    "value": balance,
                    "currency": position.ledger_account.currency,
                    "legacy_asset_valuation": None,
                    "legacy_ledger_transaction": ledger_transaction,
                    "note": "Derivada del saldo tras revalorización; el ledger no se modifica.",
                },
            )
            created += int(was_created)

        for entry in entries:
            if current_transaction is not None and entry.transaction_id != current_transaction.id:
                persist_revaluation(current_transaction)
            current_transaction = entry.transaction
            if entry.side == LedgerEntry.Side.DEBIT:
                balance += entry.amount
            else:
                balance -= entry.amount
        persist_revaluation(current_transaction)
    return created


def sync_ledger_valuations(*, position: PortfolioPosition) -> int:
    """Rebuild the derived valuations of a position from its current ledger revaluations.

    Accounting is the monetary source of truth, so a derived valuation must not survive
    the revaluation that produced it: rows are re-imported and any that no longer match a
    posted revaluation on the same date are dropped. Manual valuations are never touched.
    """
    created = import_legacy_position_valuations(position=position)
    PositionValuation.objects.filter(
        position=position,
        source=PositionValuation.Source.LEGACY_LEDGER,
    ).exclude(
        legacy_ledger_transaction__quick_entry_kind=LedgerTransaction.QuickEntryKind.REVALUATION,
        legacy_ledger_transaction__status=LedgerTransaction.Status.POSTED,
        legacy_ledger_transaction__booking_date=F("valuation_date"),
    ).delete()
    return created


def import_all_legacy_position_valuations() -> int:
    return sum(
        import_legacy_position_valuations(position=position)
        for position in PortfolioPosition.objects.select_related("portfolio", "asset").all()
    )


def _latest_total_valuation(
    *, position: PortfolioPosition, as_of_date: date
) -> PositionValuation | None:
    return (
        PositionValuation.objects.filter(
            position=position,
            valuation_date__lte=as_of_date,
        )
        .annotate(
            source_priority=Case(
                When(source=PositionValuation.Source.MANUAL, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("-valuation_date", "source_priority", "-id")
        .first()
    )


def _latest_instrument_price(
    *, position: PortfolioPosition, as_of_date: date
) -> InstrumentPrice | None:
    return (
        InstrumentPrice.objects.filter(
            instrument=position.instrument,
            price_date__lte=as_of_date,
        )
        .select_related("provider_mapping")
        .order_by("-price_date", "-fetched_at", "-id")
        .first()
    )


def resolve_position_valuation(
    *, position: PortfolioPosition, as_of_date: date | None = None
) -> dict:
    resolved_date = as_of_date or timezone.localdate()
    threshold_days = stale_days_for_position(position)
    total_valuation = _latest_total_valuation(position=position, as_of_date=resolved_date)
    price = _latest_instrument_price(position=position, as_of_date=resolved_date)
    can_use_price = (
        position.tracking_style == PortfolioPosition.TrackingStyle.UNITS_BASED
        and position.ledger_account_id is not None
        and price is not None
        and (total_valuation is None or price.price_date >= total_valuation.valuation_date)
    )
    if can_use_price and price is not None and position.ledger_account is not None:
        units = get_account_balance(
            account=position.ledger_account,
            as_of_date=resolved_date,
            status=cast(str, LedgerTransaction.Status.POSTED),
        )
        observed_on = price.price_date
        age_days = (resolved_date - observed_on).days
        return {
            "status": "fresh" if age_days <= threshold_days else "stale",
            "value": str(units * price.close),
            "currency": price.currency,
            "observed_on": observed_on.isoformat(),
            "age_days": age_days,
            "stale_after_days": threshold_days,
            "provenance": {
                "kind": "automatic_price",
                "source": price.source,
                "source_key": price.source_key,
                "source_market": price.source_market or None,
                "fetched_at": price.fetched_at.isoformat(),
                "calculation": "ledger_units_x_close",
                "units": str(units),
                "close": str(price.close),
            },
        }
    if total_valuation is not None:
        observed_on = total_valuation.valuation_date
        age_days = (resolved_date - observed_on).days
        return {
            "status": "fresh" if age_days <= threshold_days else "stale",
            "value": str(total_valuation.value),
            "currency": total_valuation.currency,
            "observed_on": observed_on.isoformat(),
            "age_days": age_days,
            "stale_after_days": threshold_days,
            "provenance": {
                "kind": "total_valuation",
                "source": total_valuation.source,
                "legacy_asset_valuation_id": total_valuation.legacy_asset_valuation_id,
                "legacy_ledger_transaction_id": total_valuation.legacy_ledger_transaction_id,
                "note": total_valuation.note or None,
            },
        }
    return {
        "status": "missing",
        "value": None,
        "currency": None,
        "observed_on": None,
        "age_days": None,
        "stale_after_days": threshold_days,
        "provenance": None,
    }


def build_valuation_health(*, user) -> dict:
    positions = list(
        PortfolioPosition.objects.filter(portfolio__user=user)
        .select_related("portfolio", "asset", "instrument", "ledger_account")
        .order_by("id")
    )
    rows = []
    counts = {"fresh": 0, "stale": 0, "missing": 0}
    for position in positions:
        valuation = resolve_position_valuation(position=position)
        counts[valuation["status"]] += 1
        mappings = InstrumentProviderMapping.objects.filter(instrument=position.instrument)
        confirmed_mapping = mappings.filter(is_confirmed=True).first()
        if (
            position.instrument.instrument_type
            in {
                Instrument.InstrumentType.STOCK,
                Instrument.InstrumentType.ETF,
                Instrument.InstrumentType.CRYPTO,
            }
            and confirmed_mapping is None
        ):
            price_issue = "mapping_missing"
        elif (
            confirmed_mapping
            and not InstrumentPrice.objects.filter(provider_mapping=confirmed_mapping).exists()
        ):
            price_issue = "price_missing"
        else:
            price_issue = None
        rows.append(
            {
                "position_id": position.id,
                "instrument_id": position.instrument_id,
                "instrument_name": position.instrument.name,
                "tracking_style": position.tracking_style,
                "mapping": (
                    {
                        "id": confirmed_mapping.id,
                        "provider": confirmed_mapping.provider,
                        "provider_symbol": confirmed_mapping.provider_symbol,
                        "provider_market": confirmed_mapping.provider_market or None,
                        "quote_currency": confirmed_mapping.quote_currency,
                    }
                    if confirmed_mapping
                    else None
                ),
                "price_issue": price_issue,
                "valuation": valuation,
            }
        )
    overall_status = "ready"
    if counts["missing"] or any(row["price_issue"] for row in rows):
        overall_status = "needs_review"
    elif counts["stale"]:
        overall_status = "stale"
    return {
        "status": overall_status,
        "position_count": len(rows),
        "counts": counts,
        "positions": rows,
    }
