from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ExternalIdentity",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("provider", models.CharField(choices=[("external", "External")], max_length=16)),
                ("external_user_id", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="external_identities",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["provider", "external_user_id"],
                        name="accounts_ex_provider_22f7f7_idx",
                    ),
                    models.Index(
                        fields=["user", "provider"], name="accounts_ex_user_id_8c3e28_idx"
                    ),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="externalidentity",
            constraint=models.UniqueConstraint(
                fields=("provider", "external_user_id"),
                name="accounts_ext_identity_provider_userid_uniq",
            ),
        ),
    ]
