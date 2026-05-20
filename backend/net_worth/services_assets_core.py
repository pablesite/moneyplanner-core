from __future__ import annotations

from bisect import bisect_right
from datetime import date, timedelta
from decimal import Decimal
from typing import cast

from django.db import transaction
from django.db.models import Q

from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError

from core.models import InflationIndex
from core.services import convert_currency, convert_currency_cached

from .services_liabilities_core import _last_day_of_month

from .models import (
    ASSET_SUBCATEGORY_MAP,
    Asset,
    AssetImprovement,
    AssetValuation,
    InvestmentAssetEvent,
    LiquidityAssetEvent,
    LiquidityMonthlyCheckin,
)

ASSET_CASH_SUBCATEGORIES_REQUIRING_TAE = {
    Asset.Subcategory.BANK_ACCOUNT,
    Asset.Subcategory.SHORT_TERM_DEPOSIT,
    Asset.Subcategory.CRYPTO_SPOT_EARN,
    Asset.Subcategory.OTHER,
}

FURNISHINGS_DEGRESSIVE_PROFILES: dict[str, tuple[tuple[Decimal, ...], Decimal, Decimal, int]] = {
    cast(str, Asset.Subcategory.VEHICLES): (
        (
            Decimal("0.18"),
            Decimal("0.15"),
            Decimal("0.12"),
            Decimal("0.10"),
        ),
        Decimal("0.08"),
        Decimal("0.15"),
        20,
    ),
    cast(str, Asset.Subcategory.SPORTS_EQUIPMENT): (
        (
            Decimal("0.12"),
            Decimal("0.10"),
            Decimal("0.08"),
        ),
        Decimal("0.06"),
        Decimal("0.20"),
        15,
    ),
}
RESIDENTIAL_REAL_ESTATE_SUBCATEGORIES = {
    Asset.Subcategory.PRIMARY_HOME,
    Asset.Subcategory.SECOND_HOME,
    Asset.Subcategory.RENTAL,
}
SYSTEM_GENERATED_ASSET_EXPENSE_EVENT_PREFIX = "asset_"
OPENING_ASSET_NOTE_PREFIX = "net_worth_opening_balance:asset:"
OPENING_BALANCE_DESCRIPTION_PREFIX = "Saldo inicial"
INVESTMENTS_SUBCATEGORY_TO_EXPENSE_SUBCATEGORY: dict[str, str] = {
    cast(str, Asset.Subcategory.DEPOSITS): "deposits_fixed_income",
    cast(str, Asset.Subcategory.FUNDS): "index_funds",
    cast(str, Asset.Subcategory.ETFS): "etf_indexed",
    cast(str, Asset.Subcategory.PENSION_PLANS): "pension_plan",
    cast(str, Asset.Subcategory.STOCKS): "stocks_dividends",
    cast(str, Asset.Subcategory.CRYPTOCURRENCIES): "crypto",
    cast(str, Asset.Subcategory.REAL_ESTATE_CROWD): "crowdfunding_real_estate",
    cast(str, Asset.Subcategory.CROWDLENDING): "crowdlending_p2p",
    cast(str, Asset.Subcategory.ROBOADVISOR): "roboadvisor",
    cast(str, Asset.Subcategory.OTHER): "other_financial_investments",
}


class AccountingIntegrationState:
    LINKED = "linked"
    AUTO_CREATED = "auto_created"
    NEEDS_REVIEW = "needs_review"


def _build_investment_contribution_schedule(
    *,
    asset: Asset,
    as_of_date: date | None = None,
    horizon_end_date: date | None = None,
) -> list[tuple[date, Decimal]]:
    # Deferred import to avoid circular dependency with budget sync module.
    from .services_assets_budget import (
        _build_investment_contribution_schedule as budget_schedule_builder,
    )

    return budget_schedule_builder(
        asset=asset,
        as_of_date=as_of_date,
        horizon_end_date=horizon_end_date,
    )


def _get_investment_contribution_schedule_cached(
    *,
    asset: Asset,
    as_of_date: date,
    position_cache=None,
) -> list[tuple[date, Decimal]]:
    if position_cache is None:
        return _build_investment_contribution_schedule(asset=asset, as_of_date=as_of_date)
    key = (asset.id, as_of_date)
    cached = position_cache.periodic_investment_schedules.get(key)
    if cached is not None:
        return cached
    schedule = _build_investment_contribution_schedule(asset=asset, as_of_date=as_of_date)
    position_cache.periodic_investment_schedules[key] = schedule
    return schedule


def _get_accounting_asset_account(*, user_id: int, account_id: int | None):
    from accounting.models import LedgerAccount
    from accounting.services_ledger import get_user_ledger_account

    return get_user_ledger_account(
        user_id=user_id,
        account_id=account_id,
        expected_type=cast(str, LedgerAccount.AccountType.ASSET),
    )


