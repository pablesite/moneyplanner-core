import os

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from datetime import date

from django.core.exceptions import ValidationError

from django.utils import timezone

from .models import FxRate, InflationIndex


def _quantize_2(amount: Decimal) -> Decimal:
    # Redondeo estándar financiero a 2 decimales (v1).
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def normalize_currency_code(value: str | None) -> str:
    return (value or "").upper().strip()


def validate_fx_currency_pair(*, from_currency: str, to_currency: str) -> None:
    if len(from_currency) != 3 or len(to_currency) != 3:
        raise ValidationError("Moneda invalida. Usa codigos ISO de 3 letras.")


def validate_inflation_period_start(*, period: date) -> None:
    if period.day != 1:
        raise ValidationError("El periodo debe ser el primer dia del mes (YYYY-MM-01).")


def _month_start(d) -> timezone.datetime.date:
    # Normaliza a primer día del mes (YYYY-MM-01)
    return d.replace(day=1)


def _normalize_month_start(d) -> date:
    """
    Acepta date o string YYYY-MM-DD y lo normaliza a YYYY-MM-01.
    """
    if isinstance(d, str):
        # Python 3.11+: date.fromisoformat
        d = date.fromisoformat(d)
    if not isinstance(d, date):
        raise ValidationError("Invalid period_month type. Expected date or ISO string.")
    return d.replace(day=1)


def _get_inflation_index(region: str, period_month) -> Decimal:
    """
    Devuelve el índice del mes 'period_month' (YYYY-MM-01) con fallback:

    1) último índice con period <= period_month
    2) si no existe (period_month anterior al primer dato), usa el primer índice disponible
    """
    region = (region or "").strip()
    if not region:
        raise ValidationError("Region is required.")

    period_month = _normalize_month_start(period_month)

    # 1) Fallback hacia atrás (último conocido anterior)
    row = (
        InflationIndex.objects.filter(region=region, period__lte=period_month)
        .order_by("-period")
        .first()
    )
    if row:
        return Decimal(row.index)

    # 2) Si period_month es anterior al primer dato, usamos el primer dato disponible
    first_row = InflationIndex.objects.filter(region=region).order_by("period").first()
    if first_row:
        return Decimal(first_row.index)

    # No hay IPC cargado para esa región
    raise ValidationError(f"Missing inflation index for region={region}.")


def convert_currency(amount: Decimal, from_currency: str, to_currency: str, date=None) -> Decimal:
    """
    Convierte 'amount' de from_currency a to_currency usando FxRate.

    Soporta:
    - rate directo (from->to)
    - rate inverso (to->from) usando 1/rate
    - triangulación vía pivote (por defecto USD) si no hay directo/inverso

    date:
      - si no se indica, usa hoy (timezone.localdate())
      - usa fallback: último rate conocido con rate_date <= date
    """
    if amount is None:
        raise ValidationError("Amount is required.")

    from_c = (from_currency or "").upper().strip()
    to_c = (to_currency or "").upper().strip()

    if len(from_c) != 3 or len(to_c) != 3:
        raise ValidationError("Invalid currency code.")

    if from_c == to_c:
        return _quantize_2(Decimal(amount))

    amount = Decimal(amount)
    rate_date = date or timezone.localdate()

    # 1) Directo
    direct = _fx_lookup_with_fallback(from_c, to_c, rate_date)
    if direct:
        return _quantize_2(amount * direct.rate)

    # 2) Inverso
    inverse = _fx_lookup_with_fallback(to_c, from_c, rate_date)
    if inverse:
        if inverse.rate == 0:
            raise ValidationError(f"Invalid FX rate: {to_c}->{from_c} is 0.")
        return _quantize_2(amount / inverse.rate)

    # 3) Triangulación vía pivote (por defecto USD)
    pivot = (os.getenv("FX_PIVOT", "USD") or "USD").upper().strip()
    if pivot in (from_c, to_c):
        # si el pivote coincide, no hay ruta adicional que probar aquí
        raise ValidationError(f"Missing FX rate for {from_c}->{to_c} on or before {rate_date}.")

    # Buscar from -> pivot (directo o inverso)
    leg1 = _fx_lookup_with_fallback(from_c, pivot, rate_date)
    leg1_inv = None
    if not leg1:
        leg1_inv = _fx_lookup_with_fallback(pivot, from_c, rate_date)

    # Buscar pivot -> to (directo o inverso)
    leg2 = _fx_lookup_with_fallback(pivot, to_c, rate_date)
    leg2_inv = None
    if not leg2:
        leg2_inv = _fx_lookup_with_fallback(to_c, pivot, rate_date)

    if (leg1 or leg1_inv) and (leg2 or leg2_inv):
        # calcular factor de conversión leg1
        if leg1:
            if leg1.rate == 0:
                raise ValidationError(f"Invalid FX rate: {from_c}->{pivot} is 0.")
            factor1 = leg1.rate
        else:
            if leg1_inv.rate == 0:
                raise ValidationError(f"Invalid FX rate: {pivot}->{from_c} is 0.")
            factor1 = Decimal("1") / leg1_inv.rate

        # calcular factor de conversión leg2
        if leg2:
            if leg2.rate == 0:
                raise ValidationError(f"Invalid FX rate: {pivot}->{to_c} is 0.")
            factor2 = leg2.rate
        else:
            if leg2_inv.rate == 0:
                raise ValidationError(f"Invalid FX rate: {to_c}->{pivot} is 0.")
            factor2 = Decimal("1") / leg2_inv.rate

        return _quantize_2(amount * factor1 * factor2)

    raise ValidationError(f"Missing FX rate for {from_c}->{to_c} on or before {rate_date}.")


