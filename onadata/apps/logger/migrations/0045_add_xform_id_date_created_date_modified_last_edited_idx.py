# Generated manually to create instance date indexes without blocking writes.
#
# The partition-aware index helpers live in _index_utils, shared with 0047.

from django.conf import settings
from django.db import migrations, models

from onadata.apps.logger.migrations._index_utils import ensure_index

INDEXES = [
    ("logger_inst_xform_i_3d0789_idx", ["xform_id", "date_created"]),
    ("logger_inst_xform_i_eba640_idx", ["xform_id", "date_modified"]),
    ("logger_inst_xform_i_c024e3_idx", ["xform_id", "last_edited"]),
]


def create_instance_date_indexes(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        for index_name, columns in INDEXES:
            ensure_index(cursor, "logger_instance", index_name, columns)


def drop_instance_date_indexes(apps, schema_editor):
    """Drop the indexes, including any this migration adopted."""
    with schema_editor.connection.cursor() as cursor:
        for index_name, _columns in INDEXES:
            cursor.execute(f'DROP INDEX IF EXISTS "{index_name}"')


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("logger", "0044_xform_unique_active_id_string"),
        (
            "taggit",
            "0006_rename_taggeditem_content_type_object_id_taggit_tagg_content_8fc721_idx",
        ),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    create_instance_date_indexes, drop_instance_date_indexes
                ),
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name="instance",
                    index=models.Index(
                        fields=["xform_id", "date_created"],
                        name="logger_inst_xform_i_3d0789_idx",
                    ),
                ),
                migrations.AddIndex(
                    model_name="instance",
                    index=models.Index(
                        fields=["xform_id", "date_modified"],
                        name="logger_inst_xform_i_eba640_idx",
                    ),
                ),
                migrations.AddIndex(
                    model_name="instance",
                    index=models.Index(
                        fields=["xform_id", "last_edited"],
                        name="logger_inst_xform_i_c024e3_idx",
                    ),
                ),
            ],
        )
    ]
