# Generated manually to create instance date indexes without blocking writes.
#
# logger_instance is a regular table by default but a partitioned table when
# ENABLE_TABLE_PARTITIONING is on (see 0034-0037). Postgres cannot CREATE INDEX
# CONCURRENTLY on a partitioned parent, so each index is built concurrently per
# partition and attached to a parent index instead. Tables that already have an
# equivalent index on the same columns (e.g. created by 0034) are skipped.

from django.conf import settings
from django.db import migrations, models

INDEXES = [
    ("logger_inst_xform_i_3d0789_idx", ["xform_id", "date_created"]),
    ("logger_inst_xform_i_eba640_idx", ["xform_id", "date_modified"]),
    ("logger_inst_xform_i_c024e3_idx", ["xform_id", "last_edited"]),
]


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


def _index_on_columns(cursor, table, columns):
    """Return the name of a valid index on table covering exactly columns."""
    cursor.execute(
        """
        SELECT c.relname
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indexrelid
        JOIN pg_class t ON t.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'public' AND t.relname = %s
          AND i.indisvalid AND i.indpred IS NULL
          AND (
            SELECT array_agg(a.attname ORDER BY k.ord)
            FROM unnest(i.indkey::int2[]) WITH ORDINALITY AS k(attnum, ord)
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.attnum
          ) = %s::name[]
        LIMIT 1
        """,
        [table, columns],
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


def _ensure_index(cursor, table, index_name, columns):
    """Create an index on table and its partitions; return the index name.

    Reuses an existing index when one already covers columns.
    """
    existing = _index_on_columns(cursor, table, columns)
    if existing:
        return existing

    columns_sql = ", ".join(f'"{column}"' for column in columns)

    if _relkind(cursor, table) == "p":
        cursor.execute(
            f'CREATE INDEX IF NOT EXISTS "{index_name}" '
            f'ON ONLY "{table}" ({columns_sql})'
        )
        for child in _child_partitions(cursor, table):
            child_index_name = f"{child}_{'_'.join(columns)}_idx"[:63]
            child_index = _ensure_index(cursor, child, child_index_name, columns)
            if not _is_attached(cursor, index_name, child_index):
                cursor.execute(
                    f'ALTER INDEX "{index_name}" ATTACH PARTITION "{child_index}"'
                )
    else:
        cursor.execute(
            f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{index_name}" '
            f'ON "{table}" ({columns_sql})'
        )

    return index_name


def create_instance_date_indexes(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        for index_name, columns in INDEXES:
            _ensure_index(cursor, "logger_instance", index_name, columns)


def drop_instance_date_indexes(apps, schema_editor):
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
