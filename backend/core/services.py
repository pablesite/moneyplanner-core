from decimal import Decimal, ROUND_HALF_UP
from datetime import date

from django.core.exceptions import ValidationError

from django.utils import timezone

from .models import FxRate, InflationIndex


def _quantize_2(amount: Decimal) -> Decimal:
    # Redondeo estándar financiero a 2 decimales (v1).
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

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
        InflationIndex.objects
        .filter(region=region, period__lte=period_month)
        .order_by("-period")
        .first()
    )
    if row:
        return Decimal(row.index)

    # 2) Si period_month es anterior al primer dato, usamos el primer dato disponible
    first_row = (
        InflationIndex.objects
        .filter(region=region)
        .order_by("period")
        .first()
    )
    if first_row:
        return Decimal(first_row.index)

    # No hay IPC cargado para esa región
    raise ValidationError(f"Missing inflation index for region={region}.")


def convert_currency(amount: Decimal, from_currency: str, to_currency: str, date=None) -> Decimal:
    """
    Convierte 'amount' de from_currency a to_currency usando FxRate.

    Convención FxRate:
      1 unit de from_currency = rate units de to_currency

    date:
      - si no se indica, usa hoy (timezone.localdate())
      - usa fallback: último rate conocido con rate_date <= date

    Soporta:
    - rate directo (from->to)
    - rate inverso (to->from) usando 1/rate
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

    direct = (
        FxRate.objects.filter(
            from_currency=from_c,
            to_currency=to_c,
            rate_date__lte=rate_date,
        )
        .order_by("-rate_date")
        .first()
    )
    if direct:
        return _quantize_2(amount * direct.rate)

    inverse = (
        FxRate.objects.filter(
            from_currency=to_c,
            to_currency=from_c,
            rate_date__lte=rate_date,
        )
        .order_by("-rate_date")
        .first()
    )
    if inverse:
        if inverse.rate == 0:
            raise ValidationError(f"Invalid FX rate: {to_c}->{from_c} is 0.")
        return _quantize_2(amount / inverse.rate)

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
