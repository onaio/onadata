"""Simulate a hot standby replica cancelling a query in a recovery conflict."""

from django.db import OperationalError


def recovery_conflict():
    """Build the error a PostgreSQL hot standby raises when it cancels a query."""
    return OperationalError(
        "canceling statement due to conflict with recovery\n"
        "DETAIL:  User query might have needed to see row versions that must be "
        "removed.\n"
    )


def conflicting_rows(*args, **kwargs):  # pylint: disable=unused-argument
    """Rows whose query a hot standby cancels on the first fetch."""
    raise recovery_conflict()
    yield  # pylint: disable=unreachable