@transaction.atomic
def ensure_asset_accounting_account(*, asset: Asset) -> str | None:
    if asset.tracking_mode != Asset.TrackingMode.ACCOUNTING:
        return None

    from accounting.models import LedgerAccount
    from accounting.services_ledger import normalize_currency_code

    normalized_currency = normalize_currency_code(asset.currency)
    if len(normalized_currency) != 3:
        return AccountingIntegrationState.NEEDS_REVIEW

    if asset.accounting_account_id:
        account = _get_accounting_asset_account(
            user_id=asset.user_id,
            account_id=asset.accounting_account_id,
        )
        if (
            account is None
            or account.currency != normalized_currency
            or account.asset_id not in (None, asset.id)
        ):
            return AccountingIntegrationState.NEEDS_REVIEW

        update_fields: list[str] = []
        if account.asset_id is None:
            account.asset_id = asset.id
            update_fields.append("asset")
        if not account.is_active and asset.is_active:
            account.is_active = True
            update_fields.append("is_active")
        if update_fields:
            account.save(update_fields=update_fields)
        return AccountingIntegrationState.LINKED

    existing_accounts = list(
        LedgerAccount.objects.filter(
            user_id=asset.user_id,
            account_type=LedgerAccount.AccountType.ASSET,
            currency=normalized_currency,
            asset_id=asset.id,
        )
        .order_by("id")
        .only("id")
    )
    if len(existing_accounts) == 1:
        asset.accounting_account_id = existing_accounts[0].id
        asset.save(update_fields=["accounting_account_id"])
        return AccountingIntegrationState.LINKED
    if len(existing_accounts) > 1:
        return AccountingIntegrationState.NEEDS_REVIEW

    account = LedgerAccount.objects.create(
        user=asset.user,
        name=asset.name[:120] or f"Activo {asset.id}",
        account_type=LedgerAccount.AccountType.ASSET,
        currency=normalized_currency,
        origin=LedgerAccount.Origin.SYSTEM,
        asset=asset,
        is_active=True,
    )
    asset.accounting_account_id = account.id
    asset.save(update_fields=["accounting_account_id"])
    return AccountingIntegrationState.AUTO_CREATED


def _validate_accounting_asset_account_link(
    *,
    user_id: int | None,
    accounting_account_id,
    current_asset_id: int | None,
    currency: str | None,
) -> None:
    if user_id is None:
        return

    accounting_account = _get_accounting_asset_account(
        user_id=user_id,
        account_id=accounting_account_id,
    )
    if accounting_account is None:
        raise DRFValidationError(
            {
                "accounting_account_id": (
                    "La cuenta contable no existe, no pertenece al usuario o no es de tipo asset."
                )
            }
        )
    normalized_currency = str(currency or "").strip().upper()
    if normalized_currency and accounting_account.currency != normalized_currency:
        raise DRFValidationError(
            {"accounting_account_id": "La cuenta contable debe usar la misma moneda que el activo."}
        )
    if accounting_account.asset_id not in (None, current_asset_id):
        raise DRFValidationError(
            {"accounting_account_id": "La cuenta contable ya esta vinculada a otro activo."}
        )


def _validate_market_value_override_payload(
    *,
    category,
    market_value_override,
    market_value_override_date: date | None,
) -> None:
    if category != Asset.Category.INVESTMENTS:
        if market_value_override is not None or market_value_override_date is not None:
            raise DRFValidationError(
                {"market_value_override": ("Solo aplica a activos de inversiones.")}
            )
        return
    if market_value_override is not None and market_value_override_date is None:
        raise DRFValidationError(
            {"market_value_override_date": ("Requerida si se informa valor de mercado manual.")}
        )
    if market_value_override is None and market_value_override_date is not None:
        raise DRFValidationError(
            {"market_value_override": ("Requerido si se informa fecha de valoracion manual.")}
        )


