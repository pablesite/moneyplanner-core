from decimal import Decimal

from django.db import migrations


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

INSTRUMENT_TYPES = {
    "deposits": ("fixed_income", "deposit"),
    "funds": ("other", "fund"),
    "etfs": ("other", "etf"),
    "roboadvisor": ("other", "fund"),
    "stocks": ("equity", "stock"),
    "pension_plans": ("other", "pension_plan"),
    "cryptocurrencies": ("crypto", "crypto"),
    "real_estate_crowd": ("real_assets", "crowdfunding"),
    "crowdlending": ("fixed_income", "crowdfunding"),
}


def bootstrap_existing_investments(apps, schema_editor):
    Asset = apps.get_model("net_worth", "Asset")
    Instrument = apps.get_model("portfolio", "Instrument")
    InvestmentContainer = apps.get_model("portfolio", "InvestmentContainer")
    LedgerAccount = apps.get_model("accounting", "LedgerAccount")
    OwnershipLink = apps.get_model("memberships", "OwnershipLink")
    Portfolio = apps.get_model("portfolio", "Portfolio")
    PortfolioMigrationIssue = apps.get_model("portfolio", "PortfolioMigrationIssue")
    PortfolioPosition = apps.get_model("portfolio", "PortfolioPosition")
    PositionOwnershipPeriod = apps.get_model("portfolio", "PositionOwnershipPeriod")
    PositionOwnershipShare = apps.get_model("portfolio", "PositionOwnershipShare")
    UserSettings = apps.get_model("accounts", "UserSettings")

    user_ids = Asset.objects.filter(category="investments").values_list("user_id", flat=True)
    for user_id in sorted(set(user_ids)):
        settings = UserSettings.objects.filter(user_id=user_id).first()
        base_currency = (settings.base_currency if settings else "EUR").strip().upper()
        portfolio, _ = Portfolio.objects.get_or_create(
            user_id=user_id,
            defaults={"base_currency": base_currency},
        )
        container, _ = InvestmentContainer.objects.get_or_create(
            portfolio=portfolio,
            name="Inversiones legacy",
            defaults={"container_type": "platform"},
        )
        assets = Asset.objects.filter(user_id=user_id, category="investments").order_by("id")
        for asset in assets:
            asset_class, instrument_type = INSTRUMENT_TYPES.get(
                asset.subcategory, ("other", "other")
            )
            instrument, _ = Instrument.objects.get_or_create(
                user_id=user_id,
                name=asset.name,
                quote_currency=asset.currency,
                defaults={
                    "identity_kind": "custom",
                    "asset_class": asset_class,
                    "instrument_type": instrument_type,
                    "is_active": asset.is_active,
                },
            )
            accounts = list(
                LedgerAccount.objects.filter(
                    user_id=user_id,
                    asset_id=asset.id,
                    account_type="asset",
                    currency=asset.currency,
                ).order_by("id")
            )
            ledger_account = accounts[0] if len(accounts) == 1 else None
            if len(accounts) != 1:
                code = "ledger_account_missing" if not accounts else "ledger_account_ambiguous"
                PortfolioMigrationIssue.objects.get_or_create(
                    portfolio=portfolio,
                    asset=asset,
                    code=code,
                    defaults={
                        "detail": (
                            "No existe una cuenta contable inequívoca para el activo."
                            if not accounts
                            else "Hay varias cuentas contables compatibles para el activo."
                        )
                    },
                )
            currency = asset.currency.strip().upper()
            tracking_style = (
                "units_based"
                if asset.subcategory == "cryptocurrencies" and currency not in FIAT_CURRENCIES
                else "value_based"
            )
            position, _ = PortfolioPosition.objects.get_or_create(
                asset=asset,
                defaults={
                    "portfolio": portfolio,
                    "container": container,
                    "instrument": instrument,
                    "ledger_account": ledger_account,
                    "tracking_style": tracking_style,
                    "status": "active" if asset.is_active else "archived",
                    "opened_on": asset.start_date,
                    "closed_on": None if asset.is_active else asset.updated_at.date(),
                },
            )
            link = OwnershipLink.objects.filter(
                user_id=user_id,
                target_type="asset",
                target_id=asset.id,
            ).first()
            if link is None:
                PortfolioMigrationIssue.objects.get_or_create(
                    portfolio=portfolio,
                    asset=asset,
                    code="ownership_missing",
                    defaults={"detail": "El activo no tiene un OwnershipLink."},
                )
                continue
            ownership = link.ownership
            period, _ = PositionOwnershipPeriod.objects.get_or_create(
                position=position,
                start_date=position.opened_on,
                defaults={"ownership": ownership},
            )
            if ownership.allocation_basis == "recurring_income_12m":
                PortfolioMigrationIssue.objects.get_or_create(
                    portfolio=portfolio,
                    asset=asset,
                    code="ownership_dynamic",
                    defaults={
                        "detail": (
                            "La titularidad dinámica requiere revisión para congelar "
                            "participaciones históricas."
                        )
                    },
                )
                continue
            if ownership.kind == "individual" and ownership.member_id:
                shares = [(ownership.member_id, Decimal("100"))]
            else:
                shares = list(ownership.splits.values_list("member_id", "percent"))
            if not shares or sum(percent for _, percent in shares) != Decimal("100"):
                PortfolioMigrationIssue.objects.get_or_create(
                    portfolio=portfolio,
                    asset=asset,
                    code="ownership_shares_invalid",
                    defaults={"detail": "Las participaciones explícitas no suman 100%."},
                )
                continue
            for member_id, percent in shares:
                PositionOwnershipShare.objects.get_or_create(
                    period=period,
                    member_id=member_id,
                    defaults={"percent": percent},
                )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_externalidentity_provider_external"),
        ("portfolio", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(bootstrap_existing_investments, migrations.RunPython.noop),
    ]
