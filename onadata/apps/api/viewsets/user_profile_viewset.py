# -*- coding: utf-8 -*-
"""
UserProfileViewSet module.
"""

import datetime
import json

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.validators import ValidationError
from django.db.models import Count
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.utils import timezone
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _

from multidb.pinning import use_master
from registration.models import RegistrationProfile
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.exceptions import ParseError, PermissionDenied
from rest_framework.filters import OrderingFilter
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from six.moves.urllib.parse import urlencode

from onadata.apps.api.permissions import UserProfilePermissions
from onadata.apps.api.tasks import send_verification_email
from onadata.apps.api.tools import get_baseviewset_class
from onadata.apps.logger.models.instance import Instance
from onadata.apps.main.models import UserProfile
from onadata.libs import filters
from onadata.libs.mixins.authenticate_header_mixin import AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.mixins.object_lookup_mixin import ObjectLookupMixin
from onadata.libs.serializers.monthly_submissions_serializer import (
    MonthlySubmissionsSerializer,
)
from onadata.libs.serializers.user_profile_serializer import UserProfileSerializer
from onadata.libs.utils.cache_tools import (
    CHANGE_PASSWORD_ATTEMPTS,
    LOCKOUT_CHANGE_PASSWORD_USER,
    USER_PROFILE_PREFIX,
    safe_delete,
)
from onadata.libs.utils.email import get_verification_email_data, get_verification_url
from onadata.libs.utils.user_auth import invalidate_and_regen_tokens

BaseViewset = get_baseviewset_class()  # pylint: disable=invalid-name
LOCKOUT_TIME = getattr(settings, "LOCKOUT_TIME", 1800)
MAX_CHANGE_PASSWORD_ATTEMPTS = getattr(settings, "MAX_CHANGE_PASSWORD_ATTEMPTS", 10)


def replace_key_value(lookup, new_value, expected_dict):
    """
    Replaces the value matching the key 'lookup' in the 'expected_dict' with
    the new value 'new_value'.
    """
    for key, value in expected_dict.items():
        if lookup == key:
            if isinstance(value, dict) and isinstance(new_value, dict):
                value.update(new_value)
            else:
                expected_dict[key] = new_value
        elif isinstance(value, dict):
            expected_dict[key] = replace_key_value(lookup, new_value, value)
    return expected_dict


def check_if_key_exists(a_key, expected_dict):
    """
    Return True or False if a_key exists in the expected_dict dictionary.
    """
    for key, value in expected_dict.items():
        if key == a_key:
            return True
        if isinstance(value, dict):
            return check_if_key_exists(a_key, value)
        if isinstance(value, list):
            for list_item in value:
                if isinstance(list_item, dict):
                    return check_if_key_exists(a_key, list_item)
    return False


def serializer_from_settings():
    """
    Return a serilizer class configured in settings.PROFILE_SERIALIZER or
    default to UserProfileSerializer.
    """
    if settings.PROFILE_SERIALIZER:
        return import_string(settings.PROFILE_SERIALIZER)

    return UserProfileSerializer


def set_is_email_verified(profile, is_email_verified):
    """Sets is_email_verified value in the profile's metadata object."""
    profile.metadata.update({"is_email_verified": is_email_verified})
    profile.save()


def check_user_lockout(request):
    """Returns the error object with lockout error message."""
    username = request.user.username
    lockout = cache.get(f"{LOCKOUT_CHANGE_PASSWORD_USER}{username}")
    if lockout:
        time_locked_out = datetime.datetime.now() - datetime.datetime.strptime(
            lockout, "%Y-%m-%dT%H:%M:%S"
        )
        remaining_time = round((LOCKOUT_TIME - time_locked_out.seconds) / 60)
        response_obj = {
            "error": _(
                "Too many password reset attempts. "
                f"Try again in {remaining_time} minutes"
            )
        }
        return response_obj
    return None


def change_password_attempts(request):
    """Track number of login attempts made by user within a specified amount
    of time"""
    username = request.user.username
    password_attempts = f"{CHANGE_PASSWORD_ATTEMPTS}{username}"
    attempts = cache.get(password_attempts)

    if attempts:
        cache.incr(password_attempts)
        attempts = cache.get(password_attempts)
        if attempts >= MAX_CHANGE_PASSWORD_ATTEMPTS:
            cache.set(
                f"{LOCKOUT_CHANGE_PASSWORD_USER}{username}",
                datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                LOCKOUT_TIME,
            )
            if check_user_lockout(request):
                return check_user_lockout(request)

        return attempts

    cache.set(password_attempts, 1)

    return 1


