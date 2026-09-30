# Built without blocking writes; see _index_utils.
#
# MAX(date_created) per user_id, as backfill_user_activity groups it. With no
# index covering both columns Postgres walks the date_created one newest-first
# and never stops for a user with no submissions, reading the whole table.

from django.conf import settings
from django.db import migrations, models

from onadata.apps.logger.migrations._index_utils import ensure_index

INDEX_NAME = "logger_inst_user_id_dc_idx"
INDEX_COLUMNS = ["user_id", "date_created"]


# pylint: disable=unused-argument
def create_instance_user_date_created_index(apps, schema_editor):
    """Build the index, adopting an equivalent one if it already exists."""
    with schema_editor.connection.cursor() as cursor:
        ensure_index(cursor, "logger_instance", INDEX_NAME, INDEX_COLUMNS)


# pylint: disable=unused-argument
def drop_instance_user_date_created_index(apps, schema_editor):
    """Drop the index, including one this migration adopted.

    Not CONCURRENTLY: that form is rejected on a partitioned index.
    """
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f'DROP INDEX IF EXISTS "{INDEX_NAME}"')


class Migration(migrations.Migration):
    # Load-bearing: CONCURRENTLY is rejected inside a transaction, and nothing
    # else keeps the RunPython below in autocommit.
    atomic = False

    dependencies = [
        ("logger", "0046_instance_validation_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    create_instance_user_date_created_index,
                    drop_instance_user_date_created_index,
                ),
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name="instance",
                    index=models.Index(
                        fields=["user", "date_created"],
                        name=INDEX_NAME,
                    ),
                ),
            ],
        )
    ]
