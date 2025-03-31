from django.db import migrations
from django.db.backends.postgresql.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps


def create_username_upper_index(_apps: StateApps, schema_editor: DatabaseSchemaEditor):
    if isinstance(schema_editor, DatabaseSchemaEditor):
        schema_editor.execute(
            "CREATE INDEX IF NOT EXISTS idx_auth_user_username_upper ON auth_user (UPPER(username));"
        )


def remove_username_upper_index(_apps: StateApps, schema_editor: DatabaseSchemaEditor):
    if isinstance(schema_editor, DatabaseSchemaEditor):
        schema_editor.execute("DROP INDEX IF EXISTS idx_auth_user_username_upper;")


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0015_metadata_main_metada_object__363d70_idx"),
    ]

    operations = [
        migrations.RunPython(create_username_upper_index, remove_username_upper_index),
    ]
