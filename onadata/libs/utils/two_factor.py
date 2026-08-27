"""Recording and notification of two-factor account events.

Shared by the API viewset and the login wizard.
"""

from django.utils.translation import gettext as _

from onadata.libs.utils.log import Actions, audit_log


def record_verification_failure(request, user, audit):
    """Audit a failed second-factor check."""
    audit_log(
        Actions.TWO_FACTOR_VERIFICATION_FAILED,
        user,
        user,
        _("Two-factor verification failed."),
        audit,
        request,
    )
