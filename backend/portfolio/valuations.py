from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

from django.db.models import Case, F, IntegerField, Value, When
from django.utils import timezone

from accounting.models import LedgerEntry, LedgerTransaction
from accounting.services_ledger import get_account_balance
from core.models import FxRate
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


def _fresher_fx_quote(
    *, position: PortfolioPosition, as_of_date: date, price: InstrumentPrice
) -> FxRate | None:
    """La misma cotizacion, si llego por el otro camino y es mas reciente.

    Un bitcoin tiene un unico precio, pero entra en Core por dos puertas: como precio de
    instrumento del proveedor de mercado y como tipo de cambio BTC->EUR. Actualizar el
    cambio desde Patrimonio solo escribia la segunda, asi que la misma posicion valia una
    cosa en Patrimonio y otra en Cartera hasta que el worker pasaba. Se toma la mas
    fresca de las dos y se dice de donde vino.
    """
    unit = position.ledger_account.currency if position.ledger_account is not None else ""
    if not unit or unit == price.currency:
        return None
    row = (
        FxRate.objects.filter(
            from_currency=unit,
            to_currency=price.currency,
            rate_date__lte=as_of_date,
            rate_date__gt=price.price_date,
        )
        .order_by("-rate_date")
        .first()
    )
    return row


def _ledger_carrying_value(
    *, position: PortfolioPosition, as_of_date: date
) -> tuple[Decimal, date] | None:
    """Carrying value of a value-based position taken from its own ledger account.

    Contributions and income are flows, not valuations, so a position funded only through
    accounting ends up with no declared value at all. For a value-tracked position the
    posted balance is still its carrying value, which beats reporting nothing and dropping
    the position out of the portfolio total. Units-based positions are excluded: their
    account holds units, not money.
    """
    if (
        position.tracking_style != PortfolioPosition.TrackingStyle.VALUE_BASED
        or position.ledger_account is None
    ):
        return None
    last_movement = (
        LedgerEntry.objects.filter(
            account_id=position.ledger_account_id,
            transaction__status=cast(str, LedgerTransaction.Status.POSTED),
            transaction__booking_date__lte=as_of_date,
        )
        .order_by("-transaction__booking_date")
        .values_list("transaction__booking_date", flat=True)
        .first()
    )
    if last_movement is None:
        return None
    balance = get_account_balance(
        account=position.ledger_account,
        as_of_date=as_of_date,
        status=cast(str, LedgerTransaction.Status.POSTED),
    )
    return balance, last_movement


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
        fx = _fresher_fx_quote(position=position, as_of_date=resolved_date, price=price)
        close = fx.rate if fx is not None else price.close
        observed_on = fx.rate_date if fx is not None else price.price_date
        age_days = (resolved_date - observed_on).days
        fetched_at = (
            (fx.last_synced_at or fx.updated_at).isoformat()
            if fx is not None
            else price.fetched_at.isoformat()
        )
        return {
            "status": "fresh" if age_days <= threshold_days else "stale",
            "value": str(units * close),
            "currency": price.currency,
            "observed_on": observed_on.isoformat(),
            "age_days": age_days,
            "stale_after_days": threshold_days,
            "provenance": {
                "kind": "automatic_price",
                "source": fx.source if fx is not None else price.source,
                "source_key": (
                    f"{fx.from_currency}->{fx.to_currency}" if fx is not None else price.source_key
                ),
                "source_market": None if fx is not None else (price.source_market or None),
                "fetched_at": fetched_at,
                "calculation": "ledger_units_x_close",
                "units": str(units),
                "close": str(close),
            },
        }
    if total_valuation is not None:
        carrying = _ledger_carrying_value(position=position, as_of_date=resolved_date)
        if (
            carrying is not None
            and carrying[0] == 0
            and carrying[1] >= total_valuation.valuation_date
        ):
            # Fully divested after that valuation was taken: the holding is gone, so the
            # old number no longer describes anything. Mirrors `performance._divested_at`.
            divested_on = carrying[1]
            return {
                "status": "fresh",
                "value": "0",
                "currency": position.ledger_account.currency
                if position.ledger_account is not None
                else total_valuation.currency,
                "observed_on": divested_on.isoformat(),
                "age_days": (resolved_date - divested_on).days,
                "stale_after_days": threshold_days,
                "provenance": {
                    "kind": "divested",
                    "source": "accounting",
                    "calculation": "posted_account_balance",
                    "note": "Posición desinvertida; el saldo contable quedó a cero.",
                },
            }
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
    carrying = _ledger_carrying_value(position=position, as_of_date=resolved_date)
    if carrying is not None and position.ledger_account is not None:
        balance, observed_on = carrying
        age_days = (resolved_date - observed_on).days
        return {
            # A balance is current by definition, so it is never stale; what is missing
            # is a valuation. Mirrors `performance._value_status`.
            "status": "at_cost",
            "value": str(balance),
            "currency": position.ledger_account.currency,
            "observed_on": observed_on.isoformat(),
            "age_days": age_days,
            "stale_after_days": threshold_days,
            "provenance": {
                "kind": "ledger_balance",
                "source": "accounting",
                "calculation": "posted_account_balance",
                "note": "Saldo contable de la posición; todavía no hay valoración declarada.",
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
    counts = {"fresh": 0, "stale": 0, "missing": 0, "at_cost": 0}
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
