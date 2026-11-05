"""Simulate a read replica that is behind the primary."""

from contextlib import contextmanager

from django.db import DEFAULT_DB_ALIAS, connections
from django.db.utils import ConnectionDoesNotExist
from django.test.utils import override_settings

from multidb.pinning import pin_this_thread, this_thread_is_pinned, unpin_this_thread

LAGGING_REPLICA_ALIAS = "lagging_replica"


class LaggingReplicaRouter:
    """Routes like the pinning router: reads go to the lagging replica unless the
    thread is pinned to the primary, and writes go to the primary."""

    # pylint: disable=unused-argument

    def db_for_read(self, model, **hints):
        return DEFAULT_DB_ALIAS if this_thread_is_pinned() else LAGGING_REPLICA_ALIAS

    def db_for_write(self, model, **hints):
        return DEFAULT_DB_ALIAS

    def allow_relation(self, obj1, obj2, **hints):
        return True


@contextmanager
def lagging_replica():
    """Route reads to a connection that sees the database as it was on entry.

    The connection holds a REPEATABLE READ snapshot taken when the block starts,
    so writes committed inside the block stay invisible to reads, as they would
    on a replica that hasn't replayed them yet. Reads inside `use_master`, and
    queries that name the primary with `using()`, see current data. The block
    starts unpinned, so a pin leaked by an earlier test can't hide a stale read.

    Needs a TransactionTestCase: inside a TestCase, the snapshot can't see the
    test's uncommitted rows at all. Single thread only: other threads have no
    replica connection. Raises on exit if the snapshot ended early, since reads
    after that saw current data.
    """
    try:
        connections[LAGGING_REPLICA_ALIAS]
    except ConnectionDoesNotExist:
        pass
    else:
        raise RuntimeError("lagging_replica() blocks can't be nested")

    # Kept out of DATABASES because test cases refuse connections to configured
    # aliases they don't declare in `databases`.
    primary = connections[DEFAULT_DB_ALIAS]
    replica = type(primary)({**primary.settings_dict}, LAGGING_REPLICA_ALIAS)
    connections[LAGGING_REPLICA_ALIAS] = replica
    was_pinned = this_thread_is_pinned()
    unpin_this_thread()
    try:
        replica.set_autocommit(False)
        with replica.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            # The transaction's first query takes the snapshot.
            cursor.execute("SELECT 1")

        with override_settings(DATABASE_ROUTERS=[LaggingReplicaRouter()]):
            yield

        if replica.connection is None or replica.get_autocommit():
            raise RuntimeError("The replica's snapshot ended inside the block")
    finally:
        # Closing ends the snapshot's transaction, which would otherwise block
        # the test database flush.
        replica.close()
        del connections[LAGGING_REPLICA_ALIAS]
        if was_pinned:
            pin_this_thread()
