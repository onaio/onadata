# -*- coding: utf-8 -*-
"""Which actions require a second factor, and how this deployment proves one."""

from django.conf import settings

#: Audience for the "Require Phone Authentication" toggle. Named once so the
#: viewset, the challenge and the caller cannot disagree about the string.
GATE_REQUIRE_AUTH = "require-auth-toggle"

#: Audience for the GDPR EU-citizen consent record. Its own audience rather
#: than sharing the toggle's, because a grant is spendable for exactly one
#: action. Proving a factor to change one setting must not open the other.
GATE_PRIVACY_CONSENT = "privacy-consent"

#: Audience for regenerating the API token, which invalidates every
#: integration holding the old one.
GATE_REGENERATE_API_KEY = "regenerate-api-key"

#: Audience for regenerating the ODK token, which invalidates the ODK Collect
#: credential the old one carried.
GATE_REGENERATE_ODK_TOKEN = "regenerate-odk-token"

#: Audience for changing the account's email, where password resets land.
GATE_CHANGE_EMAIL = "change-email"

#: Audience for changing the password. It already demands the current one;
#: the second factor is what a password alone cannot provide.
GATE_CHANGE_PASSWORD = "change-password"  # noqa

#: Audience for making someone an organisation owner or manager, who can then
#: change the organisation's gated settings with their own factor.
GATE_GRANT_ORG_ADMIN = "grant-org-admin"

#: Audience for rotating an organisation's encryption key, which makes every
#: device fetch the re-keyed forms.
GATE_ROTATE_ORG_KEY = "rotate-org-key"

#: Audience for renaming the account. Login and step-up can identify users by
#: username, so a stolen session must not be able to repoint it.
GATE_CHANGE_USERNAME = "change-username"

#: Audience for adding a webhook or changing where one sends, which would
#: forward every new submission to whoever holds the session.
GATE_CHANGE_WEBHOOK = "change-webhook"

#: Audiences for giving someone the owner or manager role, one per route so a
#: deployment can gate each on its own.
GATE_SHARE_FORM_ADMIN = "share-form-admin"
GATE_SHARE_PROJECT_ADMIN = "share-project-admin"
GATE_INVITE_PROJECT_ADMIN = "invite-project-admin"
GATE_SHARE_TEAM_ADMIN = "share-team-admin"

#: Audience for making a form's or project's data public.
GATE_PUBLISH_DATA = "publish-data"

#: Audience for moving a project to another account, which hands its data to
#: whoever controls that account.
GATE_TRANSFER_PROJECT = "transfer-project"

#: Audience for approving or registering an OAuth application, which issues a
#: long-lived credential the API token gates do not cover.
GATE_AUTHORIZE_OAUTH_APP = "authorize-oauth-app"

#: Audience for turning off a form's own require_auth.
GATE_FORM_REQUIRE_AUTH = "form-require-auth"

#: Audience for turning off a form's encryption.
GATE_DISABLE_FORM_ENCRYPTION = "disable-form-encryption"

#: Roles that can share, delete and re-share what they hold.
ADMIN_ROLE_NAMES = frozenset({"owner", "manager"})

MODE_LOCAL = "local"
MODE_FEDERATED = "federated"
KNOWN_MODES = frozenset({MODE_LOCAL, MODE_FEDERATED})

POLICY_SKIP_GATE = "skip_gate"
POLICY_DENY_PROMPT_ENROL = "deny_prompt_enrol"


def _as_tuple(value) -> tuple:
    """A setting meant as a sequence. A bare string is one entry, not a
    sequence of characters."""
    return (value,) if isinstance(value, str) else tuple(value)


def eu_consent_path() -> tuple:
    """Where the consent record sits in ``UserProfile.metadata``.

    Configuration, because the client that writes it decides the layout and
    existing deployments already have one. Named in a single place so the gate
    and the writer cannot disagree about which change is sensitive.
    """
    return _as_tuple(
        getattr(settings, "EU_CONSENT_METADATA_PATH", ("eu_citizen_consent",))
    )


def eu_consent_record(metadata):
    """The consent record in ``metadata``, or ``None`` if the path does not
    resolve."""
    record = metadata
    for key in eu_consent_path():
        if not isinstance(record, dict):
            return None
        record = record.get(key)
    return record


def _config() -> dict:
    return getattr(settings, "STEP_UP", {}) or {}


def is_gated(action: str) -> bool:
    """Whether ``action`` needs step-up here.

    Empty by default: a deployment that has not opted in gates nothing and
    behaves exactly as it did before this package existed.
    """
    return action in gated_actions()


def gated_actions() -> frozenset:
    """Every action this deployment has opted into gating."""
    return frozenset(_as_tuple(_config().get("ACTIONS", ())))


def mode() -> str:
    """``"local"`` (OnaData owns the factor) or ``"federated"`` (an IdP does).

    Read from configuration rather than inferred from how a session arrived.
    Inferring it would fall back to local verification for a session that
    never visited the IdP, which is a bypass rather than a default.
    """
    return _config().get("MODE", MODE_LOCAL)


def is_local_mode() -> bool:
    """Whether OnaData, not an identity provider, owns the second factor.

    Anything other than ``"local"`` counts as federated, which fails closed:
    grants are demanded rather than skipped.
    """
    return mode() == MODE_LOCAL


def no_factor_policy() -> str:
    """What to do when a gated action is reached by a user with no factor.

    ``skip_gate`` lets them through; ``deny_prompt_enrol``, or any other
    value, refuses. Defaults to ``skip_gate`` for rollout safety, so an
    unconfigured deployment gets the bypassable behaviour. The
    ``stepup.W001`` check warns about it.
    """
    return _config().get("NO_FACTOR_POLICY", POLICY_SKIP_GATE)
