from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
import dataclasses
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import cast

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import LedgerAccount, LedgerTransaction
from .services import create_quick_transaction, get_or_create_system_account

MONEYWIZ_IMPORT_NOTE_PREFIX = "moneywiz_import"
DEFAULT_IMPORT_CURRENCY = "EUR"
TWOPLACES = Decimal("0.01")
ZERO = Decimal("0")

# ---------------------------------------------------------------------------
# MoneyWiz Spanish category path → (category_key, subcategory_key)
# Keys: normalized segments joined by " > ", matched from most- to least-specific.
# ---------------------------------------------------------------------------
_MONEYWIZ_EXPENSE_PATH: dict[str, tuple[str, str]] = {
    # Gastos > Corrientes
    "gastos > corrientes > vivienda": ("consumption_expenses", "housing_home"),
    "gastos > corrientes > alimentacion": ("consumption_expenses", "living_expenses"),
    "gastos > corrientes > bebe": ("consumption_expenses", "family_childcare"),
    "gastos > corrientes > vehiculos": ("consumption_expenses", "transport_mobility"),
    "gastos > corrientes > ropa": ("consumption_expenses", "leisure_lifestyle"),
    "gastos > corrientes > cuidado personal": ("consumption_expenses", "health_wellbeing"),
    "gastos > corrientes > gestion": ("consumption_expenses", "other_consumption_expenses"),
    "gastos > corrientes > noia": ("consumption_expenses", "family_childcare"),
    "gastos > corrientes": ("consumption_expenses", "other_consumption_expenses"),
    # Gastos > otros grupos
    "gastos > deporte": ("consumption_expenses", "health_wellbeing"),
    "gastos > ocio > restaurantes": ("consumption_expenses", "leisure_lifestyle"),
    "gastos > ocio > cerves": ("consumption_expenses", "leisure_lifestyle"),
    "gastos > ocio > musica": ("consumption_expenses", "leisure_lifestyle"),
    "gastos > ocio > plataformas": ("consumption_expenses", "leisure_lifestyle"),
    "gastos > ocio > viajes": ("consumption_expenses", "leisure_lifestyle"),
    "gastos > ocio": ("consumption_expenses", "leisure_lifestyle"),
    "gastos > regalos": ("consumption_expenses", "gifts_donations"),
    "gastos > formacion": ("consumption_expenses", "education_growth"),
    "gastos > side projects": ("consumption_expenses", "education_growth"),
    "gastos > global ana": ("consumption_expenses", "other_consumption_expenses"),
    "gastos > otro general": ("consumption_expenses", "other_consumption_expenses"),
    "gastos": ("consumption_expenses", "other_consumption_expenses"),
    # Inversiones Gastos
    "inversiones gastos > fondos": ("financial_investments", "index_funds"),
    "inversiones gastos > crowdlending": ("financial_investments", "crowdlending_p2p"),
    "inversiones gastos > roboadvisor": ("financial_investments", "roboadvisor"),
    "inversiones gastos > plan de pensiones": ("financial_investments", "pension_plan"),
    "inversiones gastos > st criptos": ("financial_investments", "crypto"),
    "inversiones gastos > st stocks": ("financial_investments", "stocks_dividends"),
    "inversiones gastos > suscripciones": ("consumption_expenses", "other_consumption_expenses"),
    "inversiones gastos > deposito": ("financial_investments", "other_financial_investments"),
    "inversiones gastos > crowdfunding inm": ("financial_investments", "crowdfunding_real_estate"),
    "inversiones gastos > loterias y apuestas": ("consumption_expenses", "leisure_lifestyle"),
    "inversiones gastos": ("financial_investments", "other_financial_investments"),
    # Inmobiliario
    "inmobiliario > hipoteca": ("real_estate_assets", "mortgage_principal"),
    "inmobiliario > comunidad": ("consumption_expenses", "housing_home"),
    "inmobiliario > seguro vivienda": ("consumption_expenses", "housing_home"),
    "inmobiliario > obras": ("real_estate_assets", "property_improvements"),
    "inmobiliario > atrio": ("financial_investments", "other_financial_investments"),
    "inmobiliario > nueva vivienda": ("financial_investments", "other_financial_investments"),
    "inmobiliario": ("real_estate_assets", "other_real_estate_assets"),
    # Mobiliario
    "mobiliario > vehiculos": ("consumption_expenses", "transport_mobility"),
    "mobiliario": ("tangible_assets", "other_tangible_assets"),
    # Acreedores
    "acreedores": ("consumption_expenses", "other_consumption_expenses"),
}

# Subcategorías de "Pasivos > Activos financieros" que en MoneyWiz representan
# compras de activos (dinero saliendo de liquidez hacia inversión), no ingresos.
# Cuando el importe es negativo, se tratan como investment_purchase.
# Categorías de MoneyWiz que representan amortización/liquidación de deuda,
# independientemente del signo del importe.
# Aliases de descripción para el emparejamiento de deudas.
# Mapea la descripción normalizada usada en la cuenta de liquidez a la descripción
# normalizada del nombre de la cuenta de pasivo correspondiente.
# Necesario cuando el usuario introduce variantes ortográficas en MoneyWiz.
_MONEYWIZ_DEBT_DESCRIPTION_ALIASES: dict[str, str] = {
    "ivi": "ibi",  # IVI (errata) → IBI (Impuesto sobre Bienes Inmuebles)
}

_MONEYWIZ_DEBT_PAYMENT_PATHS: frozenset[str] = frozenset(
    {
        "liquidacion credito",
    }
)

# Categorías de MoneyWiz que son siempre income independientemente del signo.
# "Inversiones Ingresos" puede exportarse con importe negativo en ciertos CSVs.
_MONEYWIZ_INCOME_PATHS_ALWAYS: frozenset[str] = frozenset(
    {
        "inversiones ingresos",
    }
)


_MONEYWIZ_INVESTMENT_PURCHASE_PATHS: frozenset[str] = frozenset(
    {
        "pasivos > activos financieros > fondos",
        "pasivos > activos financieros > st criptos",
        "pasivos > activos financieros > dt criptos",
        "pasivos > activos financieros > spot act financieros",
        "pasivos > activos financieros > st stocks",
    }
)

_MONEYWIZ_INCOME_PATH: dict[str, tuple[str, str]] = {
    # Salarios
    "salarios": ("salary", "employee_salary"),
    # Inversiones Ingresos
    "inversiones ingresos > fondos": ("capital_gains", "sale_financial_assets"),
    "inversiones ingresos > crowdlending": ("passive_income", "p2p_lending"),
    "inversiones ingresos > roboadvisor": ("capital_gains", "sale_financial_assets"),
    "inversiones ingresos > plan de pensiones": ("passive_income", "other_passive"),
    "inversiones ingresos > st criptos": ("capital_gains", "sale_financial_assets"),
    "inversiones ingresos > st stocks": ("capital_gains", "sale_financial_assets"),
    "inversiones ingresos > crowdfunding inm": ("capital_gains", "other_capital_gains"),
    "inversiones ingresos > deposito": ("passive_income", "interest_income"),
    "inversiones ingresos": ("passive_income", "other_passive"),
    # Inversiones Gastos con importe positivo = realización del activo (venta, vencimiento,
    # rescate). Mismo criterio que Inversiones Ingresos; deposito incluye principal+intereses
    # sin separar (pendiente modelar la separación).
    "inversiones gastos > fondos": ("capital_gains", "sale_financial_assets"),
    "inversiones gastos > crowdlending": ("capital_gains", "sale_financial_assets"),
    "inversiones gastos > roboadvisor": ("capital_gains", "sale_financial_assets"),
    "inversiones gastos > plan de pensiones": ("capital_gains", "sale_financial_assets"),
    "inversiones gastos > st criptos": ("capital_gains", "sale_financial_assets"),
    "inversiones gastos > st stocks": ("capital_gains", "sale_financial_assets"),
    "inversiones gastos > crowdfunding inm": ("capital_gains", "other_capital_gains"),
    "inversiones gastos > deposito": ("capital_gains", "sale_financial_assets"),
    "inversiones gastos": ("capital_gains", "sale_financial_assets"),
    # Pasivos > Activos financieros
    "pasivos > activos financieros > dividendos": ("passive_income", "dividends"),
    "pasivos > activos financieros > crowdlending": ("passive_income", "p2p_lending"),
    "pasivos > activos financieros > cuentas corrientes": ("passive_income", "interest_income"),
    "pasivos > activos financieros > cashback": ("other_income", "misc"),
    "pasivos > activos financieros > depositos": ("passive_income", "interest_income"),
    "pasivos > activos financieros > fondos": ("capital_gains", "sale_financial_assets"),
    "pasivos > activos financieros > st stocks": ("capital_gains", "sale_financial_assets"),
    "pasivos > activos financieros > st criptos": ("capital_gains", "sale_financial_assets"),
    "pasivos > activos financieros > roboadvisor": ("capital_gains", "sale_financial_assets"),
    "pasivos > activos financieros > plan de pensiones": ("passive_income", "other_passive"),
    "pasivos > activos financieros > spot act financieros": (
        "capital_gains",
        "sale_financial_assets",
    ),
    "pasivos > activos financieros > loterias y apuestas": ("other_income", "misc"),
    "pasivos > activos financieros": ("other_income", "misc"),
    "pasivos > regalos": ("transfers_support", "gifts_received"),
    "pasivos > declaracion de la renta": ("other_income", "tax_refund"),
    "pasivos": ("other_income", "misc"),
    # Deudores
    "deudores > devoluciones": ("transfers_support", "other_transfers_support"),
    "deudores > prestamo personal": ("other_income", "misc"),
    "deudores": ("other_income", "misc"),
    # Ganancias de capital
    "ganancias de capital > ventas activos": ("capital_gains", "sale_personal_asset"),
    "ganancias de capital": ("capital_gains", "other_capital_gains"),
}


