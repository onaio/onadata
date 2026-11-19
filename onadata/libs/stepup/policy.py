# -*- coding: utf-8 -*-
"""Which actions require a second factor, and how this deployment proves one."""

from django.conf import settings

#: Audience for the "Require Phone Authentication" toggle.
GATE_REQUIRE_AUTH = "require-auth-toggle"

#: Audience for the GDPR EU-citizen consent record. It has its own audience so
#: a grant for the toggle cannot change it.
GATE_PRIVACY_CONSENT = "privacy-consent"

#: Audience for regenerating the API token, which invalidates every
#: integration holding the old one.
GATE_REGENERATE_API_KEY = "regenerate-api-key"

#: Audience for regenerating the ODK token, which invalidates the ODK Collect
#: credential the old one carried.
GATE_REGENERATE_ODK_TOKEN = "regenerate-odk-token"

#: Audience for changing the account's email, where password resets land.
GATE_CHANGE_EMAIL = "change-email"

#: Audience for changing the password.
GATE_CHANGE_PASSWORD = "change-password"  # noqa  # nosec B105

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

#: Every action a deployment can gate, each also an audience
#: ``/api/v1/totp/verify`` mints grants for.
KNOWN_ACTIONS = frozenset(
    {
        GATE_REQUIRE_AUTH,
        GATE_PRIVACY_CONSENT,
        GATE_REGENERATE_API_KEY,
        GATE_REGENERATE_ODK_TOKEN,
        GATE_CHANGE_EMAIL,
        GATE_CHANGE_PASSWORD,
        GATE_GRANT_ORG_ADMIN,
        GATE_ROTATE_ORG_KEY,
        GATE_CHANGE_USERNAME,
        GATE_CHANGE_WEBHOOK,
        GATE_SHARE_FORM_ADMIN,
        GATE_SHARE_PROJECT_ADMIN,
        GATE_INVITE_PROJECT_ADMIN,
        GATE_SHARE_TEAM_ADMIN,
        GATE_PUBLISH_DATA,
        GATE_TRANSFER_PROJECT,
        GATE_AUTHORIZE_OAUTH_APP,
        GATE_FORM_REQUIRE_AUTH,
        GATE_DISABLE_FORM_ENCRYPTION,
    }
)

#: The OAuth scope that lets an application ask for step-up grants.
STEP_UP_SCOPE = "stepup"

#: Roles that can share, delete and re-share what they hold.
ADMIN_ROLE_NAMES = frozenset({"owner", "manager"})

MODE_LOCAL = "local"
MODE_FEDERATED = "federated"
KNOWN_MODES = frozenset({MODE_LOCAL, MODE_FEDERATED})

POLICY_SKIP_GATE = "skip_gate"
POLICY_DENY_PROMPT_ENROL = "deny_prompt_enrol"
KNOWN_NO_FACTOR_POLICIES = frozenset({POLICY_SKIP_GATE, POLICY_DENY_PROMPT_ENROL})


def _as_tuple(value) -> tuple:
    """A setting read as a sequence. A bare string is one entry, and anything
    that is not a sequence is empty.

    Tolerant so a malformed setting cannot crash the startup checks that
    report it (``stepup.E001``).
    """
    if isinstance(value, str):
        return (value,)
    try:
        return tuple(value)
    except TypeError:
        return ()


def eu_consent_path() -> tuple:
    """Where the consent record sits in ``UserProfile.metadata``.

    A setting, because the client that writes the record decides its layout.
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


def step_up_setting():
    """``settings.STEP_UP`` as configured, which may not be a dict."""
    return getattr(settings, "STEP_UP", {}) or {}


def _config() -> dict:
    config = step_up_setting()
    return config if isinstance(config, dict) else {}


def is_gated(action: str) -> bool:
    """Whether ``action`` needs step-up here.

    A deployment that has not opted in gates nothing.
    """
    return action in gated_actions()


def gated_actions() -> frozenset:
    """Every action this deployment has opted into gating."""
    return frozenset(
        action
        for action in _as_tuple(_config().get("ACTIONS", ()))
        if isinstance(action, str)
    )


def mode() -> str:
    """``"local"`` (OnaData owns the factor) or ``"federated"`` (an IdP does).

    Read from configuration, never inferred from how a session arrived.
    Inferring it would verify locally for a session that never visited the
    IdP, which is a bypass.
    """
    return _config().get("MODE", MODE_LOCAL)


def is_local_mode() -> bool:
    """Whether OnaData, not an identity provider, owns the second factor.

    Anything other than ``"local"`` counts as federated. That fails closed,
    because grants are then demanded rather than skipped.
    """
    return mode() == MODE_LOCAL


def no_factor_policy() -> str:
    """What to do when a gated action is reached by a user with no factor.

    ``skip_gate`` lets them through. ``deny_prompt_enrol``, or any other
    value, refuses. The default is ``skip_gate`` for rollout safety, and the
    ``stepup.W001`` check warns about it.
    """
    return _config().get("NO_FACTOR_POLICY", POLICY_SKIP_GATE)
