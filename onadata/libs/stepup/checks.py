# -*- coding: utf-8 -*-
"""Startup checks for step-up configuration."""

from django.conf import settings
from django.core.checks import Warning as CheckWarning

from onadata.libs.stepup.policy import (
    KNOWN_MODES,
    POLICY_SKIP_GATE,
    gated_actions,
    is_local_mode,
    mode,
    no_factor_policy,
)


def check_step_up_not_silently_bypassable(app_configs=None, **kwargs):
    # pylint: disable=unused-argument
    """``skip_gate`` is a legitimate rollout choice, but a silent one.

    Without this a deployment can gate actions, believe them protected, and
    have every un-enrolled user waved straight through with no signal.

    Local mode only: federated mode always challenges, so the policy is never
    consulted there.
    """
    actions = sorted(gated_actions())
    if actions and is_local_mode() and no_factor_policy() == POLICY_SKIP_GATE:
        return [
            CheckWarning(
                "Step-up is configured but users without a second factor are "
                f"not challenged for: {', '.join(actions)}.",
                hint="Set STEP_UP['NO_FACTOR_POLICY'] = 'deny_prompt_enrol' "
                "once these users are expected to have enrolled.",
                id="stepup.W001",
            )
        ]
    return []


def check_step_up_actions_are_mintable(app_configs=None, **kwargs):
    # pylint: disable=unused-argument
    """A gated action whose audience cannot be minted is a locked door.

    The challenge names the action as the audience the caller must present,
    and ``/api/v1/totp/verify`` refuses an audience this deployment has not
    declared. Gate one without declaring it and the user is told to step up,
    then refused the grant that would satisfy it, with no way through.

    Local mode only: a federated deployment earns its grants at the identity
    provider's callback, which never consults this list.
    """
    if not is_local_mode():
        return []
    unmintable = sorted(
        gated_actions()
        - frozenset(getattr(settings, "TWO_FACTOR_STEP_UP_AUDIENCES", ()))
    )
    if not unmintable:
        return []
    return [
        CheckWarning(
            "Step-up gates actions whose grants cannot be minted: "
            f"{', '.join(unmintable)}. Users will be challenged and then "
            "refused the proof that would satisfy the challenge.",
            hint="Add them to TWO_FACTOR_STEP_UP_AUDIENCES, or remove them "
            "from STEP_UP['ACTIONS'].",
            id="stepup.W002",
        )
    ]


def check_step_up_has_two_factor_enabled(app_configs=None, **kwargs):
    # pylint: disable=unused-argument
    """Local step-up with two-factor switched off is a locked door.

    ``/api/v1/totp/*`` answers 404 without ``ENABLE_TWO_FACTOR``, so nobody can
    enrol or verify. A user who already holds a device is challenged with no
    way to earn the grant, and ``deny_prompt_enrol`` refuses everyone else.
    """
    if (
        not is_local_mode()
        or not gated_actions()
        or getattr(settings, "ENABLE_TWO_FACTOR", False)
    ):
        return []
    return [
        CheckWarning(
            "Step-up gates actions in local mode, but ENABLE_TWO_FACTOR is off: "
            "no user can enrol or verify, so no gated action can be stepped up "
            "for.",
            hint="Set ENABLE_TWO_FACTOR = True, or empty STEP_UP['ACTIONS'].",
            id="stepup.W004",
        )
    ]


def check_step_up_mode_is_known(app_configs=None, **kwargs):
    # pylint: disable=unused-argument
    """An unrecognised MODE silently switches the whole topology.

    Everything that is not ``"local"`` is treated as federated, so a typo like
    ``"fedarated"`` moves verification to the identity provider without a word.
    It fails closed -- grants are demanded, not bypassed -- but for a reason no
    one chose.
    """
    configured = mode()
    if configured in KNOWN_MODES:
        return []
    return [
        CheckWarning(
            f"STEP_UP['MODE'] is {configured!r}, not one of "
            f"{sorted(KNOWN_MODES)}; it is treated as federated.",
            hint="Set STEP_UP['MODE'] to 'local' or 'federated'.",
            id="stepup.W003",
        )
    ]


def check_removed_enrolment_password_setting(app_configs=None, **kwargs):
    # pylint: disable=unused-argument
    """``TWO_FACTOR_ENROLMENT_REQUIRES_PASSWORD`` no longer does anything.

    A first enrolment always needs the account password, so a deployment that
    kept the opt-out for users without a usable password has those users
    refused at enrolment with no other signal.
    """
    if not hasattr(settings, "TWO_FACTOR_ENROLMENT_REQUIRES_PASSWORD"):
        return []
    return [
        CheckWarning(
            "TWO_FACTOR_ENROLMENT_REQUIRES_PASSWORD has been removed and is "
            "ignored: enrolling a first device always needs the account "
            "password.",
            hint="Remove the setting. Users without a usable password must set "
            "one before enrolling.",
            id="stepup.W005",
        )
    ]
