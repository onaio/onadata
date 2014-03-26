import copy

from django.forms import widgets
from django.contrib.auth.models import User
from rest_framework import serializers

from onadata.apps.main.models import UserProfile
from onadata.apps.main.forms import UserProfileForm,\
    RegistrationFormUserProfile


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
        return ret

    def restore_object(self, attrs, instance=None):
        def _get_first_last_names(name):
            name_split = name.split()
            first_name = name_split[0]
            last_name = u''
            if len(name_split) > 1:
                last_name = u' '.join(name_split[1:])
            return first_name, last_name
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
            #return instance  # TODO: updates
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
