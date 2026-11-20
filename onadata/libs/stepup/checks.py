# -*- coding: utf-8 -*-
"""Startup checks for step-up configuration."""

from collections.abc import Collection

from django.conf import settings
from django.core.checks import Error as CheckError
from django.core.checks import Warning as CheckWarning

from oidc.stepup import (
    find_step_up_auth_server,
    step_up_config,
    subject_binding,
    subject_binding_is_safe,
)

from onadata.libs.stepup.policy import (
    GATE_AUTHORIZE_OAUTH_APP,
    GATE_CHANGE_EMAIL,
    KNOWN_ACTIONS,
    KNOWN_MODES,
    KNOWN_NO_FACTOR_POLICIES,
    POLICY_DENY_PROMPT_ENROL,
    POLICY_SKIP_GATE,
    gated_actions,
    is_local_mode,
    mode,
    no_factor_policy,
    step_up_setting,
)


def _malformation(config):
    """What makes ``config``, a ``STEP_UP`` setting, unreadable, or None."""
    if not isinstance(config, dict):
        return f"STEP_UP is a {type(config).__name__}, not a dict."
    actions = config.get("ACTIONS", ())
    if isinstance(actions, str):
        return None
    if not isinstance(actions, Collection) or isinstance(actions, dict):
        return f"STEP_UP['ACTIONS'] is a {type(actions).__name__}, not a list."
    if not all(isinstance(action, str) for action in actions):
        return f"STEP_UP['ACTIONS'] holds entries that are not strings: {actions!r}."
    return None


def check_step_up_is_well_formed(app_configs=None, **kwargs):
    # pylint: disable=unused-argument
    """A ``STEP_UP`` that cannot be read gates nothing.

    The policy reads such a setting as empty rather than crash every request,
    which leaves every action the deployment meant to gate ungated.
    """
    problem = _malformation(step_up_setting())
    if problem is None:
        return []
    return [
        CheckError(
            f"{problem} Step-up reads it as gating nothing.",
            hint="Set STEP_UP to a dict whose 'ACTIONS' lists action names.",
            id="stepup.E001",
        )
    ]


def check_step_up_actions_are_known(app_configs=None, **kwargs):
    # pylint: disable=unused-argument
    """An action name no gate checks protects nothing.

    A typo such as ``"change-emial"`` leaves the intended action ungated
    while the deployment believes it is protected.
    """
    unknown = sorted(gated_actions() - KNOWN_ACTIONS)
    if not unknown:
        return []
    return [
        CheckError(
            f"STEP_UP['ACTIONS'] names actions nothing gates: {', '.join(unknown)}.",
            hint=f"Use names from: {', '.join(sorted(KNOWN_ACTIONS))}.",
            id="stepup.E002",
        )
    ]


def check_step_up_no_factor_policy_is_known(app_configs=None, **kwargs):
    # pylint: disable=unused-argument
    """An unrecognised NO_FACTOR_POLICY refuses users with no factor.

    It fails closed, like ``deny_prompt_enrol``, but for a reason no one
    chose.
    """
    configured = no_factor_policy()
    if isinstance(configured, str) and configured in KNOWN_NO_FACTOR_POLICIES:
        return []
    return [
        CheckWarning(
            f"STEP_UP['NO_FACTOR_POLICY'] is {configured!r}, not one of "
            f"{sorted(KNOWN_NO_FACTOR_POLICIES)}; it is treated as "
            f"{POLICY_DENY_PROMPT_ENROL!r}.",
            hint="Set STEP_UP['NO_FACTOR_POLICY'] to 'skip_gate' or "
            "'deny_prompt_enrol'.",
            id="stepup.W008",
        )
    ]


def check_step_up_not_silently_bypassable(app_configs=None, **kwargs):
    # pylint: disable=unused-argument
    """``skip_gate`` is a valid rollout choice, but a silent one.

    It lets every user with no factor through a gated action. Local mode only,
    because federated mode always challenges.
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


def check_step_up_has_two_factor_enabled(app_configs=None, **kwargs):
    # pylint: disable=unused-argument
    """Local step-up needs ``ENABLE_TWO_FACTOR``.

    Without it ``/api/v1/totp/*`` answers 404, so nobody can enrol or verify.
    A user who holds a device is challenged with no way to earn a grant, and
    ``deny_prompt_enrol`` refuses everyone else.
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
    """An unrecognised MODE counts as federated.

    A typo such as ``"fedarated"`` moves verification to the identity provider
    without a warning. It fails closed, but for a reason no one chose.
    """
    configured = mode()
    if isinstance(configured, str) and configured in KNOWN_MODES:
        return []
    return [
        CheckWarning(
            f"STEP_UP['MODE'] is {configured!r}, not one of "
            f"{sorted(KNOWN_MODES)}; it is treated as federated.",
            hint="Set STEP_UP['MODE'] to 'local' or 'federated'.",
            id="stepup.W003",
        )
    ]


def check_federated_step_up_gates_email(app_configs=None, **kwargs):
    # pylint: disable=unused-argument
    """Federated step-up matches the provider's token to the account email.

    If changing the email is not gated, a stolen session can point it at the
    attacker's provider account and pass every gate.
    """
    actions = gated_actions()
    if not actions or is_local_mode() or GATE_CHANGE_EMAIL in actions:
        return []
    return [
        CheckWarning(
            "Federated step-up is configured, but changing the email is not "
            "gated, and step-up identifies the user by email.",
            hint=f"Add {GATE_CHANGE_EMAIL!r} to STEP_UP['ACTIONS'].",
            id="stepup.W006",
        )
    ]


def check_removed_enrolment_password_setting(app_configs=None, **kwargs):
    # pylint: disable=unused-argument
    """``TWO_FACTOR_ENROLMENT_REQUIRES_PASSWORD`` is ignored.

    A first enrolment always needs the account password. Users the setting
    meant to exempt are refused at enrolment with no other signal.
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


def check_federated_step_up_binds_by_email(app_configs=None, **kwargs):
    # pylint: disable=unused-argument
    """Step-up can identify the user by another field, but only the email
    is gated against change.

    A stolen session can rename the account to match the attacker's own
    provider account, then pass every gate with the attacker's own factor.
    """
    server = find_step_up_auth_server()
    if not gated_actions() or is_local_mode() or server is None:
        return []
    config = step_up_config(server)
    if subject_binding_is_safe(config):
        return []
    _claim, field = subject_binding(config)
    return [
        CheckWarning(
            f"Federated step-up identifies the user by {field!r}, which a "
            "user can change without step-up.",
            hint="Remove SUBJECT_CLAIM and SUBJECT_FIELD from the STEP_UP "
            "block so step-up identifies the user by email.",
            id="stepup.W007",
        )
    ]


def check_oauth_approval_can_step_up(app_configs=None, **kwargs):
    # pylint: disable=unused-argument
    """The OAuth consent and application pages cannot run a challenge.

    Their grant field starts empty, and the browser a client redirects there
    cannot add the grant header, so a gated approval is always refused.
    """
    if GATE_AUTHORIZE_OAUTH_APP not in gated_actions():
        return []
    return [
        CheckWarning(
            f"{GATE_AUTHORIZE_OAUTH_APP!r} is gated, but /o/authorize/ and "
            "/o/applications/ cannot run a step-up challenge: every user the "
            "gate challenges is refused with 403 when approving or "
            "registering an OAuth application.",
            hint=f"Remove {GATE_AUTHORIZE_OAUTH_APP!r} from STEP_UP['ACTIONS'] "
            "unless those refusals are intended.",
            id="stepup.W009",
        )
    ]
