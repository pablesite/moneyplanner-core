from django.db import migrations, models


def migrate_vehicle_to_furnishings(apps, schema_editor):
    Asset = apps.get_model("net_worth", "Asset")

    # set default subcategory for all existing assets
    Asset.objects.filter(subcategory__isnull=True).update(subcategory="other")

    # migrate old vehicle category into furnishings/vehicles
    Asset.objects.filter(category="vehicle").update(category="furnishings", subcategory="vehicles")


class Migration(migrations.Migration):
    dependencies = [
        ("net_worth", "0010_alter_asset_amount_allow_negative"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="subcategory",
            field=models.CharField(
                choices=[
                    ("bank_account", "Cuenta bancaria"),
                    ("wallet", "Monedero"),
                    ("crypto_spot_earn", "Spot/Earn Cripto"),
                    ("deposits", "Depósitos"),
                    ("funds", "Fondos"),
                    ("etfs", "ETFs"),
                    ("roboadvisor", "Roboadvisor"),
                    ("stocks", "Stocks"),
                    ("pension_plans", "Planes de pensiones"),
                    ("cryptocurrencies", "Criptomonedas"),
                    ("real_estate_crowd", "Crowdfunding Inmobiliario"),
                    ("crowdlending", "Crowdlending"),
                    ("primary_home", "Vivienda habitual"),
                    ("second_home", "Segunda vivienda"),
                    ("rental", "Rentas"),
                    ("vehicles", "Vehículos"),
                    ("technology", "Tecnología"),
                    ("home_furnishings", "Muebles vivienda"),
                    ("sports_equipment", "Equipamiento deportivo"),
                    ("jewelry", "Joyería"),
                    ("other", "Otros"),
                ],
                default="other",
                max_length=48,
            ),
        ),
        migrations.RunPython(migrate_vehicle_to_furnishings, reverse_code=migrations.RunPython.noop),
    ]
