import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Count
from requests.exceptions import ConnectionError
from rest_framework import serializers
from rest_framework.reverse import reverse

from onadata.apps.logger.models import XForm, Instance
from onadata.libs.permissions import get_role
from onadata.libs.permissions import is_organization
from onadata.libs.serializers.tag_list_serializer import TagListSerializer
from onadata.libs.serializers.metadata_serializer import MetaDataSerializer
from onadata.libs.serializers.dataview_serializer import DataViewSerializer
from onadata.libs.utils.decorators import check_obj
from onadata.libs.utils.viewer_tools import enketo_url, EnketoError
from onadata.libs.utils.viewer_tools import get_form_url
from onadata.apps.main.views import get_enketo_preview_url
from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.utils.cache_tools import (XFORM_PERMISSIONS_CACHE,
                                            ENKETO_URL_CACHE,
                                            ENKETO_PREVIEW_URL_CACHE,
                                            XFORM_METADATA_CACHE,
                                            XFORM_DATA_VERSIONS,
                                            XFORM_LINKED_DATAVIEWS)


def _create_enketo_url(request, xform):
    """
    Generate enketo url for a form

    :param request:
    :param xform:
    :return: enketo url
    """
    form_url = get_form_url(
        request, xform.user.username, settings.ENKETO_PROTOCOL)
    url = ""

    try:
        url = enketo_url(form_url, xform.id_string)
        MetaData.enketo_url(xform, url)
    except ConnectionError, e:
        logging.exception("Connection Error: %s" % e.message)
    except EnketoError, e:
        logging.exception("Enketo Error: %s" % e.message)

    return url


def _set_cache(cache_key, cache_data, obj):
    """
    Utility function that set the specified info to the provided cache key

    :param cache_key:
    :param cache_data:
    :param obj:
    :return: Data that has been cached
    """
    cache.set('{}{}'.format(cache_key, obj.pk), cache_data)
    return cache_data


def user_to_username(item):
    item['user'] = item['user'].username

    return item


