# -*- coding: utf-8 -*-
"""
UserProfile Serializers.
"""
import copy
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.query import QuerySet
from django.utils import timezone
from django.utils.translation import gettext as _

import six
from django_digest.backend.db import update_partial_digests
from registration.models import RegistrationProfile
from rest_framework import serializers

from onadata.apps.api.models.temp_token import TempToken
from onadata.apps.api.tasks import send_verification_email
from onadata.apps.main.forms import RegistrationFormUserProfile
from onadata.apps.main.models import UserProfile
from onadata.libs.authentication import expired
from onadata.libs.permissions import CAN_VIEW_PROFILE, is_organization
from onadata.libs.serializers.fields.json_field import JsonField
from onadata.libs.utils.analytics import TrackObjectEvent
from onadata.libs.utils.cache_tools import IS_ORG
from onadata.libs.utils.email import get_verification_email_data, get_verification_url

RESERVED_NAMES = RegistrationFormUserProfile.RESERVED_USERNAMES
LEGAL_USERNAMES_REGEX = RegistrationFormUserProfile.legal_usernames_re


# pylint: disable=invalid-name
User = get_user_model()


def _get_first_last_names(name, limit=30):
    if not isinstance(name, six.string_types):
        return name, name

    if len(name) > (limit * 2):
        # since we are using the default django User Model, there is an
        # imposition of 30 characters on both first_name and last_name hence
        # ensure we only have 30 characters for either field

        end = limit * 2
        return name[:limit], name[limit:end]

    name_split = name.split()
    first_name = name_split[0]
    last_name = ""

    if name_split:
        last_name = " ".join(name_split[1:])

    return first_name, last_name


def _get_registration_params(attrs):
    params = copy.deepcopy(attrs)
    name = params.get("name", None)
    user = params.pop("user", None)
    if user:
        username = user.pop("username", None)
        password = user.pop("password", None)
        first_name = user.pop("first_name", None)
        last_name = user.pop("last_name", None)
        email = user.pop("email", None)

        if username:
            params["username"] = username

        if email:
            params["email"] = email

        if password:
            params.update({"password1": password, "password2": password})

        if first_name:
            params["first_name"] = first_name

        params["last_name"] = last_name or ""

    # For backward compatibility, Users who still use only name
    if name:
        first_name, last_name = _get_first_last_names(name)
        params["first_name"] = first_name
        params["last_name"] = last_name

    return params


def _send_verification_email(redirect_url, user, request):
    verification_key = user.registrationprofile.create_new_activation_key()
    verification_url = get_verification_url(redirect_url, request, verification_key)

    email_data = get_verification_email_data(
        user.email, user.username, verification_url, request
    )

    send_verification_email.delay(**email_data)


