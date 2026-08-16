from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import cast

from django.db import transaction
from django.db.models import Q

from accounts.services import get_base_currency_for_user
from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from memberships.models import Ownership, OwnershipLink
from net_worth.models import Asset, AssetValuation, InvestmentAssetEvent

from .models import (
    Instrument,
    InvestmentContainer,
    Portfolio,
    PortfolioMigrationIssue,
    PortfolioPosition,
    PositionOwnershipPeriod,
    PositionOwnershipShare,
)

FIAT_CURRENCIES = {
    "AUD",
    "CAD",
    "CHF",
    "CNY",
    "DKK",
    "EUR",
    "GBP",
    "HKD",
    "JPY",
    "NOK",
    "NZD",
    "PLN",
    "SEK",
    "SGD",
    "USD",
}

INSTRUMENT_TYPE_BY_SUBCATEGORY = {
    Asset.Subcategory.DEPOSITS: Instrument.InstrumentType.DEPOSIT,
    Asset.Subcategory.FUNDS: Instrument.InstrumentType.FUND,
    Asset.Subcategory.ETFS: Instrument.InstrumentType.ETF,
    Asset.Subcategory.ROBOADVISOR: Instrument.InstrumentType.FUND,
    Asset.Subcategory.STOCKS: Instrument.InstrumentType.STOCK,
    Asset.Subcategory.PENSION_PLANS: Instrument.InstrumentType.PENSION_PLAN,
    Asset.Subcategory.CRYPTOCURRENCIES: Instrument.InstrumentType.CRYPTO,
    Asset.Subcategory.REAL_ESTATE_CROWD: Instrument.InstrumentType.CROWDFUNDING,
    Asset.Subcategory.CROWDLENDING: Instrument.InstrumentType.CROWDFUNDING,
}

ASSET_CLASS_BY_SUBCATEGORY = {
    Asset.Subcategory.DEPOSITS: Instrument.AssetClass.FIXED_INCOME,
    Asset.Subcategory.STOCKS: Instrument.AssetClass.EQUITY,
    Asset.Subcategory.CRYPTOCURRENCIES: Instrument.AssetClass.CRYPTO,
    Asset.Subcategory.REAL_ESTATE_CROWD: Instrument.AssetClass.REAL_ASSETS,
    Asset.Subcategory.CROWDLENDING: Instrument.AssetClass.FIXED_INCOME,
}


@dataclass(frozen=True)
class BootstrapResult:
    portfolio_id: int
    created_positions: int
    existing_positions: int
    open_issues: int


def classify_tracking_style(asset: Asset) -> str:
    currency = asset.currency.strip().upper()
    if asset.subcategory == Asset.Subcategory.CRYPTOCURRENCIES and currency not in FIAT_CURRENCIES:
        return cast(str, PortfolioPosition.TrackingStyle.UNITS_BASED)
    return cast(str, PortfolioPosition.TrackingStyle.VALUE_BASED)


def _instrument_defaults(asset: Asset) -> dict:
    return {
        "identity_kind": Instrument.IdentityKind.CUSTOM,
        "asset_class": ASSET_CLASS_BY_SUBCATEGORY.get(
            asset.subcategory, Instrument.AssetClass.OTHER
        ),
        "instrument_type": INSTRUMENT_TYPE_BY_SUBCATEGORY.get(
            asset.subcategory, Instrument.InstrumentType.OTHER
        ),
        "is_active": asset.is_active,
    }


def _sync_issue(
    *, portfolio: Portfolio, asset: Asset, code: str, detail: str, is_open: bool
) -> None:
    issue, _ = PortfolioMigrationIssue.objects.get_or_create(
        portfolio=portfolio,
        asset=asset,
        code=code,
        defaults={"detail": detail},
    )
    status = (
        PortfolioMigrationIssue.Status.OPEN if is_open else PortfolioMigrationIssue.Status.RESOLVED
    )
    if issue.status != status or issue.detail != detail:
        issue.status = status
        issue.detail = detail
        issue.save(update_fields=["status", "detail", "updated_at"])


