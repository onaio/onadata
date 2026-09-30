"""Build plain btree indexes without blocking writes.

Postgres cannot CREATE INDEX CONCURRENTLY on a partitioned parent (see
0034-0037), so on one the index is built per partition and attached instead.

An index already covering the columns is adopted by renaming rather than
rebuilt, and is therefore dropped when the adopting migration reverses.

Partial, unique and expression indexes are out of scope; is_compatible rejects
them, so 0046 keeps its own copy of this.

The leading underscore keeps the migration loader from loading this as a
migration.
"""


def is_compatible(definition, columns):
    """Check a pg_get_indexdef definition is a plain btree index on columns.

    Anything else the planner cannot use the same way - a unique index, another
    access method, an expression, INCLUDE columns, a partial index, a
    non-default operator class or sort order - renders a different definition.
    """
    return definition.startswith("CREATE INDEX ") and definition.endswith(
        f" USING btree ({', '.join(columns)})"
    )


def relkind(cursor, table):
    """Return the pg_class relkind for table, or None when it is absent."""
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


def compatible_index(cursor, table, columns, preferred=None):
    """Return the name of a valid index on table usable for columns.

    ``preferred`` is returned when it is among the matches. Without that, a
    re-run beside a hand-made index on the same columns picks whichever sorts
    first and tries to rename it onto a name already taken.
    """
    cursor.execute(
        """
        SELECT c.relname, pg_get_indexdef(i.indexrelid)
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indexrelid
        JOIN pg_class t ON t.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'public' AND t.relname = %s AND i.indisvalid
        ORDER BY (c.relname <> %s), c.relname
        """,
        [table, preferred or ""],
    )
    for name, definition in cursor.fetchall():
        if is_compatible(definition, columns):
            return name

    return None


def claim_index_name(cursor, table, index_name, columns):
    """Make index_name usable, dropping an index left by an interrupted build.

    CREATE INDEX ... IF NOT EXISTS skips any relation of that name without
    comparing its definition, so a leftover from a cancelled concurrent build
    would be kept and the migration would report success without a usable
    index. A partitioned index is instead invalid until every partition is
    attached, which is the state a resumed run continues from.
    """
    cursor.execute(
        """
        SELECT c.relkind, i.indisvalid, t.relname, pg_get_indexdef(i.indexrelid)
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_index i ON i.indexrelid = c.oid
        LEFT JOIN pg_class t ON t.oid = i.indrelid
        WHERE n.nspname = 'public' AND c.relname = %s
        """,
        [index_name],
    )
    row = cursor.fetchone()

    if row is None:
        return

    index_relkind, is_valid, index_table, definition = row

    if index_table == table:
        if index_relkind == "I" and is_compatible(definition, columns):
            return

        if index_relkind == "i":
            if is_valid and is_compatible(definition, columns):
                return

            if not is_valid:
                cursor.execute(f'DROP INDEX CONCURRENTLY "{index_name}"')
                return

    raise RuntimeError(
        f'Cannot create index "{index_name}" on "{table}": the name is already '
        "taken by another relation. Drop or rename it, then run this migration "
        "again."
    )


def child_partitions(cursor, table):
    """Return the names of table's direct partitions."""
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


def is_attached(cursor, parent_index, child_index):
    """Check child_index is already attached to parent_index."""
    cursor.execute(
        """
        SELECT 1 FROM pg_inherits
        WHERE inhrelid = %s::regclass AND inhparent = %s::regclass
        """,
        [child_index, parent_index],
    )
    return cursor.fetchone() is not None


def ensure_index(cursor, table, index_name, columns):
    """Create an index named index_name on table and each of its partitions."""
    claim_index_name(cursor, table, index_name, columns)

    existing = compatible_index(cursor, table, columns, preferred=index_name)

    if existing == index_name:
        return

    if existing:
        cursor.execute(f'ALTER INDEX "{existing}" RENAME TO "{index_name}"')
        return

    columns_sql = ", ".join(f'"{column}"' for column in columns)

    if relkind(cursor, table) == "p":
        cursor.execute(
            f'CREATE INDEX IF NOT EXISTS "{index_name}" '
            f'ON ONLY "{table}" ({columns_sql})'
        )
        for child in child_partitions(cursor, table):
            # ensure_index leaves the child's index under exactly this name,
            # whether it built it or adopted one.
            child_index_name = f"{child}_{'_'.join(columns)}_idx"[:63]
            ensure_index(cursor, child, child_index_name, columns)
            if not is_attached(cursor, index_name, child_index_name):
                cursor.execute(
                    f'ALTER INDEX "{index_name}" ATTACH PARTITION "{child_index_name}"'
                )
    else:
        cursor.execute(
            f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{index_name}" '
            f'ON "{table}" ({columns_sql})'
        )
