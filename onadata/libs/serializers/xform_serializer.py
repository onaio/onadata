# -*- coding: utf-8 -*-
"""
XForm model serialization.
"""

import hashlib
import logging
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import Count
from django.utils.translation import gettext as _

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from rest_framework import serializers
from rest_framework.reverse import reverse
from six import itervalues
from six.moves.urllib.parse import urlparse

from onadata.apps.logger.models import (
    DataView,
    EntityList,
    Instance,
    XForm,
    XFormVersion,
)
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.main.models.user_profile import UserProfile
from onadata.libs.exceptions import EncryptionError, EnketoError
from onadata.libs.kms.tools import (
    clean_public_key,
    disable_xform_encryption,
    encrypt_xform,
)
from onadata.libs.permissions import get_role, is_organization
from onadata.libs.serializers.dataview_serializer import DataViewMinimalSerializer
from onadata.libs.serializers.metadata_serializer import MetaDataSerializer
from onadata.libs.serializers.tag_list_serializer import TagListSerializer
from onadata.libs.utils.api_export_tools import get_metadata_format
from onadata.libs.utils.cache_tools import (
    ENKETO_PREVIEW_URL_CACHE,
    ENKETO_SINGLE_SUBMIT_URL_CACHE,
    ENKETO_URL_CACHE,
    XFORM_COUNT,
    XFORM_DATA_VERSIONS,
    XFORM_LINKED_DATAVIEWS,
    XFORM_METADATA_CACHE,
    XFORM_PERMISSIONS_CACHE,
    safe_cache_get,
    safe_cache_set,
)
from onadata.libs.utils.common_tags import GROUP_DELIMETER_TAG, REPEAT_INDEX_TAGS
from onadata.libs.utils.decorators import check_obj
from onadata.libs.utils.viewer_tools import get_enketo_urls, get_form_url

SUBMISSION_RETRIEVAL_THRESHOLD = getattr(
    settings, "SUBMISSION_RETRIEVAL_THRESHOLD", 10000
)

# pylint: disable=invalid-name
User = get_user_model()


def _create_enketo_urls(request, xform):
    """
    Generate enketo urls for a form

    :param request:
    :param xform:
    :return: enketo urls
    """
    form_url = get_form_url(
        request,
        xform.user.username,
        settings.ENKETO_PROTOCOL,
        xform_pk=xform.pk,
        generate_consistent_urls=True,
    )
    data = {}
    try:
        enketo_urls = get_enketo_urls(form_url, xform.id_string)
        if not enketo_urls:
            return data
        offline_url = enketo_urls.get("offline_url")
        MetaData.enketo_url(xform, offline_url)
        data["offline_url"] = offline_url
        if "preview_url" in enketo_urls:
            preview_url = enketo_urls.get("preview_url")
            MetaData.enketo_preview_url(xform, preview_url)
            data["preview_url"] = preview_url
        if "single_url" in enketo_urls:
            single_url = enketo_urls.get("single_url")
            MetaData.enketo_single_submit_url(xform, single_url)
            data["single_url"] = single_url
    except ConnectionError as e:
        logging.exception("Connection Error: %s", e)
    except EnketoError as e:
        logging.exception("Enketo Error: %s", e.message)

    return data


def _set_cache(cache_key, cache_data, obj):
    """
    Utility function that set the specified info to the provided cache key

    :param cache_key:
    :param cache_data:
    :param obj:
    :return: Data that has been cached
    """
    safe_cache_set(f"{cache_key}{obj.pk}", cache_data)
    return cache_data


def user_to_username(item):
    """
    Replaces the item["user"] user object with the to user.username.
    """
    item["user"] = item["user"].username

    return item


