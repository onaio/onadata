from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0009_two_factor_encrypted_devices"),
    ]

    operations = [
        migrations.AddField(
            model_name="organizationprofile",
            name="two_factor_required_actions",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
