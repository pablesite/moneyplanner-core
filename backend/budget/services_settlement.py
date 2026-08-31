from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import cast

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.services import get_base_currency_for_user
from accounting.models import LedgerEntry, LedgerTransaction
from memberships.models import FamilyMember, Ownership, OwnershipLink
from memberships.services_allocations import resolve_ownership_allocation
from net_worth.models import Asset
from net_worth.services_assets_core import get_effective_asset_amount

from .models import (
    AnnualExpenseEntry,
    SettlementAccount,
    SettlementOpeningAdjustment,
    SettlementOpeningBalance,
    SettlementProfile,
    SettlementSnapshot,
    SettlementWalletNormalization,
)
from .services import (
    effective_annual_expense_entries,
    effective_annual_income_entries,
    planned_expense_monthly_distribution,
)

ZERO = Decimal("0")
AMOUNT_STEP = Decimal("0.00000001")
MONEY_STEP = Decimal("0.01")


def get_or_create_settlement_profile(*, user) -> SettlementProfile:
    return SettlementProfile.objects.get_or_create(
        user=user,
        defaults={"base_currency": get_base_currency_for_user(user=user)},
    )[0]


def _ownership_for_asset(*, user, asset_id: int) -> Ownership | None:
    link = (
        OwnershipLink.objects.filter(
            user=user,
            target_type=OwnershipLink.TargetType.ASSET,
            target_id=asset_id,
        )
        .select_related("ownership", "ownership__member")
        .prefetch_related("ownership__splits", "ownership__splits__member")
        .first()
    )
    return link.ownership if link is not None else None


def _physical_wallet_accounts(profile: SettlementProfile) -> list[SettlementAccount]:
    return list(
        profile.accounts.filter(role=SettlementAccount.Role.PHYSICAL_CASH)
        .select_related("asset")
        .order_by("id")
    )


def _validated_wallet_normalization_transactions(
    *, user, profile: SettlementProfile, transaction_ids: list[int]
) -> list[LedgerTransaction]:
    unique_ids = list(dict.fromkeys(transaction_ids))
    if len(unique_ids) != len(transaction_ids):
        raise ValidationError(
            {"normalization_transaction_ids": "No repitas una transferencia de normalizacion."}
        )
    transactions = list(
        LedgerTransaction.objects.filter(user=user, id__in=unique_ids)
        .prefetch_related("entries")
        .order_by("booking_date", "id")
    )
    if len(transactions) != len(unique_ids):
        raise ValidationError(
            {"normalization_transaction_ids": "Alguna transferencia no pertenece al usuario."}
        )
    wallet_ledger_ids = {
        account.asset.accounting_account_id
        for account in _physical_wallet_accounts(profile)
        if account.asset.accounting_account_id is not None
    }
    for row in transactions:
        entries = list(row.entries.all())
        if (
            row.status != LedgerTransaction.Status.POSTED
            or row.quick_entry_kind != LedgerTransaction.QuickEntryKind.TRANSFER
            or len(entries) < 2
            or any(entry.account_id not in wallet_ledger_ids for entry in entries)
        ):
            raise ValidationError(
                {
                    "normalization_transaction_ids": (
                        f"{row.id} debe ser una transferencia contabilizada exclusivamente "
                        "entre monederos fisicos configurados."
                    )
                }
            )
    conflict = SettlementWalletNormalization.objects.filter(transaction_id__in=unique_ids).exclude(
        profile=profile
    )
    if conflict.exists():
        raise ValidationError(
            {"normalization_transaction_ids": "Una transferencia ya pertenece a otro perfil."}
        )
    return transactions


def _replace_wallet_normalizations(
    *, user, profile: SettlementProfile, transaction_ids: list[int]
) -> None:
    transactions = _validated_wallet_normalization_transactions(
        user=user, profile=profile, transaction_ids=transaction_ids
    )
    profile.wallet_normalizations.exclude(transaction_id__in=transaction_ids).delete()
    for transaction_row in transactions:
        SettlementWalletNormalization.objects.get_or_create(
            profile=profile, transaction=transaction_row
        )


