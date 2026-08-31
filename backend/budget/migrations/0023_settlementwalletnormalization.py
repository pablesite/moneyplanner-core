import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "0013_ledgertransaction_fee_for"),
        ("budget", "0022_link_shared_dynamic_ownership"),
    ]

    operations = [
        migrations.CreateModel(
            name="SettlementWalletNormalization",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wallet_normalizations",
                        to="budget.settlementprofile",
                    ),
                ),
                (
                    "transaction",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="settlement_wallet_normalization",
                        to="accounting.ledgertransaction",
                    ),
                ),
            ],
            options={
                "db_table": "budget_settlement_wallet_normalization",
                "ordering": ["transaction__booking_date", "transaction_id"],
            },
        ),
    ]
