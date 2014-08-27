import copy
import six

from django.forms import widgets
from django.contrib.auth.models import User
from django.core.validators import ValidationError
from rest_framework import serializers

from onadata.apps.main.models import UserProfile
from onadata.apps.main.forms import UserProfileForm,\
    RegistrationFormUserProfile
from onadata.libs.permissions import CAN_VIEW_PROFILE


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
    username = serializers.WritableField(source='user.username')
    email = serializers.WritableField(source='user.email')
    website = serializers.WritableField(source='home_page', required=False)
    gravatar = serializers.Field(source='gravatar')
    password = serializers.WritableField(
        source='user.password', widget=widgets.PasswordInput(), required=False)
    user = serializers.HyperlinkedRelatedField(
        view_name='user-detail', lookup_field='username', read_only=True)

    class Meta:
        model = UserProfile
        fields = ('url', 'username', 'name', 'password', 'email', 'city',
                  'country', 'organization', 'website', 'twitter', 'gravatar',
                  'require_auth', 'user')
        lookup_field = 'user'

    def to_native(self, obj):
        """
        Serialize objects -> primitives.
        """
        ret = super(UserProfileSerializer, self).to_native(obj)
        if 'password' in ret:
            del ret['password']

        request = self.context['request'] \
            if 'request' in self.context else None

        if 'email' in ret and request is None or request.user \
                and not request.user.has_perm(CAN_VIEW_PROFILE, obj):
            del ret['email']

        return ret

    def restore_object(self, attrs, instance=None):
        params = copy.deepcopy(attrs)
        username = attrs.get('user.username', None)
        password = attrs.get('user.password', None)
        name = attrs.get('name', None)
        email = attrs.get('user.email', None)

        if username:
            params['username'] = username

        if email:
            params['email'] = email

        if password:
            params.update({'password1': password, 'password2': password})

        if instance:
            form = UserProfileForm(params, instance=instance)

            # form.is_valid affects instance object for partial updates [PATCH]
            # so only use it for full updates [PUT], i.e shallow copy effect
            if not self.partial and form.is_valid():
                instance = form.save()

            # get user
            if email:
                instance.user.email = form.cleaned_data['email']

            if name:
                first_name, last_name = _get_first_last_names(name)
                instance.user.first_name = first_name
                instance.user.last_name = last_name

            if email or name:
                instance.user.save()

            return super(
                UserProfileSerializer, self).restore_object(attrs, instance)

        form = RegistrationFormUserProfile(params)
        # does not require captcha
        form.REGISTRATION_REQUIRE_CAPTCHA = False

        if form.is_valid():
            first_name, last_name = _get_first_last_names(name)
            new_user = User(username=username, first_name=first_name,
                            last_name=last_name, email=email)
            new_user.set_password(password)
            new_user.save()
            created_by = self.context['request'].user
            created_by = None if created_by.is_anonymous() else created_by
            profile = UserProfile(
                user=new_user, name=attrs.get('name', u''),
                created_by=created_by,
                city=attrs.get('city', u''),
                country=attrs.get('country', u''),
                organization=attrs.get('organization', u''),
                home_page=attrs.get('home_page', u''),
                twitter=attrs.get('twitter', u''))

            return profile

        else:
            self.errors.update(form.errors)

        return attrs

    def validate_username(self, attrs, source):
        if self.context['request'].method == 'PATCH':

            return attrs

        username = attrs[source].lower()
        form = RegistrationFormUserProfile
        if username in form._reserved_usernames:
            raise ValidationError(
                u"%s is a reserved name, please choose another" % username)
        elif not form.legal_usernames_re.search(username):
            raise ValidationError(
                u'username may only contain alpha-numeric characters and '
                u'underscores')
        try:
            User.objects.get(username=username)
        except User.DoesNotExist:
            attrs[source] = username

            return attrs
        raise ValidationError(u'%s already exists' % username)


class UserProfileWithTokenSerializer(UserProfileSerializer):
    username = serializers.WritableField(source='user.username')
    email = serializers.WritableField(source='user.email')
    website = serializers.WritableField(source='home_page', required=False)
    gravatar = serializers.Field(source='gravatar')
    password = serializers.WritableField(
        source='user.password', widget=widgets.PasswordInput(), required=False)
    user = serializers.HyperlinkedRelatedField(
        view_name='user-detail', lookup_field='username', read_only=True)
    api_token = serializers.SerializerMethodField('get_api_token')

    class Meta:
        model = UserProfile
        fields = ('url', 'username', 'name', 'password', 'email', 'city',
                  'country', 'organization', 'website', 'twitter', 'gravatar',
                  'require_auth', 'user', 'api_token')
        lookup_field = 'user'

    def get_api_token(self, object):
        return object.user.auth_token.key
