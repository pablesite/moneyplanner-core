from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from core.services import convert_currency_detailed
from net_worth.models import Asset, Liability

from .models import PlanAssetFunction

PRODUCTIVE = "productive"
SECURITY = "security"
SHORT_TERM_GOAL = "short_term_goal"
FAMILY_USE = "family_use"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class ClassifiedAsset:
    asset_id: int
    name: str
    category: str
    subcategory: str
    function: str
    inferred_function: str
    override_function: str | None
    gross_value: Decimal
    associated_liabilities: Decimal
    net_value: Decimal
    currency: str


@dataclass(frozen=True)
class ClassificationSummary:
    assets: list[ClassifiedAsset]
    productive_capital: Decimal
    security_capital: Decimal
    family_use_capital: Decimal
    short_term_goal_capital: Decimal
    unknown_capital: Decimal
    total_assets: Decimal
    total_liabilities: Decimal
    net_worth: Decimal


class AssetClassificationService:
    def infer_function(self, asset: Asset) -> str:
        if asset.category == Asset.Category.INVESTMENTS:
            return PRODUCTIVE
        if asset.category == Asset.Category.CASH:
            return SECURITY
        if asset.category == Asset.Category.REAL_ESTATE:
            if asset.subcategory in {Asset.Subcategory.SECOND_HOME, Asset.Subcategory.RENTAL}:
                return PRODUCTIVE
            if asset.subcategory == Asset.Subcategory.PRIMARY_HOME:
                return FAMILY_USE
        if asset.category in {Asset.Category.VEHICLE, Asset.Category.FURNISHINGS}:
            return FAMILY_USE
        return UNKNOWN

    def summarize(self, *, user, base_currency: str) -> ClassificationSummary:
        assets = list(Asset.objects.filter(user=user, is_active=True).order_by("id"))
        liabilities = list(
            Liability.objects.filter(user=user, is_active=True).select_related("financed_asset")
        )
        overrides = {
            row.asset_id: row.function
            for row in PlanAssetFunction.objects.filter(
                user=user, asset_id__in=[a.id for a in assets]
            )
        }
        liabilities_by_asset: dict[int, Decimal] = {}
        total_liabilities = Decimal("0")
        as_of = timezone.localdate()
        for liability in liabilities:
            liability_value = self._convert(
                Decimal(liability.amount),
                liability.currency,
                base_currency,
                as_of=as_of,
            )
            total_liabilities += liability_value
            if liability.financed_asset_id:
                liabilities_by_asset[liability.financed_asset_id] = (
                    liabilities_by_asset.get(liability.financed_asset_id, Decimal("0"))
                    + liability_value
                )

        rows: list[ClassifiedAsset] = []
        buckets = {
            PRODUCTIVE: Decimal("0"),
            SECURITY: Decimal("0"),
            FAMILY_USE: Decimal("0"),
            SHORT_TERM_GOAL: Decimal("0"),
            UNKNOWN: Decimal("0"),
        }
        total_assets = Decimal("0")
        for asset in assets:
            inferred = self.infer_function(asset)
            override = overrides.get(asset.id)
            function = str(override or inferred)
            gross_value = self._convert(
                Decimal(asset.amount),
                asset.currency,
                base_currency,
                as_of=as_of,
            )
            associated_liabilities = liabilities_by_asset.get(asset.id, Decimal("0"))
            net_value = gross_value - associated_liabilities
            total_assets += gross_value
            buckets[function] = buckets.get(function, Decimal("0")) + net_value
            rows.append(
                ClassifiedAsset(
                    asset_id=asset.id,
                    name=asset.name,
                    category=asset.category,
                    subcategory=asset.subcategory,
                    function=function,
                    inferred_function=inferred,
                    override_function=override,
                    gross_value=gross_value,
                    associated_liabilities=associated_liabilities,
                    net_value=net_value,
                    currency=base_currency,
                )
            )

        return ClassificationSummary(
            assets=rows,
            productive_capital=buckets[PRODUCTIVE],
            security_capital=buckets[SECURITY],
            family_use_capital=buckets[FAMILY_USE],
            short_term_goal_capital=buckets[SHORT_TERM_GOAL],
            unknown_capital=buckets[UNKNOWN],
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            net_worth=total_assets - total_liabilities,
        )

    def _convert(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        *,
        as_of,
    ) -> Decimal:
        try:
            return convert_currency_detailed(
                amount,
                from_currency,
                to_currency,
                on_date=as_of,
                allow_sync=False,
            ).converted
        except ValidationError:
            if (from_currency or "").upper() == (to_currency or "").upper():
                return amount
            raise
