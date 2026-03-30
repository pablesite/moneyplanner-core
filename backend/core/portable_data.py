from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from django.conf import settings
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError

from accounts.services import get_or_create_user_settings, update_user_settings
from accounting.models import LedgerAccount, LedgerTransaction
from accounting.serializers import LedgerAccountSerializer, LedgerTransactionSerializer
from accounting.services_ledger import get_or_create_system_account
from budget.models import AnnualExpenseEntry, AnnualIncomeEntry
from budget.serializers import AnnualExpenseEntrySerializer, AnnualIncomeEntrySerializer
from memberships.models import FamilyMember, Ownership, OwnershipLink
from memberships.serializers import FamilyMemberSerializer, OwnershipWriteSerializer
from memberships.services import sync_ownership_link
from net_worth.models import Asset, Liability
from net_worth.serializers import (
    AssetSerializer,
    AssetValuationSerializer,
    InvestmentAssetEventSerializer,
    LiabilityEventSerializer,
    LiabilitySerializer,
    LiabilityValuationSerializer,
    LiquidityAssetEventSerializer,
)
from net_worth.services import get_base_currency_for_user, get_financed_asset_queryset_for_user


def get_current_portable_app_version() -> str:
    return str(settings.SPECTACULAR_SETTINGS.get("VERSION", "0.0.0"))


def _parse_version(version: str) -> tuple[int, ...]:
    parts = [segment.strip() for segment in str(version).split(".")]
    parsed: list[int] = []
    for segment in parts:
        if not segment:
            parsed.append(0)
            continue
        if not segment.isdigit():
            raise DRFValidationError({"detail": f"Version portable invalida: {version}."})
        parsed.append(int(segment))
    return tuple(parsed)


def compare_portable_versions(left: str, right: str) -> int:
    left_parts = _parse_version(left)
    right_parts = _parse_version(right)
    max_len = max(len(left_parts), len(right_parts))
    left_padded = left_parts + (0,) * (max_len - len(left_parts))
    right_padded = right_parts + (0,) * (max_len - len(right_parts))
    if left_padded < right_padded:
        return -1
    if left_padded > right_padded:
        return 1
    return 0


def normalize_optional_text(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def normalize_imported_asset_tae(asset: dict[str, Any]) -> str | None:
    normalized = normalize_optional_text(asset.get("annual_interest_tae"))
    if normalized is not None:
        return normalized

    category = str(asset.get("category", "")).strip()
    subcategory = str(asset.get("subcategory", "")).strip()
    requires_tae = category == "cash" and subcategory in {
        "bank_account",
        "short_term_deposit",
        "crypto_spot_earn",
        "other",
    }
    return "0" if requires_tae else None


def normalize_imported_liability_tae(liability: dict[str, Any]) -> str | None:
    normalized = normalize_optional_text(liability.get("annual_interest_tae"))
    if normalized is not None:
        return normalized

    category = str(liability.get("category", "")).strip()
    requires_tae = category in {"mortgage", "personal_loan", "credit_card"}
    return "0" if requires_tae else None


class PortableImportRequestSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=("append", "replace"))
    bundle = serializers.DictField()

    def validate_bundle(self, value: dict[str, Any]) -> dict[str, Any]:
        if value.get("schema_version") != 1:
            raise serializers.ValidationError("Formato de archivo no compatible.")

        data = value.get("data")
        if not isinstance(data, dict):
            raise serializers.ValidationError("El archivo no contiene bloque `data` valido.")

        required_collections = ("annual_income", "annual_expense", "assets", "liabilities")
        for key in required_collections:
            if not isinstance(data.get(key), list):
                raise serializers.ValidationError(
                    f"El archivo no contiene la coleccion esperada: {key}."
                )

        optional_collections = (
            "asset_valuations",
            "investment_events",
            "liquidity_events",
            "liability_events",
            "liability_valuations",
        )
        for key in optional_collections:
            if key in data and not isinstance(data.get(key), list):
                raise serializers.ValidationError(
                    f"El archivo no contiene la coleccion esperada: {key}."
                )

        accounting = data.get("accounting")
        if accounting is not None:
            if not isinstance(accounting, dict):
                raise serializers.ValidationError("El bloque accounting del archivo no es valido.")
            if not isinstance(accounting.get("accounts"), list):
                raise serializers.ValidationError(
                    "El bloque accounting no contiene la coleccion esperada: accounts."
                )
            if not isinstance(accounting.get("transactions"), list):
                raise serializers.ValidationError(
                    "El bloque accounting no contiene la coleccion esperada: transactions."
                )

        premium = value.get("premium")
        if premium is not None:
            if not isinstance(premium, dict):
                raise serializers.ValidationError("El bloque premium del archivo no es valido.")
            for key in ("family_members", "ownerships", "ownership_links"):
                if not isinstance(premium.get(key), list):
                    raise serializers.ValidationError(
                        f"El bloque premium no contiene la coleccion esperada: {key}."
                    )

        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        bundle = attrs["bundle"]
        exported_version = normalize_optional_text(bundle.get("exported_app_version"))
        current_version = get_current_portable_app_version()

        if attrs["mode"] == "replace":
            if exported_version is None:
                raise serializers.ValidationError(
                    {
                        "bundle": {
                            "exported_app_version": (
                                "El archivo no incluye version exportada. "
                                "Por seguridad, `replace` solo admite bundles con version."
                            )
                        }
                    }
                )
            if compare_portable_versions(exported_version, current_version) > 0:
                raise serializers.ValidationError(
                    {
                        "bundle": {
                            "exported_app_version": (
                                "El archivo fue exportado desde una version mas nueva "
                                f"({exported_version}) que este Core ({current_version})."
                            )
                        }
                    }
                )

        attrs["bundle"]["exported_app_version"] = exported_version
        return attrs


