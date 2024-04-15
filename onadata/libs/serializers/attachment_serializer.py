# -*- coding: utf-8 -*-
"""
Attachments serializer.
"""

from rest_framework import serializers
from six import itervalues

from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.logger.models.instance import Instance, get_attachment_url
from onadata.libs.utils.decorators import check_obj


def dict_key_for_value(_dict, value):
    """
    This function is used to get key by value in a dictionary
    """
    return list(_dict)[list(itervalues(_dict)).index(value)]


def get_path(data, question_name, path_list):
    """
    A recursive function that returns the xpath of a media file
    :param json data: JSON representation of xform
    :param string question_name: Name of media file being searched for
    :param list path_list: Contains the names that make up the xpath
    :return: an xpath which is a string or None if name cannot be found
    :rtype: string or None
    """
    name = data.get("name")
    if name == question_name:
        return "/".join(path_list)
    if data.get("children") is not None:
        for node in data.get("children"):
            path_list.append(node.get("name"))
            path = get_path(node, question_name, path_list)
            if path is not None:
                return path
            del path_list[len(path_list) - 1]
    return None


class AttachmentSerializer(serializers.HyperlinkedModelSerializer):
    """
    Attachments serializer
    """

    url = serializers.HyperlinkedIdentityField(
        view_name="attachment-detail", lookup_field="pk"
    )
    field_xpath = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    small_download_url = serializers.SerializerMethodField()
    medium_download_url = serializers.SerializerMethodField()
    xform = serializers.SerializerMethodField()
    instance = serializers.PrimaryKeyRelatedField(queryset=Instance.objects.all())
    filename = serializers.ReadOnlyField(source="media_file.name")

    class Meta:
        fields = (
            "url",
            "filename",
            "mimetype",
            "field_xpath",
            "id",
            "xform",
            "instance",
            "download_url",
            "small_download_url",
            "medium_download_url",
        )
        model = Attachment

    @check_obj
    def get_xform(self, obj):
        """
        Return xform_id - old forms xform id is in submission instance xform_id
        """
        if obj.xform is None:
            return obj.instance.xform_id

        return obj.xform_id

    @check_obj
    def get_download_url(self, obj):
        """
        Return attachment download url.
        """
        request = self.context.get("request")

        if obj:
            path = get_attachment_url(obj)

            return request.build_absolute_uri(path) if request else path
        return ""

    def get_small_download_url(self, obj):
        """
        Return attachment download url for resized small image.
        """
        request = self.context.get("request")

        if obj.mimetype.startswith("image"):
            path = get_attachment_url(obj, "small")

            return request.build_absolute_uri(path) if request else path
        return ""

    def get_medium_download_url(self, obj):
        """
        Return attachment download url for resized medium image.
        """
        request = self.context.get("request")

        if obj.mimetype.startswith("image"):
            path = get_attachment_url(obj, "medium")

            return request.build_absolute_uri(path) if request else path
        return ""

    def get_field_xpath(self, obj):
        """
        Return question xpath
        """
        qa_dict = obj.instance.get_dict()
        if obj.filename not in qa_dict.values():
            return None

        question_name = dict_key_for_value(qa_dict, obj.filename)
        data = obj.instance.xform.json_dict()

        return get_path(data, question_name, [])
