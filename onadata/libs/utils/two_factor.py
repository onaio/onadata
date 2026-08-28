"""Recording and notification of two-factor account events.

Shared by the API viewset and the login wizard.
"""

from django.conf import settings
from django.utils.translation import gettext as _

from onadata.libs.utils.cache_tools import (
    safe_cache_add,
    safe_cache_delete,
    safe_cache_incr,
)
from onadata.libs.utils.log import Actions, audit_log

FAILURE_COUNT_CACHE_PREFIX = "two-factor-failures"


def _failure_key(user) -> str:
    return f"{FAILURE_COUNT_CACHE_PREFIX}:{user.pk}"


def notify_owner(user, event, **context):
    """Email the account owner about a change to their second factor.

    A broker outage must not fail the request whose state already committed,
    so an enqueue failure is swallowed rather than raised back to the caller.
    """
    if not user.email:
        return
    # Lazy: the login wizard reaches this module, and the task module imports
    # back into the apps the wizard belongs to.
    # pylint: disable=import-outside-toplevel
    from onadata.apps.api.tasks import send_two_factor_changed_email
    from onadata.libs.utils.email import get_two_factor_email_data

    email_data = get_two_factor_email_data(user.username, event, **context)
    try:
        send_two_factor_changed_email.apply_async(
            args=[
                user.email,
                email_data["message_txt"],
                email_data["subject"],
                email_data.get("message_html"),
            ]
        )
    except Exception:  # pylint: disable=broad-except
        pass


def record_verification_failure(request, user, audit):
    """Audit a failed second-factor check and alert the owner on repetition."""
    audit_log(
        Actions.TWO_FACTOR_VERIFICATION_FAILED,
        user,
        user,
        _("Two-factor verification failed."),
        audit,
        request,
    )
    _alert_on_repeated_failures(user)


def clear_verification_failures(user):
    """Drop the failure run once the user proves a factor, so a later slip
    does not alert on a burst that was already resolved."""
    safe_cache_delete(_failure_key(user))


def _alert_on_repeated_failures(user):
    """One owner email per window once failures reach the threshold.

    The window opens at the first failure: ``add`` sets the expiry only when
    the key is absent, and ``incr`` preserves it. Alerting on the exact
    threshold count keeps it to one email per window however long the run of
    failures continues. Cache access goes through the safe wrappers so a
    missing key or an unreachable backend cannot turn a 403 into a 500.
    """
    threshold = getattr(settings, "TWO_FACTOR_FAILURE_ALERT_THRESHOLD", 10)
    if not threshold:
        return
    window = getattr(settings, "TWO_FACTOR_FAILURE_ALERT_WINDOW", 1800)
    key = _failure_key(user)
    safe_cache_add(key, 0, window)
    if safe_cache_incr(key) == threshold:
        notify_owner(
            user,
            "failed_attempts",
            failure_count=threshold,
            window_minutes=max(1, window // 60),
        )