@dataclass
class PortableImportContext:
    user: Any
    request: Any


def _build_asset_payload(asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(asset.get("name", "")),
        "category": str(asset.get("category", "")),
        "subcategory": str(asset.get("subcategory", "other")),
        # Import assets first without accounting linkage; it is remapped after
        # ledger accounts are created in destination.
        "tracking_mode": "manual",
        "accounting_account_id": None,
        "currency": str(asset.get("currency", "EUR")).upper(),
        "start_date": asset.get("start_date"),
        "expected_end_date": normalize_optional_text(asset.get("expected_end_date")),
        "investment_contribution_mode": normalize_optional_text(
            asset.get("investment_contribution_mode")
        )
        or "one_time",
        "investment_contribution_frequency": normalize_optional_text(
            asset.get("investment_contribution_frequency")
        )
        or "monthly",
        "investment_contribution_currency": normalize_optional_text(
            asset.get("investment_contribution_currency")
        ),
        "monthly_contribution_amount": normalize_optional_text(
            asset.get("monthly_contribution_amount")
        ),
        "contribution_intervals": list(asset.get("contribution_intervals", [])),
        "market_value_override": normalize_optional_text(asset.get("market_value_override")),
        "market_value_override_date": normalize_optional_text(
            asset.get("market_value_override_date")
        ),
        "initial_purchase_value": normalize_optional_text(asset.get("initial_purchase_value")),
        "amortization_method": normalize_optional_text(asset.get("amortization_method")) or "none",
        "amortization_term_years": asset.get("amortization_term_years"),
        "valuation_model": normalize_optional_text(asset.get("valuation_model")) or "manual",
        "land_value_share_percent": normalize_optional_text(asset.get("land_value_share_percent")),
        "land_annual_appreciation_percent": normalize_optional_text(
            asset.get("land_annual_appreciation_percent")
        ),
        "building_annual_depreciation_percent": normalize_optional_text(
            asset.get("building_annual_depreciation_percent")
        ),
        "improvements": list(asset.get("improvements", [])),
        "annual_interest_tae": normalize_imported_asset_tae(asset),
        "estimated_average_balance_for_interest": normalize_optional_text(
            asset.get("estimated_average_balance_for_interest")
        ),
        "deposit_term_months": asset.get("deposit_term_months"),
        "amount": str(asset.get("amount", "0")),
        "is_active": asset.get("is_active", True),
        "notes": asset.get("notes", "") or "",
    }


def _build_liability_payload(
    liability: dict[str, Any], asset_id_map: dict[int, int]
) -> dict[str, Any]:
    financed_asset_ref = liability.get("financed_asset_ref")
    financed_asset_id = asset_id_map.get(int(financed_asset_ref)) if financed_asset_ref else None
    return {
        "name": str(liability.get("name", "")),
        "category": str(liability.get("category", "")),
        # Import liabilities first without accounting linkage; it is remapped after
        # ledger accounts are created in destination.
        "tracking_mode": "manual",
        "accounting_account_id": None,
        "currency": str(liability.get("currency", "EUR")).upper(),
        "start_date": liability.get("start_date"),
        "payment_start_date": normalize_optional_text(liability.get("payment_start_date")),
        "expected_end_date": normalize_optional_text(liability.get("expected_end_date")),
        "term_months": liability.get("term_months"),
        "rate_type": normalize_optional_text(liability.get("rate_type")) or "fixed",
        "payment_frequency": normalize_optional_text(liability.get("payment_frequency"))
        or "monthly",
        "expense_subcategory_override": normalize_optional_text(
            liability.get("expense_subcategory_override")
        ),
        "amortization_system": normalize_optional_text(liability.get("amortization_system")),
        "annual_interest_tae": normalize_imported_liability_tae(liability),
        "principal_amount": normalize_optional_text(liability.get("principal_amount")),
        "opening_fees_amount": normalize_optional_text(liability.get("opening_fees_amount")),
        "early_repayment_fee_percent": normalize_optional_text(
            liability.get("early_repayment_fee_percent")
        ),
        "novation_subrogation_fee_amount": normalize_optional_text(
            liability.get("novation_subrogation_fee_amount")
        ),
        "linked_products_monthly_cost": normalize_optional_text(
            liability.get("linked_products_monthly_cost")
        ),
        "cancellation_forecast_enabled": liability.get("cancellation_forecast_enabled", False),
        "cancellation_date": normalize_optional_text(liability.get("cancellation_date")),
        "cancellation_fee_amount": normalize_optional_text(liability.get("cancellation_fee_amount")),
        "amount": str(liability.get("amount", "0")),
        "is_active": liability.get("is_active", True),
        "notes": liability.get("notes", "") or "",
        "financed_asset_id": financed_asset_id,
    }


