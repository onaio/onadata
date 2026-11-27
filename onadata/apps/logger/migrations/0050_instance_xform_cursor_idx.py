"""Index the submission-time cursor order for each form."""

from django.db import migrations, models

from onadata.apps.logger.migrations._index_utils import ensure_index

INDEX_NAME = "logger_inst_xform_cursor_idx"
INDEX_COLUMNS = ["xform_id", "date_created", "id"]


# pylint: disable=unused-argument
def create_index(apps, schema_editor):
    """Build the cursor index concurrently."""
    with schema_editor.connection.cursor() as cursor:
        ensure_index(cursor, "logger_instance", INDEX_NAME, INDEX_COLUMNS)


# pylint: disable=unused-argument
def drop_index(apps, schema_editor):
    """Drop the index, including any attached partition indexes."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f'DROP INDEX IF EXISTS "{INDEX_NAME}"')


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("logger", "0049_retry_failed_decryptions")]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(create_index, drop_index)],
            state_operations=[
                migrations.AddIndex(
                    model_name="instance",
                    index=models.Index(fields=INDEX_COLUMNS, name=INDEX_NAME),
                )
            ],
        )
    ]
