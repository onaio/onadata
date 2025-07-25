# -*- coding: utf-8 -*-
"""
TestBase - a TestCase base class.
"""

from __future__ import unicode_literals

import base64
import csv
import os
import re
import socket
import subprocess
import warnings
from io import StringIO
from tempfile import NamedTemporaryFile

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.test import RequestFactory, TransactionTestCase
from django.test.client import Client
from django.utils import timezone

from django_digest.test import Client as DigestClient
from django_digest.test import DigestAuth
from pyxform.builder import create_survey_element_from_dict
from rest_framework.test import APIRequestFactory
from six.moves.urllib.error import URLError
from six.moves.urllib.request import urlopen

from onadata.apps.api.models import OrganizationProfile
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.logger.models import Instance, MergedXForm, XForm, XFormVersion
from onadata.apps.logger.views import submission
from onadata.apps.logger.xform_instance_parser import clean_and_parse_xml
from onadata.apps.main.models import UserProfile
from onadata.apps.viewer.models import DataDictionary
from onadata.libs.test_utils.pyxform_test_case import PyxformMarkdown
from onadata.libs.utils.common_tools import (
    filename_from_disposition,
    get_response_content,
)
from onadata.libs.utils.user_auth import get_user_default_project

# pylint: disable=invalid-name
User = get_user_model()

warnings.simplefilter("ignore")


