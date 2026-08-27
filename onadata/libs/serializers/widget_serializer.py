# -*- coding: utf-8 -*-
"""
Widget serializer
"""

from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.urls import Resolver404, get_script_prefix, resolve
from django.utils.translation import gettext as _

from guardian.shortcuts import get_users_with_perms
from rest_framework import serializers
from rest_framework.reverse import reverse
from six.moves.urllib.parse import urlparse

from onadata.apps.logger.models.data_view import DataView
from onadata.apps.logger.models.widget import Widget
from onadata.apps.logger.models.xform import XForm
from onadata.libs.permissions import OwnerRole, is_organization
from onadata.libs.serializers.fields.json_field import JsonField
from onadata.libs.utils.chart_tools import FIELD_DATA_MAP, resolve_field_xpath
from onadata.libs.utils.string import str2bool


class GenericRelatedField(serializers.HyperlinkedRelatedField):
    """
    GenericRelatedField - handle related field relations for XForm and DataView
    """

    default_error_messages = {
        "incorrect_match": _("`{input}` is not a valid relation.")
    }

    def __init__(self, *args, **kwargs):
        self.view_names = ["xform-detail", "dataviews-detail"]
        self.resolve = resolve
        self.reverse = reverse
        self.format = kwargs.pop("format", "json")
        # pylint: disable=bad-super-call
        super(serializers.RelatedField, self).__init__(*args, **kwargs)

    def _setup_field(self, view_name):
        # pylint: disable=attribute-defined-outside-init
        self.lookup_url_kwarg = self.lookup_field

        if view_name == "xform-detail":
            # pylint: disable=attribute-defined-outside-init
            self.queryset = XForm.objects.all()

        if view_name == "dataviews-detail":
            # pylint: disable=attribute-defined-outside-init
            self.queryset = DataView.objects.all()

    def to_representation(self, value):
        """Set's the self.view_name based on the type of ``value``."""
        if isinstance(value, XForm):
            # pylint: disable=attribute-defined-outside-init
            self.view_name = "xform-detail"
        elif isinstance(value, DataView):
            # pylint: disable=attribute-defined-outside-init
            self.view_name = "dataviews-detail"
        else:
            raise ValueError(_("Unknown type for content_object."))

        self._setup_field(self.view_name)

        return super().to_representation(value)

    def to_internal_value(self, data):
        """Verifies that ``data`` is a valid URL."""
        try:
            http_prefix = data.startswith(("http:", "https:"))
        except AttributeError:
            self.fail("incorrect_type", data_type=type(data).__name__)
        input_data = data
        if http_prefix:
            # If needed convert absolute URLs to relative path
            data = urlparse(data).path
            prefix = get_script_prefix()
            if data.startswith(prefix):
                data = "/" + data[len(prefix) :]

        try:
            match = self.resolve(data)
        except Resolver404:
            self.fail("no_match")

        if match.view_name not in self.view_names:
            self.fail("incorrect_match", input=input_data)

        self._setup_field(match.view_name)

        try:
            return self.get_object(match.view_name, match.args, match.kwargs)
        except (ObjectDoesNotExist, TypeError, ValueError):
            self.fail("does_not_exist")

        return data

    def use_pk_only_optimization(self):
        return False


class WidgetSerializer(serializers.HyperlinkedModelSerializer):
    """
    WidgetSerializer
    """

    # pylint: disable=invalid-name
    id = serializers.ReadOnlyField()
    url = serializers.HyperlinkedIdentityField(
        view_name="widgets-detail", lookup_field="pk"
    )
    content_object = GenericRelatedField()
    key = serializers.CharField(read_only=True)
    data = serializers.SerializerMethodField()
    order = serializers.IntegerField(required=False)
    metadata = JsonField(required=False)

    # pylint: disable=too-few-public-methods
    class Meta:
        """
        Meta model - specifies the fields in the Model Widget for the serializer
        """

        model = Widget
        fields = (
            "id",
            "url",
            "key",
            "title",
            "description",
            "widget_type",
            "order",
            "view_type",
            "column",
            "group_by",
            "content_object",
            "data",
            "aggregation",
            "metadata",
        )

    def get_data(self, obj):
        """
        Return the Widget.query_data(obj)
        """
        # Get the request obj
        request = self.context.get("request")

        # Check if data flag is present
        data_flag = request.GET.get("data")
        key = request.GET.get("key")

        if (str2bool(data_flag) or key) and obj:
            data = Widget.query_data(obj)
        else:
            data = []

        return data

    def validate(self, attrs):
        """Validate the effective widget fields for creates and updates."""
        instance = self.instance
        content_object = attrs.get(
            "content_object",
            instance.content_object if instance is not None else None,
        )
        column = attrs.get("column", instance.column if instance is not None else None)
        group_by = attrs.get(
            "group_by", instance.group_by if instance is not None else None
        )

        xform = None
        if isinstance(content_object, XForm):
            xform = content_object
        elif isinstance(content_object, DataView):
            xform = content_object.xform

        errors = {}
        canonical_column = None
        if xform is not None and column:
            try:
                _column_field, canonical_column = resolve_field_xpath(column, xform)
            except Http404:
                errors["column"] = _("'%(column)s' not in the form.") % {
                    "column": column
                }

        canonical_group_by = None
        if xform is not None and group_by:
            try:
                _group_by_field, canonical_group_by = resolve_field_xpath(
                    group_by, xform
                )
            except Http404:
                errors["group_by"] = _("'%(group_by)s' not in the form.") % {
                    "group_by": group_by
                }

        if isinstance(content_object, DataView):
            selected_columns = set(content_object.columns or [])
            if (
                canonical_column is not None
                and canonical_column not in selected_columns
                and canonical_column not in FIELD_DATA_MAP
            ):
                errors["column"] = _("'%(column)s' not in the DataView.") % {
                    "column": column
                }
            if (
                canonical_group_by is not None
                and canonical_group_by not in selected_columns
            ):
                errors["group_by"] = _("'%(group_by)s' not in the DataView.") % {
                    "group_by": group_by
                }

        if errors:
            raise serializers.ValidationError(errors)

        order = attrs.get("order")

        # Set the order
        if order:
            self.instance.to(order)

        return attrs

    def validate_content_object(self, value):
        """
        Validate if a user is the owner f the organization.
        """
        request = self.context.get("request")
        users = get_users_with_perms(
            value.project, attach_perms=False, with_group_users=False
        )

        profile = value.project.organization.profile
        # Shared or an admin in the organization
        is_owner = OwnerRole.user_has_role(request.user, profile)
        if request.user not in users and not is_organization(profile) and not is_owner:
            raise serializers.ValidationError(
                _("You don't have permission to the Project.")
            )

        return value