def _wallet_normalization_deltas(
    *, profile: SettlementProfile, after_date: date, through_date: date | None = None
) -> dict[int, Decimal]:
    accounts = _physical_wallet_accounts(profile)
    account_by_ledger = {
        account.asset.accounting_account_id: account
        for account in accounts
        if account.asset.accounting_account_id is not None
    }
    rows = profile.wallet_normalizations.filter(
        transaction__booking_date__gt=after_date,
        transaction__status=LedgerTransaction.Status.POSTED,
    )
    if through_date is not None:
        rows = rows.filter(transaction__booking_date__lte=through_date)
    rows = rows.prefetch_related("transaction__entries")
    deltas: dict[int, Decimal] = {account.id: ZERO for account in accounts}
    for normalization in rows:
        for entry in normalization.transaction.entries.all():
            account = account_by_ledger.get(entry.account_id)
            if account is None:
                continue
            signed = (
                Decimal(entry.amount)
                if entry.side == LedgerEntry.Side.DEBIT
                else -Decimal(entry.amount)
            )
            deltas[account.id] += signed
    return deltas


def _wallet_normalization_candidates(
    *, user, profile: SettlementProfile, after_date: date
) -> list[dict[str, object]]:
    accounts = _physical_wallet_accounts(profile)
    account_by_ledger = {
        account.asset.accounting_account_id: account
        for account in accounts
        if account.asset.accounting_account_id is not None
    }
    selected_ids = set(profile.wallet_normalizations.values_list("transaction_id", flat=True))
    transactions = (
        LedgerTransaction.objects.filter(
            user=user,
            status=LedgerTransaction.Status.POSTED,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.TRANSFER,
            booking_date__gt=after_date,
            entries__account_id__in=account_by_ledger,
        )
        .distinct()
        .prefetch_related("entries")
        .order_by("booking_date", "id")
    )
    result: list[dict[str, object]] = []
    for transaction_row in transactions:
        entries = list(transaction_row.entries.all())
        if len(entries) < 2 or any(entry.account_id not in account_by_ledger for entry in entries):
            continue
        result.append(
            {
                "transaction_id": transaction_row.id,
                "booking_date": transaction_row.booking_date.isoformat(),
                "description": transaction_row.description,
                "selected": transaction_row.id in selected_ids,
                "entries": [
                    {
                        "asset_id": account_by_ledger[entry.account_id].asset_id,
                        "asset_name": account_by_ledger[entry.account_id].asset.name,
                        "amount": str(
                            Decimal(entry.amount)
                            if entry.side == LedgerEntry.Side.DEBIT
                            else -Decimal(entry.amount)
                        ),
                    }
                    for entry in entries
                ],
            }
        )
    return result


def derive_expense_settlement_fields(*, expense: AnnualExpenseEntry) -> dict[str, object]:
    """Resolve fields owned by a linked asset when the relationship is unambiguous."""
    if expense.source_asset_id is None:
        return {}
    ownership = _ownership_for_asset(user=expense.user, asset_id=expense.source_asset_id)
    account = (
        SettlementAccount.objects.filter(
            profile__user=expense.user,
            asset_id=expense.source_asset_id,
            role=SettlementAccount.Role.ALLOCATION_DESTINATION,
        )
        .order_by("id")
        .first()
    )
    result: dict[str, object] = {}
    if ownership is not None:
        result["ownership"] = ownership
    if account is not None:
        result["settlement_account"] = account
    return result


def expected_expense_settlement_role(*, expense: AnnualExpenseEntry) -> str:
    if expense.cashflow_role in {
        AnnualExpenseEntry.CashflowRole.SAVINGS,
        AnnualExpenseEntry.CashflowRole.INVESTMENT,
    }:
        return cast(str, SettlementAccount.Role.ALLOCATION_DESTINATION)
    return cast(str, SettlementAccount.Role.OPERATING)


