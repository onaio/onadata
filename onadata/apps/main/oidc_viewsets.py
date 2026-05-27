# -*- coding: utf-8 -*-
"""
Project-owned OpenID Connect viewsets.

Subclasses ona-oidc's concrete viewset so that organization accounts cannot
establish a session via SSO. The base viewset looks a user up by the email or
username claim coming from the IdP and calls ``django.contrib.auth.login``
directly, bypassing ``onadata.apps.main.backends.ModelBackend``. Guarding only
the backend is therefore not enough; the rejection must also happen here.
"""
from django.utils.translation import gettext as _

from oidc.viewsets import UserModelOpenIDConnectViewset
from rest_framework import status
from rest_framework.response import Response

from onadata.libs.permissions import is_organization_user


class OnaOpenIDConnectViewset(  # pylint: disable=too-few-public-methods
    UserModelOpenIDConnectViewset
):
    """OpenID Connect viewset that refuses login for organization accounts."""

    authentication_classes = []

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