# ---------------------------------------------------------------------------
# Detailed conversion (precision-aware, with metadata + on-demand sync)
# ---------------------------------------------------------------------------


@dataclass
class FxConversion:
    """Result of a precision-aware currency conversion.

    ``resolution`` indicates how the rate was obtained:
    - ``same``: source and target currency are identical (rate 1).
    - ``exact``: a quote exists for the requested date.
    - ``synced``: the quote was fetched on demand for the requested date.
    - ``fallback``: no quote for that date; nearest earlier quote was used.
    """

    amount: Decimal
    from_currency: str
    to_currency: str
    converted: Decimal
    rate: Decimal
    rate_date: date | None
    resolution: str


def _quantize_8(amount: Decimal) -> Decimal:
    # Hasta 8 decimales: suficiente para cripto (BTC, ETH...) y fiat.
    return amount.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def _quantize_rate(rate: Decimal) -> Decimal:
    # El tipo efectivo puede venir de una división (inverso/triangulación).
    return rate.quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_UP)


def _fx_effective_rate(from_c: str, to_c: str, rate_date: date) -> tuple[Decimal, date] | None:
    """Tipo efectivo from->to y la fecha del quote usado (directo/inverso/triangulación)."""
    direct = _fx_lookup_with_fallback(from_c, to_c, rate_date)
    if direct:
        return Decimal(direct.rate), direct.rate_date
    inverse = _fx_lookup_with_fallback(to_c, from_c, rate_date)
    if inverse and inverse.rate != 0:
        return Decimal("1") / Decimal(inverse.rate), inverse.rate_date

    pivot = (os.getenv("FX_PIVOT", "USD") or "USD").upper().strip()
    if pivot in (from_c, to_c):
        return None
    leg1 = _fx_lookup_with_fallback(from_c, pivot, rate_date)
    leg1_inv = None if leg1 else _fx_lookup_with_fallback(pivot, from_c, rate_date)
    leg2 = _fx_lookup_with_fallback(pivot, to_c, rate_date)
    leg2_inv = None if leg2 else _fx_lookup_with_fallback(to_c, pivot, rate_date)
    if (leg1 or leg1_inv) and (leg2 or leg2_inv):
        factor1 = Decimal(leg1.rate) if leg1 else Decimal("1") / Decimal(leg1_inv.rate)
        factor2 = Decimal(leg2.rate) if leg2 else Decimal("1") / Decimal(leg2_inv.rate)
        leg_dates = [row.rate_date for row in (leg1, leg1_inv, leg2, leg2_inv) if row]
        return factor1 * factor2, min(leg_dates)
    return None


def _ensure_fx_for_date(from_c: str, to_c: str, rate_date: date) -> bool:
    """Pide al módulo de market data el quote del par/fecha (best-effort).

    No propaga errores de red/proveedor: si falla, el llamador cae al fallback.
    """
    try:
        from .market_data import (
            SUPPORTED_CRYPTO_IDS,
            sync_crypto_history,
            sync_fiat_history,
        )

        if from_c in SUPPORTED_CRYPTO_IDS or to_c in SUPPORTED_CRYPTO_IDS:
            crypto = from_c if from_c in SUPPORTED_CRYPTO_IDS else to_c
            fiat = to_c if crypto == from_c else from_c
            sync_crypto_history(
                from_currency=crypto, to_currency=fiat, start_date=rate_date, end_date=rate_date
            )
        else:
            sync_fiat_history(
                from_currency=from_c, to_currency=to_c, start_date=rate_date, end_date=rate_date
            )
        return True
    except Exception:
        return False


