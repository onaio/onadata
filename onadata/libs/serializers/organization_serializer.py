from django.contrib.auth.models import User
from django.core.validators import ValidationError
from rest_framework import serializers
from guardian.shortcuts import get_perms

from onadata.apps.api import tools
from onadata.apps.api.models import OrganizationProfile
from onadata.apps.api.tools import get_organization_members
from onadata.apps.main.forms import RegistrationFormUserProfile
from onadata.libs.permissions import MemberRole, OwnerRole


def get_role_for_org(user, organization):
    return OwnerRole.name if 'is_org_owner' in get_perms(
        user, organization) else MemberRole.name


class OrganizationSerializer(serializers.HyperlinkedModelSerializer):
    org = serializers.WritableField(source='user.username')
    user = serializers.HyperlinkedRelatedField(
        view_name='user-detail', lookup_field='username', read_only=True)
    creator = serializers.HyperlinkedRelatedField(
        view_name='user-detail', lookup_field='username', read_only=True)
    users = serializers.SerializerMethodField('get_org_permissions')

    class Meta:
        model = OrganizationProfile
        lookup_field = 'user'
        exclude = ('created_by', 'is_organization', 'organization')

    def restore_object(self, attrs, instance=None):
        if instance:
            return super(OrganizationSerializer, self)\
                .restore_object(attrs, instance)

        org = attrs.get('user.username', None)
        org_name = attrs.get('name', None)
        org_exists = False
        creator = None

        try:
            User.objects.get(username=org)
        except User.DoesNotExist:
            pass
        else:
            self.errors['org'] = u'Organization %s already exists.' % org
            org_exists = True

        if 'request' in self.context:
            creator = self.context['request'].user

        if org and org_name and creator and not org_exists:
            attrs['organization'] = org_name
            orgprofile = tools.create_organization_object(org, creator, attrs)

            return orgprofile

        if not org:
            self.errors['org'] = u'org is required!'

        if not org_name:
            self.errors['name'] = u'name is required!'

        return attrs

    def validate_org(self, attrs, source):
        org = attrs[source].lower()
        if org in RegistrationFormUserProfile._reserved_usernames:
            raise ValidationError(
                u"%s is a reserved name, please choose another" % org)
        elif not RegistrationFormUserProfile.legal_usernames_re.search(org):
            raise ValidationError(
                u'organization may only contain alpha-numeric characters and '
                u'underscores')
        try:
            User.objects.get(username=org)
        except User.DoesNotExist:
            attrs[source] = org

            return attrs
        raise ValidationError(u'%s already exists' % org)

    def get_org_permissions(self, obj):
        members = get_organization_members(obj)

        return [{
            'user': u.username,
            'role': get_role_for_org(u, obj)
        } for u in members]