# pylint: disable=too-few-public-methods
class MultiLookupIdentityField(serializers.HyperlinkedIdentityField):
    """
    Custom HyperlinkedIdentityField that supports multiple lookup fields.

    Credits:  https://stackoverflow.com/a/31161585
    """

    lookup_fields = (("pk", "pk"),)

    def __init__(self, *args, **kwargs):
        self.lookup_fields = kwargs.pop("lookup_fields", self.lookup_fields)
        super().__init__(*args, **kwargs)

    # pylint: disable=redefined-builtin
    def get_url(self, obj, view_name, request, format):
        """
        Returns URL to the given object.
        """
        kwargs = {}
        for model_field, url_param in self.lookup_fields:
            attr = obj
            for field in model_field.split("__"):
                attr = getattr(attr, field)
            kwargs[url_param] = attr

        fmt = self.format if not format and hasattr(self, "format") else format

        return reverse(view_name, kwargs=kwargs, request=request, format=fmt)


class XFormMixin:
    """
    XForm mixins
    """

    def get_xls_available(self, obj):
        """
        Returns True if ``obj.xls.url`` is not None, indicates XLS is present.
        """
        available = False
        if obj and obj.xls:
            try:
                available = obj.xls.url is not None
            except ValueError:
                available = False
        return available

    def _get_metadata(self, obj, key):
        if key:
            for m in obj.metadata_set.all():
                if m.data_type == key:
                    return m.data_value

        return None

    def get_users(self, obj):
        """
        Returns a list of users based on XForm permissions.
        """
        xform_perms = []
        if obj:
            xform_perms = safe_cache_get(f"{XFORM_PERMISSIONS_CACHE}{obj.pk}")
            if xform_perms:
                return xform_perms

            safe_cache_set(f"{XFORM_PERMISSIONS_CACHE}{obj.pk}", xform_perms)
        data = {}
        for perm in obj.xformuserobjectpermission_set.all():
            if perm.user_id not in data:
                user = perm.user

                # create default user profile if missing
                try:
                    profile = user.profile
                except UserProfile.DoesNotExist:
                    profile = UserProfile.objects.create(user=user)

                data[perm.user_id] = {
                    "permissions": [],
                    "is_org": is_organization(profile),
                    "metadata": profile.metadata,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "user": user.username,
                }
            if perm.user_id in data:
                data[perm.user_id]["permissions"].append(perm.permission.codename)

        for k in list(data):
            data[k]["permissions"].sort()
            data[k]["role"] = get_role(data[k]["permissions"], XForm)
            del data[k]["permissions"]

        xform_perms = list(itervalues(data))

        safe_cache_set(f"{XFORM_PERMISSIONS_CACHE}{obj.pk}", xform_perms)

        return xform_perms

    def get_enketo_url(self, obj):
        """
        Returns Enketo URL for given ``obj``.
        """
        if obj:
            _enketo_url = safe_cache_get(f"{ENKETO_URL_CACHE}{obj.pk}")
            if _enketo_url:
                return _enketo_url

            url = self._get_metadata(obj, "enketo_url")
            if url is None:
                enketo_urls = _create_enketo_urls(self.context.get("request"), obj)
                url = enketo_urls.get("offline_url")

            return _set_cache(ENKETO_URL_CACHE, url, obj)

        return None

    def get_enketo_single_submit_url(self, obj):
        """
        Returns single submit Enketo URL for given ``obj``.
        """
        if obj:
            _enketo_single_submit_url = safe_cache_get(
                f"{ENKETO_SINGLE_SUBMIT_URL_CACHE}{obj.pk}"
            )
            if _enketo_single_submit_url:
                return _enketo_single_submit_url

            url = self._get_metadata(obj, "enketo_url")
            if url is None:
                enketo_urls = _create_enketo_urls(self.context.get("request"), obj)
                url = enketo_urls.get("offline_url")

            return _set_cache(ENKETO_SINGLE_SUBMIT_URL_CACHE, url, obj)

        return None

    def get_enketo_preview_url(self, obj):
        """
        Returns preview Enketo URL for given ``obj``.
        """
        if obj:
            _enketo_preview_url = safe_cache_get(f"{ENKETO_PREVIEW_URL_CACHE}{obj.pk}")
            if _enketo_preview_url:
                return _enketo_preview_url

            url = self._get_metadata(obj, "enketo_preview_url")
            if url is None:
                enketo_urls = _create_enketo_urls(self.context.get("request"), obj)
                url = (
                    enketo_urls["preview_url"] if "preview_url" in enketo_urls else url
                )
                if url is None:
                    return url

            return _set_cache(ENKETO_PREVIEW_URL_CACHE, url, obj)

        return None

    def get_data_views(self, obj):
        """Returns a list of filtered datasets linked to the form."""
        if obj:
            key = f"{XFORM_LINKED_DATAVIEWS}{obj.pk}"
            data_views = safe_cache_get(key)
            if data_views:
                return data_views

            data_views = DataViewMinimalSerializer(
                obj.dataview_set.filter(deleted_at__isnull=True),
                many=True,
                context=self.context,
            ).data

            safe_cache_set(key, list(data_views))

            return data_views
        return []

    def get_num_of_submissions(self, obj):
        """
        Returns number of submissions.
        """
        if obj:
            key = f"{XFORM_COUNT}{obj.pk}"
            count = safe_cache_get(key)
            if count:
                return count

            count = obj.submission_count(obj.is_merged_dataset)

            safe_cache_set(key, count)
            return count
        return 0

    def get_last_submission_time(self, obj):
        """Return datetime of last submission

        If a form is a merged dataset then it is picked from the list of forms
        attached to that merged dataset.
        """
        if "last_submission_time" not in self.fields:
            return None

        if obj.is_merged_dataset:
            values = [
                x.last_submission_time.isoformat()
                for x in obj.mergedxform.xforms.only("last_submission_time")
                if x.last_submission_time
            ]
            if values:
                return sorted(values, reverse=True)[0]

        return (
            obj.last_submission_time.isoformat() if obj.last_submission_time else None
        )

    def get_contributes_entities_to(self, obj: XForm):
        """Return the EntityList that the form contributes Entities to"""
        registration_form = obj.registration_forms.first()

        if registration_form is None:
            return None

        return {
            "id": registration_form.entity_list.pk,
            "name": registration_form.entity_list.name,
            "is_active": registration_form.is_active,
        }

    def get_consumes_entities_from(self, obj: XForm):
        """Return the EntityLIst that the form consumes Entities"""
        queryset = obj.follow_up_forms.all()

        if not queryset:
            return []

        return list(
            map(
                lambda follow_up_form: {
                    "id": follow_up_form.entity_list.pk,
                    "name": follow_up_form.entity_list.name,
                    "is_active": follow_up_form.is_active,
                },
                queryset,
            )
        )

    def get_num_of_pending_decryption_submissions(self, obj):
        """Return the number of submissions pending decryption for the form."""
        return obj.num_of_pending_decryption_submissions


