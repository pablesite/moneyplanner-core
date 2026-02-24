from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("net_worth", "0017_liability_principal_amount"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="liability",
            name="monthly_payment_amount",
        ),
    ]
