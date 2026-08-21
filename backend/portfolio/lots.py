"""Titularidad por lotes de una posicion mezclada.

Una posicion vive en un contenedor y hasta ahora declaraba su titularidad en tramos: un
porcentaje del valor, valido entre dos fechas. Eso basta cuando algo es de alguien y punto,
pero no sabe contar un bote comun. Si compras bitcoin con una cuenta compartida durante dos
anos y luego sigues comprando con la tuya sin separar las monedas, ningun porcentaje fijo
describe lo que hay dentro: la proporcion cambia con cada compra, y ademas se mueve sola con
el precio aunque no compres nada, porque un porcentaje del valor no es una cantidad de
monedas.

Aqui se cuentan monedas. Cada entrada al bote va al bolsillo de la titularidad que la pago,
y cada salida sale del bolsillo que la retiro. Ambas cosas las dice el asiento contable
—`LedgerTransaction.ownership_id`—, asi que no hace falta inventar ninguna regla de reparto:
se le pregunta al dato. La participacion de alguien en un momento dado es la suma de lo que
hay en los bolsillos donde participa, dividida por lo que hay en el bote.

Lo que no cuadra no se disimula. Si una retirada saca mas de lo que su bolsillo tenia
—porque el historico se etiqueto a mano y a veces no cuadra al satoshi— el sobrante se
reparte a prorrata entre el resto y queda anotado en `unreconciled`, para que se pueda
mirar en lugar de aparecer como una participacion que nadie ha decidido.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

ZERO = Decimal("0")


@dataclass(frozen=True)
class UnitMovement:
    """Un movimiento de unidades del bote, con quien lo hizo."""

    on_date: date
    units: Decimal
    ownership_id: int | None


@dataclass
class OwnershipPockets:
    """Cuantas unidades tiene cada titularidad dentro del bote, dia a dia."""

    dates: list[date] = field(default_factory=list)
    states: list[dict[int, Decimal]] = field(default_factory=list)
    unreconciled: Decimal = ZERO

    def at(self, target: date) -> dict[int, Decimal]:
        index = bisect_right(self.dates, target) - 1
        return self.states[index] if index >= 0 else {}


def _drain(pockets: dict[int, Decimal], amount: Decimal, preferred: int | None) -> Decimal:
    """Saca `amount` unidades, primero del bolsillo que las retira. Devuelve lo no cuadrado.

    Una retirada etiquetada saca de lo suyo: vender tus monedas no toca las de nadie mas. Lo
    que exceda su bolsillo —o una retirada sin etiquetar, que es la separacion de un bote sin
    declarar de quien sale— se reparte a prorrata, que es la unica lectura neutral cuando el
    dato no dice mas.
    """
    remaining = amount
    if preferred is not None and pockets.get(preferred, ZERO) > ZERO:
        taken = min(pockets[preferred], remaining)
        pockets[preferred] -= taken
        remaining -= taken
    if remaining <= ZERO:
        return ZERO
    total = sum(value for value in pockets.values() if value > ZERO)
    if total <= ZERO:
        # El bote esta vacio y aun se pide sacar: no hay de donde, y fingir un reparto
        # inventaria unidades negativas de alguien.
        return remaining
    shortfall = remaining
    for key in list(pockets):
        if pockets[key] <= ZERO:
            continue
        share = pockets[key] / total
        taken = min(pockets[key], shortfall * share)
        pockets[key] -= taken
        remaining -= taken
    return remaining if remaining > ZERO else ZERO


def build_pockets(movements: list[UnitMovement]) -> OwnershipPockets:
    """Reconstruye el bote movimiento a movimiento."""
    book = OwnershipPockets()
    pockets: dict[int, Decimal] = {}
    unreconciled = ZERO
    for movement in sorted(movements, key=lambda row: row.on_date):
        if movement.units > ZERO:
            key = movement.ownership_id
            if key is None:
                # Una entrada sin titularidad no se puede asignar; se reparte como el bote
                # que ya hay, y si el bote esta vacio no hay nada que decir todavia.
                total = sum(value for value in pockets.values() if value > ZERO)
                if total > ZERO:
                    for pocket in list(pockets):
                        if pockets[pocket] > ZERO:
                            pockets[pocket] += movement.units * (pockets[pocket] / total)
                else:
                    unreconciled += movement.units
            else:
                pockets[key] = pockets.get(key, ZERO) + movement.units
        elif movement.units < ZERO:
            unreconciled += _drain(pockets, -movement.units, movement.ownership_id)
        if book.dates and book.dates[-1] == movement.on_date:
            book.states[-1] = dict(pockets)
        else:
            book.dates.append(movement.on_date)
            book.states.append(dict(pockets))
    book.unreconciled = unreconciled
    return book


def member_share_at(
    *,
    pockets: OwnershipPockets,
    target: date,
    member_id: int,
    shares_by_ownership: dict[int, dict[int, Decimal]],
) -> Decimal | None:
    """Que parte del bote es de este miembro en esta fecha, o None si no hay bote.

    `shares_by_ownership` traduce cada titularidad a la fraccion que toca a cada miembro:
    una individual es todo suyo, una compartida reparte por sus porcentajes.
    """
    state = pockets.at(target)
    total = sum(value for value in state.values() if value > ZERO)
    if total <= ZERO:
        return None
    mine = ZERO
    for ownership_id, units in state.items():
        if units <= ZERO:
            continue
        fraction = shares_by_ownership.get(ownership_id, {}).get(member_id, ZERO)
        mine += units * fraction
    return mine / total