def is_expense_settlement_destination_compatible(
    *, expense: AnnualExpenseEntry, destination: SettlementAccount
) -> bool:
    if expense.cashflow_role == AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT:
        return destination.role in {
            SettlementAccount.Role.OPERATING,
            SettlementAccount.Role.ALLOCATION_DESTINATION,
        }
    return destination.role == expected_expense_settlement_role(expense=expense)


def resolve_expense_settlement_destination(
    *, expense: AnnualExpenseEntry, accounts: list[SettlementAccount]
) -> SettlementAccount | None:
    account_by_id = {account.id: account for account in accounts}
    if expense.settlement_account_id is not None:
        return account_by_id.get(expense.settlement_account_id)

    derived = derive_expense_settlement_fields(expense=expense).get("settlement_account")
    if isinstance(derived, SettlementAccount):
        return account_by_id.get(derived.id)

    if expected_expense_settlement_role(expense=expense) == SettlementAccount.Role.OPERATING:
        operating_accounts = [
            account for account in accounts if account.role == SettlementAccount.Role.OPERATING
        ]
        if len(operating_accounts) == 1:
            return operating_accounts[0]
    return None


def _validate_configuration_payload(*, user, payload: dict) -> tuple[list[dict], list[dict]]:
    account_rows = payload.get("accounts", [])
    adjustment_rows = payload.get("opening_adjustments", [])
    asset_ids = [row["asset_id"] for row in account_rows]
    if len(asset_ids) != len(set(asset_ids)):
        raise ValidationError({"accounts": "Cada activo solo puede configurarse una vez."})

    assets = {asset.id: asset for asset in Asset.objects.filter(user=user, id__in=asset_ids)}
    if len(assets) != len(asset_ids):
        raise ValidationError({"accounts": "Alguna cuenta no pertenece al usuario."})

    member_ids = {
        row.get("member_id")
        for row in [*account_rows, *adjustment_rows]
        if row.get("member_id") is not None
    }
    members = {
        member.id: member for member in FamilyMember.objects.filter(user=user, id__in=member_ids)
    }
    if len(members) != len(member_ids):
        raise ValidationError({"accounts": "Algun miembro no pertenece al usuario."})

    normalized_accounts: list[dict] = []
    for row in account_rows:
        asset = assets[row["asset_id"]]
        role = row["role"]
        member_id = row.get("member_id")
        accepted_balance = row.get("accepted_physical_balance")
        if role != SettlementAccount.Role.ALLOCATION_DESTINATION and (
            asset.category != Asset.Category.CASH
        ):
            raise ValidationError({"accounts": f"{asset.name} no es una cuenta de liquidez."})
        if role == SettlementAccount.Role.PERSONAL_DESTINATION and member_id is None:
            raise ValidationError({"accounts": "Un destino personal requiere miembro."})
        if role != SettlementAccount.Role.PERSONAL_DESTINATION and member_id is not None:
            raise ValidationError({"accounts": "Solo un destino personal puede indicar miembro."})
        if role == SettlementAccount.Role.PHYSICAL_CASH:
            if asset.subcategory != Asset.Subcategory.WALLET:
                raise ValidationError({"accounts": "El efectivo fisico debe ser un monedero."})
            if accepted_balance is None:
                raise ValidationError(
                    {"accounts": "Un monedero requiere el saldo fisico aceptado."}
                )
        elif accepted_balance is not None:
            raise ValidationError(
                {"accounts": "El saldo fisico aceptado solo se usa en monederos."}
            )
        if role != SettlementAccount.Role.PERSONAL_DESTINATION and row.get("is_primary"):
            raise ValidationError(
                {"accounts": "Solo un destino personal puede marcarse como principal."}
            )
        normalized_accounts.append(
            {
                "asset": asset,
                "role": role,
                "member": members.get(member_id),
                "currency": asset.currency.strip().upper(),
                "is_primary": bool(row.get("is_primary", False)),
                "accepted_physical_balance": accepted_balance,
            }
        )

    primary_keys = [
        (row["member"].id, row["currency"])
        for row in normalized_accounts
        if row["role"] == SettlementAccount.Role.PERSONAL_DESTINATION and row["is_primary"]
    ]
    if len(primary_keys) != len(set(primary_keys)):
        raise ValidationError(
            {"accounts": "Solo puede haber un destino personal principal por miembro y moneda."}
        )

    if sum((Decimal(row["amount"]) for row in adjustment_rows), ZERO) != ZERO:
        raise ValidationError({"opening_adjustments": "Los ajustes deben sumar exactamente cero."})
    configured_asset_ids = set(asset_ids)
    normalized_adjustments: list[dict] = []
    for row in adjustment_rows:
        if row["asset_id"] not in configured_asset_ids:
            raise ValidationError(
                {"opening_adjustments": "Cada ajuste debe usar una cuenta participante."}
            )
        normalized_adjustments.append(
            {
                "asset_id": row["asset_id"],
                "member": members[row["member_id"]],
                "amount": row["amount"],
                "kind": row.get("kind", SettlementOpeningAdjustment.Kind.MANUAL),
                "note": row.get("note", ""),
            }
        )
    return normalized_accounts, normalized_adjustments


