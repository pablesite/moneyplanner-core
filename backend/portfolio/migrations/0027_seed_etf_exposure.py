"""Exposicion declarada de los tres ETFs tematicos y de factor.

Los pesos vienen de las fichas publicadas en justETF (30/06/2026 para los dos de
iShares, 25/06/2026 para el de L&G). Cada ficha agrupa la cola en un "Other" que no
detalla, asi que aqui se declara solo lo que consta y ese resto queda **sin declarar**:
es exactamente la diferencia entre saber y suponer, y la cobertura de la pantalla lo
dice en vez de dibujar un grafico completo sobre datos incompletos.

- iShares Healthcare Innovation UCITS ETF (IE00BYZK4776)
- iShares MSCI World Small Cap UCITS ETF (IE00BF4RFH31)
- L&G Clean Water UCITS ETF (IE00BK5BC891)
"""

from django.db import migrations

EXPOSICION = {
    "ETF - Healthcare": {
        "ficha": "2026-06-30",
        # EEUU 61,62 · Suiza 5,95 · Reino Unido 4,28 · Japon 4,60 · resto 23,55 sin detallar
        "geography": {"north_america": "61.62", "europe": "10.23", "japan": "4.60"},
        # Un ETF sectorial: casi todo el fondo es una sola linea, que es justo el riesgo.
        "sector": {"health_care": "99.58"},
    },
    "ETF - Small Caps": {
        "ficha": "2026-06-30",
        # EEUU 61,80 + Canada 3,81 · Reino Unido 4,47 · Japon 12,02 · resto 17,90
        "geography": {"north_america": "65.61", "europe": "4.47", "japan": "12.02"},
        # La ficha detalla solo los cuatro mayores; el 35,83 restante no se reparte.
        "sector": {
            "financials": "22.23",
            "technology": "15.81",
            "industrials": "15.66",
            "health_care": "10.47",
        },
    },
    "ETF - Water": {
        "ficha": "2026-06-25",
        # EEUU 57,50 · Reino Unido 10,86 + Suiza 6,19 · Japon 14,28 · resto 11,17
        "geography": {"north_america": "57.50", "europe": "17.05", "japan": "14.28"},
        # No es un sector: es industria y materiales con algo de utilities. Llamarlo
        # "agua" esconde que la apuesta real es industrial.
        "sector": {"industrials": "55.40", "materials": "19.69", "utilities": "14.89"},
    },
}


def seed(apps, schema_editor):
    PortfolioPosition = apps.get_model("portfolio", "PortfolioPosition")
    PositionExposure = apps.get_model("portfolio", "PositionExposure")
    for name, data in EXPOSICION.items():
        position = PortfolioPosition.objects.filter(asset__name=name).first()
        if position is None:
            continue
        for dimension in ("geography", "sector"):
            for bucket, percent in data[dimension].items():
                PositionExposure.objects.update_or_create(
                    position=position,
                    dimension=dimension,
                    bucket=bucket,
                    defaults={"percent": percent, "observed_on": data["ficha"]},
                )


def unseed(apps, schema_editor):
    PortfolioPosition = apps.get_model("portfolio", "PortfolioPosition")
    PositionExposure = apps.get_model("portfolio", "PositionExposure")
    for name, data in EXPOSICION.items():
        position = PortfolioPosition.objects.filter(asset__name=name).first()
        if position is None:
            continue
        PositionExposure.objects.filter(
            position=position,
            dimension__in=("geography", "sector"),
            observed_on=data["ficha"],
        ).delete()


class Migration(migrations.Migration):
    dependencies = [("portfolio", "0026_seed_declared_exposure")]

    operations = [migrations.RunPython(seed, unseed)]
