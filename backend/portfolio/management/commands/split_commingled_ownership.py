"""Reparte un bote mezclado entre dos titularidades, movimiento a movimiento.

Cuando un activo fungible se compra durante anos desde cuentas de titularidad distinta y
nunca se separan las monedas, el libro guarda una titularidad por asiento pero la realidad
es un bote comun. `portfolio/lots.py` sabe leer ese bote, pero solo puede leer lo que el
asiento dice, y a veces el asiento dice algo que no paso: una venta etiquetada a una persona
cuando lo que habia dentro era de otra.

Esto corrige el libro, no la lectura. Vende primero lo compartido en la fecha indicada, deja
que las ventas siguientes salgan de quien si tenia monedas, y vuelve a etiquetar compras
posteriores como compartidas hasta reconstruir la cantidad objetivo, partiendo en dos la que
cruza el umbral.

No es una migracion a proposito. Toca el historico contable de una persona concreta, y una
migracion se ejecutaria en cada instalacion, donde esos mismos identificadores son otras
filas. Aqui se invoca a mano, se mira en seco con `--dry-run` y solo escribe con `--apply`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction as db_transaction

from accounting.models import LedgerEntry, LedgerTransaction
from memberships.models import Ownership

ZERO = Decimal("0")
UNITS = Decimal("0.00000001")
SPLIT_NOTE = "Reparto de bote mezclado por titularidad"


@dataclass
class Step:
    kind: str
    transaction: LedgerTransaction
    units: Decimal
    shared_units: Decimal = ZERO

    @property
    def label(self) -> str:
        return f"{self.transaction.booking_date} tx{self.transaction.id} {self.transaction.description[:34]}"


class Command(BaseCommand):
    help = "Reparte un bote mezclado entre una titularidad compartida y una individual."

    def add_arguments(self, parser):
        parser.add_argument("--account-id", type=int, required=True, help="Cuenta del bote.")
        parser.add_argument("--shared-ownership-id", type=int, required=True)
        parser.add_argument("--own-ownership-id", type=int, required=True)
        parser.add_argument(
            "--liquidation-date",
            required=True,
            help="Fecha de la venta que liquida primero lo compartido (YYYY-MM-DD).",
        )
        parser.add_argument(
            "--target-units",
            required=True,
            help="Unidades compartidas a reconstruir despues de esa venta.",
        )
        parser.add_argument(
            "--rebuild-from",
            help=(
                "Desde cuando las compras vuelven a ser compartidas (YYYY-MM-DD). "
                "Por defecto, desde la propia liquidacion. Retrasarlo deja que las ventas "
                "intermedias salgan del bolsillo individual en lugar de comerse lo que se "
                "acaba de reconstruir."
            ),
        )
        parser.add_argument(
            "--tag-shared",
            type=int,
            nargs="*",
            default=[],
            help=(
                "Asientos que pasan a compartidos tal cual, por id. Para la salida que "
                "separa el bote: sin titularidad se reparte a prorrata y se lleva monedas "
                "de ambos en lugar de las compartidas que le tocan."
            ),
        )
        parser.add_argument("--apply", action="store_true", help="Escribe. Sin esto solo mira.")

    def handle(self, *args, **options):
        shared, own = self._ownerships(options)
        liquidation = date.fromisoformat(options["liquidation_date"])
        rebuild_from = (
            date.fromisoformat(options["rebuild_from"]) if options["rebuild_from"] else liquidation
        )
        if rebuild_from < liquidation:
            raise CommandError("--rebuild-from no puede ser anterior a la liquidacion.")
        target = Decimal(options["target_units"])
        rows = list(
            LedgerEntry.objects.filter(
                account_id=options["account_id"],
                transaction__status=LedgerTransaction.Status.POSTED,
            )
            .select_related("transaction")
            .order_by("transaction__booking_date", "transaction_id", "id")
        )
        if not rows:
            raise CommandError("Esa cuenta no tiene movimientos.")
        plan = self._plan(
            rows=rows,
            liquidation=liquidation,
            rebuild_from=rebuild_from,
            target=target,
            shared=shared,
        )
        extra = list(
            LedgerTransaction.objects.filter(id__in=options["tag_shared"]).order_by("booking_date")
        )
        missing = set(options["tag_shared"]) - {row.id for row in extra}
        if missing:
            raise CommandError(f"Asientos inexistentes: {sorted(missing)}")
        self._report(plan, target=target, extra=extra)
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("\nEn seco. Nada escrito. Usa --apply."))
            return
        with db_transaction.atomic():
            for row in extra:
                row.ownership = shared
                row.save(update_fields=["ownership", "updated_at"])
            for step in plan:
                if step.kind == "retag":
                    step.transaction.ownership = shared
                    step.transaction.save(update_fields=["ownership", "updated_at"])
                else:
                    self._split(step=step, shared=shared, own=own)
        self.stdout.write(
            self.style.SUCCESS(f"\nAplicado sobre {len(plan) + len(extra)} asientos.")
        )

    def _ownerships(self, options) -> tuple[Ownership, Ownership]:
        try:
            shared = Ownership.objects.get(id=options["shared_ownership_id"])
            own = Ownership.objects.get(id=options["own_ownership_id"])
        except Ownership.DoesNotExist as error:
            raise CommandError("Titularidad inexistente.") from error
        if shared.kind != Ownership.Kind.SHARED:
            raise CommandError("--shared-ownership-id no es una titularidad compartida.")
        return shared, own

    def _plan(
        self,
        *,
        rows: list[LedgerEntry],
        liquidation: date,
        rebuild_from: date,
        target: Decimal,
        shared: Ownership,
    ) -> list[Step]:
        """Replica el bote y anota que asiento hay que tocar y por cuanto.

        El bote se lleva en dos bolsillos porque el reparto solo distingue lo compartido de
        lo demas: mas detalle no cambiaria ninguna de las decisiones de aqui.
        """
        pocket_shared = pocket_own = ZERO
        phase = "before"
        plan: list[Step] = []
        for row in rows:
            signed = row.amount if row.side == LedgerEntry.Side.DEBIT else -row.amount
            booking = row.transaction.booking_date
            if signed < ZERO and booking == liquidation and phase == "before":
                # Lo compartido sale entero antes que nada: es lo que hace que las ventas
                # siguientes salgan de quien si tenia monedas y no haya que repartirlas.
                taken_shared = min(pocket_shared, -signed)
                pocket_shared -= taken_shared
                pocket_own -= (-signed) - taken_shared
                plan.append(
                    Step(
                        kind="split",
                        transaction=row.transaction,
                        units=-signed,
                        shared_units=taken_shared,
                    )
                )
                phase = "rebuilding"
                continue
            if signed > ZERO and phase == "rebuilding" and booking >= rebuild_from:
                missing = target - pocket_shared
                if missing <= ZERO:
                    pocket_own += signed
                    continue
                if signed <= missing:
                    pocket_shared += signed
                    plan.append(Step(kind="retag", transaction=row.transaction, units=signed))
                    continue
                pocket_shared += missing
                pocket_own += signed - missing
                plan.append(
                    Step(
                        kind="split",
                        transaction=row.transaction,
                        units=signed,
                        shared_units=missing,
                    )
                )
                phase = "done"
                continue
            if signed > ZERO:
                if row.transaction.ownership_id == shared.id:
                    pocket_shared += signed
                else:
                    pocket_own += signed
            else:
                taken = min(pocket_own, -signed)
                pocket_own -= taken
                pocket_shared -= (-signed) - taken
        if phase != "done":
            raise CommandError(
                "No se llega al objetivo con los movimientos disponibles: revisa --target-units."
            )
        return plan

    def _report(self, plan: list[Step], *, target: Decimal, extra: list[LedgerTransaction]) -> None:
        self.stdout.write(f"Objetivo compartido: {target}")
        for step in plan:
            if step.kind == "retag":
                self.stdout.write(f"  entera -> compartida  {step.label}  {step.units}")
            else:
                rest = step.units - step.shared_units
                self.stdout.write(
                    f"  PARTIR                {step.label}  {step.units}"
                    f"  -> compartida {step.shared_units} / resto {rest}"
                )
        for row in extra:
            self.stdout.write(
                f"  etiquetar compartida  {row.booking_date} tx{row.id} {row.description[:34]}"
            )

    def _split(self, *, step: Step, shared: Ownership, own: Ownership) -> None:
        """Parte el asiento en dos: uno compartido y el original con el resto.

        Se parte el asiento entero, las dos patas a la vez, porque media contrapartida no
        es un asiento. La parte compartida se redondea hacia abajo y el resto se calcula
        restando, de modo que los dos trozos suman exactamente el original y no aparece ni
        desaparece un satoshi por el camino.
        """
        source = step.transaction
        fraction = step.shared_units / step.units
        entries = list(source.entries.all())
        copy = LedgerTransaction.objects.create(
            user=source.user,
            booking_date=source.booking_date,
            value_date=source.value_date,
            description=source.description,
            status=source.status,
            origin=source.origin,
            notes=(f"{source.notes}\n{SPLIT_NOTE}").strip(),
            quick_entry_kind=source.quick_entry_kind,
            investment_direction=source.investment_direction,
            member_tag=source.member_tag,
            ownership=shared,
            # El asiento nuevo no viene de ninguna importacion: heredar la huella chocaria
            # con la del original, que es unica por usuario y origen.
            import_fingerprint="",
            import_source=source.import_source,
        )
        for entry in entries:
            portion = (entry.amount * fraction).quantize(UNITS, rounding=ROUND_DOWN)
            LedgerEntry.objects.create(
                transaction=copy,
                account=entry.account,
                asset=entry.asset,
                side=entry.side,
                amount=portion,
                currency=entry.currency,
                flow_family=entry.flow_family,
                category_key=entry.category_key,
                subcategory_key=entry.subcategory_key,
            )
            entry.amount = entry.amount - portion
            entry.save(update_fields=["amount"])
        if source.ownership_id != own.id:
            source.ownership = own
            source.save(update_fields=["ownership", "updated_at"])