@dataclass(frozen=True)
class MoneyWizRow:
    row_number: int
    booking_date: date
    description: str
    memo: str
    category_raw: str
    account_name: str
    counterparty_name: str
    currency: str
    amount: Decimal
    movement_type: str
    flow_family: str
    category_key: str
    subcategory_key: str
    fingerprint: str
    warnings: list[str]
    errors: list[str]
    existing_transaction_id: int | None
    member_tag: str = ""
    principal_amount: Decimal | None = None
    interest_amount: Decimal | None = None
    mirror: bool = False


def extract_moneywiz_csv_text(*, csv_text: str | None = None, file=None) -> str:
    if csv_text is not None and str(csv_text).strip():
        return str(csv_text)
    if file is None:
        raise ValidationError({"file": "Debes enviar un CSV de MoneyWiz o el contenido en texto."})
    raw = file.read()
    return raw.decode("utf-8-sig") if isinstance(raw, bytes) else str(raw)


def build_moneywiz_import_preview(*, user, csv_text: str) -> dict:
    delimiter, normalized_csv_text = _prepare_csv_text(csv_text)
    rows = _parse_moneywiz_rows(
        user_id=user.id,
        csv_text=normalized_csv_text,
        delimiter=delimiter,
    )
    return _build_preview_payload(delimiter=delimiter, rows=rows)


@transaction.atomic
def commit_moneywiz_import(
    *, user, csv_text: str, account_id_map: dict[str, int] | None = None
) -> dict:
    delimiter, normalized_csv_text = _prepare_csv_text(csv_text)
    rows = _parse_moneywiz_rows(
        user_id=user.id,
        csv_text=normalized_csv_text,
        delimiter=delimiter,
    )

    row_errors = {row.row_number: row.errors for row in rows if row.errors}
    if row_errors:
        raise ValidationError({"rows": row_errors})

    created_ids: list[int] = []
    skipped_existing = 0
    seen: set[str] = set()
    for row in rows:
        if row.mirror:
            continue
        if row.fingerprint in seen:
            skipped_existing += 1
            continue
        seen.add(row.fingerprint)
        if row.existing_transaction_id is not None:
            skipped_existing += 1
            continue
        created = _import_moneywiz_row(user=user, row=row, account_id_map=account_id_map)
        created_ids.append(created.id)

    preview = _build_preview_payload(delimiter=delimiter, rows=rows)
    preview["stats"]["created_transactions"] = len(created_ids)
    preview["stats"]["skipped_existing"] = skipped_existing
    return {
        "preview": preview,
        "created_count": len(created_ids),
        "skipped_existing_count": skipped_existing,
        "created_transaction_ids": created_ids,
    }


def _prepare_csv_text(csv_text: str) -> tuple[str, str]:
    normalized = (csv_text or "").lstrip("\ufeff").strip()
    if not normalized:
        raise ValidationError({"file": "El CSV de MoneyWiz no puede estar vacio."})

    first_line, _, rest = normalized.partition("\n")
    first_line = first_line.strip()
    if first_line.lower().startswith("sep=") and len(first_line) >= 5:
        delimiter = first_line[4:5] or ";"
        return delimiter, rest.lstrip("\r\n")
    return _detect_delimiter(normalized), normalized


def _detect_delimiter(csv_text: str) -> str:
    sample = csv_text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ";" if sample.count(";") >= sample.count(",") else ","


