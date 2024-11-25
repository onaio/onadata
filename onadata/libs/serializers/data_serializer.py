# -*- coding: utf-8 -*-
"""
Submission data serializers module.
"""

from io import BytesIO

from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _

import xmltodict
from rest_framework import exceptions, serializers
from rest_framework.reverse import reverse

from onadata.apps.logger.models import Project, XForm
from onadata.apps.logger.models.instance import Instance, InstanceHistory
from onadata.libs.data import parse_int
from onadata.libs.serializers.fields.json_field import JsonField
from onadata.libs.utils.analytics import TrackObjectEvent
from onadata.libs.utils.common_tags import (
    ATTACHMENTS,
    DATE_MODIFIED,
    GEOLOCATION,
    METADATA_FIELDS,
    NOTES,
    TAGS,
    UUID,
    VERSION,
    XFORM_ID,
    XFORM_ID_STRING,
)
from onadata.libs.utils.dict_tools import (
    dict_lists2strings,
    dict_paths2dict,
    floip_response_headers_dict,
    query_list_to_dict,
)
from onadata.libs.utils.logger_tools import (
    dict2xform,
    remove_metadata_fields,
    safe_create_instance,
)

NUM_FLOIP_COLUMNS = 6


def get_request_and_username(context):
    """
    Returns request object and username
    """
    request = context["request"]
    view = context["view"]
    username = view.kwargs.get("username")
    form_pk = view.kwargs.get("xform_pk")
    project_pk = view.kwargs.get("project_pk")

    if not username:
        # get the username from the XForm object if form_id is
        # present else utilize the request users username
        if form_pk:
            form_pk = parse_int(form_pk)
            if form_pk:
                form = get_object_or_404(XForm, pk=form_pk)
                username = form.user.username
            else:
                raise ValueError(_("Invalid XForm id."))
        elif project_pk:
            project_pk = parse_int(project_pk)
            if project_pk:
                project = get_object_or_404(Project, pk=project_pk)
                username = project.user.username
            else:
                raise ValueError(_("Invalid Project id."))
        else:
            username = request.user and request.user.username

    return (request, username)


def create_submission(request, username, data_dict, xform_id, gen_uuid: bool = False):
    """
    Returns validated data object instances
    """
    xml_string = dict2xform(data_dict, xform_id, username=username, gen_uuid=gen_uuid)
    xml_file = BytesIO(xml_string.encode("utf-8"))

    error, instance = safe_create_instance(username, xml_file, [], None, request)
    if error:
        raise serializers.ValidationError(error.message)

    return instance


class DataSerializer(serializers.HyperlinkedModelSerializer):
    """
    DataSerializer class - used for the list view to show `id`, `id_string`,
    `title` and `description`.
    """

    url = serializers.HyperlinkedIdentityField(view_name="data-list", lookup_field="pk")

    class Meta:
        model = XForm
        fields = ("id", "id_string", "title", "description", "url")


class JsonDataSerializer(serializers.Serializer):
    """
    JSON DataSerializer class - for json field data representation.
    """

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass

    def to_representation(self, instance):
        return instance


class InstanceHistorySerializer(serializers.ModelSerializer):
    """
    InstanceHistorySerializer class - for the json field data representation.
    """

    json = JsonField()

    class Meta:
        model = InstanceHistory
        fields = ("json",)

    def to_representation(self, instance):
        ret = super().to_representation(instance)

        return ret["json"] if "json" in ret else ret


class DataInstanceXMLSerializer(serializers.ModelSerializer):
    """
    DataInstanceXMLSerializer class - for XML field data representation
    on the Instance model.
    """

    class Meta:
        model = Instance
        fields = ("xml",)

    def _convert_metadata_field_to_attribute(self, field: str) -> str:
        """
        Converts a metadata field such as `_review_status` into
        a camel cased attribute `reviewStatus`
        """
        split_field = field.split("_")[1:]
        return split_field[0] + "".join(word.title() for word in split_field[1:])

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if "xml" in ret:
            ret = xmltodict.parse(ret["xml"], cdata_key="")

        # Add Instance attributes to representation
        instance_attributes = {
            "@formVersion": instance.version,
            "@lastModified": instance.date_modified.isoformat(),
            "@dateCreated": instance.date_created.isoformat(),
            "@objectID": str(instance.id),
        }
        ret.update(instance_attributes)
        excluded_metadata = [
            NOTES,
            TAGS,
            GEOLOCATION,
            XFORM_ID,
            DATE_MODIFIED,
            VERSION,
            ATTACHMENTS,
            XFORM_ID_STRING,
            UUID,
        ]
        additional_attributes = [
            (self._convert_metadata_field_to_attribute(metadata), metadata)
            for metadata in METADATA_FIELDS
            if metadata not in excluded_metadata
        ]
        for attrib, meta_field in additional_attributes:
            meta_value = instance.json.get(meta_field, "")
            if not isinstance(meta_value, str):
                meta_value = str(meta_value)
            ret.update({f"@{attrib}": meta_value})

        # Include linked resources
        linked_resources = {
            "linked-resources": {
                "attachments": instance.json.get(ATTACHMENTS),
                "notes": instance.json.get(NOTES),
            }
        }
        ret.update(linked_resources)
        return ret


