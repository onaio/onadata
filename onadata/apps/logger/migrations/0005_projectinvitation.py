# Generated by Django 3.2.18 on 2023-05-17 10:05

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("logger", "0004_update_instance_geoms"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectInvitation",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("email", models.EmailField(max_length=254)),
                ("role", models.CharField(max_length=100)),
                (
                    "status",
                    models.PositiveSmallIntegerField(
                        choices=[(1, "Pending"), (2, "Accepted"), (3, "Revoked")],
                        default=1,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("resent_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invitations",
                        to="logger.project",
                    ),
                ),
            ],
            options={
                "abstract": False,
                "unique_together": {("email", "project", "status")},
            },
        ),
    ]
