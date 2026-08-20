"""Politica de asignacion: donde quieres estar, frente a donde estas.

La cartera sabia decir donde estas. Esto anade la otra mitad —la politica— y su
diferencia, que es lo unico que convierte el seguimiento en una decision.

El ambito es una `Ownership`, no un miembro. "Lo de Pablo", "lo de Lucas" y "lo
compartido al 50%" son mandatos distintos, con horizontes distintos: una politica unica
para los tres no significaria nada. Filtrar por miembro responde a otra pregunta —que
parte economica te toca de cada posicion— y sigue siendo el filtro de titularidad.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import groupby
from datetime import date
from decimal import ROUND_DOWN, ROUND_UP, Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.db.models import Q
from django.utils import timezone

from accounting.models import LedgerAccount, LedgerTransaction
from accounting.services_quick_entry import create_quick_transaction
from budget.models import AnnualExpenseEntry
from budget.services import planned_expense_monthly_distribution

from memberships.models import Ownership, OwnershipLink

from .operations import confirm_operation
from .models import (
    AllocationStrategy,
    AllocationTarget,
    ContributionBasket,
    ContributionBasketLine,
    ContributionCommitment,
    Portfolio,
    PortfolioPosition,
)
from .performance import (
    PerformanceContext,
    _balance_at,
    _cash_value_base,
    _position_value_base,
    _to_base,
    load_performance_context,
    timeline_context_start,
)

ZERO = Decimal("0")


@dataclass(frozen=True)
class ScopeSlice:
    """Lo que una posicion aporta a una clase dentro del ambito."""

    position: PortfolioPosition
    asset_class: str
    value: Decimal


def resolve_strategy(
    *, portfolio: Portfolio, ownership: Ownership, on_date: date
) -> AllocationStrategy | None:
    """La version vigente en esa fecha, que no tiene por que ser la ultima escrita."""
    return (
        portfolio.allocation_strategies.filter(ownership=ownership, effective_from__lte=on_date)
        .order_by("-effective_from", "-id")
        .first()
    )


def _ownership_at(context: PerformanceContext, position_id: int, target: date):
    return next(
        (
            row
            for row in context.ownership_periods.get(position_id, [])
            if row.start_date <= target and (row.end_date is None or row.end_date >= target)
        ),
        None,
    )


def positions_in_scope(
    *, context: PerformanceContext, ownership_id: int, on_date: date
) -> list[PortfolioPosition]:
    """Las posiciones cuya titularidad vigente en esa fecha es la del ambito.

    Se lee del tramo vigente, no del ultimo escrito: si algo dejo de ser compartido en
    marzo, en febrero seguia siendolo y la politica de febrero le aplicaba.
    """
    selected = []
    for position in context.positions:
        if position.status == PortfolioPosition.Status.ARCHIVED:
            # Una posicion archivada esta fuera de la cartera: no recibe aportacion ni
            # arrastra la desviacion hacia un objetivo que ya no se persigue.
            continue
        period = _ownership_at(context, position.id, on_date)
        if period is not None and period.ownership_id == ownership_id:
            selected.append(position)
    return selected


def scope_slices(
    *, context: PerformanceContext, positions: list[PortfolioPosition], on_date: date
) -> list[ScopeSlice]:
    """Valor de cada posicion repartido por clase, aplicando el look-through si lo tiene."""
    slices: list[ScopeSlice] = []
    for position in positions:
        value, _ = _position_value_base(
            context=context, position=position, target=on_date, member_id=None
        )
        if value is None:
            continue
        breakdown = list(position.class_breakdown.all())
        if not breakdown:
            slices.append(ScopeSlice(position, position.effective_asset_class, value))
            continue
        for row in breakdown:
            slices.append(
                ScopeSlice(position, row.asset_class, value * row.percent / Decimal("100"))
            )
    return slices


def build_cash_value(
    *, context: PerformanceContext, on_date: date, member_id: int | None
) -> Decimal:
    """Todo el efectivo de contenedor de la cartera, en moneda base."""
    value, _ = _cash_value_base(context=context, target=on_date, member_id=member_id)
    return value or ZERO


def scope_cash(*, context: PerformanceContext, ownership: Ownership, on_date: date) -> Decimal:
    """El efectivo de contenedor que pertenece a este ambito.

    El efectivo no lleva titularidad propia, pero su activo en Patrimonio si: es de quien
    sea la cuenta. Sin esto la liquidez o no aparecia en ninguna parte —la clase marcaba
    cero teniendo dinero— o habria que sumarla a todos los ambitos y contarla varias
    veces.
    """
    asset_ids = [
        link.ledger_account.asset_id
        for link in context.cash_accounts
        if link.ledger_account.asset_id
    ]
    if not asset_ids:
        return ZERO
    owned = set(
        OwnershipLink.objects.filter(
            user=context.portfolio.user,
            target_type=OwnershipLink.TargetType.ASSET,
            target_id__in=asset_ids,
            ownership=ownership,
        ).values_list("target_id", flat=True)
    )
    total = ZERO
    for link in context.cash_accounts:
        if link.ledger_account.asset_id not in owned:
            continue
        balance = _balance_at(context, link.ledger_account_id, on_date)
        converted = _to_base(
            context=context, amount=balance, currency=link.currency, target=on_date
        )
        total += converted or ZERO
    return total


def _band_state(actual: Decimal, target: AllocationTarget | None) -> str:
    if target is None:
        return "unplanned"
    if target.min_percent is not None and actual < target.min_percent:
        return "below"
    if target.max_percent is not None and actual > target.max_percent:
        return "above"
    return "within"


def build_allocation(
    *,
    portfolio: Portfolio,
    ownership: Ownership,
    on_date: date,
    context: PerformanceContext | None = None,
) -> dict[str, Any]:
    """Actual frente a objetivo para un ambito, por clase y por posicion.

    Una clase sin objetivo aparece igualmente como `unplanned`: esconder lo que tienes y
    no habias planeado es justo lo contrario de lo que hace falta para decidir.
    """
    context = context or load_performance_context(
        portfolio=portfolio,
        start_date=timeline_context_start(portfolio=portfolio, start_date=on_date),
        end_date=on_date,
    )
    strategy = resolve_strategy(portfolio=portfolio, ownership=ownership, on_date=on_date)
    positions = positions_in_scope(context=context, ownership_id=ownership.id, on_date=on_date)
    slices = scope_slices(context=context, positions=positions, on_date=on_date)
    # El efectivo enlazado a un contenedor es liquidez de la cartera: cuenta en el valor,
    # asi que tiene que contar tambien en la composicion. Sin esto la clase Liquidez
    # marcaba cero teniendo dinero, y el total de la tabla no cuadraba con el hero.
    cash_value = scope_cash(context=context, ownership=ownership, on_date=on_date)
    total = sum((row.value for row in slices), ZERO) + cash_value

    targets_by_class: dict[str, AllocationTarget] = {}
    targets_by_position: dict[int, AllocationTarget] = {}
    if strategy is not None:
        for target in strategy.targets.all():
            if target.asset_class:
                targets_by_class[target.asset_class] = target
            elif target.position_id:
                targets_by_position[target.position_id] = target

    by_class: dict[str, Decimal] = {}
    by_position: dict[int, Decimal] = {}
    if cash_value:
        by_class["cash"] = cash_value
    for row in slices:
        by_class[row.asset_class] = by_class.get(row.asset_class, ZERO) + row.value
        by_position[row.position.id] = by_position.get(row.position.id, ZERO) + row.value

    def rows(current: dict, targets: dict, label: str) -> list[dict[str, Any]]:
        keys = list(current) + [key for key in targets if key not in current]
        result = []
        for key in keys:
            value = current.get(key, ZERO)
            share = (value / total * Decimal("100")) if total else ZERO
            target = targets.get(key)
            ideal = (target.target_percent / Decimal("100") * total) if target else None
            result.append(
                {
                    label: key,
                    "value": str(value.quantize(Decimal("0.01"))),
                    "actual_percent": str(share.quantize(Decimal("0.01"))),
                    "target_percent": str(target.target_percent) if target else None,
                    "min_percent": str(target.min_percent)
                    if target and target.min_percent is not None
                    else None,
                    "max_percent": str(target.max_percent)
                    if target and target.max_percent is not None
                    else None,
                    # Positivo es ir sobrado y negativo es quedarse corto, como en
                    # cualquier desviacion: el exceso suma. Al reves obligaba a traducir
                    # el signo cada vez que se leia la tabla.
                    "drift_value": str((value - ideal).quantize(Decimal("0.01")))
                    if ideal is not None
                    else None,
                    "band": _band_state(share, target),
                }
            )
        return sorted(result, key=lambda row: Decimal(row["value"]), reverse=True)

    # El segundo nivel: dentro de cada clase, que le toca a cada producto. El objetivo
    # de una posicion sin linea propia no es cero, es el trozo que hereda de su clase,
    # asi que se calcula con el mismo resolutor que usa el reparto.
    effective: dict[int, Decimal] = {}
    if strategy is not None:
        effective, _, _ = _effective_targets(
            strategy=strategy, positions=positions, current_by_position=by_position
        )
    names = {position.id: position.asset.name for position in positions}
    classes = {position.id: position.effective_asset_class for position in positions}
    position_rows = []
    for position_id, value in by_position.items():
        share = (value / total * Decimal("100")) if total else ZERO
        target_percent = effective.get(position_id)
        explicit = targets_by_position.get(position_id)
        ideal = (target_percent / Decimal("100") * total) if target_percent is not None else None
        position_rows.append(
            {
                "position_id": position_id,
                "name": names.get(position_id, ""),
                "asset_class": classes.get(position_id, "other"),
                "value": str(value.quantize(Decimal("0.01"))),
                "actual_percent": str(share.quantize(Decimal("0.01"))),
                "target_percent": str(target_percent.quantize(Decimal("0.01")))
                if target_percent is not None
                else None,
                # Lo escrito a mano se declara dentro de la clase, que es como se piensa
                # y como se edita; el efectivo de arriba ya esta en % de cartera.
                "class_share": str(explicit.target_percent) if explicit else None,
                "min_percent": str(explicit.min_percent)
                if explicit and explicit.min_percent is not None
                else None,
                "max_percent": str(explicit.max_percent)
                if explicit and explicit.max_percent is not None
                else None,
                "drift_value": str((value - ideal).quantize(Decimal("0.01")))
                if ideal is not None
                else None,
                "band": _band_state(share, explicit) if explicit else "derived",
            }
        )
    position_rows.sort(key=lambda row: Decimal(row["value"]), reverse=True)

    return {
        "ownership_id": ownership.id,
        "on_date": on_date.isoformat(),
        "currency": portfolio.base_currency,
        "strategy": (
            {
                "id": strategy.id,
                "effective_from": strategy.effective_from.isoformat(),
                "note": strategy.note,
                "target_total": str(
                    sum(
                        (row.target_percent for row in strategy.targets.all() if row.asset_class),
                        ZERO,
                    )
                ),
            }
            if strategy is not None
            else None
        ),
        "total_value": str(total.quantize(Decimal("0.01"))),
        "position_count": len(positions),
        "suggested_contribution": str(
            planned_contribution(user=portfolio.user, on_date=on_date).quantize(CENT)
        ),
        "by_class": rows(by_class, targets_by_class, "asset_class"),
        "by_position": position_rows,
    }


CENT = Decimal("0.01")
MAX_REDISTRIBUTIONS = 12


def planned_contribution(*, user: Any, on_date: date) -> Decimal:
    """Lo que el presupuesto tenia previsto invertir ese mes.

    Solo se lee: la cartera propone el importe que ya habias planificado, y decidir otra
    cosa no reescribe el presupuesto. Si no hay nada planificado, no hay sugerencia y el
    importe se escribe a mano.
    """
    total = ZERO
    entries = AnnualExpenseEntry.objects.filter(
        user=user,
        is_active=True,
        category=AnnualExpenseEntry.Category.FINANCIAL_INVESTMENTS,
    )
    for entry in entries:
        distribution = planned_expense_monthly_distribution(entry=entry, fiscal_year=on_date.year)
        total += distribution.get(on_date.month, ZERO)
    return total


def contributed_within(
    *, context: PerformanceContext, position_id: int, since: date, until: date
) -> Decimal:
    """Lo aportado a una posicion en una ventana, para saber cuanto queda de un cupo."""
    return sum(
        (
            flow.amount
            for flow in context.flows
            if flow.position_id == position_id
            and flow.external
            and since <= flow.on_date <= until
            and flow.amount > 0
        ),
        ZERO,
    )


def resolve_commitments(
    *, context: PerformanceContext, positions: list[PortfolioPosition], on_date: date
) -> tuple[dict[int, dict[str, Any]], dict[int, dict[str, Any]]]:
    """Cuanto hay que llevar a cada sitio antes de mirar la desviacion.

    Devuelve lo pendiente por posicion y lo pendiente por contenedor, que son dos cosas
    distintas: el plan de pensiones tiene su cupo anual, y la plataforma entera tiene un
    minimo mensual que da igual como se reparta por dentro.

    Lo ya aportado se descuenta: si el tope deducible son 1.500 y llevas 900, lo
    pendiente son 600, no 1.500. Y un cupo anual se **reparte por los meses que quedan**
    en vez de reclamarse entero: vaciarlo en enero deja los meses siguientes sin nada que
    aportar, y con un minimo mensual de plataforma por medio eso significa perderlo.
    """
    by_position = {position.id: position for position in positions}
    by_container: dict[int, list[int]] = {}
    for position in positions:
        by_container.setdefault(position.container_id, []).append(position.id)

    pending: dict[int, dict[str, Any]] = {}
    containers: dict[int, dict[str, Any]] = {}
    for commitment in ContributionCommitment.objects.filter(
        Q(position_id__in=list(by_position)) | Q(container_id__in=list(by_container)),
        is_active=True,
    ):
        annual = commitment.period == ContributionCommitment.Period.YEAR
        since = date(on_date.year, 1, 1) if annual else date(on_date.year, on_date.month, 1)
        targets = (
            [commitment.position_id]
            if commitment.position_id
            else by_container.get(commitment.container_id, [])
        )
        done = sum(
            (
                contributed_within(
                    context=context, position_id=position_id, since=since, until=on_date
                )
                for position_id in targets
            ),
            ZERO,
        )
        outstanding = max(commitment.amount - done, ZERO)
        if outstanding <= 0:
            continue
        # Un cupo anual va a su ritmo: lo que queda dividido entre los meses que faltan,
        # diciembre incluido. En diciembre eso es todo lo pendiente.
        months_left = 13 - on_date.month
        claim = (
            (outstanding / Decimal(months_left)).quantize(CENT, rounding=ROUND_UP)
            if annual
            else outstanding
        )
        row = {
            "amount": min(claim, outstanding),
            "outstanding": outstanding,
            # Lo que pide el compromiso y lo que ya llevas puesto en su periodo. Sin
            # esto, una propuesta de 150 sobre un minimo de 300 parece que incumple
            # cuando en realidad los otros 150 ya estaban dentro.
            "target": commitment.amount,
            "contributed": done,
            "period": commitment.period,
            "reason": commitment.reason,
            "breach_cost": commitment.breach_cost,
        }
        if commitment.position_id:
            current = pending.get(commitment.position_id)
            if current is None or row["amount"] > current["amount"]:
                pending[commitment.position_id] = row
        else:
            containers[commitment.container_id] = row
    return pending, containers


@dataclass(frozen=True)
class Candidate:
    """Algo que puede recibir dinero, con su hueco hasta el objetivo.

    La liquidez tactica es una candidata mas, sin posicion detras: es una linea de la
    politica y compite por el dinero como cualquier clase. Reservarla antes que nada le
    daba prioridad absoluta y una aportacion entera podia irse a efectivo mientras el
    resto de la cartera seguia fuera de banda.
    """

    key: int | None
    position: PortfolioPosition | None
    asset_class: str
    current: Decimal
    target_percent: Decimal
    gap: Decimal
    tax_transferable: bool
    minimum: Decimal
    step: Decimal
    operation_cost: Decimal = ZERO
    # Si su contenedor tiene cuenta de efectivo donde esperar a alcanzar el minimo.
    accumulates: bool = False


def _effective_targets(
    *,
    strategy: AllocationStrategy,
    positions: list[PortfolioPosition],
    current_by_position: dict[int, Decimal],
) -> tuple[dict[int, Decimal], Decimal, list[dict[str, Any]]]:
    """Objetivo de cada posicion en % de la cartera, el de la liquidez, y lo inalcanzable.

    El objetivo de una posicion se declara **dentro de su clase**, no sobre la cartera:
    "de mi renta variable, un 60% al indexado global". Es la unidad en la que se piensa
    el segundo nivel, y ademas es la unica que no se descuadra sola cuando el objetivo de
    la clase cambia. Lo que no se reparta a mano se hereda repartido por peso actual,
    porque el reparto dentro de una clase ya lo decidiste al construirla.
    """
    class_targets: dict[str, Decimal] = {}
    position_targets: dict[int, Decimal] = {}
    cash_target = ZERO
    for target in strategy.targets.all():
        if target.position_id:
            position_targets[target.position_id] = target.target_percent
        elif target.asset_class == "cash":
            cash_target = target.target_percent
        else:
            class_targets[target.asset_class] = target.target_percent

    resolved: dict[int, Decimal] = {}
    by_class: dict[str, list[PortfolioPosition]] = {}
    for position in positions:
        by_class.setdefault(position.effective_asset_class, []).append(position)

    for asset_class, members in by_class.items():
        share = class_targets.get(asset_class)
        if share is None:
            continue
        # Lo declarado a mano dentro de la clase se sirve primero; el resto de la clase
        # se reparte entre las demas posiciones.
        declared = [row for row in members if row.id in position_targets]
        for position in declared:
            resolved[position.id] = share * position_targets[position.id] / Decimal("100")
        claimed = sum((position_targets[row.id] for row in declared), ZERO)
        rest = [row for row in members if row.id not in position_targets]
        remaining = share * max(Decimal("100") - claimed, ZERO) / Decimal("100")
        if not rest or remaining <= 0:
            continue
        weights = {p.id: current_by_position.get(p.id, ZERO) for p in rest}
        total_weight = sum(weights.values(), ZERO)
        if total_weight > 0:
            for position in rest:
                resolved[position.id] = remaining * weights[position.id] / total_weight
            continue
        # Clase planeada y todavia vacia: no hay historia de la que deducir un peso, asi
        # que aqui si se elige donde construir. Se construye en lo traspasable, porque
        # esa parte se podra rebalancear manana sin pagar peaje y la otra no. Si ninguna
        # lo admite, a partes iguales, que es lo unico neutral.
        preferred = [row for row in rest if row.tax_transferable] or rest
        for position in rest:
            resolved[position.id] = (
                remaining / Decimal(len(preferred)) if position in preferred else ZERO
            )

    # Una clase con objetivo y sin ninguna posicion no es un reparto de cero: es dinero
    # que no tiene donde ir. Antes desaparecia en silencio y su parte se la repartian las
    # demas, asi que la propuesta se alejaba del objetivo sin decir por que.
    unreachable = [
        {"asset_class": asset_class, "target_percent": str(share), "reason": "no_position"}
        for asset_class, share in sorted(class_targets.items())
        if share > 0 and asset_class not in by_class
    ]
    return resolved, cash_target, unreachable


def _distribute(
    amount: Decimal, candidates: list[Candidate]
) -> tuple[dict[int | None, Decimal], dict[int | None, Decimal], dict[int | None, Decimal]]:
    """Reparte la aportacion: primero cierra huecos, luego mantiene el rumbo.

    Devuelve lo repartido, lo reservado para acumular y lo que se quedo sin sitio: una
    posicion que no alcanza su minimo y cuyo contenedor no tiene efectivo donde esperar.
    Eso ultimo se aparta igual, pero hay que decirlo o la posicion desaparece de la
    propuesta sin explicacion. Son tres fases:

    1. Quien no llega a su minimo se aparta. Si su contenedor tiene efectivo, su parte se
       reserva ahi en vez de volver al bote: repartirla entre las demas condenaria a una
       plataforma con minimo de entrada alto a no financiarse nunca.
    2. El resto se reparte proporcional al hueco, sin pasarse de largo.
    3. Si aun sobra, se coloca a peso de politica, que deja la cartera en el objetivo en
       vez de dejar dinero parado en efectivo sin que nadie lo haya decidido.

    Los minimos obligan a iterar la primera fase: al apartar una candidata el bote cambia
    y puede hacer que otra deje de alcanzar el suyo. El bucle esta acotado y termina
    porque cada vuelta aparta al menos una o se estabiliza.
    """
    eligible = [row for row in candidates if row.gap > 0]
    reserved: dict[int | None, Decimal] = {}
    homeless: dict[int | None, Decimal] = {}
    budget = amount
    raw: dict[int | None, Decimal] = {}
    for _ in range(MAX_REDISTRIBUTIONS):
        if not eligible or budget <= 0:
            break
        total_gap = sum((row.gap for row in eligible), ZERO)
        if total_gap <= 0:
            eligible = []
            break
        raw = {row.key: min(budget * row.gap / total_gap, row.gap) for row in eligible}
        dropped = [row for row in eligible if raw[row.key] < row.minimum]
        if not dropped:
            break
        for row in dropped:
            if not row.accumulates:
                homeless[row.key] = raw[row.key].quantize(CENT, rounding=ROUND_DOWN)
                continue
            # Va a una cuenta de efectivo, asi que el escalon de la posicion no aplica.
            take = min(raw[row.key], budget).quantize(CENT, rounding=ROUND_DOWN)
            if take <= 0:
                continue
            reserved[row.key] = reserved.get(row.key, ZERO) + take
            budget -= take
        eligible = [row for row in eligible if row not in dropped]

    assigned: dict[int | None, Decimal] = {}
    if budget > 0 and eligible:
        total_gap = sum((row.gap for row in eligible), ZERO)
        if total_gap > 0:
            for row in eligible:
                value = min(budget * row.gap / total_gap, row.gap)
                placed = _step_down(value, row)
                if placed >= row.minimum and placed > 0:
                    assigned[row.key] = placed

    open_slots = [row for row in candidates if row.key in assigned] or [
        row for row in candidates if row.minimum <= 0 and row.key not in reserved
    ]
    remaining = budget - sum(assigned.values(), ZERO)
    if remaining > 0 and open_slots:
        total_target = sum((row.target_percent for row in open_slots), ZERO)
        if total_target > 0:
            for row in open_slots:
                extra = _step_down(remaining * row.target_percent / total_target, row)
                if extra > 0:
                    assigned[row.key] = assigned.get(row.key, ZERO) + extra

    # El residuo de cuantizar se coloca de a poco. Se prefiere lo traspasable, porque
    # construir donde luego se puede rebalancear sin peaje deja gratis el rebalanceo.
    residual = budget - sum(assigned.values(), ZERO)
    if residual >= CENT and open_slots:
        for row in sorted(
            open_slots,
            key=lambda row: (not row.tax_transferable, -row.gap, row.key is None, row.key or 0),
        ):
            if residual < CENT or row.step > 0:
                continue
            assigned[row.key] = assigned.get(row.key, ZERO) + residual
            residual = ZERO
            break
    return {key: value for key, value in assigned.items() if value > 0}, reserved, homeless


def _step_down(value: Decimal, row: Candidate) -> Decimal:
    """A la baja siempre: nunca se propone mas dinero del que hay."""
    if row.step > 0:
        value = (value // row.step) * row.step
    return value.quantize(CENT, rounding=ROUND_DOWN)


def _merge_commitment_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Una posicion, una linea. Su cupo propio y el suelo de su plataforma son dos motivos
    del mismo dinero, y publicarlos por separado hacia leer "114 al plan" y "36 de
    compromiso" como si fueran dos destinos distintos.
    """
    merged: dict[int | None, dict[str, Any]] = {}
    for row in rows:
        current = merged.get(row["position_id"])
        if current is None:
            merged[row["position_id"]] = dict(row)
            continue
        current["amount"] = str(Decimal(current["amount"]) + Decimal(row["amount"]))
        reasons = [text for text in (current["reason"], row["reason"]) if text]
        current["reason"] = " · ".join(dict.fromkeys(reasons))
        # Al fusionar se queda el compromiso mas grande de los dos: es el que el usuario
        # reconoce cuando lee la linea.
        if Decimal(row["target"]) > Decimal(current["target"]):
            current["target"] = row["target"]
            current["contributed"] = row["contributed"]
    return sorted(merged.values(), key=lambda row: Decimal(row["amount"]), reverse=True)