def convert_currency_detailed(
    amount: Decimal,
    from_currency: str,
    to_currency: str,
    *,
    on_date: date | None = None,
    allow_sync: bool = True,
) -> FxConversion:
    """Convierte preservando precisión (hasta 8 decimales) y devuelve metadatos.

    Resuelve el tipo de la ``on_date`` (devengo). Si no hay quote ese día y
    ``allow_sync``, pide al módulo de market data que lo obtenga; si sigue sin
    estar disponible, usa el quote anterior más cercano (fallback).
    """
    if amount is None:
        raise ValidationError("Amount is required.")
    from_c = (from_currency or "").upper().strip()
    to_c = (to_currency or "").upper().strip()
    if len(from_c) != 3 or len(to_c) != 3:
        raise ValidationError("Invalid currency code.")

    amount = Decimal(amount)
    if from_c == to_c:
        return FxConversion(
            amount=amount,
            from_currency=from_c,
            to_currency=to_c,
            converted=_quantize_8(amount),
            rate=Decimal("1"),
            rate_date=None,
            resolution="same",
        )

    rate_date = on_date or timezone.localdate()
    resolved = _fx_effective_rate(from_c, to_c, rate_date)
    resolution: str | None = None

    if (resolved is None or resolved[1] != rate_date) and allow_sync:
        if _ensure_fx_for_date(from_c, to_c, rate_date):
            synced = _fx_effective_rate(from_c, to_c, rate_date)
            if synced and synced[1] == rate_date:
                resolved = synced
                resolution = "synced"

    if resolved is None:
        raise ValidationError(f"Missing FX rate for {from_c}->{to_c} on or before {rate_date}.")

    rate, used_date = resolved
    if resolution is None:
        resolution = "exact" if used_date == rate_date else "fallback"

    return FxConversion(
        amount=amount,
        from_currency=from_c,
        to_currency=to_c,
        converted=_quantize_8(amount * rate),
        rate=_quantize_rate(rate),
        rate_date=used_date,
        resolution=resolution,
    )


def refresh_currency_rate(
    from_currency: str,
    to_currency: str,
    *,
    on_date: date | None = None,
) -> FxConversion:
    """Force a provider refresh for one FX pair and return its effective quote."""
    from_c = (from_currency or "").upper().strip()
    to_c = (to_currency or "").upper().strip()
    if len(from_c) != 3 or len(to_c) != 3:
        raise ValidationError("Invalid currency code.")

    target_date = on_date or timezone.localdate()
    if from_c != to_c and not _ensure_fx_for_date(from_c, to_c, target_date):
        raise ValidationError(f"Could not refresh FX rate for {from_c}->{to_c}.")

    conversion = convert_currency_detailed(
        Decimal("1"), from_c, to_c, on_date=target_date, allow_sync=False
    )
    if conversion.rate_date not in (None, target_date):
        raise ValidationError(f"No current FX rate available for {from_c}->{to_c}.")
    return conversion


# ---------------------------------------------------------------------------
# Bulk FX cache for timeline-style loops
# ---------------------------------------------------------------------------


def build_fx_cache(currencies: set[str]) -> dict[tuple[str, str], list[tuple[date, Decimal]]]:
    """
    Bulk-load all FxRate rows involving the given currencies into an in-memory
    lookup.  Returns ``{(from, to): [(rate_date, rate), ...]}`` sorted
    descending by ``rate_date`` so that a linear scan finds the latest rate
    <= a target date quickly.
    """
    if not currencies:
        return {}
    rows = (
        FxRate.objects.filter(from_currency__in=currencies, to_currency__in=currencies)
        .order_by("from_currency", "to_currency", "-rate_date")
        .values_list("from_currency", "to_currency", "rate_date", "rate")
    )
    cache: dict[tuple[str, str], list[tuple[date, Decimal]]] = {}
    for from_c, to_c, rd, rate in rows:
        cache.setdefault((from_c, to_c), []).append((rd, Decimal(rate)))
    return cache


def _cache_lookup(
    cache: dict[tuple[str, str], list[tuple[date, Decimal]]],
    from_c: str,
    to_c: str,
    rate_date: date,
) -> Decimal | None:
    """
    Return the latest rate <= *rate_date* from the cache.

    If *rate_date* is older than the earliest known row, fallback to the
    earliest available rate for that pair to avoid hard failures on very old
    timelines with partial FX history.
    """
    entries = cache.get((from_c, to_c))
    if not entries:
        return None
    # entries are sorted descending by date
    for rd, rate in entries:
        if rd <= rate_date:
            return rate
    return entries[-1][1]


