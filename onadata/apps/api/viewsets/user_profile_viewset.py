# -*- coding: utf-8 -*-
"""
UserProfileViewSet module.
"""

import datetime
import json
from future.moves.urllib.parse import urlencode

from past.builtins import basestring  # pylint: disable=redefined-builtin

from django.conf import settings
from django.core.validators import ValidationError
from django.db.models import Count
from django.http import HttpResponseRedirect, HttpResponseBadRequest
from django.utils.translation import ugettext as _
from django.utils import timezone

from registration.models import RegistrationProfile
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.exceptions import ParseError
from rest_framework.filters import OrderingFilter
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from onadata.apps.api.tasks import send_verification_email
from onadata.apps.api.permissions import UserProfilePermissions
from onadata.apps.api.tools import get_baseviewset_class, load_class
from onadata.apps.logger.models.instance import Instance
from onadata.apps.main.models import UserProfile
from onadata.libs.utils.email import (get_verification_email_data,
                                      get_verification_url)
from onadata.libs import filters
from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.mixins.object_lookup_mixin import ObjectLookupMixin
from onadata.libs.serializers.monthly_submissions_serializer import \
    MonthlySubmissionsSerializer
from onadata.libs.serializers.user_profile_serializer import \
    UserProfileSerializer

BaseViewset = get_baseviewset_class()  # pylint: disable=invalid-name


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
        elif isinstance(value, dict):
            return check_if_key_exists(a_key, value)
        elif isinstance(value, list):
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
        return load_class(settings.PROFILE_SERIALIZER)

    return UserProfileSerializer


def set_is_email_verified(profile, is_email_verified):
    profile.metadata.update({"is_email_verified": is_email_verified})
    profile.save()