@transaction.atomic
def replace_settlement_configuration(*, user, payload: dict) -> SettlementProfile:
    profile = get_or_create_settlement_profile(user=user)
    if profile.is_enabled or profile.opening_balances.exists():
        raise ValidationError(
            {
                "detail": (
                    "La configuracion con baseline de activacion es historica y no se puede "
                    "reescribir."
                )
            }
        )
    accounts, adjustments = _validate_configuration_payload(user=user, payload=payload)
    base_currency = str(payload.get("base_currency") or profile.base_currency).strip().upper()
    if len(base_currency) != 3:
        raise ValidationError({"base_currency": "Usa un codigo ISO de tres letras."})

    keep_account_ids: list[int] = []
    account_by_asset: dict[int, SettlementAccount] = {}
    for row in accounts:
        asset = row.pop("asset")
        account, _ = SettlementAccount.objects.update_or_create(
            profile=profile,
            asset=asset,
            defaults=row,
        )
        keep_account_ids.append(account.id)
        account_by_asset[asset.id] = account

    profile.opening_adjustments.all().delete()
    profile.accounts.exclude(id__in=keep_account_ids).delete()
    SettlementOpeningAdjustment.objects.bulk_create(
        [
            SettlementOpeningAdjustment(
                profile=profile,
                account=account_by_asset[row.pop("asset_id")],
                **row,
            )
            for row in adjustments
        ]
    )
    _replace_wallet_normalizations(
        user=user,
        profile=profile,
        transaction_ids=list(payload.get("normalization_transaction_ids", [])),
    )
    profile.base_currency = base_currency
    profile.readiness_status = SettlementProfile.ReadinessStatus.NOT_CHECKED
    profile.readiness_checked_at = None
    profile.save(
        update_fields=["base_currency", "readiness_status", "readiness_checked_at", "updated_at"]
    )
    return profile


def _allocation_vector(
    *, ownership: Ownership, fiscal_year: int, month: int
) -> tuple[dict[int, Decimal] | None, dict[str, object]]:
    result = resolve_ownership_allocation(
        ownership=ownership,
        fiscal_year=fiscal_year,
        month=month,
        persist=False,
    )
    if result["status"] == "blocked":
        return None, result
    return {
        int(share["member_id"]): Decimal(str(share["percent"])) for share in result["shares"]
    }, result


