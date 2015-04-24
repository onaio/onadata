from django.forms import widgets
from rest_framework import serializers
from rest_framework.reverse import reverse
from django.core.cache import cache
from django.db.models import Count

from onadata.apps.logger.models import XForm, Instance
from onadata.libs.permissions import get_object_users_with_permissions
from onadata.libs.serializers.fields.boolean_field import BooleanField
from onadata.libs.serializers.tag_list_serializer import TagListSerializer
from onadata.libs.serializers.metadata_serializer import MetaDataSerializer
from onadata.libs.utils.decorators import check_obj
from onadata.libs.utils.viewer_tools import enketo_url, EnketoError
from onadata.libs.utils.viewer_tools import _get_form_url
from onadata.apps.main.views import get_enketo_preview_url
from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.utils.cache_tools import (XFORM_PERMISSIONS_CACHE,
                                            ENKETO_URL_CACHE,
                                            ENKETO_PREVIEW_URL_CACHE,
                                            XFORM_METADATA_CACHE,
                                            XFORM_DATA_VERSIONS)


class XFormSerializer(serializers.HyperlinkedModelSerializer):
    formid = serializers.Field(source='id')
    metadata = serializers.SerializerMethodField('get_xform_metadata')
    owner = serializers.HyperlinkedRelatedField(view_name='user-detail',
                                                source='user',
                                                lookup_field='username')
    created_by = serializers.HyperlinkedRelatedField(view_name='user-detail',
                                                     source='created_by',
                                                     lookup_field='username')
    public = BooleanField(source='shared', widget=widgets.CheckboxInput())
    public_data = BooleanField(source='shared_data')
    require_auth = BooleanField(source='require_auth',
                                widget=widgets.CheckboxInput())
    submission_count_for_today = serializers.Field(
        source='submission_count_for_today')
    tags = TagListSerializer(read_only=True)
    title = serializers.CharField(max_length=255, source='title')
    url = serializers.HyperlinkedIdentityField(view_name='xform-detail',
                                               lookup_field='pk')
    users = serializers.SerializerMethodField('get_xform_permissions')
    enketo_url = serializers.SerializerMethodField('get_enketo_url')
    enketo_preview_url = serializers.SerializerMethodField(
        'get_enketo_preview_url')
    instances_with_geopoints = serializers.SerializerMethodField(
        'get_instances_with_geopoints')
    num_of_submissions = serializers.SerializerMethodField(
        'get_num_of_submissions')
    form_versions = serializers.SerializerMethodField(
        'get_xform_versions')

    class Meta:
        model = XForm
        read_only_fields = (
            'json', 'xml', 'date_created', 'date_modified', 'encrypted',
            'bamboo_dataset', 'last_submission_time')
        exclude = ('id', 'json', 'xml', 'xls', 'user', 'has_start_time',
                   'shared', 'shared_data', 'deleted_at')

    def get_num_of_submissions(self, obj):
        if obj.num_of_submissions != obj.instances.filter(
                deleted_at__isnull=True).count():
            obj.submission_count(force_update=True)

        return obj.num_of_submissions

    def get_instances_with_geopoints(self, obj):
        if not obj.instances_with_geopoints and obj.instances.exclude(
                geom=None).count() > 0:
            obj.instances_with_geopoints = True
            obj.save()

        return obj.instances_with_geopoints

    def get_xform_permissions(self, obj):
        if obj:
            xform_perms = cache.get(
                '{}{}'.format(XFORM_PERMISSIONS_CACHE, obj.pk))
            if xform_perms:
                return xform_perms

            xform_perms = get_object_users_with_permissions(obj)
            cache.set(
                '{}{}'.format(XFORM_PERMISSIONS_CACHE, obj.pk), xform_perms)
            return xform_perms

        return []

    def get_enketo_url(self, obj):
        if obj:
            _enketo_url = cache.get(
                '{}{}'.format(ENKETO_URL_CACHE, obj.pk))
            if _enketo_url:
                return _enketo_url

            try:
                metadata = MetaData.objects.get(
                    xform=obj, data_type="enketo_url")
            except MetaData.DoesNotExist:
                request = self.context.get('request')
                form_url = _get_form_url(request, obj.user.username)
                url = ""

                try:
                    url = enketo_url(form_url, obj.id_string)
                    MetaData.enketo_url(obj, url)
                except EnketoError:
                    pass

                cache.set('{}{}'.format(ENKETO_URL_CACHE, obj.pk), url)
                return url

            _enketo_url = metadata.data_value
            cache.set('{}{}'.format(ENKETO_URL_CACHE, obj.pk), _enketo_url)
            return _enketo_url

        return None

    def get_enketo_preview_url(self, obj):
        if obj:
            _enketo_preview_url = cache.get(
                '{}{}'.format(ENKETO_PREVIEW_URL_CACHE, obj.pk))
            if _enketo_preview_url:
                return _enketo_preview_url

            try:
                metadata = MetaData.objects.get(
                    xform=obj, data_type="enketo_preview_url")
            except MetaData.DoesNotExist:
                request = self.context.get('request')
                preview_url = ""

                try:
                    preview_url = get_enketo_preview_url(request,
                                                         obj.user.username,
                                                         obj.id_string)
                    MetaData.enketo_preview_url(obj, preview_url)
                except EnketoError:
                    pass

                cache.set('{}{}'.format(ENKETO_PREVIEW_URL_CACHE, obj.pk),
                          preview_url)
                return preview_url

            _enketo_preview_url = metadata.data_value
            cache.set(
                '{}{}'.format(ENKETO_URL_CACHE, obj.pk), _enketo_preview_url)
            return _enketo_preview_url

        return None

    def get_xform_metadata(self, obj):
        if obj:
            xform_metadata = cache.get(
                '{}{}'.format(XFORM_METADATA_CACHE, obj.pk))
            if xform_metadata:
                return xform_metadata

            xform_metadata = MetaDataSerializer(
                obj.metadata_set.all(),
                many=True,
                context=self.context).data
            cache.set(
                '{}{}'.format(XFORM_METADATA_CACHE, obj.pk), xform_metadata)
            return xform_metadata

        return []

    def get_xform_versions(self, obj):
        versions = cache.get('{}{}'.format(XFORM_DATA_VERSIONS, obj.pk))

        if versions:
            return versions

        versions = Instance.objects.filter(xform=obj)\
            .values('version')\
            .annotate(total=Count('version'))

        cache.set('{}{}'.format(XFORM_DATA_VERSIONS, obj.pk), versions)

        return versions


