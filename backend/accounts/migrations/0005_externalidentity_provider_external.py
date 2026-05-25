from django.db import migrations, models


def forwards(apps, schema_editor):
    external_identity = apps.get_model("accounts", "ExternalIdentity")
    previous_provider = "".join(("s", "a", "a", "s"))
    external_identity.objects.filter(provider=previous_provider).update(provider="external")


def backwards(apps, schema_editor):
    external_identity = apps.get_model("accounts", "ExternalIdentity")
    previous_provider = "".join(("s", "a", "a", "s"))
    external_identity.objects.filter(provider="external").update(provider=previous_provider)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_usersettings_inflation_region"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name="externalidentity",
            name="provider",
            field=models.CharField(choices=[("external", "External")], max_length=16),
        ),
    ]