def _resolve_investment_mirrors(
    *,
    user_id: int,
    rows: list[MoneyWizRow],
) -> list[MoneyWizRow]:
    """Pairs 'Inversiones Gastos' rows (capital deployment) with their mirror
    'Inversiones Ingresos' rows (investment-account credit side).

    For each matched pair:
    - Row A (Inversiones Gastos, amount < 0): upgraded to investment_purchase
      with the real investment account name as counterparty.
    - Row B (Inversiones Ingresos, amount > 0): marked mirror=True and skipped
      during preview stats and commit.
    """

    def _inv_side(category_raw: str) -> str | None:
        normalized = _normalize_lookup_text(category_raw)
        if normalized.startswith("inversiones gastos"):
            return "gastos"
        if normalized.startswith("inversiones ingresos"):
            return "ingresos"
        return None

    def _inv_subcategory(category_raw: str) -> str:
        normalized = _normalize_lookup_text(category_raw)
        for prefix in ("inversiones gastos > ", "inversiones ingresos > "):
            if normalized.startswith(prefix):
                return normalized[len(prefix) :]
        return ""

    # Index Row-B candidates by (date, abs_amount, subcategory, description); first match wins.
    ingresos_idx: dict[tuple, int] = {}
    for i, row in enumerate(rows):
        if _inv_side(row.category_raw) == "ingresos" and row.amount > ZERO:
            key = (
                row.booking_date,
                row.amount.copy_abs(),
                _inv_subcategory(row.category_raw),
                _normalize_lookup_text(row.description),
            )
            ingresos_idx.setdefault(key, i)

    mirrored: set[int] = set()
    updated: dict[int, MoneyWizRow] = {}

    for i, row in enumerate(rows):
        if _inv_side(row.category_raw) != "gastos" or row.amount >= ZERO:
            continue
        key = (
            row.booking_date,
            row.amount.copy_abs(),
            _inv_subcategory(row.category_raw),
            _normalize_lookup_text(row.description),
        )
        j = ingresos_idx.get(key)
        if j is None or j in mirrored:
            continue

        row_b = rows[j]
        new_flow_family, new_cat_key, new_subcat_key, cls_warnings = _classify_row(
            movement_type="investment_purchase",
            category_raw=row.category_raw,
            description=row.description,
        )
        new_warnings = [
            w for w in row.warnings if "se creara una cuenta provisional" not in w.lower()
        ] + cls_warnings
        new_fingerprint = _build_fingerprint(
            booking_date=row.booking_date,
            description=row.description,
            memo=row.memo,
            category_raw=row.category_raw,
            account_name=row.account_name,
            counterparty_name=row_b.account_name,
            currency=row.currency,
            amount=row.amount,
            movement_type="investment_purchase",
            flow_family=new_flow_family,
            category_key=new_cat_key,
            subcategory_key=new_subcat_key,
        )
        new_existing_id = _find_existing_transaction(user_id=user_id, fingerprint=new_fingerprint)
        if new_existing_id is not None:
            new_warnings.append("Esta fila ya fue importada anteriormente; se omitira en commit.")
        updated[i] = dataclasses.replace(
            row,
            movement_type="investment_purchase",
            counterparty_name=row_b.account_name,
            flow_family=new_flow_family,
            category_key=new_cat_key,
            subcategory_key=new_subcat_key,
            fingerprint=new_fingerprint,
            warnings=new_warnings,
            existing_transaction_id=new_existing_id,
        )
        mirrored.add(j)

    # Pass 2b: pair sale mirrors.
    # When an investment is sold, MoneyWiz records two rows with no Transferencias:
    #   - Liquidity account: "Inversiones Gastos > X" with amount > 0 (sale proceeds coming in)
    #   - Investment account: "Inversiones Ingresos > X" with amount < 0 (position decreasing)
    # The liquidity side is reclassified as income by Pass 3; the investment side must be
    # marked mirror=True so it is not committed as a phantom investment_purchase.
    gastos_sale_idx: dict[tuple, int] = {}
    for i, row in enumerate(rows):
        if i in updated or i in mirrored:
            continue
        if _inv_side(row.category_raw) == "gastos" and row.amount > ZERO:
            key = (
                row.booking_date,
                row.amount.copy_abs(),
                _inv_subcategory(row.category_raw),
                _normalize_lookup_text(row.description),
            )
            gastos_sale_idx.setdefault(key, i)

    for i, row in enumerate(rows):
        if i in updated or i in mirrored:
            continue
        if _inv_side(row.category_raw) != "ingresos" or row.amount >= ZERO:
            continue
        key = (
            row.booking_date,
            row.amount.copy_abs(),
            _inv_subcategory(row.category_raw),
            _normalize_lookup_text(row.description),
        )
        if gastos_sale_idx.get(key) is not None:
            mirrored.add(i)

    result = []
    for i, row in enumerate(rows):
        if i in updated:
            result.append(updated[i])
        elif i in mirrored:
            result.append(dataclasses.replace(row, mirror=True))
        else:
            result.append(row)

    # Pass 3: reclassify remaining investment_purchase rows that still have a
    # synthetic NNN counterparty.  These are either portfolio revaluations
    # (negative "Pasivos > Activos financieros" entries) or misclassified sales
    # ("Inversiones Gastos" with positive amount).  None of them represent a
    # real capital deployment between two accounts, so they must not create a
    # phantom counterparty account.
    _NNN_PREFIX = "MoneyWiz counterparty"
    final: list[MoneyWizRow] = []
    for row in result:
        # Only reclassify investment_purchase rows that match one of two
        # MoneyWiz-specific patterns that should never create a counterparty
        # account:
        #   a) "Pasivos > Activos financieros > ..." with negative amount:
        #      these are portfolio value-adjustments (mark-to-market), not
        #      capital deployments.
        #   b) "Inversiones Gastos > ..." with positive amount: a positive
        #      entry under a "gastos" category is a sale/return of capital,
        #      not a purchase.
        _is_pasivos_revaluation = _match_moneywiz_path_set(
            row.category_raw, _MONEYWIZ_INVESTMENT_PURCHASE_PATHS
        )
        _is_inversiones_gastos_sale = _inv_side(row.category_raw) == "gastos" and row.amount > ZERO
        if (
            row.movement_type == "investment_purchase"
            and row.counterparty_name.startswith(_NNN_PREFIX)
            and not row.mirror
            and (_is_pasivos_revaluation or _is_inversiones_gastos_sale)
        ):
            # Positive "Inversiones Gastos" = sale/return → income.
            # Revaluations (mark-to-market adjustments) → revaluation.
            if _is_inversiones_gastos_sale:
                new_movement_type = "income"
            else:
                new_movement_type = "revaluation"
            new_flow_family, new_cat_key, new_subcat_key, cls_warnings = _classify_row(
                movement_type=new_movement_type,
                category_raw=row.category_raw,
                description=row.description,
            )
            new_warnings = [
                w for w in row.warnings if "se creara una cuenta provisional" not in w.lower()
            ] + cls_warnings
            new_fingerprint = _build_fingerprint(
                booking_date=row.booking_date,
                description=row.description,
                memo=row.memo,
                category_raw=row.category_raw,
                account_name=row.account_name,
                counterparty_name="",
                currency=row.currency,
                amount=row.amount,
                movement_type=new_movement_type,
                flow_family=new_flow_family,
                category_key=new_cat_key,
                subcategory_key=new_subcat_key,
            )
            new_existing_id = _find_existing_transaction(
                user_id=user_id, fingerprint=new_fingerprint
            )
            if new_existing_id is not None:
                new_warnings.append(
                    "Esta fila ya fue importada anteriormente; se omitira en commit."
                )
            final.append(
                dataclasses.replace(
                    row,
                    movement_type=new_movement_type,
                    counterparty_name="",
                    flow_family=new_flow_family,
                    category_key=new_cat_key,
                    subcategory_key=new_subcat_key,
                    fingerprint=new_fingerprint,
                    warnings=new_warnings,
                    existing_transaction_id=new_existing_id,
                )
            )
        else:
            final.append(row)
    return final


