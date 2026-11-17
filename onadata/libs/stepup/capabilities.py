# -*- coding: utf-8 -*-
"""What this deployment lets an account manage about its own credentials.

The server reports this so a client cannot disagree with it. A deployment
where an identity provider owns identity has no password to change and no
factor to enrol.
"""

from django.conf import settings

from onadata.libs.stepup.policy import is_local_mode


def identity_is_federated() -> bool:
    """Whether an identity provider, rather than OnaData, owns credentials.

    Follows the step-up mode. If the provider owns the second factor, it also
    owns the password.
    """
    return not is_local_mode()


def account_capabilities() -> dict:
    """The credential controls this deployment can honour.

    The server also enforces the ``twoFactor`` values. The ``/totp`` routes
    answer 409 when OnaData does not own the factor. ``password.change`` is
    advice only, and the password routes stay open.
    """
    federated = identity_is_federated()
    # Without ENABLE_TWO_FACTOR, /api/v1/totp/* answers 404, so offer nothing.
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
        # Tells a client where the user manages credentials. Empty when
        # OnaData owns identity.
        "identityProvider": _identity_provider_name() if federated else "",
    }


def _identity_provider_name() -> str:
    """The provider's display name, from ``STEP_UP_IDP_NAME``.

    Do not derive it from the auth-server key. Keys are internal slugs that
    users do not recognise.
    """
    return getattr(settings, "STEP_UP_IDP_NAME", "") or ""