class UserProfileViewSet(
        AuthenticateHeaderMixin,  # pylint: disable=R0901
        CacheControlMixin,
        ETagsMixin,
        ObjectLookupMixin,
        BaseViewset,
        ModelViewSet):
    """
    List, Retrieve, Update, Create/Register users.
    """
    queryset = UserProfile.objects.select_related().filter(
        user__is_active=True).exclude(
            user__username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME)
    serializer_class = serializer_from_settings()
    lookup_field = 'user'
    permission_classes = [UserProfilePermissions]
    filter_backends = (filters.UserProfileFilter, OrderingFilter)
    ordering = ('user__username', )

    def get_object(self, queryset=None):
        """Lookup user profile by pk or username"""
        if self.kwargs.get(self.lookup_field, None) is None:
            raise ParseError(
                'Expected URL keyword argument `%s`.' % self.lookup_field)
        if queryset is None:
            queryset = self.filter_queryset(self.get_queryset())

        serializer = self.get_serializer()
        lookup_field = self.lookup_field

        if self.lookup_field in serializer.get_fields():
            k = serializer.get_fields()[self.lookup_field]
            if isinstance(k, serializers.HyperlinkedRelatedField):
                lookup_field = '%s__%s' % (self.lookup_field, k.lookup_field)

        lookup = self.kwargs[self.lookup_field]
        filter_kwargs = {lookup_field: lookup}

        try:
            user_pk = int(lookup)
        except (TypeError, ValueError):
            filter_kwargs = {'%s__iexact' % lookup_field: lookup}
        else:
            filter_kwargs = {'user__pk': user_pk}

        obj = get_object_or_404(queryset, **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj

    @action(methods=['POST'], detail=True)
    def change_password(self, request, *args, **kwargs):  # noqa
        """
        Change user's password.
        """
        user_profile = self.get_object()
        current_password = request.data.get('current_password', None)
        new_password = request.data.get('new_password', None)

        if new_password:
            if user_profile.user.check_password(current_password):
                metadata = user_profile.metadata or {}
                metadata['last_password_edit'] = timezone.now().isoformat()
                user_profile.user.set_password(new_password)
                user_profile.metadata = metadata
                user_profile.user.save()
                user_profile.save()

                return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, *args, **kwargs):
        profile = self.get_object()
        metadata = profile.metadata or {}
        if request.data.get('overwrite') == 'false':
            if isinstance(request.data.get('metadata'), basestring):
                metadata_items = json.loads(
                    request.data.get('metadata')).items()
            else:
                metadata_items = request.data.get('metadata').items()

            for key, value in metadata_items:
                if check_if_key_exists(key, metadata):
                    metadata = replace_key_value(key, value, metadata)
                else:
                    metadata[key] = value

            profile.metadata = metadata
            profile.save()
            return Response(data=profile.metadata, status=status.HTTP_200_OK)

        return super(UserProfileViewSet, self).partial_update(
            request, *args, **kwargs)

    @action(methods=['GET'], detail=True)
    def monthly_submissions(self, request, *args, **kwargs):
        """ Get the total number of submissions for a user """
        profile = self.get_object()
        month_param = self.request.query_params.get('month', None)
        year_param = self.request.query_params.get('year', None)

        # check if parameters are valid
        if month_param:
            if not month_param.isdigit() or \
               int(month_param) not in range(1, 13):
                raise ValidationError(u'Invalid month provided as parameter')
        if year_param:
            if not year_param.isdigit() or len(year_param) != 4:
                raise ValidationError(u'Invalid year provided as parameter')

        # Use query parameter values for month and year
        # if none, use the current month and year
        now = datetime.datetime.now()
        month = month_param if month_param else now.month
        year = year_param if year_param else now.year

        instance_count = Instance.objects.filter(
            xform__user=profile.user,
            xform__deleted_at__isnull=True,
            date_created__year=year,
            date_created__month=month).values('xform__shared').annotate(
                num_instances=Count('id'))

        serializer = MonthlySubmissionsSerializer(instance_count, many=True)
        return Response(serializer.data[0])

    @action(detail=False)
    def verify_email(self, request, *args, **kwargs):
        verified_key_text = getattr(settings, "VERIFIED_KEY_TEXT", None)

        if not verified_key_text:
            return Response(status=status.HTTP_204_NO_CONTENT)

        redirect_url = request.query_params.get('redirect_url')
        verification_key = request.query_params.get('verification_key')
        response_message = _("Missing or invalid verification key")
        if verification_key:
            try:
                rp = RegistrationProfile.objects.get(
                    activation_key=verification_key)
            except RegistrationProfile.DoesNotExist:
                pass
            else:
                rp.activation_key = verified_key_text
                rp.save()

                set_is_email_verified(rp.user.profile, True)

                response_data = {
                    'username': rp.user.username,
                    'is_email_verified': True
                }

                if redirect_url:
                    query_params_string = urlencode(response_data)
                    redirect_url = '{}?{}'.format(redirect_url,
                                                  query_params_string)

                    return HttpResponseRedirect(redirect_url)

                return Response(response_data)

        return HttpResponseBadRequest(response_message)

    @action(methods=['POST'], detail=False)
    def send_verification_email(self, request, *args, **kwargs):
        verified_key_text = getattr(settings, "VERIFIED_KEY_TEXT", None)
        if not verified_key_text:
            return Response(status=status.HTTP_204_NO_CONTENT)

        username = request.data.get('username')
        redirect_url = request.data.get('redirect_url')
        response_message = _("Verification email has NOT been sent")

        if username:
            try:
                rp = RegistrationProfile.objects.get(user__username=username)
            except RegistrationProfile.DoesNotExist:
                pass
            else:
                set_is_email_verified(rp.user.profile, False)

                verification_key = rp.activation_key
                if verification_key == verified_key_text:
                    verification_key = (rp.user.registrationprofile.
                                        create_new_activation_key())

                verification_url = get_verification_url(
                    redirect_url, request, verification_key)

                email_data = get_verification_email_data(
                    rp.user.email, rp.user.username, verification_url, request)

                send_verification_email.delay(**email_data)
                response_message = _("Verification email has been sent")

                return Response(response_message)

        return HttpResponseBadRequest(response_message)