def _resolve_ledger_account(*, portfolio: Portfolio, asset: Asset) -> LedgerAccount | None:
    accounts = list(
        LedgerAccount.objects.filter(
            user=portfolio.user,
            asset=asset,
            account_type=LedgerAccount.AccountType.ASSET,
            currency=asset.currency,
        ).order_by("id")
    )
    if len(accounts) == 1:
        account = accounts[0]
        _sync_issue(
            portfolio=portfolio,
            asset=asset,
            code=cast(str, PortfolioMigrationIssue.Code.LEDGER_ACCOUNT_MISSING),
            detail="No existe una cuenta contable inequívoca para el activo.",
            is_open=False,
        )
        _sync_issue(
            portfolio=portfolio,
            asset=asset,
            code=cast(str, PortfolioMigrationIssue.Code.LEDGER_ACCOUNT_AMBIGUOUS),
            detail="Hay varias cuentas contables compatibles para el activo.",
            is_open=False,
        )
        return account

    code = cast(
        str,
        PortfolioMigrationIssue.Code.LEDGER_ACCOUNT_MISSING
        if not accounts
        else PortfolioMigrationIssue.Code.LEDGER_ACCOUNT_AMBIGUOUS,
    )
    detail = (
        "No existe una cuenta contable inequívoca para el activo."
        if not accounts
        else "Hay varias cuentas contables compatibles para el activo."
    )
    _sync_issue(portfolio=portfolio, asset=asset, code=code, detail=detail, is_open=True)
    other_code = cast(
        str,
        PortfolioMigrationIssue.Code.LEDGER_ACCOUNT_AMBIGUOUS
        if not accounts
        else PortfolioMigrationIssue.Code.LEDGER_ACCOUNT_MISSING,
    )
    _sync_issue(portfolio=portfolio, asset=asset, code=other_code, detail="", is_open=False)
    return None


def _bootstrap_ownership(*, portfolio: Portfolio, position: PortfolioPosition) -> None:
    asset = position.asset
    ownership_link = (
        OwnershipLink.objects.filter(
            user=portfolio.user,
            target_type=OwnershipLink.TargetType.ASSET,
            target_id=asset.id,
        )
        .select_related("ownership__member")
        .prefetch_related("ownership__splits")
        .first()
    )
    if ownership_link is None:
        _sync_issue(
            portfolio=portfolio,
            asset=asset,
            code=cast(str, PortfolioMigrationIssue.Code.OWNERSHIP_MISSING),
            detail="El activo no tiene un OwnershipLink.",
            is_open=True,
        )
        return

    _sync_issue(
        portfolio=portfolio,
        asset=asset,
        code=cast(str, PortfolioMigrationIssue.Code.OWNERSHIP_MISSING),
        detail="El activo no tiene un OwnershipLink.",
        is_open=False,
    )
    ownership = ownership_link.ownership
    period, _ = PositionOwnershipPeriod.objects.get_or_create(
        position=position,
        start_date=position.opened_on,
        defaults={"ownership": ownership},
    )
    if ownership.allocation_basis == Ownership.AllocationBasis.RECURRING_INCOME_12M:
        _sync_issue(
            portfolio=portfolio,
            asset=asset,
            code=cast(str, PortfolioMigrationIssue.Code.OWNERSHIP_DYNAMIC),
            detail="La titularidad dinámica requiere revisión para congelar participaciones históricas.",
            is_open=True,
        )
        return

    _sync_issue(
        portfolio=portfolio,
        asset=asset,
        code=cast(str, PortfolioMigrationIssue.Code.OWNERSHIP_DYNAMIC),
        detail="",
        is_open=False,
    )
    shares: list[tuple[int, Decimal]] = []
    if ownership.kind == Ownership.Kind.INDIVIDUAL and ownership.member_id:
        shares = [(ownership.member_id, Decimal("100"))]
    else:
        shares = [(row.member_id, row.percent) for row in ownership.splits.all()]
    valid_shares = bool(shares) and sum(percent for _, percent in shares) == Decimal("100")
    _sync_issue(
        portfolio=portfolio,
        asset=asset,
        code=cast(str, PortfolioMigrationIssue.Code.OWNERSHIP_SHARES_INVALID),
        detail="Las participaciones explícitas no suman 100%.",
        is_open=not valid_shares,
    )
    if valid_shares:
        for member_id, percent in shares:
            PositionOwnershipShare.objects.get_or_create(
                period=period,
                member_id=member_id,
                defaults={"percent": percent},
            )


