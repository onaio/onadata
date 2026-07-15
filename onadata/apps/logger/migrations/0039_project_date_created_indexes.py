# Generated manually to create project list indexes without blocking writes.

from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("logger", "0038_instance_last_edited_by"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        'CREATE INDEX CONCURRENTLY "idx_lproj_notdel_created" '
                        'ON "logger_project" ("date_created" DESC) '
                        'INCLUDE ("id", "organization_id") '
                        'WHERE "deleted_at" IS NULL;'
                    ),
                    reverse_sql=(
                        'DROP INDEX CONCURRENTLY "idx_lproj_notdel_created";'
                    ),
                ),
                migrations.RunSQL(
                    sql=(
                        'CREATE INDEX CONCURRENTLY "idx_lproj_shr_notdel_created" '
                        'ON "logger_project" ("date_created" DESC) '
                        'INCLUDE ("id", "organization_id") '
                        'WHERE "deleted_at" IS NULL AND "shared";'
                    ),
                    reverse_sql=(
                        'DROP INDEX CONCURRENTLY "idx_lproj_shr_notdel_created";'
                    ),
                ),
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name="project",
                    index=models.Index(
                        fields=["-date_created"],
                        name="idx_lproj_notdel_created",
                        include=["id", "organization"],
                        condition=models.Q(deleted_at__isnull=True),
                    ),
                ),
                migrations.AddIndex(
                    model_name="project",
                    index=models.Index(
                        fields=["-date_created"],
                        name="idx_lproj_shr_notdel_created",
                        include=["id", "organization"],
                        condition=models.Q(deleted_at__isnull=True, shared=True),
                    ),
                ),
            ],
        ),
    ]