# pylint: disable=too-many-ancestors
class UserProfileViewSet(
    AuthenticateHeaderMixin,
    CacheControlMixin,
    ETagsMixin,
    ObjectLookupMixin,
    BaseViewset,
    ModelViewSet,
):
    """
    List, Retrieve, Update, Create/Register users.
    """

    queryset = (
        UserProfile.objects.select_related()
        .filter(user__is_active=True)
        .exclude(user__username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME)
    )
    serializer_class = serializer_from_settings()
    lookup_field = "user"
    permission_classes = [UserProfilePermissions]
    filter_backends = (filters.UserProfileFilter, OrderingFilter)
    ordering = ("user__username",)

    def get_object(self, queryset=None):
        """Lookup user profile by pk or username"""
        if self.kwargs.get(self.lookup_field, None) is None:
            raise ParseError(_(f"Expected URL keyword argument `{self.lookup_field}`."))

        if queryset is None:
            queryset = self.filter_queryset(self.get_queryset())

        serializer = self.get_serializer()
        lookup_field = self.lookup_field

        if self.lookup_field in serializer.get_fields():
            k = serializer.get_fields()[self.lookup_field]
            if isinstance(k, serializers.HyperlinkedRelatedField):
                lookup_field = f"{self.lookup_field}__{k.lookup_field}"

        lookup = self.kwargs[self.lookup_field]
        filter_kwargs = {lookup_field: lookup}

        try:
            user_pk = int(lookup)
        except (TypeError, ValueError):
            filter_kwargs = {f"{lookup_field}__iexact": lookup}
        else:
            filter_kwargs = {"user__pk": user_pk}

        obj = get_object_or_404(queryset, **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj

    def update(self, request, *args, **kwargs):
        """Update user in cache and db"""
        username = kwargs.get("user")
        response = super().update(request, *args, **kwargs)
        cache.set(f"{USER_PROFILE_PREFIX}{username}", response.data)
        return response

    def retrieve(self, request, *args, **kwargs):
        """Get user profile from cache or db"""
        username = kwargs.get("user")
        cached_user = cache.get(f"{USER_PROFILE_PREFIX}{username}")
        if cached_user:
            return Response(cached_user)
        response = super().retrieve(request, *args, **kwargs)
        return response

    def create(self, request, *args, **kwargs):
        """Create and cache user profile"""
        disable_user_creation = getattr(settings, "DISABLE_CREATING_USERS", False)
        if disable_user_creation:
            raise PermissionDenied(
                _("You do not have permission to create user.")
            )

        response = super().create(request, *args, **kwargs)
        profile = response.data
        user_name = profile.get("username")
        cache.set(f"{USER_PROFILE_PREFIX}{user_name}", profile)
        return response

    @action(methods=["POST"], detail=True)
    def change_password(self, request, *args, **kwargs):  # noqa
        """
        Change user's password.
        """
        # clear cache
        safe_delete(f"{USER_PROFILE_PREFIX}{request.user.username}")
        user_profile = self.get_object()
        current_password = request.data.get("current_password", None)
        new_password = request.data.get("new_password", None)
        lock_out = check_user_lockout(request)

        if not current_password or not new_password:
            return Response(
                data={
                    "error": _(
                        "current_password and new_password fields cannot be blank"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if lock_out:
            return Response(data=lock_out, status=status.HTTP_400_BAD_REQUEST)

        if not user_profile.user.check_password(current_password):
            response = change_password_attempts(request)
            if isinstance(response, int):
                limits_remaining = MAX_CHANGE_PASSWORD_ATTEMPTS - response
                response = {
                    "error": _(
                        "Invalid password. "
                        f"You have {limits_remaining} attempts left."
                    )
                }
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_password(new_password, user=user_profile.user)
        except ValidationError as error:
            return Response(
                data={"errors": error.messages}, status=status.HTTP_400_BAD_REQUEST
            )

        data = {"username": user_profile.user.username}
        metadata = user_profile.metadata or {}
        metadata["last_password_edit"] = timezone.now().isoformat()
        user_profile.user.set_password(new_password)
        user_profile.metadata = metadata
        user_profile.user.save()
        user_profile.save()
        data.update(invalidate_and_regen_tokens(user=user_profile.user))

        return Response(status=status.HTTP_200_OK, data=data)

    def partial_update(self, request, *args, **kwargs):
        """Allows for partial update of the user profile data."""
        profile = self.get_object()
        metadata = profile.metadata or {}
        if request.data.get("overwrite") == "false":
            if isinstance(request.data.get("metadata"), str):
                metadata_items = json.loads(request.data.get("metadata")).items()
            else:
                metadata_items = request.data.get("metadata").items()

            for key, value in metadata_items:
                if check_if_key_exists(key, metadata):
                    metadata = replace_key_value(key, value, metadata)
                else:
                    metadata[key] = value

            profile.metadata = metadata
            profile.save()
            return Response(data=profile.metadata, status=status.HTTP_200_OK)

        return super().partial_update(request, *args, **kwargs)

    @action(methods=["GET"], detail=True)
    def monthly_submissions(self, request, *args, **kwargs):
        """Get the total number of submissions for a user"""
        # clear cache
        safe_delete(f"{USER_PROFILE_PREFIX}{request.user.username}")
        profile = self.get_object()
        month_param = self.request.query_params.get("month", None)
        year_param = self.request.query_params.get("year", None)

        # check if parameters are valid
        if month_param:
            if not month_param.isdigit() or int(month_param) not in range(1, 13):
                raise ValidationError("Invalid month provided as parameter")
        if year_param:
            if not year_param.isdigit() or len(year_param) != 4:
                raise ValidationError("Invalid year provided as parameter")

        # Use query parameter values for month and year
        # if none, use the current month and year
        now = datetime.datetime.now()
        month = month_param if month_param else now.month
        year = year_param if year_param else now.year

        instance_count = (
            Instance.objects.filter(
                xform__user=profile.user,
                xform__deleted_at__isnull=True,
                date_created__year=year,
                date_created__month=month,
            )
            .values("xform__shared")
            .annotate(num_instances=Count("id"))
        )

        serializer = MonthlySubmissionsSerializer(instance_count, many=True)
        return Response(serializer.data[0])

    @action(detail=False)
    def verify_email(self, request, *args, **kwargs):
        """Accpet's email verification token and marks the profile as verified."""
        verified_key_text = getattr(settings, "VERIFIED_KEY_TEXT", None)

        if not verified_key_text:
            return Response(status=status.HTTP_204_NO_CONTENT)

        redirect_url = request.query_params.get("redirect_url")
        verification_key = request.query_params.get("verification_key")
        response_message = _("Missing or invalid verification key")
        if verification_key:
            registration_profile = None
            try:
                registration_profile = RegistrationProfile.objects.select_related(
                    "user", "user__profile"
                ).get(activation_key=verification_key)
            except RegistrationProfile.DoesNotExist:
                with use_master:
                    try:
                        registration_profile = (
                            RegistrationProfile.objects.select_related(
                                "user", "user__profile"
                            ).get(activation_key=verification_key)
                        )
                    except RegistrationProfile.DoesNotExist:
                        pass

            if registration_profile:
                registration_profile.activation_key = verified_key_text
                registration_profile.save()

                username = registration_profile.user.username
                set_is_email_verified(registration_profile.user.profile, True)
                # Clear profiles cache
                safe_delete(f"{USER_PROFILE_PREFIX}{username}")

                response_data = {"username": username, "is_email_verified": True}

                if redirect_url:
                    query_params_string = urlencode(response_data)
                    redirect_url = f"{redirect_url}?{query_params_string}"

                    return HttpResponseRedirect(redirect_url)

                return Response(response_data)

        return HttpResponseBadRequest(response_message)

    @action(methods=["POST"], detail=False)
    def send_verification_email(self, request, *args, **kwargs):
        """Sends verification email on user profile registration."""
        verified_key_text = getattr(settings, "VERIFIED_KEY_TEXT", None)
        if not verified_key_text:
            return Response(status=status.HTTP_204_NO_CONTENT)

        username = request.data.get("username")
        redirect_url = request.data.get("redirect_url")
        response_message = _("Verification email has NOT been sent")

        if username:
            try:
                registration_profile = RegistrationProfile.objects.get(
                    user__username=username
                )
            except RegistrationProfile.DoesNotExist:
                pass
            else:
                user = registration_profile.user
                set_is_email_verified(user.profile, False)

                verification_key = registration_profile.activation_key
                if verification_key == verified_key_text:
                    verification_key = (
                        user.registrationprofile.create_new_activation_key()
                    )

                verification_url = get_verification_url(
                    redirect_url, request, verification_key
                )

                email_data = get_verification_email_data(
                    user.email,
                    user.username,
                    verification_url,
                    request,
                )

                send_verification_email.delay(**email_data)
                response_message = _("Verification email has been sent")

                return Response(response_message)

        return HttpResponseBadRequest(response_message)
