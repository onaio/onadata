# -*- coding: utf-8 -*-
"""
Tests the XForm viewset.
"""

from __future__ import unicode_literals

import codecs
import csv
import json
import os
import re
from builtins import open
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from http.client import BadStatusLine
from io import StringIO
from unittest.mock import Mock, patch
from xml.dom import Node

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.test.utils import override_settings
from django.utils.dateparse import parse_datetime
from django.utils.html import conditional_escape

import jwt
from defusedxml import minidom
from django_digest.test import DigestAuth
from flaky import flaky
from httmock import HTTMock
from rest_framework import status

from onadata.apps.api.tests.mocked_data import (
    enketo_error500_mock,
    enketo_error502_mock,
    enketo_error_mock,
    enketo_mock,
    enketo_mock_with_form_defaults,
    enketo_urls_mock,
    external_mock,
    external_mock_single_instance,
    external_mock_single_instance2,
    xls_url_no_extension_mock,
    xls_url_no_extension_mock_content_disposition_attr_jumbled_v1,
    xls_url_no_extension_mock_content_disposition_attr_jumbled_v2,
)
from onadata.apps.api.tests.viewsets.test_abstract_viewset import (
    TestAbstractViewSet,
    get_mocked_response_for_file,
)
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.logger.models import Attachment, EntityList, Instance, Project, XForm
from onadata.apps.logger.models.xform_version import XFormVersion
from onadata.apps.logger.views import delete_xform
from onadata.apps.logger.xform_instance_parser import XLSFormError
from onadata.apps.main.models import MetaData
from onadata.apps.messaging.constants import FORM_UPDATED, XFORM
from onadata.apps.viewer.models import Export
from onadata.libs.exceptions import EncryptionError
from onadata.libs.models.share_project import ShareProject
from onadata.libs.permissions import (
    ROLES_ORDERED,
    DataEntryMinorRole,
    DataEntryOnlyRole,
    DataEntryRole,
    EditorMinorRole,
    EditorNoDownload,
    EditorRole,
    ManagerRole,
    OwnerRole,
    ReadOnlyRole,
    ReadOnlyRoleNoDownload,
)
from onadata.libs.serializers.metadata_serializer import create_xform_meta_permissions
from onadata.libs.serializers.xform_serializer import (
    XFormBaseSerializer,
    XFormSerializer,
)
from onadata.libs.utils.api_export_tools import get_existing_file_format
from onadata.libs.utils.cache_tools import (
    ENKETO_URL_CACHE,
    PROJ_FORMS_CACHE,
    XFORM_DATA_VERSIONS,
    XFORM_PERMISSIONS_CACHE,
    safe_cache_delete,
)
from onadata.libs.utils.common_tags import GROUPNAME_REMOVED_FLAG, MONGO_STRFTIME
from onadata.libs.utils.common_tools import (
    filename_from_disposition,
    get_response_content,
)
from onadata.libs.utils.xform_utils import get_xform_users

ROLES = [ReadOnlyRole, DataEntryRole, EditorRole, ManagerRole, OwnerRole]

JWT_SECRET_KEY = "thesecretkey"
JWT_ALGORITHM = "HS256"


def fixtures_path(filepath):
    """Returns the file object at the given filepath."""
    return open(
        os.path.join(
            settings.PROJECT_ROOT, "libs", "tests", "utils", "fixtures", filepath
        ),
        "rb",
    )


def raise_bad_status_line(arg):
    """
    Raises http.client BadStatusLine
    """
    raise BadStatusLine("RANDOM STATUS")


class XFormViewSetBaseTestCase(TestAbstractViewSet):
    def _make_submission_over_date_range(self, start, days=1):
        self._publish_xls_form_to_project()

        start_time = start
        curr_time = start_time
        for survey in self.surveys:
            _submission_time = curr_time
            self._make_submission(
                os.path.join(
                    settings.PROJECT_ROOT,
                    "apps",
                    "main",
                    "tests",
                    "fixtures",
                    "transportation",
                    "instances",
                    survey,
                    survey + ".xml",
                ),
                forced_submission_time=_submission_time,
            )
            curr_time += timedelta(days=days)


class PublishXLSFormTestCase(XFormViewSetBaseTestCase):
    """Tests for publishing an XLSForm"""

    def setUp(self):
        super().setUp()

        self.view = XFormViewSet.as_view({"post": "create"})

    def test_form_publishing_arabic(self):
        with HTTMock(enketo_mock):
            xforms = XForm.objects.count()
            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "subdistrict_profiling_tool.xlsx",
            )
            with open(path, "rb") as xls_file:
                post_data = {"xls_file": xls_file}
                request = self.factory.post("/", data=post_data, **self.extra)
                response = self.view(request)
                self.assertEqual(xforms + 1, XForm.objects.count())
                self.assertEqual(response.status_code, 201)

    def test_publish_xlsform(self):
        with HTTMock(enketo_urls_mock):
            data = {
                "owner": "http://testserver/api/v1/users/bob",
                "public": False,
                "public_data": False,
                "description": "",
                "downloadable": True,
                "allows_sms": False,
                "encrypted": False,
                "sms_id_string": "transportation_2011_07_25",
                "id_string": "transportation_2011_07_25",
                "title": "transportation_2011_07_25",
                "bamboo_dataset": "",
            }
            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation.xlsx",
            )

            with open(path, "rb") as xls_file:
                post_data = {"xls_file": xls_file}
                request = self.factory.post("/", data=post_data, **self.extra)
                response = self.view(request)
                self.assertEqual(response.status_code, 201)
                xform = self.user.xforms.get(id_string="transportation_2011_07_25")
                data.update({"url": "http://testserver/api/v1/forms/%s" % xform.pk})

                self.assertDictContainsSubset(data, response.data)
                self.assertTrue(OwnerRole.user_has_role(self.user, xform))
                self.assertEqual("owner", response.data["users"][0]["role"])

                # pylint: disable=no-member
                self.assertIsNotNone(
                    MetaData.objects.get(object_id=xform.id, data_type="enketo_url")
                )
                self.assertIsNotNone(
                    MetaData.objects.get(
                        object_id=xform.id, data_type="enketo_preview_url"
                    )
                )

                # Ensure XFormVersion object is created on XForm publish
                versions_count = XFormVersion.objects.filter(xform=xform).count()
                self.assertEqual(versions_count, 1)

    def test_publish_xlsforms_with_same_id_string(self):
        with HTTMock(enketo_urls_mock):
            counter = XForm.objects.count()
            data = {
                "owner": "http://testserver/api/v1/users/bob",
                "public": False,
                "public_data": False,
                "description": "",
                "downloadable": True,
                "allows_sms": False,
                "encrypted": False,
                "sms_id_string": "transportation_2011_07_25",
                "id_string": "transportation_2011_07_25",
                "title": "transportation_2011_07_25",
                "bamboo_dataset": "",
            }
            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation.xlsx",
            )
            with open(path, "rb") as xls_file:
                post_data = {"xls_file": xls_file}
                request = self.factory.post("/", data=post_data, **self.extra)
                response = self.view(request)
                self.assertEqual(response.status_code, 201)
                xform = self.user.xforms.all()[0]
                data.update(
                    {
                        "url": "http://testserver/api/v1/forms/%s" % xform.pk,
                        "has_id_string_changed": False,
                    }
                )
                self.assertDictContainsSubset(data, response.data)
                self.assertTrue(OwnerRole.user_has_role(self.user, xform))
                self.assertEqual("owner", response.data["users"][0]["role"])

                # pylint: disable=no-member
                self.assertIsNotNone(
                    MetaData.objects.get(object_id=xform.id, data_type="enketo_url")
                )
                self.assertIsNotNone(
                    MetaData.objects.get(
                        object_id=xform.id, data_type="enketo_preview_url"
                    )
                )

            self.assertEqual(counter + 1, XForm.objects.count())
            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation_copy.xlsx",
            )

            with open(path, "rb") as xls_file:
                post_data = {"xls_file": xls_file}
                request = self.factory.post("/", data=post_data, **self.extra)
                response = self.view(request)
                self.assertEqual(response.status_code, 201)
                xform = self.user.xforms.get(id_string="Transportation_2011_07_25_1")
                data.update(
                    {
                        "url": "http://testserver/api/v1/forms/%s" % xform.pk,
                        "id_string": "Transportation_2011_07_25_1",
                        "title": "Transportation_2011_07_25",
                        "sms_id_string": "Transportation_2011_07_25",
                        "has_id_string_changed": True,
                    }
                )

                self.assertDictContainsSubset(data, response.data)
                self.assertTrue(OwnerRole.user_has_role(self.user, xform))
                self.assertEqual("owner", response.data["users"][0]["role"])

                # pylint: disable=no-member
                self.assertIsNotNone(
                    MetaData.objects.get(object_id=xform.id, data_type="enketo_url")
                )
                self.assertIsNotNone(
                    MetaData.objects.get(
                        object_id=xform.id, data_type="enketo_preview_url"
                    )
                )

            xform = XForm.objects.get(id_string="transportation_2011_07_25")
            self.assertIsInstance(xform, XForm)
            self.assertEqual(counter + 2, XForm.objects.count())

    # pylint: disable=invalid-name
    @patch("onadata.apps.main.forms.requests")
    def test_publish_xlsform_using_url_upload(self, mock_requests):
        with HTTMock(enketo_mock):
            xls_url = "https://ona.io/examples/forms/tutorial/form.xlsx"
            pre_count = XForm.objects.count()
            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation_different_id_string.xlsx",
            )

            with open(path, "rb") as xls_file:
                mock_response = get_mocked_response_for_file(
                    xls_file, "transportation_different_id_string.xlsx", 200
                )
                mock_requests.head.return_value = mock_response
                mock_requests.get.return_value = mock_response

                post_data = {"xls_url": xls_url}
                request = self.factory.post("/", data=post_data, **self.extra)
                response = self.view(request)

                mock_requests.get.assert_called_with(xls_url, timeout=30)
                xls_file.close()

                self.assertEqual(response.status_code, 201)
                self.assertEqual(XForm.objects.count(), pre_count + 1)

    # pylint: disable=invalid-name
    @patch("onadata.apps.main.forms.requests")
    def test_publish_xlsform_using_url_with_no_extension(self, mock_requests):
        with HTTMock(enketo_mock, xls_url_no_extension_mock):
            xls_url = "https://ona.io/examples/forms/tutorial/form"
            pre_count = XForm.objects.count()
            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation_different_id_string.xlsx",
            )

            with open(path, "rb") as xls_file:
                mock_response = get_mocked_response_for_file(
                    xls_file, "transportation_version.xlsx", 200
                )
                mock_requests.head.return_value = mock_response
                mock_requests.get.return_value = mock_response

                post_data = {"xls_url": xls_url}
                request = self.factory.post("/", data=post_data, **self.extra)
                response = self.view(request)

                self.assertEqual(response.status_code, 201, response.data)
                self.assertEqual(XForm.objects.count(), pre_count + 1)

    # pylint: disable=invalid-name
    @patch("onadata.apps.main.forms.requests")
    def test_publish_xlsform_using_url_content_disposition_attr_jumbled_v1(
        self, mock_requests
    ):
        with HTTMock(
            enketo_mock, xls_url_no_extension_mock_content_disposition_attr_jumbled_v1
        ):
            xls_url = "https://ona.io/examples/forms/tutorial/form"
            pre_count = XForm.objects.count()
            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation_different_id_string.xlsx",
            )

            with open(path, "rb") as xls_file:
                mock_response = get_mocked_response_for_file(
                    xls_file, "transportation_different_id_string.xlsx", 200
                )
                mock_requests.head.return_value = mock_response
                mock_requests.get.return_value = mock_response

                post_data = {"xls_url": xls_url}
                request = self.factory.post("/", data=post_data, **self.extra)
                response = self.view(request)

                self.assertEqual(response.status_code, 201)
                self.assertEqual(XForm.objects.count(), pre_count + 1)

    # pylint: disable=invalid-name
    @patch("onadata.apps.main.forms.requests")
    def test_publish_xlsform_using_url_content_disposition_attr_jumbled_v2(
        self, mock_requests
    ):
        with HTTMock(
            enketo_mock, xls_url_no_extension_mock_content_disposition_attr_jumbled_v2
        ):
            xls_url = "https://ona.io/examples/forms/tutorial/form"
            pre_count = XForm.objects.count()
            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation_different_id_string.xlsx",
            )

            with open(path, "rb") as xls_file:
                mock_response = get_mocked_response_for_file(
                    xls_file, "transportation_different_id_string.xlsx", 200
                )
                mock_requests.head.return_value = mock_response
                mock_requests.get.return_value = mock_response

                post_data = {"xls_url": xls_url}
                request = self.factory.post("/", data=post_data, **self.extra)
                response = self.view(request)

                self.assertEqual(response.status_code, 201)
                self.assertEqual(XForm.objects.count(), pre_count + 1)

    # pylint: disable=invalid-name
    @patch("onadata.apps.main.forms.requests")
    def test_publish_csvform_using_url_upload(self, mock_requests):
        with HTTMock(enketo_mock):
            csv_url = "https://ona.io/examples/forms/tutorial/form.csv"
            pre_count = XForm.objects.count()
            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "api",
                "tests",
                "fixtures",
                "text_and_integer.csv",
            )

            with open(path, "rb") as csv_file:
                mock_response = get_mocked_response_for_file(
                    csv_file, "text_and_integer.csv", 200
                )
                mock_requests.head.return_value = mock_response
                mock_requests.get.return_value = mock_response

                post_data = {"csv_url": csv_url}
                request = self.factory.post("/", data=post_data, **self.extra)
                response = self.view(request)

                mock_requests.get.assert_called_with(csv_url, timeout=30)
                csv_file.close()

                self.assertEqual(response.status_code, 201)
                self.assertEqual(XForm.objects.count(), pre_count + 1)

    # pylint: disable=invalid-name
    def test_publish_select_external_xlsform(self):
        with HTTMock(enketo_urls_mock):
            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "api",
                "tests",
                "fixtures",
                "select_one_external.xlsx",
            )
            with open(path, "rb") as xls_file:
                # pylint: disable=no-member
                meta_count = MetaData.objects.count()
                post_data = {"xls_file": xls_file}
                request = self.factory.post("/", data=post_data, **self.extra)
                response = self.view(request)
                xform = self.user.xforms.all()[0]
                self.assertEqual(response.status_code, 201)
                self.assertEqual(meta_count + 5, MetaData.objects.count())
                metadata = MetaData.objects.get(
                    object_id=xform.id, data_value="itemsets.csv"
                )
                self.assertIsNotNone(metadata)
                self.assertTrue(OwnerRole.user_has_role(self.user, xform))
                self.assertEqual("owner", response.data["users"][0]["role"], self.user)

    def test_publish_csv_with_universal_newline_xlsform(self):
        with HTTMock(enketo_mock):
            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "api",
                "tests",
                "fixtures",
                "universal_newline.csv",
            )
            with open(path, encoding="utf-8") as xls_file:
                post_data = {"xls_file": xls_file}
                request = self.factory.post("/", data=post_data, **self.extra)
                response = self.view(request)
                self.assertEqual(response.status_code, 201, response.data)

    def test_publish_xlsform_anon(self):
        path = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "main",
            "tests",
            "fixtures",
            "transportation",
            "transportation.xlsx",
        )
        username = "Anon"
        error_msg = "User with username %s does not exist." % username
        with open(path, "rb") as xls_file:
            post_data = {"xls_file": xls_file, "owner": username}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = self.view(request)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.data.get("message"), error_msg)

    def test_publish_invalid_xls_form(self):
        path = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "main",
            "tests",
            "fixtures",
            "transportation",
            "transportation.bad_id.xlsx",
        )
        with open(path, "rb") as xls_file:
            post_data = {"xls_file": xls_file}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = self.view(request)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get("Cache-Control"), None)
            error_msg = (
                "In strict mode, the XForm ID must be "
                "a valid slug and contain no spaces."
                " Please ensure that you have set an"
                " id_string in the settings sheet or "
                "have modified the filename to not "
                "contain any spaces."
            )
            self.assertEqual(response.data.get("text"), error_msg)

        path = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "main",
            "tests",
            "fixtures",
            "transportation",
            "transportation_ampersand_in_title.xlsx",
        )
        with open(path, "rb") as xls_file:
            post_data = {"xls_file": xls_file}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = self.view(request)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get("Cache-Control"), None)
            error_msg = "Title shouldn't have any invalid xml characters ('>' '&' '<')"
            self.assertEqual(response.data.get("text"), error_msg)

    def test_publish_invalid_xls_form_no_choices(self):
        path = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "main",
            "tests",
            "fixtures",
            "transportation",
            "transportation.no_choices.xlsx",
        )
        with open(path, "rb") as xls_file:
            post_data = {"xls_file": xls_file}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = self.view(request)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get("Cache-Control"), None)
            error_msg = (
                "There should be a choices sheet in this xlsform. "
                "Please ensure that the choices sheet has the mandatory columns "
                "'list_name', 'name', and 'label'."
            )
            self.assertEqual(response.data.get("text"), error_msg)

    def test_upload_xml_form_file(self):
        with HTTMock(enketo_mock):
            path = os.path.join(
                os.path.dirname(__file__), "..", "fixtures", "forms", "contributions"
            )
            form_path = os.path.join(path, "contributions.xml")
            xforms = XForm.objects.count()

            with open(form_path, encoding="utf-8") as xml_file:
                post_data = {"xml_file": xml_file}
                request = self.factory.post("/", data=post_data, **self.extra)
                response = self.view(request)
                self.assertEqual(xforms + 1, XForm.objects.count())
                self.assertEqual(response.status_code, 201)

            instances_path = os.path.join(path, "instances")
            for uuid in os.listdir(instances_path):
                s_path = os.path.join(instances_path, uuid, "submission.xml")
                self._make_submission(s_path)
            xform = XForm.objects.last()
            self.assertEqual(xform.instances.count(), 6)

    def test_form_publishing_floip(self):
        self.skipTest("FLOIP package out of date with pyxform 3.0.0")
        with HTTMock(enketo_mock):
            xforms = XForm.objects.count()
            path = os.path.join(
                os.path.dirname(__file__),
                "../",
                "fixtures",
                "flow-results-example-1.json",
            )
            with open(path, "rb") as xls_file:
                post_data = {"floip_file": xls_file}
                request = self.factory.post("/", data=post_data, **self.extra)
                response = self.view(request)
                self.assertEqual(response.status_code, 201, response.data)
                self.assertEqual(xforms + 1, XForm.objects.count())

    def test_external_choice_integer_name_xlsform(self):
        """Test that names with integers are converted to strings"""
        with HTTMock(enketo_urls_mock):
            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "api",
                "tests",
                "fixtures",
                "integer_name_test.xlsx",
            )
            with open(path, "rb") as xls_file:
                # pylint: disable=no-member
                meta_count = MetaData.objects.count()
                post_data = {"xls_file": xls_file}
                request = self.factory.post("/", data=post_data, **self.extra)
                response = self.view(request)
                xform = self.user.xforms.all()[0]
                self.assertEqual(response.status_code, 201)
                self.assertEqual(meta_count + 5, MetaData.objects.count())
                metadata = MetaData.objects.get(
                    object_id=xform.id, data_value="itemsets.csv"
                )
                self.assertIsNotNone(metadata)

                csv_reader = csv.reader(codecs.iterdecode(metadata.data_file, "utf-8"))
                expected_data = [
                    ["list_name", "name", "label", "state", "county"],
                    ["states", "1", "Texas", "", ""],
                    ["states", "2", "Washington", "", ""],
                    ["counties", "b1", "King", "2", ""],
                    ["counties", "b2", "Pierce", "2", ""],
                    ["counties", "b3", "King", "1", ""],
                    ["counties", "b4", "Cameron", "1", ""],
                    ["cities", "dumont", "Dumont", "1", "b3"],
                    ["cities", "finney", "Finney", "1", "b3"],
                    ["cities", "brownsville", "brownsville", "1", "b4"],
                    ["cities", "harlingen", "harlingen", "1", "b4"],
                    ["cities", "seattle", "Seattle", "2", "b3"],
                    ["cities", "redmond", "Redmond", "2", "b3"],
                    ["cities", "tacoma", "Tacoma", "2", "b2"],
                    ["cities", "puyallup", "Puyallup", "2", "b2"],
                ]
                for index, row in enumerate(csv_reader):
                    self.assertEqual(row, expected_data[index])