def _prepare_income_payload(entry: dict[str, Any]) -> dict[str, Any]:
    inferred_time_profile = entry.get("time_profile") or (
        AnnualIncomeEntry.TimeProfile.ONE_OFF
        if entry.get("income_type") == AnnualIncomeEntry.IncomeType.ONE_OFF
        else AnnualIncomeEntry.TimeProfile.STRUCTURAL_RECURRENT
    )
    target_month = entry.get("target_month")
    if inferred_time_profile == AnnualIncomeEntry.TimeProfile.ONE_OFF and target_month in (
        None,
        "",
    ):
        target_month = 12
    return {
        "name": str(entry.get("name", "")),
        "category": str(entry.get("category", "")),
        "subcategory": str(entry.get("subcategory", "")),
        "owner_name": str(entry.get("owner_name", "")).strip(),
        "income_type": entry.get("income_type", "recurrent"),
        "time_profile": inferred_time_profile,
        "cashflow_role": entry.get("cashflow_role"),
        "event_group": str(entry.get("event_group", "")),
        "target_month": target_month,
        "term_end_month": entry.get("term_end_month"),
        "term_end_year": entry.get("term_end_year"),
        "amount_input_period": (
            "monthly" if entry.get("amount_input_period") == "monthly" else "annual"
        ),
        "amount_annual": str(entry.get("amount_annual", "0")),
        "fiscal_year": int(entry.get("fiscal_year", 0)),
        "currency": str(entry.get("currency", "EUR")).upper(),
        "notes": entry.get("notes", "") or "",
        "is_active": entry.get("is_active", True),
    }


def _prepare_expense_payload(entry: dict[str, Any]) -> dict[str, Any]:
    inferred_time_profile = entry.get("time_profile") or (
        AnnualExpenseEntry.TimeProfile.ONE_OFF
        if entry.get("expense_type") == AnnualExpenseEntry.ExpenseType.ONE_OFF
        else AnnualExpenseEntry.TimeProfile.STRUCTURAL_RECURRENT
    )
    target_month = entry.get("target_month")
    if inferred_time_profile == AnnualExpenseEntry.TimeProfile.ONE_OFF and target_month in (
        None,
        "",
    ):
        target_month = 12
    return {
        "name": str(entry.get("name", "")),
        "category": str(entry.get("category", "")),
        "subcategory": str(entry.get("subcategory", "")),
        "owner_name": str(entry.get("owner_name", "")).strip(),
        "expense_type": entry.get("expense_type", "recurrent"),
        "time_profile": inferred_time_profile,
        "cashflow_role": entry.get("cashflow_role"),
        "event_group": str(entry.get("event_group", "")),
        "target_month": target_month,
        "term_end_month": entry.get("term_end_month"),
        "term_end_year": entry.get("term_end_year"),
        "amount_input_period": (
            "monthly" if entry.get("amount_input_period") == "monthly" else "annual"
        ),
        "amount_annual": str(entry.get("amount_annual", "0")),
        "fiscal_year": int(entry.get("fiscal_year", 0)),
        "currency": str(entry.get("currency", "EUR")).upper(),
        "notes": entry.get("notes", "") or "",
        "is_active": entry.get("is_active", True),
    }


def _clear_existing_portable_core_data(*, user) -> None:
    LedgerTransaction.objects.filter(user=user).delete()
    LedgerAccount.objects.filter(user=user).delete()
    OwnershipLink.objects.filter(
        user=user,
        target_type__in=[OwnershipLink.TargetType.ASSET, OwnershipLink.TargetType.LIABILITY],
    ).delete()
    AnnualIncomeEntry.objects.filter(user=user).delete()
    AnnualExpenseEntry.objects.filter(user=user).delete()
    Liability.objects.filter(user=user).delete()
    Asset.objects.filter(user=user).delete()


def _clear_existing_portable_premium_data(*, user) -> None:
    OwnershipLink.objects.filter(user=user).delete()
    Ownership.objects.filter(user=user).delete()
    FamilyMember.objects.filter(user=user).delete()