class XFormListSerializer(serializers.Serializer):
    formID = serializers.Field(source='id_string')
    name = serializers.Field(source='title')
    majorMinorVersion = serializers.SerializerMethodField('get_version')
    version = serializers.SerializerMethodField('get_version')
    hash = serializers.SerializerMethodField('get_hash')
    descriptionText = serializers.Field(source='description')
    downloadUrl = serializers.SerializerMethodField('get_url')
    manifestUrl = serializers.SerializerMethodField('get_manifest_url')

    def get_version(self, obj):
        return None

    @check_obj
    def get_hash(self, obj):
        return u"md5:%s" % obj.hash

    @check_obj
    def get_url(self, obj):
        kwargs = {'pk': obj.pk, 'username': obj.user.username}
        request = self.context.get('request')

        return reverse('download_xform', kwargs=kwargs, request=request)

    @check_obj
    def get_manifest_url(self, obj):
        kwargs = {'pk': obj.pk, 'username': obj.user.username}
        request = self.context.get('request')

        return reverse('manifest-url', kwargs=kwargs, request=request)


class XFormManifestSerializer(serializers.Serializer):
    filename = serializers.Field(source='data_value')
    hash = serializers.SerializerMethodField('get_hash')
    downloadUrl = serializers.SerializerMethodField('get_url')

    @check_obj
    def get_url(self, obj):
        kwargs = {'pk': obj.xform.pk,
                  'username': obj.xform.user.username,
                  'metadata': obj.pk}
        request = self.context.get('request')
        format = obj.data_value[obj.data_value.rindex('.') + 1:]

        return reverse('xform-media', kwargs=kwargs,
                       request=request, format=format.lower())

    @check_obj
    def get_hash(self, obj):
        return u"%s" % (obj.file_hash or 'md5:')