def validate_asset_payload(
    *,
    tracking_mode: str | None,
    accounting_account_id,
    category,
    subcategory,
    annual_interest_tae,
    amortization_method,
    amortization_term_years,
    initial_purchase_value,
    amount=None,
    start_date: date | None = None,
    valuation_model=None,
    land_value_share_percent=None,
    land_annual_appreciation_percent=None,
    building_annual_depreciation_percent=None,
    deposit_term_months=None,
    market_value_override=None,
    market_value_override_date: date | None = None,
    has_contribution_intervals: bool = False,
    user_id: int | None = None,
    current_asset_id: int | None = None,
    currency: str | None = None,
) -> None:
    if (
        tracking_mode == Asset.TrackingMode.ACCOUNTING
        and accounting_account_id is not None
        and user_id is not None
    ):
        _validate_accounting_asset_account_link(
            user_id=user_id,
            accounting_account_id=accounting_account_id,
            current_asset_id=current_asset_id,
            currency=currency,
        )

    if category and subcategory:
        allowed = ASSET_SUBCATEGORY_MAP.get(category)
        if allowed and subcategory not in allowed:
            raise DRFValidationError({"subcategory": "Subcategoria invalida para esta categoria."})

    requires_tae = (
        category == Asset.Category.CASH and subcategory in ASSET_CASH_SUBCATEGORIES_REQUIRING_TAE
    )
    if requires_tae and annual_interest_tae is None:
        raise DRFValidationError(
            {
                "annual_interest_tae": (
                    "Requerido para liquidez en cuenta bancaria, depositos a corto plazo, "
                    "spot/earn cripto y otros."
                )
            }
        )

    if (
        category == Asset.Category.CASH
        and subcategory == Asset.Subcategory.SHORT_TERM_DEPOSIT
        and deposit_term_months is None
    ):
        raise DRFValidationError(
            {"deposit_term_months": ("Requerido para depositos a corto plazo (1-12 meses).")}
        )

    if deposit_term_months is not None and (
        not isinstance(deposit_term_months, int)
        or deposit_term_months < 1
        or deposit_term_months > 12
    ):
        raise DRFValidationError(
            {"deposit_term_months": ("La duracion del deposito debe estar entre 1 y 12 meses.")}
        )

    purchase_value = initial_purchase_value if initial_purchase_value is not None else amount

    if (
        category == Asset.Category.INVESTMENTS
        and has_contribution_intervals
        and purchase_value is None
    ):
        raise DRFValidationError(
            {"amount": ("Requerido para aportacion periodica en inversiones.")}
        )

    _validate_market_value_override_payload(
        category=category,
        market_value_override=market_value_override,
        market_value_override_date=market_value_override_date,
    )

    if amortization_method == Asset.AmortizationMethod.STRAIGHT_LINE:
        if purchase_value is None:
            raise DRFValidationError(
                {"initial_purchase_value": ("Requerido si se define amortizacion del activo.")}
            )
        default_term_years = get_default_amortization_term_years(
            category=category,
            subcategory=subcategory,
            amortization_method=amortization_method,
        )
        if amortization_term_years is None and default_term_years is None:
            raise DRFValidationError(
                {"amortization_term_years": ("Requerido si se define amortizacion del activo.")}
            )

    is_auto_real_estate = valuation_model == Asset.ValuationModel.REAL_ESTATE_AUTO
    if is_auto_real_estate:
        if not (
            category == Asset.Category.REAL_ESTATE
            and subcategory in RESIDENTIAL_REAL_ESTATE_SUBCATEGORIES
        ):
            raise DRFValidationError(
                {
                    "valuation_model": (
                        "La valoracion automatica solo aplica a inmuebles residenciales."
                    )
                }
            )
        if initial_purchase_value is None:
            raise DRFValidationError(
                {"initial_purchase_value": ("Requerido para valoracion automatica de vivienda.")}
            )
        if land_value_share_percent is None:
            raise DRFValidationError(
                {"land_value_share_percent": ("Requerido para valoracion automatica de vivienda.")}
            )
        if land_annual_appreciation_percent is None:
            raise DRFValidationError(
                {
                    "land_annual_appreciation_percent": (
                        "Requerido para valoracion automatica de vivienda."
                    )
                }
            )
        if building_annual_depreciation_percent is None:
            raise DRFValidationError(
                {
                    "building_annual_depreciation_percent": (
                        "Requerido para valoracion automatica de vivienda."
                    )
                }
            )


def create_asset_for_user(*, user, validated_data: dict) -> Asset:
    return Asset.objects.create(user=user, **validated_data)


def validate_asset_improvement_payload(
    *,
    amortization_method: str | None,
    amortization_term_years,
    capitalize_interest: bool,
    annual_interest_tae,
    manual_current_value,
) -> None:
    if amortization_method == AssetImprovement.AmortizationMethod.STRAIGHT_LINE:
        if amortization_term_years is None:
            raise DRFValidationError(
                {"amortization_term_years": "Requerido si la reforma amortiza en lineal."}
            )
    else:
        if amortization_term_years is not None:
            raise DRFValidationError(
                {
                    "amortization_term_years": (
                        "Solo aplica cuando amortization_method=straight_line."
                    )
                }
            )

    if amortization_method == AssetImprovement.AmortizationMethod.MANUAL:
        if manual_current_value is None:
            raise DRFValidationError(
                {"manual_current_value": "Requerido si amortization_method=manual."}
            )
    elif manual_current_value is not None:
        raise DRFValidationError(
            {"manual_current_value": "Solo aplica cuando amortization_method=manual."}
        )

    if capitalize_interest and annual_interest_tae is None:
        raise DRFValidationError({"annual_interest_tae": "Requerido si capitalize_interest=true."})


def _whole_months_elapsed(*, start: date, end: date) -> int:
    if end <= start:
        return 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(months, 0)


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _get_inflation_index_or_none(*, region: str, period_month: date) -> Decimal | None:
    row = (
        InflationIndex.objects.filter(region=region, period__lte=period_month)
        .order_by("-period")
        .first()
    )
    if row:
        return Decimal(row.index)
    first_row = InflationIndex.objects.filter(region=region).order_by("period").first()
    if first_row:
        return Decimal(first_row.index)
    return None


def _get_cached_inflation_index_or_none(
    *,
    region: str,
    period_month: date,
    position_cache,
) -> Decimal | None:
    rows = getattr(position_cache, "inflation_indexes", {}).get(region, [])
    if not rows:
        return None
    previous_index = None
    for row_period, row_index in rows:
        if row_period <= period_month:
            previous_index = row_index
        else:
            break
    return previous_index if previous_index is not None else rows[0][1]