def _serve_position_commitments(
    *,
    candidates: list[Candidate],
    commitments: dict[int, dict[str, Any]],
    committed: dict[int | None, Decimal],
    budget: Decimal,
) -> tuple[Decimal, list[dict[str, Any]], list[dict[str, Any]]]:
    """Atiende los compromisos de posicion, y reparte cuando la aportacion no llega.

    Primero el que mas cuesta romper: dejar la aportacion periodica que conserva una
    ventaja del banco puede costar mucho mas que la aportacion misma. Pero **a igualdad
    de coste se reparte a prorrata**, no en orden hasta agotar. Servir uno entero y dejar
    al otro a cero solo se justifica si romperlos cuesta distinto; si cuestan lo mismo,
    vaciar el cupo de uno y no tocar el del otro es una decision que no ha tomado nadie.
    """
    honoured: list[dict[str, Any]] = []
    unmet: list[dict[str, Any]] = []
    claimants = [row for row in candidates if row.key is not None and row.key in commitments]
    claimants.sort(key=lambda row: commitments[row.key]["breach_cost"], reverse=True)

    for _, group in groupby(claimants, key=lambda row: commitments[row.key]["breach_cost"]):
        tier = list(group)
        wanted = sum((commitments[row.key]["amount"] for row in tier), ZERO)
        if wanted <= 0:
            continue
        # Con presupuesto de sobra cada uno cobra lo suyo; si no llega, cada uno cobra su
        # parte proporcional de lo que reclama.
        share = min(budget, wanted)
        for index, candidate in enumerate(tier):
            claim = commitments[candidate.key]
            portion = (
                claim["amount"]
                if share >= wanted
                else (share * claim["amount"] / wanted).quantize(CENT)
            )
            take = _step_down(min(portion, budget), candidate) if budget > 0 else ZERO
            del index
            if take > 0:
                committed[candidate.key] = committed.get(candidate.key, ZERO) + take
                budget -= take
                honoured.append(
                    {
                        "position_id": candidate.key,
                        "amount": str(take),
                        "period": claim["period"],
                        "reason": claim["reason"],
                        "target": str(claim["target"]),
                        "contributed": str(claim["contributed"]),
                    }
                )
            if take < claim["amount"]:
                # Cumplido a medias es incumplido para lo que depende de el: la ventaja
                # del banco no se conserva por aportar la mitad del minimo.
                unmet.append(
                    {
                        "position_id": candidate.key,
                        "amount": str(claim["amount"] - take),
                        "period": claim["period"],
                        "reason": claim["reason"],
                        "breach_cost": str(claim["breach_cost"]),
                    }
                )
    return budget, honoured, unmet


