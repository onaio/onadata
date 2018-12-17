import logging
import os
from hashlib import md5

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db.models import Count
from future.moves.urllib.parse import urlparse
from future.utils import listvalues
from requests.exceptions import ConnectionError
from rest_framework import serializers
from rest_framework.reverse import reverse

from onadata.apps.logger.models import DataView, Instance, XForm
from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.exceptions import EnketoError
from onadata.libs.permissions import get_role, is_organization
from onadata.libs.serializers.dataview_serializer import \
    DataViewMinimalSerializer
from onadata.libs.serializers.metadata_serializer import MetaDataSerializer
from onadata.libs.serializers.tag_list_serializer import TagListSerializer
from onadata.libs.utils.cache_tools import (
    ENKETO_PREVIEW_URL_CACHE, ENKETO_URL_CACHE, XFORM_DATA_VERSIONS,
    XFORM_LINKED_DATAVIEWS, XFORM_METADATA_CACHE, XFORM_PERMISSIONS_CACHE,
    XFORM_COUNT)
from onadata.libs.utils.common_tags import (GROUP_DELIMETER_TAG,
                                            REPEAT_INDEX_TAGS)
from onadata.libs.utils.decorators import check_obj
from onadata.libs.utils.viewer_tools import (
    enketo_url, get_enketo_preview_url, get_form_url)


def _create_enketo_url(request, xform):
    """
    Generate enketo url for a form

    :param request:
    :param xform:
    :return: enketo url
    """
    form_url = get_form_url(request, xform.user.username,
                            settings.ENKETO_PROTOCOL, xform_pk=xform.pk)
    url = ""

    try:
        url = enketo_url(form_url, xform.id_string)
        MetaData.enketo_url(xform, url)
    except ConnectionError as e:
        logging.exception("Connection Error: %s" % e.message)
    except EnketoError as e:
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


class XFormMixin(object):
    def _get_metadata(self, obj, key):
        if key:
            for m in obj.metadata_set.all():
                if m.data_type == key:
                    return m.data_value
        else:
            return obj.metadata_set.all()

    def get_users(self, obj):
        xform_perms = []
        if obj:
            xform_perms = cache.get(
                '{}{}'.format(XFORM_PERMISSIONS_CACHE, obj.pk))
            if xform_perms:
                return xform_perms

            cache.set('{}{}'.format(XFORM_PERMISSIONS_CACHE, obj.pk),
                      xform_perms)
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
                    perm.permission.codename)

        for k in list(data):
            data[k]['permissions'].sort()
            data[k]['role'] = get_role(data[k]['permissions'], XForm)
            del (data[k]['permissions'])

        xform_perms = listvalues(data)

        cache.set('{}{}'.format(XFORM_PERMISSIONS_CACHE, obj.pk), xform_perms)

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
                try:
                    url = get_enketo_preview_url(
                        self.context.get('request'), obj.user.username,
                        obj.id_string, xform_pk=obj.pk)
                except Exception:
                    return url
                else:
                    MetaData.enketo_preview_url(obj, url)

            return _set_cache(ENKETO_PREVIEW_URL_CACHE, url, obj)

        return None

    def get_data_views(self, obj):
        if obj:
            key = '{}{}'.format(XFORM_LINKED_DATAVIEWS, obj.pk)
            data_views = cache.get(key)
            if data_views:
                return data_views

            data_views = DataViewMinimalSerializer(
                obj.dataview_set.filter(deleted_at__isnull=True),
                many=True, context=self.context).data

            cache.set(key, list(data_views))

            return data_views
        return []

    def get_num_of_submissions(self, obj):
        if obj:
            key = '{}{}'.format(XFORM_COUNT, obj.pk)
            count = cache.get(key)
            if count:
                return count

            force_update = True if obj.is_merged_dataset else False
            count = obj.submission_count(force_update)

            cache.set(key, count)
            return count

    def get_last_submission_time(self, obj):
        """Return datetime of last submission

        If a form is a merged dataset then it is picked from the list of forms
        attached to that merged dataset.
        """
        if 'last_submission_time' not in self.fields:
            return None

        if obj.is_merged_dataset:
            values = [
                x.last_submission_time.isoformat()
                for x in obj.mergedxform.xforms.only('last_submission_time')
                if x.last_submission_time
            ]
            if values:
                return sorted(values, reverse=True)[0]

        return obj.last_submission_time.isoformat() \
            if obj.last_submission_time else None


