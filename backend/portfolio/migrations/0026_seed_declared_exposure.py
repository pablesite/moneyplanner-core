"""Exposicion declarada de los productos de renta variable, desde sus fichas.

Los pesos salen del X-Ray de Morningstar de 20/08/2026 para el roboadvisor y el plan de
pensiones. Son datos del usuario, no del producto, asi que van como migracion de datos y
no como fixture: es la unica forma de que lleguen a produccion sin teclearlos a mano uno
a uno.

Se declara **solo lo que consta en la ficha**. Los tres ETFs entran con su vehiculo, que
es seguro, y sin geografia ni sector, que no consta aqui: inventarlos ensuciaria justo el
analisis para el que existe esta pantalla. La cobertura lo dira.

Los porcentajes de Morningstar son sobre la parte de renta variable, y estas posiciones no
son 100% renta variable, asi que se escalan por su peso en acciones. Lo que queda sin
declarar es efectivo y sin clasificar del propio producto.
"""

from django.db import migrations

FICHA = "2026-08-20"

# nombre del activo -> {dimension: {bucket: porcentaje de la posicion}}
EXPOSICION = {
    "Roboadvisor - Cartera Metal": {
        "geography": {
            "north_america": "58.07",
            "japan": "12.50",
            "emerging": "14.61",
            "europe": "10.85",
            "asia_pacific": "2.04",
            "other": "0.04",
        },
        "sector": {
            "technology": "30.54",
            "financials": "16.19",
            "industrials": "10.77",
            "consumer_discretionary": "9.04",
            "communication": "8.21",
            "health_care": "7.97",
            "consumer_staples": "4.04",
            "materials": "3.28",
            "energy": "2.94",
            "utilities": "2.11",
            "real_estate_sector": "1.76",
        },
        "vehicle": {"index_fund": "97.58"},
    },
    "Plan Pensiones - MyInv. Indexado Global (MSCI)": {
        "geography": {
            "north_america": "62.53",
            "europe": "14.29",
            "emerging": "12.07",
            "japan": "4.64",
            "other": "2.97",
            "asia_pacific": "1.65",
        },
        "sector": {
            "technology": "30.81",
            "financials": "15.37",
            "industrials": "10.25",
            "consumer_discretionary": "8.33",
            "communication": "7.46",
            "health_care": "7.83",
            "consumer_staples": "4.40",
            "energy": "3.39",
            "materials": "3.21",
            "utilities": "2.35",
            "real_estate_sector": "1.65",
        },
        "vehicle": {"pension_plan": "100.00"},
    },
    # Los ETFs entran solo con el vehiculo: su geografia y su sector no constan en las
    # fichas aportadas, y el sitio de un dato que no se tiene es vacio, no inventado.
    "ETF - Healthcare": {"vehicle": {"etf": "100.00"}},
    "ETF - Water": {"vehicle": {"etf": "100.00"}},
    "ETF - Small Caps": {"vehicle": {"etf": "100.00"}},
}


def seed(apps, schema_editor):
    PortfolioPosition = apps.get_model("portfolio", "PortfolioPosition")
    PositionExposure = apps.get_model("portfolio", "PositionExposure")
    for name, dimensions in EXPOSICION.items():
        position = PortfolioPosition.objects.filter(asset__name=name).first()
        if position is None:
            continue
        for dimension, weights in dimensions.items():
            for bucket, percent in weights.items():
                # `update_or_create` para que reaplicarla no duplique ni pise a mano lo
                # que el usuario haya corregido despues... salvo el propio valor, que es
                # lo que esta migracion declara.
                PositionExposure.objects.update_or_create(
                    position=position,
                    dimension=dimension,
                    bucket=bucket,
                    defaults={"percent": percent, "observed_on": FICHA},
                )


def unseed(apps, schema_editor):
    PortfolioPosition = apps.get_model("portfolio", "PortfolioPosition")
    PositionExposure = apps.get_model("portfolio", "PositionExposure")
    for name, dimensions in EXPOSICION.items():
        position = PortfolioPosition.objects.filter(asset__name=name).first()
        if position is None:
            continue
        PositionExposure.objects.filter(
            position=position, dimension__in=list(dimensions), observed_on=FICHA
        ).delete()


class Migration(migrations.Migration):
    dependencies = [("portfolio", "0025_positionexposure")]

    operations = [migrations.RunPython(seed, unseed)]
