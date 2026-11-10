# -*- coding: utf-8 -*-
"""Viewset mixin turning a policy decision into a 401 challenge."""

from rest_framework import status
from rest_framework.fields import empty
from rest_framework.response import Response

from onadata.libs.stepup.challenge import build_challenge
from onadata.libs.stepup.gate import (
    ENROL_REQUIRED,
    changed_gated_actions,
    refusal_reason,
)


def incoming_value(serializer, name: str, data):
    """The value ``data`` would write to the serializer field ``name``, or
    ``empty`` when it writes none.

    Read through the field itself, so a gate and the write agree on "on"
    meaning true and on an absent form checkbox meaning false in a full update.
    """
    field = serializer.fields.get(name)
    if field is None:
        return empty
    value = field.get_value(data)
    return value if value is empty else field.to_internal_value(value)


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


def gated_change_refusal(viewset, request, changes):
    """Refuse the gated change among ``changes``, ``(action, changed)`` pairs,
    or None to proceed.

    A request carries one grant, so one making two gated changes is refused
    before any grant is spent.
    """
    gated = changed_gated_actions(changes)
    if len(gated) > 1:
        return Response(
            {"error": "one_gated_change_per_request", "audiences": gated},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return viewset.check_step_up(request, gated[0]) if gated else None