def _serve_container_floors(
    *,
    candidates: list[Candidate],
    container_commitments: dict[int, dict[str, Any]],
    commitments: dict[int, dict[str, Any]],
    committed: dict[int | None, Decimal],
    budget: Decimal,
) -> tuple[Decimal, list[dict[str, Any]], list[dict[str, Any]]]:
    """Cubre el minimo de cada plataforma repartiendolo entre sus posiciones.

    El minimo de una plataforma es de la plataforma entera: da igual si los 300 EUR de
    MyInvestor van al plan de pensiones o al roboadvisor. Se cuenta lo que ya se les ha
    comprometido en esta misma aportacion y solo se completa la diferencia, repartida a
    proporcion del cupo anual que le queda a cada una: con 1.500 y 2.100 pendientes, de
    300 salen 125 y 175. Asi el cupo del ano llega hasta diciembre en vez de gastarse en
    enero y dejar los meses siguientes por debajo del minimo de la plataforma.
    """
    honoured: list[dict[str, Any]] = []
    unmet: list[dict[str, Any]] = []
    for container_id, claim in sorted(
        container_commitments.items(), key=lambda item: -item[1]["breach_cost"]
    ):
        members = [
            member
            for member in candidates
            if member.position is not None and member.position.container_id == container_id
        ]
        already = sum((committed.get(member.key, ZERO) for member in members), ZERO)
        missing = min(claim["amount"] - already, budget)
        if not members or missing <= 0:
            if claim["amount"] > already:
                unmet.append(_container_breach(container_id, claim, claim["amount"] - already))
            continue
        weights: dict[int | None, Decimal] = {}
        for member in members:
            quota = commitments.get(member.key)
            # Sitio que le queda para recibir, en euros las dos formas: lo que falta de
            # su cupo, o lo que le falta para llegar a su objetivo. Un producto que va
            # sobrado y no tiene cupo no tiene sitio, y entonces el suelo se lo lleva
            # entero el que si lo tiene, que es la respuesta correcta aunque sorprenda.
            room = quota["outstanding"] - committed.get(member.key, ZERO) if quota else member.gap
            weights[member.key] = max(room, ZERO)
        total_weight = sum(weights.values(), ZERO)
        if total_weight <= 0:
            weights = {member.key: Decimal("1") for member in members}
            total_weight = Decimal(len(members))
        placed = ZERO
        for index, member in enumerate(members):
            share = (
                missing - placed
                if index == len(members) - 1
                else (missing * weights[member.key] / total_weight).quantize(CENT)
            )
            take = _step_down(min(share, budget), member)
            if take <= 0:
                continue
            committed[member.key] = committed.get(member.key, ZERO) + take
            budget -= take
            placed += take
            honoured.append(
                {
                    "position_id": member.key,
                    "amount": str(take),
                    "period": claim["period"],
                    "reason": claim["reason"] or "Minimo de la plataforma",
                    "target": str(claim["target"]),
                    "contributed": str(claim["contributed"]),
                }
            )
        if placed < missing:
            unmet.append(_container_breach(container_id, claim, missing - placed))
    return budget, honoured, unmet


