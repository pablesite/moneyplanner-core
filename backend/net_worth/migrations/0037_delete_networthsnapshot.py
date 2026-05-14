from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("net_worth", "0036_liability_payment_start_date"),
    ]

    operations = [
        migrations.DeleteModel(
            name="NetWorthSnapshot",
        ),
    ]