def _fx_lookup_with_fallback(from_c: str, to_c: str, rate_date: date):
    """
    Lookup an FX row with the same fallback semantics as cached conversions:
    latest <= rate_date, or earliest available if the requested date is older
    than the first known quote.
    """
    row = (
        FxRate.objects.filter(
            from_currency=from_c,
            to_currency=to_c,
            rate_date__lte=rate_date,
        )
        .order_by("-rate_date")
        .first()
    )
    if row:
        return row
    return (
        FxRate.objects.filter(
            from_currency=from_c,
            to_currency=to_c,
        )
        .order_by("rate_date")
        .first()
    )


def convert_currency_cached(
    amount: Decimal,
    from_currency: str,
    to_currency: str,
    *,
    rate_date: date,
    fx_cache: dict[tuple[str, str], list[tuple[date, Decimal]]],
) -> Decimal:
    """Like ``convert_currency`` but resolves rates from *fx_cache*."""
    if amount is None:
        raise ValidationError("Amount is required.")

    from_c = (from_currency or "").upper().strip()
    to_c = (to_currency or "").upper().strip()

    if len(from_c) != 3 or len(to_c) != 3:
        raise ValidationError("Invalid currency code.")

    if from_c == to_c:
        return _quantize_2(Decimal(amount))

    amount = Decimal(amount)

    # 1) Direct
    rate = _cache_lookup(fx_cache, from_c, to_c, rate_date)
    if rate is not None:
        return _quantize_2(amount * rate)

    # 2) Inverse
    rate = _cache_lookup(fx_cache, to_c, from_c, rate_date)
    if rate is not None:
        if rate == 0:
            raise ValidationError(f"Invalid FX rate: {to_c}->{from_c} is 0.")
        return _quantize_2(amount / rate)

    # 3) Triangulation via pivot
    pivot = (os.getenv("FX_PIVOT", "USD") or "USD").upper().strip()
    if pivot in (from_c, to_c):
        raise ValidationError(f"Missing FX rate for {from_c}->{to_c} on or before {rate_date}.")

    leg1 = _cache_lookup(fx_cache, from_c, pivot, rate_date)
    leg1_inv = None if leg1 is not None else _cache_lookup(fx_cache, pivot, from_c, rate_date)

    leg2 = _cache_lookup(fx_cache, pivot, to_c, rate_date)
    leg2_inv = None if leg2 is not None else _cache_lookup(fx_cache, to_c, pivot, rate_date)

    if (leg1 is not None or leg1_inv is not None) and (leg2 is not None or leg2_inv is not None):
        if leg1 is not None:
            factor1 = leg1
        else:
            if leg1_inv == 0:
                raise ValidationError(f"Invalid FX rate: {pivot}->{from_c} is 0.")
            factor1 = Decimal("1") / leg1_inv

        if leg2 is not None:
            factor2 = leg2
        else:
            if leg2_inv == 0:
                raise ValidationError(f"Invalid FX rate: {to_c}->{pivot} is 0.")
            factor2 = Decimal("1") / leg2_inv

        return _quantize_2(amount * factor1 * factor2)

    raise ValidationError(f"Missing FX rate for {from_c}->{to_c} on or before {rate_date}.")


def get_latest_inflation_period(region: str = InflationIndex.Region.ES):
    row = InflationIndex.objects.filter(region=region).order_by("-period").first()
    if not row:
        raise ValidationError(f"Missing inflation index for region={region}.")
    return row.period


def adjust_for_inflation(
    amount: Decimal,
    date=None,
    region: str = InflationIndex.Region.ES,
    base_period=None,
) -> Decimal:
    """
    Convierte un valor nominal en 'date' a euros constantes del 'base_period' (mes base).

    Fórmula:
      real = nominal * (index_base / index_date)

    - date: si None -> hoy
    - base_period: si None -> último índice disponible (más reciente) para esa región
    - Fallback: si falta índice exacto, usa el último anterior.
    """
    if amount is None:
        raise ValidationError("Amount is required.")

    amount = Decimal(amount)
    d = date or timezone.localdate()
    d_month = _month_start(d)

    if base_period is None:
        base_row = InflationIndex.objects.filter(region=region).order_by("-period").first()
        if not base_row:
            raise ValidationError(f"Missing inflation index for region={region}.")
        base_month = base_row.period
        index_base = Decimal(base_row.index)
    else:
        base_month = _month_start(base_period)
        index_base = _get_inflation_index(region, base_month)

    index_date = _get_inflation_index(region, d_month)

    if index_date == 0:
        raise ValidationError(f"Invalid inflation index: region={region} period={d_month} is 0.")

    real = amount * (index_base / index_date)
    return _quantize_2(real)