def _get_inflation_growth_factor_or_one(
    *,
    start: date,
    end: date,
    position_cache=None,
) -> Decimal:
    if end <= start:
        return Decimal("1")
    region = cast(str, InflationIndex.Region.ES)
    start_month = _month_start(start)
    end_month = _month_start(end)
    if position_cache is not None:
        start_index = _get_cached_inflation_index_or_none(
            region=region,
            period_month=start_month,
            position_cache=position_cache,
        )
        end_index = _get_cached_inflation_index_or_none(
            region=region,
            period_month=end_month,
            position_cache=position_cache,
        )
    else:
        start_index = _get_inflation_index_or_none(
            region=region,
            period_month=start_month,
        )
        end_index = _get_inflation_index_or_none(
            region=region,
            period_month=end_month,
        )
    if not start_index or not end_index or start_index == 0:
        return Decimal("1")
    return end_index / start_index


def get_default_amortization_term_years(
    *,
    category: str | None,
    subcategory: str | None,
    amortization_method: str | None,
) -> int | None:
    if (
        category != Asset.Category.FURNISHINGS
        or amortization_method != Asset.AmortizationMethod.STRAIGHT_LINE
    ):
        return None
    profile = FURNISHINGS_DEGRESSIVE_PROFILES.get(str(subcategory or "").strip())
    if not profile:
        return None
    return profile[3]


def _get_degressive_remaining_ratio(
    *,
    elapsed_months: int,
    annual_rates: tuple[Decimal, ...],
    tail_annual_rate: Decimal,
) -> Decimal:
    if elapsed_months <= 0:
        return Decimal("1")
    remaining = Decimal("1")
    months_left = elapsed_months
    year_index = 0
    while months_left > 0:
        chunk_months = min(12, months_left)
        annual_rate = (
            annual_rates[year_index] if year_index < len(annual_rates) else tail_annual_rate
        )
        chunk_factor = Decimal("1") - (annual_rate * (Decimal(str(chunk_months)) / Decimal("12")))
        if chunk_factor < 0:
            chunk_factor = Decimal("0")
        remaining *= chunk_factor
        months_left -= chunk_months
        year_index += 1
    if remaining < 0:
        return Decimal("0")
    return remaining


def _get_effective_accounting_asset_amount_or_none(
    *,
    asset: Asset,
    as_of_date: date,
    position_cache=None,
) -> Decimal | None:
    if asset.tracking_mode != Asset.TrackingMode.ACCOUNTING:
        return None

    if position_cache is not None:
        account_id = asset.accounting_account_id
        if account_id is None:
            return None
        account_id_int = int(account_id)
        cached_account = getattr(position_cache, "accounting_accounts", {}).get(account_id_int)
        if (
            cached_account is None
            or cached_account["account_type"] != "asset"
            or cached_account["currency"] != asset.currency
            or cached_account["asset_id"] not in (None, asset.id)
        ):
            return None

        dates = position_cache.accounting_prefix_dates.get(account_id_int, [])
        if not dates:
            return None
        idx = bisect_right(dates, as_of_date) - 1
        if idx < 0:
            return None
        debit_total = position_cache.accounting_prefix_debits[account_id_int][idx]
        credit_total = position_cache.accounting_prefix_credits[account_id_int][idx]
        raw_full = debit_total - credit_total

        if asset.category == Asset.Category.CASH:
            opening_date = position_cache.asset_opening_booking_dates.get(asset.id)
            if opening_date is not None and as_of_date >= opening_date:
                before_opening_idx = bisect_right(dates, opening_date - timedelta(days=1)) - 1
                if before_opening_idx >= 0:
                    before_debit_total = position_cache.accounting_prefix_debits[account_id_int][
                        before_opening_idx
                    ]
                    before_credit_total = position_cache.accounting_prefix_credits[account_id_int][
                        before_opening_idx
                    ]
                    raw_full -= before_debit_total - before_credit_total
        return raw_full

    integration_state = ensure_asset_accounting_account(asset=asset)
    if integration_state == AccountingIntegrationState.NEEDS_REVIEW:
        return None

    from accounting.models import LedgerTransaction
    from accounting.services_ledger import (
        compute_account_balance_from_totals,
        compute_entry_balance_totals,
        get_account_balance,
        get_account_entries,
        has_account_entries,
    )

    accounting_account = _get_accounting_asset_account(
        user_id=asset.user_id,
        account_id=asset.accounting_account_id,
    )
    if accounting_account is None or accounting_account.currency != asset.currency:
        return None

    should_apply_opening_anchor = asset.category == Asset.Category.CASH

    if not has_account_entries(
        account=accounting_account,
        as_of_date=as_of_date,
        status=cast(str, LedgerTransaction.Status.POSTED),
    ):
        return None

    if should_apply_opening_anchor:
        opening_tx = _get_latest_opening_balance_tx_for_accounting_asset(
            user_id=asset.user_id,
            asset_id=asset.id,
            account_id=accounting_account.id,
        )
        if opening_tx is not None and as_of_date >= opening_tx.booking_date:
            anchored_entries = get_account_entries(
                account=accounting_account,
                as_of_date=as_of_date,
                status=cast(str, LedgerTransaction.Status.POSTED),
            ).filter(transaction__booking_date__gte=opening_tx.booking_date)
            if anchored_entries.exists():
                totals = compute_entry_balance_totals(
                    anchored_entries,
                    account_id=accounting_account.id,
                )
                return compute_account_balance_from_totals(
                    account_type=accounting_account.account_type,
                    totals=totals,
                )

    return get_account_balance(
        account=accounting_account,
        as_of_date=as_of_date,
        status=cast(str, LedgerTransaction.Status.POSTED),
    )