class XFormSerializer(serializers.HyperlinkedModelSerializer):
    formid = serializers.ReadOnlyField(source='id')
    metadata = serializers.SerializerMethodField()
    owner = serializers.HyperlinkedRelatedField(
        view_name='user-detail', source='user', lookup_field='username',
        queryset=User.objects.exclude(pk=settings.ANONYMOUS_USER_ID)
    )
    created_by = serializers.HyperlinkedRelatedField(
        view_name='user-detail', lookup_field='username',
        queryset=User.objects.exclude(pk=settings.ANONYMOUS_USER_ID)
    )
    public = serializers.BooleanField(source='shared')
    public_data = serializers.BooleanField(source='shared_data')
    require_auth = serializers.BooleanField()
    submission_count_for_today = serializers.ReadOnlyField()
    tags = TagListSerializer(read_only=True)
    title = serializers.CharField(max_length=255)
    url = serializers.HyperlinkedIdentityField(view_name='xform-detail',
                                               lookup_field='pk')
    users = serializers.SerializerMethodField()
    enketo_url = serializers.SerializerMethodField()
    enketo_preview_url = serializers.SerializerMethodField()
    instances_with_geopoints = serializers.SerializerMethodField()
    num_of_submissions = serializers.ReadOnlyField()
    form_versions = serializers.SerializerMethodField()
    data_views = serializers.SerializerMethodField()

    class Meta:
        model = XForm
        read_only_fields = (
            'json', 'xml', 'date_created', 'date_modified', 'encrypted',
            'bamboo_dataset', 'last_submission_time')
        exclude = ('json', 'xml', 'xls', 'user', 'has_start_time',
                   'shared', 'shared_data', 'deleted_at')

    def _get_metadata(self, obj, key):
        if key:
            for m in obj.metadata_set.all():
                if m.data_type == key:
                    return m.data_value
        else:
            return obj.metadata_set.all()

    def get_instances_with_geopoints(self, obj):
        if not obj.instances_with_geopoints and obj.num_of_submissions:
            has_geo = obj.instances.exclude(geom=None).count() > 0
            if has_geo:
                obj.instances_with_geopoints = has_geo
                obj.save(update_fields=['instances_with_geopoints'])

        return obj.instances_with_geopoints

    def get_users(self, obj):
        xform_perms = []
        if obj:
            xform_perms = cache.get(
                '{}{}'.format(XFORM_PERMISSIONS_CACHE, obj.pk))
            if xform_perms:
                return xform_perms

            cache.set(
                '{}{}'.format(XFORM_PERMISSIONS_CACHE, obj.pk), xform_perms)
        data = {}
        for perm in obj.xformuserobjectpermission_set.all():
            if perm.user_id not in data:
                user = perm.user

                data[perm.user_id] = {
                    'permissions': [],
                    'is_org': is_organization(user.profile),
                    'metadata': user.profile.metadata,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'user': user.username
                }
            if perm.user_id in data:
                data[perm.user_id]['permissions'].append(
                    perm.permission.codename
                )

        for k in data.keys():
            data[k]['permissions'].sort()
            data[k]['role'] = get_role(data[k]['permissions'], obj)
            del(data[k]['permissions'])

        xform_perms = data.values()

        cache.set(
            '{}{}'.format(XFORM_PERMISSIONS_CACHE, obj.pk), xform_perms)

        return xform_perms

    def get_enketo_url(self, obj):
        if obj:
            _enketo_url = cache.get('{}{}'.format(ENKETO_URL_CACHE, obj.pk))
            if _enketo_url:
                return _enketo_url

            url = self._get_metadata(obj, 'enketo_url')
            if url is None:
                url = _create_enketo_url(self.context.get('request'), obj)

            return _set_cache(ENKETO_URL_CACHE, url, obj)

        return None

    def get_enketo_preview_url(self, obj):
        if obj:
            _enketo_preview_url = cache.get(
                '{}{}'.format(ENKETO_PREVIEW_URL_CACHE, obj.pk))
            if _enketo_preview_url:
                return _enketo_preview_url

            url = self._get_metadata(obj, 'enketo_preview_url')
            if url is None:
                url = get_enketo_preview_url(self.context.get('request'),
                                             obj.user.username, obj.id_string)
                MetaData.enketo_preview_url(obj, url)

            return _set_cache(ENKETO_PREVIEW_URL_CACHE, url, obj)

        return None

    def get_metadata(self, obj):
        xform_metadata = []
        if obj:
            xform_metadata = cache.get(
                '{}{}'.format(XFORM_METADATA_CACHE, obj.pk))
            if xform_metadata:
                return xform_metadata

            xform_metadata = list(MetaDataSerializer(
                obj.metadata_set.all(),
                many=True,
                context=self.context
            ).data)
            cache.set(
                '{}{}'.format(XFORM_METADATA_CACHE, obj.pk), xform_metadata)

        return xform_metadata

    def get_form_versions(self, obj):
        versions = []
        if obj:
            versions = cache.get('{}{}'.format(XFORM_DATA_VERSIONS, obj.pk))

            if versions:
                return versions

            versions = list(Instance.objects.filter(xform=obj)
                            .values('version')
                            .annotate(total=Count('version')))

            if versions:
                cache.set('{}{}'.format(XFORM_DATA_VERSIONS, obj.pk),
                          list(versions))

        return versions

    def get_data_views(self, obj):
        if obj:
            key = '{}{}'.format(XFORM_LINKED_DATAVIEWS, obj.pk)
            data_views = cache.get(key)
            if data_views:
                return data_views

            data_views = DataViewSerializer(
                obj.dataview_set.all(),
                many=True,
                context=self.context).data

            cache.set(key, list(data_views))

            return data_views
        return []


class XFormListSerializer(serializers.Serializer):
    formID = serializers.ReadOnlyField(source='id_string')
    name = serializers.ReadOnlyField(source='title')
    majorMinorVersion = serializers.SerializerMethodField('get_version')
    version = serializers.SerializerMethodField()
    hash = serializers.SerializerMethodField()
    descriptionText = serializers.ReadOnlyField(source='description')
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
    filename = serializers.ReadOnlyField(source='data_value')
    hash = serializers.SerializerMethodField()
    downloadUrl = serializers.SerializerMethodField('get_url')

    @check_obj
    def get_url(self, obj):
        kwargs = {'pk': obj.content_object.pk,
                  'username': obj.content_object.user.username,
                  'metadata': obj.pk}
        request = self.context.get('request')
        format = obj.data_value[obj.data_value.rindex('.') + 1:]

        return reverse('xform-media', kwargs=kwargs,
                       request=request, format=format.lower())

    @check_obj
    def get_hash(self, obj):
        return u"%s" % (obj.file_hash or 'md5:')
