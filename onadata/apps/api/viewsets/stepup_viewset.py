# -*- coding: utf-8 -*-
"""Where the identity provider returns after a step-up.

Separate from the OIDC login callback on purpose: that one establishes
identity and cycles the session key. A step-up is performed by someone already
signed in, so reusing it would disturb a live session as a side effect of
proving a factor.
"""

import logging

from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer, StaticHTMLRenderer
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from oidc.stepup_grants import issue_grant
from oidc.stepup_viewsets import StepUpCallbackMixin

from onadata.libs.authentication import SSOHeaderAuthentication
from onadata.libs.stepup.federated import start_step_up
from onadata.libs.stepup.policy import is_gated, mode

logger = logging.getLogger(__name__)


class StepUpViewSet(StepUpCallbackMixin, ViewSet):
    """Completes a federated step-up and hands the grant back to the caller."""

    authentication_classes = (SSOHeaderAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated,)
    # StaticHTMLRenderer is here for content negotiation, not for rendering:
    # DRF negotiates before the handler runs, so a JSON-only viewset answers
    # the returning popup's ``Accept: text/html`` with a 406 and the browser
    # never reaches the page that hands the grant back.
    renderer_classes = (JSONRenderer, StaticHTMLRenderer)

    @action(detail=False, methods=["get"], url_path="start")
    def start(self, request):
        """Where to send the user to prove a factor for ``audience``.

        Asked before acting rather than after a 401: a browser caller must
        open its popup inside the click handler, and one opened later from an
        async response is what browsers block.
        """
        audience = str(request.query_params.get("audience", "")).strip()
        if not audience or not is_gated(audience):
            return Response(
                {"error": "not_gated"}, status=status.HTTP_400_BAD_REQUEST
            )
        if mode() == "local":
            return Response(
                {"error": "not_federated"}, status=status.HTTP_400_BAD_REQUEST
            )
        auth_server = self.step_up_auth_server()
        try:
            url, _ = start_step_up(auth_server, audience, request.user)
        except (ValueError, KeyError):
            # No server carries a STEP_UP block, or the one that does is
            # missing its endpoints. Either way there is nowhere to send the
            # user, and that is the deployment's fault rather than theirs.
            logger.exception("step-up: cannot build an authorization request")
            return Response(
                {"error": "step_up_unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"authorizationUrl": url})

    @action(detail=False, methods=["get", "post"], url_path="callback")
    def callback(self, request):
        """Verify the provider's answer; mint a grant only if it satisfies."""
        params = request.query_params if request.method == "GET" else request.data
        code = str(params.get("code", "")).strip()
        state = str(params.get("state", "")).strip()
        auth_server = str(params.get("auth_server", "")).strip() or None

        if not code or not state:
            return Response(
                {"error": "invalid_request"}, status=status.HTTP_400_BAD_REQUEST
            )

        grant, reason = self.complete_step_up(request, code, state, auth_server)

        # A browser landing here is the popup returning from the provider; it
        # needs a page that hands the grant to its opener, not JSON.
        if "text/html" in request.headers.get("Accept", ""):
            return self.step_up_popup_response(grant, reason)

        if grant is None:
            # Opaque to the caller: "wrong code", "cancelled" and "the provider
            # has no MFA configured" are indistinguishable here, and guessing
            # produces misleading UX. The reason is in the logs.
            return Response(
                {"error": "step_up_failed", "reason": reason or "unknown"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response({"grant": grant})

    def verify_step_up_context(self, request, context):
        """The state must belong to the session redeeming it."""
        if context.get("user_pk") != request.user.pk:
            logger.warning("step-up: state belongs to a different user")
            return "state_user_mismatch"
        return None

    def on_step_up_verified(self, request, claims, context):
        """A proven factor earns a grant for the action it was proven for.

        Scoped to that action alone: a factor proved for one gate must not
        open the others the user never saw a prompt for.
        """
        return issue_grant(request.user.pk, context["audience"])