def _get_latest_opening_balance_tx_for_accounting_asset(
    *,
    user_id: int,
    asset_id: int,
    account_id: int,
):
    from accounting.models import LedgerTransaction
    from accounting.services_ledger import build_net_worth_opening_balance_note

    opening_note = build_net_worth_opening_balance_note(
        position_kind="asset",
        position_id=asset_id,
    )
    exact_match = (
        LedgerTransaction.objects.filter(
            user_id=user_id,
            status=LedgerTransaction.Status.POSTED,
            notes=opening_note,
            entries__account_id=account_id,
        )
        .distinct()
        .order_by("-booking_date", "-id")
        .first()
    )
    if exact_match is not None:
        return exact_match

    queryset = LedgerTransaction.objects.filter(
        user_id=user_id,
        status=LedgerTransaction.Status.POSTED,
        entries__account_id=account_id,
    ).filter(
        Q(
            origin=LedgerTransaction.Origin.SYSTEM,
            notes__startswith=OPENING_ASSET_NOTE_PREFIX,
            entries__asset_id=asset_id,
        )
        | Q(
            origin=LedgerTransaction.Origin.SYSTEM,
            description__startswith=OPENING_BALANCE_DESCRIPTION_PREFIX,
        )
    )
    for tx in queryset.distinct().order_by("-booking_date", "-id"):
        if _is_opening_balance_candidate_for_accounting_asset(
            transaction=tx,
            asset_id=asset_id,
            account_id=account_id,
        ):
            return tx
    return None


def _is_opening_balance_candidate_for_accounting_asset(
    *,
    transaction,
    asset_id: int,
    account_id: int,
) -> bool:
    from accounting.models import LedgerAccount

    entries = list(transaction.entries.select_related("account").all())
    if len(entries) != 2:
        return False

    position_entries = [entry for entry in entries if entry.account_id == account_id]
    if len(position_entries) != 1:
        return False

    counterpart_entries = [entry for entry in entries if entry.account_id != account_id]
    if len(counterpart_entries) != 1:
        return False

    position_entry = position_entries[0]
    counterpart_entry = counterpart_entries[0]

    if counterpart_entry.account.account_type != LedgerAccount.AccountType.EQUITY:
        return False
    if position_entry.amount != counterpart_entry.amount:
        return False
    if position_entry.side == counterpart_entry.side:
        return False
    if position_entry.asset_id not in (None, asset_id):
        return False
    return True


def _cached_latest_valuation(position_cache, asset_id: int, as_of_date: date):
    """Return the latest AssetValuation <= as_of_date from the cache, or None."""
    entries = position_cache.asset_valuations.get(asset_id, [])
    # entries are pre-sorted desc by (valuation_date, updated_at, id)
    for v in entries:
        if v.valuation_date <= as_of_date:
            return v
    return None