class XFormBaseSerializer(XFormMixin, serializers.HyperlinkedModelSerializer):
    formid = serializers.ReadOnlyField(source='id')
    owner = serializers.HyperlinkedRelatedField(
        view_name='user-detail',
        source='user',
        lookup_field='username',
        queryset=User.objects.exclude(
            username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME))
    created_by = serializers.HyperlinkedRelatedField(
        view_name='user-detail',
        lookup_field='username',
        queryset=User.objects.exclude(
            username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME))
    public = serializers.BooleanField(source='shared')
    public_data = serializers.BooleanField(source='shared_data')
    require_auth = serializers.BooleanField()
    tags = TagListSerializer(read_only=True)
    title = serializers.CharField(max_length=255)
    url = serializers.HyperlinkedIdentityField(
        view_name='xform-detail', lookup_field='pk')
    users = serializers.SerializerMethodField()
    enketo_url = serializers.SerializerMethodField()
    enketo_preview_url = serializers.SerializerMethodField()
    num_of_submissions = serializers.SerializerMethodField()
    last_submission_time = serializers.SerializerMethodField()
    data_views = serializers.SerializerMethodField()

    class Meta:
        model = XForm
        read_only_fields = ('json', 'xml', 'date_created', 'date_modified',
                            'encrypted', 'bamboo_dataset',
                            'last_submission_time', 'is_merged_dataset')
        exclude = ('json', 'xml', 'xls', 'user', 'has_start_time', 'shared',
                   'shared_data', 'deleted_at', 'deleted_by')


class XFormSerializer(XFormMixin, serializers.HyperlinkedModelSerializer):
    formid = serializers.ReadOnlyField(source='id')
    metadata = serializers.SerializerMethodField()
    owner = serializers.HyperlinkedRelatedField(
        view_name='user-detail',
        source='user',
        lookup_field='username',
        queryset=User.objects.exclude(
            username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME))
    created_by = serializers.HyperlinkedRelatedField(
        view_name='user-detail',
        lookup_field='username',
        queryset=User.objects.exclude(
            username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME))
    public = serializers.BooleanField(source='shared')
    public_data = serializers.BooleanField(source='shared_data')
    require_auth = serializers.BooleanField()
    submission_count_for_today = serializers.ReadOnlyField()
    tags = TagListSerializer(read_only=True)
    title = serializers.CharField(max_length=255)
    url = serializers.HyperlinkedIdentityField(
        view_name='xform-detail', lookup_field='pk')
    users = serializers.SerializerMethodField()
    enketo_url = serializers.SerializerMethodField()
    enketo_preview_url = serializers.SerializerMethodField()
    num_of_submissions = serializers.SerializerMethodField()
    last_submission_time = serializers.SerializerMethodField()
    form_versions = serializers.SerializerMethodField()
    data_views = serializers.SerializerMethodField()

    class Meta:
        model = XForm
        read_only_fields = ('json', 'xml', 'date_created', 'date_modified',
                            'encrypted', 'bamboo_dataset',
                            'last_submission_time', 'is_merged_dataset')
        exclude = ('json', 'xml', 'xls', 'user', 'has_start_time', 'shared',
                   'shared_data', 'deleted_at', 'deleted_by')

    def get_metadata(self, obj):
        xform_metadata = []
        if obj:
            xform_metadata = cache.get(
                '{}{}'.format(XFORM_METADATA_CACHE, obj.pk))
            if xform_metadata:
                return xform_metadata

            xform_metadata = list(
                MetaDataSerializer(
                    obj.metadata_set.all(), many=True, context=self.context)
                .data)
            cache.set('{}{}'.format(XFORM_METADATA_CACHE, obj.pk),
                      xform_metadata)

        return xform_metadata

    def get_form_versions(self, obj):
        versions = []
        if obj:
            versions = cache.get('{}{}'.format(XFORM_DATA_VERSIONS, obj.pk))

            if versions:
                return versions

            versions = list(
                Instance.objects.filter(xform=obj, deleted_at__isnull=True)
                .values('version').annotate(total=Count('version')))

            if versions:
                cache.set('{}{}'.format(XFORM_DATA_VERSIONS, obj.pk),
                          list(versions))

        return versions


