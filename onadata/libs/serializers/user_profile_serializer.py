import copy
import six
import re

from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.utils.translation import ugettext as _
from registration.models import RegistrationProfile
from rest_framework import serializers
from onadata.apps.api.models.temp_token import TempToken

from onadata.apps.main.forms import UserProfileForm
from onadata.apps.main.forms import RegistrationFormUserProfile
from onadata.apps.main.models import UserProfile
from onadata.libs.serializers.fields.json_field import JsonField
from onadata.libs.permissions import CAN_VIEW_PROFILE, is_organization
from onadata.libs.authentication import expired
from onadata.libs.utils.cache_tools import IS_ORG

RESERVED_NAMES = RegistrationFormUserProfile._reserved_usernames
LEGAL_USERNAMES_REGEX = RegistrationFormUserProfile.legal_usernames_re


def _get_first_last_names(name, limit=30):
    if not isinstance(name, six.string_types):
        return name, name

    if name.__len__() > (limit * 2):
        # since we are using the default django User Model, there is an
        # imposition of 30 characters on both first_name and last_name hence
        # ensure we only have 30 characters for either field

        return name[:limit], name[limit:limit * 2]

    name_split = name.split()
    first_name = name_split[0]
    last_name = u''

    if len(name_split) > 1:
        last_name = u' '.join(name_split[1:])

    return first_name, last_name


