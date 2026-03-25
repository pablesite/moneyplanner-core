from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError

from accounts.services import get_or_create_user_settings, update_user_settings
from budget.models import AnnualExpenseEntry, AnnualIncomeEntry
from budget.serializers import AnnualExpenseEntrySerializer, AnnualIncomeEntrySerializer
from memberships.models import FamilyMember, Ownership, OwnershipLink
from memberships.serializers import FamilyMemberSerializer, OwnershipWriteSerializer
from memberships.services import sync_ownership_link
from net_worth.models import Asset, Liability
from net_worth.serializers import AssetSerializer, LiabilitySerializer
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
        "tracking_mode": str(asset.get("tracking_mode", "manual")),
        "accounting_account_id": asset.get("accounting_account_id"),
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
        "market_value_override": normalize_optional_text(asset.get("market_value_override")),
        "market_value_override_date": normalize_optional_text(
            asset.get("market_value_override_date")
        ),
        "initial_purchase_value": normalize_optional_text(asset.get("initial_purchase_value")),
        "amortization_method": normalize_optional_text(asset.get("amortization_method")) or "none",
        "amortization_term_years": asset.get("amortization_term_years"),
        "annual_interest_tae": normalize_imported_asset_tae(asset),
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
        "tracking_mode": str(liability.get("tracking_mode", "manual")),
        "accounting_account_id": liability.get("accounting_account_id"),
        "currency": str(liability.get("currency", "EUR")).upper(),
        "start_date": liability.get("start_date"),
        "payment_start_date": normalize_optional_text(liability.get("payment_start_date")),
        "expected_end_date": normalize_optional_text(liability.get("expected_end_date")),
        "term_months": liability.get("term_months"),
        "rate_type": normalize_optional_text(liability.get("rate_type")) or "fixed",
        "payment_frequency": normalize_optional_text(liability.get("payment_frequency"))
        or "monthly",
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


def _import_annual_income(
    *, context: PortableImportContext, annual_income: list[dict[str, Any]]
) -> int:
    for entry in sorted(annual_income, key=lambda row: int(row.get("id", 0))):
        serializer = AnnualIncomeEntrySerializer(
            data=_prepare_income_payload(entry),
            context={"request": context.request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(user=context.user)
    return len(annual_income)


def _import_annual_expense(
    *, context: PortableImportContext, annual_expense: list[dict[str, Any]]
) -> int:
    for entry in sorted(annual_expense, key=lambda row: int(row.get("id", 0))):
        serializer = AnnualExpenseEntrySerializer(
            data=_prepare_expense_payload(entry),
            context={"request": context.request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(user=context.user)
    return len(annual_expense)


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


def import_portable_bundle(*, user, request, mode: str, bundle: dict[str, Any]) -> dict[str, Any]:
    context = PortableImportContext(user=user, request=request)
    premium = bundle.get("premium") if isinstance(bundle.get("premium"), dict) else None
    data = bundle["data"]

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
        income_count = _import_annual_income(
            context=context, annual_income=list(data["annual_income"])
        )
        expense_count = _import_annual_expense(
            context=context, annual_expense=list(data["annual_expense"])
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
