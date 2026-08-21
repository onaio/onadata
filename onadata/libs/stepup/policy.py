# -*- coding: utf-8 -*-
"""Which actions require a second factor, and how this deployment proves one."""

from django.conf import settings

#: Audience for the "Require Phone Authentication" toggle. Named once so the
#: viewset, the challenge and the SPA cannot disagree about the string.
GATE_REQUIRE_AUTH = "require-auth-toggle"

#: Audience for the GDPR EU-citizen consent record. Its own audience rather
#: than sharing the toggle's, because a grant is spendable for exactly one
#: action -- proving a factor to change one setting must not silently open
#: the other.
GATE_PRIVACY_CONSENT = "privacy-consent"

#: Audience for regenerating the API token, which invalidates every
#: integration holding the old one.
GATE_REGENERATE_API_KEY = "regenerate-api-key"

#: Audience for changing the account's email, where password resets land.
GATE_CHANGE_EMAIL = "change-email"

#: Audience for changing the password. It already demands the current one;
#: the second factor is what a password alone cannot provide.
GATE_CHANGE_PASSWORD = "change-password"

def eu_consent_path() -> tuple:
    """Where the consent record sits in ``UserProfile.metadata``.

    Configuration, because the client that writes it decides the layout and
    existing deployments already have one. Named in a single place so the gate
    and the writer cannot disagree about which change is sensitive.
    """
    return tuple(
        getattr(settings, "EU_CONSENT_METADATA_PATH", ("eu_citizen_consent",))
    )


def _config() -> dict:
    return getattr(settings, "STEP_UP", {}) or {}


def is_gated(action: str) -> bool:
    """Whether ``action`` needs step-up here.

    Empty by default: a deployment that has not opted in gates nothing and
    behaves exactly as it did before this package existed.
    """
    return action in set(_config().get("ACTIONS", ()))


def mode() -> str:
    """``"local"`` (OnaData owns the factor) or ``"federated"`` (an IdP does).

    Read from configuration rather than inferred from how a session arrived.
    Inferring it would fall back to local verification for a session that
    never visited the IdP, which is a bypass rather than a default.
    """
    return _config().get("MODE", "local")


def no_factor_policy() -> str:
    """What to do when a gated action is reached by a user with no factor.

    ``skip_gate`` lets them through, ``deny_prompt_enrol`` refuses. Defaults
    to ``skip_gate`` for rollout safety, which means an unconfigured
    deployment gets the bypassable behaviour -- made loud by the system check
    rather than left silent.
    """
    return _config().get("NO_FACTOR_POLICY", "skip_gate")
