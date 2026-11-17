# -*- coding: utf-8 -*-
"""Viewset mixin turning a policy decision into a step-up challenge."""

from rest_framework import status
from rest_framework.response import Response

from onadata.libs.stepup.challenge import STEP_UP_UNAVAILABLE, build_challenge
from onadata.libs.stepup.gate import (
    ENROL_REQUIRED,
    ONE_GATED_CHANGE_PER_REQUEST,
    change_refusal,
    refusal_reason,
)


class RequiresStepUp:
    """Refuse a gated action unless the request carries a spent-once grant.

    The server decides which actions are gated. A gate that a client enforced
    could be bypassed by calling the API directly.
    """

    def check_step_up(self, request, action: str):
        """``None`` to proceed, or a Response to return instead."""
        return self.step_up_refusal(request, refusal_reason(request, action), (action,))

    def gated_change_refusal(self, request, changes):
        """Refuse the gated change among ``changes``, ``(action, changed)``
        pairs, or None to proceed."""
        return self.step_up_refusal(request, *change_refusal(request, changes))

    def step_up_refusal(self, request, reason, audiences):
        """The Response refusing ``audiences`` for ``reason``, or None when
        there is no reason."""
        if reason is None:
            return None
        if reason == ONE_GATED_CHANGE_PER_REQUEST:
            return Response(
                {"error": reason, "audiences": list(audiences)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if reason == ENROL_REQUIRED:
            return Response(
                {"error": ENROL_REQUIRED},
                status=status.HTTP_403_FORBIDDEN,
            )
        challenge = build_challenge(audiences[0], request.user)
        if challenge["error"] == STEP_UP_UNAVAILABLE:
            return Response(
                {"error": STEP_UP_UNAVAILABLE},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(challenge, status=status.HTTP_401_UNAUTHORIZED)

    def gated_create(self, request, refusal_for):
        """DRF's create with a gate between validating and writing.

        ``refusal_for(validated_data)`` returns None to proceed or a Response
        to answer instead, as for ``gated_update``.
        """
        # pylint: disable=no-member
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refusal = refusal_for(serializer.validated_data)
        if refusal is not None:
            return refusal
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def gated_update(self, request, refusal_for, partial=False):
        """DRF's update with a gate between validating and writing.

        ``refusal_for(instance, validated_data)`` returns None to proceed or a
        Response to answer instead. Validating first means a request the write
        would reject is answered 400 before any grant is spent.
        """
        # pylint: disable=no-member
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        refusal = refusal_for(instance, serializer.validated_data)
        if refusal is not None:
            return refusal
        self.perform_update(serializer)
        if getattr(instance, "_prefetched_objects_cache", None):
            # The update can change relations the queryset prefetched.
            # pylint: disable=protected-access
            instance._prefetched_objects_cache = {}
        return Response(serializer.data)