def _parse_moneywiz_rows(
    *,
    user_id: int,
    csv_text: str,
    delimiter: str,
) -> list[MoneyWizRow]:
    reader = csv.DictReader(io.StringIO(csv_text), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValidationError({"file": "No se encontraron cabeceras en el CSV de MoneyWiz."})

    rows: list[MoneyWizRow] = []
    seen: dict[str, int] = {}
    for row_number, raw_row in enumerate(reader, start=2):
        if _is_account_summary_row(raw_row):
            continue
        row = _normalize_row(
            user_id=user_id,
            row_number=row_number,
            raw_row=raw_row,
        )
        if row.fingerprint in seen:
            row.warnings.append(
                f"Fila duplicada dentro del archivo; coincide con la fila {seen[row.fingerprint]}."
            )
        else:
            seen[row.fingerprint] = row_number
        rows.append(row)
    rows = _resolve_transfer_mirrors(rows=rows)
    rows = _resolve_investment_mirrors(user_id=user_id, rows=rows)
    return _resolve_debt_mirrors(user_id=user_id, rows=rows)


def _resolve_transfer_mirrors(*, rows: list[MoneyWizRow]) -> list[MoneyWizRow]:
    """Collapses mirrored transfer rows exported by MoneyWiz into a single movement.

    Some exports include both sides of the same transfer as two rows:
    - source account row (amount < 0, e.g. "Transferencia a X")
    - target account row (amount > 0, e.g. "Transferencia de Y")

    If both sides are present (same date/currency/absolute amount and swapped
    source-counterparty names), keep the outflow row and mark the inflow row
    as mirror=True so preview/commit do not duplicate the transaction.
    """

    def _key(row: MoneyWizRow) -> tuple:
        return (
            row.booking_date,
            row.currency,
            row.amount.copy_abs(),
            _normalize_lookup_text(row.account_name),
            _normalize_lookup_text(row.counterparty_name),
        )

    def _transfer_direction_hint(description: str) -> str:
        normalized = _normalize_lookup_text(description)
        if (
            re.search(r"\btransferencia\s+a\b", normalized) is not None
            or re.search(r"\btraspaso\s+a\b", normalized) is not None
            or re.search(r"\btransfer\s+to\b", normalized) is not None
        ):
            return "to"
        if (
            re.search(r"\btransferencia\s+de\b", normalized) is not None
            or re.search(r"\btraspaso\s+de\b", normalized) is not None
            or re.search(r"\btransfer\s+from\b", normalized) is not None
        ):
            return "from"
        return "unknown"

    transfer_idx: dict[tuple, list[int]] = {}
    for i, row in enumerate(rows):
        if row.movement_type != "transfer" or row.mirror:
            continue
        if not row.account_name or not row.counterparty_name:
            continue
        transfer_idx.setdefault(_key(row), []).append(i)

    mirrored: set[int] = set()
    processed: set[int] = set()

    for i, row in enumerate(rows):
        if i in processed:
            continue
        if row.movement_type != "transfer" or row.mirror:
            continue
        if not row.account_name or not row.counterparty_name:
            continue

        key = _key(row)
        reverse_key = (
            row.booking_date,
            row.currency,
            row.amount.copy_abs(),
            _normalize_lookup_text(row.counterparty_name),
            _normalize_lookup_text(row.account_name),
        )
        if key == reverse_key:
            # Self-transfer style row; nothing to pair.
            continue

        pair_index: int | None = None
        for j in transfer_idx.get(reverse_key, []):
            if j != i and j not in processed:
                pair_index = j
                break

        if pair_index is None:
            continue

        other = rows[pair_index]
        row_hint = _transfer_direction_hint(row.description)
        other_hint = _transfer_direction_hint(other.description)

        primary_index = i
        mirror_index = pair_index
        # Prefer explicit "transferencia a ..." row as canonical source -> target.
        if row_hint == "to" and other_hint == "from":
            primary_index = i
            mirror_index = pair_index
        elif row_hint == "from" and other_hint == "to":
            primary_index = pair_index
            mirror_index = i
        elif row.amount < ZERO and other.amount > ZERO:
            primary_index = i
            mirror_index = pair_index
        elif other.amount < ZERO and row.amount > ZERO:
            primary_index = pair_index
            mirror_index = i
        elif pair_index < i:
            primary_index = pair_index
            mirror_index = i

        processed.add(primary_index)
        processed.add(mirror_index)
        mirrored.add(mirror_index)

    if not mirrored:
        return rows

    result: list[MoneyWizRow] = []
    for i, row in enumerate(rows):
        if i in mirrored:
            result.append(dataclasses.replace(row, mirror=True))
        else:
            result.append(row)
    return result


def _is_account_summary_row(raw_row: dict[str, str | None]) -> bool:
    """Detecta filas de cabecera de cuenta (ej. MoneyWiz), que tienen nombre/saldo
    pero no tienen fecha ni importe de transacción. Se saltan silenciosamente."""
    normalized = _normalize_headers(raw_row)
    has_date = bool(normalized.get("date"))
    has_amount = any(
        normalized.get(f)
        for f in ("amount", "amount_incomes", "amount_expenses", "credits", "debits")
    )
    return not has_date and not has_amount


def _resolve_debt_mirrors(
    *,
    user_id: int,
    rows: list[MoneyWizRow],
) -> list[MoneyWizRow]:
    """Pairs 'Liquidación Crédito' (liability-side) rows with their corresponding
    cash-outflow (liquidity-side) rows, eliminating the double-count that would
    arise from importing both independently.

    For each matched pair:
    - Row A (cash outflow, expense type, negative amount): reclassified as
      debt_payment pointing to the liability account as counterparty.
      principal_amount = abs(liquidacion_amount)
      interest_amount  = abs(outflow_amount) - abs(liquidacion_amount)  (≥ 0)
    - Row B (Liquidación Crédito, debt_payment type): marked mirror=True and skipped.

    Unmatched Liquidación Crédito rows remain as debt_payment with the "Deuda: X"
    synthetic counterparty generated in _resolve_counterparty_name.
    """

    # --- Step 1: Index Liquidación Crédito rows by (date, normalized_account_name).
    # These are the liability-side entries: no explicit transfer, counterparty
    # already resolved to "Deuda: <account_name>" by _resolve_counterparty_name.
    liq_idx: dict[tuple, list[int]] = {}
    for i, row in enumerate(rows):
        if (
            row.movement_type == "debt_payment"
            and not row.mirror
            and row.counterparty_name.startswith("Deuda: ")
        ):
            key = (row.booking_date, _normalize_lookup_text(row.account_name))
            liq_idx.setdefault(key, []).append(i)

    if not liq_idx:
        return rows

    mirrored: set[int] = set()
    updated: dict[int, MoneyWizRow] = {}

    # --- Step 2: For each cash-outflow expense row, try to find its matching
    # Liquidación Crédito row by date + debt-account-name appearing in the
    # outflow's description or category path.
    for i, row in enumerate(rows):
        if row.movement_type != "expense" or row.amount >= ZERO or row.mirror:
            continue

        norm_desc = _normalize_lookup_text(row.description)
        canonical_desc = _MONEYWIZ_DEBT_DESCRIPTION_ALIASES.get(norm_desc, norm_desc)
        combined_text = _normalize_lookup_text(f"{canonical_desc} {row.category_raw}")

        matched_j: int | None = None
        matched_liq_row: MoneyWizRow | None = None
        best_gap: Decimal | None = None
        total = row.amount.copy_abs()

        for (liq_date, liq_account_norm), candidates in liq_idx.items():
            if liq_date != row.booking_date:
                continue
            # Check that the debt account name (or any of its tokens) appears
            # in the outflow's combined text.
            tokens = [t for t in liq_account_norm.split() if len(t) > 2]
            if liq_account_norm not in combined_text and not any(
                t in combined_text for t in tokens
            ):
                continue
            # Pick the closest unmirrored candidate whose principal does not
            # exceed the observed cash outflow amount.
            for j in candidates:
                if j not in mirrored:
                    candidate = rows[j]
                    principal_candidate = candidate.amount.copy_abs()
                    if principal_candidate > total:
                        continue
                    gap = total - principal_candidate
                    if best_gap is None or gap < best_gap:
                        best_gap = gap
                        matched_j = j
                        matched_liq_row = candidate

        if matched_j is None or matched_liq_row is None:
            continue

        principal = matched_liq_row.amount.copy_abs()
        interest = total - principal

        new_warnings = [w for w in row.warnings if "provisional" not in w.lower()]
        if interest > ZERO:
            new_warnings.append(
                f"Deuda con intereses: principal {principal} EUR, "
                f"intereses {interest} EUR (total {total} EUR)."
            )
        new_warnings.append("La transferencia no usa clasificacion presupuestaria.")

        new_fingerprint = _build_fingerprint(
            booking_date=row.booking_date,
            description=row.description,
            memo=row.memo,
            category_raw=row.category_raw,
            account_name=row.account_name,
            counterparty_name=matched_liq_row.account_name,
            currency=row.currency,
            amount=row.amount,
            movement_type="debt_payment",
            flow_family="",
            category_key="",
            subcategory_key="",
        )
        new_existing_id = _find_existing_transaction(user_id=user_id, fingerprint=new_fingerprint)
        if new_existing_id is not None:
            new_warnings.append("Esta fila ya fue importada anteriormente; se omitira en commit.")

        updated[i] = dataclasses.replace(
            row,
            movement_type="debt_payment",
            counterparty_name=matched_liq_row.account_name,
            flow_family="",
            category_key="",
            subcategory_key="",
            fingerprint=new_fingerprint,
            warnings=new_warnings,
            existing_transaction_id=new_existing_id,
            principal_amount=principal,
            interest_amount=interest,
        )
        mirrored.add(matched_j)

    result = []
    for i, row in enumerate(rows):
        if i in updated:
            result.append(updated[i])
        elif i in mirrored:
            result.append(dataclasses.replace(row, mirror=True))
        else:
            result.append(row)
    return result


def _parse_moneywiz_tags(raw: str) -> str:
    """Parses the MoneyWiz 'Etiquetas' column into a normalized member_tag.

    Returns 'pablo', 'ana', 'compartido', or '' if absent/unknown.
    - 'Compartido; ' → 'compartido'
    - 'Pablo; ' → 'pablo'
    - 'Ana; ' → 'ana'
    - Multiple tags including 'Compartido' → 'compartido'
    - Multiple individual names → 'compartido'
    """
    if not raw:
        return ""
    parts = [_normalize_lookup_text(p) for p in raw.split(";") if p.strip()]
    parts = [p for p in parts if p]
    if not parts:
        return ""
    if "compartido" in parts:
        return "compartido"
    if len(parts) > 1:
        return "compartido"
    return parts[0]


def _normalize_row(
    *,
    user_id: int,
    row_number: int,
    raw_row: dict[str, str | None],
) -> MoneyWizRow:
    warnings: list[str] = []
    errors: list[str] = []
    row = _normalize_headers(raw_row)

    description = _clean_text(row.get("description") or row.get("memo"))
    memo = _clean_text(row.get("memo"))
    category_raw = _clean_text(row.get("category"))
    account_raw = _clean_text(row.get("account"))
    transfers_raw = _clean_text(row.get("transfers"))
    member_tag = _parse_moneywiz_tags(_clean_text(row.get("tags")))
    currency = _normalize_currency(
        row.get("currency") or row.get("account_currency") or row.get("currency_code")
    )
    booking_date = _parse_moneywiz_date(row.get("date") or row.get("booking_date"))
    if booking_date is None:
        errors.append("La fecha no es valida o falta en la fila.")
        booking_date = timezone.localdate()

    amount, amount_warning = _resolve_amount(row)
    if amount_warning:
        warnings.append(amount_warning)
    if amount is None:
        errors.append("El importe no es valido o falta en la fila.")
        amount = ZERO

    movement_type = _infer_movement_type(
        row=row,
        category_raw=category_raw,
        description=description,
        transfers_raw=transfers_raw,
        amount=amount,
    )
    flow_family, category_key, subcategory_key, classification_warnings = _classify_row(
        movement_type=movement_type,
        category_raw=category_raw,
        description=description,
    )
    warnings.extend(classification_warnings)

    account_name = _resolve_account_name(
        raw_name=account_raw,
        row_number=row_number,
        movement_type=movement_type,
        role="source",
        description=description,
        category_raw=category_raw,
    )
    counterparty_name = _resolve_counterparty_name(
        raw_name=transfers_raw,
        row_number=row_number,
        movement_type=movement_type,
        account_name=account_name,
        description=description,
        category_raw=category_raw,
    )

    fingerprint = _build_fingerprint(
        booking_date=booking_date,
        description=description,
        memo=memo,
        category_raw=category_raw,
        account_name=account_name,
        counterparty_name=counterparty_name,
        currency=currency,
        amount=amount,
        movement_type=movement_type,
        flow_family=flow_family,
        category_key=category_key,
        subcategory_key=subcategory_key,
    )
    existing_transaction_id = _find_existing_transaction(user_id=user_id, fingerprint=fingerprint)
    if existing_transaction_id is not None:
        warnings.append("Esta fila ya fue importada anteriormente; se omitira en commit.")

    if not account_raw:
        warnings.append("La columna Account esta vacia; se creara una cuenta provisional.")
    if movement_type in {"transfer", "investment_purchase", "debt_payment"} and not transfers_raw:
        warnings.append("La fila no trae contrapartida; se creara una cuenta provisional.")

    return MoneyWizRow(
        row_number=row_number,
        booking_date=booking_date,
        description=description or "Movimiento MoneyWiz",
        memo=memo,
        category_raw=category_raw,
        account_name=account_name,
        counterparty_name=counterparty_name,
        currency=currency,
        amount=amount,
        movement_type=movement_type,
        flow_family=flow_family,
        category_key=category_key,
        subcategory_key=subcategory_key,
        fingerprint=fingerprint,
        warnings=warnings,
        errors=errors,
        existing_transaction_id=existing_transaction_id,
        member_tag=member_tag,
    )


def _resolve_amount(row: dict[str, str]) -> tuple[Decimal | None, str | None]:
    for field_name, sign in (
        ("amount", 1),
        ("amount_incomes", 1),
        ("credits", 1),
        ("amount_expenses", -1),
        ("debits", -1),
    ):
        raw_value = _clean_text(row.get(field_name))
        if not raw_value:
            continue
        parsed = _parse_money_amount(raw_value)
        if parsed is None:
            return None, f'El valor de "{field_name}" no es valido.'
        return (parsed if sign > 0 else -abs(parsed)), None
    return None, None


def _infer_movement_type(
    *,
    row: dict[str, str],
    category_raw: str,
    description: str,
    transfers_raw: str,
    amount: Decimal,
) -> str:
    text = _normalize_lookup_text(f"{category_raw} {description}")
    has_category = bool(_clean_text(category_raw))
    has_synthetic_transfer_token = _is_synthetic_transfer_token(transfers_raw)
    if transfers_raw and not has_synthetic_transfer_token:
        return "transfer"
    # If MoneyWiz exported a machine token in Transfers, do not re-classify
    # as transfer from the description text (it commonly mirrors the same token).
    # Also require an empty category for description-based transfer fallback:
    # when a category exists (e.g. "Gastos > ..."), treat it as normal flow.
    if (
        (not has_synthetic_transfer_token)
        and (not has_category)
        and _looks_like_transfer_description(raw_description=description, normalized_text=text)
    ):
        return "transfer"
    if any(
        _contains_keyword(text, keyword)
        for keyword in (
            "loan",
            "mortgage",
            "credit card",
            "debt",
            "interest",
            "repayment",
        )
    ):
        return "debt_payment"
    # Common investment-income labels in MoneyWiz exports should not be
    # interpreted as investment purchases just because they mention "stock".
    if _contains_any_keyword(text, ("dividendo", "dividend", "coupon", "cupon")):
        return "income"
    if any(
        _contains_keyword(text, keyword)
        for keyword in (
            "investment",
            "invest",
            "etf",
            "fund",
            "crypto",
            "real estate",
            "property",
            "house",
            "vehicle",
            "furniture",
            "technology",
        )
    ):
        return "investment_purchase"
    # Categorías que fuerzan un tipo concreto independientemente del signo del importe.
    if _match_moneywiz_path_set(category_raw, _MONEYWIZ_DEBT_PAYMENT_PATHS):
        return "debt_payment"
    if _match_moneywiz_path_set(category_raw, _MONEYWIZ_INCOME_PATHS_ALWAYS):
        return "income"

    if row.get("amount_expenses") or row.get("debits") or amount < ZERO:
        # Categorías de "Pasivos > Activos financieros" que representan compra de
        # activos financieros (dinero de liquidez → inversión) aunque el CSV los
        # exporte como débito.
        if _match_moneywiz_path_set(category_raw, _MONEYWIZ_INVESTMENT_PURCHASE_PATHS):
            return "investment_purchase"
        return "expense"
    return "income"


def _contains_keyword(text: str, keyword: str) -> bool:
    """Matches whole words/phrases to avoid substring false positives.

    Example: "myinvestor premium" should not match "invest".
    """
    pattern = rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _contains_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    return any(_contains_keyword(text, keyword) for keyword in keywords)


def _looks_like_transfer_description(*, raw_description: str, normalized_text: str) -> bool:
    # Bank-export identifiers like "transfer_0049_xxx" are not reliable
    # transfer signals and often represent ordinary expense/income rows.
    raw_description_clean = (raw_description or "").strip().lower()
    if re.search(r"\b(transfer|transferencia|traspaso|move)_[a-z0-9_]+", raw_description_clean):
        return False
    # Also ignore machine-like tags produced from "transfer_####" after normalization.
    if re.search(r"\btransfer\s+\d{2,}\b", normalized_text) is not None:
        return False
    return (
        re.search(r"\btransferencia\s+(a|de)\b", normalized_text) is not None
        or re.search(r"\btransfer\s+(to|from)\b", normalized_text) is not None
        or re.search(r"\bmove\s+(to|from)\b", normalized_text) is not None
    )


def _is_synthetic_transfer_token(value: str) -> bool:
    cleaned = _clean_text(value).lower()
    return (
        re.search(r"^(transfer|transferencia|traspaso|move)_[a-z0-9_]+$", cleaned) is not None
        or re.search(r"^(transfer|transferencia|traspaso|move)-[a-z0-9_-]+$", cleaned) is not None
    )


def _lookup_moneywiz_path(
    category_raw: str,
    path_map: dict[str, tuple[str, str]],
) -> tuple[str, str] | None:
    """Matches MoneyWiz category path from most-specific to least-specific prefix."""
    parts = [_normalize_lookup_text(p) for p in category_raw.split(">")]
    parts = [p for p in parts if p]
    for length in range(len(parts), 0, -1):
        key = " > ".join(parts[:length])
        if key in path_map:
            return path_map[key]
    return None


def _match_moneywiz_path_set(category_raw: str, path_set: frozenset[str]) -> bool:
    """Returns True if any prefix of the category path is in path_set."""
    parts = [_normalize_lookup_text(p) for p in category_raw.split(">")]
    parts = [p for p in parts if p]
    for length in range(len(parts), 0, -1):
        if " > ".join(parts[:length]) in path_set:
            return True
    return False


def _classify_row(
    *,
    movement_type: str,
    category_raw: str,
    description: str,
) -> tuple[str, str, str, list[str]]:
    warnings: list[str] = []
    text = _normalize_lookup_text(f"{category_raw} {description}")

    if movement_type == "income":
        path_result = _lookup_moneywiz_path(category_raw, _MONEYWIZ_INCOME_PATH)
        if path_result is not None:
            return "income", path_result[0], path_result[1], warnings
        classification = _resolve_income_classification(text)
        if classification is None:
            warnings.append(
                "Categoria sin mapeo exacto; se usara el fallback seguro other_income/misc."
            )
            return "income", "other_income", "misc", warnings
        if classification == ("other_income", "misc"):
            warnings.append("Categoria de ingreso normalizada con fallback seguro.")
        return "income", classification[0], classification[1], warnings

    if movement_type == "expense":
        path_result = _lookup_moneywiz_path(category_raw, _MONEYWIZ_EXPENSE_PATH)
        if path_result is not None:
            return "expense", path_result[0], path_result[1], warnings
        classification = _resolve_expense_classification(text)
        if classification is None:
            warnings.append(
                "Categoria sin mapeo exacto; se usara el fallback seguro "
                "consumption_expenses/other_consumption_expenses."
            )
            return "expense", "consumption_expenses", "other_consumption_expenses", warnings
        return "expense", classification[0], classification[1], warnings

    if movement_type == "debt_payment":
        warnings.append(
            "El pago de deuda se importara como movimiento patrimonial sin desglose de intereses."
        )
    elif movement_type == "investment_purchase":
        warnings.append("La compra de inversion se importara sin clasificacion presupuestaria.")
    elif movement_type == "revaluation":
        warnings.append(
            "La revalorizacion se importara como ajuste de valor sin clasificacion presupuestaria."
        )
    elif movement_type == "transfer":
        warnings.append("La transferencia no usa clasificacion presupuestaria.")

    return "", "", "", warnings


def _resolve_income_classification(text: str) -> tuple[str, str] | None:
    rules = [
        ("salary", ("salary", "employee_salary")),
        ("payroll", ("salary", "employee_salary")),
        ("wage", ("salary", "employee_salary")),
        ("bonus", ("salary", "bonus_commission")),
        ("commission", ("salary", "bonus_commission")),
        ("dividend", ("passive_income", "dividends")),
        ("interest", ("passive_income", "interest_income")),
        ("rent", ("passive_income", "real_estate_rent")),
        ("staking", ("passive_income", "staking_yield")),
        ("p2p", ("passive_income", "p2p_lending")),
        ("tax refund", ("other_income", "tax_refund")),
        ("refund", ("other_income", "tax_refund")),
        ("gift", ("transfers_support", "gifts_received")),
        ("inheritance", ("transfers_support", "inheritance")),
        ("alimony", ("transfers_support", "alimony_received")),
        ("benefit", ("public_benefits", "other_public_benefits")),
        ("subsidy", ("public_benefits", "subsidy_grant")),
    ]
    for keyword, classification in rules:
        if keyword in text:
            return classification
    if text in {"salary", "business", "passive income", "capital gains"}:
        return "other_income", "misc"
    return None


def _resolve_expense_classification(text: str) -> tuple[str, str] | None:
    rules = [
        ("emergency fund", ("savings_allocation", "emergency_fund")),
        ("savings", ("savings_allocation", "short_term_savings")),
        ("cash reserve", ("savings_allocation", "cash_reserve")),
        ("fund", ("financial_investments", "index_funds")),
        ("etf", ("financial_investments", "etf_indexed")),
        ("stock", ("financial_investments", "stocks_dividends")),
        ("crypto", ("financial_investments", "crypto")),
        ("roboadvisor", ("financial_investments", "roboadvisor")),
        ("crowdlending", ("financial_investments", "crowdlending_p2p")),
        ("crowdfunding", ("financial_investments", "crowdfunding_real_estate")),
        ("mortgage principal", ("real_estate_assets", "mortgage_principal")),
        ("mortgage", ("real_estate_assets", "mortgage_principal")),
        ("property purchase", ("real_estate_assets", "property_purchase")),
        ("real estate", ("real_estate_assets", "property_purchase")),
        ("house", ("real_estate_assets", "property_purchase")),
        ("vehicle", ("tangible_assets", "vehicle_purchase")),
        ("car", ("tangible_assets", "vehicle_purchase")),
        ("furniture", ("tangible_assets", "home_furniture_appliances")),
        ("technology", ("tangible_assets", "technology_devices")),
        ("jewelry", ("tangible_assets", "jewelry_collectibles")),
        ("housing", ("consumption_expenses", "housing_home")),
        ("rent", ("consumption_expenses", "housing_home")),
        ("food", ("consumption_expenses", "living_expenses")),
        ("grocery", ("consumption_expenses", "living_expenses")),
        ("supermarket", ("consumption_expenses", "living_expenses")),
        ("child", ("consumption_expenses", "family_childcare")),
        ("transport", ("consumption_expenses", "transport_mobility")),
        ("fuel", ("consumption_expenses", "transport_mobility")),
        ("health", ("consumption_expenses", "health_wellbeing")),
        ("education", ("consumption_expenses", "education_growth")),
        ("leisure", ("consumption_expenses", "leisure_lifestyle")),
        ("gift", ("consumption_expenses", "gifts_donations")),
        ("donation", ("consumption_expenses", "gifts_donations")),
        ("loan", ("consumption_expenses", "financial_commitments")),
        ("credit card", ("consumption_expenses", "financial_commitments")),
        ("interest", ("consumption_expenses", "financial_commitments")),
        ("fee", ("consumption_expenses", "financial_commitments")),
    ]
    for keyword, classification in rules:
        if keyword in text:
            return classification
    if text in {"financial investments", "real estate assets", "tangible assets"}:
        return "consumption_expenses", "other_consumption_expenses"
    return None


def _resolve_account_name(
    *,
    raw_name: str,
    row_number: int,
    movement_type: str,
    role: str,
    description: str,
    category_raw: str,
) -> str:
    cleaned = _clean_text(raw_name)
    if cleaned:
        return cleaned
    seed = _normalize_lookup_text(description or category_raw or movement_type or "import")
    seed = seed.replace(" ", "_")[:32] or "import"
    return f"MoneyWiz {role} {row_number} {seed}".strip()


def _resolve_counterparty_name(
    *,
    raw_name: str,
    row_number: int,
    movement_type: str,
    account_name: str,
    description: str,
    category_raw: str,
) -> str:
    if _clean_text(raw_name):
        return _clean_text(raw_name)
    # For debt_payment rows without an explicit counterparty (typical in MoneyWiz liability
    # accounts like Hipoteca, Ibi, etc.), derive a stable name from the source account so
    # the user sees "Deuda: Hipoteca" instead of "MoneyWiz counterparty 379 liquidacion_credito".
    if movement_type == "debt_payment" and account_name:
        return f"Deuda: {account_name}"
    return _resolve_account_name(
        raw_name="",
        row_number=row_number,
        movement_type=movement_type,
        role="counterparty",
        description=description,
        category_raw=category_raw,
    )


def _build_fingerprint(
    *,
    booking_date: date,
    description: str,
    memo: str,
    category_raw: str,
    account_name: str,
    counterparty_name: str,
    currency: str,
    amount: Decimal,
    movement_type: str,
    flow_family: str,
    category_key: str,
    subcategory_key: str,
) -> str:
    payload = "|".join(
        [
            booking_date.isoformat(),
            description,
            memo,
            category_raw,
            account_name,
            counterparty_name,
            currency,
            _format_money(amount),
            movement_type,
            flow_family,
            category_key,
            subcategory_key,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _find_existing_transaction(*, user_id: int, fingerprint: str) -> int | None:
    transaction_row = (
        LedgerTransaction.objects.filter(
            user_id=user_id,
            import_source="moneywiz",
            import_fingerprint=fingerprint,
        )
        .only("id")
        .first()
    )
    return transaction_row.id if transaction_row is not None else None


def _import_moneywiz_row(
    *, user, row: MoneyWizRow, account_id_map: dict[str, int] | None = None
) -> LedgerTransaction:
    source_account = _get_or_create_moneywiz_account(
        user=user,
        account_type=cast(str, LedgerAccount.AccountType.ASSET),
        currency=row.currency,
        name=row.account_name,
        account_id_map=account_id_map,
    )
    if row.movement_type == "income":
        return create_quick_transaction(
            user=user,
            movement_type="income",
            booking_date=row.booking_date,
            value_date=row.booking_date,
            description=row.description,
            amount=row.amount.copy_abs(),
            account=source_account,
            counterparty_account=get_or_create_system_account(
                user_id=user.id,
                account_type=cast(str, LedgerAccount.AccountType.INCOME),
                currency=row.currency,
                name=_system_counterparty_name(
                    "income", row.category_key, row.subcategory_key, row.category_raw
                ),
            ),
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.IMPORT,
            notes=row.memo,
            import_source="moneywiz",
            import_fingerprint=row.fingerprint,
            member_tag=row.member_tag,
            flow_family=row.flow_family,
            category_key=row.category_key,
            subcategory_key=row.subcategory_key,
        )

    if row.movement_type == "expense":
        return create_quick_transaction(
            user=user,
            movement_type="expense",
            booking_date=row.booking_date,
            value_date=row.booking_date,
            description=row.description,
            amount=row.amount.copy_abs(),
            account=source_account,
            counterparty_account=get_or_create_system_account(
                user_id=user.id,
                account_type=cast(str, LedgerAccount.AccountType.EXPENSE),
                currency=row.currency,
                name=_system_counterparty_name(
                    "expense", row.category_key, row.subcategory_key, row.category_raw
                ),
            ),
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.IMPORT,
            notes=row.memo,
            import_source="moneywiz",
            import_fingerprint=row.fingerprint,
            member_tag=row.member_tag,
            flow_family=row.flow_family,
            category_key=row.category_key,
            subcategory_key=row.subcategory_key,
        )

    if row.movement_type == "transfer":
        target_account = _get_or_create_moneywiz_account(
            user=user,
            account_type=cast(str, LedgerAccount.AccountType.ASSET),
            currency=row.currency,
            name=row.counterparty_name,
            account_id_map=account_id_map,
        )
        return create_quick_transaction(
            user=user,
            movement_type="transfer",
            booking_date=row.booking_date,
            value_date=row.booking_date,
            description=row.description,
            amount=row.amount.copy_abs(),
            account=source_account,
            counterparty_account=target_account,
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.IMPORT,
            notes=row.memo,
            import_source="moneywiz",
            import_fingerprint=row.fingerprint,
            member_tag=row.member_tag,
        )

    if row.movement_type == "investment_purchase":
        target_account = _get_or_create_moneywiz_account(
            user=user,
            account_type=cast(str, LedgerAccount.AccountType.ASSET),
            currency=row.currency,
            name=row.counterparty_name,
            account_id_map=account_id_map,
        )
        return create_quick_transaction(
            user=user,
            movement_type="investment_purchase",
            booking_date=row.booking_date,
            value_date=row.booking_date,
            description=row.description,
            amount=row.amount.copy_abs(),
            account=source_account,
            counterparty_account=target_account,
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.IMPORT,
            notes=row.memo,
            import_source="moneywiz",
            import_fingerprint=row.fingerprint,
            member_tag=row.member_tag,
        )

    if row.movement_type == "debt_payment":
        target_account = _get_or_create_moneywiz_account(
            user=user,
            account_type=cast(str, LedgerAccount.AccountType.LIABILITY),
            currency=row.currency,
            name=row.counterparty_name,
            account_id_map=account_id_map,
        )
        principal = (
            row.principal_amount if row.principal_amount is not None else row.amount.copy_abs()
        )
        interest = row.interest_amount if row.interest_amount is not None else ZERO
        interest_account = None
        if interest > ZERO:
            interest_account = get_or_create_system_account(
                user_id=user.id,
                account_type=cast(str, LedgerAccount.AccountType.EXPENSE),
                currency=row.currency,
                name=_system_counterparty_name(
                    "expense",
                    "consumption_expenses",
                    "financial_commitments",
                    row.category_raw,
                ),
            )
        return create_quick_transaction(
            user=user,
            movement_type="debt_payment",
            booking_date=row.booking_date,
            value_date=row.booking_date,
            description=row.description,
            amount=row.amount.copy_abs(),
            account=source_account,
            counterparty_account=target_account,
            liability_account=target_account,
            principal_amount=principal,
            interest_amount=interest,
            interest_account=interest_account,
            flow_family="expense" if interest > ZERO else "",
            category_key="consumption_expenses" if interest > ZERO else "",
            subcategory_key="financial_commitments" if interest > ZERO else "",
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.IMPORT,
            notes=row.memo,
            import_source="moneywiz",
            import_fingerprint=row.fingerprint,
            member_tag=row.member_tag,
        )

    if row.movement_type == "revaluation":
        return create_quick_transaction(
            user=user,
            movement_type="revaluation",
            booking_date=row.booking_date,
            value_date=row.booking_date,
            description=row.description,
            amount=row.amount.copy_abs(),
            account=source_account,
            counterparty_account=get_or_create_system_account(
                user_id=user.id,
                account_type=cast(str, LedgerAccount.AccountType.EXPENSE),
                currency=row.currency,
                name=_system_counterparty_name(
                    "revaluation", row.category_key, row.subcategory_key, row.category_raw
                ),
            ),
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.IMPORT,
            notes=row.memo,
            import_source="moneywiz",
            import_fingerprint=row.fingerprint,
            member_tag=row.member_tag,
        )

    raise ValidationError(
        {"movement_type": f"Tipo de movimiento MoneyWiz no soportado: {row.movement_type}"}
    )


def _get_or_create_moneywiz_account(
    *,
    user,
    account_type: str,
    currency: str,
    name: str,
    account_id_map: dict[str, int] | None = None,
) -> LedgerAccount:
    normalized_currency = _normalize_currency(currency)
    # If the user mapped this CSV account name to an existing account ID, use it directly.
    if account_id_map and name in account_id_map:
        mapped = LedgerAccount.objects.filter(user=user, id=account_id_map[name]).first()
        if mapped is None:
            raise ValidationError(
                {
                    "account_id_map": f"La cuenta mapeada para '{name}' no existe o no pertenece al usuario."
                }
            )
        account_pair = {mapped.account_type, account_type}
        asset_liability_pair = {
            cast(str, LedgerAccount.AccountType.ASSET),
            cast(str, LedgerAccount.AccountType.LIABILITY),
        }
        # MoneyWiz may represent debt accounts as operational sources in some rows;
        # allow mapped asset/liability interchange while keeping strict checks for
        # all other account-type combinations.
        if mapped.account_type != account_type and account_pair != asset_liability_pair:
            raise ValidationError(
                {
                    "account_id_map": (
                        f"La cuenta mapeada para '{name}' debe ser de tipo "
                        f"'{account_type}' y es '{mapped.account_type}'."
                    )
                }
            )
        if mapped.currency != normalized_currency:
            raise ValidationError(
                {
                    "account_id_map": (
                        f"La cuenta mapeada para '{name}' debe tener moneda "
                        f"'{normalized_currency}' y es '{mapped.currency}'."
                    )
                }
            )
        return mapped

    normalized_name = _clean_text(name) or "Imported MoneyWiz account"
    account = LedgerAccount.objects.filter(
        user=user,
        account_type=account_type,
        currency=normalized_currency,
        name=normalized_name,
    ).first()
    if account is not None:
        return account
    return LedgerAccount.objects.create(
        user=user,
        name=normalized_name,
        account_type=account_type,
        currency=normalized_currency,
        origin=LedgerAccount.Origin.SYSTEM,
    )


def _system_counterparty_name(
    movement_type: str,
    category_key: str,
    subcategory_key: str,
    category_raw: str,
) -> str:
    if category_key and subcategory_key:
        return f"MoneyWiz {movement_type}: {category_key}/{subcategory_key}"
    if _clean_text(category_raw):
        return f"MoneyWiz {movement_type}: {_clean_text(category_raw)}"
    return f"MoneyWiz {movement_type}"


def _build_preview_payload(*, delimiter: str, rows: list[MoneyWizRow]) -> dict:
    stats = {
        "income": 0,
        "expense": 0,
        "transfer": 0,
        "investment_purchase": 0,
        "debt_payment": 0,
        "revaluation": 0,
        "fallback_classifications": 0,
        "auto_created_accounts": 0,
        "existing_rows": 0,
        "duplicate_rows": 0,
        "mirror_rows": 0,
        "created_transactions": 0,
        "skipped_existing": 0,
    }
    warnings: list[str] = []
    payload_rows = []
    for row in rows:
        if row.mirror:
            stats["mirror_rows"] += 1
            payload_rows.append(_serialize_row(row))
            continue
        if row.movement_type in stats:
            stats[row.movement_type] += 1
        if row.existing_transaction_id is not None:
            stats["existing_rows"] += 1
        if any("fallback" in warning.lower() for warning in row.warnings):
            stats["fallback_classifications"] += 1
        if any("provisional" in warning.lower() for warning in row.warnings):
            stats["auto_created_accounts"] += 1
        if any("duplicada dentro del archivo" in warning.lower() for warning in row.warnings):
            stats["duplicate_rows"] += 1
        warnings.extend(row.warnings)
        payload_rows.append(_serialize_row(row))

    return {
        "delimiter": delimiter,
        "row_count": len(rows),
        "valid_row_count": sum(1 for row in rows if not row.errors and not row.mirror),
        "error_row_count": sum(1 for row in rows if row.errors),
        "duplicate_row_count": stats["duplicate_rows"],
        "existing_row_count": stats["existing_rows"],
        "mirror_row_count": stats["mirror_rows"],
        "warnings": _dedupe_preserve_order(warnings),
        "stats": stats,
        "detected_accounts": _build_detected_accounts(rows),
        "unmapped_categories": _build_unmapped_categories(rows),
        "rows": payload_rows,
    }


def _build_unmapped_categories(rows: list[MoneyWizRow]) -> list[dict]:
    """Returns unique categories that used a fallback classification, sorted by row count."""
    seen: dict[tuple[str, str], dict] = {}
    for row in rows:
        if row.movement_type not in ("income", "expense"):
            continue
        if not any("fallback" in w.lower() for w in row.warnings):
            continue
        key = (row.movement_type, row.category_raw)
        if key not in seen:
            seen[key] = {
                "category_raw": row.category_raw,
                "movement_type": row.movement_type,
                "fallback_category_key": row.category_key,
                "fallback_subcategory_key": row.subcategory_key,
                "row_count": 0,
            }
        seen[key]["row_count"] += 1
    return sorted(seen.values(), key=lambda x: -x["row_count"])


def _build_detected_accounts(rows: list[MoneyWizRow]) -> list[dict]:
    # Pre-pass: any account that appears as a debt_payment counterparty is
    # definitely a liability — even if it also appears as a source account in
    # its own rows (e.g. a credit card that has spending rows AND receives
    # payments from a bank account).
    known_liabilities: set[str] = {
        row.counterparty_name
        for row in rows
        if not row.mirror and row.movement_type == "debt_payment" and row.counterparty_name
    }

    # Key is (name, account_type, currency).  Using the resolved account_type
    # means a credit card that is both a source and a debt_payment counterparty
    # collapses into a single LIABILITY entry instead of producing duplicates.
    detected: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        if row.mirror:
            continue
        src_account_type = (
            cast(str, LedgerAccount.AccountType.LIABILITY)
            if row.account_name in known_liabilities
            else cast(str, LedgerAccount.AccountType.ASSET)
        )
        source_key = (row.account_name, src_account_type, row.currency)
        detected.setdefault(
            source_key,
            {
                "name": row.account_name,
                "account_type": src_account_type,
                "currency": row.currency,
                "role": "source",
                "status": "existing_or_created",
            },
        )
        if row.movement_type in {"transfer", "investment_purchase"}:
            target_key = (
                row.counterparty_name,
                cast(str, LedgerAccount.AccountType.ASSET),
                row.currency,
            )
            detected.setdefault(
                target_key,
                {
                    "name": row.counterparty_name,
                    "account_type": cast(str, LedgerAccount.AccountType.ASSET),
                    "currency": row.currency,
                    "role": "counterparty",
                    "status": "existing_or_created",
                },
            )
        elif row.movement_type == "debt_payment":
            target_key = (
                row.counterparty_name,
                cast(str, LedgerAccount.AccountType.LIABILITY),
                row.currency,
            )
            detected.setdefault(
                target_key,
                {
                    "name": row.counterparty_name,
                    "account_type": cast(str, LedgerAccount.AccountType.LIABILITY),
                    "currency": row.currency,
                    "role": "counterparty",
                    "status": "existing_or_created",
                },
            )
    return list(detected.values())


def _serialize_row(row: MoneyWizRow) -> dict:
    return {
        "row_number": row.row_number,
        "booking_date": row.booking_date.isoformat(),
        "description": row.description,
        "memo": row.memo,
        "category": row.category_raw,
        "account_name": row.account_name,
        "counterparty_name": row.counterparty_name,
        "currency": row.currency,
        "amount": _format_money(row.amount),
        "movement_type": row.movement_type,
        "flow_family": row.flow_family,
        "category_key": row.category_key,
        "subcategory_key": row.subcategory_key,
        "fingerprint": row.fingerprint,
        "existing_transaction_id": row.existing_transaction_id,
        "member_tag": row.member_tag,
        "warnings": list(row.warnings),
        "errors": list(row.errors),
        "mirror": row.mirror,
    }


def _normalize_headers(raw_row: dict[str, str | None]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in raw_row.items():
        canonical = _canonical_header(key)
        if canonical is None:
            continue
        cleaned = _clean_text(value)
        if cleaned and canonical not in normalized:
            normalized[canonical] = cleaned
    return normalized


def _canonical_header(value: str | None) -> str | None:
    normalized = _normalize_lookup_text(value or "")
    aliases = {
        "date": {"date", "booking date", "transaction date", "booking_date", "fecha"},
        "description": {"description", "payee", "name", "descripcion", "beneficiario"},
        "memo": {"memo", "note", "notes", "memoria"},
        "category": {"category", "categories", "categoria"},
        "account": {"account", "account name", "from account", "cuentas"},
        "transfers": {"transfers", "transfer", "transfer account", "to", "transferencias"},
        "amount": {"amount", "importe"},
        "amount_expenses": {"amount expenses", "amount (expenses)", "amount expense"},
        "amount_incomes": {"amount incomes", "amount (incomes)", "amount income"},
        "credits": {"credits", "credit"},
        "debits": {"debits", "debit"},
        "currency": {"currency", "currency code", "moneda"},
        "account_currency": {"account currency"},
        "currency_code": {"currency code"},
        "tags": {"tags", "tag", "etiquetas", "etiqueta", "labels", "label"},
    }
    for canonical, options in aliases.items():
        if normalized in options:
            return canonical
    return None


def _parse_moneywiz_date(value: str | None) -> date | None:
    cleaned = _clean_text(value)
    if not cleaned:
        return None
    try:
        return datetime.fromisoformat(cleaned).date()
    except ValueError:
        pass
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d/%m/%y", "%m/%d/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(cleaned, pattern).date()
        except ValueError:
            continue
    return None


def _parse_money_amount(value: str) -> Decimal | None:
    cleaned = _clean_text(value)
    if not cleaned:
        return None
    cleaned = cleaned.replace(" ", "")
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    if cleaned.count(",") > 0 and cleaned.count(".") > 0:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif cleaned.count(",") > 0:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        parsed = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    if negative:
        parsed = -abs(parsed)
    return parsed.quantize(TWOPLACES)


def _format_money(value: Decimal) -> str:
    return str(value.quantize(TWOPLACES))


def _normalize_currency(value: str | None) -> str:
    return _clean_text(value).upper()[:3] or DEFAULT_IMPORT_CURRENCY


def _clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_lookup_text(value: str | None) -> str:
    text = (
        unicodedata.normalize("NFKD", _clean_text(value)).encode("ascii", "ignore").decode("ascii")
    )
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
