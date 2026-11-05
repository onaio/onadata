# -*- coding: utf-8 -*-
"""Viewset mixin turning a policy decision into a 401 challenge."""

from rest_framework import status
from rest_framework.response import Response

from onadata.libs.stepup.challenge import build_challenge
from onadata.libs.stepup.gate import ENROL_REQUIRED, refusal_reason


class RequiresStepUp:  # pylint: disable=too-few-public-methods
    """Refuse a gated action unless the request carries a spent-once grant.

    The decision lives here rather than in the client because a client that
    decided which actions were sensitive would be bypassed by calling the API
    directly.
    """

    def check_step_up(self, request, action: str):
        """``None`` to proceed, or a Response to return instead."""
        reason = refusal_reason(request, action)
        if reason is None:
            return None
        if reason == ENROL_REQUIRED:
            return Response(
                {"error": ENROL_REQUIRED},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(
            build_challenge(action, request.user),
            status=status.HTTP_401_UNAUTHORIZED,
        )
