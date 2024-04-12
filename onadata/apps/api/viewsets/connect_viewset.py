# -*- coding: utf-8 -*-
"""
The /api/v1/user API implementation

User authentication API support to access API tokens.
"""
from django.core.exceptions import MultipleObjectsReturned
from django.utils import timezone
from django.utils.translation import gettext as _

from multidb.pinning import use_master
from rest_framework import mixins, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import ParseError
from rest_framework.response import Response

from onadata.apps.api.models.odk_token import ODKToken
from onadata.apps.api.models.temp_token import TempToken
from onadata.apps.api.permissions import ConnectViewsetPermissions
from onadata.apps.api.viewsets.user_profile_viewset import serializer_from_settings
from onadata.apps.main.models.user_profile import UserProfile
from onadata.libs.mixins.authenticate_header_mixin import AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.mixins.object_lookup_mixin import ObjectLookupMixin
from onadata.libs.serializers.password_reset_serializer import (
    PasswordResetChangeSerializer,
    PasswordResetSerializer,
    get_user_from_uid,
)
from onadata.libs.serializers.project_serializer import ProjectSerializer
from onadata.libs.serializers.user_profile_serializer import (
    UserProfileWithTokenSerializer,
)
from onadata.libs.utils.cache_tools import USER_PROFILE_PREFIX, cache
from onadata.settings.common import DEFAULT_SESSION_EXPIRY_TIME


def user_profile_w_token_response(request, status_code):
    """Returns authenticated user profile"""

    if request and not request.user.is_anonymous:
        session = getattr(request, "session")
        if not session.session_key:
            # login user to create session token
            session.set_expiry(DEFAULT_SESSION_EXPIRY_TIME)

    try:
        user_profile = request.user.profile
    except UserProfile.DoesNotExist:
        user_profile = cache.get(f"{USER_PROFILE_PREFIX}{request.user.username}")
        if not user_profile:
            with use_master:
                user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
                serializer = serializer_from_settings()(
                    user_profile, context={"request": request}
                )
                cache.set(
                    f"{USER_PROFILE_PREFIX}{request.user.username}", serializer.data
                )

    serializer = UserProfileWithTokenSerializer(
        instance=user_profile, context={"request": request}
    )

    return Response(serializer.data, status=status_code)


# pylint: disable=too-many-ancestors
class ConnectViewSet(
    mixins.CreateModelMixin,
    AuthenticateHeaderMixin,
    CacheControlMixin,
    ETagsMixin,
    ObjectLookupMixin,
    viewsets.GenericViewSet,
):
    """
    This endpoint allows you retrieve the authenticated user's profile info.
    """

    lookup_field = "user"
    queryset = UserProfile.objects.all()
    permission_classes = (ConnectViewsetPermissions,)
    serializer_class = UserProfileWithTokenSerializer

    def create(self, request, *args, **kwargs):
        return user_profile_w_token_response(request, status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        """
        Implements the List endpoint - returns authentication tokens for current user.
        """
        return user_profile_w_token_response(request, status.HTTP_200_OK)

    @action(methods=["GET"], detail=True)
    def starred(self, request, *args, **kwargs):
        """Return projects starred for this user."""
        user_profile = self.get_object()
        user = user_profile.user
        projects = user.project_stars.all()
        serializer = ProjectSerializer(
            projects, context={"request": request}, many=True
        )

        return Response(data=serializer.data)

    @action(methods=["POST"], detail=False)
    def reset(self, request, *args, **kwargs):
        """
        Implements the /reset endpoint

        Allows a user to reset and change their password.
        """
        context = {"request": request}
        data = request.data if request.data is not None else {}
        if "token" in request.data:
            serializer = PasswordResetChangeSerializer(data=data, context=context)

            if serializer.is_valid():
                serializer.save()
                user = get_user_from_uid(serializer.data["uid"])
                return Response(
                    data={"username": user.username}, status=status.HTTP_200_OK
                )
        else:
            serializer = PasswordResetSerializer(data=data, context=context)
            if serializer.is_valid():
                serializer.save()
                return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=["DELETE"], detail=False)
    def expire(self, request, *args, **kwargs):
        """
        Implements the /expire endpoint

        Allows a user to expire a TempToken.
        """
        try:
            TempToken.objects.get(user=request.user).delete()
        except TempToken.DoesNotExist as exc:
            raise ParseError(_("Temporary token not found!")) from exc

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=["GET"], detail=False)
    def regenerate_auth_token(self, request, *args, **kwargs):
        """
        Implements the /regenerate_auth_token endpoint

        Allows a user to expire and create a new API Token.
        """
        try:
            Token.objects.get(user=request.user).delete()
        except Token.DoesNotExist as exc:
            raise ParseError(_(" Token not found!")) from exc

        new_token = Token.objects.create(user=request.user)

        return Response(data=new_token.key, status=status.HTTP_201_CREATED)

    @action(methods=["GET", "POST"], detail=False)
    def odk_token(self, request, *args, **kwargs):
        """
        Implements the /odk_token endpoint

        Allows a user to get or create or expire an ODKToken for use with ODK Collect.
        """
        user = request.user
        status_code = status.HTTP_200_OK

        if request.method == "GET":
            try:
                token, created = ODKToken.objects.get_or_create(
                    user=user, status=ODKToken.ACTIVE
                )

                if not token.expires or (
                    not created and timezone.now() > token.expires
                ):
                    token.status = ODKToken.INACTIVE
                    token.save()
                    token = ODKToken.objects.create(user=user)
            except MultipleObjectsReturned:
                ODKToken.objects.filter(user=user, status=ODKToken.ACTIVE).update(
                    status=ODKToken.INACTIVE
                )
                token = ODKToken.objects.create(user=user)

        if request.method == "POST":
            # Regenerates the ODK Token if one is already existant
            ODKToken.objects.filter(user=user, status=ODKToken.ACTIVE).update(
                status=ODKToken.INACTIVE
            )

            token = ODKToken.objects.create(user=user)
            status_code = status.HTTP_201_CREATED

        return Response(
            data={"odk_token": token.raw_key, "expires": token.expires},
            status=status_code,
        )