class DataInstanceSerializer(serializers.ModelSerializer):
    """
    DataInstanceSerializer class - for json field data representation on the
    Instance (submission) model.
    """

    json = JsonField()

    class Meta:
        model = Instance
        fields = ("json",)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if "json" in ret:
            ret = ret["json"]
        return ret


class TableauDataSerializer(serializers.ModelSerializer):
    """
    TableauDataSerializer class - cleans out instance fields.
    """

    json = JsonField()

    class Meta:
        model = Instance
        fields = ("json",)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if "json" in ret:
            ret = ret["json"]
            # Remove metadata fields from the instance
            remove_metadata_fields(ret)

        return ret


class SubmissionSuccessMixin:  # pylint: disable=too-few-public-methods
    """
    SubmissionSuccessMixin - prepares submission success data/message.
    """

    def to_representation(self, instance):
        """
        Returns a dict with a successful submission message.
        """
        if instance is None:
            return super().to_representation(instance)

        return {
            "message": _("Successful submission."),
            "formid": instance.xform.id_string,
            "encrypted": instance.xform.encrypted,
            "instanceID": f"uuid:{instance.uuid}",
            "submissionDate": instance.date_created.isoformat(),
            "markedAsCompleteDate": instance.date_modified.isoformat(),
        }


class BaseRapidProSubmissionSerializer(SubmissionSuccessMixin, serializers.Serializer):
    """
    Base Rapidpro SubmissionSerializer - Implements the basic functionalities
    of a Rapidpro webhook serializer
    """

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass

    def validate(self, attrs):
        """
        Validate that the XForm ID is passed in view kwargs
        """
        view = self.context["view"]

        if "xform_pk" in view.kwargs:
            xform_pk = view.kwargs.get("xform_pk")
            xform = get_object_or_404(XForm, pk=xform_pk)
            attrs.update({"id_string": xform.id_string})
        else:
            raise serializers.ValidationError(
                {
                    "xform_pk": _(
                        "Incorrect url format. Use format "
                        "https://api.ona.io/username/formid/submission"
                    )
                }
            )

        return super().validate(attrs)


class SubmissionSerializer(SubmissionSuccessMixin, serializers.Serializer):
    """
    XML SubmissionSerializer - handles creating a submission from XML.
    """

    def update(self, instance, validated_data):
        pass

    def validate(self, attrs):
        try:
            request, __ = get_request_and_username(self.context)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))
        if not request.FILES or "xml_submission_file" not in request.FILES:
            raise serializers.ValidationError(_("No XML submission file."))

        return super().validate(attrs)

    @TrackObjectEvent(
        user_field="xform__user",
        properties={
            "submitted_by": "user",
            "xform_id": "xform__pk",
            "project_id": "xform__project__pk",
            "organization": "xform__user__profile__organization",
        },
        additional_context={"from": "XML Submissions"},
    )
    def create(self, validated_data):
        """
        Returns object instances based on the validated data
        """
        request, username = get_request_and_username(self.context)

        xml_file_list = request.FILES.pop("xml_submission_file", [])
        xml_file = xml_file_list[0] if xml_file_list else None
        media_files = request.FILES.values()

        error, instance = safe_create_instance(
            username, xml_file, media_files, None, request
        )
        if error:
            exc = exceptions.APIException(detail=error)
            exc.response = error
            exc.status_code = error.status_code

            raise exc

        return instance


class OSMSerializer(serializers.Serializer):
    """
    OSM Serializer - represents OSM data.
    """

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass

    def to_representation(self, instance):
        """
        Return a list of osm file objects from attachments.
        """
        return instance

    @property
    def data(self):
        """
        Returns the serialized data on the serializer.
        """
        # pylint: disable=attribute-defined-outside-init
        if not hasattr(self, "_data"):
            if self.instance is not None and not getattr(self, "_errors", None):
                self._data = self.to_representation(self.instance)
            elif hasattr(self, "_validated_data") and not getattr(
                self, "_errors", None
            ):
                self._data = self.to_representation(self.validated_data)
            else:
                self._data = self.get_initial()

        return self._data


class OSMSiteMapSerializer(serializers.Serializer):
    """
    OSM SiteMap Serializer.
    """

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass

    def to_representation(self, instance):
        """
        Return a list of osm file objects from attachments.
        """
        if instance is None:
            return super().to_representation(instance)

        id_string = instance.get("instance__xform__id_string")
        title = instance.get("instance__xform__title")
        user = instance.get("instance__xform__user__username")

        kwargs = {"pk": instance.get("instance__xform")}
        url = reverse("osm-list", kwargs=kwargs, request=self.context.get("request"))

        return {"url": url, "title": title, "id_string": id_string, "user": user}


