from django.db import migrations
from django.utils import timezone


CRYPTO_INSTRUMENTS = {
    "BTC": ("Bitcoin", "bitcoin"),
    "ETH": ("Ethereum", "ethereum"),
}


def import_legacy_valuations_and_crypto_mappings(apps, schema_editor):
    AssetValuation = apps.get_model("net_worth", "AssetValuation")
    Instrument = apps.get_model("portfolio", "Instrument")
    InstrumentProviderMapping = apps.get_model("portfolio", "InstrumentProviderMapping")
    PortfolioPosition = apps.get_model("portfolio", "PortfolioPosition")
    PositionValuation = apps.get_model("portfolio", "PositionValuation")

    positions = PortfolioPosition.objects.select_related("asset", "portfolio").all()
    for position in positions:
        valuations = AssetValuation.objects.filter(
            user_id=position.portfolio.user_id,
            asset_id=position.asset_id,
        ).order_by("valuation_date", "id")
        for valuation in valuations:
            PositionValuation.objects.get_or_create(
                legacy_asset_valuation_id=valuation.id,
                defaults={
                    "position_id": position.id,
                    "valuation_date": valuation.valuation_date,
                    "value": valuation.value,
                    "currency": position.asset.currency,
                    "source": "legacy_asset",
                    "note": "Derivada de AssetValuation; la fuente legacy no se modifica.",
                },
            )

        crypto_identity = CRYPTO_INSTRUMENTS.get(position.asset.currency.upper())
        if position.tracking_style != "units_based" or crypto_identity is None:
            continue
        name, provider_symbol = crypto_identity
        canonical, _ = Instrument.objects.get_or_create(
            identity_kind="canonical",
            ticker=position.asset.currency.upper(),
            market="CRYPTO",
            defaults={
                "user_id": None,
                "name": name,
                "asset_class": "crypto",
                "instrument_type": "crypto",
                "quote_currency": "USD",
                "is_active": True,
            },
        )
        old_instrument_id = position.instrument_id
        if old_instrument_id != canonical.id:
            position.instrument_id = canonical.id
            position.save(update_fields=["instrument_id", "updated_at"])
            if not PortfolioPosition.objects.filter(instrument_id=old_instrument_id).exists():
                Instrument.objects.filter(id=old_instrument_id).update(is_active=False)
        InstrumentProviderMapping.objects.get_or_create(
            instrument_id=canonical.id,
            provider="coingecko",
            quote_currency=position.portfolio.base_currency,
            defaults={
                "provider_symbol": provider_symbol,
                "provider_market": "",
                "is_confirmed": True,
                "confirmed_at": timezone.now(),
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0004_instrumentprovidermapping_instrumentprice_and_more"),
    ]

    operations = [
        migrations.RunPython(
            import_legacy_valuations_and_crypto_mappings,
            migrations.RunPython.noop,
        )
    ]