class XFormBaseSerializer(XFormMixin, serializers.HyperlinkedModelSerializer):
    """XForm base serializer."""

    formid = serializers.ReadOnlyField(source="id")
    owner = serializers.HyperlinkedRelatedField(
        view_name="user-detail",
        source="user",
        lookup_field="username",
        queryset=User.objects.exclude(
            username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME
        ),
    )
    created_by = serializers.HyperlinkedRelatedField(
        view_name="user-detail",
        lookup_field="username",
        queryset=User.objects.exclude(
            username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME
        ),
    )
    public = serializers.BooleanField(source="shared")
    public_data = serializers.BooleanField(source="shared_data")
    public_key = serializers.CharField(required=False)
    require_auth = serializers.BooleanField()
    tags = TagListSerializer(read_only=True)
    title = serializers.CharField(max_length=255)
    url = serializers.HyperlinkedIdentityField(
        view_name="xform-detail", lookup_field="pk"
    )
    users = serializers.SerializerMethodField()
    enketo_url = serializers.SerializerMethodField()
    enketo_preview_url = serializers.SerializerMethodField()
    enketo_single_submit_url = serializers.SerializerMethodField()
    num_of_submissions = serializers.SerializerMethodField()
    num_of_pending_decryption_submissions = serializers.SerializerMethodField()
    last_submission_time = serializers.SerializerMethodField()
    data_views = serializers.SerializerMethodField()
    xls_available = serializers.SerializerMethodField()
    contributes_entities_to = serializers.SerializerMethodField()
    consumes_entities_from = serializers.SerializerMethodField()

    # pylint: disable=too-few-public-methods,missing-class-docstring
    class Meta:
        model = XForm
        read_only_fields = (
            "json",
            "xml",
            "date_created",
            "date_modified",
            "encrypted",
            "bamboo_dataset",
            "last_submission_time",
            "is_merged_dataset",
            "xls_available",
            "is_managed",
        )
        exclude = (
            "json",
            "xml",
            "xls",
            "user",
            "has_start_time",
            "shared",
            "shared_data",
            "deleted_at",
            "deleted_by",
        )