def get_effective_asset_amount(
    *,
    asset: Asset,
    as_of_date: date | None = None,
    position_cache=None,
) -> Decimal:
    ref_date = as_of_date or timezone.localdate()
    accounting_amount = _get_effective_accounting_asset_amount_or_none(
        asset=asset,
        as_of_date=ref_date,
        position_cache=position_cache,
    )
    if accounting_amount is not None:
        return accounting_amount

    if asset.category == Asset.Category.INVESTMENTS:
        return _get_effective_investment_asset_amount(
            asset=asset,
            as_of_date=ref_date,
            position_cache=position_cache,
        )
    if asset.category == Asset.Category.CASH:
        return _get_effective_cash_asset_amount(
            asset=asset,
            as_of_date=ref_date,
            position_cache=position_cache,
        )

    manual_override = _get_latest_asset_manual_value(
        asset=asset,
        as_of_date=ref_date,
        position_cache=position_cache,
    )
    if manual_override is not None:
        return manual_override

    if (
        asset.category == Asset.Category.INVESTMENTS
        and _can_apply_periodic_investment_to_effective_amount(asset=asset)
    ):
        accrued_contributions = sum(
            installment
            for _, installment in _get_investment_contribution_schedule_cached(
                asset=asset, as_of_date=ref_date, position_cache=position_cache
            )
        )
        return Decimal(asset.amount) + Decimal(accrued_contributions)

    if (
        asset.valuation_model != Asset.ValuationModel.REAL_ESTATE_AUTO
        or asset.category != Asset.Category.REAL_ESTATE
        or asset.subcategory not in RESIDENTIAL_REAL_ESTATE_SUBCATEGORIES
    ):
        if asset.amortization_method == Asset.AmortizationMethod.STRAIGHT_LINE:
            term_years = asset.amortization_term_years or 0
            if term_years <= 0:
                default_term_years = get_default_amortization_term_years(
                    category=asset.category,
                    subcategory=asset.subcategory,
                    amortization_method=asset.amortization_method,
                )
                term_years = default_term_years or 0
            if term_years <= 0:
                return asset.amount
            purchase_value = (
                asset.amount
                if asset.category == Asset.Category.FURNISHINGS
                else asset.initial_purchase_value or asset.amount
            )
            months = _whole_months_elapsed(start=asset.start_date, end=ref_date)
            life_months = term_years * 12
            profile = FURNISHINGS_DEGRESSIVE_PROFILES.get(asset.subcategory)

            if profile is None:
                remaining_ratio = Decimal("1") - (Decimal(str(months)) / Decimal(str(life_months)))
                if remaining_ratio < 0:
                    remaining_ratio = Decimal("0")
                if remaining_ratio == 0:
                    return Decimal("0")
            else:
                months_for_depreciation = min(months, life_months)
                annual_rates, tail_annual_rate, residual_ratio, _default_term_years = profile
                remaining_ratio = _get_degressive_remaining_ratio(
                    elapsed_months=months_for_depreciation,
                    annual_rates=annual_rates,
                    tail_annual_rate=tail_annual_rate,
                )
                if remaining_ratio < residual_ratio:
                    remaining_ratio = residual_ratio

            effective_value = purchase_value * remaining_ratio
            if asset.category == Asset.Category.FURNISHINGS and asset.currency == "EUR":
                inflation_growth = _get_inflation_growth_factor_or_one(
                    start=asset.start_date,
                    end=ref_date,
                    position_cache=position_cache,
                )
                effective_value *= inflation_growth
            return effective_value
        return asset.amount

    purchase_value = asset.initial_purchase_value or asset.amount
    land_share = asset.land_value_share_percent
    land_appreciation = asset.land_annual_appreciation_percent
    building_depreciation = asset.building_annual_depreciation_percent
    if (
        purchase_value is None
        or land_share is None
        or land_appreciation is None
        or building_depreciation is None
    ):
        return asset.amount

    months = _whole_months_elapsed(start=asset.start_date, end=ref_date)
    land_initial = purchase_value * (land_share / Decimal("100"))
    building_initial = purchase_value - land_initial

    land_monthly_rate = land_appreciation / Decimal("1200")
    building_monthly_depreciation = building_depreciation / Decimal("1200")

    land_growth_factor = Decimal("1") + land_monthly_rate
    building_decay_factor = Decimal("1") - building_monthly_depreciation
    if building_decay_factor < 0:
        building_decay_factor = Decimal("0")

    land_amount = land_initial * (land_growth_factor**months)
    building_amount = building_initial * (building_decay_factor**months)
    if building_amount < 0:
        building_amount = Decimal("0")

    improvements_total = Decimal("0")
    for improvement in asset.improvements.all():
        improvements_total += get_effective_asset_improvement_amount(
            improvement=improvement,
            as_of_date=ref_date,
        )
    return land_amount + building_amount + improvements_total


def _get_effective_investment_asset_amount(
    *,
    asset: Asset,
    as_of_date: date,
    position_cache=None,
) -> Decimal:
    anchor_date = None
    anchor_value = Decimal(asset.amount)

    if position_cache is not None:
        latest_manual = _cached_latest_valuation(position_cache, asset.id, as_of_date)
    else:
        latest_manual = (
            AssetValuation.objects.filter(asset=asset, valuation_date__lte=as_of_date)
            .order_by("-valuation_date", "-updated_at", "-id")
            .first()
        )
    latest_market_override = (
        asset.market_value_override
        if asset.market_value_override is not None
        and asset.market_value_override_date is not None
        and asset.market_value_override_date <= as_of_date
        else None
    )
    latest_manual_date = latest_manual.valuation_date if latest_manual is not None else None
    latest_market_override_date = (
        asset.market_value_override_date if latest_market_override is not None else None
    )
    if latest_manual is not None and (
        latest_market_override_date is None or latest_manual_date >= latest_market_override_date
    ):
        anchor_date = latest_manual.valuation_date
        anchor_value = Decimal(latest_manual.value)
    elif latest_market_override is not None:
        return Decimal(latest_market_override)

    event_delta = get_investment_asset_events_delta(
        asset=asset,
        from_date=anchor_date,
        as_of_date=as_of_date,
        position_cache=position_cache,
    )
    scheduled_delta = _get_periodic_investment_delta_since_anchor(
        asset=asset,
        anchor_date=anchor_date,
        as_of_date=as_of_date,
        position_cache=position_cache,
    )
    return anchor_value + event_delta + scheduled_delta