def _import_family_and_ownerships(
    *, context: PortableImportContext, premium: dict[str, Any] | None
) -> dict[int, int]:
    ownership_id_map: dict[int, int] = {}
    if premium is None:
        return ownership_id_map

    member_id_map: dict[int, int] = {}

    for member in sorted(premium["family_members"], key=lambda row: int(row.get("id", 0))):
        serializer = FamilyMemberSerializer(
            data={
                "name": str(member.get("name", "")),
                "role": member.get("role", "adult"),
                "is_active": member.get("is_active", True),
            },
            context={"request": context.request},
        )
        serializer.is_valid(raise_exception=True)
        created_member = serializer.save()
        member_id_map[int(member.get("id", 0))] = created_member.id

    current_ownerships = list(
        Ownership.objects.filter(user=context.user)
        .select_related("member")
        .prefetch_related("splits", "splits__member")
    )
    for ownership in premium["ownerships"]:
        if ownership.get("kind") != "individual":
            continue
        member = ownership.get("member") or {}
        old_member_id = member.get("id")
        if old_member_id is None:
            continue
        new_member_id = member_id_map.get(int(old_member_id))
        if new_member_id is None:
            continue
        mapped = next(
            (
                candidate
                for candidate in current_ownerships
                if candidate.kind == Ownership.Kind.INDIVIDUAL
                and candidate.member_id == new_member_id
            ),
            None,
        )
        if mapped is not None:
            ownership_id_map[int(ownership.get("id", 0))] = mapped.id

    for ownership in sorted(
        [row for row in premium["ownerships"] if row.get("kind") == "shared"],
        key=lambda row: int(row.get("id", 0)),
    ):
        splits: list[dict[str, Any]] = []
        for split in ownership.get("splits", []):
            member = split.get("member") or {}
            member_id = member_id_map.get(int(member.get("id", 0)))
            if member_id is None:
                continue
            splits.append({"member_id": member_id, "percent": str(split.get("percent", "0"))})
        if not splits:
            continue
        serializer = OwnershipWriteSerializer(
            data={"kind": "shared", "member": None, "splits": splits},
            context={"request": context.request},
        )
        serializer.is_valid(raise_exception=True)
        created = serializer.save()
        ownership_id_map[int(ownership.get("id", 0))] = created.id

    return ownership_id_map


def _import_assets(
    *, context: PortableImportContext, assets: list[dict[str, Any]]
) -> dict[int, int]:
    asset_id_map: dict[int, int] = {}
    for asset in sorted(assets, key=lambda row: int(row.get("id", 0))):
        serializer = AssetSerializer(
            data=_build_asset_payload(asset),
            context={
                "request": context.request,
                "base_currency": get_base_currency_for_user(user=context.user),
            },
        )
        serializer.is_valid(raise_exception=True)
        created = serializer.save()
        asset_id_map[int(asset.get("id", 0))] = created.id
    return asset_id_map


def _import_liabilities(
    *,
    context: PortableImportContext,
    liabilities: list[dict[str, Any]],
    asset_id_map: dict[int, int],
) -> dict[int, int]:
    liability_id_map: dict[int, int] = {}
    for liability in sorted(liabilities, key=lambda row: int(row.get("id", 0))):
        serializer = LiabilitySerializer(
            data=_build_liability_payload(liability, asset_id_map),
            context={
                "request": context.request,
                "base_currency": get_base_currency_for_user(user=context.user),
                "financed_asset_queryset": get_financed_asset_queryset_for_user(user=context.user),
            },
        )
        serializer.is_valid(raise_exception=True)
        created = serializer.save()
        liability_id_map[int(liability.get("id", 0))] = created.id
    return liability_id_map