def _check_account_readiness(
    *,
    user,
    profile: SettlementProfile,
    accounts: list[SettlementAccount],
    blockers: list[dict[str, object]],
    wallet_reconciliations: list[dict[str, object]],
    as_of_date: date,
) -> dict[int, Ownership]:
    if not any(account.role == SettlementAccount.Role.OPERATING for account in accounts):
        blockers.append({"code": "missing_operating_account"})

    account_ownerships: dict[int, Ownership] = {}
    has_opening_baseline = profile.opening_balances.exists()
    normalization_deltas = _wallet_normalization_deltas(profile=profile, after_date=as_of_date)
    for account in accounts:
        ownership = _ownership_for_asset(user=user, asset_id=account.asset_id)
        if ownership is None:
            blockers.append(
                {
                    "code": "account_missing_ownership",
                    "account_id": account.id,
                    "asset_id": account.asset_id,
                    "asset_name": account.asset.name,
                }
            )
            continue
        account_ownerships[account.id] = ownership
        if account.role == SettlementAccount.Role.PHYSICAL_CASH:
            modeled_balance = get_effective_asset_amount(asset=account.asset, as_of_date=as_of_date)
            accepted_balance = Decimal(account.accepted_physical_balance or 0)
            has_wallet_adjustment = profile.opening_adjustments.filter(
                account=account,
                kind=SettlementOpeningAdjustment.Kind.WALLET_NORMALIZATION,
            ).exists()
            # The UI and settlement are expressed in currency cents. Do not block
            # activation for an internal precision residue that displays as 0.00.
            modeled_difference = modeled_balance - accepted_balance
            wallet_difference = (
                modeled_difference + normalization_deltas.get(account.id, ZERO)
            ).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)
            wallet_reconciliations.append(
                {
                    "account_id": account.id,
                    "asset_id": account.asset_id,
                    "asset_name": account.asset.name,
                    "currency": account.currency,
                    "balance_date": as_of_date.isoformat(),
                    "modeled_balance": str(modeled_balance),
                    "accepted_physical_balance": str(accepted_balance),
                    "difference": str(wallet_difference),
                    "normalization_recorded": bool(
                        has_wallet_adjustment or normalization_deltas.get(account.id, ZERO)
                    ),
                }
            )
            if wallet_difference != ZERO and not has_wallet_adjustment and not has_opening_baseline:
                blockers.append(
                    {
                        "code": "wallet_adjustment_required",
                        "account_id": account.id,
                        "asset_id": account.asset_id,
                        "asset_name": account.asset.name,
                        "modeled_balance": str(modeled_balance),
                        "accepted_physical_balance": str(accepted_balance),
                        "difference": str(wallet_difference),
                    }
                )

    members = FamilyMember.objects.filter(
        user=user, is_active=True, role=FamilyMember.Role.ADULT
    ).order_by("id")
    for member in members:
        has_destination = any(
            account.role == SettlementAccount.Role.PERSONAL_DESTINATION
            and account.member_id == member.id
            and account.currency == profile.base_currency
            and account.is_primary
            for account in accounts
        )
        if not has_destination:
            blockers.append(
                {
                    "code": "missing_personal_destination",
                    "member_id": member.id,
                    "member_name": member.name,
                    "currency": profile.base_currency,
                }
            )
    return account_ownerships


def _record_allocation_quality(
    *,
    result: dict[str, object],
    blockers: list[dict[str, object]],
    warnings: list[dict[str, object]],
) -> None:
    if result["status"] == "provisional":
        warning = {
            "code": "allocation_provisional",
            "ownership_id": result["ownership_id"],
            "observed_months": result["observed_months"],
        }
        if warning not in warnings:
            warnings.append(warning)
    elif result["status"] == "blocked":
        blocker = {
            "code": "allocation_blocked",
            "ownership_id": result["ownership_id"],
            "quality_reasons": result["quality_reasons"],
        }
        if blocker not in blockers:
            blockers.append(blocker)


