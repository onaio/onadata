# -*- coding: utf-8 -*-
"""Step-up for server-rendered pages that write gated values.

These pages cannot run the API's challenge, so a gated change made through
them is refused unless the request already carries a grant.
"""

from copy import deepcopy

from django.http import HttpResponseForbidden
from django.utils.translation import gettext as _

from onadata.libs.stepup.gate import (
    ENROL_REQUIRED,
    ONE_GATED_CHANGE_PER_REQUEST,
    change_refusal,
    refusal_reason,
)
from onadata.libs.stepup.policy import (
    GATE_CHANGE_EMAIL,
    GATE_PRIVACY_CONSENT,
    GATE_REQUIRE_AUTH,
    eu_consent_record,
)


def _forbidden(reason):
    """``None`` when there is no ``reason``, or a 403 explaining it."""
    if reason is None:
        return None
    if reason == ONE_GATED_CHANGE_PER_REQUEST:
        return HttpResponseForbidden(_("Change one protected setting at a time."))
    if reason == ENROL_REQUIRED:
        return HttpResponseForbidden(
            _("Set up two-factor authentication before making this change.")
        )
    return HttpResponseForbidden(
        _(
            "This change requires verifying your second factor, "
            "which this page does not support."
        )
    )


def refuse_page_action(request, action: str):
    """``None`` to proceed, or a 403 refusing ``action``."""
    return _forbidden(refusal_reason(request, action))


def gated_profile_values(require_auth, email, metadata) -> dict:
    """The profile values a step-up gates, keyed by the audience gating each.

    Deep-copied, so a snapshot taken before a form writes the instance keeps
    the stored values.
    """
    return {
        GATE_REQUIRE_AUTH: bool(require_auth),
        GATE_CHANGE_EMAIL: (email or "").strip().lower(),
        GATE_PRIVACY_CONSENT: deepcopy(eu_consent_record(metadata or {})),
    }


def refuse_gated_changes(request, before: dict, after: dict):
    """``None``, or a 403 for a gated value changed without a grant."""
    reason, _audiences = change_refusal(
        request, ((action, after[action] != value) for action, value in before.items())
    )
    return _forbidden(reason)