@transaction.atomic
def bootstrap_portfolio_for_user(*, user) -> BootstrapResult:
    portfolio, _ = Portfolio.objects.get_or_create(
        user=user,
        defaults={"base_currency": get_base_currency_for_user(user=user)},
    )
    container, _ = InvestmentContainer.objects.get_or_create(
        portfolio=portfolio,
        name="Inversiones legacy",
        defaults={"container_type": InvestmentContainer.ContainerType.PLATFORM},
    )
    created_positions = 0
    existing_positions = 0
    assets = Asset.objects.filter(user=user, category=Asset.Category.INVESTMENTS).order_by("id")
    for asset in assets:
        instrument, _ = Instrument.objects.get_or_create(
            user=user,
            name=asset.name,
            quote_currency=asset.currency,
            defaults=_instrument_defaults(asset),
        )
        ledger_account = _resolve_ledger_account(portfolio=portfolio, asset=asset)
        position, created = PortfolioPosition.objects.get_or_create(
            asset=asset,
            defaults={
                "portfolio": portfolio,
                "container": container,
                "instrument": instrument,
                "ledger_account": ledger_account,
                "tracking_style": classify_tracking_style(asset),
                "status": (
                    PortfolioPosition.Status.ACTIVE
                    if asset.is_active
                    else PortfolioPosition.Status.ARCHIVED
                ),
                "opened_on": asset.start_date,
                "closed_on": None if asset.is_active else asset.updated_at.date(),
            },
        )
        if created:
            created_positions += 1
        else:
            existing_positions += 1
            update_fields: list[str] = []
            if position.ledger_account_id is None and ledger_account is not None:
                position.ledger_account = ledger_account
                update_fields.append("ledger_account")
            expected_status = (
                PortfolioPosition.Status.ACTIVE
                if asset.is_active
                else PortfolioPosition.Status.ARCHIVED
            )
            if position.status != expected_status:
                position.status = expected_status
                update_fields.append("status")
            if update_fields:
                update_fields.append("updated_at")
                position.save(update_fields=update_fields)
        _bootstrap_ownership(portfolio=portfolio, position=position)
        from .market_data import ensure_confirmed_crypto_mapping
        from .valuations import import_legacy_position_valuations

        ensure_confirmed_crypto_mapping(position=position)
        import_legacy_position_valuations(position=position)

    return BootstrapResult(
        portfolio_id=portfolio.id,
        created_positions=created_positions,
        existing_positions=existing_positions,
        open_issues=portfolio.migration_issues.filter(status="open").count(),
    )