def build_settlement_readiness(
    *,
    user,
    fiscal_year: int,
    month: int,
    persist_status: bool = True,
    balance_date: date | None = None,
) -> dict[str, object]:
    profile = get_or_create_settlement_profile(user=user)
    accounts = list(profile.accounts.select_related("asset", "member").order_by("id"))
    blockers: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    wallet_reconciliations: list[dict[str, object]] = []
    allocation_cache: dict[int, tuple[dict[int, Decimal] | None, dict[str, object]]] = {}
    account_ownerships = _check_account_readiness(
        user=user,
        profile=profile,
        accounts=accounts,
        blockers=blockers,
        wallet_reconciliations=wallet_reconciliations,
        as_of_date=balance_date or date(fiscal_year, month, 1),
    )
    for ownership in account_ownerships.values():
        if ownership.id not in allocation_cache:
            allocation_cache[ownership.id] = _allocation_vector(
                ownership=ownership, fiscal_year=fiscal_year, month=month
            )
            _record_allocation_quality(
                result=allocation_cache[ownership.id][1],
                blockers=blockers,
                warnings=warnings,
            )

    income_entries = list(
        effective_annual_income_entries(user=user, fiscal_year=fiscal_year).filter(is_active=True)
    )
    expense_entries = list(
        effective_annual_expense_entries(user=user, fiscal_year=fiscal_year).filter(is_active=True)
    )

    # Income budget rows are forecasts and may aggregate several owners. Realized
    # settlement income is attributed from each posted transaction's ownership.

    for entry in expense_entries:
        if month not in planned_expense_monthly_distribution(entry=entry, fiscal_year=fiscal_year):
            continue
        if entry.time_profile == AnnualExpenseEntry.TimeProfile.ONE_OFF:
            continue
        destination = resolve_expense_settlement_destination(expense=entry, accounts=accounts)
        if destination is None:
            quality_target = (
                warnings
                if expected_expense_settlement_role(expense=entry)
                == SettlementAccount.Role.ALLOCATION_DESTINATION
                else blockers
            )
            quality_target.append(
                {
                    "code": (
                        "allocation_missing_destination"
                        if quality_target is warnings
                        else "expense_missing_settlement_account"
                    ),
                    "entry_id": entry.id,
                    "name": entry.name,
                }
            )
            continue
        if not is_expense_settlement_destination_compatible(expense=entry, destination=destination):
            blockers.append(
                {
                    "code": "expense_invalid_settlement_account",
                    "entry_id": entry.id,
                    "settlement_account_id": destination.id,
                }
            )
            continue
        destination_ownership = account_ownerships.get(destination.id)
        if destination_ownership is None:
            blockers.append(
                {
                    "code": "expense_invalid_settlement_account",
                    "entry_id": entry.id,
                    "settlement_account_id": destination.id,
                }
            )
            continue
        if destination_ownership.id not in allocation_cache:
            allocation_cache[destination_ownership.id] = _allocation_vector(
                ownership=destination_ownership, fiscal_year=fiscal_year, month=month
            )
            _record_allocation_quality(
                result=allocation_cache[destination_ownership.id][1],
                blockers=blockers,
                warnings=warnings,
            )

    adjustment_total = sum(
        (Decimal(value) for value in profile.opening_adjustments.values_list("amount", flat=True)),
        ZERO,
    )
    if adjustment_total != ZERO:
        blockers.append({"code": "opening_adjustments_not_zero", "total": str(adjustment_total)})

    status = (
        SettlementProfile.ReadinessStatus.BLOCKED
        if blockers
        else SettlementProfile.ReadinessStatus.READY
    )
    if persist_status:
        profile.readiness_status = status
        profile.readiness_checked_at = timezone.now()
        profile.save(update_fields=["readiness_status", "readiness_checked_at", "updated_at"])
    return {
        "status": status,
        "is_enabled": profile.is_enabled,
        "activation_date": profile.activation_date.isoformat() if profile.activation_date else None,
        "baseline_date": (balance_date or date(fiscal_year, month, 1)).isoformat(),
        "start_date": (profile.activation_date + timedelta(days=1)).isoformat()
        if profile.activation_date
        else None,
        "base_currency": profile.base_currency,
        "target_period": {"year": fiscal_year, "month": month},
        "blockers": blockers,
        "warnings": warnings,
        "wallet_reconciliations": wallet_reconciliations,
        "wallet_normalization_candidates": _wallet_normalization_candidates(
            user=user,
            profile=profile,
            after_date=balance_date or date(fiscal_year, month, 1),
        ),
        "allocation_coverage": [
            {
                "ownership_id": result["ownership_id"],
                "allocation_basis": result["allocation_basis"],
                "status": result["status"],
                "observed_months": result["observed_months"],
                "eligible_transaction_count": result["eligible_transaction_count"],
                "quality_reasons": result["quality_reasons"],
            }
            for _, (_, result) in sorted(allocation_cache.items())
        ],
        "counts": {
            "accounts": len(accounts),
            "income_entries": len(income_entries),
            "expense_entries": len(expense_entries),
        },
    }


