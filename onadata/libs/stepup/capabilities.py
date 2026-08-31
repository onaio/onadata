# -*- coding: utf-8 -*-
"""What this deployment lets an account manage about its own credentials.

Reported by the server rather than decided by the client, because the two
must not be able to disagree. A deployment where an identity provider owns
identity has no password to change and no factor to enrol -- and a client that
decided that for itself, from its own configuration, is one deployment change
away from offering controls the server refuses.
"""

from django.conf import settings

from onadata.libs.stepup.policy import mode


def identity_is_federated() -> bool:
    """Whether an identity provider, rather than OnaData, owns credentials.

    Keyed off the step-up mode because that is the same question asked of the
    second factor: if the factor lives at the provider, so does the password
    the user would change, and neither is OnaData's to manage.
    """
    return mode() != "local"


def account_capabilities() -> dict:
    """The credential controls this deployment can honour.

    Every value here is enforced server-side as well. These exist so a client
    can avoid offering a control that would be refused, not as the refusal
    itself -- a capability a client chooses to ignore must still fail.
    """
    federated = identity_is_federated()
    # A deployment that never enabled two-factor manages none of it either:
    # /api/v1/totp/* answers 404 there, so reporting the controls as available
    # would make this endpoint the cause of the mismatch it exists to prevent.
    manages_second_factor = not federated and getattr(
        settings, "ENABLE_TWO_FACTOR", False
    )
    return {
        "password": {"change": not federated},
        "twoFactor": {
            "managedBy": "idp" if federated else "onadata",
            "enroll": manages_second_factor,
            "disable": manages_second_factor,
            "recoveryCodes": manages_second_factor,
            "verify": manages_second_factor,
        },
        # Named so a client can say WHERE to go instead of showing a dead
        # control. Empty when OnaData owns identity and there is nowhere else.
        "identityProvider": _identity_provider_name() if federated else "",
    }


def _identity_provider_name() -> str:
    """A human-facing name for the provider, for "managed by X" copy.

    Only ever what a deployment configured. There is no fallback to the
    auth-server key: those are internal slugs, and title-casing them invents
    names users do not recognise -- a slug like "acme-sso" would surface as
    "Acme Sso". Clients render generic copy when this is empty,
    which is honest, where a mangled brand name is not.
    """
    return getattr(settings, "STEP_UP_IDP_NAME", "") or ""
