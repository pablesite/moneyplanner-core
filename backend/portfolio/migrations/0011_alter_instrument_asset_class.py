from django.db import migrations, models

# Old value -> new value. Every retired class needs an explicit destination: leaving one
# unmapped would keep a value the field no longer accepts, and the instrument would fail
# validation the next time anything saved it.
#
# `crypto` goes to `safe_haven` by explicit decision of the portfolio owner. Instruments
# that are really trading vehicles (grid bots, automated trading) are expected to be moved
# to `trading` by hand from "Configurar posición": guessing them by name here would be
# fragile and would silently reclassify someone else's portfolio.
FORWARD = {
    "cash": "opportunity_cash",
    "crypto": "safe_haven",
    "real_assets": "real_estate",
    "mixed": "other",
}

# `real_estate` and `safe_haven` both had a single source, so the reverse is unambiguous
# for them; `other` cannot be told apart from an instrument that always was "other", so it
# stays put rather than inventing a `mixed` that may never have existed.
BACKWARD = {
    "opportunity_cash": "cash",
    "safe_haven": "crypto",
    "real_estate": "real_assets",
}


def _remap(apps, mapping):
    Instrument = apps.get_model("portfolio", "Instrument")
    for old_value, new_value in mapping.items():
        Instrument.objects.filter(asset_class=old_value).update(asset_class=new_value)


def forwards(apps, schema_editor):
    _remap(apps, FORWARD)


def backwards(apps, schema_editor):
    _remap(apps, BACKWARD)


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0010_alter_positionvaluation_legacy_ledger_transaction"),
    ]

    operations = [
        migrations.AlterField(
            model_name="instrument",
            name="asset_class",
            field=models.CharField(
                choices=[
                    ("fixed_income", "Renta fija"),
                    ("equity", "Renta variable"),
                    ("real_estate", "Inmobiliario"),
                    ("private_equity", "Capital privado"),
                    ("safe_haven", "Activos refugio"),
                    ("commodities", "Materias primas"),
                    ("alternatives", "Inversiones alternativas"),
                    ("trading", "Trading"),
                    ("opportunity_cash", "Liquidez para oportunidades"),
                    ("other", "Otros"),
                ],
                max_length=24,
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