class XFormCreateSerializer(XFormSerializer):
    has_id_string_changed = serializers.SerializerMethodField()

    def get_has_id_string_changed(self, obj):
        return obj.has_id_string_changed


class XFormListSerializer(serializers.Serializer):
    formID = serializers.ReadOnlyField(source='id_string')
    name = serializers.ReadOnlyField(source='title')
    version = serializers.SerializerMethodField()
    hash = serializers.ReadOnlyField()
    descriptionText = serializers.ReadOnlyField(source='description')
    downloadUrl = serializers.SerializerMethodField('get_url')
    manifestUrl = serializers.SerializerMethodField('get_manifest_url')

    @check_obj
    def get_version(self, obj):
        if obj.version and obj.version.isdigit():
            return obj.version

    @check_obj
    def get_url(self, obj):
        kwargs = {'pk': obj.pk, 'username': obj.user.username}
        request = self.context.get('request')

        return reverse('download_xform', kwargs=kwargs, request=request)

    @check_obj
    def get_manifest_url(self, obj):
        kwargs = {'pk': obj.pk, 'username': obj.user.username}
        request = self.context.get('request')
        object_list = MetaData.objects.filter(data_type='media',
                                              object_id=obj.pk)
        if object_list:
            return reverse('manifest-url', kwargs=kwargs, request=request)
        return None


class XFormManifestSerializer(serializers.Serializer):
    filename = serializers.SerializerMethodField()
    hash = serializers.SerializerMethodField()
    downloadUrl = serializers.SerializerMethodField('get_url')

    @check_obj
    def get_url(self, obj):
        kwargs = {
            'pk': obj.content_object.pk,
            'username': obj.content_object.user.username,
            'metadata': obj.pk
        }
        request = self.context.get('request')
        try:
            fmt = obj.data_value[obj.data_value.rindex('.') + 1:]
        except ValueError:
            fmt = 'csv'
        url = reverse(
            'xform-media', kwargs=kwargs, request=request, format=fmt.lower())

        group_delimiter = self.context.get(GROUP_DELIMETER_TAG)
        repeat_index_tags = self.context.get(REPEAT_INDEX_TAGS)
        if group_delimiter and repeat_index_tags and fmt == 'csv':
            return (url+"?%s=%s&%s=%s" % (
                GROUP_DELIMETER_TAG, group_delimiter, REPEAT_INDEX_TAGS,
                repeat_index_tags))

        return url

    @check_obj
    def get_hash(self, obj):
        filename = obj.data_value
        hsh = obj.file_hash
        parts = filename.split(' ')
        # filtered dataset is of the form "xform PK name", xform pk is the
        # second item
        # other file uploads other than linked datasets have a data_file
        if len(parts) > 2 and obj.data_file == '':
            dataset_type = parts[0]
            pk = parts[1]
            xform = None
            if dataset_type == 'xform':
                xform = XForm.objects.filter(pk=pk)\
                    .only('last_submission_time').first()
            else:
                data_view = DataView.objects.filter(pk=pk)\
                    .only('xform__last_submission_time').first()
                if data_view:
                    xform = data_view.xform

            if xform and xform.last_submission_time:
                hsh = u'md5:%s' % (md5(
                    xform.last_submission_time.isoformat().encode(
                        'utf-8')).hexdigest())

        return u"%s" % (hsh or 'md5:')

    @check_obj
    def get_filename(self, obj):
        filename = obj.data_value
        parts = filename.split(' ')
        # filtered dataset is of the form "xform PK name", filename is the
        # third item
        if len(parts) > 2:
            filename = u'%s.csv' % parts[2]
        else:
            try:
                URLValidator()(filename)
            except ValidationError:
                pass
            else:
                urlparts = urlparse(obj.data_value)
                filename = os.path.basename(urlparts.path) or urlparts.netloc

        return filename
