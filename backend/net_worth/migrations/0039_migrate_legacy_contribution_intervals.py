from django.db import migrations


def migrate_legacy_intervals(apps, schema_editor):
    Asset = apps.get_model("net_worth", "Asset")
    Interval = apps.get_model("net_worth", "InvestmentContributionInterval")
    for asset in Asset.objects.filter(
        category="investments",
        investment_contribution_mode="periodic_contribution",
        monthly_contribution_amount__isnull=False,
    ).exclude(monthly_contribution_amount=0):
        Interval.objects.create(
            asset=asset,
            start_date=asset.start_date,
            end_date=asset.expected_end_date,
            amount=asset.monthly_contribution_amount,
            frequency=asset.investment_contribution_frequency or "monthly",
            currency=(asset.investment_contribution_currency or None),
        )


class Migration(migrations.Migration):
    dependencies = [
        ("net_worth", "0038_investmentcontributioninterval"),
    ]

    operations = [
        migrations.RunPython(migrate_legacy_intervals, migrations.RunPython.noop),
    ]
