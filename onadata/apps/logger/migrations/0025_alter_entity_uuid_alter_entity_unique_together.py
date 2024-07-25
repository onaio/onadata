# Generated by Django 4.2.14 on 2024-09-09 07:16

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('logger', '0024_project_idx_logger_project_deleted_at_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='entity',
            name='uuid',
            field=models.UUIDField(db_index=True, default=uuid.uuid4),
        ),
        migrations.AlterUniqueTogether(
            name='entity',
            unique_together={('entity_list', 'uuid')},
        ),
    ]