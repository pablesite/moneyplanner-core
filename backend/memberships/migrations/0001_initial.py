from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FamilyMember",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=80)),
                (
                    "role",
                    models.CharField(
                        choices=[("adult", "Adulto"), ("child", "Nino")],
                        default="adult",
                        max_length=16,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="family_members",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["role", "name"],
                "indexes": [
                    models.Index(
                        fields=["user", "is_active"], name="memberships_f_user_id_8b8f60_idx"
                    ),
                    models.Index(fields=["user", "role"], name="memberships_f_user_id_d6f6b6_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "name"), name="uniq_member_name_per_user"
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="Ownership",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[("individual", "Individual"), ("shared", "Compartido")],
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "member",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="individual_ownerships",
                        to="memberships.familymember",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ownerships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["user", "kind"], name="memberships_o_user_id_2f3efb_idx"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=Q(
                            ("kind", "individual"), ("member__isnull", False), _connector="OR"
                        )
                        | Q(("kind", "shared"), ("member__isnull", True), _connector="OR"),
                        name="ownership_individual_requires_member",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="OwnershipSplit",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "percent",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=5,
                        validators=[MinValueValidator(0), MaxValueValidator(100)],
                    ),
                ),
                (
                    "member",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ownership_splits",
                        to="memberships.familymember",
                    ),
                ),
                (
                    "ownership",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="splits",
                        to="memberships.ownership",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("ownership", "member"), name="uniq_split_member_per_ownership"
                    ),
                ],
            },
        ),
    ]
