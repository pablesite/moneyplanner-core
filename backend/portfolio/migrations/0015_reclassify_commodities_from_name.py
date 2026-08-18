from django.db import migrations

# La clase retirada `real_assets` metía en el mismo cajón el inmobiliario y las materias
# primas, y la migración que la deshizo mandó todo a inmobiliario porque no había forma de
# distinguirlos por el tipo de instrumento: un ETF de oro y un ETF de REITs son los dos
# "etf". Lo que sí los distingue es el nombre, así que se rescatan por ahí los que se
# quedaron en inmobiliario o en el cajón de "Otros".
#
# El patrón es deliberadamente estrecho: `gold` y `oro` exigen frontera de palabra a ambos
# lados, de modo que "Goldman" no entra, y solo se tocan las dos clases donde una materia
# prima está claramente fuera de sitio. Nada que ya esté razonablemente clasificado se
# mueve.
COMMODITY_NAME = r"(\ygold\y|\yoro\y|\ycommodit)"
RESCUED_FROM = ["other", "real_estate"]


def forwards(apps, schema_editor):
    apps.get_model("portfolio", "Instrument").objects.filter(
        asset_class__in=RESCUED_FROM, name__iregex=COMMODITY_NAME
    ).update(asset_class="commodities")
    apps.get_model("portfolio", "PortfolioPosition").objects.filter(
        asset_class_override__in=RESCUED_FROM, instrument__name__iregex=COMMODITY_NAME
    ).update(asset_class_override="commodities")


def backwards(apps, schema_editor):
    """No se deshace: no se sabe de cuál de los dos cajones vino cada uno.

    Revertir a ciegas devolvería a inmobiliario un ETF de oro que quizá estaba en "Otros",
    lo que sería peor que dejarlo donde está. La migración anterior sí revierte, y esta
    solo afina dentro de la taxonomía nueva.
    """


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0014_positionclassbreakdown"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