def _capture_opening_baseline(
    *, user, profile: SettlementProfile, baseline_date: date, start_date: date
) -> SettlementProfile:
    if profile.wallet_normalizations.filter(transaction__booking_date__lte=baseline_date).exists():
        raise ValidationError(
            {
                "normalization_transaction_ids": (
                    "Las normalizaciones deben estar registradas despues del baseline."
                )
            }
        )
    readiness = build_settlement_readiness(
        user=user,
        fiscal_year=start_date.year,
        month=start_date.month,
        persist_status=True,
        balance_date=baseline_date,
    )
    if readiness["status"] != SettlementProfile.ReadinessStatus.READY:
        raise ValidationError({"readiness": readiness})

    profile.opening_balances.all().delete()
    for account in profile.accounts.select_related("asset").order_by("id"):
        modeled_balance = get_effective_asset_amount(asset=account.asset, as_of_date=baseline_date)
        account.modeled_balance_at_activation = modeled_balance
        account.save(update_fields=["modeled_balance_at_activation", "updated_at"])
        physical_balance = (
            Decimal(account.accepted_physical_balance)
            if account.role == SettlementAccount.Role.PHYSICAL_CASH
            else Decimal(modeled_balance)
        )
        ownership = _ownership_for_asset(user=user, asset_id=account.asset_id)
        if ownership is None:
            raise ValidationError({"accounts": "Una cuenta participante no tiene ownership."})
        vector, _ = _allocation_vector(
            ownership=ownership,
            fiscal_year=start_date.year,
            month=start_date.month,
        )
        if vector is None:
            raise ValidationError({"accounts": "No se puede resolver el ownership de una cuenta."})
        allocated = ZERO
        vector_rows = sorted(vector.items())
        for index, (member_id, percent) in enumerate(vector_rows):
            amount = (
                physical_balance - allocated
                if index == len(vector_rows) - 1
                else (physical_balance * percent / Decimal("100")).quantize(
                    AMOUNT_STEP, rounding=ROUND_HALF_UP
                )
            )
            allocated += amount
            SettlementOpeningBalance.objects.create(
                profile=profile,
                account=account,
                member_id=member_id,
                amount=amount,
                currency=account.currency,
            )

    profile.is_enabled = True
    profile.activation_date = baseline_date
    profile.readiness_status = SettlementProfile.ReadinessStatus.READY
    profile.save(update_fields=["is_enabled", "activation_date", "readiness_status", "updated_at"])
    return profile


