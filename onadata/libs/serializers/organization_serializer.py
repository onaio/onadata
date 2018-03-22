from past.builtins import basestring

from django.contrib.auth.models import User
from django.utils.translation import ugettext as _

from rest_framework import serializers

from onadata.apps.api import tools
from onadata.apps.api.models import OrganizationProfile
from onadata.apps.api.tools import (_get_first_last_names,
                                    get_organization_members)
from onadata.apps.main.forms import RegistrationFormUserProfile
from onadata.libs.permissions import get_role_in_org
from onadata.libs.serializers.fields.json_field import JsonField


class OrganizationSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='organizationprofile-detail', lookup_field='user')
    org = serializers.CharField(source='user.username', max_length=30)
    user = serializers.HyperlinkedRelatedField(
        view_name='user-detail', lookup_field='username', read_only=True)
    creator = serializers.HyperlinkedRelatedField(
        view_name='user-detail', lookup_field='username', read_only=True)
    users = serializers.SerializerMethodField()
    metadata = JsonField(required=False)
    name = serializers.CharField(max_length=30)

    class Meta:
        model = OrganizationProfile
        exclude = ('created_by', 'is_organization', 'organization')

    def update(self, instance, validated_data):
        # update the user model
        if 'name' in validated_data:
            first_name, last_name = \
                _get_first_last_names(validated_data.get('name'))
            instance.user.first_name = first_name
            instance.user.last_name = last_name
            instance.user.save()

        return super(OrganizationSerializer, self).update(
            instance, validated_data
        )

    def create(self, validated_data):
        org = validated_data.get('user')
        if org:
            org = org.get('username')

        org_name = validated_data.get('name', None)
        creator = None

        if 'request' in self.context:
            creator = self.context['request'].user

        validated_data['organization'] = org_name

        profile = tools.create_organization_object(org, creator,
                                                   validated_data)
        profile.save()

        return profile

    def validate_org(self, value):
        org = value.lower() if isinstance(value, basestring) else value

        if org in RegistrationFormUserProfile.RESERVED_USERNAMES:
            raise serializers.ValidationError(_(
                u"%s is a reserved name, please choose another" % org
            ))
        elif not RegistrationFormUserProfile.legal_usernames_re.search(org):
            raise serializers.ValidationError(_(
                u"Organization may only contain alpha-numeric characters and "
                u"underscores"
            ))
        try:
            User.objects.get(username=org)
        except User.DoesNotExist:
            return org

        raise serializers.ValidationError(_(
            u"Organization %s already exists." % org
        ))

    def get_users(self, obj):
        members = get_organization_members(obj) if obj else []

        return [{
            'user': u.username,
            'role': get_role_in_org(u, obj),
            'first_name': u.first_name,
            'last_name': u.last_name,
            'gravatar': u.profile.gravatar,
            'metadata': u.profile.metadata,
        } for u in members]
