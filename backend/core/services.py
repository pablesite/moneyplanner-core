from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from .models import FxRate


def _quantize_2(amount: Decimal) -> Decimal:
    # Redondeo estándar financiero a 2 decimales (v1).
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def convert_currency(amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
    """
    Convierte 'amount' de from_currency a to_currency usando FxRate.

    Convención FxRate:
      1 unit de from_currency = rate units de to_currency

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

    direct = FxRate.objects.filter(from_currency=from_c, to_currency=to_c).first()
    if direct:
        return _quantize_2(amount * direct.rate)

    inverse = FxRate.objects.filter(from_currency=to_c, to_currency=from_c).first()
    if inverse:
        if inverse.rate == 0:
            raise ValidationError(f"Invalid FX rate: {to_c}->{from_c} is 0.")
        return _quantize_2(amount / inverse.rate)

    raise ValidationError(f"Missing FX rate for {from_c}->{to_c}.")