def _container_breach(container_id: int, claim: dict[str, Any], amount: Decimal) -> dict[str, Any]:
    return {
        "container_id": container_id,
        "amount": str(amount),
        "period": claim["period"],
        "reason": claim["reason"],
        "breach_cost": str(claim["breach_cost"]),
    }


def build_contribution(
    *,
    portfolio: Portfolio,
    ownership: Ownership,
    amount: Decimal,
    on_date: date,
    context: PerformanceContext | None = None,
) -> dict[str, Any]:
    """Reparte una aportacion hacia donde mas falta para la politica del ambito.

    Solo aportaciones: no propone ventas. Mientras la cartera siga creciendo por
    aportacion, dirigirla sostiene las bandas sin pagar peaje fiscal, que es justo lo que
    una venta de rebalanceo si cuesta.
    """
    context = context or load_performance_context(
        portfolio=portfolio,
        start_date=timeline_context_start(portfolio=portfolio, start_date=on_date),
        end_date=on_date,
    )
    strategy = resolve_strategy(portfolio=portfolio, ownership=ownership, on_date=on_date)
    if strategy is None:
        return {"status": "no_strategy", "lines": [], "amount": str(amount)}

    # Solo las lineas de clase: las de posicion son un reparto *dentro* de su clase, y
    # sumarlas aqui hacia que anadir un segundo nivel rompiera la validacion del 100%.
    declared = sum((row.target_percent for row in strategy.targets.all() if row.asset_class), ZERO)
    if abs(declared - Decimal("100")) > Decimal("0.01"):
        # No se normaliza en silencio: con una politica incompleta el ideal se calcula
        # sobre una cartera que no es la tuya y el reparto resultante seria inventado.
        return {
            "status": "incomplete_strategy",
            "declared_percent": str(declared),
            "lines": [],
            "amount": str(amount),
        }

    positions = positions_in_scope(context=context, ownership_id=ownership.id, on_date=on_date)
    slices = scope_slices(context=context, positions=positions, on_date=on_date)
    current_by_position: dict[int, Decimal] = {}
    for row in slices:
        current_by_position[row.position.id] = (
            current_by_position.get(row.position.id, ZERO) + row.value
        )
    total = sum(current_by_position.values(), ZERO)
    post_total = total + amount

    resolved, cash_target, unreachable = _effective_targets(
        strategy=strategy, positions=positions, current_by_position=current_by_position
    )

    candidates: list[Candidate] = []
    skipped: list[dict[str, Any]] = []
    for position in sorted(positions, key=lambda row: row.id):
        rule = getattr(position, "allocation_rule", None)
        target_percent = resolved.get(position.id, ZERO)
        if rule is not None and rule.excluded:
            skipped.append({"position_id": position.id, "reason": "excluded"})
            continue
        if target_percent <= 0:
            skipped.append({"position_id": position.id, "reason": "no_target"})
            continue
        current = current_by_position.get(position.id, ZERO)
        ideal = target_percent / Decimal("100") * post_total
        candidates.append(
            Candidate(
                key=position.id,
                position=position,
                asset_class=position.effective_asset_class,
                current=current,
                target_percent=target_percent,
                gap=max(ideal - current, ZERO),
                tax_transferable=position.tax_transferable,
                minimum=(
                    rule.min_contribution
                    if rule and rule.min_contribution > 0
                    else strategy.min_line_amount
                ),
                step=rule.rounding_step if rule else ZERO,
                operation_cost=(
                    ZERO if rule is None or rule.fee_free_plan else rule.operation_cost
                ),
                accumulates=position.container.cash_accounts.exists(),
            )
        )

    if cash_target > 0:
        # La liquidez entra como una candidata mas y compite por el hueco. El efectivo
        # del contenedor no es de ninguna posicion, asi que dentro del ambito parte de
        # cero y su hueco es su objetivo entero.
        candidates.append(
            Candidate(
                key=None,
                position=None,
                asset_class="cash",
                current=ZERO,
                target_percent=cash_target,
                gap=cash_target / Decimal("100") * post_total,
                tax_transferable=False,
                minimum=ZERO,
                step=ZERO,
            )
        )

    # Los compromisos se atienden antes que la politica: una deduccion fiscal o una
    # ventaja del broker valen, en euros, mucho mas que la desviacion que se corrige.
    commitments, container_commitments = resolve_commitments(
        context=context, positions=positions, on_date=on_date
    )
    # Un cupo lleno sigue siendo un techo: la posicion no debe recibir mas aunque su
    # compromiso ya no reclame nada.
    _year_capped = set(
        ContributionCommitment.objects.filter(
            position_id__in=[position.id for position in positions],
            is_active=True,
            period=ContributionCommitment.Period.YEAR,
        ).values_list("position_id", flat=True)
    )
    committed: dict[int | None, Decimal] = {}
    budget = amount
    honoured: list[dict[str, Any]] = []
    unmet: list[dict[str, Any]] = []
    budget, honoured, unmet = _serve_position_commitments(
        candidates=candidates, commitments=commitments, committed=committed, budget=budget
    )

    # Un cupo anual es tambien un techo: pasarse no desgrava. La posicion se financia
    # con su compromiso y se aparta del reparto, asi que el resto del dinero va a las
    # demas en vez de acabar donde ya no aporta nada.
    budget, container_honoured, container_unmet = _serve_container_floors(
        candidates=candidates,
        container_commitments=container_commitments,
        commitments=commitments,
        committed=committed,
        budget=budget,
    )
    honoured = _merge_commitment_rows(honoured + container_honoured)
    unmet.extend(container_unmet)

    capped = {
        position_id
        for position_id, claim in commitments.items()
        if claim["period"] == ContributionCommitment.Period.YEAR
    }
    capped.update(
        candidate.key
        for candidate in candidates
        if candidate.key is not None and candidate.key in _year_capped
    )
    open_candidates = [row for row in candidates if row.key not in capped]

    assigned, short, homeless = _distribute(budget, open_candidates) if budget > 0 else ({}, {}, {})
    # Una posicion que no llega a su minimo y no tiene efectivo de contenedor donde
    # esperar se aparta igual, pero se dice: si no, desaparece de la propuesta y parece
    # que el reparto la ignora sin motivo.
    for key, value in homeless.items():
        candidate = next((row for row in open_candidates if row.key == key), None)
        if candidate is None or candidate.position is None:
            continue
        skipped.append(
            {
                "position_id": key,
                "reason": "below_minimum_no_cash",
                "amount": str(value),
                "minimum": str(candidate.minimum),
                "container": candidate.position.container.name,
            }
        )
    for key, value in committed.items():
        assigned[key] = assigned.get(key, ZERO) + value

    # Una linea cuya comision se lleva mas de lo tolerable no se propone: la operacion se
    # come a si misma y es mejor acumular para la siguiente. Un compromiso se atiende
    # igual, porque la deduccion vale mucho mas que la comision.
    uneconomic = [
        candidate
        for candidate in candidates
        if candidate.key in assigned
        and candidate.operation_cost > 0
        and assigned[candidate.key] > 0
        and candidate.operation_cost / assigned[candidate.key] > strategy.max_cost_share
        and candidate.key not in committed
    ]
    for candidate in uneconomic:
        skipped.append(
            {
                "position_id": candidate.key,
                "reason": "cost_exceeds_ticket",
                "operation_cost": str(candidate.operation_cost),
                "amount": str(assigned[candidate.key]),
            }
        )
        assigned.pop(candidate.key, None)

    # Lo reservado por no alcanzar el minimo se acumula en el efectivo de su contenedor:
    # dinero real esperando en la propia plataforma hasta que alcance el minimo de
    # entrada. Sin cuenta de efectivo no hay donde esperar y su parte vuelve al reparto.
    accumulate: list[dict[str, Any]] = []
    by_key = {row.key: row for row in candidates if row.position is not None}
    for key, value in short.items():
        candidate = by_key.get(key)
        if candidate is None or candidate.position is None or value <= 0:
            continue
        cash = candidate.position.container.cash_accounts.first()
        if cash is None:
            continue
        accumulate.append(
            {
                "cash_account_id": cash.id,
                "container": candidate.position.container.name,
                "position_id": key,
                "amount": str(value),
                "reason": "below_minimum",
            }
        )

    reserved_cash = assigned.pop(None, ZERO)
    placed = sum(assigned.values(), ZERO)
    accumulated = sum((Decimal(row["amount"]) for row in accumulate), ZERO)
    leftover = (amount - reserved_cash - placed - accumulated).quantize(CENT)

    by_position = {row.key: row for row in candidates if row.position is not None}
    return {
        "status": "ok",
        "ownership_id": ownership.id,
        "on_date": on_date.isoformat(),
        "currency": portfolio.base_currency,
        "strategy_id": strategy.id,
        "amount": str(amount.quantize(CENT)),
        "reserved_cash": str(reserved_cash),
        "leftover": str(leftover),
        "lines": [
            {
                "position_id": position_id,
                "name": by_position[position_id].position.asset.name,
                "asset_class": by_position[position_id].asset_class,
                "amount": str(value),
                "tax_transferable": by_position[position_id].tax_transferable,
                "target_percent": str(
                    by_position[position_id].target_percent.quantize(Decimal("0.001"))
                ),
                "gap_before": str(by_position[position_id].gap.quantize(CENT)),
            }
            for position_id, value in sorted(assigned.items(), key=lambda item: -item[1])
        ],
        "commitments": honoured,
        # Compromisos que esta aportacion no cubre. Con lo que cuesta romperlos delante,
        # porque esa es la cifra que decide si merece la pena aportar mas este mes.
        "unmet_commitments": unmet,
        "accumulate": accumulate,
        "skipped": skipped,
        # Clases con objetivo escrito y ningun producto donde colocarlo: la propuesta
        # tiene que decirlo, porque si no parece que las ignora sin motivo.
        "unreachable": unreachable,
    }


