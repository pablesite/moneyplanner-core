from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("net_worth", "0008_liability_financed_asset"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="ownership",
            name="notes",
        ),
    ]
