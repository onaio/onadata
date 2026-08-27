"""Recording and notification of two-factor account events.

Shared by the API viewset and the login wizard, so both doors onto the second
factor report through one funnel.
"""

from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext as _

from onadata.libs.utils.log import Actions, audit_log

FAILURE_COUNT_CACHE_PREFIX = "two-factor-failures"


def notify_owner(user, event, **context):
    """Email the account owner about a change to their second factor.

    Whoever made the change -- owner or intruder -- the owner finds out.
    Skipped when the account has no address to reach.
    """
    if not user.email:
        return
    # Lazy: the login wizard reaches this module, and the task module imports
    # back into the apps the wizard belongs to.
    # pylint: disable=import-outside-toplevel
    from onadata.apps.api.tasks import send_two_factor_changed_email
    from onadata.libs.utils.email import get_two_factor_email_data

    email_data = get_two_factor_email_data(user.username, event, **context)
    send_two_factor_changed_email.apply_async(
        args=[user.email, email_data["message_txt"], email_data["subject"]]
    )


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


def _alert_on_repeated_failures(user):
    """One owner email per window once failures reach the threshold.

    The window opens at the first failure: ``cache.add`` sets the expiry only
    when the key is absent, and ``incr`` preserves it. Alerting on the exact
    threshold count keeps it to one email per window however long the run of
    failures continues.
    """
    threshold = getattr(settings, "TWO_FACTOR_FAILURE_ALERT_THRESHOLD", 10)
    if not threshold:
        return
    window = getattr(settings, "TWO_FACTOR_FAILURE_ALERT_WINDOW", 1800)
    key = f"{FAILURE_COUNT_CACHE_PREFIX}:{user.pk}"
    cache.add(key, 0, window)
    if cache.incr(key) == threshold:
        notify_owner(
            user,
            "failed_attempts",
            failure_count=threshold,
            window_minutes=max(1, window // 60),
        )