@db_transaction.atomic
def create_basket(
    *,
    portfolio: Portfolio,
    ownership: Ownership,
    amount: Decimal,
    on_date: date,
    source_account_id: int | None = None,
    context: PerformanceContext | None = None,
) -> ContributionBasket:
    """Guarda un reparto como propuesta pendiente, sin efecto contable.

    Nada de esto toca el ledger: la cesta se revisa y solo la confirmacion crea
    operaciones reales. Una propuesta que se ejecuta sola no se puede revisar.
    """
    solved = build_contribution(
        portfolio=portfolio,
        ownership=ownership,
        amount=amount,
        on_date=on_date,
        context=context,
    )
    if solved["status"] != "ok":
        raise ValidationError({"strategy": solved["status"]})

    basket = ContributionBasket.objects.create(
        portfolio=portfolio,
        ownership=ownership,
        strategy_id=solved["strategy_id"],
        booking_date=on_date,
        amount=Decimal(solved["amount"]),
        reserved_cash=Decimal(solved["reserved_cash"]),
        leftover=Decimal(solved["leftover"]),
        source_account_id=source_account_id,
        explanation={
            "commitments": solved["commitments"],
            "skipped": solved["skipped"],
            "unreachable": solved["unreachable"],
            "unmet_commitments": solved["unmet_commitments"],
        },
    )
    lines = [
        ContributionBasketLine(
            basket=basket,
            position_id=row["position_id"],
            amount=Decimal(row["amount"]),
            reason="policy",
        )
        for row in solved["lines"]
    ]
    lines.extend(
        ContributionBasketLine(
            basket=basket,
            cash_account_id=row["cash_account_id"],
            amount=Decimal(row["amount"]),
            reason=row["reason"],
        )
        for row in solved["accumulate"]
    )
    ContributionBasketLine.objects.bulk_create(lines)
    return basket


