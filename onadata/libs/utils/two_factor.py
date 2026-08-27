"""Recording and notification of two-factor account events.

Shared by the API viewset and the login wizard.
"""

from django.utils.translation import gettext as _

from onadata.libs.utils.log import Actions, audit_log


def notify_owner(user, event, **context):
    """Email the account owner about a change to their second factor."""
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
    """Audit a failed second-factor check."""
    audit_log(
        Actions.TWO_FACTOR_VERIFICATION_FAILED,
        user,
        user,
        _("Two-factor verification failed."),
        audit,
        request,
    )