def _import_asset_valuations(
    *,
    context: PortableImportContext,
    valuations: list[dict[str, Any]],
    asset_id_map: dict[int, int],
) -> int:
    if not valuations:
        return 0

    asset_queryset = Asset.objects.filter(user=context.user)
    imported = 0
    for row in sorted(valuations, key=lambda entry: int(entry.get("id", 0))):
        old_asset_id = row.get("asset_ref")
        if old_asset_id in (None, ""):
            continue
        new_asset_id = asset_id_map.get(int(old_asset_id))
        if new_asset_id is None:
            continue
        serializer = AssetValuationSerializer(
            data={
                "asset_id": new_asset_id,
                "valuation_date": row.get("valuation_date"),
                "value": str(row.get("value", "0")),
                "source": str(row.get("source", "manual_checkpoint")),
                "note": row.get("note", "") or "",
            },
            context={"request": context.request, "asset_queryset": asset_queryset},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        imported += 1
    return imported


def _import_investment_events(
    *,
    context: PortableImportContext,
    events: list[dict[str, Any]],
    asset_id_map: dict[int, int],
) -> int:
    if not events:
        return 0

    investment_queryset = Asset.objects.filter(user=context.user, category=Asset.Category.INVESTMENTS)
    imported = 0
    for row in sorted(events, key=lambda entry: int(entry.get("id", 0))):
        old_asset_id = row.get("asset_ref")
        if old_asset_id in (None, ""):
            continue
        new_asset_id = asset_id_map.get(int(old_asset_id))
        if new_asset_id is None:
            continue
        serializer = InvestmentAssetEventSerializer(
            data={
                "asset_id": new_asset_id,
                "event_date": row.get("event_date"),
                "event_type": str(row.get("event_type", "")),
                "amount": str(row.get("amount", "0")),
                "is_reinvested": row.get("is_reinvested", True),
                "note": row.get("note", "") or "",
            },
            context={"request": context.request, "investment_asset_queryset": investment_queryset},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        imported += 1
    return imported


def _import_liquidity_events(
    *,
    context: PortableImportContext,
    events: list[dict[str, Any]],
    asset_id_map: dict[int, int],
) -> int:
    if not events:
        return 0

    liquidity_queryset = Asset.objects.filter(user=context.user, category=Asset.Category.CASH)
    imported = 0
    for row in sorted(events, key=lambda entry: int(entry.get("id", 0))):
        old_asset_id = row.get("asset_ref")
        if old_asset_id in (None, ""):
            continue
        new_asset_id = asset_id_map.get(int(old_asset_id))
        if new_asset_id is None:
            continue
        serializer = LiquidityAssetEventSerializer(
            data={
                "asset_id": new_asset_id,
                "event_date": row.get("event_date"),
                "event_type": str(row.get("event_type", "")),
                "amount": str(row.get("amount", "0")),
                "note": row.get("note", "") or "",
            },
            context={"request": context.request, "liquidity_event_asset_queryset": liquidity_queryset},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        imported += 1
    return imported


def _import_liability_events(
    *,
    context: PortableImportContext,
    events: list[dict[str, Any]],
    liability_id_map: dict[int, int],
) -> int:
    if not events:
        return 0

    liability_queryset = Liability.objects.filter(user=context.user)
    imported = 0
    for row in sorted(events, key=lambda entry: int(entry.get("id", 0))):
        old_liability_id = row.get("liability_ref")
        if old_liability_id in (None, ""):
            continue
        new_liability_id = liability_id_map.get(int(old_liability_id))
        if new_liability_id is None:
            continue
        serializer = LiabilityEventSerializer(
            data={
                "liability_id": new_liability_id,
                "event_date": row.get("event_date"),
                "event_type": str(row.get("event_type", "")),
                "amount": str(row.get("amount", "0")),
                "note": row.get("note", "") or "",
            },
            context={"request": context.request, "liability_event_queryset": liability_queryset},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        imported += 1
    return imported


def _import_liability_valuations(
    *,
    context: PortableImportContext,
    valuations: list[dict[str, Any]],
    liability_id_map: dict[int, int],
) -> int:
    if not valuations:
        return 0

    liability_queryset = Liability.objects.filter(user=context.user)
    imported = 0
    for row in sorted(valuations, key=lambda entry: int(entry.get("id", 0))):
        old_liability_id = row.get("liability_ref")
        if old_liability_id in (None, ""):
            continue
        new_liability_id = liability_id_map.get(int(old_liability_id))
        if new_liability_id is None:
            continue
        serializer = LiabilityValuationSerializer(
            data={
                "liability_id": new_liability_id,
                "valuation_date": row.get("valuation_date"),
                "value": str(row.get("value", "0")),
                "source": str(row.get("source", "manual_checkpoint")),
                "note": row.get("note", "") or "",
            },
            context={"request": context.request, "liability_queryset": liability_queryset},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        imported += 1
    return imported


def _import_annual_income(
    *, context: PortableImportContext, annual_income: list[dict[str, Any]]
) -> tuple[int, dict[int, int]]:
    income_id_map: dict[int, int] = {}
    for entry in sorted(annual_income, key=lambda row: int(row.get("id", 0))):
        serializer = AnnualIncomeEntrySerializer(
            data=_prepare_income_payload(entry),
            context={"request": context.request},
        )
        serializer.is_valid(raise_exception=True)
        created = serializer.save(user=context.user)
        income_id_map[int(entry.get("id", 0))] = created.id
    return len(annual_income), income_id_map


def _import_annual_expense(
    *, context: PortableImportContext, annual_expense: list[dict[str, Any]]
) -> tuple[int, dict[int, int]]:
    expense_id_map: dict[int, int] = {}
    for entry in sorted(annual_expense, key=lambda row: int(row.get("id", 0))):
        serializer = AnnualExpenseEntrySerializer(
            data=_prepare_expense_payload(entry),
            context={"request": context.request},
        )
        serializer.is_valid(raise_exception=True)
        created = serializer.save(user=context.user)
        expense_id_map[int(entry.get("id", 0))] = created.id
    return len(annual_expense), expense_id_map


def _import_settings(
    *, context: PortableImportContext, bundle: dict[str, Any]
) -> None:
    settings_payload = bundle.get("settings")
    if isinstance(settings_payload, dict) and normalize_optional_text(
        settings_payload.get("base_currency")
    ):
        update_user_settings(
            user=context.user,
            validated_data={"base_currency": str(settings_payload["base_currency"]).upper()},
        )
    else:
        get_or_create_user_settings(user=context.user)


def _import_ownership_links(
    *,
    context: PortableImportContext,
    premium: dict[str, Any] | None,
    ownership_id_map: dict[int, int],
    asset_id_map: dict[int, int],
    liability_id_map: dict[int, int],
) -> int:
    if premium is None:
        return 0

    imported = 0
    for link in premium["ownership_links"]:
        target_type = "liability" if link.get("target_type") == "liability" else "asset"
        old_target_id = int(link.get("target_id", 0))
        new_target_id = (
            liability_id_map.get(old_target_id)
            if target_type == "liability"
            else asset_id_map.get(old_target_id)
        )
        new_ownership_id = ownership_id_map.get(int(link.get("ownership_id", 0)))
        if new_target_id is None or new_ownership_id is None:
            continue
        ownership = Ownership.objects.get(user=context.user, id=new_ownership_id)
        sync_ownership_link(
            user=context.user,
            target_type=target_type,
            target_id=new_target_id,
            ownership=ownership,
        )
        imported += 1
    return imported


def _build_account_payload(
    *,
    account: dict[str, Any],
    asset_id_map: dict[int, int],
    liability_id_map: dict[int, int],
) -> dict[str, Any]:
    old_asset_id = account.get("asset_id")
    old_liability_id = account.get("liability_id")
    mapped_asset_id = asset_id_map.get(int(old_asset_id)) if old_asset_id not in (None, "") else None
    mapped_liability_id = (
        liability_id_map.get(int(old_liability_id)) if old_liability_id not in (None, "") else None
    )
    return {
        "name": str(account.get("name", "")),
        "account_type": str(account.get("account_type", "")),
        "currency": str(account.get("currency", "EUR")).upper(),
        "origin": str(account.get("origin", LedgerAccount.Origin.USER)),
        "asset_id": mapped_asset_id,
        "liability_id": mapped_liability_id,
        "is_active": account.get("is_active", True),
        "notes": account.get("notes", "") or "",
    }


def _import_ledger_accounts(
    *,
    context: PortableImportContext,
    accounts: list[dict[str, Any]],
    asset_id_map: dict[int, int],
    liability_id_map: dict[int, int],
) -> dict[int, int]:
    account_id_map: dict[int, int] = {}
    for account in sorted(accounts, key=lambda row: int(row.get("id", 0))):
        serializer = LedgerAccountSerializer(
            data=_build_account_payload(
                account=account,
                asset_id_map=asset_id_map,
                liability_id_map=liability_id_map,
            ),
            context={"request": context.request},
        )
        serializer.is_valid(raise_exception=True)
        created = serializer.save()
        account_id_map[int(account.get("id", 0))] = created.id
    return account_id_map


def _sync_imported_tracking_account_links(
    *,
    context: PortableImportContext,
    assets: list[dict[str, Any]],
    liabilities: list[dict[str, Any]],
    asset_id_map: dict[int, int],
    liability_id_map: dict[int, int],
    account_id_map: dict[int, int],
) -> None:
    for raw_asset in assets:
        old_asset_id = raw_asset.get("id")
        old_account_id = raw_asset.get("accounting_account_id")
        if old_asset_id in (None, "") or old_account_id in (None, ""):
            continue
        new_asset_id = asset_id_map.get(int(old_asset_id))
        new_account_id = account_id_map.get(int(old_account_id))
        if new_asset_id is None or new_account_id is None:
            continue
        Asset.objects.filter(user=context.user, id=new_asset_id).update(
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            accounting_account_id=new_account_id,
        )

    for raw_liability in liabilities:
        old_liability_id = raw_liability.get("id")
        old_account_id = raw_liability.get("accounting_account_id")
        if old_liability_id in (None, "") or old_account_id in (None, ""):
            continue
        new_liability_id = liability_id_map.get(int(old_liability_id))
        new_account_id = account_id_map.get(int(old_account_id))
        if new_liability_id is None or new_account_id is None:
            continue
        Liability.objects.filter(user=context.user, id=new_liability_id).update(
            tracking_mode=Liability.TrackingMode.ACCOUNTING,
            accounting_account_id=new_account_id
        )


def _build_transaction_payload(
    *,
    transaction_row: dict[str, Any],
    account_id_map: dict[int, int],
    ownership_id_map: dict[int, int],
    annual_income_id_map: dict[int, int],
    annual_expense_id_map: dict[int, int],
    asset_id_map: dict[int, int],
    liability_id_map: dict[int, int],
) -> dict[str, Any]:
    ownership_id: int | None = None
    old_ownership_id = transaction_row.get("ownership_id")
    if old_ownership_id not in (None, ""):
        ownership_id = ownership_id_map.get(int(old_ownership_id))

    entries_payload: list[dict[str, Any]] = []
    for entry in transaction_row.get("entries", []):
        old_account_id = entry.get("account_id")
        new_account_id = account_id_map.get(int(old_account_id)) if old_account_id not in (None, "") else None
        if new_account_id is None:
            raise serializers.ValidationError(
                {
                    "bundle": {
                        "data": {
                            "accounting": {
                                "transactions": "No se pudo mapear account_id en una entrada contable."
                            }
                        }
                    }
                }
            )

        old_income_id = entry.get("annual_income_entry_id")
        old_expense_id = entry.get("annual_expense_entry_id")
        old_asset_id = entry.get("asset_id")
        old_liability_id = entry.get("liability_id")
        flow_family = str(entry.get("flow_family", "")).strip()
        category_key = str(entry.get("category_key", "")).strip()
        subcategory_key = str(entry.get("subcategory_key", "")).strip()

        # Legacy bundles can contain only one/two classification fields.
        # Ledger serializers require the three values together, so normalize
        # partial classifications to unclassified entries during import.
        has_any_classification = bool(flow_family or category_key or subcategory_key)
        has_complete_classification = bool(flow_family and category_key and subcategory_key)
        if has_any_classification and not has_complete_classification:
            flow_family = ""
            category_key = ""
            subcategory_key = ""

        entries_payload.append(
            {
                "account_id": new_account_id,
                "side": str(entry.get("side", "")),
                "amount": str(entry.get("amount", "0")),
                "currency": str(entry.get("currency", "EUR")).upper(),
                "flow_family": flow_family,
                "category_key": category_key,
                "subcategory_key": subcategory_key,
                "annual_income_entry_id": (
                    annual_income_id_map.get(int(old_income_id)) if old_income_id not in (None, "") else None
                ),
                "annual_expense_entry_id": (
                    annual_expense_id_map.get(int(old_expense_id))
                    if old_expense_id not in (None, "")
                    else None
                ),
                "asset_id": asset_id_map.get(int(old_asset_id)) if old_asset_id not in (None, "") else None,
                "liability_id": (
                    liability_id_map.get(int(old_liability_id))
                    if old_liability_id not in (None, "")
                    else None
                ),
                "notes": entry.get("notes", "") or "",
            }
        )

    return {
        "booking_date": transaction_row.get("booking_date"),
        "value_date": transaction_row.get("value_date"),
        "description": str(transaction_row.get("description", "")),
        "status": str(transaction_row.get("status", LedgerTransaction.Status.POSTED)),
        "origin": str(transaction_row.get("origin", LedgerTransaction.Origin.MANUAL)),
        "notes": transaction_row.get("notes", "") or "",
        "ownership_id": ownership_id,
        "quick_entry_kind": str(transaction_row.get("quick_entry_kind", "")),
        "investment_direction": str(transaction_row.get("investment_direction", "")),
        "entries": entries_payload,
    }


def _import_ledger_transactions(
    *,
    context: PortableImportContext,
    transactions: list[dict[str, Any]],
    account_id_map: dict[int, int],
    ownership_id_map: dict[int, int],
    annual_income_id_map: dict[int, int],
    annual_expense_id_map: dict[int, int],
    asset_id_map: dict[int, int],
    liability_id_map: dict[int, int],
) -> int:
    for transaction_row in sorted(transactions, key=lambda row: int(row.get("id", 0))):
        payload = _build_transaction_payload(
            transaction_row=transaction_row,
            account_id_map=account_id_map,
            ownership_id_map=ownership_id_map,
            annual_income_id_map=annual_income_id_map,
            annual_expense_id_map=annual_expense_id_map,
            asset_id_map=asset_id_map,
            liability_id_map=liability_id_map,
        )
        _ensure_minimum_transaction_entries(payload=payload, user=context.user)
        _ensure_balanced_entries_by_currency(payload=payload, user=context.user)
        serializer = LedgerTransactionSerializer(data=payload, context={"request": context.request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
    return len(transactions)


def _ensure_minimum_transaction_entries(*, payload: dict[str, Any], user: Any) -> None:
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return
    if len(entries) == 0:
        raise serializers.ValidationError(
            {"entries": "La transaccion no contiene apuntes importables."}
        )
    if len(entries) >= 2:
        return

    entry = entries[0]
    side = str(entry.get("side", "debit")).strip().lower()
    amount = str(entry.get("amount", "0"))
    currency = str(entry.get("currency", "EUR")).strip().upper()
    counter_side = "credit" if side == "debit" else "debit"
    contra_account = get_or_create_system_account(
        user_id=user.id,
        account_type=LedgerAccount.AccountType.EQUITY,
        currency=currency,
        name="Ajuste importacion portable",
    )
    entries.append(
        {
            "account_id": contra_account.id,
            "side": counter_side,
            "amount": amount,
            "currency": currency,
            "flow_family": "",
            "category_key": "",
            "subcategory_key": "",
            "annual_income_entry_id": None,
            "annual_expense_entry_id": None,
            "asset_id": None,
            "liability_id": None,
            "notes": "Contraapunte generado automaticamente durante importacion portable.",
        }
    )


def _ensure_balanced_entries_by_currency(*, payload: dict[str, Any], user: Any) -> None:
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        return

    totals_by_currency: dict[str, dict[str, Decimal]] = {}
    for entry in entries:
        currency = str(entry.get("currency", "EUR")).strip().upper() or "EUR"
        side = str(entry.get("side", "debit")).strip().lower()
        amount_raw = str(entry.get("amount", "0")).strip() or "0"
        try:
            amount = Decimal(amount_raw)
        except (InvalidOperation, ValueError):
            # Let serializer raise canonical validation errors for malformed amounts.
            continue

        if currency not in totals_by_currency:
            totals_by_currency[currency] = {"debit": Decimal("0"), "credit": Decimal("0")}
        if side in ("debit", "credit"):
            totals_by_currency[currency][side] += amount

    for currency, totals in totals_by_currency.items():
        diff = totals["debit"] - totals["credit"]
        if diff == Decimal("0"):
            continue

        contra_side = "credit" if diff > 0 else "debit"
        contra_account = get_or_create_system_account(
            user_id=user.id,
            account_type=LedgerAccount.AccountType.EQUITY,
            currency=currency,
            name="Ajuste importacion portable",
        )
        entries.append(
            {
                "account_id": contra_account.id,
                "side": contra_side,
                "amount": str(abs(diff)),
                "currency": currency,
                "flow_family": "",
                "category_key": "",
                "subcategory_key": "",
                "annual_income_entry_id": None,
                "annual_expense_entry_id": None,
                "asset_id": None,
                "liability_id": None,
                "notes": (
                    "Contraapunte generado automaticamente para balancear "
                    "la transaccion por moneda durante importacion portable."
                ),
            }
        )


def import_portable_bundle(*, user, request, mode: str, bundle: dict[str, Any]) -> dict[str, Any]:
    context = PortableImportContext(user=user, request=request)
    premium = bundle.get("premium") if isinstance(bundle.get("premium"), dict) else None
    data = bundle["data"]
    accounting = data.get("accounting") if isinstance(data.get("accounting"), dict) else {}
    asset_valuations = list(data.get("asset_valuations", []))
    investment_events = list(data.get("investment_events", []))
    liquidity_events = list(data.get("liquidity_events", []))
    liability_events = list(data.get("liability_events", []))
    liability_valuations = list(data.get("liability_valuations", []))
    accounting_accounts = list(accounting.get("accounts", []))
    accounting_transactions = list(accounting.get("transactions", []))

    with transaction.atomic():
        if mode == "replace":
            _clear_existing_portable_core_data(user=user)
            if premium is not None:
                _clear_existing_portable_premium_data(user=user)

        ownership_id_map = _import_family_and_ownerships(context=context, premium=premium)
        asset_id_map = _import_assets(context=context, assets=list(data["assets"]))
        liability_id_map = _import_liabilities(
            context=context,
            liabilities=list(data["liabilities"]),
            asset_id_map=asset_id_map,
        )
        asset_valuation_count = _import_asset_valuations(
            context=context,
            valuations=asset_valuations,
            asset_id_map=asset_id_map,
        )
        investment_event_count = _import_investment_events(
            context=context,
            events=investment_events,
            asset_id_map=asset_id_map,
        )
        liquidity_event_count = _import_liquidity_events(
            context=context,
            events=liquidity_events,
            asset_id_map=asset_id_map,
        )
        liability_event_count = _import_liability_events(
            context=context,
            events=liability_events,
            liability_id_map=liability_id_map,
        )
        liability_valuation_count = _import_liability_valuations(
            context=context,
            valuations=liability_valuations,
            liability_id_map=liability_id_map,
        )
        income_count, annual_income_id_map = _import_annual_income(
            context=context, annual_income=list(data["annual_income"])
        )
        expense_count, annual_expense_id_map = _import_annual_expense(
            context=context, annual_expense=list(data["annual_expense"])
        )
        account_id_map = _import_ledger_accounts(
            context=context,
            accounts=accounting_accounts,
            asset_id_map=asset_id_map,
            liability_id_map=liability_id_map,
        )
        _sync_imported_tracking_account_links(
            context=context,
            assets=list(data["assets"]),
            liabilities=list(data["liabilities"]),
            asset_id_map=asset_id_map,
            liability_id_map=liability_id_map,
            account_id_map=account_id_map,
        )
        transaction_count = _import_ledger_transactions(
            context=context,
            transactions=accounting_transactions,
            account_id_map=account_id_map,
            ownership_id_map=ownership_id_map,
            annual_income_id_map=annual_income_id_map,
            annual_expense_id_map=annual_expense_id_map,
            asset_id_map=asset_id_map,
            liability_id_map=liability_id_map,
        )
        _import_settings(context=context, bundle=bundle)
        ownership_link_count = _import_ownership_links(
            context=context,
            premium=premium,
            ownership_id_map=ownership_id_map,
            asset_id_map=asset_id_map,
            liability_id_map=liability_id_map,
        )

    return {
        "ok": True,
        "mode": mode,
        "meta": {
            "schema_version": bundle.get("schema_version", 1),
            "source_app": bundle.get("source_app", "core"),
            "exported_at": bundle.get("exported_at", ""),
            "exported_app_version": bundle.get("exported_app_version"),
            "imported_into_app_version": get_current_portable_app_version(),
        },
        "counts": {
            "annual_income": income_count,
            "annual_expense": expense_count,
            "assets": len(data["assets"]),
            "liabilities": len(data["liabilities"]),
            "asset_valuations": asset_valuation_count,
            "investment_events": investment_event_count,
            "liquidity_events": liquidity_event_count,
            "liability_events": liability_event_count,
            "liability_valuations": liability_valuation_count,
            "accounting_accounts": len(accounting_accounts),
            "accounting_transactions": transaction_count,
            "family_members": len(premium["family_members"]) if premium is not None else 0,
            "ownerships": len(premium["ownerships"]) if premium is not None else 0,
            "ownership_links": ownership_link_count,
        },
    }


def import_portable_bundle_from_request(*, user, request_data, request) -> dict[str, Any]:
    serializer = PortableImportRequestSerializer(data=request_data)
    serializer.is_valid(raise_exception=True)
    validated = serializer.validated_data
    return import_portable_bundle(
        user=user,
        request=request,
        mode=validated["mode"],
        bundle=validated["bundle"],
    )
