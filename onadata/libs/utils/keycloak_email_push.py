"""
Best-effort helper for propagating a confirmed email change to Keycloak.

The caller (confirm_email_change viewset action) wraps this in try/except so
a push failure never rolls back the already-applied OnaData email update.
OnaData is the source of truth; a Keycloak FORCE mapper will self-heal if the
push is skipped.
"""
import logging

logger = logging.getLogger(__name__)


def push_email(session, email: str) -> None:
    """
    PATCH the authenticated user's email in Keycloak via the Account REST API,
    using the user's stashed OIDC access token from ``session``.

    If no access token is present the function returns silently — the caller
    already wraps us in try/except, and a missing token simply means the user
    authenticated without OIDC (e.g. token auth) so there is nothing to push.

    Keycloak's Account REST API endpoint is configured as
    ``ACCOUNT_ENDPOINT`` inside ``OPENID_CONNECT_AUTH_SERVERS["default"]``.
    We issue a POST to ``{account_endpoint}`` (empty path_suffix) with
    ``{"email": <new_email>, "emailVerified": True}``.  The Keycloak Account
    API uses POST for profile updates (not PATCH), so we use ``POST`` here.

    .. note::
        The push helper is **not** unit-tested directly.  Tests for the
        confirm_email_change action patch this function at
        ``onadata.libs.utils.keycloak_email_push.push_email``.
    """
    # ona-oidc client — imported inside the function to avoid a hard
    # dependency when the app is used without the OIDC integration.
    from oidc.client import OpenIDClient  # noqa: PLC0415

    token = session.get("oidc_access_token")
    if not token:
        return

    client = OpenIDClient("default")
    # Keycloak's Account REST API accepts POST to the account root for
    # profile updates.  ``emailVerified: true`` tells Keycloak to skip its
    # own verification flow for the address we just verified in OnaData.
    client.request_keycloak_account(
        token,
        "POST",
        "",
        {"email": email, "emailVerified": True},
    )
