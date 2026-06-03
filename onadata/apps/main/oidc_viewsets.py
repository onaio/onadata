# -*- coding: utf-8 -*-
"""
Project-owned OpenID Connect viewsets.

Subclasses ona-oidc's concrete viewset so that organization accounts cannot
establish a session via SSO. The base viewset looks a user up by the email or
username claim coming from the IdP and calls ``django.contrib.auth.login``
directly, bypassing ``onadata.apps.main.backends.ModelBackend``. Guarding only
the backend is therefore not enough; the rejection must also happen here.
"""

from django.conf import settings
from django.utils.translation import gettext as _

from oidc.viewsets import SSO_COOKIE_NAME, UserModelOpenIDConnectViewset
from rest_framework import status
from rest_framework.response import Response

from onadata.apps.main.models.user_profile import UserProfile
from onadata.libs.permissions import is_organization_user


class OnaOpenIDConnectViewset(  # pylint: disable=too-few-public-methods
    UserModelOpenIDConnectViewset
):
    """OpenID Connect viewset that refuses login for organization accounts."""

    authentication_classes = []

    def login(self, request, **kwargs):
        # Evict stale auth cookies a partly-logged-out browser may still
        # be sending; without this, a 401 from the downstream callback
        # carries a WWW-Authenticate challenge and pops the browser's
        # native sign-in dialog mid-OIDC-flow. ``csrftoken`` is cleared
        # by the base.
        response = super().login(request, **kwargs)
        current_host = request.get_host().split(":")[0]
        response.delete_cookie(
            "sessionid",
            domain=getattr(settings, "SESSION_COOKIE_DOMAIN", None) or current_host,
            path=getattr(settings, "SESSION_COOKIE_PATH", "/"),
            samesite=getattr(settings, "SESSION_COOKIE_SAMESITE", "Lax"),
        )
        # Attrs must mirror the success path's set_cookie or the delete won't match.
        response.delete_cookie(
            SSO_COOKIE_NAME,
            domain=self.cookie_domain,
            path=self.cookie_path,
            samesite=self.cookie_samesite,
        )
        response.delete_cookie("messages")
        return response

    def generate_successful_response(self, request, user, *args, **kwargs):
        # Signature kept permissive (*args/**kwargs) to track the ona-oidc base
        # across versions; only ``user`` is needed for the organization check.
        if is_organization_user(user):
            return Response(
                {
                    "error": _(
                        "Organization accounts cannot sign in via SSO. "
                        "Sign in with your own member account instead."
                    ),
                    "error_title": _("Organization account sign-in not allowed"),
                },
                status=status.HTTP_403_FORBIDDEN,
                template_name="oidc/oidc_unrecoverable_error.html",
            )
        return super().generate_successful_response(request, user, *args, **kwargs)

    def is_session_allowed(self, user):
        # Mirror the login org-rejection: an org account must not be able to
        # restore a session via the challenge-free ``session`` probe either.
        return not is_organization_user(user)

    def get_session_data(self, user, request):
        data = super().get_session_data(user, request)
        profile, _created = UserProfile.objects.get_or_create(user=user)
        data.update(
            {
                "name": profile.name,
                "gravatar": profile.gravatar,
                "require_auth": profile.require_auth,
            }
        )
        return data