class UserProfileSerializer(serializers.HyperlinkedModelSerializer):
    """
    UserProfile serializer.
    """

    url = serializers.HyperlinkedIdentityField(
        view_name="userprofile-detail", lookup_field="user"
    )
    is_org = serializers.SerializerMethodField()
    username = serializers.CharField(
        source="user.username", min_length=3, max_length=30
    )
    name = serializers.CharField(required=False, allow_blank=True)
    first_name = serializers.CharField(
        source="user.first_name", required=False, allow_blank=True, max_length=30
    )
    last_name = serializers.CharField(
        source="user.last_name", required=False, allow_blank=True, max_length=30
    )
    email = serializers.EmailField(source="user.email")
    website = serializers.CharField(
        source="home_page", required=False, allow_blank=True
    )
    twitter = serializers.CharField(required=False, allow_blank=True)
    gravatar = serializers.ReadOnlyField()
    password = serializers.CharField(
        source="user.password", allow_blank=True, required=False
    )
    user = serializers.HyperlinkedRelatedField(
        view_name="user-detail", lookup_field="username", read_only=True
    )
    metadata = JsonField(required=False)
    # pylint: disable=invalid-name
    id = serializers.ReadOnlyField(source="user.id")
    joined_on = serializers.ReadOnlyField(source="user.date_joined")

    # pylint: disable=too-few-public-methods,missing-class-docstring
    class Meta:
        model = UserProfile
        fields = (
            "id",
            "is_org",
            "url",
            "username",
            "password",
            "first_name",
            "last_name",
            "email",
            "city",
            "country",
            "organization",
            "website",
            "twitter",
            "gravatar",
            "require_auth",
            "user",
            "metadata",
            "joined_on",
            "name",
        )
        owner_only_fields = ("metadata",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.Meta, "owner_only_fields"):
            request = self.context.get("request")
            if (
                isinstance(self.instance, QuerySet)
                or (request and request.user != self.instance.user)
                or not request
            ):
                for field in getattr(self.Meta, "owner_only_fields"):
                    self.fields.pop(field)

    def get_is_org(self, obj):
        """
        Returns True if it is an organization profile.
        """
        if obj:
            is_org = cache.get(f"{IS_ORG}{obj.pk}")
            if is_org:
                return is_org

        is_org = is_organization(obj)
        cache.set(f"{IS_ORG}{obj.pk}", is_org)
        return is_org

    def to_representation(self, instance):
        """
        Serialize objects -> primitives.
        """
        ret = super().to_representation(instance)
        if "password" in ret:
            del ret["password"]

        request = self.context["request"] if "request" in self.context else None

        if (
            "email" in ret
            and request is None
            or request.user
            and not request.user.has_perm(CAN_VIEW_PROFILE, instance)
        ):
            del ret["email"]

        if "first_name" in ret:
            ret["name"] = " ".join([ret.get("first_name"), ret.get("last_name", "")])
            ret["name"] = ret["name"].strip()

        return ret

    def update(self, instance, validated_data):
        """Update user properties."""
        params = validated_data
        password = params.get("password1")
        email = params.get("email")

        # Check password if email is being updated
        if email and not password:
            raise serializers.ValidationError(
                _("Your password is required when updating your email address.")
            )
        if password and not instance.user.check_password(password):
            raise serializers.ValidationError(_("Invalid password"))

        # get user
        instance.user.email = email or instance.user.email

        instance.user.first_name = params.get("first_name", instance.user.first_name)

        instance.user.last_name = params.get("last_name", instance.user.last_name)

        instance.user.username = params.get("username", instance.user.username)

        instance.user.save()

        if email:
            instance.metadata.update({"is_email_verified": False})
            instance.save()

            request = self.context.get("request")
            redirect_url = params.get("redirect_url")
            _send_verification_email(redirect_url, instance.user, request)

        if password:
            # force django-digest to regenerate its stored partial digests
            update_partial_digests(instance.user, password)

        return super().update(instance, params)

    @TrackObjectEvent(
        user_field="user", properties={"name": "name", "country": "country"}
    )
    def create(self, validated_data):
        """Creates a user registration profile and account."""
        params = validated_data
        request = self.context.get("request")
        metadata = {}
        username = params.get("username")
        site = Site.objects.get(pk=settings.SITE_ID)
        new_user = None
        try:
            new_user = RegistrationProfile.objects.create_inactive_user(
                username=username,
                password=params.get("password1"),
                email=params.get("email"),
                site=site,
                send_email=settings.SEND_EMAIL_ACTIVATION_API,
            )
            validate_password(params.get("password1"), user=new_user)
        except IntegrityError as e:
            raise serializers.ValidationError(
                _(f"User account {username} already exists")
            ) from e
        except ValidationError as e:
            # Delete created user object if created
            # to allow re-registration
            if new_user:
                new_user.delete()
            raise serializers.ValidationError({"password": e.messages})
        new_user.is_active = True
        new_user.first_name = params.get("first_name")
        new_user.last_name = params.get("last_name")
        new_user.save()

        if getattr(settings, "ENABLE_EMAIL_VERIFICATION", False):
            redirect_url = params.get("redirect_url")
            _send_verification_email(redirect_url, new_user, request)

        created_by = request.user
        created_by = None if created_by.is_anonymous else created_by
        metadata["last_password_edit"] = timezone.now().isoformat()
        profile = UserProfile(
            user=new_user,
            name=params.get("first_name"),
            created_by=created_by,
            city=params.get("city", ""),
            country=params.get("country", ""),
            organization=params.get("organization", ""),
            home_page=params.get("home_page", ""),
            twitter=params.get("twitter", ""),
            metadata=metadata,
        )
        profile.save()

        return profile

    def validate_username(self, value):
        """
        Validate username.
        """
        username = value.lower() if isinstance(value, str) else value

        if username.isdigit():
            raise serializers.ValidationError(_("Username cannot be purely numeric."))
        if username in RESERVED_NAMES:
            raise serializers.ValidationError(
                _(f"{username} is a reserved name, please choose another")
            )
        if not LEGAL_USERNAMES_REGEX.search(username):
            raise serializers.ValidationError(
                _(
                    "username may only contain alpha-numeric characters and "
                    "underscores"
                )
            )
        if len(username) < 3:
            raise serializers.ValidationError(
                _("Username must have 3 or more characters")
            )
        users = User.objects.filter(username=username)
        if self.instance:
            users = users.exclude(pk=self.instance.user.pk)
        if users.exists():
            raise serializers.ValidationError(_(f"{username} already exists"))

        return username

    def validate_email(self, value):
        """
        Checks if user with the same email has already been registered.
        """
        users = User.objects.filter(email=value)
        if self.instance:
            users = users.exclude(pk=self.instance.user.pk)

        if users.exists():
            raise serializers.ValidationError(
                _("This email address is already in use. ")
            )

        return value

    def validate_twitter(self, value):
        """
        Checks if the twitter handle is valid.
        """
        if isinstance(value, str) and value:
            match = re.search(r"^[A-Za-z0-9_]{1,15}$", value)
            if not match:
                raise serializers.ValidationError(
                    _(f"Invalid twitter username {value}")
                )

        return value

    def validate(self, attrs):
        params = _get_registration_params(attrs)
        if (
            not self.instance
            and params.get("name") is None
            and params.get("first_name") is None
        ):
            raise serializers.ValidationError(
                {"name": _("Either name or first_name should be provided")}
            )

        return params


