# Generated by Django 2.1.5 on 2019-01-25 10:17

from django.conf import settings
import django.contrib.auth.models
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0003_auto_20180425_0754"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="organizationprofile",
            options={
                "permissions": (
                    ("can_add_project", "Can add a project to an organization"),
                    ("can_add_xform", "Can add/upload an xform to an organization"),
                )
            },
        ),
        migrations.AlterModelOptions(
            name="team",
            options={"permissions": ()},
        ),
        migrations.AlterModelManagers(
            name="team",
            managers=[
                ("objects", django.contrib.auth.models.GroupManager()),
            ],
        ),
        migrations.AlterField(
            model_name="organizationprofile",
            name="creator",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
            ),
        ),
    ]