class UserProfileSerializer(serializers.HyperlinkedModelSerializer):
    is_org = serializers.SerializerMethodField()
    username = serializers.Field(source='user.username')
    name = serializers.CharField(required=False)
    first_name = serializers.Field(source='user.first_name', required=False)
    last_name = serializers.Field(source='user.last_name', required=False)
    email = serializers.EmailField(source='user.email')
    website = serializers.Field(source='home_page', required=False)
    twitter = serializers.Field(required=False)
    gravatar = serializers.ReadOnlyField(source='gravatar')
    password = serializers.Field(source='user.password', required=False)
    user = serializers.HyperlinkedRelatedField(
        view_name='user-detail', lookup_field='username', read_only=True)
    metadata = JsonField(required=False)
    id = serializers.ReadOnlyField(source='user.id')
    joined_on = serializers.ReadOnlyField(source='user.date_joined')

    class Meta:
        model = UserProfile
        fields = ('id', 'is_org', 'url', 'username', 'password', 'first_name',
                  'last_name', 'email', 'city', 'country', 'organization',
                  'website', 'twitter', 'gravatar', 'require_auth', 'user',
                  'metadata', 'joined_on', 'name')

    def get_is_org(self, obj):
        if obj:
            is_org = cache.get('{}{}'.format(IS_ORG, obj.pk))
            if is_org:
                return is_org

        is_org = is_organization(obj)
        cache.set('{}{}'.format(IS_ORG, obj.pk), is_org)
        return is_org

    def to_representation(self, obj):
        """
        Serialize objects -> primitives.
        """
        ret = super(UserProfileSerializer, self).to_representation(obj)
        if 'password' in ret:
            del ret['password']

        request = self.context['request'] \
            if 'request' in self.context else None

        if 'email' in ret and request is None or request.user \
                and not request.user.has_perm(CAN_VIEW_PROFILE, obj):
            del ret['email']

        if 'first_name' in ret:
            ret['name'] = u' '.join([ret.get('first_name'),
                                     ret.get('last_name', "")])
            ret['name'] = ret['name'].strip()

        return ret

    def _get_params(self, attrs):
        params = copy.deepcopy(attrs)
        username = attrs.get('user.username', None)
        password = attrs.get('user.password', None)
        first_name = attrs.get('user.first_name', None)
        last_name = attrs.get('user.last_name', None)
        email = attrs.get('user.email', None)
        name = attrs.get('name', None)

        if username:
            params['username'] = username

        if email:
            params['email'] = email

        if password:
            params.update({'password1': password, 'password2': password})

        if first_name:
            params['first_name'] = first_name

        if last_name:
            params['last_name'] = last_name

        # For backward compatibility, Users who still use only name
        if name:
            first_name, last_name = \
                _get_first_last_names(name)
            params['first_name'] = first_name
            params['last_name'] = last_name

        return params

    def update(self, instance, validated_data):
        params = self._get_params(validated_data)
        form = UserProfileForm(params, instance=instance)

        # form.is_valid affects instance object for partial updates [PATCH]
        # so only use it for full updates [PUT], i.e shallow copy effect
        if not self.partial and form.is_valid():
            instance = form.save()

        # get user
        instance.user.email = params.get('email', instance.user.email)

        instance.user.first_name = params.get('first_name',
                                              instance.user.first_name)

        instance.user.last_name = params.get('last_name',
                                             instance.user.last_name)

        instance.user.username = params.get('username', instance.user.username)

        instance.user.save()

        return super(UserProfileSerializer, self).update(instance, params)

    def create(self, validated_data):
        params = self._get_params(validated_data)
        form = RegistrationFormUserProfile(params)
        # does not require captcha
        form.REGISTRATION_REQUIRE_CAPTCHA = False

        site = Site.objects.get(pk=settings.SITE_ID)
        new_user = RegistrationProfile.objects.create_inactive_user(
            username=params.get('username'),
            password=params.get('password'),
            email=params.get('email'),
            site=site,
            send_email=settings.SEND_EMAIL_ACTIVATION_API)
        new_user.is_active = True
        new_user.first_name = params.get('first_name')
        new_user.last_name = params.get('last_name')
        new_user.save()

        created_by = self.context['request'].user
        created_by = None if created_by.is_anonymous() else created_by
        profile = UserProfile(
            user=new_user, name=params.get('first_name'),
            created_by=created_by,
            city=params.get('city', u''),
            country=params.get('country', u''),
            organization=params.get('organization', u''),
            home_page=params.get('home_page', u''),
            twitter=params.get('twitter', u'')
        )
        profile.save()

        return profile

    def validate_username(self, value):
        username = value.lower() if isinstance(value, basestring) else value

        if username in RESERVED_NAMES:
            raise serializers.ValidationError(_(
                u"%s is a reserved name, please choose another" % username
            ))
        elif not LEGAL_USERNAMES_REGEX.search(username):
            raise serializers.ValidationError(_(
                u"username may only contain alpha-numeric characters and "
                u"underscores"
            ))
        try:
            User.objects.get(username=username)
        except User.DoesNotExist:
            value = username

        return value

    def validate_email(self, value):

        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(_(
                u"This email address is already in use. "
            ))

        return value

    def validate_twitter(self, value):
        if isinstance(value, basestring) and len(value) > 0:
            match = re.search(r"^[A-Za-z0-9_]{1,15}$", value)
            if not match:
                raise serializers.ValidationError(_(
                    u"Invalid twitter username {}".format(value)
                ))

        return value

    def validate(self, attrs):
        if (attrs.get('name') is None) and\
                (attrs.get('user.first_name') is None):
            raise serializers.ValidationError(
                u"Either name or first_name should be provided")

        return attrs


class UserProfileWithTokenSerializer(UserProfileSerializer):
    username = serializers.Field(source='user.username')
    email = serializers.Field(source='user.email')
    website = serializers.Field(source='home_page', required=False)
    gravatar = serializers.ReadOnlyField()
    password = serializers.Field(source='user.password', required=False)
    user = serializers.HyperlinkedRelatedField(
        view_name='user-detail', lookup_field='username', read_only=True)
    api_token = serializers.SerializerMethodField()
    temp_token = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = ('url', 'username', 'name', 'password', 'email', 'city',
                  'country', 'organization', 'website', 'twitter', 'gravatar',
                  'require_auth', 'user', 'api_token', 'temp_token')

    def get_api_token(self, object):
        return object.user.auth_token.key

    def get_temp_token(self, object):
        """This should return a valid temp token for this user profile."""
        token, created = TempToken.objects.get_or_create(user=object.user)

        if not created and expired(token.created):
            token.delete()
            token = TempToken.objects.create(user=object.user)

        return token.key