def discard_basket(*, basket: ContributionBasket) -> ContributionBasket:
    """Descartar no borra: la propuesta que no seguiste tambien es informacion."""
    if basket.status != ContributionBasket.Status.DRAFT:
        raise ValidationError({"status": "Solo se descarta una cesta pendiente."})
    basket.status = ContributionBasket.Status.DISCARDED
    basket.save(update_fields=["status"])
    basket.lines.filter(status=ContributionBasketLine.Status.PENDING).update(
        status=ContributionBasketLine.Status.SKIPPED
    )
    return basket


@db_transaction.atomic
def confirm_basket(
    *,
    basket: ContributionBasket,
    line_ids: list[int] | None = None,
    source_account_id: int | None = None,
) -> ContributionBasket:
    """Convierte en operaciones reales las lineas que decidas, no necesariamente todas.

    La confirmacion es parcial a proposito: una cesta puede tener una linea que hoy no
    quieres ejecutar y el resto si. Lo que no confirmas se queda pendiente, y la cesta
    solo se cierra cuando no queda nada por decidir.

    Cada linea toma una de las dos rutas segun donde vaya: al efectivo de un contenedor
    —un traspaso, porque es cargar el monedero de la plataforma— o a una posicion —una
    compra financiada desde la cuenta que declares.
    """
    if basket.status != ContributionBasket.Status.DRAFT:
        raise ValidationError({"status": "Solo se confirma una cesta pendiente."})
    source_id = source_account_id or basket.source_account_id
    if source_id is None:
        raise ValidationError({"source_account_id": "Indica de donde sale el dinero."})

    pending = basket.lines.filter(status=ContributionBasketLine.Status.PENDING)
    if line_ids is not None:
        pending = pending.filter(id__in=line_ids)
    pending = list(pending.select_related("position", "cash_account__ledger_account"))
    if not pending:
        raise ValidationError({"lines": "No hay lineas pendientes que confirmar."})

    source = LedgerAccount.objects.get(id=source_id, user=basket.portfolio.user)
    now = timezone.now()
    for line in pending:
        if line.cash_account_id is not None:
            # Cargar el monedero de la plataforma es un traspaso entre cuentas propias,
            # no una compra: todavia no se ha invertido en nada.
            transaction = create_quick_transaction(
                user=basket.portfolio.user,
                movement_type="transfer",
                booking_date=basket.booking_date,
                value_date=basket.booking_date,
                description=f"Aportacion a {line.cash_account.container.name}",
                amount=line.amount,
                account=source,
                counterparty_account=line.cash_account.ledger_account,
                status=LedgerTransaction.Status.POSTED,
                origin=LedgerTransaction.Origin.MANUAL,
            )
        else:
            result = confirm_operation(
                portfolio=basket.portfolio,
                payload={
                    "operation_type": "buy",
                    "position_id": line.position_id,
                    "source_account_id": source.id,
                    "booking_date": basket.booking_date.isoformat(),
                    "amount": str(line.amount),
                    "fee": "0",
                },
                require_preview=False,
            )
            transaction = LedgerTransaction.objects.get(id=result["ledger_transaction_id"])
        line.ledger_transaction = transaction
        line.status = ContributionBasketLine.Status.CONFIRMED
        line.confirmed_at = now
        line.save(update_fields=["ledger_transaction", "status", "confirmed_at"])

    if not basket.lines.filter(status=ContributionBasketLine.Status.PENDING).exists():
        basket.status = ContributionBasket.Status.CONFIRMED
        basket.confirmed_at = now
        basket.save(update_fields=["status", "confirmed_at"])
    return basket


