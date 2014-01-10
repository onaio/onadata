import json
from django import forms
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _
from rest_framework import exceptions, permissions
from rest_framework.decorators import link
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.viewsets import ViewSet
from rest_framework.mixins import CreateModelMixin, ListModelMixin,\
    RetrieveModelMixin
from taggit.forms import TagField

from onadata.apps.api.tools import get_accessible_forms, get_xform
from onadata.apps.odk_logger.models import Instance
from onadata.apps.odk_viewer.models.parsed_instance import ParsedInstance
from onadata.libs.utils.user_auth import check_and_set_form_by_id,\
    check_and_set_form_by_id_string


class ChartsViewSet(ViewSet):
    """
Returns a html view of a chart that could be embedded in an iframe.

Example:

    GET /api/v1/charts/ukanga/1/bar/field-name

Response:

    [
        {
            "count": 8,
            "day_of_submission": "2013-11-15",
        },
        {
            "count": 99,
            "day_of_submission": "2013-11-16",
        },
        {
            "count": 133,
            "day_of_submission": "2013-11-17",
        },
        {
            "count": 162,
            "day_of_submission": "2013-11-18",
        },
        {
            "count": 102,
            "day_of_submission": "2013-11-19",
        }
    ]
"""
    #lookup_fields = ('owner', 'formid', 'chart_type', 'field_name')

    @link()
    def chart(self, request, owner, formid, chart_type, field_name):
        #xform = get_xform(request, formid)
        return Response('<html></html>')