@transaction.atomic
def activate_settlement_profile(*, user, start_date: date) -> SettlementProfile:
    profile = get_or_create_settlement_profile(user=user)
    baseline_date = start_date - timedelta(days=1)
    if profile.activation_date is not None and profile.opening_balances.exists():
        existing_start = profile.activation_date + timedelta(days=1)
        if existing_start != start_date:
            raise ValidationError(
                {
                    "start_date": (
                        f"La liquidacion ya empieza el {existing_start.isoformat()}. "
                        "Usa la recalibracion para cambiar el inicio."
                    )
                }
            )
        if not profile.is_enabled:
            profile.is_enabled = True
            profile.save(update_fields=["is_enabled", "updated_at"])
        return profile
    return _capture_opening_baseline(
        user=user,
        profile=profile,
        baseline_date=baseline_date,
        start_date=start_date,
    )


def can_rebaseline_settlement_profile(*, profile: SettlementProfile) -> bool:
    return not profile.snapshots.filter(status=SettlementSnapshot.Status.READY).exists()


@transaction.atomic
def rebaseline_settlement_profile(*, user, payload: dict) -> SettlementProfile:
    existing_profile = get_or_create_settlement_profile(user=user)
    profile = SettlementProfile.objects.select_for_update().get(pk=existing_profile.pk)
    if not can_rebaseline_settlement_profile(profile=profile):
        raise ValidationError(
            {
                "detail": (
                    "No se puede recalibrar una liquidacion con resultados validos ya finalizados."
                )
            }
        )

    start_date = payload["start_date"]
    baseline_date = start_date - timedelta(days=1)
    wallet_accounts = _physical_wallet_accounts(profile)
    wallet_by_asset = {account.asset_id: account for account in wallet_accounts}
    wallet_rows = payload.get("wallet_balances", [])
    if {row["asset_id"] for row in wallet_rows} != set(wallet_by_asset):
        raise ValidationError(
            {"wallet_balances": "Indica el efectivo inicial de todos los monederos configurados."}
        )
    for row in wallet_rows:
        account = wallet_by_asset[row["asset_id"]]
        account.accepted_physical_balance = row["accepted_physical_balance"]
        account.save(update_fields=["accepted_physical_balance", "updated_at"])

    configuration_rows = [
        {
            "asset_id": account.asset_id,
            "role": account.role,
            "member_id": account.member_id,
            "is_primary": account.is_primary,
            "accepted_physical_balance": account.accepted_physical_balance,
        }
        for account in profile.accounts.select_related("asset", "member").order_by("id")
    ]
    _, adjustment_rows = _validate_configuration_payload(
        user=user,
        payload={
            "accounts": configuration_rows,
            "opening_adjustments": payload.get("opening_adjustments", []),
        },
    )
    account_by_asset = {account.asset_id: account for account in profile.accounts.all()}
    profile.opening_adjustments.all().delete()
    SettlementOpeningAdjustment.objects.bulk_create(
        [
            SettlementOpeningAdjustment(
                profile=profile,
                account=account_by_asset[row.pop("asset_id")],
                **row,
            )
            for row in adjustment_rows
        ]
    )
    transaction_ids = list(payload.get("normalization_transaction_ids", []))
    _replace_wallet_normalizations(
        user=user,
        profile=profile,
        transaction_ids=transaction_ids,
    )
    profile.opening_balances.all().delete()
    profile.accounts.update(modeled_balance_at_activation=None)
    profile.is_enabled = False
    profile.activation_date = None
    profile.readiness_status = SettlementProfile.ReadinessStatus.NOT_CHECKED
    profile.readiness_checked_at = None
    profile.save(
        update_fields=[
            "is_enabled",
            "activation_date",
            "readiness_status",
            "readiness_checked_at",
            "updated_at",
        ]
    )
    return _capture_opening_baseline(
        user=user,
        profile=profile,
        baseline_date=baseline_date,
        start_date=start_date,
    )


@transaction.atomic
def disable_settlement_profile(*, user) -> SettlementProfile:
    profile = get_or_create_settlement_profile(user=user)
    profile.is_enabled = False
    profile.save(update_fields=["is_enabled", "updated_at"])
    return profile
