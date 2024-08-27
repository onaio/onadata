# Generated by Django 4.2.14 on 2024-08-27 09:10

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('logger', '0023_populate_project_entity_list_perm'),
    ]

    operations = [
        migrations.AlterField(
            model_name='entity',
            name='uuid',
            field=models.UUIDField(db_index=True, default=uuid.uuid4),
        ),
    ]
