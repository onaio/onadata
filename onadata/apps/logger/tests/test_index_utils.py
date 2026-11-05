# -*- coding: utf-8 -*-
"""
Test the index helpers shared by the index-building migrations.
"""

from django.db import connection
from django.test import TransactionTestCase

from onadata.apps.logger.migrations._index_utils import ensure_index

TABLE = "index_utils_probe"
PARENT = "index_utils_partitioned_probe"
TARGET = "probe_target_idx"
COLUMNS = ["user_id", "date_created"]


class EnsureIndexTestCase(TransactionTestCase):
    """Build indexes on a throwaway plain table."""

    def setUp(self):
        super().setUp()
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE TABLE {TABLE} "
                "(user_id integer, date_created timestamptz, note text)"
            )

    def tearDown(self):
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {TABLE} CASCADE")
        super().tearDown()

    def _index_names(self, cursor):
        cursor.execute(
            "SELECT indexname FROM pg_indexes WHERE tablename = %s ORDER BY indexname",
            [TABLE],
        )
        return [row[0] for row in cursor.fetchall()]

    def test_creates_the_index_when_none_exists(self):
        with connection.cursor() as cursor:
            ensure_index(cursor, TABLE, TARGET, COLUMNS)

            self.assertEqual(self._index_names(cursor), [TARGET])

    def test_adopts_an_equivalent_index_under_another_name(self):
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE INDEX probe_manual ON {TABLE} (user_id, date_created)"
            )

            ensure_index(cursor, TABLE, TARGET, COLUMNS)

            self.assertEqual(self._index_names(cursor), [TARGET])

    def test_re_running_beside_a_duplicate_that_sorts_first_is_a_no_op(self):
        """Renaming a duplicate onto the taken name used to abort the migration."""
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE INDEX {TARGET} ON {TABLE} (user_id, date_created)")
            cursor.execute(f"CREATE INDEX probe_aaa ON {TABLE} (user_id, date_created)")

            ensure_index(cursor, TABLE, TARGET, COLUMNS)

            self.assertEqual(self._index_names(cursor), ["probe_aaa", TARGET])

    def test_does_not_adopt_an_index_on_other_columns(self):
        """A prefix of the wanted columns is not an equivalent either."""
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE INDEX probe_other ON {TABLE} (note)")
            cursor.execute(f"CREATE INDEX probe_prefix ON {TABLE} (user_id)")

            ensure_index(cursor, TABLE, TARGET, COLUMNS)

            self.assertEqual(
                self._index_names(cursor), ["probe_other", "probe_prefix", TARGET]
            )


class EnsureIndexPartitionedTestCase(TransactionTestCase):
    """ENABLE_TABLE_PARTITIONING is off wherever the suite runs, so build one here."""

    def setUp(self):
        super().setUp()
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE TABLE {PARENT} "
                "(user_id integer, date_created timestamptz, xform_id integer) "
                "PARTITION BY LIST (xform_id)"
            )
            for value in (1, 2):
                cursor.execute(
                    f"CREATE TABLE {PARENT}_p_{value} PARTITION OF {PARENT} "
                    f"FOR VALUES IN ({value})"
                )

    def tearDown(self):
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {PARENT} CASCADE")
        super().tearDown()

    def _parent_index_valid(self, cursor):
        cursor.execute(
            """
            SELECT i.indisvalid
            FROM pg_index i
            JOIN pg_class c ON c.oid = i.indexrelid
            WHERE c.relname = %s
            """,
            [TARGET],
        )
        row = cursor.fetchone()
        return row is not None and row[0]

    def _attached(self, cursor):
        cursor.execute(
            "SELECT count(*) FROM pg_inherits WHERE inhparent = %s::regclass", [TARGET]
        )
        return cursor.fetchone()[0]

    def test_builds_and_attaches_an_index_on_every_partition(self):
        """The parent index goes valid only once every partition is attached."""
        with connection.cursor() as cursor:
            ensure_index(cursor, PARENT, TARGET, COLUMNS)

            self.assertTrue(self._parent_index_valid(cursor))
            self.assertEqual(self._attached(cursor), 2)

    def test_re_running_is_a_no_op_and_covers_a_new_partition(self):
        with connection.cursor() as cursor:
            ensure_index(cursor, PARENT, TARGET, COLUMNS)
            ensure_index(cursor, PARENT, TARGET, COLUMNS)

            self.assertEqual(self._attached(cursor), 2)

            cursor.execute(
                f"CREATE TABLE {PARENT}_p_3 PARTITION OF {PARENT} FOR VALUES IN (3)"
            )
            ensure_index(cursor, PARENT, TARGET, COLUMNS)

            self.assertTrue(self._parent_index_valid(cursor))
            self.assertEqual(self._attached(cursor), 3)
