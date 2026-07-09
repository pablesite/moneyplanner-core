from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [
        ("memberships", "0005_rename_familymember_unique_constraint"),
    ]

    operations = [
        migrations.AddField(
            model_name="familymember",
            name="birth_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="familymember",
            name="employment_income_end_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="familymember",
            name="estimated_monthly_pension_today_eur",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=14,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.AddField(
            model_name="familymember",
            name="other_future_income_today_eur",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=14,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.AddField(
            model_name="familymember",
            name="pension_start_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
