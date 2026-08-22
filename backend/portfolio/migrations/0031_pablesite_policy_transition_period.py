"""Correct the policy cutover after the pablesite portfolio liquidation.

The March 2022 version was initially treated as the diversified policy, but the
ledger shows that the former funds were still being sold through 2022-06-01.
The cash interval that followed is an explicit tactical policy, not a zero-value
portfolio or a gap in history. The diversified policy starts with its first
purchase on 2022-07-19.
"""

from datetime import date

from django.db import migrations


USERNAME = "pablesite"
MEMBER_NAME = "Pablo"
ORIGINAL_POLICY_DATE = date(2022, 3, 1)
LIQUIDATION_END = date(2022, 6, 1)
LIQUIDITY_FROM = date(2022, 6, 2)
DIVERSIFIED_FROM = date(2022, 7, 19)
LIQUIDITY_TARGET = {
    "asset_class": "cash",
    "target_percent": "100.000",
    "min_percent": "100.000",
    "max_percent": "100.000",
}


def correct_policy_periods(apps, schema_editor):
    User = apps.get_model("auth", "User")
    Ownership = apps.get_model("memberships", "Ownership")
    Portfolio = apps.get_model("portfolio", "Portfolio")
    AllocationStrategy = apps.get_model("portfolio", "AllocationStrategy")
    AllocationTarget = apps.get_model("portfolio", "AllocationTarget")

    user = User.objects.filter(username=USERNAME).first()
    if user is None:
        return
    portfolio = Portfolio.objects.filter(user_id=user.id).first()
    ownership = (
        Ownership.objects.filter(
            user_id=user.id,
            kind="individual",
            member__name__iexact=MEMBER_NAME,
        )
        .order_by("id")
        .first()
    )
    if portfolio is None or ownership is None:
        return

    scope = AllocationStrategy.objects.filter(portfolio_id=portfolio.id, ownership_id=ownership.id)
    historical = (
        scope.filter(effective_from__lt=ORIGINAL_POLICY_DATE)
        .order_by("effective_from", "id")
        .first()
    )
    if historical is not None:
        historical.note = "Política anterior: 65% renta variable y 35% renta fija."
        historical.save(update_fields=["note"])

    diversified = scope.filter(effective_from=ORIGINAL_POLICY_DATE).order_by("id").first()
    if diversified is not None and not scope.filter(effective_from=DIVERSIFIED_FROM).exists():
        diversified.effective_from = DIVERSIFIED_FROM
        diversified.note = "Política diversificada actual."
        diversified.save(update_fields=["effective_from", "note"])

    transition, _ = AllocationStrategy.objects.get_or_create(
        portfolio_id=portfolio.id,
        ownership_id=ownership.id,
        effective_from=LIQUIDITY_FROM,
    )
    transition.note = (
        "Transición de liquidez tras liquidar la cartera anterior; "
        f"ventas completadas el {LIQUIDATION_END.isoformat()}."
    )
    transition.save(update_fields=["note"])
    AllocationTarget.objects.filter(strategy_id=transition.id).delete()
    AllocationTarget.objects.create(strategy_id=transition.id, **LIQUIDITY_TARGET)


class Migration(migrations.Migration):
    dependencies = [("portfolio", "0030_pablesite_historical_allocation_policy")]

    operations = [migrations.RunPython(correct_policy_periods, migrations.RunPython.noop)]