def build_scopes(*, portfolio: Portfolio, on_date: date) -> list[dict[str, Any]]:
    """Que ambitos de titularidad tienen algo, para no obligar a adivinar.

    Sin esto la interfaz aterriza en el primero que le llega, que puede ser el de un
    menor con cuatrocientos euros o el de alguien sin ninguna posicion. El ambito con mas
    dinero es casi siempre el que vienes a mirar.
    """
    context = load_performance_context(
        portfolio=portfolio,
        start_date=timeline_context_start(portfolio=portfolio, start_date=on_date),
        end_date=on_date,
    )
    strategies = {
        row.ownership_id
        for row in portfolio.allocation_strategies.filter(effective_from__lte=on_date)
    }
    scopes = []
    for ownership in Ownership.objects.filter(user=portfolio.user).prefetch_related(
        "splits__member"
    ):
        positions = positions_in_scope(context=context, ownership_id=ownership.id, on_date=on_date)
        if not positions:
            continue
        value = sum(
            (
                row.value
                for row in scope_slices(context=context, positions=positions, on_date=on_date)
            ),
            ZERO,
        )
        scopes.append(
            {
                "ownership_id": ownership.id,
                "kind": ownership.kind,
                "label": (
                    ownership.member.name
                    if ownership.kind == Ownership.Kind.INDIVIDUAL and ownership.member
                    else " + ".join(
                        f"{row.member.name} {row.percent:g}%" for row in ownership.splits.all()
                    )
                ),
                "position_count": len(positions),
                "value": str(value.quantize(CENT)),
                "has_strategy": ownership.id in strategies,
            }
        )
    return sorted(scopes, key=lambda row: Decimal(row["value"]), reverse=True)