def _get_effective_cash_asset_amount(
    *,
    asset: Asset,
    as_of_date: date,
    position_cache=None,
) -> Decimal:
    anchor_date = None
    anchor_value = Decimal(asset.amount)

    if position_cache is not None:
        latest_manual = _cached_latest_valuation(position_cache, asset.id, as_of_date)
    else:
        latest_manual = (
            AssetValuation.objects.filter(asset=asset, valuation_date__lte=as_of_date)
            .order_by("-valuation_date", "-updated_at", "-id")
            .first()
        )
    latest_checkin = _get_latest_liquidity_checkin(
        asset=asset,
        as_of_date=as_of_date,
        position_cache=position_cache,
    )
    latest_manual_date = latest_manual.valuation_date if latest_manual is not None else None
    latest_checkin_date = _get_liquidity_checkin_effective_date(latest_checkin)

    if latest_manual is not None and (
        latest_checkin_date is None or latest_manual_date >= latest_checkin_date
    ):
        anchor_date = latest_manual.valuation_date
        anchor_value = Decimal(latest_manual.value)
    elif latest_checkin is not None:
        anchor_date = latest_checkin_date
        anchor_value = Decimal(latest_checkin.closing_balance_real)

    delta = get_liquidity_asset_events_delta(
        asset=asset,
        from_date=anchor_date,
        as_of_date=as_of_date,
        position_cache=position_cache,
    )
    return anchor_value + delta


def _get_latest_asset_manual_value(
    *,
    asset: Asset,
    as_of_date: date,
    position_cache=None,
) -> Decimal | None:
    if position_cache is not None:
        valuation = _cached_latest_valuation(position_cache, asset.id, as_of_date)
    else:
        valuation = (
            AssetValuation.objects.filter(asset=asset, valuation_date__lte=as_of_date)
            .order_by("-valuation_date", "-updated_at", "-id")
            .first()
        )
    valuation_date = valuation.valuation_date if valuation is not None else None

    liquidity_checkin = None
    checkin_date = None
    if asset.category == Asset.Category.CASH:
        liquidity_checkin = _get_latest_liquidity_checkin(
            asset=asset,
            as_of_date=as_of_date,
            position_cache=position_cache,
        )
        checkin_date = _get_liquidity_checkin_effective_date(liquidity_checkin)

    if valuation is not None and (checkin_date is None or valuation_date >= checkin_date):
        return Decimal(valuation.value)
    if liquidity_checkin is not None:
        return Decimal(liquidity_checkin.closing_balance_real)
    return None


def _can_apply_periodic_investment_to_effective_amount(*, asset: Asset) -> bool:
    intervals = list(asset.contribution_intervals.all())
    if not intervals:
        return False
    asset_currency = str(asset.currency or "").strip().upper()
    for interval in intervals:
        interval_currency = str(interval.currency or "").strip().upper()
        if interval_currency and interval_currency != asset_currency:
            return False
    return True


def validate_investment_asset_event_payload(
    *,
    asset: Asset | None,
    event_date: date | None = None,
    event_type: str | None,
    amount,
    is_reinvested: bool | None,
) -> None:
    if asset is None:
        raise DRFValidationError({"asset_id": "Requerido."})
    if asset.category != Asset.Category.INVESTMENTS:
        raise DRFValidationError(
            {"asset_id": "Solo se permiten eventos en activos de inversiones."}
        )
    if event_type not in {
        InvestmentAssetEvent.EventType.CONTRIBUTION,
        InvestmentAssetEvent.EventType.WITHDRAWAL,
        InvestmentAssetEvent.EventType.FEE,
        InvestmentAssetEvent.EventType.PASSIVE_INCOME,
    }:
        raise DRFValidationError({"event_type": "Tipo de evento invalido."})
    if amount is None or Decimal(str(amount)) <= 0:
        raise DRFValidationError({"amount": "Debe ser mayor que 0."})
    if event_date is not None and event_date < asset.start_date:
        raise DRFValidationError(
            {"event_date": "Debe ser igual o posterior a start_date del activo."}
        )
    if event_type != InvestmentAssetEvent.EventType.PASSIVE_INCOME and is_reinvested is False:
        raise DRFValidationError(
            {
                "is_reinvested": "Solo aplica a passive_income cuando se desea extraer el rendimiento."
            }
        )


def validate_liquidity_asset_event_payload(
    *,
    asset: Asset | None,
    event_date: date | None = None,
    event_type: str | None,
    amount,
) -> None:
    if asset is None:
        raise DRFValidationError({"asset_id": "Requerido."})
    if asset.category != Asset.Category.CASH:
        raise DRFValidationError(
            {"asset_id": "Solo se permiten movimientos en activos de liquidez."}
        )
    if event_type not in {
        LiquidityAssetEvent.EventType.INFLOW,
        LiquidityAssetEvent.EventType.OUTFLOW,
        LiquidityAssetEvent.EventType.FEE,
        LiquidityAssetEvent.EventType.INTEREST,
    }:
        raise DRFValidationError({"event_type": "Tipo de movimiento invalido."})
    if amount is None or Decimal(str(amount)) <= 0:
        raise DRFValidationError({"amount": "Debe ser mayor que 0."})
    if event_date is not None and event_date < asset.start_date:
        raise DRFValidationError(
            {"event_date": "Debe ser igual o posterior a start_date del activo."}
        )


