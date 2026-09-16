# Adds Instance.validation_status and indexes it without blocking writes.
#
# logger_instance is a regular table by default but a partitioned table when
# ENABLE_TABLE_PARTITIONING is on (see 0034-0037). Postgres cannot CREATE INDEX
# CONCURRENTLY on a partitioned parent, so the index is built concurrently per
# partition and attached to a parent index instead.
#
# The index is partial because validation_status is null for every submission
# that was never decrypted, which is the vast majority of the table. The index
# name is the one Django generates for this field; a partial index has to be
# named explicitly because Django rejects a models.Index that sets condition
# without a name.

from django.conf import settings
from django.db import migrations, models

INDEX_NAME = "logger_inst_validat_6ae220_idx"
PREDICATE = '("validation_status") WHERE "validation_status" IS NOT NULL'


def _relkind(cursor, table):
    cursor.execute(
        """
        SELECT c.relkind
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relname = %s
        """,
        [table],
    )
    row = cursor.fetchone()
    return row[0] if row else None


def _child_partitions(cursor, table):
    cursor.execute(
        """
        SELECT c.relname
        FROM pg_inherits h
        JOIN pg_class c ON c.oid = h.inhrelid
        WHERE h.inhparent = %s::regclass
        ORDER BY c.relname
        """,
        [table],
    )
    return [row[0] for row in cursor.fetchall()]


def _is_attached(cursor, parent_index, child_index):
    cursor.execute(
        """
        SELECT 1 FROM pg_inherits
        WHERE inhrelid = %s::regclass AND inhparent = %s::regclass
        """,
        [child_index, parent_index],
    )
    return cursor.fetchone() is not None


def _ensure_index(cursor, table, index_name):
    """Create the partial index on table and, if partitioned, its partitions."""
    if _relkind(cursor, table) == "p":
        cursor.execute(
            f'CREATE INDEX IF NOT EXISTS "{index_name}" ON ONLY "{table}" {PREDICATE}'
        )

        for child in _child_partitions(cursor, table):
            child_index_name = f"{child}_validation_status_idx"[:63]
            _ensure_index(cursor, child, child_index_name)

            if not _is_attached(cursor, index_name, child_index_name):
                cursor.execute(
                    f'ALTER INDEX "{index_name}" ATTACH PARTITION "{child_index_name}"'
                )
    else:
        cursor.execute(
            f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{index_name}" '
            f'ON "{table}" {PREDICATE}'
        )


# pylint: disable=unused-argument
def create_validation_status_index(apps, schema_editor):
    """Create the partial index on validation_status."""
    with schema_editor.connection.cursor() as cursor:
        _ensure_index(cursor, "logger_instance", INDEX_NAME)


# pylint: disable=unused-argument
def drop_validation_status_index(apps, schema_editor):
    """Drop the index, including the partition indexes attached to it."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f'DROP INDEX IF EXISTS "{INDEX_NAME}"')


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("logger", "0045_add_xform_id_date_created_date_modified_last_edited_idx"),
        (
            "taggit",
            "0006_rename_taggeditem_content_type_object_id_taggit_tagg_content_8fc721_idx",
        ),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="instance",
            name="validation_status",
            field=models.CharField(
                choices=[
                    ("valid", "Content matches its signature"),
                    ("not_valid", "Content does not match its signature"),
                    ("not_validated", "No signature to check against"),
                ],
                default=None,
                help_text=(
                    "Outcome of checking a decrypted submission against the "
                    "signature it was submitted with. Null if the submission "
                    "was never decrypted."
                ),
                max_length=20,
                null=True,
            ),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    create_validation_status_index, drop_validation_status_index
                ),
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name="instance",
                    index=models.Index(
                        condition=models.Q(("validation_status__isnull", False)),
                        fields=["validation_status"],
                        name="logger_inst_validat_6ae220_idx",
                    ),
                ),
            ],
        ),
    ]