class UserProfileWithTokenSerializer(serializers.HyperlinkedModelSerializer):
    """
    User Profile Serializer that includes the users API Tokens.
    """

    url = serializers.HyperlinkedIdentityField(
        view_name="userprofile-detail", lookup_field="user"
    )
    username = serializers.CharField(source="user.username")
    email = serializers.CharField(source="user.email")
    website = serializers.CharField(source="home_page", required=False)
    gravatar = serializers.ReadOnlyField()
    user = serializers.HyperlinkedRelatedField(
        view_name="user-detail", lookup_field="username", read_only=True
    )
    api_token = serializers.SerializerMethodField()
    temp_token = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = (
            "url",
            "username",
            "name",
            "email",
            "city",
            "country",
            "organization",
            "website",
            "twitter",
            "gravatar",
            "require_auth",
            "user",
            "api_token",
            "temp_token",
        )

    def get_api_token(self, obj):
        """
        Returns user's API Token.
        """
        return obj.user.auth_token.key

    def get_temp_token(self, obj):
        """
        This should return a valid temp token for this user profile.
        """
        token, created = TempToken.objects.get_or_create(user=obj.user)
        check_expired = getattr(settings, "CHECK_EXPIRED_TEMP_TOKEN", True)

        try:
            if check_expired and not created and expired(token.created):
                with transaction.atomic():
                    TempToken.objects.get(user=obj.user).delete()
                    token = TempToken.objects.create(user=obj.user)
        except IntegrityError:
            pass

        return token.key
