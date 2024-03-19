# Generated by Django 3.2.23 on 2024-03-19 07:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("logger", "0015_auto_20240205_0315"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="entitylist",
            name="metadata",
        ),
        migrations.AddField(
            model_name="entitylist",
            name="last_entity_update_time",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="entitylist",
            name="num_entities",
            field=models.IntegerField(default=0),
        ),
    ]