def position_coverage(position: PortfolioPosition) -> dict:
    asset = position.asset
    valuation_dates = list(
        AssetValuation.objects.filter(user=asset.user, asset=asset)
        .order_by("valuation_date")
        .values_list("valuation_date", flat=True)
    )
    legacy_flow_dates = list(
        InvestmentAssetEvent.objects.filter(user=asset.user, asset=asset)
        .order_by("event_date")
        .values_list("event_date", flat=True)
    )
    ledger_flow_dates = list(
        LedgerEntry.objects.filter(
            account__user=asset.user,
            account__asset=asset,
            transaction__status=LedgerTransaction.Status.POSTED,
            transaction__quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
        )
        .order_by("transaction__booking_date")
        .values_list("transaction__booking_date", flat=True)
        .distinct()
    )
    flow_dates = legacy_flow_dates + ledger_flow_dates
    has_valuation = bool(valuation_dates) or asset.market_value_override_date is not None
    has_flows = bool(flow_dates)
    if has_valuation and has_flows:
        performance_status = "complete"
    elif has_valuation or has_flows:
        performance_status = "partial"
    else:
        performance_status = "missing"
    performance_dates: list[date] = valuation_dates + flow_dates
    if asset.market_value_override_date:
        performance_dates.append(asset.market_value_override_date)

    if position.tracking_style == PortfolioPosition.TrackingStyle.VALUE_BASED:
        detail_status = "value_only"
    elif position.ledger_account_id and ledger_flow_dates:
        detail_status = "complete"
    elif position.ledger_account_id:
        detail_status = "partial"
    else:
        detail_status = "missing"
    return {
        "performance_coverage": {
            "status": performance_status,
            "start_date": min(performance_dates).isoformat() if performance_dates else None,
            "has_flows": has_flows,
            "has_valuations": has_valuation,
        },
        "position_detail_coverage": {
            "status": detail_status,
            "start_date": (
                min(ledger_flow_dates).isoformat()
                if ledger_flow_dates
                and position.tracking_style == PortfolioPosition.TrackingStyle.UNITS_BASED
                else None
            ),
            "tracking_style": position.tracking_style,
        },
    }


def build_portfolio_readiness(*, user) -> dict:
    investment_assets = Asset.objects.filter(user=user, category=Asset.Category.INVESTMENTS)
    portfolio = Portfolio.objects.filter(user=user).first()
    if portfolio is None:
        return {
            "status": "not_started",
            "asset_count": investment_assets.count(),
            "position_count": 0,
            "covered_asset_count": 0,
            "uncovered_asset_ids": list(investment_assets.values_list("id", flat=True)),
            "open_issue_count": 0,
            "issues": [],
            "positions": [],
        }

    positions = list(
        PortfolioPosition.objects.filter(portfolio=portfolio)
        .select_related("asset", "instrument", "container", "ledger_account")
        .order_by("id")
    )
    positioned_asset_ids = {position.asset_id for position in positions}
    open_issues = list(
        PortfolioMigrationIssue.objects.filter(portfolio=portfolio, status="open")
        .values("id", "asset_id", "code", "detail")
        .order_by("asset_id", "code")
    )
    issue_asset_ids = {int(row["asset_id"]) for row in open_issues}
    all_asset_ids = set(investment_assets.values_list("id", flat=True))
    covered_asset_ids = positioned_asset_ids | issue_asset_ids
    uncovered_asset_ids = sorted(all_asset_ids - covered_asset_ids)
    return {
        "status": "ready" if not uncovered_asset_ids and not open_issues else "needs_review",
        "portfolio_id": portfolio.id,
        "asset_count": len(all_asset_ids),
        "position_count": len(positions),
        "covered_asset_count": len(all_asset_ids & covered_asset_ids),
        "uncovered_asset_ids": uncovered_asset_ids,
        "open_issue_count": len(open_issues),
        "issues": open_issues,
        "positions": [
            {
                "position_id": position.id,
                "asset_id": position.asset_id,
                "asset_name": position.asset.name,
                **position_coverage(position),
            }
            for position in positions
        ],
    }


def validate_ownership_period(
    *, position: PortfolioPosition, start_date: date, end_date: date | None
) -> None:
    periods = PositionOwnershipPeriod.objects.filter(position=position).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=start_date)
    )
    if end_date is not None:
        periods = periods.filter(start_date__lte=end_date)
    if periods.exists():
        raise ValueError("Ya existe un periodo de titularidad que cubre esa fecha.")