def get_investment_asset_events_delta(
    *,
    asset: Asset,
    from_date: date | None = None,
    as_of_date: date | None = None,
    position_cache=None,
) -> Decimal:
    ref_date = as_of_date or timezone.localdate()
    delta = Decimal("0")
    if position_cache is not None:
        all_events = position_cache.investment_events.get(asset.id, [])
        events = [
            e
            for e in all_events
            if e.event_date <= ref_date and (from_date is None or e.event_date > from_date)
        ]
    else:
        events = InvestmentAssetEvent.objects.filter(asset=asset, event_date__lte=ref_date)
        if from_date is not None:
            events = events.filter(event_date__gt=from_date)
    for event in events:
        amount = Decimal(event.amount)
        if event.event_type == InvestmentAssetEvent.EventType.CONTRIBUTION:
            delta += amount
        elif event.event_type in (
            InvestmentAssetEvent.EventType.WITHDRAWAL,
            InvestmentAssetEvent.EventType.FEE,
        ):
            delta -= amount
        elif (
            event.event_type == InvestmentAssetEvent.EventType.PASSIVE_INCOME
            and event.is_reinvested
        ):
            delta += amount
    return delta


def get_liquidity_asset_events_delta(
    *,
    asset: Asset,
    from_date: date | None = None,
    as_of_date: date | None = None,
    position_cache=None,
) -> Decimal:
    ref_date = as_of_date or timezone.localdate()
    delta = Decimal("0")
    if position_cache is not None:
        all_events = position_cache.liquidity_events.get(asset.id, [])
        events = [
            e
            for e in all_events
            if e.event_date <= ref_date and (from_date is None or e.event_date > from_date)
        ]
    else:
        events = LiquidityAssetEvent.objects.filter(asset=asset, event_date__lte=ref_date)
        if from_date is not None:
            events = events.filter(event_date__gt=from_date)
    for event in events:
        amount = Decimal(event.amount)
        if event.event_type in (
            LiquidityAssetEvent.EventType.INFLOW,
            LiquidityAssetEvent.EventType.INTEREST,
        ):
            delta += amount
        else:
            delta -= amount
    return delta


def _get_periodic_investment_delta_since_anchor(
    *,
    asset: Asset,
    anchor_date: date | None,
    as_of_date: date,
    position_cache=None,
) -> Decimal:
    if not _can_apply_periodic_investment_to_effective_amount(asset=asset):
        return Decimal("0")
    return sum(
        (
            installment
            for due_date, installment in _get_investment_contribution_schedule_cached(
                asset=asset, as_of_date=as_of_date, position_cache=position_cache
            )
            if anchor_date is None or due_date > anchor_date
        ),
        start=Decimal("0"),
    )


def _get_latest_liquidity_checkin(
    *,
    asset: Asset,
    as_of_date: date,
    position_cache=None,
) -> LiquidityMonthlyCheckin | None:
    if position_cache is not None:
        rows = position_cache.liquidity_checkins.get(asset.id, [])
    else:
        rows = LiquidityMonthlyCheckin.objects.filter(asset=asset).order_by(
            "-fiscal_year", "-month", "-updated_at", "-id"
        )
    candidate = None
    for row in rows:
        effective_date = _get_liquidity_checkin_effective_date(row)
        if effective_date is not None and effective_date <= as_of_date:
            candidate = row
            break
    return candidate


def _get_liquidity_checkin_effective_date(checkin: LiquidityMonthlyCheckin | None) -> date | None:
    if checkin is None:
        return None
    return date(
        checkin.fiscal_year, checkin.month, _last_day_of_month(checkin.fiscal_year, checkin.month)
    )


def get_effective_asset_improvement_amount(
    *, improvement: AssetImprovement, as_of_date: date | None = None
) -> Decimal:
    ref_date = as_of_date or timezone.localdate()
    if ref_date < improvement.reform_date:
        return Decimal("0")

    months = _whole_months_elapsed(start=improvement.reform_date, end=ref_date)
    amount = improvement.amount

    if improvement.capitalize_interest and improvement.annual_interest_tae is not None:
        monthly_rate = improvement.annual_interest_tae / Decimal("1200")
        amount = amount * ((Decimal("1") + monthly_rate) ** months)

    if improvement.amortization_method == AssetImprovement.AmortizationMethod.STRAIGHT_LINE:
        term_years = improvement.amortization_term_years or 0
        if term_years <= 0:
            return amount
        life_months = term_years * 12
        remaining_ratio = Decimal("1") - (Decimal(str(months)) / Decimal(str(life_months)))
        if remaining_ratio < 0:
            remaining_ratio = Decimal("0")
        return amount * remaining_ratio

    if improvement.amortization_method == AssetImprovement.AmortizationMethod.MANUAL:
        return improvement.manual_current_value or amount

    return amount


def get_amount_base_value(
    *,
    amount,
    currency: str,
    base_currency: str | None,
    as_of_date: date | None = None,
    fx_cache: dict | None = None,
):
    if not base_currency:
        return None
    try:
        ref_date = as_of_date or timezone.localdate()
        if fx_cache is not None:
            return str(
                convert_currency_cached(
                    amount,
                    currency,
                    base_currency,
                    rate_date=ref_date,
                    fx_cache=fx_cache,
                )
            )
        return str(convert_currency(amount, currency, base_currency, date=ref_date))
    except Exception:
        return None


def get_financed_asset_queryset_for_user(*, user):
    return Asset.objects.filter(user=user, is_active=True)
