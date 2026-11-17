# -*- coding: utf-8 -*-
"""Whether a request may perform a gated action."""

from oidc.stepup_grants import spend_grant

from onadata.libs.stepup.policy import (
    POLICY_SKIP_GATE,
    is_gated,
    is_local_mode,
    no_factor_policy,
)

#: Why a gate refused. Either no grant was presented, or the user has no
#: factor and the deployment refuses rather than skips.
STEP_UP_REQUIRED = "step_up_required"
ENROL_REQUIRED = "enrol_required"

#: Why a request making more than one gated change is refused. One grant
#: cannot satisfy two gates, so the request is refused before any is spent.
ONE_GATED_CHANGE_PER_REQUEST = "one_gated_change_per_request"

#: Header a caller may use when the request has no body to put a grant in.
#: Do not accept a query parameter instead. A grant is a bearer credential, and
#: query strings are written to access logs, browser history and Referer.
GRANT_HEADER = "X-Step-Up-Grant"


class StepUpRefused(Exception):
    """A gated change was refused where no response can be returned.

    Carries the decision, ``reason`` and the ``audiences`` involved, for the
    caller that catches it to answer with.
    """

    def __init__(self, reason: str, audiences):
        super().__init__(reason)
        self.reason = reason
        self.audiences = tuple(audiences)


def has_second_factor(user) -> bool:
    """Whether the login view would challenge this user for a second factor.

    Uses ``default_device`` rather than an EncryptedTOTPDevice lookup, because
    two_factor challenges on any confirmed device named ``"default"``.
    ``TOTPViewSet`` verifies only TOTP and recovery codes. Teach it any new
    device type in the same change.
    """
    # pylint: disable=import-outside-toplevel
    from two_factor.utils import default_device

    return default_device(user) is not None


def _presented_grant(request) -> str:
    """The grant this request carries, from its body or the header.

    Reads ``data`` on a DRF request and ``POST`` on a plain Django one.
    """
    body = getattr(request, "data", None) or getattr(request, "POST", None) or {}
    if hasattr(body, "get"):
        from_body = str(body.get("grant", "") or "").strip()
        if from_body:
            return from_body
    return str(request.headers.get(GRANT_HEADER, "") or "").strip()


def changed_gated_actions(changes) -> list:
    """The gated actions among ``changes``, an iterable of
    ``(action, changed)`` pairs, in order.

    ``changed`` may be a function, called only when ``action`` is gated, so a
    check that costs queries runs only where a deployment gates the action."""
    return [
        action
        for action, changed in changes
        if is_gated(action) and (changed() if callable(changed) else changed)
    ]


def refusal_reason(request, action: str):
    """``None`` to proceed, or why ``action`` is refused. Spends the grant the
    request presents."""
    if not is_gated(action):
        return None
    # A gating view can delegate to another that gates the same action. The
    # grant is single-use, so spend it once per request and pass repeats on
    # that result.
    spent = getattr(request, "_stepped_up_actions", None)
    if spent is None:
        spent = set()
        request._stepped_up_actions = spent  # pylint: disable=protected-access
    if action in spent:
        return None
    # Only local mode can tell whether a user has a second factor. In
    # federated mode the IdP holds it, the local lookup is False for every
    # user, and skip_gate would open the gate everywhere. Challenge instead,
    # and let the IdP decide what a user with no factor may do.
    if is_local_mode() and not has_second_factor(request.user):
        # Only an exact skip_gate opens the gate, so a misspelt policy refuses.
        if no_factor_policy() != POLICY_SKIP_GATE:
            return ENROL_REQUIRED
        return None
    if spend_grant(request.user.pk, action, _presented_grant(request)):
        spent.add(action)
        return None
    return STEP_UP_REQUIRED


def change_refusal(request, changes) -> tuple:
    """``(reason, audiences)`` for the gated change among ``changes``,
    ``(action, changed)`` pairs. ``reason`` is ``None`` to proceed.

    Spends the grant the request presents. A request with more than one gated
    change is refused first, with ``ONE_GATED_CHANGE_PER_REQUEST``.
    """
    gated = changed_gated_actions(changes)
    if len(gated) > 1:
        return ONE_GATED_CHANGE_PER_REQUEST, gated
    if not gated:
        return None, gated
    return refusal_reason(request, gated[0]), gated


def require_gated_change(request, changes):
    """Raise ``StepUpRefused`` unless the gated change among ``changes``,
    ``(action, changed)`` pairs, may proceed."""
    reason, audiences = change_refusal(request, changes)
    if reason is not None:
        raise StepUpRefused(reason, audiences)
