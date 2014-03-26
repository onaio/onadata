from django.contrib.auth.models import User
from rest_framework import serializers

from onadata.apps.api import tools
from onadata.apps.api.models import OrganizationProfile


class OrganizationSerializer(serializers.HyperlinkedModelSerializer):
    org = serializers.WritableField(source='user.username')
    user = serializers.HyperlinkedRelatedField(
        view_name='user-detail', lookup_field='username', read_only=True)
    creator = serializers.HyperlinkedRelatedField(
        view_name='user-detail', lookup_field='username', read_only=True)

    class Meta:
        model = OrganizationProfile
        lookup_field = 'user'
        exclude = ('created_by', 'is_organization', 'organization')

    def restore_object(self, attrs, instance=None):
        if instance:
            return super(OrganizationSerializer, self)\
                .restore_object(attrs, instance)
        org = attrs.get('user.username', None)
        org_exists = False
        try:
            User.objects.get(username=org)
        except User.DoesNotExist:
            pass
        else:
            self.errors['org'] = u'Organization %s already exists.' % org
            org_exists = True
        creator = None
        if 'request' in self.context:
            creator = self.context['request'].user
        if org and creator and not org_exists:
            attrs['organization'] = attrs.get('name')
            orgprofile = tools.create_organization_object(org, creator, attrs)
            return orgprofile
        if not org:
            self.errors['org'] = u'org is required!'
        return attrs
