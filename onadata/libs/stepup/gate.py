# -*- coding: utf-8 -*-
"""Whether a request may perform a gated action."""

from oidc.stepup_grants import spend_grant

from onadata.libs.stepup.policy import is_gated, mode, no_factor_policy

#: Why a gate refused: no grant was presented, or the user has no factor to
#: earn one with and the deployment refuses rather than skips.
STEP_UP_REQUIRED = "step_up_required"
ENROL_REQUIRED = "enrol_required"

#: Header a caller may use when the request has no body to put a grant in.
#: Not a query parameter: a grant is a bearer credential for the gated action,
#: and a query string is written to access logs, browser history and Referer.
GRANT_HEADER = "X-Step-Up-Grant"


def _has_second_factor(user) -> bool:
    # Imported lazily: two_factor pulls in django_otp's models, and this
    # module is imported from apps.py while the app registry is still loading.
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


def refusal_reason(request, action: str):
    """``None`` to proceed, or why ``action`` is refused. Spends the grant the
    request presents."""
    if not is_gated(action):
        return None
    # One request can reach this twice for the same action: DRF's
    # partial_update delegates to update, and both gate. The grant is
    # single-use, so spend it once per request and let a repeat of the
    # same action through on that result rather than on a grant now gone.
    spent = getattr(request, "_stepped_up_actions", None)
    if spent is None:
        spent = set()
        request._stepped_up_actions = spent  # pylint: disable=protected-access
    if action in spent:
        return None
    # "Does this user have a second factor" is only answerable in local
    # mode. Federated, the factor lives at the IdP and this process cannot
    # see it -- a local lookup returns False for every user, and skip_gate
    # would then wave through exactly the deployments the gate is for.
    # Challenge instead and let the IdP answer: a user with no factor there
    # cannot satisfy the assurance claim, so the action still fails closed.
    if mode() == "local" and not _has_second_factor(request.user):
        if no_factor_policy() == "deny_prompt_enrol":
            return ENROL_REQUIRED
        return None
    if spend_grant(request.user.pk, action, _presented_grant(request)):
        spent.add(action)
        return None
    return STEP_UP_REQUIRED