class XFormSerializer(XFormMixin, serializers.HyperlinkedModelSerializer):
    """
    XForm model serializer
    """

    formid = serializers.ReadOnlyField(source="id")
    metadata = serializers.SerializerMethodField()
    owner = serializers.HyperlinkedRelatedField(
        view_name="user-detail",
        source="user",
        lookup_field="username",
        queryset=User.objects.exclude(
            username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME
        ),
    )
    created_by = serializers.HyperlinkedRelatedField(
        view_name="user-detail",
        lookup_field="username",
        queryset=User.objects.exclude(
            username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME
        ),
    )
    public = serializers.BooleanField(source="shared")
    public_data = serializers.BooleanField(source="shared_data")
    public_key = serializers.CharField(required=False)
    enable_kms_encryption = serializers.BooleanField(required=False, write_only=True)
    require_auth = serializers.BooleanField()
    submission_count_for_today = serializers.ReadOnlyField()
    tags = TagListSerializer(read_only=True)
    title = serializers.CharField(max_length=255)
    url = serializers.HyperlinkedIdentityField(
        view_name="xform-detail", lookup_field="pk"
    )
    users = serializers.SerializerMethodField()
    enketo_url = serializers.SerializerMethodField()
    enketo_preview_url = serializers.SerializerMethodField()
    enketo_single_submit_url = serializers.SerializerMethodField()
    num_of_submissions = serializers.SerializerMethodField()
    num_of_pending_decryption_submissions = serializers.SerializerMethodField()
    last_submission_time = serializers.SerializerMethodField()
    form_versions = serializers.SerializerMethodField()
    data_views = serializers.SerializerMethodField()
    xls_available = serializers.SerializerMethodField()
    contributes_entities_to = serializers.SerializerMethodField()
    consumes_entities_from = serializers.SerializerMethodField()

    class Meta:
        model = XForm
        read_only_fields = (
            "json",
            "xml",
            "date_created",
            "date_modified",
            "encrypted",
            "bamboo_dataset",
            "last_submission_time",
            "is_merged_dataset",
            "xls_available",
            "is_managed",
        )
        exclude = (
            "json",
            "xml",
            "xls",
            "user",
            "has_start_time",
            "shared",
            "shared_data",
            "deleted_at",
            "deleted_by",
        )

    def get_metadata(self, obj):
        """
        Returns XForn ``obj`` metadata.
        """
        xform_metadata = []
        if obj:
            xform_metadata = safe_cache_get(f"{XFORM_METADATA_CACHE}{obj.pk}")
            if xform_metadata:
                return xform_metadata

            xform_metadata = list(
                MetaDataSerializer(
                    obj.metadata_set.all(), many=True, context=self.context
                ).data
            )
            safe_cache_set(f"{XFORM_METADATA_CACHE}{obj.pk}", xform_metadata)

        return xform_metadata

    def validate_public_key(self, value):
        """
        Checks that the given RSA public key is a valid key by trying
        to use the key data to create an RSA key object using the cryptography
        package
        """
        try:
            load_pem_public_key(value.encode("utf-8"), backend=default_backend())
        except ValueError as e:
            raise serializers.ValidationError(
                _("The public key is not a valid base64 RSA key")
            ) from e
        return clean_public_key(value)

    def _check_if_allowed_public(self, value):
        """
        Verify that users are allowed to create public
        forms
        """
        if not settings.ALLOW_PUBLIC_DATASETS and value:
            raise serializers.ValidationError(_("Public forms are currently disabled."))
        return value

    def validate_public_data(self, value):
        """
        Validate the public_data field
        """
        return self._check_if_allowed_public(value)

    def validate_public(self, value):
        """
        Validate the public field
        """
        return self._check_if_allowed_public(value)

    def get_form_versions(self, obj):
        """
        Returns all form versions.
        """
        versions = []
        if obj:
            versions = safe_cache_get(f"{XFORM_DATA_VERSIONS}{obj.pk}")

            if versions:
                return versions
            if obj.num_of_submissions > SUBMISSION_RETRIEVAL_THRESHOLD:
                return []

            versions = list(
                Instance.objects.filter(xform=obj, deleted_at__isnull=True)
                .values("version")
                .annotate(total=Count("version"))
            )

            if versions:
                safe_cache_set(f"{XFORM_DATA_VERSIONS}{obj.pk}", list(versions))

        return versions

    def update(self, instance, validated_data):
        enable_kms_encryption = validated_data.pop("enable_kms_encryption", None)

        with transaction.atomic():
            instance = super().update(instance, validated_data)

            if enable_kms_encryption and not instance.encrypted:
                try:
                    encrypt_xform(instance, encrypted_by=self.context["request"].user)

                except EncryptionError as exc:
                    raise serializers.ValidationError(
                        {"enable_kms_encryption": f"{exc}"}
                    )

            elif (
                enable_kms_encryption is not None
                and not enable_kms_encryption
                and instance.encrypted
            ):
                try:
                    disable_xform_encryption(
                        instance, disabled_by=self.context["request"].user
                    )

                except EncryptionError as exc:
                    raise serializers.ValidationError(
                        {"enable_kms_encryption": f"{exc}"}
                    )

            return instance


