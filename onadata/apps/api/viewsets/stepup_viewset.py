# -*- coding: utf-8 -*-
"""Where the identity provider returns after a step-up."""

import logging

from oidc.stepup_grants import issue_grant
from oidc.stepup_viewsets import StepUpCallbackMixin
from rest_framework import status
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer, StaticHTMLRenderer
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from onadata.libs.authentication import SSOHeaderAuthentication
from onadata.libs.stepup.challenge import STEP_UP_UNAVAILABLE
from onadata.libs.stepup.federated import start_step_up
from onadata.libs.stepup.policy import is_gated, is_local_mode

logger = logging.getLogger(__name__)

#: Why ``start`` refuses. Either the audience is not gated here, or the factor
#: is verified locally rather than at an identity provider.
NOT_GATED = "not_gated"
NOT_FEDERATED = "not_federated"

#: Why ``callback`` refuses. Either the provider's answer is missing, or it
#: does not satisfy the step-up.
INVALID_REQUEST = "invalid_request"
STEP_UP_FAILED = "step_up_failed"


class StepUpViewSet(StepUpCallbackMixin, ViewSet):
    """Completes a federated step-up and hands the grant back to the caller."""

    # The popup returning from the provider sends cookies only, so accept the
    # Django session as well as the SSO cookie.
    authentication_classes = (
        SSOHeaderAuthentication,
        SessionAuthentication,
        TokenAuthentication,
    )
    permission_classes = (IsAuthenticated,)
    # StaticHTMLRenderer is for content negotiation, not rendering. DRF
    # negotiates before the handler runs, so without it the returning popup's
    # ``Accept: text/html`` gets a 406.
    renderer_classes = (JSONRenderer, StaticHTMLRenderer)

    def finalize_response(self, request, response, *args, **kwargs):
        """Mark every response no-store, because a callback body carries a
        grant."""
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    @action(detail=False, methods=["get"], url_path="start")
    def start(self, request):
        """Where to send the user to prove a factor for ``audience``.

        Call this before the gated request, not after its 401. A browser
        caller must open its popup inside the click handler, because browsers
        block a popup opened later from an async response.
        """
        audience = str(request.query_params.get("audience", "")).strip()
        if not audience or not is_gated(audience):
            return Response({"error": NOT_GATED}, status=status.HTTP_400_BAD_REQUEST)
        if is_local_mode():
            return Response(
                {"error": NOT_FEDERATED}, status=status.HTTP_400_BAD_REQUEST
            )
        auth_server = self.step_up_auth_server()
        try:
            url, _ = start_step_up(auth_server, audience, request.user)
        except (ValueError, KeyError):
            # No server carries a STEP_UP block, or the one that does lacks
            # its endpoints.
            logger.exception("step-up: cannot build an authorization request")
            return Response(
                {"error": STEP_UP_UNAVAILABLE},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"authorizationUrl": url})

    @action(detail=False, methods=["get", "post"], url_path="callback")
    def callback(self, request):
        """Verify the provider's answer, and mint a grant only if it
        satisfies the step-up."""
        params = request.query_params if request.method == "GET" else request.data
        code = str(params.get("code", "")).strip()
        state = str(params.get("state", "")).strip()
        auth_server = str(params.get("auth_server", "")).strip() or None
        # A browser here is the popup returning from the provider. It needs a
        # page that hands the result to its opener, not JSON.
        popup = "text/html" in request.headers.get("Accept", "")

        if not code or not state:
            # A provider reports a cancelled or failed prompt as ``error``.
            reason = "provider_error" if params.get("error") else INVALID_REQUEST
            if popup:
                return self.step_up_popup_response(None, reason)
            return Response(
                {"error": INVALID_REQUEST}, status=status.HTTP_400_BAD_REQUEST
            )

        grant, reason = self.complete_step_up(request, code, state, auth_server)

        if popup:
            return self.step_up_popup_response(grant, reason)

        if grant is None:
            # ``reason`` names the check that failed, not what the user did. A
            # cancelled prompt and a provider with no MFA can look alike, so a
            # caller should show one generic failure.
            return Response(
                {"error": STEP_UP_FAILED, "reason": reason or "unknown"},
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
        """A proven factor earns a grant for the action it was proven for."""
        # pylint: disable=unused-argument
        return issue_grant(request.user.pk, context["audience"])
