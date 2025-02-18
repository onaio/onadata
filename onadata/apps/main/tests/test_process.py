# -*- coding: utf-8 -*-
"""
Test usage process - form publishing and export.
"""

import csv
import fnmatch
import json
import os
import re
from datetime import datetime, timezone
from hashlib import md5
from io import BytesIO
from unittest.mock import patch
from xml.dom import Node

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.test.testcases import SerializeMixin
from django.urls import reverse

import openpyxl
import requests
from defusedxml import minidom
from django_digest.test import Client as DigestClient
from flaky import flaky
from six import iteritems

from onadata.apps.logger.models import XForm
from onadata.apps.logger.models.xform import XFORM_TITLE_LENGTH, _additional_headers
from onadata.apps.logger.xform_instance_parser import clean_and_parse_xml
from onadata.apps.main.models import MetaData
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models.data_dictionary import DataDictionary
from onadata.libs.utils.common_tags import MONGO_STRFTIME
from onadata.libs.utils.common_tools import get_response_content

uuid_regex = re.compile(r'(</instance>.*uuid[^//]+="\')([^\']+)(\'".*)', re.DOTALL)


@flaky()
class TestProcess(TestBase, SerializeMixin):
    """
    Test form publishing processes.
    """

    lockfile = __file__

    loop_str = "loop_over_transport_types_frequency"
    frequency_str = "frequency_to_referral_facility"
    ambulance_key = f"{loop_str}/ambulance/{frequency_str}"
    bicycle_key = f"{loop_str}/bicycle/{frequency_str}"
    other_key = f"{loop_str}/other/{frequency_str}"
    taxi_key = f"{loop_str}/taxi/{frequency_str}"
    transport_ambulance_key = f"transport/{ambulance_key}"
    transport_bicycle_key = f"transport/{bicycle_key}"
    uuid_to_submission_times = {
        "5b2cc313-fc09-437e-8149-fcd32f695d41": "2013-02-14T15:37:21",
        "f3d8dc65-91a6-4d0f-9e97-802128083390": "2013-02-14T15:37:22",
        "9c6f3468-cfda-46e8-84c1-75458e72805d": "2013-02-14T15:37:23",
        "9f0a1508-c3b7-4c99-be00-9b237c26bcbf": "2013-02-14T15:37:24",
    }

    # pylint: disable=unused-argument
    def test_process(self, username=None, password=None):
        """Test usage process."""
        self._publish_xls_file()
        self._check_formlist()
        self._download_xform()
        self._make_submissions()
        self._update_dynamic_data()
        self._check_csv_export()
        self._check_delete()

    def _update_dynamic_data(self):
        """
        Update stuff like submission time so we can compare within out fixtures
        """
        for uuid, submission_time in iteritems(self.uuid_to_submission_times):
            i = self.xform.instances.get(uuid=uuid)
            i.date_created = datetime.strptime(submission_time, MONGO_STRFTIME).replace(
                tzinfo=timezone.utc
            )
            i.json = i.get_full_dict()
            i.save()

    def test_uuid_submit(self):
        """Test submission with uuid included."""
        self._publish_xls_file()
        survey = "transport_2011-07-25_19-05-49"
        path = os.path.join(
            self.this_directory,
            "fixtures",
            "transportation",
            "instances",
            survey,
            survey + ".xml",
        )
        with open(path, encoding="utf-8") as f:
            post_data = {"xml_submission_file": f, "uuid": self.xform.uuid}
            url = "/submission"
            # pylint: disable=attribute-defined-outside-init
            self.response = self.client.post(url, post_data)

    def test_publish_xlsx_file(self):
        """Test publishing an XLSX file."""
        self._publish_xlsx_file()

    def test_publish_xlsx_file_with_external_choices(self):
        """Test publishing an XLSX file with external choices"""
        self._publish_xlsx_file_with_external_choices()

    def test_public_xlsx_file_with_external_choices_with_empty_row(self):
        """
        Test that a form with empty spaces in list_name column is uploaded correctly
        """
        self._publish_xlsx_file_with_external_choices(form_version="v3")

    @patch("onadata.apps.main.forms.requests")
    def test_google_url_upload(self, mock_requests):
        """Test uploading an XLSForm from a Google Docs SpreadSheet URL."""
        if self._internet_on(url="http://google.com"):
            xls_url = (
                "https://docs.google.com/spreadsheet/pub?"
                "key=0AvhZpT7ZLAWmdDhISGhqSjBOSl9XdXd5SHZHUUE2RFE&output=xlsx"
            )
            pre_count = XForm.objects.count()

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
                mock_response = requests.Response()
                mock_response.status_code = 200
                mock_response.headers = {
                    "content-type": (
                        "application/vnd.openxmlformats-"
                        "officedocument.spreadsheetml.sheet"
                    ),
                    "Content-Disposition": (
                        'attachment; filename="transportation.'
                        "xlsx\"; filename*=UTF-8''transportation.xlsx"
                    ),
                }
                mock_requests.head.return_value = mock_response
                # pylint: disable=protected-access
                mock_response._content = xls_file.read()
                mock_requests.get.return_value = mock_response
                response = self.client.post(
                    f"/{self.user.username}/", {"xls_url": xls_url}
                )

                mock_requests.get.assert_called_with(xls_url, timeout=30)
                mock_requests.head.assert_called_with(
                    xls_url, allow_redirects=True, timeout=30
                )
                # make sure publishing the survey worked
                self.assertEqual(response.status_code, 200)
                self.assertEqual(XForm.objects.count(), pre_count + 1)

    @flaky(max_runs=3, min_passes=2)
    @patch("onadata.apps.main.forms.requests")
    def test_url_upload(self, mock_requests):
        """Test uploading an XLSForm from a URL."""
        if self._internet_on(url="http://google.com"):
            xls_url = "https://ona.io/examples/forms/tutorial/form.xlsx"
            pre_count = XForm.objects.count()

            path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation.xlsx",
            )

            # pylint: disable=consider-using-with
            with open(path, "rb") as xls_file:
                mock_response = requests.Response()
                mock_response.status_code = 200
                mock_response.headers = {
                    "content-type": (
                        "application/vnd.openxmlformats-"
                        "officedocument.spreadsheetml.sheet"
                    ),
                    "content-disposition": (
                        'attachment; filename="transportation.'
                        "xlsx\"; filename*=UTF-8''transportation.xlsx"
                    ),
                }
                # pylint: disable=protected-access
                mock_response._content = xls_file.read()
                mock_requests.get.return_value = mock_response

                response = self.client.post(
                    f"/{self.user.username}/", {"xls_url": xls_url}
                )
                mock_requests.get.assert_called_with(xls_url, timeout=30)

                # make sure publishing the survey worked
                self.assertEqual(response.status_code, 200)
                self.assertEqual(XForm.objects.count(), pre_count + 1)

    def test_bad_url_upload(self):
        """Test uploading an XLSForm from a badly formatted URL."""
        xls_url = "formhuborg/pld/forms/transportation_2011_07_25/form.xlsx"
        pre_count = XForm.objects.count()
        response = self.client.post(f"/{self.user.username}/", {"xls_url": xls_url})
        # make sure publishing the survey worked
        self.assertEqual(response.status_code, 200)
        self.assertEqual(XForm.objects.count(), pre_count)

    # This method tests a large number of xls files.
    # create a directory /main/test/fixtures/online_xls
    # containing the files you would like to test.
    # DO NOT CHECK IN PRIVATE XLS FILES!!
    def test_upload_all_xls(self):
        """Test all XLSForms in online_xls folder can upload successfuly."""
        root_dir = os.path.join(self.this_directory, "fixtures", "online_xls")
        if os.path.exists(root_dir):
            success = True
            for root, _sub_folders, filenames in os.walk(root_dir):
                # ignore files that don't end in '.xlsx'
                for filename in fnmatch.filter(filenames, "*.xlsx"):
                    success = self._publish_file(os.path.join(root, filename), False)
                    if success:
                        # delete it so we don't have id_string conflicts
                        if self.xform:
                            self.xform.delete()
                            # pylint: disable=attribute-defined-outside-init
                            self.xform = None
                print(f"finished sub-folder {root}")
            self.assertEqual(success, True)

    # pylint: disable=invalid-name
    def test_url_upload_non_dot_xls_path(self):
        """Test a non .xls URL allows XLSForm upload."""
        if self._internet_on():
            xls_url = "http://formhub.org/formhub_u/forms/tutorial/form.xlsx"
            pre_count = XForm.objects.count()
            response = self.client.post(f"/{self.user.username}", {"xls_url": xls_url})
            # make sure publishing the survey worked
            self.assertEqual(response.status_code, 200)
            self.assertEqual(XForm.objects.count(), pre_count + 1)

    # pylint: disable=invalid-name
    def test_not_logged_in_cannot_upload(self):
        """Test anonymous user cannot upload an XLSForm."""
        path = os.path.join(
            self.this_directory, "fixtures", "transportation", "transportation.xlsx"
        )
        if not path.startswith(f"/{self.user.username}"):
            path = os.path.join(self.this_directory, path)
        with open(path, "rb") as xls_file:
            post_data = {"xls_file": xls_file}
            return self.client.post(f"/{self.user.username}", post_data)

    def _publish_file(self, xls_path, strict=True):
        """
        Return False if not strict and publish fails
        """
        pre_count = XForm.objects.count()
        TestBase._publish_xls_file(self, xls_path)
        # make sure publishing the survey worked
        if XForm.objects.count() != pre_count + 1:
            print(f"\nPublish Failure for file: {xls_path}")
            if strict:
                self.assertEqual(XForm.objects.count(), pre_count + 1)
            else:
                return False
        # pylint: disable=attribute-defined-outside-init
        self.xform = list(XForm.objects.all())[-1]
        return True

    def _publish_xls_file(self, path=None):
        xls_path = os.path.join(
            self.this_directory, "fixtures", "transportation", "transportation.xlsx"
        )
        self._publish_file(xls_path)
        self.assertEqual(self.xform.id_string, "transportation_2011_07_25")

    def _check_formlist(self):
        url = f"/{self.user.username}/formList"
        client = DigestClient()
        client.set_authorization("bob", "bob")
        response = client.get(url)
        # pylint: disable=attribute-defined-outside-init
        self.download_url = (
            f"http://testserver/{self.user.username}/forms/{self.xform.pk}/form.xml"
        )
        md5_hash = md5(self.xform.xml.encode("utf-8")).hexdigest()
        expected_content = f"""<?xml version="1.0" encoding="utf-8"?>
<xforms xmlns="http://openrosa.org/xforms/xformsList"><xform><formID>transportation_2011_07_25</formID><name>transportation_2011_07_25</name><version>2014111</version><hash>md5:{md5_hash}</hash><descriptionText></descriptionText><downloadUrl>{self.download_url}</downloadUrl></xform></xforms>"""  # noqa
        self.assertEqual(response.content.decode("utf-8"), expected_content)
        self.assertTrue(response.has_header("X-OpenRosa-Version"))
        self.assertTrue(response.has_header("Date"))

    def _download_xform(self):
        client = DigestClient()
        client.set_authorization("bob", "bob")
        response = client.get(self.download_url)
        response_doc = minidom.parseString(response.content)

        xml_path = os.path.join(
            self.this_directory, "fixtures", "transportation", "transportation.xml"
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

        response_xml = response_doc.toxml().replace(self.xform.version, "201411120717")
        # check content without UUID
        self.assertEqual(response_xml, expected_doc.toxml())

    def _check_csv_export(self):
        self._check_data_dictionary()
        self._check_data_for_csv_export()
        self._check_group_xpaths_do_not_appear_in_dicts_for_export()
        self._check_csv_export_first_pass()
        self._check_csv_export_second_pass()

    def _check_data_dictionary(self):
        # test to make sure the data dictionary returns the expected headers
        queryset = DataDictionary.objects.filter(user=self.user)
        self.assertEqual(queryset.count(), 1)
        # pylint: disable=attribute-defined-outside-init
        self.data_dictionary = DataDictionary.objects.all()[0]
        with open(
            os.path.join(
                self.this_directory, "fixtures", "transportation", "headers.json"
            ),
            encoding="utf-8",
        ) as f:
            expected_list = json.load(f)
        self.assertEqual(self.data_dictionary.get_headers(), expected_list)

        # test to make sure the headers in the actual csv are as expected
        actual_csv = self._get_csv_()
        with open(
            os.path.join(
                self.this_directory, "fixtures", "transportation", "headers_csv.json"
            ),
            encoding="utf-8",
        ) as f:
            expected_list = json.load(f)
        self.assertEqual(sorted(next(actual_csv)), sorted(expected_list))

    def _check_data_for_csv_export(self):
        data = [
            {
                "available_transportation_types_to_referral_facility/ambulance": True,
                "available_transportation_types_to_referral_facility/bicycle": True,
                self.ambulance_key: "daily",
                self.bicycle_key: "weekly",
            },
            {},
            {
                "available_transportation_types_to_referral_facility/ambulance": True,
                self.ambulance_key: "weekly",
            },
            {
                "available_transportation_types_to_referral_facility/taxi": True,
                "available_transportation_types_to_referral_facility/other": True,
                "available_transportation_types_to_referral_facility_other": "camel",
                self.taxi_key: "daily",
                self.other_key: "other",
            },
        ]
        for d_from_db in self.data_dictionary.get_data_for_excel():
            test_dict = {}
            for k, v in iteritems(d_from_db):
                if (
                    k
                    not in [
                        "_xform_id_string",
                        "meta/instanceID",
                        "_version",
                        "_id",
                        "image1",
                    ]
                ) and v:
                    new_key = k[len("transport/") :]
                    test_dict[new_key] = d_from_db[k]
            self.assertTrue(test_dict in data, (test_dict, data))
            data.remove(test_dict)
        self.assertEqual(data, [])

    def _check_group_xpaths_do_not_appear_in_dicts_for_export(self):
        uuid = "uuid:f3d8dc65-91a6-4d0f-9e97-802128083390"
        instance = self.xform.instances.get(uuid=uuid.split(":")[1])
        expected_dict = {
            "transportation": {
                "meta": {"instanceID": uuid},
                "transport": {
                    "loop_over_transport_types_frequency": {
                        "bicycle": {"frequency_to_referral_facility": "weekly"},
                        "ambulance": {"frequency_to_referral_facility": "daily"},
                    },
                    "available_transportation_types_to_referral_facility": "ambulance bicycle",
                },
            }
        }
        self.assertEqual(instance.get_dict(flat=False), expected_dict)
        expected_dict = {
            "transport/available_transportation_types_to_referral_facility": "ambulance bicycle",
            self.transport_ambulance_key: "daily",
            self.transport_bicycle_key: "weekly",
            "_xform_id_string": "transportation_2011_07_25",
            "_version": "2014111",
            "meta/instanceID": uuid,
        }
        self.assertEqual(instance.get_dict(), expected_dict)

    def _get_csv_(self):
        # todo: get the csv.reader to handle unicode as done here:
        # http://docs.python.org/library/csv.html#examples
        url = reverse(
            "csv_export",
            kwargs={"username": self.user.username, "id_string": self.xform.id_string},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        actual_csv = get_response_content(response)
        actual_lines = actual_csv.split("\n")
        return csv.reader(actual_lines)

    def _check_csv_export_first_pass(self):
        url = reverse(
            "csv_export",
            kwargs={"username": self.user.username, "id_string": self.xform.id_string},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        test_file_path = os.path.join(
            self.this_directory, "fixtures", "transportation", "transportation.csv"
        )
        self._test_csv_response(response, test_file_path)

    # pylint: disable=too-many-locals
    def _check_csv_export_second_pass(self):
        url = reverse(
            "csv_export",
            kwargs={"username": self.user.username, "id_string": self.xform.id_string},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        actual_csv = get_response_content(response)
        actual_lines = actual_csv.split("\n")
        actual_csv = csv.reader(actual_lines)
        headers = next(actual_csv)
        data = [
            {
                "image1": "1335783522563.jpg",
                "meta/instanceID": "uuid:5b2cc313-fc09-437e-8149-fcd32f695d41",
                "_uuid": "5b2cc313-fc09-437e-8149-fcd32f695d41",
                "_submission_time": "2013-02-14T15:37:21+00:00",
                "_tags": "",
                "_notes": "",
                "_version": "2014111",
                "_duration": "",
                "_submitted_by": "bob",
                "_total_media": "1",
                "_media_count": "0",
            },
            {
                "available_transportation_types_to_referral_facility/ambulance": "True",
                "available_transportation_types_to_referral_facility/bicycle": "True",
                self.ambulance_key: "daily",
                self.bicycle_key: "weekly",
                "meta/instanceID": "uuid:f3d8dc65-91a6-4d0f-9e97-802128083390",
                "_uuid": "f3d8dc65-91a6-4d0f-9e97-802128083390",
                "_submission_time": "2013-02-14T15:37:22+00:00",
                "_tags": "",
                "_notes": "",
                "_version": "2014111",
                "_duration": "",
                "_submitted_by": "bob",
                "_total_media": "0",
                "_media_count": "0",
                "_media_all_received": "True",
            },
            {
                "available_transportation_types_to_referral_facility/ambulance": "True",
                self.ambulance_key: "weekly",
                "meta/instanceID": "uuid:9c6f3468-cfda-46e8-84c1-75458e72805d",
                "_uuid": "9c6f3468-cfda-46e8-84c1-75458e72805d",
                "_submission_time": "2013-02-14T15:37:23+00:00",
                "_tags": "",
                "_notes": "",
                "_version": "2014111",
                "_duration": "",
                "_submitted_by": "bob",
                "_total_media": "0",
                "_media_count": "0",
                "_media_all_received": "True",
            },
            {
                "available_transportation_types_to_referral_facility/taxi": "True",
                "available_transportation_types_to_referral_facility/other": "True",
                "available_transportation_types_to_referral_facility_other": "camel",
                self.other_key: "other",
                self.taxi_key: "daily",
                "meta/instanceID": "uuid:9f0a1508-c3b7-4c99-be00-9b237c26bcbf",
                "_uuid": "9f0a1508-c3b7-4c99-be00-9b237c26bcbf",
                "_submission_time": "2013-02-14T15:37:24+00:00",
                "_tags": "",
                "_notes": "",
                "_version": "2014111",
                "_duration": "",
                "_submitted_by": "bob",
                "_total_media": "0",
                "_media_count": "0",
                "_media_all_received": "True",
            },
        ]

        additional_headers = _additional_headers() + [
            "_id",
            "_date_modified",
        ]
        for row, expected_dict in zip(actual_csv, data):
            test_dict = {}
            row_dict = dict(zip(headers, row))
            for k, v in iteritems(row_dict):
                if not (v in ["n/a", "False"] or k in additional_headers):
                    test_dict[k] = v
            this_list = []
            for k, v in expected_dict.items():
                if k in ["image1", "meta/instanceID"] or k.startswith("_"):
                    this_list.append((k, v))
                else:
                    this_list.append(("transport/" + k, v))
            self.assertEqual(test_dict, dict(this_list))

    def test_xlsx_export_content(self):
        """Test publish and export XLS content."""
        self._publish_xls_file()
        self._make_submissions()
        self._update_dynamic_data()
        self._check_xlsx_export()

    def _check_xlsx_export(self):
        xlsx_export_url = reverse(
            "xlsx_export",
            kwargs={"username": self.user.username, "id_string": self.xform.id_string},
        )
        response = self.client.get(xlsx_export_url)
        expected_xls = openpyxl.open(
            filename=os.path.join(
                self.this_directory,
                "fixtures",
                "transportation",
                "transportation_export.xlsx",
            ),
            data_only=True,
        )
        content = get_response_content(response, decode=False)
        actual_xls = openpyxl.load_workbook(filename=BytesIO(content))
        actual_sheet = actual_xls["data"]
        expected_sheet = expected_xls["transportation"]
        # check headers
        self.assertEqual(list(actual_sheet.values)[0], list(expected_sheet.values)[0])

        # check cell data
        self.assertEqual(
            len(list(actual_sheet.columns)), len(list(expected_sheet.columns))
        )
        self.assertEqual(len(list(actual_sheet.rows)), len(list(expected_sheet.rows)))
        for i in range(1, len(list(actual_sheet.columns))):
            i = 1
            actual_row = list(list(actual_sheet.values)[i])
            expected_row = list(list(expected_sheet.values)[i])
            # remove _id from result set, varies depending on the database
            del actual_row[24]
            del expected_row[24]
            self.assertEqual(actual_row, expected_row)

    def _check_delete(self):
        self.assertEqual(self.user.xforms.count(), 1)
        self.user.xforms.all()[0].delete()
        self.assertEqual(self.user.xforms.count(), 0)

    def test_405_submission(self):
        url = reverse("submissions")
        response = self.client.get(url)
        self.assertContains(response, 'Method "GET" not allowed', status_code=405)

    # pylint: disable=invalid-name
    def test_publish_bad_xls_with_unicode_in_error(self):
        """
        Publish an xls where the error has a unicode character

        Return a 200, thus showing a readable error to the user
        """
        self._create_user_and_login()
        path = os.path.join(
            self.this_directory, "fixtures", "form_with_unicode_in_relevant_column.xlsx"
        )
        with open(path, "rb") as xls_file:
            post_data = {"xls_file": xls_file}
            response = self.client.post(f"/{self.user.username}/", post_data)
            self.assertEqual(response.status_code, 200)

    def test_metadata_file_hash(self):
        """Test a metadata file hash is generated."""
        self._publish_transportation_form()
        src = os.path.join(
            self.this_directory, "fixtures", "transportation", "screenshot.png"
        )
        with open(src, "rb") as screenshot_file:
            upload_file = UploadedFile(file=screenshot_file, content_type="image/png")
            count = MetaData.objects.count()
            MetaData.media_upload(self.xform, upload_file)
            # assert successful insert of new metadata record
            self.assertEqual(MetaData.objects.count(), count + 1)
            metadata = MetaData.objects.get(
                object_id=self.xform.id, data_value="screenshot.png"
            )
            # assert checksum string has been generated, hash length > 1
            self.assertTrue(len(metadata.hash) > 16)

    # pylint: disable=invalid-name
    def test_uuid_injection_in_cascading_select(self):
        """
        UUID is injected in the right instance for forms with cascading select
        """
        pre_count = XForm.objects.count()
        xls_path = os.path.join(
            self.this_directory,
            "fixtures",
            "cascading_selects",
            "new_cascading_select.xlsx",
        )
        TestBase._publish_xls_file(self, xls_path)
        post_count = XForm.objects.count()
        self.assertEqual(post_count, pre_count + 1)
        xform = XForm.objects.latest("date_created")

        # check that the uuid is within the main instance/
        # the one without an id attribute
        xml = clean_and_parse_xml(xform.xml)

        # check for instance nodes that are direct children of the model node
        model_node = xml.getElementsByTagName("model")[0]
        instance_nodes = [
            node
            for node in model_node.childNodes
            if node.nodeType == Node.ELEMENT_NODE
            and node.tagName.lower() == "instance"
            and not node.hasAttribute("id")
        ]
        self.assertEqual(len(instance_nodes), 1)
        instance_node = instance_nodes[0]

        # get the first element whose id attribute is equal to our form's
        # id_string
        form_nodes = [
            node
            for node in instance_node.childNodes
            if node.nodeType == Node.ELEMENT_NODE
            and node.getAttribute("id") == xform.id_string
        ]
        form_node = form_nodes[0]

        # find the formhub node that has a uuid child node
        formhub_nodes = form_node.getElementsByTagName("formhub")
        self.assertEqual(len(formhub_nodes), 1)
        uuid_nodes = formhub_nodes[0].getElementsByTagName("uuid")
        self.assertEqual(len(uuid_nodes), 1)

        # check for the calculate bind
        calculate_bind_nodes = [
            node
            for node in model_node.childNodes
            if node.nodeType == Node.ELEMENT_NODE
            and node.tagName == "bind"
            and node.getAttribute("nodeset") == "/data/formhub/uuid"
        ]
        self.assertEqual(len(calculate_bind_nodes), 1)
        calculate_bind_node = calculate_bind_nodes[0]
        self.assertEqual(
            calculate_bind_node.getAttribute("calculate"), f"'{xform.uuid}'"
        )

    def test_csv_publishing(self):
        """Test publishing a CSV XLSForm."""
        csv_text = "\n".join(
            [
                "survey,,",
                ",type,name,label",
                ',text,whatsyourname,"What is your name?"',
                "choices,,",
            ]
        )
        url = reverse("user_profile", kwargs={"username": self.user.username})
        num_xforms = XForm.objects.count()
        params = {"text_xls_form": csv_text}
        self.client.post(url, params)
        self.assertEqual(XForm.objects.count(), num_xforms + 1)

    # pylint: disable=invalid-name
    def test_truncate_xform_title_to_255(self):
        """Test the XLSForm title is truncated at 255 characters."""
        self._publish_transportation_form()
        title = "a" * (XFORM_TITLE_LENGTH + 1)
        groups = re.match(
            r"(.+<h:title>)([^<]+)(</h:title>.*)", self.xform.xml, re.DOTALL
        ).groups()
        self.xform.xml = f"{groups[0]}{title}{groups[2]}"
        self.xform.title = title
        self.xform.save()
        self.assertEqual(self.xform.title, "a" * XFORM_TITLE_LENGTH)

    # pylint: disable=invalid-name
    def test_multiple_submissions_by_different_users(self):
        """
        Two users publishing the same form breaks the CSV export.
        """
        TestProcess.test_process(self)
        TestProcess.test_process(self, "doug", "doug")
