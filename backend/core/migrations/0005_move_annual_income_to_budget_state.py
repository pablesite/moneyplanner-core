from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_annualincomeentry"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(
                    name="AnnualIncomeEntry",
                ),
            ],
        ),
    ]
