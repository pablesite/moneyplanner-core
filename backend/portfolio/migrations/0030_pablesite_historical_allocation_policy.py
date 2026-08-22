"""Backfill the allocation policy history for the production ``pablesite`` portfolio.

The modern diversified policy was already in use on 2022-03-01 but was registered later.
Before that date the portfolio followed a 65/35 equity/fixed-income mandate with explicit
60-70 and 30-40 tolerance bands. This is deliberately a user-scoped data migration: it
must not infer or alter the policy of any other installation.
"""

from datetime import date

from django.db import migrations


USERNAME = "pablesite"
MEMBER_NAME = "Pablo"
CUTOVER_DATE = date(2022, 3, 1)
HISTORICAL_TARGETS = (
    {
        "asset_class": "equity",
        "target_percent": "65.000",
        "min_percent": "60.000",
        "max_percent": "70.000",
    },
    {
        "asset_class": "fixed_income",
        "target_percent": "35.000",
        "min_percent": "30.000",
        "max_percent": "40.000",
    },
)


def seed_policy_history(apps, schema_editor):
    User = apps.get_model("auth", "User")
    Ownership = apps.get_model("memberships", "Ownership")
    Portfolio = apps.get_model("portfolio", "Portfolio")
    PositionValuation = apps.get_model("portfolio", "PositionValuation")
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

    # Only backdate an existing modern policy. A portfolio with no written strategy must
    # not receive one merely because it happens to have the same username.
    modern = (
        AllocationStrategy.objects.filter(
            portfolio_id=portfolio.id,
            ownership_id=ownership.id,
            effective_from__gte=CUTOVER_DATE,
        )
        .order_by("effective_from", "id")
        .first()
    )
    if modern is None:
        return
    if modern.effective_from != CUTOVER_DATE:
        existing_cutover = AllocationStrategy.objects.filter(
            portfolio_id=portfolio.id,
            ownership_id=ownership.id,
            effective_from=CUTOVER_DATE,
        ).first()
        if existing_cutover is None:
            modern.effective_from = CUTOVER_DATE
            modern.save(update_fields=["effective_from"])

    historical_start = (
        PositionValuation.objects.filter(position__portfolio_id=portfolio.id)
        .order_by("valuation_date", "id")
        .values_list("valuation_date", flat=True)
        .first()
    )
    if historical_start is None or historical_start >= CUTOVER_DATE:
        return

    historical, _ = AllocationStrategy.objects.get_or_create(
        portfolio_id=portfolio.id,
        ownership_id=ownership.id,
        effective_from=historical_start,
    )
    AllocationTarget.objects.filter(strategy_id=historical.id).delete()
    AllocationTarget.objects.bulk_create(
        [AllocationTarget(strategy_id=historical.id, **target) for target in HISTORICAL_TARGETS]
    )


class Migration(migrations.Migration):
    dependencies = [("portfolio", "0029_allocationstrategy_benchmark_instrument")]

    operations = [migrations.RunPython(seed_policy_history, migrations.RunPython.noop)]
