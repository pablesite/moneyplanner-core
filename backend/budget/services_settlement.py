from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import cast

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.services import get_base_currency_for_user
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
        if account.role == SettlementAccount.Role.PHYSICAL_CASH and not has_opening_baseline:
            modeled_balance = get_effective_asset_amount(asset=account.asset, as_of_date=as_of_date)
            accepted_balance = Decimal(account.accepted_physical_balance or 0)
            has_wallet_adjustment = profile.opening_adjustments.filter(
                account=account,
                kind=SettlementOpeningAdjustment.Kind.WALLET_NORMALIZATION,
            ).exists()
            # The UI and settlement are expressed in currency cents. Do not block
            # activation for an internal precision residue that displays as 0.00.
            wallet_difference = (modeled_balance - accepted_balance).quantize(
                MONEY_STEP, rounding=ROUND_HALF_UP
            )
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
                    "normalization_recorded": has_wallet_adjustment,
                }
            )
            if wallet_difference != ZERO and not has_wallet_adjustment:
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
        expected_role = expected_expense_settlement_role(expense=entry)
        if destination.role != expected_role:
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
        "base_currency": profile.base_currency,
        "target_period": {"year": fiscal_year, "month": month},
        "blockers": blockers,
        "warnings": warnings,
        "wallet_reconciliations": wallet_reconciliations,
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


@transaction.atomic
def activate_settlement_profile(*, user, activation_date: date) -> SettlementProfile:
    profile = get_or_create_settlement_profile(user=user)
    if profile.is_enabled:
        return profile
    if profile.activation_date is not None and profile.opening_balances.exists():
        profile.is_enabled = True
        profile.save(update_fields=["is_enabled", "updated_at"])
        return profile
    readiness = build_settlement_readiness(
        user=user,
        fiscal_year=activation_date.year,
        month=activation_date.month,
        persist_status=True,
        balance_date=activation_date,
    )
    if readiness["status"] != SettlementProfile.ReadinessStatus.READY:
        raise ValidationError({"readiness": readiness})

    profile.opening_balances.all().delete()
    for account in profile.accounts.select_related("asset").order_by("id"):
        modeled_balance = get_effective_asset_amount(
            asset=account.asset, as_of_date=activation_date
        )
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
            fiscal_year=activation_date.year,
            month=activation_date.month,
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
    profile.activation_date = activation_date
    profile.readiness_status = SettlementProfile.ReadinessStatus.READY
    profile.save(update_fields=["is_enabled", "activation_date", "readiness_status", "updated_at"])
    return profile


@transaction.atomic
def disable_settlement_profile(*, user) -> SettlementProfile:
    profile = get_or_create_settlement_profile(user=user)
    profile.is_enabled = False
    profile.save(update_fields=["is_enabled", "updated_at"])
    return profile
