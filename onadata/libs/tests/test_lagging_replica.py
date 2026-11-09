"""Tests for onadata.libs.test_utils.lagging_replica"""

from django.db import connections
from django.test import TransactionTestCase

from onadata.libs.test_utils.lagging_replica import (
    LAGGING_REPLICA_ALIAS,
    lagging_replica,
)


class LaggingReplicaTestCase(TransactionTestCase):
    """Tests for lagging_replica()"""

    def test_dropped_snapshot_raises(self):
        """A block whose snapshot ended early raises instead of passing"""
        with self.assertRaisesMessage(RuntimeError, "snapshot ended"):
            with lagging_replica():
                connections[LAGGING_REPLICA_ALIAS].close_if_unusable_or_obsolete()