# pylint: disable=too-many-instance-attributes
class TestBase(PyxformMarkdown, TransactionTestCase):
    """
    A TransactionTestCase base class for test modules.
    """

    maxDiff = None
    surveys = [
        "transport_2011-07-25_19-05-49",
        "transport_2011-07-25_19-05-36",
        "transport_2011-07-25_19-06-01",
        "transport_2011-07-25_19-06-14",
    ]
    this_directory = os.path.abspath(os.path.dirname(__file__))

    def setUp(self):
        self.maxDiff = None
        self._create_user_and_login()
        self.base_url = "http://testserver"
        self.factory = RequestFactory()

    # pylint: disable=no-self-use
    def _fixture_path(self, *args):
        return os.path.join(os.path.dirname(__file__), "fixtures", *args)

    # pylint: disable=no-self-use
    def _create_user(self, username, password, create_profile=False):
        user, _created = User.objects.get_or_create(username=username)
        user.set_password(password)
        user.save()

        # create user profile and set require_auth to false for tests
        if create_profile:
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.require_auth = False
            profile.save()

        return user

    def _create_organization(self, username, name, created_by):
        user = self._create_user(username, "", False)
        organization, _ = OrganizationProfile.objects.get_or_create(
            user=user, defaults={"name": name, "creator": created_by}
        )
        return organization

    # pylint: disable=no-self-use
    def _login(self, username, password):
        client = Client()
        assert client.login(username=username, password=password)
        return client

    def _logout(self, client=None):
        if not client:
            client = self.client
        client.logout()

    def _create_user_and_login(self, username="bob", password="bob", factory=None):
        self.login_username = username
        self.login_password = password
        self.user = self._create_user(username, password, create_profile=True)

        if factory is None:
            self.client = self._login(username, password)
            self.anon = Client()

    def _publish_xls_file(self, path, user=None):
        user = user or self.user
        if not path.startswith(f"/{user.username}/"):
            path = os.path.join(self.this_directory, path)
        with open(path, "rb") as f:
            xls_file = InMemoryUploadedFile(
                f,
                "xls_file",
                os.path.abspath(os.path.basename(path)),
                "application/vnd.ms-excel",
                os.path.getsize(path),
                None,
            )
            if not hasattr(self, "project"):
                # pylint: disable=attribute-defined-outside-init
                self.project = get_user_default_project(user)

            DataDictionary.objects.create(
                created_by=user, user=user, xls=xls_file, project=self.project
            )

    def _publish_xlsx_file(self):
        path = os.path.join(self.this_directory, "fixtures", "exp.xlsx")
        pre_count = XForm.objects.count()
        TestBase._publish_xls_file(self, path)
        # make sure publishing the survey worked
        self.assertEqual(XForm.objects.count(), pre_count + 1)

    def _publish_xlsx_file_with_external_choices(self, form_version="v1"):
        path = os.path.join(
            self.this_directory, "fixtures", f"external_choice_form_{form_version}.xlsx"
        )
        pre_count = XForm.objects.count()
        TestBase._publish_xls_file(self, path)
        # make sure publishing the survey worked
        self.assertEqual(XForm.objects.count(), pre_count + 1)

    def _publish_xls_file_and_set_xform(self, path):
        count = XForm.objects.count()
        self._publish_xls_file(path)
        self.assertEqual(XForm.objects.count(), count + 1)
        # pylint: disable=attribute-defined-outside-init
        self.xform = XForm.objects.order_by("pk").reverse()[0]

    def _share_form_data(self, id_string="transportation_2011_07_25"):
        xform = XForm.objects.get(id_string=id_string)
        xform.shared_data = True
        xform.save()

    def _publish_transportation_form(self):
        xls_path = os.path.join(
            self.this_directory, "fixtures", "transportation", "transportation.xlsx"
        )
        count = XForm.objects.count()
        TestBase._publish_xls_file(self, xls_path)
        self.assertEqual(XForm.objects.count(), count + 1)
        # pylint: disable=attribute-defined-outside-init
        self.xform = XForm.objects.order_by("pk").reverse()[0]

    def _submit_transport_instance(self, survey_at=0):
        s = self.surveys[survey_at]
        self._make_submission(
            os.path.join(
                self.this_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
        )

    def _submit_transport_instance_w_uuid(self, name):
        self._make_submission(
            os.path.join(
                self.this_directory,
                "fixtures",
                "transportation",
                "instances_w_uuid",
                name,
                name + ".xml",
            )
        )

    def _submit_transport_instance_w_attachment(
        self, survey_at=0, delete_existing_attachments=True
    ):
        s = self.surveys[survey_at]
        media_file = "1335783522563.jpg"
        if delete_existing_attachments:
            try:
                cmd = f"rm {settings.MEDIA_ROOT}*/attachments/*/{media_file}"
                subprocess.run(cmd, shell=True, check=True)
            except subprocess.CalledProcessError:
                pass

        self._make_submission_w_attachment(
            os.path.join(
                self.this_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            ),
            os.path.join(
                self.this_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                media_file,
            ),
        )
        success_xml = clean_and_parse_xml(self.response.content)
        submission_metadata = success_xml.getElementsByTagName("submissionMetadata")
        self.assertEqual(len(submission_metadata), 1)
        uuid = submission_metadata[0].getAttribute("instanceID").replace("uuid:", "")
        instance = Instance.objects.get(uuid=uuid)

        # pylint: disable=attribute-defined-outside-init
        self.attachment = instance.attachments.all()[0]
        self.attachment_media_file = self.attachment.media_file

    def _publish_transportation_form_and_submit_instance(self):
        self._publish_transportation_form()
        self._submit_transport_instance()

    def _make_submissions_gps(self):
        surveys = [
            "gps_1980-01-23_20-52-08",
            "gps_1980-01-23_21-21-33",
        ]
        for survey in surveys:
            path = self._fixture_path("gps", "instances", survey + ".xml")
            self._make_submission(path)

    # pylint: disable=too-many-arguments, too-many-positional-arguments,too-many-locals,unused-argument
    def _make_submission(
        self,
        path,
        username=None,
        add_uuid=False,
        forced_submission_time=None,
        auth=None,
        client=None,
    ):
        # store temporary file with dynamic uuid

        self.factory = APIRequestFactory()
        if auth is None:
            auth = DigestAuth(self.login_username, self.login_password)

        tmp_file = None

        if add_uuid:
            with NamedTemporaryFile(delete=False, mode="w") as tmp_file:
                split_xml = None

                with open(path, encoding="utf-8") as _file:
                    split_xml = re.split(r"(<transport>)", _file.read())

                split_xml[1:1] = [f"<formhub><uuid>{self.xform.uuid}</uuid></formhub>"]
                tmp_file.write("".join(split_xml))
                path = tmp_file.name

        with open(path, encoding="utf-8") as f:
            post_data = {"xml_submission_file": f}

            if username is None:
                username = self.user.username

            url_prefix = f"{username if username else ''}/"
            url = f"/{url_prefix}submission"

            request = self.factory.post(url, post_data)
            request.user = authenticate(
                request, username=auth.username, password=auth.password
            )

            # pylint: disable=attribute-defined-outside-init
            self.response = submission(request, username=username)

            if auth and self.response.status_code == 401:
                request.META.update(auth(request.META, self.response))
                self.response = submission(request, username=username)

        if forced_submission_time:
            instance = Instance.objects.order_by("-pk").all()[0]
            instance.date_created = forced_submission_time
            instance.json = instance.get_full_dict()
            instance.save()
            instance.parsed_instance.save()

        # remove temporary file if stored
        if add_uuid:
            os.unlink(tmp_file.name)

    def _make_submission_w_attachment(self, path, attachment_path):
        with open(path, encoding="utf-8") as f:
            data = {"xml_submission_file": f}
            if attachment_path is not None:
                if isinstance(attachment_path, list):
                    for index, item_path in enumerate(attachment_path):
                        # pylint: disable=consider-using-with
                        data[f"media_file_{index}"] = open(item_path, "rb")
                else:
                    # pylint: disable=consider-using-with
                    data["media_file"] = open(attachment_path, "rb")

            url = f"/{self.user.username}/submission"
            auth = DigestAuth(self.login_username, self.login_password)
            self.factory = APIRequestFactory()
            request = self.factory.post(url, data)
            request.user = authenticate(
                request, username=auth.username, password=auth.password
            )
            # pylint: disable=attribute-defined-outside-init
            self.response = submission(request, username=self.user.username)

            if auth and self.response.status_code == 401:
                request.META.update(auth(request.META, self.response))
                self.response = submission(request, username=self.user.username)

    def _make_submissions(self, username=None, add_uuid=False, should_store=True):
        """Make test fixture submissions to current xform.

        :param username: submit under this username, default None.
        :param add_uuid: add UUID to submission, default False.
        :param should_store: should submissions be save, default True.
        """

        paths = [
            os.path.join(
                self.this_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            for s in self.surveys
        ]
        pre_count = Instance.objects.count()

        for path in paths:
            self._make_submission(path, username, add_uuid)

        post_count = pre_count + len(self.surveys) if should_store else pre_count
        self.assertEqual(Instance.objects.count(), post_count)
        self.assertEqual(self.xform.instances.count(), post_count)
        xform = XForm.objects.get(pk=self.xform.pk)
        self.assertEqual(xform.num_of_submissions, post_count)
        self.assertEqual(xform.user.profile.num_of_submissions, post_count)

    def _check_url(self, url, timeout=1):
        try:
            with urlopen(url, timeout=timeout):
                return True
        except (URLError, socket.timeout):
            pass
        return False

    def _internet_on(self, url="http://74.125.113.99"):
        # default value is some google IP
        return self._check_url(url)

    def _set_auth_headers(self, username, password):
        return {
            "HTTP_AUTHORIZATION": "Basic "
            + base64.b64encode(f"{username}:{password}".encode("utf-8")).decode(
                "utf-8"
            ),
        }

    def _get_authenticated_client(
        self, url, username="bob", password="bob", extra=None
    ):
        client = DigestClient()
        extra = {} if extra is None else extra
        # request with no credentials
        req = client.get(url, {}, **extra)
        self.assertEqual(req.status_code, 401)
        # apply credentials
        client.set_authorization(username, password, "Digest")
        return client

    def _set_mock_time(self, mock_time):
        current_time = timezone.now()
        mock_time.return_value = current_time

    def _set_require_auth(self, auth=True):
        profile, _created = UserProfile.objects.get_or_create(user=self.user)
        profile.require_auth = auth
        profile.save()

    def _get_digest_client(self):
        self._set_require_auth(True)
        client = DigestClient()
        client.set_authorization("bob", "bob", "Digest")
        return client

    def _publish_submit_geojson(self, has_empty_geoms=False, only_geopoints=False):
        path = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "main",
            "tests",
            "fixtures",
            "geolocation",
            (
                "GeoLocationFormNoPolylineOrPolygon.xlsx"
                if only_geopoints
                else "GeoLocationForm.xlsx"
            ),
        )

        self._publish_xls_file_and_set_xform(path)

        csv_sub = "empty_geoms" if has_empty_geoms else "2015_01_15_01_28_45"

        view = XFormViewSet.as_view({"post": "csv_import"})
        with open(
            os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "geolocation",
                f"GeoLocationForm_{csv_sub}.csv",
            ),
            encoding="utf-8",
        ) as csv_import:
            post_data = {"csv_file": csv_import}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = view(request, pk=self.xform.id)
            self.assertEqual(response.status_code, 200)

    def _publish_submit_geoms_in_repeats(self, geom_type):
        view = XFormViewSet.as_view({"post": "csv_import"})
        with open(
            os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "geolocation",
                f"{geom_type}.csv",
            ),
            encoding="utf-8",
        ) as csv_import:
            post_data = {"csv_file": csv_import}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = view(request, pk=self.xform.id)
            self.assertEqual(response.status_code, 200)

    def _publish_markdown(self, md_xlsform, user, project=None, **kwargs):
        """
        Publishes a markdown XLSForm.
        """
        kwargs["name"] = "data"
        survey = self.md_to_pyxform_survey(md_xlsform, kwargs=kwargs)
        survey["sms_keyword"] = survey["id_string"]

        if not project or not hasattr(self, "project"):
            project = get_user_default_project(user)
            self.project = project

        data_dict = DataDictionary(
            created_by=user,
            user=user,
            xml=survey.to_xml(),
            json=survey.to_json_dict(),
            project=project,
            version=survey.get("version"),
        )
        data_dict.save()
        latest_form = XForm.objects.all().order_by("-pk").first()
        XFormVersion.objects.create(
            xform=latest_form,
            version=survey.get("version"),
            xml=data_dict.xml,
            json=survey.to_json(),
        )

        return data_dict

    def _test_csv_response(self, response, csv_file_path):
        headers = dict(response.items())
        self.assertEqual(headers["Content-Type"], "application/csv")
        content_disposition = headers["Content-Disposition"]
        filename = filename_from_disposition(content_disposition)
        __, ext = os.path.splitext(filename)
        self.assertEqual(ext, '.csv"')

        data = get_response_content(response)
        reader = csv.DictReader(StringIO(data))
        data = list(reader)
        with open(csv_file_path, encoding="utf-8") as test_file:
            expected_csv_reader = csv.DictReader(test_file)
            for index, row in enumerate(expected_csv_reader):
                if None in row:
                    row.pop(None)
                self.assertDictContainsSubset(row, data[index])

    def _test_csv_files(self, csv_file, csv_file_path):
        reader = csv.DictReader(csv_file)
        data = list(reader)
        with open(csv_file_path, encoding="utf-8") as test_file:
            expected_csv_reader = csv.DictReader(test_file)
            for index, row in enumerate(expected_csv_reader):
                if None in row:
                    row.pop(None)
                self.assertDictContainsSubset(row, data[index])

    def _publish_registration_form(self, user, project=None):
        md = """
        | survey   |
        |          | type               | name                                       | label                    | save_to                                    |
        |          | geopoint           | location                                   | Tree location            | geometry                                   |
        |          | select_one species | species                                    | Tree species             | species                                    |
        |          | integer            | circumference                              | Tree circumference in cm | circumference_cm                           |
        |          | text               | intake_notes                               | Intake notes             |                                            |
        | choices  |                    |                                            |                          |                                            |
        |          | list_name          | name                                       | label                    |                                            |
        |          | species            | wallaba                                    | Wallaba                  |                                            |
        |          | species            | mora                                       | Mora                     |                                            |
        |          | species            | purpleheart                                | Purpleheart              |                                            |
        |          | species            | greenheart                                 | Greenheart               |                                            |
        | settings |                    |                                            |                          |                                            |
        |          | form_title         | form_id                                    | version                  | instance_name                              |
        |          | Trees registration | trees_registration                         | 2022110901               | concat(${circumference}, "cm ", ${species})|
        | entities |                    |                                            |                          |                                            |
        |          | list_name          | label                                      |                          |                                            |
        |          | trees              | concat(${circumference}, "cm ", ${species})|                          |                                            |"""
        self._publish_markdown(
            md,
            user,
            project,
            id_string="trees_registration",
            title="Trees registration",
        )
        latest_form = XForm.objects.all().order_by("-pk").first()

        return latest_form

    def _publish_follow_up_form(self, user, project=None):
        md = """
        | survey  |
        |         | type                           | name            | label                            | required |
        |         | select_one_from_file trees.csv | tree            | Select the tree you are visiting | yes      |
        | settings|                                |                 |                                  |          |
        |         | form_title                     | form_id         |  version                         |          |
        |         | Trees follow-up                | trees_follow_up |  2022111801                      |          |
        """
        self._publish_markdown(
            md,
            user,
            project,
            id_string="trees_follow_up",
            title="Trees follow-up",
        )
        latest_form = XForm.objects.all().order_by("-pk").first()

        return latest_form

    def _create_merged_dataset(self, make_submissions=False):
        md = """
        | survey  |
        |         | type              | name  | label   |
        |         | select one fruits | fruit | Fruit   |
        | choices |
        |         | list name         | name   | label  |
        |         | fruits            | orange | Orange |
        |         | fruits            | mango  | Mango  |
        """
        self._publish_markdown(md, self.user, id_string="a")
        self._publish_markdown(md, self.user, id_string="b")
        xf1 = XForm.objects.get(id_string="a")
        xf2 = XForm.objects.get(id_string="b")
        survey = create_survey_element_from_dict(xf1.json_dict())
        survey["id_string"] = "c"
        survey["sms_keyword"] = survey["id_string"]
        survey["title"] = "Merged XForm"
        merged_xf = MergedXForm.objects.create(
            id_string=survey["id_string"],
            sms_id_string=survey["id_string"],
            title=survey["title"],
            user=self.user,
            created_by=self.user,
            is_merged_dataset=True,
            project=self.project,
            xml=survey.to_xml(),
            json=survey.to_json(),
        )
        merged_xf.xforms.add(xf1)
        merged_xf.xforms.add(xf2)

        if make_submissions:
            # Make submission for form a
            xml = '<data id="a"><fruit>orange</fruit></data>'
            Instance(xform=xf1, xml=xml).save()
            # Make submission for form b
            xml = '<data id="b"><fruit>mango</fruit></data>'
            Instance(xform=xf2, xml=xml).save()

        return merged_xf

    def _publish_entity_update_form(self, user, project=None):
        md = """
        | survey  |
        |         | type                           | name          | label                    | save_to                                 |
        |         | select_one_from_file trees.csv | tree          | Select the tree          |                                         |
        |         | integer                        | circumference | Tree circumference in cm | circumference_cm                        |
        |         | date                           | today         | Today's date             | latest_visit                            |
        | settings|                                |               |                          |                                         |
        |         | form_title                     | form _id      | version                  | instance_name                           |
        |         | Trees update                   | trees_update  | 2024050801               | concat(${circumference}, "cm ", ${tree})|
        | entities| list_name                      | entity_id     |                          |                                         |
        |         | trees                          | ${tree}       |                          |                                         |
        """
        self._publish_markdown(
            md,
            user,
            project,
            id_string="trees_update",
            title="Trees update",
        )
        latest_form = XForm.objects.all().order_by("-pk").first()

        return latest_form

    def _encrypt_xform(self, xform, kms_key, encrypted_by=None):
        version = timezone.now().strftime("%Y%m%d%H%M")

        json_dict = xform.json_dict()
        json_dict["public_key"] = kms_key.public_key
        json_dict["version"] = version

        survey = create_survey_element_from_dict(json_dict)

        xform.json = survey.to_json_dict()
        xform.xml = survey.to_xml()
        xform.version = version
        xform.public_key = kms_key.public_key
        xform.encrypted = True
        xform.save()
        xform.kms_keys.create(
            version=version, kms_key=kms_key, encrypted_by=encrypted_by
        )