class TestXFormViewSet(XFormViewSetBaseTestCase):
    """Test XFormViewSet"""

    def setUp(self):
        super(TestXFormViewSet, self).setUp()
        self.view = XFormViewSet.as_view(
            {
                "get": "list",
            }
        )

    @patch("onadata.apps.api.viewsets.xform_viewset.send_message")
    @flaky
    def test_replace_form_with_external_choices(self, mock_send_message):
        with HTTMock(enketo_mock):
            xls_file_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "logger",
                "fixtures",
                "external_choice_form_v1.xlsx",
            )
            self._publish_xls_form_to_project(xlsform_path=xls_file_path)

            self.assertIsNotNone(self.xform.version)
            form_id = self.xform.pk

            self.view = XFormViewSet.as_view(
                {
                    "get": "retrieve",
                }
            )

            request = self.factory.get("/", **self.extra)
            response = self.view(request, pk=self.xform.id)
            self.assertEqual(response.status_code, 200)
            self.assertNotEqual(response.get("Cache-Control"), None)

            view = XFormViewSet.as_view(
                {
                    "patch": "partial_update",
                }
            )

            xls_file_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "logger",
                "fixtures",
                "external_choice_form_v2.xlsx",
            )
            with open(xls_file_path, "rb") as xls_file:
                post_data = {"xls_file": xls_file}
                request = self.factory.patch("/", data=post_data, **self.extra)
                response = view(request, pk=form_id)
                self.assertEqual(response.status_code, 200)
            # send message upon form update
            self.assertTrue(mock_send_message.called)
            mock_send_message.assert_called_with(
                instance_id=self.xform.id,
                target_id=self.xform.id,
                target_type=XFORM,
                user=request.user,
                message_verb=FORM_UPDATED,
            )

    def test_form_publishing_using_invalid_text_xls_form(self):
        view = ProjectViewSet.as_view({"post": "forms"})
        self._project_create()
        project_id = self.project.pk

        invalid_post_data = {
            "downloadable": ["True"],
            "text_xls_form": ["invalid data"],
        }
        request = self.factory.post("/", data=invalid_post_data, **self.extra)
        response = view(request, pk=project_id)
        self.assertEqual(response.status_code, 400)

    def test_form_publishing_using_text_xls_form(self):
        view = ProjectViewSet.as_view({"post": "forms"})
        self._project_create()
        project_id = self.project.pk

        pre_count = XForm.objects.count()
        valid_post_data = {
            "downloadable": ["True"],
            "text_xls_form": [
                (
                    "survey\r\n,"
                    "required,type,name,label,calculation\r\n,"
                    "true,text,What_is_your_name,What is your name\r\n,"
                    ",calculate,__version__,,'vbP67kPMwnY8aTFcFHgWMN'\r\n"
                    "settings\r\n,"
                    "form_title,version,id_string\r\n,"
                    "Demo to Jonathan,vbP67kPMwnY8aTFcFHgWMN,"
                    "afPkTij9pVg8T8c35h3SvS\r\n"
                )
            ],
        }

        request = self.factory.post("/", data=valid_post_data, **self.extra)
        response = view(request, pk=project_id)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(XForm.objects.count(), pre_count + 1)

        updated_post_data = {
            "downloadable": ["True"],
            "text_xls_form": [
                (
                    "survey\r\n,"
                    "required,type,name,label,calculation\r\n,"
                    "true,text,What_is_your_name,What is your name\r\n,"
                    "true,integer,What_is_your_age,What is your age\r\n,"
                    ",calculate,__version__,,'vB9EtM9inCMPC4qpPcuX3h'\r\n"
                    "settings\r\n,"
                    "form_title,version,id_string\r\n,"
                    "Demo to Jonathan,vB9EtM9inCMPC4qpPcuX3h,"
                    "afPkTij9pVg8T8c35h3SvS\r\n"
                )
            ],
        }

        xform = XForm.objects.last()
        view = XFormViewSet.as_view(
            {
                "patch": "partial_update",
            }
        )
        request = self.factory.patch("/", data=updated_post_data, **self.extra)
        response = view(request, pk=xform.id)
        self.assertEqual(response.status_code, 200)

    def test_instances_with_geopoints_true_for_instances_with_geopoints(self):
        with HTTMock(enketo_mock):
            xls_file_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "logger",
                "fixtures",
                "tutorial",
                "tutorial.xlsx",
            )

            self._publish_xls_form_to_project(xlsform_path=xls_file_path)

            xml_submission_file_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "logger",
                "fixtures",
                "tutorial",
                "instances",
                "tutorial_2012-06-27_11-27-53.xml",
            )

            self._make_submission(xml_submission_file_path)
            self.xform.refresh_from_db()

            view = XFormViewSet.as_view(
                {
                    "get": "retrieve",
                }
            )
            formid = self.xform.pk
            request = self.factory.get("/", **self.extra)
            response = view(request, pk=formid)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.data.get("instances_with_geopoints"))

            Instance.objects.get(xform__id=formid).delete()
            request = self.factory.get("/", **self.extra)
            response = view(request, pk=formid)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.data.get("instances_with_geopoints"))

    def test_form_list(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            request = self.factory.get("/", **self.extra)
            response = self.view(request)
            self.assertNotEqual(response.get("Cache-Control"), None)

    @override_settings(STREAM_DATA=True)
    def test_form_list_stream(self):
        view = XFormViewSet.as_view(
            {
                "get": "list",
            }
        )
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            request = self.factory.get("/", **self.extra)
            response = view(request)
            self.assertTrue(response.streaming)
            streaming_data = json.loads(
                "".join([i.decode("utf-8") for i in response.streaming_content])
            )
            self.assertIsInstance(streaming_data, list)
            self.assertNotEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.status_code, 200)

    def test_form_list_with_pagination(self):
        view = XFormViewSet.as_view(
            {
                "get": "list",
            }
        )
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            form_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation_different_id_string.xlsx",
            )
            self._publish_xls_form_to_project(xlsform_path=form_path)
            # no page param no pagination
            request = self.factory.get("/", **self.extra)
            response = view(request)
            self.assertNotEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(len(response.data), 2)

            # test pagination
            request = self.factory.get(
                "/", data={"page": 1, "page_size": 1}, **self.extra
            )
            response = view(request)
            self.assertEqual(response.status_code, 200)
            # check that only one form is returned
            self.assertEqual(len(response.data), 1)

    @override_settings(STREAM_DATA=True)
    def test_form_list_stream_with_pagination(self):
        view = XFormViewSet.as_view(
            {
                "get": "list",
            }
        )
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            form_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation_different_id_string.xlsx",
            )
            self._publish_xls_form_to_project(xlsform_path=form_path)
            # no page param no pagination
            request = self.factory.get("/", **self.extra)
            response = view(request)
            self.assertTrue(response.streaming)
            streaming_data = json.loads(
                "".join([i.decode("utf-8") for i in response.streaming_content])
            )
            self.assertNotEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(streaming_data), 2)

            # test pagination
            request = self.factory.get(
                "/", data={"page": 1, "page_size": 1}, **self.extra
            )
            response = view(request)
            self.assertTrue(response.streaming)
            streaming_data = json.loads(
                "".join([i.decode("utf-8") for i in response.streaming_content])
            )
            self.assertEqual(response.status_code, 200)
            # check that only one form is returned
            self.assertEqual(len(streaming_data), 1)

    def test_form_list_without_enketo_connection(self):
        self._publish_xls_form_to_project()
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)

    def test_form_list_anon(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            request = self.factory.get("/")
            response = self.view(request)
            self.assertEqual(response.status_code, 200)
            self.assertNotEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.data, [])

    def test_public_form_list(self):
        with HTTMock(enketo_urls_mock):
            self._publish_xls_form_to_project()
            self.view = XFormViewSet.as_view(
                {
                    "get": "retrieve",
                }
            )
            request = self.factory.get("/", **self.extra)
            response = self.view(request, pk="public")
            self.assertEqual(response.status_code, 200)
            self.assertNotEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.data, [])

            # public shared form
            self.xform.shared = True
            self.xform.save()
            response = self.view(request, pk="public")
            self.assertNotEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.status_code, 200)
            self.form_data["public"] = True
            # pylint: disable=no-member
            resultset = MetaData.objects.filter(
                Q(object_id=self.xform.pk),
                Q(data_type="enketo_url")
                | Q(data_type="enketo_preview_url")
                | Q(data_type="enketo_single_submit_url")
                | Q(data_type="xform_meta_perms"),
            )
            url = resultset.get(data_type="enketo_url")
            preview_url = resultset.get(data_type="enketo_preview_url")
            single_submit_url = resultset.get(data_type="enketo_single_submit_url")
            meta_perms = resultset.get(data_type="xform_meta_perms")
            self.form_data["metadata"] = [
                OrderedDict(
                    [
                        ("id", meta_perms.pk),
                        ("xform", self.xform.pk),
                        (
                            "data_value",
                            "editor|dataentry|readonly",
                        ),
                        ("data_type", "xform_meta_perms"),
                        ("data_file", None),
                        ("extra_data", {}),
                        ("data_file_type", None),
                        ("media_url", None),
                        ("file_hash", None),
                        ("url", f"http://testserver/api/v1/metadata/{meta_perms.pk}"),
                        ("date_created", meta_perms.date_created),
                    ]
                ),
                OrderedDict(
                    [
                        ("id", url.pk),
                        ("xform", self.xform.pk),
                        ("data_value", "https://enketo.ona.io/::YY8M"),
                        ("data_type", "enketo_url"),
                        ("data_file", None),
                        ("extra_data", {}),
                        ("data_file_type", None),
                        ("media_url", None),
                        ("file_hash", None),
                        ("url", "http://testserver/api/v1/metadata/%s" % url.pk),
                        ("date_created", url.date_created),
                    ]
                ),
                OrderedDict(
                    [
                        ("id", preview_url.pk),
                        ("xform", self.xform.pk),
                        ("data_value", "https://enketo.ona.io/preview/::YY8M"),
                        ("data_type", "enketo_preview_url"),
                        ("data_file", None),
                        ("extra_data", {}),
                        ("data_file_type", None),
                        ("media_url", None),
                        ("file_hash", None),
                        (
                            "url",
                            "http://testserver/api/v1/metadata/%s" % preview_url.pk,
                        ),
                        ("date_created", preview_url.date_created),
                    ]
                ),
                OrderedDict(
                    [
                        ("id", single_submit_url.pk),
                        ("xform", self.xform.pk),
                        ("data_value", "http://enketo.ona.io/single/::XZqoZ94y"),
                        ("data_type", "enketo_single_submit_url"),
                        ("data_file", None),
                        ("extra_data", {}),
                        ("data_file_type", None),
                        ("media_url", None),
                        ("file_hash", None),
                        (
                            "url",
                            "http://testserver/api/v1/metadata/%s"
                            % single_submit_url.pk,
                        ),
                        ("date_created", single_submit_url.date_created),
                    ]
                ),
            ]
            del self.form_data["date_modified"]
            del response.data[0]["date_modified"]

            del self.form_data["last_updated_at"]
            del response.data[0]["last_updated_at"]

            self.form_data.pop("has_id_string_changed")
            self.form_data["metadata"].sort(key=lambda x: x["id"])
            response.data[0]["metadata"].sort(key=lambda x: x["id"])
            self.assertEqual(response.data, [self.form_data])

            # public shared form data
            self.xform.shared_data = True
            self.xform.shared = False
            self.xform.save()
            response = self.view(request, pk="public")
            self.assertEqual(response.status_code, 200)
            self.assertNotEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.data, [])

    def test_form_list_other_user_access(self):
        with HTTMock(enketo_urls_mock):
            """Test that a different user has no access to bob's form"""
            self._publish_xls_form_to_project()
            request = self.factory.get("/", **self.extra)
            response = self.view(request)
            self.assertNotEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.status_code, 200)

            # pylint: disable=no-member
            resultset = MetaData.objects.filter(
                Q(object_id=self.xform.pk),
                Q(data_type="enketo_url") | Q(data_type="enketo_preview_url"),
            )
            url = resultset.get(data_type="enketo_url")
            preview_url = resultset.get(data_type="enketo_preview_url")
            self.form_data["metadata"] = [
                {
                    "id": preview_url.pk,
                    "xform": self.xform.pk,
                    "data_value": "https://enketo.ona.io/preview/::YY8M",
                    "data_type": "enketo_preview_url",
                    "data_file": None,
                    "data_file_type": None,
                    "url": "http://testserver/api/v1/metadata/%s" % preview_url.pk,
                    "file_hash": None,
                    "media_url": None,
                    "date_created": preview_url.date_created,
                },
                {
                    "id": url.pk,
                    "xform": self.xform.pk,
                    "data_value": "https://enketo.ona.io/::YY8M",
                    "data_type": "enketo_url",
                    "data_file": None,
                    "data_file_type": None,
                    "url": "http://testserver/api/v1/metadata/%s" % url.pk,
                    "file_hash": None,
                    "media_url": None,
                    "date_created": url.date_created,
                },
            ]

            self.assertEqual(response.data.sort(), [self.form_data].sort())

            # test with different user
            previous_user = self.user
            alice_data = {"username": "alice", "email": "alice@localhost.com"}
            self._login_user_and_profile(extra_post_data=alice_data)
            self.assertEqual(self.user.username, "alice")
            self.assertNotEqual(previous_user, self.user)
            request = self.factory.get("/", **self.extra)
            response = self.view(request)
            self.assertEqual(response.status_code, 200)
            self.assertNotEqual(response.get("Cache-Control"), None)
            # should be empty
            self.assertEqual(response.data, [])

    def test_form_list_filter_by_user(self):
        with HTTMock(enketo_urls_mock):
            # publish bob's form
            self._publish_xls_form_to_project()

            previous_user = self.user
            alice_data = {"username": "alice", "email": "alice@localhost.com"}
            self._login_user_and_profile(extra_post_data=alice_data)
            self.assertEqual(self.user.username, "alice")
            self.assertNotEqual(previous_user, self.user)

            ReadOnlyRole.add(self.user, self.xform)
            view = XFormViewSet.as_view({"get": "retrieve"})
            safe_cache_delete("{}{}".format(XFORM_PERMISSIONS_CACHE, self.xform.pk))
            request = self.factory.get("/", **self.extra)
            response = view(request, pk=self.xform.pk)
            bobs_form_data = response.data
            form_users = [(u["role"], u["user"]) for u in bobs_form_data["users"]]
            self.assertEqual(len(form_users), 2)
            self.assertIn(("owner", "bob"), form_users)
            self.assertIn(("readonly", "alice"), form_users)

            # publish alice's form
            self._publish_xls_form_to_project()

            request = self.factory.get("/", **self.extra)
            response = self.view(request)
            self.assertNotEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.status_code, 200)

            self.form_data.pop("has_id_string_changed")
            response_data = sorted(response.data, key=lambda x: x["formid"])
            for k in ["submission_count_for_today", "metadata", "form_versions"]:
                bobs_form_data.pop(k)
                self.form_data.pop(k)
            expected_data = [OrderedDict(bobs_form_data), OrderedDict(self.form_data)]

            self.assertTrue(len(response_data), 2)

            # remove date modified and last updated at
            for indx in [0, 1]:
                response_data[indx].pop("date_modified")
                expected_data[indx].pop("date_modified")
                response_data[indx].pop("last_updated_at")
                expected_data[indx].pop("last_updated_at")

            response_users = sorted(
                response_data[0].pop("users"), key=lambda x: x["user"]
            )
            expected_users = sorted(
                expected_data[0].pop("users"), key=lambda x: x["user"]
            )
            self.assertEqual(response_data[0], expected_data[0])
            self.assertEqual(response_users, expected_users)

            self.assertEqual(response_data[1], expected_data[1])
            self.assertEqual(response_users, expected_users)

            # apply filter, see only bob's forms
            request = self.factory.get("/", data={"owner": "bob"}, **self.extra)
            response = self.view(request)
            self.assertNotEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, [bobs_form_data])

            # apply filter, see only bob's forms, case insensitive
            request = self.factory.get("/", data={"owner": "BoB"}, **self.extra)
            response = self.view(request)
            self.assertNotEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, [bobs_form_data])

            # apply filter, see only alice's forms
            request = self.factory.get("/", data={"owner": "alice"}, **self.extra)
            response = self.view(request)
            self.assertNotEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.status_code, 200)

            # remove date-modified
            response.data[0].pop("date_modified")
            self.form_data.pop("date_modified")

            # remove last updated at
            response.data[0].pop("last_updated_at")
            self.form_data.pop("last_updated_at")

            self.assertEqual(response.data, [self.form_data])

            # apply filter, see a non existent user
            request = self.factory.get("/", data={"owner": "noone"}, **self.extra)
            response = self.view(request)
            self.assertEqual(response.status_code, 200)
            self.assertNotEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.data, [])

    def test_form_get(self):
        with HTTMock(enketo_urls_mock):
            view = XFormViewSet.as_view({"get": "retrieve"})
            self._publish_xls_form_to_project()
            formid = self.xform.pk
            request = self.factory.get("/", **self.extra)
            response = view(request, pk=formid)
            self.assertNotEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.status_code, 200)
            # pylint: disable=no-member
            resultset = MetaData.objects.filter(
                Q(object_id=self.xform.pk),
                Q(data_type="enketo_url")
                | Q(data_type="enketo_preview_url")
                | Q(data_type="enketo_single_submit_url")
                | Q(data_type="xform_meta_perms"),
            )
            url = resultset.get(data_type="enketo_url")
            preview_url = resultset.get(data_type="enketo_preview_url")
            single_submit_url = resultset.get(data_type="enketo_single_submit_url")
            meta_perms = resultset.get(data_type="xform_meta_perms")

            self.form_data["metadata"] = [
                OrderedDict(
                    [
                        ("id", meta_perms.pk),
                        ("xform", self.xform.pk),
                        (
                            "data_value",
                            "editor|dataentry|readonly",
                        ),
                        ("data_type", "xform_meta_perms"),
                        ("data_file", None),
                        ("extra_data", {}),
                        ("data_file_type", None),
                        ("media_url", None),
                        ("file_hash", None),
                        ("url", f"http://testserver/api/v1/metadata/{meta_perms.pk}"),
                        ("date_created", meta_perms.date_created),
                    ]
                ),
                OrderedDict(
                    [
                        ("id", url.pk),
                        ("xform", self.xform.pk),
                        ("data_value", "https://enketo.ona.io/::YY8M"),
                        ("data_type", "enketo_url"),
                        ("data_file", None),
                        ("extra_data", {}),
                        ("data_file_type", None),
                        ("media_url", None),
                        ("file_hash", None),
                        ("url", "http://testserver/api/v1/metadata/%s" % url.pk),
                        ("date_created", url.date_created),
                    ]
                ),
                OrderedDict(
                    [
                        ("id", preview_url.pk),
                        ("xform", self.xform.pk),
                        ("data_value", "https://enketo.ona.io/preview/::YY8M"),
                        ("data_type", "enketo_preview_url"),
                        ("data_file", None),
                        ("extra_data", {}),
                        ("data_file_type", None),
                        ("media_url", None),
                        ("file_hash", None),
                        (
                            "url",
                            "http://testserver/api/v1/metadata/%s" % preview_url.pk,
                        ),
                        ("date_created", preview_url.date_created),
                    ]
                ),
                OrderedDict(
                    [
                        ("id", single_submit_url.pk),
                        ("xform", self.xform.pk),
                        ("data_value", "http://enketo.ona.io/single/::XZqoZ94y"),
                        ("data_type", "enketo_single_submit_url"),
                        ("data_file", None),
                        ("extra_data", {}),
                        ("data_file_type", None),
                        ("media_url", None),
                        ("file_hash", None),
                        (
                            "url",
                            "http://testserver/api/v1/metadata/%s"
                            % single_submit_url.pk,
                        ),
                        ("date_created", single_submit_url.date_created),
                    ]
                ),
            ]

            self.form_data["metadata"] = sorted(
                self.form_data["metadata"], key=lambda x: x["id"]
            )
            response.data["metadata"] = sorted(
                response.data["metadata"], key=lambda x: x["id"]
            )

            # remove date modified
            self.form_data.pop("date_modified")
            response.data.pop("date_modified")
            # remove last updated at
            self.form_data.pop("last_updated_at")
            response.data.pop("last_updated_at")

            self.form_data.pop("has_id_string_changed")

            self.assertEqual(response.data, self.form_data)

    def test_form_format(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view({"get": "form"})
            formid = self.xform.pk
            data = {
                "name": "data",
                "title": "transportation_2011_07_25",
                "default_language": "default",
                "id_string": "transportation_2011_07_25",
                "type": "survey",
            }
            request = self.factory.get("/", **self.extra)

            # test for unsupported format
            response = view(request, pk=formid, format="csvzip")
            self.assertEqual(response.status_code, 400)

            # test for supported formats

            # JSON format
            response = view(request, pk=formid, format="json")
            self.assertEqual(response.status_code, 200)
            self.assertNotEqual(response.get("Cache-Control"), None)
            self.assertDictContainsSubset(data, response.data)

            # test correct file name
            self.assertEqual(
                response.get("Content-Disposition"),
                "attachment; filename=" + self.xform.id_string + "." + "json",
            )

            # XML format
            response = view(request, pk=formid, format="xml")
            self.assertEqual(response.status_code, 200)
            self.assertNotEqual(response.get("Cache-Control"), None)
            response_doc = minidom.parseString(response.data)

            # test correct file name
            self.assertEqual(
                response.get("Content-Disposition"),
                "attachment; filename=" + self.xform.id_string + "." + "xml",
            )

            # XLS format
            response = view(request, pk=formid, format="xlsx")
            self.assertEqual(response.status_code, 200)
            self.assertNotEqual(response.get("Cache-Control"), None)

            # test correct file name
            self.assertEqual(
                response.get("Content-Disposition"),
                "attachment; filename=" + self.xform.id_string + "." + "xlsx",
            )

            xml_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation.xml",
            )
            with open(xml_path, "rb") as xml_file:
                expected_doc = minidom.parse(xml_file)

            model_node = [
                n
                for n in response_doc.getElementsByTagName("h:head")[0].childNodes
                if n.nodeType == Node.ELEMENT_NODE and n.tagName == "model"
            ][0]

            # check for UUID and remove
            uuid_nodes = [
                node
                for node in model_node.childNodes
                if node.nodeType == Node.ELEMENT_NODE
                and node.getAttribute("nodeset") == "/data/formhub/uuid"
            ]
            self.assertEqual(len(uuid_nodes), 1)
            uuid_node = uuid_nodes[0]
            uuid_node.setAttribute("calculate", "''")

            # check content without UUID
            response_xml = response_doc.toxml().replace(
                self.xform.version, "201411120717"
            )
            self.assertEqual(response_xml, expected_doc.toxml())

    def test_existing_form_format(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view({"get": "form"})
            formid = self.xform.pk
            request = self.factory.get("/", **self.extra)
            # get existing form format
            exsting_format = get_existing_file_format(self.xform.xls, "xls")

            # XLSX format
            response = view(request, pk=formid, format="xlsx")
            self.assertEqual(response.status_code, 200)
            self.assertNotEqual(response.get("Cache-Control"), None)

            # test correct content disposition
            # ensure it still maintains the existing form extension
            self.assertEqual(
                response.get("Content-Disposition"),
                "attachment; filename=" + self.xform.id_string + "." + exsting_format,
            )

            # XLS format
            response = view(request, pk=formid, format="xls")
            self.assertEqual(response.status_code, 200)
            self.assertNotEqual(response.get("Cache-Control"), None)

            # test correct content disposition
            # ensure it still maintains the existing form extension
            self.assertEqual(
                response.get("Content-Disposition"),
                "attachment; filename=" + self.xform.id_string + "." + exsting_format,
            )

    def test_form_tags(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view(
                {"get": "labels", "post": "labels", "delete": "labels"}
            )
            list_view = XFormViewSet.as_view(
                {
                    "get": "list",
                }
            )
            formid = self.xform.pk

            # no tags
            request = self.factory.get("/", **self.extra)
            response = view(request, pk=formid)
            self.assertEqual(response.data, [])

            # add tag "hello"
            request = self.factory.post("/", data={"tags": "hello"}, **self.extra)
            response = view(request, pk=formid)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.data, ["hello"])

            # check filter by tag
            request = self.factory.get("/", data={"tags": "hello"}, **self.extra)
            self.form_data = XFormBaseSerializer(
                self.xform, context={"request": request}
            ).data
            response = list_view(request)
            self.assertNotEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.status_code, 200)
            response_data = dict(response.data[0])
            response_data.pop("date_modified")
            response_data.pop("last_updated_at")
            self.form_data.pop("date_modified")
            self.form_data.pop("last_updated_at")
            self.assertEqual(response_data, self.form_data)

            request = self.factory.get("/", data={"tags": "goodbye"}, **self.extra)
            response = list_view(request, pk=formid)
            self.assertEqual(response.status_code, 200)
            self.assertNotEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.data, [])

            # remove tag "hello"
            request = self.factory.delete("/", data={"tags": "hello"}, **self.extra)
            response = view(request, pk=formid, label="hello")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.data, [])

    def test_enketo_url_no_account(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view({"get": "enketo"})
            formid = self.xform.pk
            # no tags
            request = self.factory.get("/", **self.extra)
            with HTTMock(enketo_error_mock):
                response = view(request, pk=formid)
                data = {
                    "message": "Enketo error: no account exists for this OpenRosa server"
                }

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(response.data, data)

    def test_enketo_url_error500(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view({"get": "enketo"})
            formid = self.xform.pk
            # no tags
            request = self.factory.get("/", **self.extra)
            with HTTMock(enketo_error500_mock):
                response = view(request, pk=formid)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_enketo_url_error502(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view({"get": "enketo"})
            formid = self.xform.pk
            # no tags
            request = self.factory.get("/", **self.extra)
            with HTTMock(enketo_error502_mock):
                response = view(request, pk=formid)
                data = {
                    "message": "Enketo error: Sorry, we cannot load your form right "
                    "now.  Please try again later."
                }
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(response.data, data)

    @override_settings(TESTING_MODE=False)
    def test_enketo_url(self):
        """Test functionality to expose enketo urls."""
        with HTTMock(enketo_urls_mock):
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view({"get": "enketo"})
            formid = self.xform.pk
            # no tags
            request = self.factory.get("/", **self.extra)
            response = view(request, pk=formid)
            url = "https://enketo.ona.io/::YY8M"
            preview_url = "https://enketo.ona.io/preview/::YY8M"
            single_url = "http://enketo.ona.io/single/::XZqoZ94y"
            data = {
                "enketo_url": url,
                "enketo_preview_url": preview_url,
                "single_submit_url": single_url,
            }
            self.assertEqual(response.data, data)

            alice_data = {"username": "alice", "email": "alice@localhost.com"}
            alice_profile = self._create_user_profile(alice_data)
            credentials = {
                "HTTP_AUTHORIZATION": ("Token %s" % alice_profile.user.auth_token)
            }
            request = self.factory.get("/", **credentials)
            response = view(request, pk=formid)
            # Alice has no permissions to the form hence no access to web form
            self.assertEqual(response.status_code, 404)

            # Give Alice read-only permissions to the form
            ReadOnlyRole.add(alice_profile.user, self.xform)
            response = view(request, pk=formid)
            # Alice with read-only access should not have access to web form
            self.assertEqual(response.status_code, 404)

            # Give Alice data-entry permissions
            DataEntryRole.add(alice_profile.user, self.xform)
            response = view(request, pk=formid)
            # Alice with data-entry access should have access to web form
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, data)

    def test_get_single_submit_url(self):
        with HTTMock(enketo_urls_mock):
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view({"get": "enketo"})
            formid = self.xform.pk
            get_data = {"survey_type": "single"}
            request = self.factory.get("/", data=get_data, **self.extra)
            response = view(request, pk=formid)
            submit_url = "http://enketo.ona.io/single/::XZqoZ94y"
            self.assertEqual(response.data["single_submit_url"], submit_url)

    def test_enketo_url_with_default_form_params(self):
        with HTTMock(enketo_mock_with_form_defaults):
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view({"get": "enketo"})
            formid = self.xform.pk

            get_data = {"num": "1"}
            request = self.factory.get("/", data=get_data, **self.extra)
            response = view(request, pk=formid)
            url = "https://dmfrm.enketo.org/webform?d[%2Fnum]=1"
            self.assertEqual(response.data["enketo_url"], url)

    def test_handle_memory_error_on_form_replacement(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            form_id = self.xform.pk

            with patch("onadata.apps.api.tools.QuickConverter.publish") as mock_func:
                mock_func.side_effect = MemoryError()
                view = XFormViewSet.as_view(
                    {
                        "patch": "partial_update",
                    }
                )

                path = os.path.join(
                    settings.PROJECT_ROOT,
                    "apps",
                    "main",
                    "tests",
                    "fixtures",
                    "transportation",
                    "transportation_version.xlsx",
                )
                with open(path, "rb") as xls_file:
                    post_data = {"xls_file": xls_file}
                    request = self.factory.patch("/", data=post_data, **self.extra)
                    response = view(request, pk=form_id)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(
                        response.data,
                        {
                            "text": (
                                "An error occurred while publishing the "
                                "form. Please try again."
                            ),
                            "type": "alert-error",
                        },
                    )

    def test_enketo_urls_remain_the_same_after_form_replacement(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()

            self.assertIsNotNone(self.xform.version)
            version = self.xform.version
            form_id = self.xform.pk
            id_string = self.xform.id_string

            self.view = XFormViewSet.as_view(
                {
                    "get": "retrieve",
                }
            )

            request = self.factory.get("/", **self.extra)
            response = self.view(request, pk=self.xform.id)
            self.assertEqual(response.status_code, 200)
            self.assertNotEqual(response.get("Cache-Control"), None)

            enketo_url = response.data.get("enketo_url")
            enketo_preview_url = response.data.get("enketo_preview_url")

            view = XFormViewSet.as_view(
                {
                    "patch": "partial_update",
                }
            )

            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation_version.xlsx",
            )
            with open(path, "rb") as xls_file:
                post_data = {"xls_file": xls_file}
                request = self.factory.patch("/", data=post_data, **self.extra)
                response = view(request, pk=form_id)
                self.assertEqual(
                    response.data.get("enketo_preview_url"), enketo_preview_url
                )
                self.assertEqual(response.data.get("enketo_url"), enketo_url)
                self.assertEqual(response.status_code, 200)

            self.xform.refresh_from_db()

            # diff versions
            self.assertNotEqual(version, self.xform.version)
            self.assertEqual(form_id, self.xform.pk)
            self.assertEqual(id_string, self.xform.id_string)

    def test_xform_hash_changes_after_form_replacement(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()

            self.assertIsNotNone(self.xform.version)
            form_id = self.xform.pk
            xform_old_hash = self.xform.hash

            view = XFormViewSet.as_view(
                {
                    "patch": "partial_update",
                }
            )

            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation_version.xlsx",
            )
            with open(path, "rb") as xls_file:
                post_data = {"xls_file": xls_file}
                request = self.factory.patch("/", data=post_data, **self.extra)
                response = view(request, pk=form_id)
                self.assertEqual(response.status_code, 200)

            self.xform.refresh_from_db()
            self.assertNotEqual(xform_old_hash, self.xform.hash)

    def test_hash_changes_after_update_xform_xls_file(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()

            xform_old_hash = self.xform.hash
            form_id = self.xform.pk

            view = XFormViewSet.as_view(
                {
                    "patch": "partial_update",
                }
            )

            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation_version.xlsx",
            )
            with open(path, "rb") as xls_file:
                post_data = {"xls_file": xls_file}
                request = self.factory.patch("/", data=post_data, **self.extra)
                response = view(request, pk=form_id)
                self.assertEqual(response.status_code, 200)

            self.xform.refresh_from_db()
            self.assertNotEqual(xform_old_hash, self.xform.hash)

    def test_login_enketo_no_redirect(self):
        with HTTMock(enketo_urls_mock):
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view({"get": "login"})
            formid = self.xform.pk
            request = self.factory.get("/")
            response = view(request, pk=formid)
            self.assertEqual(
                response.content.decode("utf-8"),
                "Authentication failure, cannot redirect",
            )

    @override_settings(
        ENKETO_CLIENT_LOGIN_URL={
            "*": "http://test.ona.io/login",
            "stage-testserver": "http://gh.ij.kl/login",
        }
    )
    @override_settings(ALLOWED_HOSTS=["*"])
    def test_login_enketo_no_jwt_but_with_return_url(self):
        with HTTMock(enketo_urls_mock):
            self._publish_xls_form_to_project()

            view = XFormViewSet.as_view({"get": "login"})

            formid = self.xform.pk
            url = "https://enketo.ona.io/::YY8M"
            query_data = {"return": url}
            request = self.factory.get("/", data=query_data)

            # user is redirected to default login page "*"
            response = view(request, pk=formid)
            self.assertTrue(response.url.startswith("http://test.ona.io/login"))
            self.assertEqual(response.status_code, 302)

            # user is redirected to login page for "stage-testserver"
            request.META["HTTP_HOST"] = "stage-testserver"
            response = view(request, pk=formid)
            self.assertTrue(response.url.startswith("http://gh.ij.kl/login"))
            self.assertEqual(response.status_code, 302)

    @override_settings(JWT_SECRET_KEY=JWT_SECRET_KEY, JWT_ALGORITHM=JWT_ALGORITHM)
    def test_login_enketo_online_url_bad_token(self):
        with HTTMock(enketo_urls_mock):
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view({"get": "login"})
            formid = self.xform.pk
            temp_token = "abc"

            # do not store temp token

            url = "https://enketo.ona.io/::YY8M?jwt=%s" % temp_token
            query_data = {"return": url}
            request = self.factory.get("/", data=query_data)
            response = view(request, pk=formid)

            self.assertEqual(response.status_code, 401)
            self.assertEqual(
                response.data.get("detail"), "JWT DecodeError: Not enough segments"
            )

    @override_settings(JWT_SECRET_KEY=JWT_SECRET_KEY, JWT_ALGORITHM=JWT_ALGORITHM)
    def test_login_enketo_offline_url_using_jwt(self):
        with HTTMock(enketo_urls_mock):
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view({"get": "login"})
            formid = self.xform.pk

            payload = {
                "api-token": self.user.auth_token.key,
            }

            encoded_payload = jwt.encode(
                payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM
            )

            return_url = "https://enketo.ona.io/_/#YY8M"
            url = "https://enketo.ona.io/_/?jwt=%s#YY8M" % encoded_payload

            query_data = {"return": url}
            request = self.factory.get("/", data=query_data)
            response = view(request, pk=formid)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.get("Location"), return_url)

    @patch("onadata.libs.authentication.EnketoTokenAuthentication.authenticate")
    def test_enketo_cookie_authentication_with_invalid_jwt(self, mock_jwt_decode):
        mock_jwt_decode.side_effect = jwt.DecodeError(
            "JWT DecodeError: Not enough segments"
        )

        with HTTMock(enketo_urls_mock):
            with self.assertRaises(jwt.DecodeError):
                self._publish_xls_form_to_project()
                self.assertTrue(mock_jwt_decode.called)

    @override_settings(JWT_SECRET_KEY=JWT_SECRET_KEY, JWT_ALGORITHM=JWT_ALGORITHM)
    def test_login_enketo_online_url_using_jwt(self):
        with HTTMock(enketo_urls_mock):
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view({"get": "login"})
            formid = self.xform.pk

            payload = {
                "api-token": self.user.auth_token.key,
            }

            encoded_payload = jwt.encode(
                payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM
            )

            return_url = "https://enketo.ona.io/::YY8M"
            url = "%s?jwt=%s" % (return_url, encoded_payload)
            query_data = {"return": url}
            request = self.factory.get("/", data=query_data)
            response = view(request, pk=formid)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.get("Location"), return_url)
            cookies = response.cookies
            uid_cookie = cookies.get(settings.ENKETO_META_UID_COOKIE)._value
            username_cookie = cookies.get(settings.ENKETO_META_USERNAME_COOKIE)._value
            # example cookie: bob:1jlVih:i2KvHoAtsQOlYB71CJeNuVUlEY0
            self.assertEqual(username_cookie.split(":")[0], "bob")
            self.assertEqual(uid_cookie.split(":")[0], "bob")

    @patch("onadata.apps.api.viewsets.xform_viewset.XFormViewSet.list")
    def test_return_400_on_xlsform_error_on_list_action(self, mock_set_title):
        with HTTMock(enketo_mock):
            with self.assertRaises(XLSFormError):
                error_msg = "Title shouldn't have an ampersand"
                mock_set_title.side_effect = XLSFormError(error_msg)
                request = self.factory.get("/", **self.extra)
                response = self.view(request)
                self.assertTrue(mock_set_title.called)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.content.decode("utf-8"), error_msg)

    def test_partial_update(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view({"patch": "partial_update"})
            title = "Hello & World!"
            description = "DESCRIPTION"
            data = {
                "public": True,
                "description": description,
                "title": title,
                "downloadable": True,
            }

            self.assertFalse(self.xform.shared)

            request = self.factory.patch("/", data=data, **self.extra)
            response = view(request, pk=self.xform.id)
            self.assertEqual(response.status_code, 400)

            title = "Hello and World!"
            data["title"] = title
            request = self.factory.patch("/", data=data, **self.extra)
            response = view(request, pk=self.xform.id)
            self.assertEqual(response.status_code, 200)
            xform_old_hash = self.xform.hash
            self.xform.refresh_from_db()
            self.assertTrue(self.xform.downloadable)
            self.assertTrue(self.xform.shared)
            self.assertEqual(self.xform.description, description)
            self.assertEqual(response.data["public"], True)
            self.assertEqual(response.data["description"], description)
            self.assertEqual(response.data["title"], title)
            self.assertEqual(response.data["public_key"], "")
            matches = re.findall(r"<h:title>([^<]+)</h:title>", self.xform.xml)
            self.assertTrue(len(matches) > 0)
            self.assertEqual(matches[0], title)
            self.assertFalse(self.xform.hash == "" or self.xform.hash is None)
            self.assertFalse(self.xform.hash == xform_old_hash)

            # Test can update public_key
            public_key = """
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxNlbF920Dj7CYsKYrxcK
PL0PatubLO2OhcMCpHgdbpGZscbWVAcXNkdjhmPhTuVPXmOa2Wjwe4ZkRfXJW2Iv
lvPm//UIWXhXUsNQaB9P
X4yxLWC0fZQ9T3ito8PcZ1nS+B39HYMkRSn9K5r65zRi
SZhwvTkhcwq7Cea+wX3UT/pfEx62Z8GZ3E8iiYrIcNv2DM+x+0yYmQEboXq1tlKE
twkF965z9mUTyXYfinrrHVx7xXhz1jbiWyOvTpiY8aAC35EaV3h/MdNXKk7WznJi
xdM
nhMo+jI88L3qfm4/rtWKuQ9/a268phlNj34uQeoDDHuRViQo00L5meE/pFptm
7QIDAQAB
-----END PUBLIC KEY-----"""

            clean_public_key = """
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxNlbF920Dj7CYsKYrxcK
PL0PatubLO2OhcMCpHgdbpGZscbWVAcXNkdjhmPhTuVPXmOa2Wjwe4ZkRfXJW2Iv
lvPm//UIWXhXUsNQaB9P
X4yxLWC0fZQ9T3ito8PcZ1nS+B39HYMkRSn9K5r65zRi
SZhwvTkhcwq7Cea+wX3UT/pfEx62Z8GZ3E8iiYrIcNv2DM+x+0yYmQEboXq1tlKE
twkF965z9mUTyXYfinrrHVx7xXhz1jbiWyOvTpiY8aAC35EaV3h/MdNXKk7WznJi
xdM
nhMo+jI88L3qfm4/rtWKuQ9/a268phlNj34uQeoDDHuRViQo00L5meE/pFptm
7QIDAQAB"""

            data = {"public_key": public_key}
            request = self.factory.patch("/", data=data, **self.extra)
            response = view(request, pk=self.xform.id)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["public_key"], clean_public_key.strip())
            self.assertTrue(response.data["encrypted"])

    def test_partial_update_anon(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view({"patch": "partial_update"})
            title = "مرحب"
            description = "DESCRIPTION"
            username = "Anon"
            error_msg = "Invalid hyperlink - Object does not exist."
            data = {
                "public": True,
                "description": description,
                "title": title,
                "downloadable": True,
                "owner": "http://testserver/api/v1/users/%s" % username,
            }

            self.assertFalse(self.xform.shared)

            request = self.factory.patch("/", data=data, **self.extra)
            response = view(request, pk=self.xform.id)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.data.get("owner")[0], error_msg)

    def test_set_form_private(self):
        with HTTMock(enketo_mock):
            key = "shared"
            self._publish_xls_form_to_project()
            self.xform.__setattr__(key, True)
            self.xform.save()
            view = XFormViewSet.as_view({"patch": "partial_update"})
            data = {"public": False}

            self.assertTrue(self.xform.__getattribute__(key))

            request = self.factory.patch("/", data=data, **self.extra)
            response = view(request, pk=self.xform.id)

            self.xform.refresh_from_db()
            self.assertFalse(self.xform.__getattribute__(key))
            self.assertFalse(response.data["public"])

    def test_set_form_bad_value(self):
        with HTTMock(enketo_mock):
            key = "shared"
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view({"patch": "partial_update"})
            data = {"public": "String"}

            request = self.factory.patch("/", data=data, **self.extra)
            response = view(request, pk=self.xform.id)

            self.xform.refresh_from_db()
            self.assertFalse(self.xform.__getattribute__(key))
            shared = ["Must be a valid boolean."]
            self.assertEqual(response.data, {"public": shared})

    def test_set_form_bad_key(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            self.xform.save()
            view = XFormViewSet.as_view({"patch": "partial_update"})
            data = {"nonExistentField": False}

            request = self.factory.patch("/", data=data, **self.extra)
            response = view(request, pk=self.xform.id)

            self.xform.refresh_from_db()
            self.assertFalse(self.xform.shared)
            self.assertFalse(response.data["public"])

    def test_form_add_project_cache(self):
        with HTTMock(enketo_mock):
            self._project_create()

            cleared_cache_content = ["forms"]
            # set project XForm cache
            cache.set(f"{PROJ_FORMS_CACHE}{self.project.pk}", cleared_cache_content)

            self.assertNotEqual(cache.get(f"{PROJ_FORMS_CACHE}{self.project.pk}"), None)

            self._publish_xls_form_to_project()

            # test project XForm cache has new content
            self.assertNotEqual(
                cache.get(f"{PROJ_FORMS_CACHE}{self.project.pk}"), cleared_cache_content
            )

    def test_form_delete(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()

            self.xform.save()
            request = self.factory.get("/", **self.extra)
            response = self.view(request)
            self.assertEqual(response.status_code, 200)
            etag_value = response.get("Etag")
            self.assertNotEqual(etag_value, None)

            # set project XForm cache
            cache.set(f"{PROJ_FORMS_CACHE}{self.project.pk}", ["forms"])

            self.assertNotEqual(cache.get(f"{PROJ_FORMS_CACHE}{self.project.pk}"), None)

            view = XFormViewSet.as_view({"delete": "destroy", "get": "retrieve"})
            formid = self.xform.pk
            request = self.factory.delete("/", **self.extra)
            response = view(request, pk=formid)
            self.assertEqual(response.data, None)
            self.assertEqual(response.status_code, 204)

            # test project XForm cache is emptied
            self.assertEqual(cache.get(f"{PROJ_FORMS_CACHE}{self.project.pk}"), None)

            self.xform.refresh_from_db()

            self.assertIsNotNone(self.xform.deleted_at)
            self.assertTrue("deleted-at" in self.xform.id_string)

            request = self.factory.get("/", **self.extra)
            response = view(request, pk=formid)

            self.assertEqual(response.status_code, 404)

            request = self.factory.get("/", **self.extra)
            response = self.view(request)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data), 0)

    def test_form_share_endpoint_handles_no_username(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            alice_data = {"username": "alice", "email": "alice@localhost.com"}
            alice_profile = self._create_user_profile(alice_data)

            view = XFormViewSet.as_view({"post": "share"})
            formid = self.xform.pk

            for role_class in ROLES:
                self.assertFalse(
                    role_class.user_has_role(alice_profile.user, self.xform)
                )

                data = {"role": role_class.name}
                request = self.factory.post("/", data=data, **self.extra)
                response = view(request, pk=formid)

                self.assertEqual(response.status_code, 400)
                self.assertFalse(
                    role_class.user_has_role(alice_profile.user, self.xform)
                )

    def test_form_share_endpoint_takes_username(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            alice_data = {"username": "alice", "email": "alice@localhost.com"}
            alice_profile = self._create_user_profile(alice_data)

            view = XFormViewSet.as_view({"post": "share"})
            formid = self.xform.pk

            for role_class in ROLES:
                self.assertFalse(
                    role_class.user_has_role(alice_profile.user, self.xform)
                )

                data = {"username": "alice", "role": role_class.name}
                request = self.factory.post("/", data=data, **self.extra)
                response = view(request, pk=formid)

                self.assertEqual(response.status_code, 204)
                self.assertTrue(
                    role_class.user_has_role(alice_profile.user, self.xform)
                )

    def test_form_share_endpoint_takes_usernames(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            alice_data = {"username": "alice", "email": "alice@localhost.com"}
            job_data = {"username": "job", "email": "job@localhost.com"}
            alice_profile = self._create_user_profile(alice_data)
            job_profile = self._create_user_profile(job_data)

            view = XFormViewSet.as_view({"post": "share"})
            formid = self.xform.pk

            for role_class in ROLES:
                self.assertFalse(
                    role_class.user_has_role(alice_profile.user, self.xform)
                )
                self.assertFalse(role_class.user_has_role(job_profile.user, self.xform))

                data = {"usernames": "alice,job", "role": role_class.name}
                request = self.factory.post("/", data=data, **self.extra)
                response = view(request, pk=formid)

                self.assertEqual(response.status_code, 204)
                self.assertTrue(
                    role_class.user_has_role(alice_profile.user, self.xform)
                )

    def test_form_clone_endpoint(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            alice_data = {"username": "alice", "email": "alice@localhost.com"}
            alice_profile = self._create_user_profile(alice_data)
            view = XFormViewSet.as_view({"post": "clone"})
            formid = self.xform.pk
            count = XForm.objects.count()

            data = {}
            request = self.factory.post("/", data=data, **self.extra)
            response = view(request, pk=formid)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get("Cache-Control"), None)

            data = {"username": "mjomba"}
            request = self.factory.post("/", data=data, **self.extra)
            response = view(request, pk=formid)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get("Cache-Control"), None)

            data = {"username": "alice"}
            request = self.factory.post("/", data=data, **self.extra)
            response = view(request, pk=formid)
            self.assertFalse(self.user.has_perm("can_add_xform", alice_profile))
            self.assertEqual(response.status_code, 403)

            ManagerRole.add(self.user, alice_profile)
            request = self.factory.post("/", data=data, **self.extra)
            response = view(request, pk=formid)
            self.assertTrue(self.user.has_perm("can_add_xform", alice_profile))
            self.assertEqual(response.status_code, 201)
            self.assertEqual(count + 1, XForm.objects.count())

            data["project_id"] = 5000
            request = self.factory.post("/", data=data, **self.extra)
            response = view(request, pk=formid)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                response.data["project"][0], "Project with id '5000' does not exist."
            )

            data["project_id"] = "abc123"
            request = self.factory.post("/", data=data, **self.extra)
            response = view(request, pk=formid)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                str(response.data["project"]),
                "[ErrorDetail(string=\"Field 'id' expected a number but got 'abc123'.\", code='invalid')]",
            )

            # pylint: disable=no-member
            project = Project.objects.create(
                name="alice's other project",
                organization=alice_profile.user,
                created_by=alice_profile.user,
                metadata="{}",
            )

            data["project_id"] = project.id
            request = self.factory.post("/", data=data, **self.extra)
            response = view(request, pk=formid)
            self.assertTrue(self.user.has_perm("can_add_xform", alice_profile))
            self.assertEqual(response.status_code, 201)
            self.assertEqual(count + 2, XForm.objects.count())
            form_id = response.data["formid"]
            form = XForm.objects.get(pk=form_id)
            self.assertEqual(form.project_id, project.id)

    def test_form_clone_shared_forms(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            alice_data = {"username": "alice", "email": "alice@localhost.com"}
            alice_profile = self._create_user_profile(alice_data)
            view = XFormViewSet.as_view({"post": "clone"})
            self.xform.shared = True
            self.xform.save()
            formid = self.xform.pk
            count = XForm.objects.count()
            data = {"username": "alice"}

            # can clone shared forms
            self.user = alice_profile.user
            self.extra = {"HTTP_AUTHORIZATION": "Token %s" % self.user.auth_token}
            request = self.factory.post("/", data=data, **self.extra)
            response = view(request, pk=formid)
            self.assertTrue(self.xform.shared)
            self.assertTrue(self.user.has_perm("can_add_xform", alice_profile))
            self.assertEqual(response.status_code, 201)
            self.assertEqual(count + 1, XForm.objects.count())

    @flaky(max_runs=8)
    def test_return_error_on_clone_duplicate(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view({"post": "clone"})
            alice_data = {"username": "alice", "email": "alice@localhost.com"}
            alice_profile = self._create_user_profile(alice_data)
            count = XForm.objects.count()

            data = {"username": "alice"}
            formid = self.xform.pk
            ManagerRole.add(self.user, alice_profile)
            request = self.factory.post("/", data=data, **self.extra)
            response = view(request, pk=formid)
            self.assertTrue(self.user.has_perm("can_add_xform", alice_profile))
            self.assertEqual(response.status_code, 201)
            self.assertEqual(count + 1, XForm.objects.count())

            request = self.factory.post("/", data=data, **self.extra)
            response = view(request, pk=formid)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                response.data["detail"],
                "A clone with the same id_string has already been created",
            )

    def test_xform_serializer_none(self):
        data = {
            "title": "",
            "owner": None,
            "public": False,
            "public_data": False,
            "public_key": "",
            "enable_kms_encryption": False,
            "require_auth": False,
            "description": "",
            "downloadable": False,
            "allows_sms": False,
            "uuid": "",
            "version": "",
            "project": None,
            "created_by": None,
            "instances_with_osm": False,
            "instances_with_geopoints": False,
            "has_hxl_support": False,
            "hash": "",
            "is_instance_json_regenerated": False,
            "num_of_decrypted_submissions": None,
        }

        self.assertEqual(data, XFormSerializer(None).data)

    def test_external_export(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            self._make_submissions()

            data_value = "template 1|http://xls_server"
            self._add_form_metadata(self.xform, "external_export", data_value)
            # pylint: disable=no-member
            metadata = MetaData.objects.get(
                object_id=self.xform.id, data_type="external_export"
            )
            paths = [
                os.path.join(
                    self.main_directory,
                    "fixtures",
                    "transportation",
                    "instances_w_uuid",
                    s,
                    s + ".xml",
                )
                for s in ["transport_2011-07-25_19-05-36"]
            ]

            self._make_submission(paths[0])
            self.assertEqual(self.response.status_code, 201)

            view = XFormViewSet.as_view(
                {
                    "get": "retrieve",
                }
            )
            data = {"meta": metadata.pk}
            formid = self.xform.pk
            request = self.factory.get("/", data=data, **self.extra)
            with HTTMock(external_mock):
                # External export
                response = view(request, pk=formid, format="xlsx")
                self.assertEqual(response.status_code, 302)
                expected_url = "http://xls_server/xls/ee3ff9d8f5184fc4a8fdebc2547cc059"
                self.assertEqual(response.url, expected_url)

    def test_external_export_with_data_id(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            self._make_submissions()

            data_value = "template 1|http://xls_server"
            self._add_form_metadata(self.xform, "external_export", data_value)
            # pylint: disable=no-member
            metadata = MetaData.objects.get(
                object_id=self.xform.id, data_type="external_export"
            )
            paths = [
                os.path.join(
                    self.main_directory,
                    "fixtures",
                    "transportation",
                    "instances_w_uuid",
                    s,
                    s + ".xml",
                )
                for s in ["transport_2011-07-25_19-05-36"]
            ]

            self._make_submission(paths[0])
            self.assertEqual(self.response.status_code, 201)

            view = XFormViewSet.as_view(
                {
                    "get": "retrieve",
                }
            )
            data_id = self.xform.instances.all().order_by("-pk")[0].pk
            data = {"meta": metadata.pk, "data_id": data_id}
            formid = self.xform.pk
            request = self.factory.get("/", data=data, **self.extra)
            with HTTMock(external_mock_single_instance):
                # External export
                response = view(request, pk=formid, format="xlsx")
                self.assertEqual(response.status_code, 302)
                expected_url = "http://xls_server/xls/ee3ff9d8f5184fc4a8fdebc2547cc059"
                self.assertEqual(response.url, expected_url)

    def test_external_export_error(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()

            data_value = "template 1|http://xls_server"
            self._add_form_metadata(self.xform, "external_export", data_value)

            paths = [
                os.path.join(
                    self.main_directory,
                    "fixtures",
                    "transportation",
                    "instances_w_uuid",
                    s,
                    s + ".xml",
                )
                for s in ["transport_2011-07-25_19-05-36"]
            ]

            self._make_submission(paths[0])
            self.assertEqual(self.response.status_code, 201)

            view = XFormViewSet.as_view(
                {
                    "get": "retrieve",
                }
            )
            formid = self.xform.pk
            token = "http://xls_server/xls/" + "8e86d4bdfa7f435ab89485aeae4ea6f5"
            data = {"token": token}
            request = self.factory.get("/", data=data, **self.extra)

            # External export
            response = view(request, pk=formid, format="xlsx")

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get("Cache-Control"), None)
            data = json.loads(response.data)
            self.assertTrue(
                data.get("error").startswith("J2X client could not generate report.")
            )

    def test_csv_import(self):
        with HTTMock(enketo_mock):
            xls_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "tutorial.xlsx",
            )
            self._publish_xls_form_to_project(xlsform_path=xls_path)
            view = XFormViewSet.as_view({"post": "csv_import"})
            csv_import = fixtures_path("good.csv")
            post_data = {"csv_file": csv_import}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = view(request, pk=self.xform.id)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.data.get("additions"), 9)
            self.assertEqual(response.data.get("updates"), 0)

    def test_extra_data_passed_in_select_multiple(self):
        """
        Test that extra details present in CSV Import are
        safely removed
        """
        form_md = """  # noqa
        | survey |
        |        | type                  | name         | label                       |
        |        | select_multiple moods | mood         | How are you feeling today ? |
        |        | dateTime              | now          | Current time                |
        |        | begin group           | demographics | Demographics                |
        |        | integer               | age          | Enter age                   |
        |        | select_multiple moods | mood_2       | How are you feeling today ? |
        |        | end group             |              |                             |
        | choices |
        |         | list_name | name  | label |
        |         | moods     | happy | Happy |
        |         | moods     | sad   | Sad   |
        |         | moods     | meh   | Meh   |
        """

        xform = self._publish_markdown(form_md, self.user)
        view = XFormViewSet.as_view({"post": "csv_import"})
        csv_import = fixtures_path("extra_details.csv")
        post_data = {"csv_file": csv_import}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = view(request, pk=xform.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get("additions"), 3)
        # Delete instances
        xform.instances.all().delete()

        # Ensure data is correctly imported
        csv_import = fixtures_path("single_submission_extra_details.csv")
        post_data = {"csv_file": csv_import}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = view(request, pk=xform.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get("additions"), 1)
        instance_data = xform.instances.first().json

        self.assertEqual(instance_data.get("mood"), "happy")
        self.assertEqual(instance_data.get("demographics/mood_2"), "happy")
        self.assertEqual(instance_data.get("demographics/age"), 20)

    @override_settings(CSV_FILESIZE_IMPORT_ASYNC_THRESHOLD=4 * 100000)
    def test_large_csv_import(self):
        with HTTMock(enketo_mock):
            xls_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "tutorial.xlsx",
            )
            self._publish_xls_form_to_project(xlsform_path=xls_path)
            view = XFormViewSet.as_view({"post": "csv_import", "get": "csv_import"})
            csv_import = fixtures_path("large_csv_upload.csv")
            post_data = {"csv_file": csv_import}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = view(request, pk=self.xform.id)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.data.get("additions"), 800)
            self.assertEqual(response.data.get("updates"), 0)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @override_settings(CSV_FILESIZE_IMPORT_ASYNC_THRESHOLD=20)
    def test_csv_import_async(self):
        with HTTMock(enketo_mock):
            xls_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "tutorial.xlsx",
            )
            self._publish_xls_form_to_project(xlsform_path=xls_path)
            count_before = self.xform.instances.count()
            view = XFormViewSet.as_view({"post": "csv_import"})
            csv_import = fixtures_path("good.csv")
            post_data = {"csv_file": csv_import}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = view(request, pk=self.xform.id)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(count_before + 9, self.xform.instances.count())

    def test_csv_import_diff_column(self):
        with HTTMock(enketo_mock):
            xls_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "tutorial.xlsx",
            )
            self._publish_xls_form_to_project(xlsform_path=xls_path)
            view = XFormViewSet.as_view({"post": "csv_import"})
            csv_import = fixtures_path("wrong_col.csv")
            post_data = {"csv_file": csv_import}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = view(request, pk=self.xform.id)
            self.assertEqual(response.status_code, 400)
            self.assertIn("error", response.data)
            self.assertEqual(
                response.data.get("error"),
                "Sorry uploaded file does not match the form. "
                "The file is missing the column(s): age, name.",
            )

    def test_csv_import_additional_columns(self):
        with HTTMock(enketo_mock):
            xls_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "tutorial.xlsx",
            )
            self._publish_xls_form_to_project(xlsform_path=xls_path)
            view = XFormViewSet.as_view({"post": "csv_import"})
            csv_import = fixtures_path("additional.csv")
            post_data = {"csv_file": csv_import}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = view(request, pk=self.xform.id)

            self.assertEqual(response.status_code, 200)
            self.assertIn("info", response.data)
            self.assertEqual(
                response.data.get("info"),
                "Additional column(s) excluded from the upload: '_additional'.",
            )

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch("onadata.apps.api.viewsets.xform_viewset.submit_csv_async")
    def test_raise_error_when_task_is_none(self, mock_submit_csv_async):
        with HTTMock(enketo_mock):
            settings.CSV_FILESIZE_IMPORT_ASYNC_THRESHOLD = 20
            mock_submit_csv_async.delay.return_value = None
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view({"post": "csv_import"})
            csv_import = fixtures_path("good.csv")
            post_data = {"csv_file": csv_import}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = view(request, pk=self.xform.id)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data.get("detail"), "Task not found")

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch("onadata.apps.api.viewsets.xform_viewset.submit_csv_async")
    def test_import_csv_asynchronously(self, mock_submit_csv_async):
        with HTTMock(enketo_mock):
            settings.CSV_FILESIZE_IMPORT_ASYNC_THRESHOLD = 20
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view({"post": "csv_import"})
            csv_import = fixtures_path("good.csv")
            post_data = {"csv_file": csv_import}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = view(request, pk=self.xform.id)
            self.assertEqual(response.status_code, 200)
            self.assertIsNotNone(response.data.get("task_id"))

    def test_csv_import_fail(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view({"post": "csv_import"})
            csv_import = fixtures_path("bad.csv")
            post_data = {"csv_file": csv_import}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = view(request, pk=self.xform.id)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get("Cache-Control"), None)
            self.assertIsNotNone(response.data.get("error"))

    def test_csv_import_fail_invalid_field_post(self):
        """Test that invalid post returns 400 with the error in json respone"""
        self._publish_xls_form_to_project()
        view = XFormViewSet.as_view({"post": "csv_import"})
        csv_import = fixtures_path("bad.csv")
        post_data = {"wrong_file_field": csv_import}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = view(request, pk=self.xform.id)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get("Cache-Control"), None)
        self.assertIsNotNone(response.data.get("error"))

    def test_csv_import_status_check(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view({"get": "csv_import"})
            data = {"job_uuid": "12345678"}
            request = self.factory.get("/", data=data, **self.extra)

            with patch(
                "onadata.apps.api.viewsets.xform_viewset."
                "get_async_csv_submission_status"
            ) as mock_async_response:
                mock_async_response.return_value = {"progress": 10, "total": 100}
                response = view(request, pk=self.xform.id)

                self.assertEqual(response.status_code, 200)
                self.assertIsNotNone(response.get("Cache-Control"))
                self.assertEqual(response.data.get("progress"), 10)
                self.assertEqual(response.data.get("total"), 100)

    @patch(("onadata.apps.api.viewsets.xform_viewset.get_async_csv_submission_status"))
    def test_csv_import_status_check_invalid_returned_value(
        self, mock_submission_status
    ):
        mock_submission_status.return_value = [(0, 0, {"h": 88})]
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view({"get": "csv_import"})
            data = {"job_uuid": "12345678"}
            request = self.factory.get("/", data=data, **self.extra)
            response = view(request, pk=self.xform.id)
            self.assertEqual(response.status_code, 400)
            error_message = (
                "The instance of the result is not a basestring;"
                " the job_uuid variable might be incorrect"
            )
            self.assertEqual(response.data["detail"], error_message)

    def test_update_xform_xls_file(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()

            title_old = self.xform.title
            self.assertIsNotNone(self.xform.version)
            last_updated_at = self.xform.last_updated_at
            version = self.xform.version
            form_id = self.xform.pk
            id_string = self.xform.id_string

            view = XFormViewSet.as_view(
                {
                    "patch": "partial_update",
                }
            )

            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation_version.xlsx",
            )
            with open(path, "rb") as xls_file:
                post_data = {"xls_file": xls_file}
                request = self.factory.patch("/", data=post_data, **self.extra)
                response = view(request, pk=form_id)
                self.assertEqual(response.status_code, 200)

            self.xform.refresh_from_db()
            new_version = self.xform.version
            new_last_updated_at = self.xform.last_updated_at
            # diff versions
            self.assertNotEqual(last_updated_at, new_last_updated_at)
            self.assertNotEqual(version, new_version)
            self.assertNotEqual(title_old, self.xform.title)
            self.assertEqual(form_id, self.xform.pk)
            self.assertEqual(id_string, self.xform.id_string)

    def test_manager_can_update_xform_xls_file(self):
        """Manager Role can replace xlsform"""
        self._publish_xls_form_to_project()
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._login_user_and_profile(extra_post_data=alice_data)

        # assign data entry role
        data = {
            "project": self.xform.project,
            "username": "alice",
            "role": "dataentry",
        }

        share_project = ShareProject(**data)
        share_project.save()

        title_old = self.xform.title
        self.assertIsNotNone(self.xform.version)
        version = self.xform.version
        form_id = self.xform.pk
        id_string = self.xform.id_string
        xml = self.xform.xml
        fhuuid = xml.find("formhub/uuid")
        self.assertEqual(xml[xml[:fhuuid].rfind("=") + 2 : fhuuid], "/data/")

        view = XFormViewSet.as_view(
            {
                "patch": "partial_update",
            }
        )

        path = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "main",
            "tests",
            "fixtures",
            "transportation",
            "transportation_version.xlsx",
        )
        with open(path, "rb") as xls_file:
            post_data = {"xls_file": xls_file}
            request = self.factory.patch("/", data=post_data, **self.extra)
            response = view(request, pk=form_id)
            self.assertEqual(response.status_code, 403)

        # assign manager role
        data = {
            "project": self.xform.project,
            "username": self.user.username,
            "role": "manager",
        }

        share_project = ShareProject(**data)
        share_project.save()

        with open(path, "rb") as xls_file:
            post_data = {"xls_file": xls_file}
            request = self.factory.patch("/", data=post_data, **self.extra)
            response = view(request, pk=form_id)
            self.assertEqual(response.status_code, 200)

        self.xform.refresh_from_db()
        new_version = self.xform.version

        # diff versions
        self.assertNotEqual(version, new_version)
        self.assertNotEqual(title_old, self.xform.title)
        self.assertEqual(form_id, self.xform.pk)
        self.assertEqual(id_string, self.xform.id_string)
        xml = self.xform.xml
        fhuuid = xml.find("formhub/uuid")
        self.assertEqual(xml[xml[:fhuuid].rfind("=") + 2 : fhuuid], "/data/")

    def test_update_xform_with_different_id_string_form_with_sub(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            self._make_submissions()

            self.assertIsNotNone(self.xform.version)
            form_id = self.xform.pk

            view = XFormViewSet.as_view(
                {
                    "patch": "partial_update",
                }
            )

            # try to replace a file that has a different id_string
            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation_different_id_string.xlsx",
            )
            with open(path, "rb") as xls_file:
                post_data = {"xls_file": xls_file}
                request = self.factory.patch("/", data=post_data, **self.extra)
                response = view(request, pk=form_id)
                self.assertEqual(response.status_code, 400)
                expected_response = (
                    "Your updated form's id_string "
                    "'transportation_2015_01_07' must match the existing "
                    "forms' id_string 'transportation_2011_07_25'."
                )
                self.assertEqual(response.data.get("text"), expected_response)

            # try to replace a file whose id_string hasn't been set
            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "tutorial_.xlsx",
            )
            with open(path, "rb") as xls_file:
                post_data = {"xls_file": xls_file}
                request = self.factory.patch("/", data=post_data, **self.extra)
                response = view(request, pk=form_id)
                self.assertEqual(response.status_code, 400)
                expected_response = (
                    "Your updated form's id_string "
                    "'tutorial_' must match the existing "
                    "forms' id_string 'transportation_2011_07_25'."
                )
                self.assertEqual(response.data.get("text"), expected_response)

    def test_update_xform_with_different_id_string_form_with_no_sub(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()

            self.assertIsNotNone(self.xform.version)
            form_id = self.xform.pk

            view = XFormViewSet.as_view(
                {
                    "patch": "partial_update",
                }
            )

            # try to replace a file that has a different id_string
            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation_different_id_string.xlsx",
            )
            with open(path, "rb") as xls_file:
                post_data = {"xls_file": xls_file}
                request = self.factory.patch("/", data=post_data, **self.extra)
                response = view(request, pk=form_id)
                self.assertEqual(response.status_code, 400)
                expected_response = (
                    "Your updated form's id_string "
                    "'transportation_2015_01_07' must match the existing "
                    "forms' id_string 'transportation_2011_07_25'."
                )
                self.assertEqual(response.data.get("text"), expected_response)

            # try to replace a file whose id_string hasn't been set
            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "tutorial_.xlsx",
            )
            with open(path, "rb") as xls_file:
                post_data = {"xls_file": xls_file}
                request = self.factory.patch("/", data=post_data, **self.extra)
                response = view(request, pk=form_id)
                self.assertEqual(response.status_code, 400)
                expected_response = (
                    "Your updated form's id_string "
                    "'tutorial_' must match the existing "
                    "forms' id_string 'transportation_2011_07_25'."
                )
                self.assertEqual(response.data.get("text"), expected_response)

    def test_update_xform_xls_file_with_different_model_name(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()

            self.assertIsNotNone(self.xform.version)
            form_id = self.xform.pk

            view = XFormViewSet.as_view(
                {
                    "patch": "partial_update",
                }
            )

            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation_updated.xlsx",
            )
            with open(path, "rb") as xls_file:
                post_data = {"xls_file": xls_file}
                request = self.factory.patch("/", data=post_data, **self.extra)
                response = view(request, pk=form_id)
                self.assertEqual(response.status_code, 200)
                xform = XForm.objects.get(pk=form_id)
                self.assertEqual("data", xform.survey.xml_instance().tagName)

    def test_id_strings_should_be_unique_in_each_account(self):
        with HTTMock(enketo_mock):
            # pylint: disable=no-member
            project_count = Project.objects.count()

            self._project_create()
            self._publish_xls_form_to_project()
            data_2 = {
                "name": "demo2",
                "owner": "http://testserver/api/v1/users/%s" % self.user.username,
                "metadata": {
                    "description": "Demo2 Description",
                    "location": "Nakuru, Kenya",
                    "category": "education",
                },
                "public": False,
            }
            data_3 = {
                "name": "demo3",
                "owner": "http://testserver/api/v1/users/%s" % self.user.username,
                "metadata": {
                    "description": "Demo3 Description",
                    "location": "Kisumu, Kenya",
                    "category": "nursing",
                },
                "public": False,
            }
            self._project_create(data_2, False)
            self._publish_xls_form_to_project()
            self._project_create(data_3, False)
            self._publish_xls_form_to_project()
            self.assertEqual(project_count + 3, Project.objects.count())

            xform_1 = XForm.objects.get(project__name="demo")
            xform_2 = XForm.objects.get(project__name="demo2")
            xform_3 = XForm.objects.get(project__name="demo3")
            self.assertEqual(xform_1.id_string, "transportation_2011_07_25")
            self.assertEqual(xform_2.id_string, "transportation_2011_07_25_1")
            self.assertEqual(xform_3.id_string, "transportation_2011_07_25_2")

    def test_id_string_is_unique_after_form_deletion(self):
        xform_count = XForm.objects.count()

        # create 2 projects and submit the same form to each of the project
        self._project_create()
        first_project = self.project
        self._publish_xls_form_to_project()
        data_2 = {
            "name": "demo2",
            "owner": "http://testserver/api/v1/users/%s" % self.user.username,
            "metadata": {
                "description": "Demo2 Description",
                "location": "Nakuru, Kenya",
                "category": "education",
            },
            "public": False,
        }
        self._project_create(data_2, False)
        self._publish_xls_form_to_project()
        self.assertEqual(xform_count + 2, XForm.objects.count())

        xform_1 = XForm.objects.get(project__name="demo")
        xform_2 = XForm.objects.get(project__name="demo2")
        self.assertEqual(xform_1.id_string, "transportation_2011_07_25")
        self.assertEqual(xform_2.id_string, "transportation_2011_07_25_1")
        self.assertEqual(xform_1.user, xform_2.user)

        # delete one form in a project, publish the same form to the project
        # where the form was deleted and check that '_1' is not appended to
        # the id_string; ensure the id_string is unique
        xform_1.delete()
        self.project = first_project
        self._publish_xls_form_to_project()
        xform_3 = XForm.objects.get(project__name="demo")
        self.assertEqual(xform_count + 2, XForm.objects.count())
        self.assertEqual(xform_3.id_string, "transportation_2011_07_25")
        self.assertEqual(xform_1.user, xform_3.user)

    def test_update_xform_xls_bad_file(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()

            self.assertIsNotNone(self.xform.version)
            version = self.xform.version
            form_id = self.xform.pk

            view = XFormViewSet.as_view(
                {
                    "patch": "partial_update",
                }
            )

            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation.bad_id.xlsx",
            )
            with open(path, "rb") as xls_file:
                post_data = {"xls_file": xls_file}
                request = self.factory.patch("/", data=post_data, **self.extra)
                response = view(request, pk=form_id)

                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get("Cache-Control"), None)

            self.xform.refresh_from_db()
            new_version = self.xform.version

            # fails to update the form
            self.assertEqual(version, new_version)
            self.assertEqual(form_id, self.xform.pk)

    def test_update_xform_xls_file_with_submissions(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            self._make_submissions()

            self.assertIsNotNone(self.xform.version)
            version = self.xform.version
            form_id = self.xform.pk
            xform_json = self.xform.json
            xform_xml = self.xform.xml

            view = XFormViewSet.as_view(
                {
                    "patch": "partial_update",
                }
            )

            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation_updated.xlsx",
            )
            with open(path, "rb") as xls_file:
                post_data = {"xls_file": xls_file}
                request = self.factory.patch("/", data=post_data, **self.extra)
                response = view(request, pk=form_id)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get("Cache-Control"), None)

            self.xform.refresh_from_db()

            self.assertEqual(form_id, self.xform.pk)
            self.assertNotEqual(version, self.xform.version)
            self.assertNotEqual(xform_json, self.xform.json)
            self.assertNotEqual(xform_xml, self.xform.xml)
            is_updated_form = (
                len(
                    [
                        e.name
                        for e in self.xform.survey_elements
                        if e.name == "preferred_means"
                    ]
                )
                > 0
            )
            self.assertTrue(is_updated_form)

    def test_update_xform_xls_file_with_version_set(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            form_id = self.xform.pk

            self.assertIsNotNone(self.xform.version)

            view = XFormViewSet.as_view(
                {
                    "patch": "partial_update",
                }
            )

            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation_version.xlsx",
            )
            with open(path, "rb") as xls_file:
                post_data = {"xls_file": xls_file}
                request = self.factory.patch("/", data=post_data, **self.extra)
                response = view(request, pk=form_id)

                self.assertEqual(response.status_code, 200)

            self.xform.refresh_from_db()

            # diff versions
            self.assertEqual(self.xform.version, "212121211")
            self.assertEqual(form_id, self.xform.pk)

    @patch("onadata.apps.main.forms.requests")
    def test_update_xform_xls_url(self, mock_requests):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            form_id = self.xform.pk
            count = XForm.objects.all().count()

            self.assertIsNotNone(self.xform.version)

            view = XFormViewSet.as_view(
                {
                    "patch": "partial_update",
                }
            )

            xls_url = "https://ona.io/examples/forms/tutorial/form.xlsx"
            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation_version.xlsx",
            )

            with open(path, "rb") as xls_file:
                mock_response = get_mocked_response_for_file(
                    xls_file, "transportation_version.xlsx", 200
                )
                mock_requests.head.return_value = mock_response
                mock_requests.get.return_value = mock_response

                post_data = {"xls_url": xls_url}
                request = self.factory.patch("/", data=post_data, **self.extra)
                response = view(request, pk=form_id)

                self.assertEqual(response.status_code, 200)

                self.xform.refresh_from_db()

                self.assertEqual(count, XForm.objects.all().count())
                # diff versions
                self.assertEqual(self.xform.version, "212121211")
                self.assertEqual(form_id, self.xform.pk)

    @patch("onadata.apps.main.forms.requests")
    def test_update_xform_dropbox_url(self, mock_requests):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            form_id = self.xform.pk
            count = XForm.objects.all().count()

            self.assertIsNotNone(self.xform.version)

            view = XFormViewSet.as_view(
                {
                    "patch": "partial_update",
                }
            )

            xls_url = "https://ona.io/examples/forms/tutorial/form.xlsx"
            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation_version.xlsx",
            )

            with open(path, "rb") as xls_file:
                mock_response = get_mocked_response_for_file(
                    xls_file, "transportation_version.xlsx", 200
                )
                mock_requests.head.return_value = mock_response
                mock_requests.get.return_value = mock_response

                post_data = {"dropbox_xls_url": xls_url}
                request = self.factory.patch("/", data=post_data, **self.extra)
                response = view(request, pk=form_id)

                self.assertEqual(response.status_code, 200)

                self.xform.refresh_from_db()

                self.assertEqual(count, XForm.objects.all().count())
                # diff versions
                self.assertEqual(self.xform.version, "212121211")
                self.assertEqual(form_id, self.xform.pk)

    def test_update_xform_using_put_with_invalid_input(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            form_id = self.xform.pk

            unsanitized_html_str = "<h1>HTML Injection testing</h1>"
            view = XFormViewSet.as_view(
                {
                    "put": "update",
                }
            )

            put_data = {
                "uuid": "ae631e898bd34ced91d2a309d8b72das",
                "description": unsanitized_html_str,
                "downloadable": False,
                "owner": "http://testserver/api/v1/users/{0}".format(self.user),
                "created_by": "http://testserver/api/v1/users/{0}".format(self.user),
                "public": False,
                "public_data": False,
                "project": "http://testserver/api/v1/projects/{0}".format(
                    self.xform.project.pk
                ),
                "title": "http://api.kfc.burger-king.nandos.io",
                "version": unsanitized_html_str,
            }

            with self.assertRaises(XLSFormError) as err:
                request = self.factory.put("/", data=put_data, **self.extra)
                response = view(request, pk=form_id)

            self.assertEqual(
                "Invalid title value; value shouldn't match a URL", str(err.exception)
            )

            put_data["title"] = "api.kfc.burger-king.nandos.io"

            with self.assertRaises(XLSFormError) as err:
                request = self.factory.put("/", data=put_data, **self.extra)
                response = view(request, pk=form_id)

            self.assertEqual(
                "Invalid title value; value shouldn't match a URL", str(err.exception)
            )

            put_data["title"] = "mercycorps.org"

            with self.assertRaises(XLSFormError) as err:
                request = self.factory.put("/", data=put_data, **self.extra)
                response = view(request, pk=form_id)

            self.assertEqual(
                "Invalid title value; value shouldn't match a URL", str(err.exception)
            )

            put_data["title"] = "https://example.qwerty.com:8989/id"

            with self.assertRaises(XLSFormError) as err:
                request = self.factory.put("/", data=put_data, **self.extra)
                response = view(request, pk=form_id)

            self.assertEqual(
                "Invalid title value; value shouldn't match a URL", str(err.exception)
            )

            put_data["title"] = "http://10.1.1.1:9090/id"

            with self.assertRaises(XLSFormError) as err:
                request = self.factory.put("/", data=put_data, **self.extra)
                response = view(request, pk=form_id)

            self.assertEqual(
                "Invalid title value; value shouldn't match a URL", str(err.exception)
            )

            put_data["title"] = "Transport Form"

            # trigger error is form version is invalid
            with self.assertRaises(XLSFormError) as err:
                request = self.factory.put("/", data=put_data, **self.extra)
                response = view(request, pk=form_id)

            self.assertEqual(
                "Version shouldn't have any invalid characters ('>' '&' '<')",
                str(err.exception),
            )

            put_data["version"] = self.xform.version

            request = self.factory.put("/", data=put_data, **self.extra)
            response = view(request, pk=form_id)
            self.assertEqual(response.status_code, 200, response.data)

            put_data["title"] = "Domain 1: Laws, Policies and Plans"

            request = self.factory.put("/", data=put_data, **self.extra)
            response = view(request, pk=form_id)
            self.assertEqual(response.status_code, 200, response.data)

            self.xform.refresh_from_db()

            # check that description has been sanitized
            self.assertEqual(
                conditional_escape(unsanitized_html_str), self.xform.description
            )

    def test_update_xform_using_put(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            form_id = self.xform.pk

            version = self.xform.version
            view = XFormViewSet.as_view(
                {
                    "put": "update",
                }
            )

            post_data = {
                "uuid": "ae631e898bd34ced91d2a309d8b72das",
                "description": "Transport form",
                "downloadable": False,
                "owner": "http://testserver/api/v1/users/{0}".format(self.user),
                "created_by": "http://testserver/api/v1/users/{0}".format(self.user),
                "public": False,
                "public_data": False,
                "project": "http://testserver/api/v1/projects/{0}".format(
                    self.xform.project.pk
                ),
                "title": "Transport Form",
                "version": self.xform.version,
            }
            request = self.factory.put("/", data=post_data, **self.extra)
            response = view(request, pk=form_id)
            self.assertEqual(response.status_code, 200, response.data)

            self.xform.refresh_from_db()

            self.assertEqual(version, self.xform.version)
            self.assertEqual(self.xform.description, "Transport form")
            self.assertEqual(self.xform.title, "Transport Form")
            self.assertEqual(form_id, self.xform.pk)

    def test_update_xform_using_put_without_required_field(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            form_id = self.xform.pk

            view = XFormViewSet.as_view(
                {
                    "put": "update",
                }
            )

            post_data = {
                "uuid": "ae631e898bd34ced91d2a309d8b72das",
                "description": "Transport form",
                "downloadable": False,
                "owner": "http://testserver/api/v1/users/{0}".format(self.user),
                "created_by": "http://testserver/api/v1/users/{0}".format(self.user),
                "public": False,
                "public_data": False,
                "project": "http://testserver/api/v1/projects/{0}".format(
                    self.xform.project.pk
                ),
            }
            request = self.factory.put("/", data=post_data, **self.extra)
            response = view(request, pk=form_id)

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.data, {"title": ["This field is required."]})

    def test_public_xform_accessible_by_authenticated_users(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            self.xform.shared = True
            self.xform.save()

            # log in as other user other than form owner
            previous_user = self.user
            alice_data = {"username": "alice", "email": "alice@localhost.com"}
            self._login_user_and_profile(extra_post_data=alice_data)
            self.assertEqual(self.user.username, "alice")
            self.assertNotEqual(previous_user, self.user)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch("onadata.apps.api.tasks.get_async_status")
    def test_publish_form_async(self, mock_get_status):
        mock_get_status.return_value = {"job_status": "PENDING"}

        count = XForm.objects.count()
        view = XFormViewSet.as_view({"post": "create_async", "get": "create_async"})

        path = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "main",
            "tests",
            "fixtures",
            "transportation",
            "transportation.xlsx",
        )

        with open(path, "rb") as xls_file:
            post_data = {"xls_file": xls_file}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = view(request)

            self.assertEqual(response.status_code, 202)

        self.assertTrue("job_uuid" in response.data)

        self.assertEqual(count + 1, XForm.objects.count())

        # get the result
        get_data = {"job_uuid": response.data.get("job_uuid")}
        request = self.factory.get("/", data=get_data, **self.extra)
        response = view(request)

        self.assertTrue(mock_get_status.called)

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data, {"job_status": "PENDING"})

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch(
        "onadata.apps.api.tasks.tools.do_publish_xlsform",
        side_effect=[MemoryError(), MemoryError(), Mock()],
    )
    @patch("onadata.apps.api.tasks.get_async_status")
    def test_publish_form_async_trigger_memory_error_then_published(
        self, mock_get_status, mock_publish_xlsform
    ):
        mock_get_status.return_value = {"job_status": "PENDING"}

        view = XFormViewSet.as_view(
            {
                "post": "create_async",
            }
        )

        path = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "main",
            "tests",
            "fixtures",
            "transportation",
            "transportation.xlsx",
        )

        with open(path, "rb") as xls_file:
            post_data = {"xls_file": xls_file}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = view(request)

            self.assertTrue(mock_publish_xlsform.called)
            # `do_publish_xlsform` function should be called 3 times as that's
            # the size of the side_effect list - the function will be retried 3
            # times (fail twice and succeed on the third call)
            self.assertEqual(mock_publish_xlsform.call_count, 3)
            self.assertEqual(response.status_code, 202)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch(
        "onadata.apps.api.tasks.tools.do_publish_xlsform",
        side_effect=[MemoryError(), MemoryError(), MemoryError()],
    )
    @patch("onadata.apps.api.tasks.get_async_status")
    def test_failed_form_publishing_after_maximum_retries(
        self, mock_get_status, mock_publish_xlsform
    ):
        error_message = {
            "error": (
                "Service temporarily unavailable, please try to publish the form again"
            )
        }
        mock_get_status.return_value = error_message

        view = XFormViewSet.as_view({"post": "create_async", "get": "create_async"})

        path = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "main",
            "tests",
            "fixtures",
            "transportation",
            "transportation.xlsx",
        )

        get_data = None
        with open(path, "rb") as xls_file:
            post_data = {"xls_file": xls_file}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = view(request)

            self.assertTrue(mock_publish_xlsform.called)
            # `do_publish_xlsform` function should be called 4 times as the
            # 4th triggers `MemoryError` exception which is not retried and
            # that's where we return a custom message
            self.assertEqual(mock_publish_xlsform.call_count, 4)
            self.assertEqual(response.status_code, 202)
            self.assertTrue("job_uuid" in response.data)
            get_data = {"job_uuid": response.data.get("job_uuid")}

        if get_data:
            request = self.factory.get("/", data=get_data, **self.extra)
            response = view(request)

            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.data, error_message)

    @flaky(max_runs=10)
    def test_survey_preview_endpoint(self):
        view = XFormViewSet.as_view({"post": "survey_preview", "get": "survey_preview"})

        request = self.factory.post("/", **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data.get("detail"), "Missing body")

        body = (
            '"survey",,,,,,,,,,\n,"name","type","label","hint",'
            '"required","relevant","default","'
            'constraint","constraint_message","appearance"\n,"sdfasdfaf"'
            ',"geopoint","sdfasdfaf",,"false",,,,,\n,"sdfsdaf","text",'
            '"sdfsdaf",,"true",,,,,\n,"start","start",,,,,,,,\n,"end",'
            '"end",,,,,,,,\n"settings",,\n,"form_title","form_id"\n,'
            '"Post refactro","Post_refactro"'
        )
        data = {"body": body}
        request = self.factory.post("/", data=data, **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200, response.data)
        unique_string = response.data.get("unique_string")
        username = response.data.get("username")
        self.assertIsNotNone(unique_string)

        request = self.factory.get("/")
        response = view(request)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data.get("detail"), "Username not provided")

        data = {"username": username}
        request = self.factory.get("/", data=data)
        response = view(request)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data.get("detail"), "Filename MUST be provided")

        data = {"filename": unique_string, "username": username}
        request = self.factory.get("/", data=data)
        response = view(request)
        self.assertEqual(response.status_code, 200, response.data)

        body = (
            '"survey",,,,,,,,,,\n,"name","type","label","hint",'
            '"required","relevant","default","'
            'constraint","constraint_message","appearance"\n,"sdfasdfaf sdf"'
            ',"geopoint","sdfasdfaf",,"false",,,,,\n,"sdfsdaf","text",'
            '"sdfsdaf",,"true",,,,,\n,"start","start",,,,,,,,\n,"end",'
            '"end",,,,,,,,\n"settings",,\n,"form_title","form_id"\n,'
            '"Post refactro","Post_refactro"'
        )
        data = {"body": body}
        request = self.factory.post("/", data=data, **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 400, response.data)
        error_message = (
            "[row : 2] Invalid question name 'sdfasdfaf sdf'. "
            "Names must begin with a letter, colon, or underscore. "
            "Other characters can include numbers, dashes, and periods."
        )
        self.assertEqual(response.data.get("detail"), error_message)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch("onadata.apps.api.tasks.get_async_status")
    def test_delete_xform_async(self, mock_get_status):
        with HTTMock(enketo_mock):
            mock_get_status.return_value = {"job_status": "PENDING"}
            self._publish_xls_form_to_project()
            count = XForm.objects.count()
            view = XFormViewSet.as_view(
                {
                    "delete": "delete_async",
                }
            )
            formid = self.xform.pk
            request = self.factory.delete("/", **self.extra)
            response = view(request, pk=formid)
            self.assertIsNotNone(response.data)
            self.assertEqual(response.status_code, 202)
            self.assertTrue("job_uuid" in response.data)
            self.assertTrue("time_async_triggered" in response.data)
            self.assertEqual(count, XForm.objects.count())

            view = XFormViewSet.as_view({"get": "delete_async"})

            get_data = {"job_uuid": response.data.get("job_uuid")}
            request = self.factory.get("/", data=get_data, **self.extra)
            response = view(request, pk=formid)

            self.assertTrue(mock_get_status.called)
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.data, {"job_status": "PENDING"})

            xform = XForm.objects.get(pk=formid)

            self.assertIsNotNone(xform.deleted_at)
            self.assertTrue("deleted-at" in xform.id_string)
            self.assertEqual(xform.deleted_by, self.user)

            view = XFormViewSet.as_view({"get": "retrieve"})

            request = self.factory.get("/", **self.extra)
            response = view(request, pk=formid)

            self.assertEqual(response.status_code, 404)

    def test_xform_retrieve_osm_format(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()

            view = XFormViewSet.as_view(
                {
                    "get": "retrieve",
                }
            )
            formid = self.xform.pk

            request = self.factory.get("/", data={"format": "osm"}, **self.extra)
            response = view(request, pk=formid)
            self.assertEqual(response.status_code, 200)

    def test_check_async_publish_empty_uuid(self):
        view = XFormViewSet.as_view({"get": "create_async"})

        # set an empty uuid
        get_data = {"job_uuid": ""}
        request = self.factory.get("/", data=get_data, **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data, {"error": "Empty job uuid"})

    def test_always_new_report_with_data_id(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            self._make_submissions()

            data_value = "template 1|http://xls_server"
            self._add_form_metadata(self.xform, "external_export", data_value)
            # pylint: disable=no-member
            metadata = MetaData.objects.get(
                object_id=self.xform.id, data_type="external_export"
            )
            paths = [
                os.path.join(
                    self.main_directory,
                    "fixtures",
                    "transportation",
                    "instances_w_uuid",
                    s,
                    s + ".xml",
                )
                for s in ["transport_2011-07-25_19-05-36"]
            ]

            self._make_submission(paths[0])
            self.assertEqual(self.response.status_code, 201)

            view = XFormViewSet.as_view(
                {
                    "get": "retrieve",
                }
            )
            data_id = self.xform.instances.all().order_by("-pk")[0].pk
            data = {"meta": metadata.pk, "data_id": data_id}
            formid = self.xform.pk
            request = self.factory.get("/", data=data, **self.extra)

            with HTTMock(external_mock_single_instance):
                # External export
                response = view(request, pk=formid, format="xlsx")
                self.assertEqual(response.status_code, 302)
                expected_url = "http://xls_server/xls/ee3ff9d8f5184fc4a8fdebc2547cc059"
                self.assertEqual(response.url, expected_url)

            count = Export.objects.filter(
                xform=self.xform, export_type=Export.EXTERNAL_EXPORT
            ).count()

            with HTTMock(external_mock_single_instance2):
                # External export
                response = view(request, pk=formid, format="xlsx")
                self.assertEqual(response.status_code, 302)
                expected_url = "http://xls_server/xls/ee3ff9d8f5184fc4a8fdebc2547cc057"
                self.assertEqual(response.url, expected_url)

            count2 = Export.objects.filter(
                xform=self.xform, export_type=Export.EXTERNAL_EXPORT
            ).count()

            self.assertEqual(count + 1, count2)

    def test_different_form_versions(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()

            view = XFormViewSet.as_view({"patch": "partial_update", "get": "retrieve"})

            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation_version.xlsx",
            )
            version_count = XFormVersion.objects.filter(xform=self.xform).count()
            with open(path, "rb") as xls_file:
                post_data = {"xls_file": xls_file}
                request = self.factory.patch("/", data=post_data, **self.extra)
                response = view(request, pk=self.xform.pk)
                self.assertEqual(response.status_code, 200)
                self.xform.refresh_from_db()

                # ensure that an XForm version object is created
                versions = XFormVersion.objects.filter(xform=self.xform)
                self.assertEqual(versions.count(), version_count + 1)
                latest_version = versions.order_by("-date_created").first()
                self.assertEqual(latest_version.version, self.xform.version)
                self.assertEqual(latest_version.xls, self.xform.xls)
                self.assertEqual(latest_version.xml, self.xform.xml)

            self._make_submissions()
            # make more submission after form update
            surveys = ["transport_2011-07-25_19-05-36-edited"]
            paths = [
                os.path.join(
                    self.main_directory,
                    "fixtures",
                    "transportation",
                    "instances_w_uuid",
                    s,
                    s + ".xml",
                )
                for s in surveys
            ]

            auth = DigestAuth(
                self.profile_data["username"], self.profile_data["password1"]
            )
            for path in paths:
                self._make_submission(path, None, None, auth=auth)

            request = self.factory.get("/", **self.extra)
            response = view(request, pk=self.xform.pk)
            self.assertEqual(response.status_code, 200)

            self.assertIn("form_versions", response.data)

            expected = [
                {"total": 3, "version": "212121211"},
                {"total": 2, "version": "2014111"},
            ]

            for v in expected:
                self.assertIn(v, response.data.get("form_versions"))

    def test_versions_endpoint(self):
        """
        Tests the versions endpoint
        """
        xls_file_path = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "logger",
            "fixtures",
            "external_choice_form_v1.xlsx",
        )
        self._publish_xls_form_to_project(xlsform_path=xls_file_path)

        view = XFormViewSet.as_view({"patch": "partial_update", "get": "versions"})

        request = self.factory.get(
            f"/api/v1/forms/{self.xform.id}/versions", **self.extra
        )
        response = view(request, pk=self.xform.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        version_count = XFormVersion.objects.filter(xform=self.xform).count()

        expected_keys = [
            "xform",
            "url",
            "xml",
            "created_by",
            "version",
            "date_created",
            "date_modified",
        ]
        self.assertEqual(list(response.data[0].keys()), expected_keys)
        expected_data = {
            "xform": f"http://testserver/api/v1/forms/{self.xform.pk}",
            "version": self.xform.version,
            "url": (
                "http://testserver/api/v1/forms/"
                f"{self.xform.pk}/versions/{self.xform.version}"
            ),
            "xml": (
                "http://testserver/api/v1/forms/"
                f"{self.xform.pk}/versions/{self.xform.version}.xml"
            ),
            "created_by": (f"http://testserver/api/v1/users/{self.user.username}"),
        }
        returned_data = dict(response.data[0])
        returned_data.pop("date_created")
        returned_data.pop("date_modified")
        self.assertEqual(returned_data, expected_data)
        old_version = self.xform.version
        expected_json = self.xform.json_dict()
        expected_xml = self.xform.xml

        # Replace form
        xls_file_path = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "logger",
            "fixtures",
            "external_choice_form_v2.xlsx",
        )
        with open(xls_file_path, "rb") as xls_file:
            post_data = {"xls_file": xls_file}
            request = self.factory.patch("/", data=post_data, **self.extra)
            response = view(request, pk=self.xform.id)
            self.assertEqual(response.status_code, 200)
        self.assertEqual(
            XFormVersion.objects.filter(xform=self.xform).count(), version_count + 1
        )

        # Able to retrieve old version
        request = self.factory.get(
            f"/api/v1/forms/{self.xform.id}/versions/{old_version}", **self.extra
        )
        response = view(request, pk=self.xform.pk, version_id=old_version)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected_json)

        response = view(request, pk=self.xform.pk, version_id=old_version, format="xml")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected_xml)

        # Returns a 404 for an invalid version
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.xform.pk, version_id="invalid")
        self.assertEqual(response.status_code, 404)

    def test_csv_export_with_win_excel_utf8(self):
        with HTTMock(enketo_mock):
            # provide hxl file path
            xlsform_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "hxl_test",
                "hxl_example.xlsx",
            )
            self._publish_xls_form_to_project(xlsform_path=xlsform_path)
            # submit one hxl instance
            _submission_time = parse_datetime("2013-02-18 15:54:01Z")
            mock_date_modified = datetime(2023, 9, 20, 11, 41, 0, tzinfo=timezone.utc)

            with patch(
                "django.utils.timezone.now", Mock(return_value=mock_date_modified)
            ):
                self._make_submission(
                    os.path.join(
                        settings.PROJECT_ROOT,
                        "apps",
                        "main",
                        "tests",
                        "fixtures",
                        "hxl_test",
                        "hxl_example_2.xml",
                    ),
                    forced_submission_time=_submission_time,
                )

            self.assertTrue(self.xform.has_hxl_support)

            view = XFormViewSet.as_view({"get": "retrieve"})

            request = self.factory.get("/", **self.extra)
            response = view(request, pk=self.xform.pk)
            # check that response has property 'has_hxl_support' which is true
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.data.get("has_hxl_support"))
            # sort csv data in ascending order
            data = {"win_excel_utf8": True}
            request = self.factory.get("/", data=data, **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)
            instance = self.xform.instances.first()
            data_id, date_modified = (
                instance.pk,
                mock_date_modified.isoformat(),
            )

            content = get_response_content(response)

            expected_content = (
                "\ufeffage,name,meta/instanceID,_id,_uuid,_submission_time,"
                "_date_modified,_tags,_notes,_version,_duration,_submitted_by,"
                "_total_media,_media_count,_media_all_received\n\ufeff#age"
                ",,,,,,,,,,,,,,\n\ufeff"
                "38,CR7,uuid:74ee8b73-48aa-4ced-9089-862f93d49c16,"
                "%s,74ee8b73-48aa-4ced-9089-862f93d49c16,2013-02-18T15:54:01+00:00,"
                "%s,,,201604121155,,bob,0,0,True\n" % (data_id, date_modified)
            )
            self.assertEqual(content, expected_content)
            headers = dict(response.items())
            self.assertEqual(headers["Content-Type"], "application/csv")
            content_disposition = headers["Content-Disposition"]
            filename = filename_from_disposition(content_disposition)
            _, ext = os.path.splitext(filename)
            self.assertEqual(ext, '.csv"')
            # sort csv data in ascending order
            data = {"win_excel_utf8": False}
            request = self.factory.get("/", data=data, **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            content = get_response_content(response)
            expected_content = (
                "age,name,meta/instanceID,_id,_uuid,_submission_time,"
                "_date_modified,_tags,_notes,_version,_duration,_submi"
                "tted_by,_total_media,_media_count,_media_all_received\n"
                "#age,,,,,,,,,,,,,,\n"
                "38,CR7,uuid:74ee8b73-48aa-4ced-9089-862f93d49c16"
                ",%s,74ee8b73-48aa-4ced-9089-862f93d49c16,2013-02-18T15:54:01+00:00,"
                "%s,,,201604121155,,bob,0,0,True\n" % (data_id, date_modified)
            )

            self.assertEqual(expected_content, content)

            headers = dict(response.items())
            self.assertEqual(headers["Content-Type"], "application/csv")
            content_disposition = headers["Content-Disposition"]
            filename = filename_from_disposition(content_disposition)
            basename, ext = os.path.splitext(filename)
            self.assertEqual(ext, '.csv"')

    @flaky
    def test_csv_export_with_and_without_include_hxl(self):
        with HTTMock(enketo_mock):
            # provide hxl file path
            xlsform_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "hxl_test",
                "hxl_example.xlsx",
            )
            self._publish_xls_form_to_project(xlsform_path=xlsform_path)
            # submit one hxl instance
            _submission_time = parse_datetime("2013-02-18 15:54:01Z")
            self._make_submission(
                os.path.join(
                    settings.PROJECT_ROOT,
                    "apps",
                    "main",
                    "tests",
                    "fixtures",
                    "hxl_test",
                    "hxl_example.xml",
                ),
                forced_submission_time=_submission_time,
            )
            self.assertTrue(self.xform.has_hxl_support)
            instance = self.xform.instances.first()
            data_id, date_modified = (
                instance.json["_id"],
                instance.json["_date_modified"],
            )

            view = XFormViewSet.as_view({"get": "retrieve"})

            request = self.factory.get("/", **self.extra)
            response = view(request, pk=self.xform.pk)
            # check that response has property 'has_hxl_support' which is true
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.data.get("has_hxl_support"))

            data = {"include_hxl": False}
            request = self.factory.get("/", data=data, **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            content = get_response_content(response)
            expected_content = (
                "age,name,meta/instanceID,_id,_uuid,_submission_time,"
                "_date_modified,_tags,_notes,_version,_duration,_submitted_by,"
                "_total_media,_media_count,_media_all_received\n"
                "29,Lionel Messi,uuid:74ee8b73-48aa-4ced-9072-862f93d49c16,"
                f"{data_id},74ee8b73-48aa-4ced-9072-862f93d49c16,2013-02-18T15:54:01+00:00,"
                f"{date_modified},,,201604121155,,bob,0,0,True\n"
            )
            self.assertEqual(expected_content, content)
            headers = dict(response.items())
            self.assertEqual(headers["Content-Type"], "application/csv")
            content_disposition = headers["Content-Disposition"]
            filename = filename_from_disposition(content_disposition)
            basename, ext = os.path.splitext(filename)
            self.assertEqual(ext, '.csv"')

            request = self.factory.get("/", **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            content = get_response_content(response)
            expected_content = (
                "age,name,meta/instanceID,_id,_uuid,_submission_time,"
                "_date_modified,_tags,_notes,_version,_duration,"
                "_submitted_by,_total_media,_media_count,"
                "_media_all_received\n"
                "#age,,,,,,,,,,,,,,\n"
                "29,Lionel Messi,uuid:74ee8b73-48aa-4ced-9072-862f93d49c16,"
                "%s,74ee8b73-48aa-4ced-9072-862f93d49c16,2013-02-18T15:54:01+00:00"
                ",%s,,,201604121155,,bob,0,0,True\n" % (data_id, date_modified)
            )
            self.assertEqual(expected_content, content)
            headers = dict(response.items())
            self.assertEqual(headers["Content-Type"], "application/csv")
            content_disposition = headers["Content-Disposition"]
            filename = filename_from_disposition(content_disposition)
            basename, ext = os.path.splitext(filename)
            self.assertEqual(ext, '.csv"')

    def test_csv_export__with_and_without_group_delimiter(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            survey = self.surveys[0]
            _submission_time = parse_datetime("2013-02-18 15:54:01Z")
            self._make_submission(
                os.path.join(
                    settings.PROJECT_ROOT,
                    "apps",
                    "main",
                    "tests",
                    "fixtures",
                    "transportation",
                    "instances",
                    survey,
                    survey + ".xml",
                ),
                forced_submission_time=_submission_time,
            )

            view = XFormViewSet.as_view({"get": "retrieve"})

            data = {"remove_group_name": False}
            request = self.factory.get("/", data=data, **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            headers = dict(response.items())
            self.assertEqual(headers["Content-Type"], "application/csv")
            content_disposition = headers["Content-Disposition"]
            filename = filename_from_disposition(content_disposition)
            basename, ext = os.path.splitext(filename)
            self.assertEqual(ext, '.csv"')

            content = get_response_content(response)
            content_header_row_with_slashes = content.split("\n")[0]

            data = {"remove_group_name": False, "group_delimiter": "."}
            request = self.factory.get("/", data=data, **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            headers = dict(response.items())
            self.assertEqual(headers["Content-Type"], "application/csv")
            content_disposition = headers["Content-Disposition"]
            filename = filename_from_disposition(content_disposition)
            basename, ext = os.path.splitext(filename)
            self.assertEqual(ext, '.csv"')

            content = get_response_content(response)
            content_header_row_with_dots = content.split("\n")[0]
            self.assertEqual(
                content_header_row_with_dots,
                content_header_row_with_slashes.replace("/", "."),
            )

    def test_csv_export__with_and_without_do_not_split_select_multiples(self):
        with HTTMock(enketo_mock):
            xlsform_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "sample_accent.xlsx",
            )
            self._publish_xls_form_to_project(xlsform_path=xlsform_path)
            _submission_time = parse_datetime("2013-02-18 15:54:01Z")
            for a in range(1, 4):
                self._make_submission(
                    os.path.join(
                        settings.PROJECT_ROOT,
                        "apps",
                        "main",
                        "tests",
                        "fixtures",
                        "sample_accent_instances",
                        "instance_%s.xml" % a,
                    ),
                    forced_submission_time=_submission_time,
                )

            view = XFormViewSet.as_view({"get": "retrieve"})

            data = {"remove_group_name": False}
            request = self.factory.get("/", data=data, **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            headers = dict(response.items())
            self.assertEqual(headers["Content-Type"], "application/csv")
            content_disposition = headers["Content-Disposition"]
            filename = filename_from_disposition(content_disposition)
            basename, ext = os.path.splitext(filename)
            self.assertEqual(ext, '.csv"')

            content = get_response_content(response)
            content_header_row_select_multiple_split = content.split("\n")[0]
            multiples_select_split = len(
                content_header_row_select_multiple_split.split(",")
            )

            data = {"remove_group_name": False, "do_not_split_select_multiples": True}
            request = self.factory.get("/", data=data, **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            headers = dict(response.items())
            self.assertEqual(headers["Content-Type"], "application/csv")
            content_disposition = headers["Content-Disposition"]
            filename = filename_from_disposition(content_disposition)
            basename, ext = os.path.splitext(filename)
            self.assertEqual(ext, '.csv"')

            content = get_response_content(response)
            content_header_row_select_multiple_not_split = content.split("\n")[0]
            no_multiples_select_split = len(
                content_header_row_select_multiple_not_split.split(",")
            )

            self.assertNotEqual(multiples_select_split, no_multiples_select_split)
            self.assertGreater(multiples_select_split, no_multiples_select_split)

    @override_settings(ALLOWED_HOSTS=["*"])
    def test_csv_export_with_and_without_removed_group_name(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            survey = self.surveys[0]
            _submission_time = parse_datetime("2013-02-18 15:54:01Z")
            self._make_submission(
                os.path.join(
                    settings.PROJECT_ROOT,
                    "apps",
                    "main",
                    "tests",
                    "fixtures",
                    "transportation",
                    "instances",
                    survey,
                    survey + ".xml",
                ),
                forced_submission_time=_submission_time,
            )

            view = XFormViewSet.as_view({"get": "retrieve"})

            data = {"remove_group_name": True}
            request = self.factory.get("/", data=data, **self.extra)
            request.META["HTTP_HOST"] = "example.com"
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            headers = dict(response.items())
            self.assertEqual(headers["Content-Type"], "application/csv")
            content_disposition = headers["Content-Disposition"]
            filename = filename_from_disposition(content_disposition)
            self.assertIn(GROUPNAME_REMOVED_FLAG, filename)
            basename, ext = os.path.splitext(filename)
            self.assertEqual(ext, '.csv"')

            expected_data = ["n/a"]
            key = "available_transportation_types_to_referral_facility_other"  # noqa
            self._validate_csv_export(response, None, key, expected_data)

            request = self.factory.get("/", **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            headers = dict(response.items())
            self.assertEqual(headers["Content-Type"], "application/csv")
            content_disposition = headers["Content-Disposition"]
            filename = filename_from_disposition(content_disposition)
            self.assertNotIn(GROUPNAME_REMOVED_FLAG, filename)
            basename, ext = os.path.splitext(filename)
            self.assertEqual(ext, '.csv"')

            expected_data = ["n/a"]
            key = "transport/available_transportation_types_to_referral_facility_other"  # noqa
            self._validate_csv_export(response, None, key, expected_data)

    def test_csv_export_no_new_generated(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            survey = self.surveys[0]
            _submission_time = parse_datetime("2013-02-18 15:54:01Z")
            self._make_submission(
                os.path.join(
                    settings.PROJECT_ROOT,
                    "apps",
                    "main",
                    "tests",
                    "fixtures",
                    "transportation",
                    "instances",
                    survey,
                    survey + ".xml",
                ),
                forced_submission_time=_submission_time,
            )
            count = Export.objects.all().count()

            view = XFormViewSet.as_view({"get": "retrieve"})

            request = self.factory.get("/", **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            self.assertEqual(count + 1, Export.objects.all().count())

            headers = dict(response.items())
            self.assertEqual(headers["Content-Type"], "application/csv")
            content_disposition = headers["Content-Disposition"]
            filename = filename_from_disposition(content_disposition)
            self.assertNotIn(GROUPNAME_REMOVED_FLAG, filename)
            basename, ext = os.path.splitext(filename)
            self.assertEqual(ext, '.csv"')

            request = self.factory.get("/", **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            # no new export generated
            self.assertEqual(count + 1, Export.objects.all().count())

            headers = dict(response.items())
            self.assertEqual(headers["Content-Type"], "application/csv")
            content_disposition = headers["Content-Disposition"]
            filename = filename_from_disposition(content_disposition)
            self.assertNotIn(GROUPNAME_REMOVED_FLAG, filename)
            basename, ext = os.path.splitext(filename)
            self.assertEqual(ext, '.csv"')

    def test_xform_linked_dataviews(self):
        xlsform_path = os.path.join(
            settings.PROJECT_ROOT, "libs", "tests", "utils", "fixtures", "tutorial.xlsx"
        )

        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        for x in range(1, 9):
            path = os.path.join(
                settings.PROJECT_ROOT,
                "libs",
                "tests",
                "utils",
                "fixtures",
                "tutorial",
                "instances",
                "uuid{}".format(x),
                "submission.xml",
            )
            self._make_submission(path)
            x += 1

        self._create_dataview()

        data = {
            "name": "Another DataView",
            "xform": f"http://testserver/api/v1/forms/{self.xform.pk}",
            "project": f"http://testserver/api/v1/projects/{self.project.pk}",
            "columns": '["name", "age", "gender"]',
            "query": '[{"column":"age","filter":">","value":"50"}]',
        }

        self._create_dataview(data=data)

        view = XFormViewSet.as_view(
            {
                "get": "retrieve",
            }
        )

        formid = self.xform.pk
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=formid)

        self.assertEqual(response.status_code, 200)
        self.assertIn("data_views", response.data)
        self.assertEqual(2, len(response.data["data_views"]))

    def test_delete_xform_also_deletes_linked_dataviews(self):
        """
        Tests that filtered datasets are also soft deleted
        when a form is soft deleted
        """
        # publish form and make submissions
        xlsform_path = os.path.join(
            settings.PROJECT_ROOT, "libs", "tests", "utils", "fixtures", "tutorial.xlsx"
        )
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        for x in range(1, 9):
            path = os.path.join(
                settings.PROJECT_ROOT,
                "libs",
                "tests",
                "utils",
                "fixtures",
                "tutorial",
                "instances",
                "uuid{}".format(x),
                "submission.xml",
            )
            self._make_submission(path)
            x += 1

        # create dataview
        self._create_dataview()
        data = {
            "name": "Another DataView",
            "xform": f"http://testserver/api/v1/forms/{self.xform.pk}",
            "project": f"http://testserver/api/v1/projects/{self.project.pk}",
            "columns": '["name", "age", "gender"]',
            "query": '[{"column":"age","filter":">","value":"50"}]',
        }
        self._create_dataview(data=data)

        # check that dataview exists
        view = XFormViewSet.as_view(
            {
                "get": "retrieve",
            }
        )
        formid = self.xform.pk
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertIn("data_views", response.data)
        self.assertEqual(2, len(response.data["data_views"]))

        # delete xform
        view = XFormViewSet.as_view({"delete": "destroy", "get": "retrieve"})
        request = self.factory.delete("/", **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.data, None)
        self.assertEqual(response.status_code, 204)
        self.xform.refresh_from_db()
        self.assertIsNotNone(self.xform.deleted_at)

        # check that dataview is also soft deleted
        self.data_view.refresh_from_db()
        self.assertIsNotNone(self.data_view.deleted_at)
        self.assertIn("-deleted-at-", self.data_view.name)

    def test_delete_xform_endpoint(self):
        """
        Tests that the delete_xform view soft deletes xforms
        """
        # publish form and make submissions
        xlsform_path = os.path.join(
            settings.PROJECT_ROOT, "libs", "tests", "utils", "fixtures", "tutorial.xlsx"
        )
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        for x in range(1, 9):
            path = os.path.join(
                settings.PROJECT_ROOT,
                "libs",
                "tests",
                "utils",
                "fixtures",
                "tutorial",
                "instances",
                "uuid{}".format(x),
                "submission.xml",
            )
            self._make_submission(path)

        # Make request to delete
        request = self.factory.post("/", **self.extra)
        request.user = self.xform.user
        response = delete_xform(
            request, username=self.xform.user.username, id_string=self.xform.id_string
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.content, b"")
        self.xform.refresh_from_db()
        self.assertIsNotNone(self.xform.deleted_at)

    def test_multitple_enketo_urls(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()

            # an extra obj to induce multiple object exception
            content_type = ContentType.objects.get_for_model(self.xform)

            meta = MetaData(
                content_type=content_type,
                object_id=self.xform.id,
                data_type="enketo_url",
                data_value="http://localtest/enketo_url2",
            )
            meta.save()

            # pylint: disable=no-member
            count = MetaData.objects.filter(
                object_id=self.xform.id, data_type="enketo_url"
            ).count()
            self.assertEqual(2, count)

            # delete cache
            safe_cache_delete(f"{ENKETO_URL_CACHE}{self.xform.pk}")

            view = XFormViewSet.as_view(
                {
                    "get": "retrieve",
                }
            )
            formid = self.xform.pk
            request = self.factory.get("/", **self.extra)
            response = view(request, pk=formid)

            self.assertEqual(response.status_code, 200)
            self.assertIn("enketo_url", response.data)

    def _validate_csv_export(
        self, response, test_file_path, field=None, test_data=None
    ):
        headers = dict(response.items())
        self.assertEqual(headers["Content-Type"], "application/csv")
        content_disposition = headers["Content-Disposition"]
        filename = filename_from_disposition(content_disposition)
        basename, ext = os.path.splitext(filename)
        self.assertEqual(ext, '.csv"')

        content = get_response_content(response)

        if test_data and field:
            reader = csv.DictReader(StringIO(content))
            self.assertEqual([i[field] for i in reader], test_data)
        else:
            with open(test_file_path, encoding="utf-8") as test_file:
                self.assertEqual(content, test_file.read())

    def _get_date_filtered_export(self, query_str):
        view = XFormViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/?query=%s" % query_str, **self.extra)
        response = view(request, pk=self.xform.pk, format="csv")

        self.assertEqual(response.status_code, 200)

        return response

    def test_csv_export_filtered_by_date(self):
        with HTTMock(enketo_mock):
            start_date = datetime(2015, 12, 2, tzinfo=timezone.utc)
            self._make_submission_over_date_range(start_date)

            first_datetime = start_date.strftime(MONGO_STRFTIME)
            second_datetime = start_date + timedelta(days=1, hours=20)

            query_str = (
                '{"_submission_time": {"$gte": "'
                + first_datetime
                + '", "$lte": "'
                + second_datetime.strftime(MONGO_STRFTIME)
                + '"}}'
            )

            count = Export.objects.all().count()
            response = self._get_date_filtered_export(query_str)
            self.assertEqual(count + 1, Export.objects.all().count())

            test_file_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "viewer",
                "tests",
                "fixtures",
                "transportation_filtered_date.csv",
            )

            expected_submission = [
                "2015-12-02T00:00:00+00:00",
                "2015-12-03T00:00:00+00:00",
            ]
            self._validate_csv_export(
                response, test_file_path, "_submission_time", expected_submission
            )

            export = Export.objects.last()
            self.assertIn("query", export.options)
            self.assertEqual(export.options["query"], query_str)

    def test_previous_export_with_date_filter_is_returned(self):
        with HTTMock(enketo_mock):
            start_date = datetime(2015, 12, 2, tzinfo=timezone.utc)
            self._make_submission_over_date_range(start_date)

            first_datetime = start_date.strftime(MONGO_STRFTIME)
            second_datetime = start_date + timedelta(days=1, hours=20)

            query_str = (
                '{"_submission_time": {"$gte": "'
                + first_datetime
                + '", "$lte": "'
                + second_datetime.strftime(MONGO_STRFTIME)
                + '"}}'
            )

            # Generate initial filtered export by date
            self._get_date_filtered_export(query_str)

            count = Export.objects.all().count()

            # request for export again
            self._get_date_filtered_export(query_str)

            # no change in count of exports
            self.assertEqual(count, Export.objects.all().count())

    def test_download_export_with_export_id(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            survey = self.surveys[0]
            _submission_time = parse_datetime("2013-02-18 15:54:01Z")
            self._make_submission(
                os.path.join(
                    settings.PROJECT_ROOT,
                    "apps",
                    "main",
                    "tests",
                    "fixtures",
                    "transportation",
                    "instances",
                    survey,
                    survey + ".xml",
                ),
                forced_submission_time=_submission_time,
            )

            view = XFormViewSet.as_view({"get": "retrieve"})

            request = self.factory.get("/", **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            export = Export.objects.last()

            data = {"export_id": export.pk}
            request = self.factory.get("/", data=data, **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            key = "_uuid"
            expected_data = ["5b2cc313-fc09-437e-8149-fcd32f695d41"]
            self._validate_csv_export(response, None, key, expected_data)

    def test_download_export_with_invalid_export_id(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            self._make_submissions()

            view = XFormViewSet.as_view({"get": "retrieve"})

            request = self.factory.get("/", **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            data = {"export_id": 12131231}
            request = self.factory.get("/", data=data, **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 404)

    def test_normal_export_after_export_with_date_filter(self):
        with HTTMock(enketo_mock):
            start_date = datetime(2015, 12, 2, tzinfo=timezone.utc)
            self._make_submission_over_date_range(start_date)

            first_datetime = start_date.strftime(MONGO_STRFTIME)
            second_datetime = start_date + timedelta(days=1, hours=20)

            query_str = (
                '{"_submission_time": {"$gte": "'
                + first_datetime
                + '", "$lte": "'
                + second_datetime.strftime(MONGO_STRFTIME)
                + '"}}'
            )

            # Generate initial filtered export by date
            self._get_date_filtered_export(query_str)

            count = Export.objects.all().count()

            view = XFormViewSet.as_view({"get": "retrieve"})

            # request for export again
            request = self.factory.get("/", **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            # should create a new export
            self.assertEqual(count + 1, Export.objects.all().count())

    @override_settings(ALLOWED_HOSTS=["*"])
    def test_csv_exports_w_images_link(self):
        with HTTMock(enketo_mock):
            xlsform_path = os.path.join(
                settings.PROJECT_ROOT,
                "libs",
                "tests",
                "utils",
                "fixtures",
                "tutorial.xlsx",
            )

            self._publish_xls_form_to_project(xlsform_path=xlsform_path)
            media_file = "1442323232322.jpg"

            path = os.path.join(
                settings.PROJECT_ROOT,
                "libs",
                "tests",
                "utils",
                "fixtures",
                "tutorial",
                "instances",
                "uuid1",
                media_file,
            )
            with open(path, "rb") as f:
                self._make_submission(
                    os.path.join(
                        settings.PROJECT_ROOT,
                        "libs",
                        "tests",
                        "utils",
                        "fixtures",
                        "tutorial",
                        "instances",
                        "uuid1",
                        "submission.xml",
                    ),
                    media_file=f,
                    forced_submission_time=datetime(2015, 12, 2, tzinfo=timezone.utc),
                )

            attachment_id = Attachment.objects.all().last().pk

            view = XFormViewSet.as_view({"get": "retrieve"})

            data = {"include_images": True}
            # request for export again
            request = self.factory.get("/", data=data, **self.extra)
            request.META["HTTP_HOST"] = "example.com"
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            expected_data = [
                "http://example.com/api/v1/files/{}?"
                "filename=bob/attachments/{}_{}/"
                "1442323232322.jpg".format(
                    attachment_id, self.xform.id, self.xform.id_string
                )
            ]
            key = "photo"
            self._validate_csv_export(response, None, key, expected_data)

            data = {"include_images": False}
            # request for export again
            request = self.factory.get("/", data=data, **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            expected_data = [media_file]
            self._validate_csv_export(response, None, key, expected_data)

    def test_csv_export_with_and_without_labels_only(self):
        with HTTMock(enketo_mock):
            # create a project and form and add a submission to the form
            self._publish_xls_form_to_project()
            survey = self.surveys[0]
            _submission_time = parse_datetime("2013-02-18 15:54:01Z")
            self._make_submission(
                os.path.join(
                    settings.PROJECT_ROOT,
                    "apps",
                    "main",
                    "tests",
                    "fixtures",
                    "transportation",
                    "instances",
                    survey,
                    survey + ".xml",
                ),
                forced_submission_time=_submission_time,
            )

            view = XFormViewSet.as_view({"get": "retrieve"})

            # export the sumbitted data as csv
            request = self.factory.get("/", **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            expected_data = ["n/a"]
            key = "transport/available_transportation_types_to_referral_facility_other"  # noqa
            self._validate_csv_export(response, None, key, expected_data)

            # export submitted data with include_labels_only and
            # remove_group_name set to true
            data = {"include_labels_only": True, "remove_group_name": True}
            request = self.factory.get("/", data=data, **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)
            expected_data = ["n/a"]
            key = "Is ambulance available daily or weekly?"
            self._validate_csv_export(response, None, key, expected_data)

            # assert that the next request without the options doesn't result
            # to the same result as the previous result
            request = self.factory.get("/", **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            with self.assertRaises(KeyError):
                self._validate_csv_export(response, None, key, expected_data)

    @override_settings(GOOGLE_EXPORT=True)
    def test_xform_gsheet_exports_disabled_sync_mode(self):
        xlsform_path = os.path.join(
            settings.PROJECT_ROOT, "libs", "tests", "utils", "fixtures", "tutorial.xlsx"
        )

        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        for x in range(1, 9):
            path = os.path.join(
                settings.PROJECT_ROOT,
                "libs",
                "tests",
                "utils",
                "fixtures",
                "tutorial",
                "instances",
                "uuid{}".format(x),
                "submission.xml",
            )
            self._make_submission(path)
            x += 1

        view = XFormViewSet.as_view(
            {
                "get": "retrieve",
            }
        )

        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.xform.pk, format="gsheets")

        text_response = '{"details": "Sheets export only supported in async mode"}'
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data, text_response)

    @flaky
    def test_sav_zip_export_long_variable_length(self):
        self._publish_xls_form_to_project()
        survey = self.surveys[0]
        _submission_time = parse_datetime("2013-02-18 15:54:01Z")
        self._make_submission(
            os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "instances",
                survey,
                survey + ".xml",
            ),
            forced_submission_time=_submission_time,
        )

        view = XFormViewSet.as_view({"get": "retrieve"})

        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.xform.pk, format="savzip")
        self.assertEqual(response.status_code, 200)

    def test_xform_version_count(self):
        self._publish_xls_form_to_project()

        self._make_submissions()

        view = XFormViewSet.as_view(
            {
                "get": "retrieve",
            }
        )

        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.xform.pk)

        self.assertIn("form_versions", response.data)
        self.assertEqual(response.data["form_versions"][0].get("total"), 4)

        # soft delete an instance
        instance = self.xform.instances.last()
        instance.set_deleted()

        # delete cache
        safe_cache_delete(f"{XFORM_DATA_VERSIONS}{self.xform.pk}")

        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.xform.pk)

        self.assertIn("form_versions", response.data)
        self.assertEqual(response.data["form_versions"][0].get("total"), 3)

    def test_readonly_no_download_role_not_changed_by_metapermissions(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            alice_data = {"username": "alice", "email": "alice@localhost.com"}
            frankline_data = {
                "username": "frankline",
                "email": "frankline@localhost.com",
            }
            alice_profile = self._create_user_profile(alice_data)
            frankline_profile = self._create_user_profile(frankline_data)

            view = ProjectViewSet.as_view({"post": "share"})
            alice_perms = {"username": "alice", "role": "readonly-no-download"}
            frankline_perms = {"username": "frankline", "role": "readonly"}
            alice_request = self.factory.post("/", data=alice_perms, **self.extra)
            frankline_request = self.factory.post(
                "/", data=frankline_perms, **self.extra
            )
            response = view(alice_request, pk=self.xform.project.id)
            self.assertEqual(response.status_code, 204)
            response = view(frankline_request, pk=self.xform.project.id)
            self.assertEqual(response.status_code, 204)

            # confirm metadata for the xform to be the default
            self.assertEqual(
                "editor|dataentry|readonly",
                self.xform.metadata_set.get(data_type="xform_meta_perms").data_value,
            )

            self.assertEqual(
                get_xform_users(self.xform)[alice_profile.user]["role"],
                "readonly-no-download",
            )
            self.assertEqual(
                get_xform_users(self.xform)[frankline_profile.user]["role"],
                "readonly",
            )

            # change metadata
            data_value = "editor-minor|dataentry|readonly-no-download"
            create_xform_meta_permissions(data_value, self.xform)
            self.assertEqual(
                get_xform_users(self.xform)[alice_profile.user]["role"],
                "readonly-no-download",
            )
            self.assertEqual(
                get_xform_users(self.xform)[frankline_profile.user]["role"],
                "readonly-no-download",
            )

            # change metadata
            data_value = "editor-minor|dataentry|readonly"
            create_xform_meta_permissions(data_value, self.xform)
            self.assertEqual(
                get_xform_users(self.xform)[alice_profile.user]["role"],
                "readonly-no-download",
            )
            self.assertEqual(
                get_xform_users(self.xform)[frankline_profile.user]["role"],
                "readonly",
            )

    def test_share_auto_xform_meta_perms(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            alice_data = {"username": "alice", "email": "alice@localhost.com"}
            alice_profile = self._create_user_profile(alice_data)

            view = XFormViewSet.as_view({"post": "share"})
            formid = self.xform.pk

            data_value = "editor-minor|dataentry|readonly-no-download"

            MetaData.xform_meta_permission(self.xform, data_value=data_value)

            for role_class in ROLES_ORDERED:
                data = {"username": "alice", "role": role_class.name}
                request = self.factory.post("/", data=data, **self.extra)
                response = view(request, pk=formid)

                self.assertEqual(response.status_code, 204)

                if role_class in [
                    EditorNoDownload,
                    EditorRole,
                    EditorMinorRole,
                ]:
                    self.assertFalse(
                        EditorRole.user_has_role(alice_profile.user, self.xform)
                    )
                    self.assertTrue(
                        EditorMinorRole.user_has_role(alice_profile.user, self.xform)
                    )

                elif role_class in [
                    DataEntryRole,
                    DataEntryMinorRole,
                    DataEntryOnlyRole,
                ]:
                    self.assertTrue(
                        DataEntryRole.user_has_role(alice_profile.user, self.xform)
                    )
                elif role_class in [ReadOnlyRole, ReadOnlyRoleNoDownload]:
                    self.assertTrue(
                        ReadOnlyRoleNoDownload.user_has_role(
                            alice_profile.user, self.xform
                        )
                    )

                else:
                    self.assertTrue(
                        role_class.user_has_role(alice_profile.user, self.xform)
                    )

    def test_csv_export_with_meta_perms(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()

            for survey in self.surveys:
                _submission_time = parse_datetime("2013-02-18 15:54:01Z")
                self._make_submission(
                    os.path.join(
                        settings.PROJECT_ROOT,
                        "apps",
                        "main",
                        "tests",
                        "fixtures",
                        "transportation",
                        "instances",
                        survey,
                        survey + ".xml",
                    ),
                    forced_submission_time=_submission_time,
                )

            alice_data = {"username": "alice", "email": "alice@localhost.com"}
            alice_profile = self._create_user_profile(alice_data)

            data_value = "editor|dataentry-minor|readonly-no-download"
            MetaData.xform_meta_permission(self.xform, data_value=data_value)

            DataEntryMinorRole.add(alice_profile.user, self.xform)

            for i in self.xform.instances.all()[:2]:
                i.user = alice_profile.user
                i.save()

            view = XFormViewSet.as_view({"get": "retrieve"})

            alices_extra = {
                "HTTP_AUTHORIZATION": "Token %s" % alice_profile.user.auth_token.key
            }

            request = self.factory.get("/", **alices_extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            headers = dict(response.items())
            self.assertEqual(headers["Content-Type"], "application/csv")
            content_disposition = headers["Content-Disposition"]
            filename = filename_from_disposition(content_disposition)
            basename, ext = os.path.splitext(filename)
            self.assertEqual(ext, '.csv"')

            expected_data = ["alice", "alice"]
            key = "_submitted_by"
            self._validate_csv_export(response, None, key, expected_data)

            DataEntryOnlyRole.add(alice_profile.user, self.xform)

            request = self.factory.get("/", **alices_extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 403)

    def test_csv_export_cache(self):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            self._make_submissions()

            count = Export.objects.all().count()

            view = XFormViewSet.as_view({"get": "retrieve"})

            data = {"export_type": "csv", "win_excel_utf8": False}

            request = self.factory.get("/", data=data, **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            # should generate new
            self.assertEqual(count + 1, Export.objects.all().count())

            survey = self.surveys[0]
            self._make_submission(
                os.path.join(
                    settings.PROJECT_ROOT,
                    "apps",
                    "main",
                    "tests",
                    "fixtures",
                    "transportation",
                    "instances",
                    survey,
                    survey + ".xml",
                )
            )

            data = {"export_type": "csv", "win_excel_utf8": True}

            request = self.factory.get("/", data=data, **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            # changed options, should generate new
            self.assertEqual(count + 2, Export.objects.all().count())

            data = {"export_type": "csv", "win_excel_utf8": False}

            request = self.factory.get("/", data=data, **self.extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            # reused options, should generate new with new submission
            self.assertEqual(count + 3, Export.objects.all().count())

    def test_created_by_field_on_cloned_forms(self):
        """
        Test that the created by field is not empty for cloned forms
        """
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view({"post": "clone"})
            alice_data = {"username": "alice", "email": "alice@localhost.com"}
            alice_profile = self._create_user_profile(alice_data)
            count = XForm.objects.count()

            data = {"username": "alice"}
            formid = self.xform.pk
            ManagerRole.add(self.user, alice_profile)
            request = self.factory.post("/", data=data, **self.extra)
            response = view(request, pk=formid)
            self.assertTrue(self.user.has_perm("can_add_xform", alice_profile))
            self.assertEqual(response.status_code, 201)
            self.assertEqual(count + 1, XForm.objects.count())
            cloned_form = XForm.objects.last()
            self.assertEqual(cloned_form.created_by.username, "alice")

    def test_xlsx_import(self):
        """Ensure XLSX imports work as expected and dates are formatted correctly"""
        with HTTMock(enketo_mock):
            xls_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "double_image_form.xlsx",
            )
            self._publish_xls_form_to_project(xlsform_path=xls_path)
            view = XFormViewSet.as_view({"post": "data_import"})
            xls_import = fixtures_path("double_image_field_form_data.xlsx")
            post_data = {"xls_file": xls_import}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = view(request, pk=self.xform.id)

            # check that date columns are formatted correctly
            self.assertEqual(
                self.xform.instances.values("json___submission_time")[::1],
                [
                    {"json___submission_time": "2023-02-03T10:27:41+00:00"},
                    {"json___submission_time": "2023-02-03T10:27:42+00:00"},
                    {"json___submission_time": "2023-03-13T08:42:57+00:00"},
                ],
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.data.get("additions"), 3)
            self.assertEqual(response.data.get("updates"), 0)

    def test_xls_import(self):
        with HTTMock(enketo_mock):
            xls_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "tutorial.xlsx",
            )
            self._publish_xls_form_to_project(xlsform_path=xls_path)
            view = XFormViewSet.as_view({"post": "data_import"})
            xls_import = fixtures_path("good.xlsx")

            post_data = {"xls_file": xls_import}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = view(request, pk=self.xform.id)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.data.get("additions"), 9)
            self.assertEqual(response.data.get("updates"), 0)

    def test_csv_xls_import_errors(self):
        with HTTMock(enketo_mock):
            xls_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "tutorial.xlsx",
            )
            self._publish_xls_form_to_project(xlsform_path=xls_path)
            view = XFormViewSet.as_view({"post": "data_import"})

            csv_import = fixtures_path("good.csv")
            xls_import = fixtures_path("good.xlsx")

            post_data = {"xls_file": csv_import}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = view(request, pk=self.xform.id)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data.get("error"), "xls_file not an excel file")

            post_data = {"csv_file": xls_import}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = view(request, pk=self.xform.id)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data.get("error"), "csv_file not a csv file")

    @override_settings(TIME_ZONE="UTC")
    def test_get_single_registration_form(self):
        """Response a for an XForm contributing entities is correct"""
        # Publish registration form
        xform = self._publish_registration_form(self.user)
        view = XFormViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=xform.pk)
        self.assertEqual(response.status_code, 200)
        entity_list = EntityList.objects.get(name="trees")
        self.assertEqual(
            response.data["contributes_entities_to"],
            {
                "id": entity_list.pk,
                "name": "trees",
                "is_active": True,
            },
        )

    @override_settings(TIME_ZONE="UTC")
    def test_get_list_registration_form(self):
        """Getting a list of registration forms is correct"""
        # Publish registration form
        self._publish_registration_form(self.user)
        view = XFormViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        entity_list = EntityList.objects.get(name="trees")
        self.assertEqual(
            response.data[0]["contributes_entities_to"],
            {
                "id": entity_list.pk,
                "name": "trees",
                "is_active": True,
            },
        )

    @override_settings(TIME_ZONE="UTC")
    def test_get_single_follow_up_form(self):
        """Response a for an XForm consuming entities is correct"""
        self._project_create()
        entity_list = EntityList.objects.create(name="trees", project=self.project)
        xform = self._publish_follow_up_form(self.user, self.project)
        view = XFormViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=xform.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["consumes_entities_from"],
            [
                {
                    "id": entity_list.pk,
                    "name": "trees",
                    "is_active": True,
                }
            ],
        )

    @override_settings(TIME_ZONE="UTC")
    def test_get_list_follow_up_form(self):
        """Getting a list of follow up forms is correct"""
        # Publish registration form
        self._project_create()
        entity_list = EntityList.objects.create(name="trees", project=self.project)
        self._publish_follow_up_form(self.user, self.project)
        view = XFormViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        entity_list = EntityList.objects.get(name="trees")
        self.assertEqual(
            response.data[0]["consumes_entities_from"],
            [
                {
                    "id": entity_list.pk,
                    "name": "trees",
                    "is_active": True,
                }
            ],
        )

    @patch("onadata.libs.serializers.xform_serializer.encrypt_xform")
    def test_enable_kms_encryption(self, mock_encrypt_xform):
        """Enabling KMS encryption works."""
        self._publish_transportation_form()
        self.view = XFormViewSet.as_view({"patch": "partial_update"})

        request = self.factory.patch(
            "/", data={"enable_kms_encryption": True}, **self.extra
        )
        response = self.view(request, pk=self.xform.id)
        self.assertEqual(response.status_code, 200)

        mock_encrypt_xform.assert_called_once_with(self.xform, encrypted_by=self.user)

        # Encryption error messages are captured
        mock_encrypt_xform.side_effect = EncryptionError(
            "Encryption failed due to missing key."
        )

        request = self.factory.patch(
            "/", data={"enable_kms_encryption": True}, **self.extra
        )
        response = self.view(request, pk=self.xform.id)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Encryption failed due to missing key", str(response.data))

        # Already encrypted form is not encrypted again
        mock_encrypt_xform.reset_mock()
        mock_encrypt_xform.side_effect = None
        self.xform.public_key = "fake-public-key"
        self.xform.save()
        self.xform.refresh_from_db()

        self.assertTrue(self.xform.encrypted)

        request = self.factory.patch(
            "/", data={"enable_kms_encryption": True}, **self.extra
        )
        response = self.view(request, pk=self.xform.id)
        self.assertEqual(response.status_code, 200)

        mock_encrypt_xform.assert_not_called()

    @patch("onadata.libs.serializers.xform_serializer.disable_xform_encryption")
    def test_disable_kms_encryption(self, mock_disable_enc):
        """Disabling KMS encryption works."""
        self._publish_transportation_form()
        self.xform.public_key = "fake-public-key"
        self.xform.save()

        self.view = XFormViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/", data={"enable_kms_encryption": False}, **self.extra
        )
        response = self.view(request, pk=self.xform.id)

        self.assertEqual(response.status_code, 200)
        mock_disable_enc.assert_called_once_with(self.xform, disabled_by=self.user)

        # Encryption error messages are captured
        mock_disable_enc.side_effect = EncryptionError("XForm already has submissions.")

        request = self.factory.patch(
            "/", data={"enable_kms_encryption": False}, **self.extra
        )
        response = self.view(request, pk=self.xform.id)

        self.assertEqual(response.status_code, 400)
        self.assertIn("XForm already has submissions", str(response.data))

        # Unencrypted form is ignored
        mock_disable_enc.reset_mock()
        mock_disable_enc.side_effect = None
        self.xform.delete()
        self._publish_transportation_form()

        self.view = XFormViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/", data={"enable_kms_encryption": False}, **self.extra
        )
        response = self.view(request, pk=self.xform.id)

        self.assertEqual(response.status_code, 200)
        mock_disable_enc.assert_not_called()

    def test_retrive_kms_encrypted_form(self):
        """Retrieving a KMS enecrypted form is correct."""
        self._publish_transportation_form()
        self.xform.public_key = "fake-public-key"
        self.xform.encrypted = True
        self.xform.is_managed = True
        self.xform.save()

        self.view = XFormViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.xform.id)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_managed"])

    def test_retrieve_managed_form(self):
        """Retrieving a managed form is correct."""
        self._publish_transportation_form()
        self.xform.is_managed = True
        self.xform.save()

        self.view = XFormViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.xform.id)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data["num_of_pending_decryption_submissions"], 0)


class ExportAsyncTestCase(XFormViewSetBaseTestCase):
    """Tests for exporting form data asynchronously"""

    def _google_credentials_mock(self):
        """Returns a mock of a Google Credentials instance"""

        class GoogleCredentialsMock:
            def to_json(self):
                return {
                    "refresh_token": "refresh-token",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "client_id": "client-id",
                    "client_secret": "client-secret",
                    "scopes": ["https://www.googleapis.com/auth/drive.file"],
                    "expiry": datetime(2016, 8, 18, 12, 43, 30, 316792),
                }

        return GoogleCredentialsMock()

    def setUp(self):
        super().setUp()

        self.view = XFormViewSet.as_view({"get": "export_async"})

    def test_authentication(self):
        """Authentication is required"""
        self._publish_xls_form_to_project()
        request = self.factory.get("/")
        response = self.view(request, pk=self.xform.pk)
        self.assertEqual(response.status_code, 404)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch("onadata.libs.utils.api_export_tools.AsyncResult")
    def test_export_form_data_async(self, async_result):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view(
                {
                    "get": "export_async",
                }
            )
            formid = self.xform.pk

            for format in ["xlsx", "osm", "csv"]:
                request = self.factory.get("/", data={"format": format}, **self.extra)
                response = view(request, pk=formid)
                self.assertIsNotNone(response.data)
                self.assertEqual(response.status_code, 202)
                self.assertTrue("job_uuid" in response.data)
                task_id = response.data.get("job_uuid")
                get_data = {"job_uuid": task_id}
                request = self.factory.get("/", data=get_data, **self.extra)
                response = view(request, pk=formid)

                self.assertTrue(async_result.called)
                self.assertEqual(response.status_code, 202)
                export = Export.objects.get(task_id=task_id)
                self.assertTrue(export.is_successful)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch("onadata.libs.utils.api_export_tools.AsyncResult")
    def test_export_zip_async(self, async_result):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            self._make_submissions()
            form_view = XFormViewSet.as_view(
                {
                    "get": "retrieve",
                }
            )
            export_async_view = XFormViewSet.as_view(
                {
                    "get": "export_async",
                }
            )
            formid = self.xform.pk
            fmt = "zip"

            request = self.factory.get("/", data={"format": fmt}, **self.extra)
            response = export_async_view(request, pk=formid)
            self.assertIsNotNone(response.data)
            self.assertEqual(response.status_code, 202)
            self.assertTrue("job_uuid" in response.data)
            task_id = response.data.get("job_uuid")
            get_data = {"job_uuid": task_id}
            request = self.factory.get("/", data=get_data, **self.extra)
            response = export_async_view(request, pk=formid)

            self.assertTrue(async_result.called)
            self.assertEqual(response.status_code, 202)
            export = Export.objects.get(task_id=task_id)
            self.assertTrue(export.is_successful)

            request = self.factory.get("/", **self.extra)
            response = form_view(request, pk=formid, format=fmt)
            self.assertTrue(response.status_code, 200)
            headers = dict(response.items())
            content_disposition = headers["Content-Disposition"]
            filename = filename_from_disposition(content_disposition)
            basename, ext = os.path.splitext(filename)
            self.assertEqual(ext, '.zip"')

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch("onadata.libs.utils.api_export_tools.AsyncResult")
    def test_export_async_connection_error(self, async_result):
        with HTTMock(enketo_mock):
            async_result.side_effect = ConnectionError(
                "Error opening socket: a socket error occurred"
            )
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view(
                {
                    "get": "export_async",
                }
            )
            formid = self.xform.pk
            format = "xlsx"
            request = self.factory.get("/", data={"format": format}, **self.extra)
            response = view(request, pk=formid)
            self.assertIsNotNone(response.data)
            self.assertEqual(response.status_code, 202)
            self.assertTrue("job_uuid" in response.data)
            task_id = response.data.get("job_uuid")
            get_data = {"job_uuid": task_id}
            request = self.factory.get("/", data=get_data, **self.extra)
            response = view(request, pk=formid)

            self.assertTrue(async_result.called)
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.status_text.upper(), "SERVICE UNAVAILABLE")
            self.assertEqual(
                response.data["detail"],
                "Service temporarily unavailable, try again later.",
            )
            export = Export.objects.get(task_id=task_id)
            self.assertTrue(export.is_successful)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch("onadata.libs.utils.api_export_tools.AsyncResult")
    def test_create_xls_report_async(self, async_result):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            self._make_submissions()

            data_value = "template 1|http://xls_server"
            self._add_form_metadata(self.xform, "external_export", data_value)
            # pylint: disable=no-member
            metadata = MetaData.objects.get(
                object_id=self.xform.id, data_type="external_export"
            )
            paths = [
                os.path.join(
                    self.main_directory,
                    "fixtures",
                    "transportation",
                    "instances_w_uuid",
                    s,
                    s + ".xml",
                )
                for s in ["transport_2011-07-25_19-05-36"]
            ]

            self._make_submission(paths[0])
            view = XFormViewSet.as_view(
                {
                    "get": "export_async",
                }
            )
            formid = self.xform.pk
            with HTTMock(external_mock):
                # External export
                request = self.factory.get(
                    "/", data={"format": "xlsx", "meta": metadata.pk}, **self.extra
                )
                response = view(request, pk=formid)

            self.assertIsNotNone(response.data)
            self.assertEqual(response.status_code, 202)
            self.assertTrue("job_uuid" in response.data)

            data = response.data
            get_data = {"job_uuid": data.get("job_uuid")}

            request = self.factory.get("/", data=get_data, **self.extra)
            response = view(request, pk=formid, format="xlsx")
            self.assertTrue(async_result.called)
            self.assertEqual(response.status_code, 202)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch("onadata.libs.utils.api_export_tools.AsyncResult")
    def test_create_xls_report_async_with_data_id(self, async_result):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            self._make_submissions()

            data_value = "template 1|http://xls_server"
            self._add_form_metadata(self.xform, "external_export", data_value)
            # pylint: disable=no-member
            metadata = MetaData.objects.get(
                object_id=self.xform.id, data_type="external_export"
            )
            paths = [
                os.path.join(
                    self.main_directory,
                    "fixtures",
                    "transportation",
                    "instances_w_uuid",
                    s,
                    s + ".xml",
                )
                for s in ["transport_2011-07-25_19-05-36"]
            ]

            self._make_submission(paths[0])
            self.assertEqual(self.response.status_code, 201)

            view = XFormViewSet.as_view(
                {
                    "get": "export_async",
                }
            )
            data = {"meta": metadata.pk, "data_id": self.xform.instances.all()[0].pk}
            formid = self.xform.pk
            request = self.factory.get("/", data=data, **self.extra)
            with HTTMock(external_mock):
                # External export
                request = self.factory.get(
                    "/",
                    data={
                        "format": "xlsx",
                        "meta": metadata.pk,
                        "data_id": self.xform.instances.all()[0].pk,
                    },
                    **self.extra,
                )
                response = view(request, pk=formid)

            self.assertIsNotNone(response.data)
            self.assertEqual(response.status_code, 202)
            self.assertTrue("job_uuid" in response.data)

            data = response.data
            get_data = {"job_uuid": data.get("job_uuid")}

            request = self.factory.get("/", data=get_data, **self.extra)
            response = view(request, pk=formid, format="xlsx")
            self.assertTrue(async_result.called)
            self.assertEqual(response.status_code, 202)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch("onadata.libs.utils.api_export_tools.AsyncResult")
    def test_export_csv_data_async_with_remove_group_name(self, async_result):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()

            view = XFormViewSet.as_view(
                {
                    "get": "export_async",
                }
            )
            formid = self.xform.pk

            request = self.factory.get(
                "/", data={"format": "csv", "remove_group_name": True}, **self.extra
            )
            response = view(request, pk=formid)
            self.assertIsNotNone(response.data)
            self.assertEqual(response.status_code, 202)
            self.assertTrue("job_uuid" in response.data)
            task_id = response.data.get("job_uuid")

            export_pk = Export.objects.all().order_by("pk").reverse()[0].pk

            # metaclaass for mocking results
            job = type(
                str("AsyncResultMock"), (), {"state": "SUCCESS", "result": export_pk}
            )
            async_result.return_value = job

            get_data = {"job_uuid": task_id, "remove_group_name": True}
            request = self.factory.get("/", data=get_data, **self.extra)
            response = view(request, pk=formid)

            export = Export.objects.last()
            self.assertIn(str(export.pk), response.data.get("export_url"))

            self.assertTrue(async_result.called)
            self.assertEqual(response.status_code, 202)
            export = Export.objects.get(task_id=task_id)
            self.assertTrue(export.is_successful)

    @patch("onadata.libs.utils.api_export_tools.AsyncResult")
    def test_export_form_data_async_with_filtered_date(self, async_result):
        with HTTMock(enketo_mock):
            start_date = datetime(2015, 12, 2, tzinfo=timezone.utc)
            self._make_submission_over_date_range(start_date)

            first_datetime = start_date.strftime(MONGO_STRFTIME)
            second_datetime = start_date + timedelta(days=1, hours=20)
            query_str = (
                '{"_submission_time": {"$gte": "'
                + first_datetime
                + '", "$lte": "'
                + second_datetime.strftime(MONGO_STRFTIME)
                + '"}}'
            )
            count = Export.objects.all().count()

            export_view = XFormViewSet.as_view(
                {
                    "get": "export_async",
                }
            )
            formid = self.xform.pk

            for export_format in ["csv"]:
                request = self.factory.get(
                    "/",
                    data={"format": export_format, "query": query_str},
                    **self.extra,
                )
                response = export_view(request, pk=formid)
                self.assertIsNotNone(response.data)
                self.assertEqual(response.status_code, 202)
                self.assertTrue("job_uuid" in response.data)
                self.assertEqual(count + 1, Export.objects.all().count())

                task_id = response.data.get("job_uuid")
                get_data = {"job_uuid": task_id}
                request = self.factory.get("/", data=get_data, **self.extra)
                response = export_view(request, pk=formid)

                self.assertTrue(async_result.called)
                self.assertEqual(response.status_code, 202)
                export = Export.objects.get(task_id=task_id)
                self.assertTrue(export.is_successful)

                export = Export.objects.last()
                self.assertIn("query", export.options)
                self.assertEqual(export.options["query"], query_str)

    @patch("onadata.libs.utils.api_export_tools.AsyncResult")
    def test_export_form_data_async_include_labels(self, async_result):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            self._make_submissions()
            export_view = XFormViewSet.as_view(
                {
                    "get": "export_async",
                }
            )
            form_view = XFormViewSet.as_view(
                {
                    "get": "retrieve",
                }
            )
            formid = self.xform.pk

            for export_format in ["csv"]:
                request = self.factory.get(
                    "/",
                    data={"format": export_format, "include_labels": "true"},
                    **self.extra,
                )
                response = export_view(request, pk=formid)
                self.assertIsNotNone(response.data)
                self.assertEqual(response.status_code, 202)
                self.assertTrue("job_uuid" in response.data)
                task_id = response.data.get("job_uuid")
                get_data = {"job_uuid": task_id}
                request = self.factory.get("/", data=get_data, **self.extra)
                response = export_view(request, pk=formid)

                self.assertTrue(async_result.called)
                self.assertEqual(response.status_code, 202)
                export = Export.objects.get(task_id=task_id)
                self.assertTrue(export.is_successful)
                with default_storage.open(export.filepath, "r") as f:
                    csv_reader = csv.reader(f)
                    # jump over headers first
                    next(csv_reader)
                    labels = next(csv_reader)
                    self.assertIn("Is ambulance available daily or weekly?", labels)

                request = self.factory.get(
                    "/", data={"include_labels": "true"}, **self.extra
                )
                response = form_view(request, pk=formid, format=export_format)
                f = StringIO(
                    "".join([c.decode("utf-8") for c in response.streaming_content])
                )
                csv_reader = csv.reader(f)
                # jump over headers first
                next(csv_reader)
                labels = next(csv_reader)
                self.assertIn("Is ambulance available daily or weekly?", labels)

    @patch("onadata.libs.utils.api_export_tools.AsyncResult")
    def test_export_form_data_async_include_labels_only(self, async_result):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            self._make_submissions()
            export_view = XFormViewSet.as_view(
                {
                    "get": "export_async",
                }
            )
            form_view = XFormViewSet.as_view(
                {
                    "get": "retrieve",
                }
            )
            formid = self.xform.pk

            for export_format in ["csv"]:
                request = self.factory.get(
                    "/",
                    data={"format": export_format, "include_labels_only": "true"},
                    **self.extra,
                )
                response = export_view(request, pk=formid)
                self.assertIsNotNone(response.data)
                self.assertEqual(response.status_code, 202)
                self.assertTrue("job_uuid" in response.data)
                task_id = response.data.get("job_uuid")
                get_data = {"job_uuid": task_id}
                request = self.factory.get("/", data=get_data, **self.extra)
                response = export_view(request, pk=formid)

                self.assertTrue(async_result.called)
                self.assertEqual(response.status_code, 202)
                export = Export.objects.get(task_id=task_id)
                self.assertTrue(export.is_successful)
                with default_storage.open(export.filepath, "r") as f:
                    csv_reader = csv.reader(f)
                    headers = next(csv_reader)
                    self.assertIn("Is ambulance available daily or weekly?", headers)

                request = self.factory.get(
                    "/", data={"include_labels_only": "true"}, **self.extra
                )
                response = form_view(request, pk=formid, format=export_format)
                f = StringIO(
                    "".join([c.decode("utf-8") for c in response.streaming_content])
                )
                csv_reader = csv.reader(f)
                headers = next(csv_reader)
                self.assertIn("Is ambulance available daily or weekly?", headers)

    @override_settings(GOOGLE_EXPORT=True)
    @patch("onadata.libs.utils.api_export_tools._get_google_credential")
    def test_xform_gsheet_exports_authorization_url(self, mock_google_creds):
        redirect_url = "https://google.com/api/example/authorization_url"
        mock_google_creds.return_value = HttpResponseRedirect(redirect_to=redirect_url)

        self._publish_xls_form_to_project()
        self._make_submissions()

        view = XFormViewSet.as_view(
            {
                "get": "export_async",
            }
        )

        data = {"format": "gsheets"}
        request = self.factory.get("/", data=data, **self.extra)
        response = view(request, pk=self.xform.pk)

        self.assertTrue(mock_google_creds.called)

        expected_response = {
            "details": "Google authorization needed",
            "url": redirect_url,
        }

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data, expected_response)

    @override_settings(GOOGLE_EXPORT=False)
    @patch("onadata.libs.utils.api_export_tools._get_google_credential")
    def test_google_exports_setting_false(self, mock_google_creds):
        """Google sheet export not allowed if setting.GOOGLE_EXPORT is false"""
        mock_google_creds.return_value = self._google_credentials_mock()
        self._publish_xls_form_to_project()
        data = {"format": "gsheets"}
        request = self.factory.get("/", data=data, **self.extra)
        response = self.view(request, pk=self.xform.pk)
        expected_response = {"details": "Export format not supported"}
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data, expected_response)

    @patch("onadata.libs.utils.api_export_tools._get_google_credential")
    def test_google_exports_setting_missing(self, mock_google_creds):
        """Google sheet export not allowed if setting.GOOGLE_EXPORT is missing"""
        mock_google_creds.return_value = self._google_credentials_mock()
        self._publish_xls_form_to_project()
        data = {"format": "gsheets"}
        request = self.factory.get("/", data=data, **self.extra)
        response = self.view(request, pk=self.xform.pk)
        expected_response = {"details": "Export format not supported"}
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data, expected_response)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch("onadata.libs.utils.api_export_tools.AsyncResult")
    def test_sav_zip_export_long_variable_length_async(self, async_result):
        self._publish_xls_form_to_project()
        view = XFormViewSet.as_view(
            {
                "get": "export_async",
            }
        )
        formid = self.xform.pk
        request = self.factory.get("/", data={"format": "savzip"}, **self.extra)
        response = view(request, pk=formid)
        self.assertIsNotNone(response.data)
        self.assertEqual(response.status_code, 202)
        self.assertTrue("job_uuid" in response.data)
        task_id = response.data.get("job_uuid")
        get_data = {"job_uuid": task_id}
        request = self.factory.get("/", data=get_data, **self.extra)
        response = view(request, pk=formid)

        self.assertTrue(async_result.called)
        self.assertEqual(response.status_code, 202)
        export = Export.objects.get(task_id=task_id)
        self.assertTrue(export.is_successful)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    @patch("onadata.libs.utils.api_export_tools.AsyncResult")
    def test_pending_export_async(self, async_result):
        with HTTMock(enketo_mock):
            self._publish_xls_form_to_project()
            view = XFormViewSet.as_view(
                {
                    "get": "export_async",
                }
            )
            formid = self.xform.pk
            request = self.factory.get("/", data={"format": "csv"}, **self.extra)
            response = view(request, pk=formid)
            self.assertIsNotNone(response.data)
            self.assertEqual(response.status_code, 202)
            self.assertTrue("job_uuid" in response.data)
            task_id = response.data.get("job_uuid")

            request = self.factory.get("/", data={"format": "csv"}, **self.extra)
            response = view(request, pk=formid)
            self.assertIsNotNone(response.data)
            self.assertEqual(response.status_code, 202)
            self.assertTrue("job_uuid" in response.data)
            task_id_two = response.data.get("job_uuid")

            self.assertEqual(task_id, task_id_two)

            get_data = {"job_uuid": task_id_two}
            request = self.factory.get("/", data=get_data, **self.extra)
            response = view(request, pk=formid)

            self.assertTrue(async_result.called)
            self.assertEqual(response.status_code, 202)
            export = Export.objects.get(task_id=task_id)
            self.assertTrue(export.is_pending)

    def test_export_csvzip_form_data_async(self):
        with HTTMock(enketo_mock):
            xls_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "tutorial.xlsx",
            )
            self._publish_xls_form_to_project(xlsform_path=xls_path)
            view = XFormViewSet.as_view(
                {
                    "get": "export_async",
                }
            )
            formid = self.xform.pk

            request = self.factory.get("/", data={"format": "csvzip"}, **self.extra)
            response = view(request, pk=formid)
            self.assertIsNotNone(response.data)
            self.assertEqual(response.status_code, 202)
            print(response.data)
            # Ensure response is renderable
            response.render()