# pylint: disable=abstract-method
class XFormCreateSerializer(XFormSerializer):
    """
    XForm serializer that is only relevant during the XForm publishing process.
    """

    has_id_string_changed = serializers.SerializerMethodField()

    def get_has_id_string_changed(self, obj):
        """
        Returns the value of ``obj.has_id_string_changed``
        """
        return obj.has_id_string_changed


# pylint: disable=abstract-method
class XFormListSerializer(serializers.Serializer):
    """
    XForm serializer for OpenRosa form list API.
    """

    formID = serializers.ReadOnlyField(source="id_string")  # noqa
    name = serializers.ReadOnlyField(source="title")
    version = serializers.ReadOnlyField()
    hash = serializers.ReadOnlyField()
    descriptionText = serializers.ReadOnlyField(source="description")  # noqa
    downloadUrl = serializers.SerializerMethodField("get_url")  # noqa
    manifestUrl = serializers.SerializerMethodField("get_manifest_url")  # noqa

    @check_obj
    def get_url(self, obj):
        """
        Returns XForm download URL.
        """
        kwargs = {"pk": obj.pk, "username": obj.user.username}
        request = self.context.get("request")

        return reverse("download_xform", kwargs=kwargs, request=request)

    @check_obj
    def get_manifest_url(self, obj):
        """
        Return manifest URL.
        """
        kwargs = {"pk": obj.pk, "username": obj.user.username}
        request = self.context.get("request")
        object_list = MetaData.objects.filter(data_type="media", object_id=obj.pk)
        if object_list:
            return reverse("manifest-url", kwargs=kwargs, request=request)
        return None