class JSONSubmissionSerializer(SubmissionSuccessMixin, serializers.Serializer):
    """
    JSON SubmissionSerializer - handles JSON submission data.
    """

    def update(self, instance, validated_data):
        pass

    def validate(self, attrs):
        """
        Custom submission validator in request data.
        """
        request = self.context["request"]

        if "submission" not in request.data:
            raise serializers.ValidationError(
                {"submission": _("No submission key provided.")}
            )

        submission = request.data.get("submission")
        if not submission:
            raise serializers.ValidationError(
                {"submission": _("Received empty submission. No instance was created")}
            )

        return super().validate(attrs)

    @TrackObjectEvent(
        user_field="xform__user",
        properties={
            "submitted_by": "user",
            "xform_id": "xform__pk",
            "project_id": "xform__project__pk",
            "organization": "xform__user__profile__organization",
        },
        additional_context={"from": "JSON Submission"},
    )
    def create(self, validated_data):
        """
        Returns object instances based on the validated data
        """
        request, username = get_request_and_username(self.context)
        submission = request.data.get("submission")
        # convert lists in submission dict to joined strings
        try:
            submission_joined = dict_paths2dict(dict_lists2strings(submission))
        except AttributeError as exc:
            raise serializers.ValidationError(
                _(
                    "Incorrect format, see format details here,"
                    "https://api.ona.io/static/docs/submissions.html."
                )
            ) from exc

        instance = create_submission(
            request, username, submission_joined, request.data.get("id")
        )

        return instance


class RapidProSubmissionSerializer(BaseRapidProSubmissionSerializer):
    """
    Rapidpro SubmissionSerializer - handles Rapidpro webhook post.
    """

    def update(self, instance, validated_data):
        pass

    @TrackObjectEvent(
        user_field="xform__user",
        properties={
            "submitted_by": "user",
            "xform_id": "xform__pk",
            "project_id": "xform__project__pk",
        },
        additional_context={"from": "RapidPro"},
    )
    def create(self, validated_data):
        """
        Returns object instances based on the validated data.
        """
        request, username = get_request_and_username(self.context)
        rapidpro_dict = query_list_to_dict(request.data.get("values"))
        instance = create_submission(
            request, username, rapidpro_dict, validated_data["id_string"], gen_uuid=True
        )

        return instance


class RapidProJSONSubmissionSerializer(BaseRapidProSubmissionSerializer):
    """
    Rapidpro SubmissionSerializer - handles RapidPro JSON webhook posts
    """

    def update(self, instance, validated_data):
        pass

    @TrackObjectEvent(
        user_field="xform__user",
        properties={
            "submitted_by": "user",
            "xform_id": "xform__pk",
            "project_id": "xform__project__pk",
        },
        additional_context={"from": "RapidPro(JSON)"},
    )
    def create(self, validated_data):
        """
        Returns object instances based on validated data.
        """
        request, username = get_request_and_username(self.context)
        post_data = request.data.get("results")
        instance_data_dict = {k: post_data[k].get("value") for k in post_data.keys()}
        instance = create_submission(
            request,
            username,
            instance_data_dict,
            validated_data["id_string"],
            gen_uuid=True,
        )
        return instance


class FLOIPListSerializer(serializers.ListSerializer):
    """
    Custom ListSerializer for a FLOIP submission.
    """

    def update(self, instance, validated_data):
        pass

    @TrackObjectEvent(
        user_field="xform__user",
        properties={
            "submitted_by": "user",
            "xform_id": "xform__pk",
            "project_id": "xform__project__pk",
        },
        additional_context={"from": "FLOIP"},
    )
    def create(self, validated_data):
        """
        Returns object instances based on the validated data.
        """
        request, username = get_request_and_username(self.context)
        xform_pk = self.context["view"].kwargs["xform_pk"]
        xform = get_object_or_404(XForm, pk=xform_pk)
        xform_headers = xform.get_keys()
        flow_dict = floip_response_headers_dict(request.data, xform_headers)
        instance = create_submission(request, username, flow_dict, xform)
        return [instance]


class FLOIPSubmissionSerializer(SubmissionSuccessMixin, serializers.Serializer):
    """
    FLOIP SubmmissionSerializer - Handles a row of FLOIP specification format.
    """

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass

    def run_validators(self, value):
        # Only run default run_validators if we have validators attached to the
        # serializer.
        if self.validators:
            return super().run_validators(value)

        return []

    def validate(self, attrs):
        """
        Custom list data validator.
        """
        data = self.context["request"].data
        error_msg = None

        if not isinstance(data, list):
            error_msg = "Invalid format. Expecting a list."
        elif data:
            for row_i, row in enumerate(data):
                if len(row) != NUM_FLOIP_COLUMNS:
                    error_msg = _(
                        "Wrong number of values (%(values)d) in row"
                        " %(row)d, expecting %(expected)d values"
                        % {
                            "row": row_i,
                            "values": (len(row)),
                            "expected": NUM_FLOIP_COLUMNS,
                        }
                    )
                break

        if error_msg:
            raise serializers.ValidationError(_(error_msg))

        return super().validate(attrs)

    def to_internal_value(self, data):
        """
        Overrides validating rows in list data.
        """
        if isinstance(data, list) and len(data) == 6:
            data = {data[1]: data}

        return data

    class Meta:
        """
        Call the list serializer class to create an instance.
        """

        list_serializer_class = FLOIPListSerializer
