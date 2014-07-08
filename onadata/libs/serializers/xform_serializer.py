from django.forms import widgets
from guardian.shortcuts import get_users_with_perms, get_perms
from rest_framework import serializers

from onadata.apps.logger.models import XForm
from onadata.libs.serializers.fields.boolean_field import BooleanField
from onadata.libs.serializers.tag_list_serializer import TagListSerializer
from onadata.libs.permissions import get_role


class XFormSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='xform-detail',
                                               lookup_field='pk')
    formid = serializers.Field(source='id')
    owner = serializers.HyperlinkedRelatedField(
        view_name='user-detail',
        source='user', lookup_field='username')
    public = BooleanField(
        source='shared', widget=widgets.CheckboxInput())
    public_data = BooleanField(
        source='shared_data')
    tags = TagListSerializer(read_only=True)
    users = serializers.SerializerMethodField('get_xform_permissions')

    class Meta:
        model = XForm
        read_only_fields = (
            'json', 'xml', 'date_created', 'date_modified', 'encrypted',
            'bamboo_dataset', 'last_submission_time')
        exclude = ('id', 'json', 'xml', 'xls', 'user',
                   'has_start_time', 'shared', 'shared_data')

    def get_xform_permissions(self, obj):
        users_with_perms = []
        if obj:
            for user in get_users_with_perms(obj):
                user_permissions = {'user': user,
                                    'role': get_role(user, obj),
                                    'permissions': get_perms(user, obj)}
            users_with_perms.append(user_permissions)
        return users_with_perms
