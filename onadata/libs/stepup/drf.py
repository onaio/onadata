# -*- coding: utf-8 -*-
"""Viewset mixin turning a policy decision into a 401 challenge."""

from rest_framework import status
from rest_framework.response import Response

from oidc.stepup_grants import spend_grant

from onadata.libs.stepup.challenge import build_challenge
from onadata.libs.stepup.policy import is_gated, mode, no_factor_policy


def _has_second_factor(user) -> bool:
    # Imported lazily: two_factor pulls in django_otp's models, and this
    # module is imported from apps.py while the app registry is still loading.
    # pylint: disable=import-outside-toplevel
    from two_factor.utils import default_device

    return default_device(user) is not None


#: Header a caller may use when the request has no body to put a grant in.
#: Not a query parameter: a grant is a bearer credential for the gated action,
#: and a query string is written to access logs, browser history and Referer.
GRANT_HEADER = "X-Step-Up-Grant"


def _presented_grant(request) -> str:
    """The grant this request carries, from its body or the header."""
    body = getattr(request, "data", None) or {}
    if hasattr(body, "get"):
        from_body = str(body.get("grant", "") or "").strip()
        if from_body:
            return from_body
    return str(request.headers.get(GRANT_HEADER, "") or "").strip()


class RequiresStepUp:  # pylint: disable=too-few-public-methods
    """Refuse a gated action unless the request carries a spent-once grant.

    The decision lives here rather than in the client because a client that
    decided which actions were sensitive would be bypassed by calling the API
    directly.
    """

    def check_step_up(self, request, action: str):
        """``None`` to proceed, or a Response to return instead."""
        if not is_gated(action):
            return None
        # One request can reach this twice for the same action: DRF's
        # partial_update delegates to update, and both gate. The grant is
        # single-use, so spend it once per request and let a repeat of the
        # same action through on that result rather than on a grant now gone.
        spent = getattr(request, "_stepped_up_actions", None)
        if spent is None:
            spent = set()
            request._stepped_up_actions = spent
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
                return Response(
                    {"error": "enrol_required"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            return None
        if spend_grant(request.user.pk, action, _presented_grant(request)):
            spent.add(action)
            return None
        return Response(
            build_challenge(action, request.user),
            status=status.HTTP_401_UNAUTHORIZED,
        )