class XFormManifestSerializer(serializers.Serializer):
    """XForm Manifest serializer class."""

    filename = serializers.SerializerMethodField()
    hash = serializers.SerializerMethodField()
    downloadUrl = serializers.SerializerMethodField("get_url")  # noqa

    @check_obj
    def get_url(self, obj):
        """
        Return media download URL.
        """
        kwargs = {
            "pk": obj.content_object.pk,
            "username": obj.content_object.user.username,
            "metadata": obj.pk,
        }
        request = self.context.get("request")
        extension = get_metadata_format(obj.data_value)
        try:
            fmt_index = obj.data_value.rindex(".") + 1
            fmt = obj.data_value[fmt_index:]
        except ValueError:
            fmt = extension
        url = reverse("xform-media", kwargs=kwargs, request=request, format=fmt.lower())

        group_delimiter = self.context.get(GROUP_DELIMETER_TAG)
        repeat_index_tags = self.context.get(REPEAT_INDEX_TAGS)
        if group_delimiter and repeat_index_tags and fmt == "csv":
            return url + (
                f"?{GROUP_DELIMETER_TAG}={group_delimiter}"
                f"&{REPEAT_INDEX_TAGS}={repeat_index_tags}"
            )

        return url

    def _generate_hash(self, data) -> str:
        md5_hash = hashlib.new(
            "md5",
            data,
            usedforsecurity=False,
        ).hexdigest()
        return f"md5:{md5_hash}"

    @check_obj
    def get_hash(self, obj):
        """
        Returns MD5 hash based on last_submission_time for a media linked form.
        """
        filename = obj.data_value
        hsh = obj.file_hash
        parts = filename.split(" ")
        # filtered dataset is of the form "xform PK name", xform pk is the
        # second item
        # other file uploads other than linked datasets have a data_file
        if len(parts) > 2 and obj.data_file == "":
            dataset_type = parts[0]
            pk = parts[1]
            xform = None
            if dataset_type == "xform":
                xform = XForm.objects.filter(pk=pk).only("last_submission_time").first()

            elif dataset_type == "entity_list":
                entity_list = EntityList.objects.filter(pk=pk).first()

                if entity_list.last_entity_update_time is not None:
                    update_time_str = entity_list.last_entity_update_time.isoformat()
                    num_entities = str(entity_list.num_entities)
                    hsh = self._generate_hash(
                        f"{update_time_str}-{num_entities}".encode("utf-8")
                    )
            else:
                data_view = (
                    DataView.objects.filter(pk=pk)
                    .only("xform__last_submission_time")
                    .first()
                )
                if data_view:
                    xform = data_view.xform

            if xform and xform.last_submission_time:
                hsh = self._generate_hash(
                    xform.last_submission_time.isoformat().encode("utf-8")
                )

        return f"{hsh or 'md5:'}"

    @check_obj
    def get_filename(self, obj):
        """
        Returns media filename.
        """
        filename = obj.data_value
        parts = filename.split(" ")
        extension = get_metadata_format(filename)
        # filtered dataset is of the form "xform PK name", filename is the
        # third item
        if len(parts) > 2:
            filename = f"{parts[2]}.{extension}"
        else:
            try:
                URLValidator()(filename)
            except ValidationError:
                pass
            else:
                urlparts = urlparse(obj.data_value)
                filename = os.path.basename(urlparts.path) or urlparts.netloc

        return filename


# pylint: disable=too-few-public-methods
class XFormVersionListSerializer(serializers.ModelSerializer):
    """
    XFormVersion list API serializer
    """

    xform = serializers.HyperlinkedRelatedField(
        view_name="xform-detail",
        lookup_field="pk",
        queryset=XForm.objects.filter(deleted_at__isnull=True),
    )
    url = MultiLookupIdentityField(
        view_name="form-version-detail",
        lookup_fields=(("xform__pk", "pk"), ("version", "version_id")),
    )
    xml = MultiLookupIdentityField(
        view_name="form-version-detail",
        format="xml",
        lookup_fields=(("xform__pk", "pk"), ("version", "version_id")),
    )
    created_by = serializers.HyperlinkedRelatedField(
        view_name="user-detail",
        lookup_field="username",
        queryset=User.objects.exclude(
            username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME
        ),
    )

    class Meta:
        model = XFormVersion
        exclude = ("json", "xls", "id")
