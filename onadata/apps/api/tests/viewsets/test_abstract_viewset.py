# -*- coding: utf-8 -*-
"""
Test base class for API viewset tests.
"""

import json
import os
import re
import warnings
from tempfile import NamedTemporaryFile

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import Permission
from django.db.models.signals import post_save
from django.test import TestCase

import requests
from django_digest.test import Client as DigestClient
from django_digest.test import DigestAuth
from httmock import HTTMock
from rest_framework.test import APIRequestFactory

from onadata.apps.api.models import OrganizationProfile, Team
from onadata.apps.api.tests.mocked_data import enketo_urls_mock
from onadata.apps.api.viewsets.dataview_viewset import DataViewViewSet
from onadata.apps.api.viewsets.metadata_viewset import MetaDataViewSet
from onadata.apps.api.viewsets.organization_profile_viewset import (
    OrganizationProfileViewSet,
)
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.team_viewset import TeamViewSet
from onadata.apps.api.viewsets.widget_viewset import WidgetViewSet
from onadata.apps.logger.models import (
    Attachment,
    Entity,
    EntityList,
    Instance,
    Project,
    XForm,
)
from onadata.apps.logger.models.data_view import DataView
from onadata.apps.logger.models.widget import Widget
from onadata.apps.logger.views import submission
from onadata.apps.logger.xform_instance_parser import clean_and_parse_xml
from onadata.apps.main import tests as main_tests
from onadata.apps.main.models import MetaData, UserProfile
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models import DataDictionary
from onadata.apps.viewer.models.data_dictionary import create_or_update_export_register
from onadata.libs.serializers.project_serializer import ProjectSerializer
from onadata.libs.utils.common_tools import merge_dicts

# pylint: disable=invalid-name
User = get_user_model()

warnings.simplefilter("ignore")


def _set_api_permissions(user):
    add_userprofile = Permission.objects.get(
        content_type__app_label="main",
        content_type__model="userprofile",
        codename="add_userprofile",
    )
    user.user_permissions.add(add_userprofile)


def add_uuid_to_submission_xml(path, xform):
    """
    Adds the formhub uuid to an XML XForm submission at the given path.
    """
    with NamedTemporaryFile(delete=False, mode="w") as tmp_file:
        split_xml = None

        with open(path, encoding="utf-8") as _file:
            split_xml = re.split(r"(<transport>)", _file.read())

        split_xml[1:1] = [f"<formhub><uuid>{xform.uuid}</uuid></formhub>"]
        tmp_file.write("".join(split_xml))
        path = tmp_file.name

    return path


# pylint: disable=invalid-name
def get_mocked_response_for_file(file_object, filename, status_code=200):
    """Returns a requests.Response() object for mocked tests."""
    mock_response = requests.Response()
    mock_response.status_code = status_code
    mock_response.headers = {
        "content-type": (
            "application/vnd.openxmlformats-" "officedocument.spreadsheetml.sheet"
        ),
        "Content-Disposition": (
            'attachment; filename="transportation.'
            f"xlsx\"; filename*=UTF-8''{filename}"
        ),
    }
    # pylint: disable=protected-access
    mock_response._content = file_object.read()

    return mock_response


# pylint: disable=too-many-instance-attributes
class TestAbstractViewSet(TestBase, TestCase):
    """
    Base test class for API viewsets.
    """

    surveys = [
        "transport_2011-07-25_19-05-49",
        "transport_2011-07-25_19-05-36",
        "transport_2011-07-25_19-06-01",
        "transport_2011-07-25_19-06-14",
    ]
    main_directory = os.path.dirname(main_tests.__file__)

    profile_data = {
        "username": "bob",
        "email": "bob@columbia.edu",
        "password1": "bobbob",
        "password2": "bobbob",
        "first_name": "Bob",
        "last_name": "erama",
        "city": "Bobville",
        "country": "US",
        "organization": "Bob Inc.",
        "home_page": "bob.com",
        "twitter": "boberama",
        "name": "Bob erama",
    }

    def setUp(self):
        TestCase.setUp(self)
        self.factory = APIRequestFactory()
        self._login_user_and_profile()
        self.maxDiff = None
        # Disable signals
        post_save.disconnect(
            sender=DataDictionary, dispatch_uid="create_or_update_export_register"
        )

    def tearDown(self):
        # Enable signals
        post_save.connect(
            sender=DataDictionary,
            dispatch_uid="create_or_update_export_register",
            receiver=create_or_update_export_register,
        )

        TestCase.tearDown(self)

    def user_profile_data(self):
        """Returns the user profile python object."""
        return {
            "id": self.user.pk,
            "url": "http://testserver/api/v1/profiles/bob",
            "username": "bob",
            "first_name": "Bob",
            "last_name": "erama",
            "email": "bob@columbia.edu",
            "city": "Bobville",
            "country": "US",
            "organization": "Bob Inc.",
            "website": "bob.com",
            "twitter": "boberama",
            "gravatar": self.user.profile.gravatar,
            "require_auth": False,
            "user": "http://testserver/api/v1/users/bob",
            "is_org": False,
            "metadata": {},
            "joined_on": self.user.date_joined,
            "name": "Bob erama",
        }

    def _create_user_profile(self, extra_post_data=None):
        extra_post_data = {} if extra_post_data is None else extra_post_data
        self.profile_data = merge_dicts(self.profile_data, extra_post_data)
        user, _created = User.objects.get_or_create(
            username=self.profile_data["username"],
            first_name=self.profile_data["first_name"],
            last_name=self.profile_data["last_name"],
            email=self.profile_data["email"],
        )
        user.set_password(self.profile_data["password1"])
        user.save()
        new_profile, _created = UserProfile.objects.get_or_create(
            user=user,
            name=self.profile_data["first_name"],
            city=self.profile_data["city"],
            country=self.profile_data["country"],
            organization=self.profile_data["organization"],
            home_page=self.profile_data["home_page"],
            twitter=self.profile_data["twitter"],
            require_auth=False,
        )

        return new_profile

    def _login_user_and_profile(self, extra_post_data=None):
        extra_post_data = {} if extra_post_data is None else extra_post_data
        profile = self._create_user_profile(extra_post_data)
        self.user = profile.user
        self.assertTrue(
            self.client.login(
                username=self.user.username, password=self.profile_data["password1"]
            )
        )
        self.extra = {"HTTP_AUTHORIZATION": f"Token {self.user.auth_token}"}
        self.login_username = self.profile_data["username"]
        self.login_password = self.profile_data["password1"]

    def _org_create(self, org_data=None):
        org_data = {} if org_data is None else org_data
        view = OrganizationProfileViewSet.as_view({"get": "list", "post": "create"})
        request = self.factory.get("/", **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        data = {
            "email": "mail@mail-server.org",
            "org": "denoinc",
            "name": "Dennis",
            "city": "Denoville",
            "country": "US",
            "home_page": "deno.com",
            "twitter": "denoinc",
            "description": "",
            "address": "",
            "phonenumber": "",
            "require_auth": False,
        }

        if org_data:
            data.update(org_data)

        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request)
        self.assertEqual(response.status_code, 201)
        data["url"] = f"http://testserver/api/v1/orgs/{data['org']}"
        data["user"] = f"http://testserver/api/v1/users/{data['org']}"
        data["creator"] = "http://testserver/api/v1/users/bob"
        data.pop("email")
        self.assertDictContainsSubset(data, response.data)
        # pylint: disable=attribute-defined-outside-init
        self.company_data = response.data
        self.organization = OrganizationProfile.objects.get(user__username=data["org"])

    def _publish_form_with_hxl_support(self):
        xlsform_path = os.path.join(
            settings.PROJECT_ROOT,
            "libs",
            "tests",
            "utils",
            "fixtures",
            "hxl_example",
            "hxl_example.xlsx",
        )

        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        for x in range(1, 3):
            path = os.path.join(
                settings.PROJECT_ROOT,
                "libs",
                "tests",
                "utils",
                "fixtures",
                "hxl_example",
                "instances",
                f"instance_{x}.xml",
            )
            self._make_submission(path)

    def _project_create(self, project_data=None, merge=True):
        project_data = {} if project_data is None else project_data
        view = ProjectViewSet.as_view({"post": "create"})

        if merge:
            data = {
                "name": "demo",
                "owner": f"http://testserver/api/v1/users/{self.user.username}",
                "metadata": {
                    "description": "Some description",
                    "location": "Naivasha, Kenya",
                    "category": "governance",
                },
                "public": False,
            }
            data.update(project_data)
        else:
            data = project_data

        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, owner=self.user.username)
        self.assertEqual(response.status_code, 201)
        # pylint: disable=attribute-defined-outside-init
        self.project = Project.objects.filter(name=data["name"], created_by=self.user)[
            0
        ]
        data["url"] = f"http://testserver/api/v1/projects/{self.project.pk}"
        self.assertDictContainsSubset(data, response.data)

        request.user = self.user
        # pylint: disable=attribute-defined-outside-init
        self.project_data = ProjectSerializer(
            self.project, context={"request": request}
        ).data

    def _publish_xls_form_to_project(
        self, publish_data=None, merge=True, public=False, xlsform_path=None
    ):
        publish_data = {} if publish_data is None else publish_data
        if not hasattr(self, "project"):
            self._project_create()
        elif self.project.created_by != self.user:
            self._project_create()

        view = ProjectViewSet.as_view({"post": "forms"})

        project_id = self.project.pk
        if merge:
            data = {
                "owner": (
                    "http://testserver/api/v1/users/"
                    f"{self.project.organization.username}"
                ),
                "public": False,
                "public_data": False,
                "description": "transportation_2011_07_25",
                "downloadable": True,
                "allows_sms": False,
                "encrypted": False,
                "sms_id_string": "transportation_2011_07_25",
                "id_string": "transportation_2011_07_25",
                "title": "transportation_2011_07_25",
                "bamboo_dataset": "",
            }
            data.update(publish_data)
        else:
            data = publish_data

        path = xlsform_path or os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "main",
            "tests",
            "fixtures",
            "transportation",
            "transportation.xlsx",
        )

        with HTTMock(enketo_urls_mock):
            with open(path, "rb") as xls_file:
                post_data = {"xls_file": xls_file}
                request = self.factory.post("/", data=post_data, **self.extra)
                response = view(request, pk=project_id)
                self.assertEqual(response.status_code, 201)
                # pylint: disable=attribute-defined-outside-init
                self.xform = XForm.objects.all().order_by("pk").reverse()[0]
                data.update({"url": f"http://testserver/api/v1/forms/{self.xform.pk}"})
                # Input was a private so change to public if project public
                if public:
                    data["public_data"] = data["public"] = True

                # pylint: disable=attribute-defined-outside-init
                self.form_data = response.data

    # pylint: disable=too-many-arguments, too-many-positional-arguments,too-many-locals,unused-argument
    def _make_submission(
        self,
        path,
        username=None,
        add_uuid=False,
        forced_submission_time=None,
        client=None,
        media_file=None,
        auth=None,
    ):
        # store temporary file with dynamic uuid
        self.factory = APIRequestFactory()
        if auth is None:
            auth = DigestAuth(
                self.profile_data["username"], self.profile_data["password1"]
            )

        media_count = 0
        tmp_file = None

        if add_uuid:
            path = add_uuid_to_submission_xml(path, self.xform)
        with open(path, encoding="utf-8") as f:
            post_data = {"xml_submission_file": f}

            if media_file is not None:
                if isinstance(media_file, list):
                    for position, _value in enumerate(media_file):
                        post_data[f"media_file_{position}"] = media_file[position]
                        media_count += 1
                else:
                    post_data["media_file"] = media_file
                    media_count += 1

            if username is None:
                username = self.user.username

            url_prefix = f"{username if username else ''}/"
            url = f"/{url_prefix}submission"

            request = self.factory.post(url, post_data)
            request.user = authenticate(username=auth.username, password=auth.password)
            # pylint: disable=attribute-defined-outside-init
            self.response = submission(request, username=username)

            if auth and self.response.status_code == 401:
                request.META.update(auth(request.META, self.response))
                self.response = submission(request, username=username)
            if media_file and media_count > 0 and self.response.status_code == 201:
                success_xml = clean_and_parse_xml(self.response.content)
                submission_metadata = success_xml.getElementsByTagName(
                    "submissionMetadata"
                )
                self.assertEqual(len(submission_metadata), 1)
                uuid = (
                    submission_metadata[0]
                    .getAttribute("instanceID")
                    .replace("uuid:", "")
                )
                self.instance = Instance.objects.get(uuid=uuid)
                self.assertEqual(self.instance.attachments.all().count(), media_count)
            else:
                if hasattr(self, "logger"):
                    self.logger.debug(
                        "Auth/Submission request: %s, media: %s",
                        self.response.status_code,
                        media_count,
                    )

        if forced_submission_time:
            instance = Instance.objects.order_by("-pk").all()[0]
            instance.date_created = forced_submission_time
            instance.save()
            instance.parsed_instance.save()

        # remove temporary file if stored
        if add_uuid:
            os.unlink(tmp_file.name)

    def _make_submissions(self, username=None, add_uuid=False, should_store=True):
        """Make test fixture submissions to current xform.

        :param username: submit under this username, default None.
        :param add_uuid: add UUID to submission, default False.
        :param should_store: should submissions be save, default True.
        """
        paths = [
            os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            for s in self.surveys
        ]
        pre_count = Instance.objects.count()
        xform_pre_count = self.xform.instances.count()

        auth = DigestAuth(self.profile_data["username"], self.profile_data["password1"])
        for path in paths:
            self._make_submission(path, username, add_uuid, auth=auth)
        post_count = pre_count + len(self.surveys) if should_store else pre_count
        xform_post_count = (
            xform_pre_count + len(self.surveys) if should_store else xform_pre_count
        )
        self.assertEqual(Instance.objects.count(), post_count)
        self.assertEqual(self.xform.instances.count(), xform_post_count)
        xform = XForm.objects.get(pk=self.xform.pk)
        self.assertEqual(xform.num_of_submissions, xform_post_count)
        self.assertEqual(xform.user.profile.num_of_submissions, xform_post_count)

    def _submit_transport_instance_w_attachment(
        self, survey_at=0, media_file=None, forced_submission_time=None
    ):
        s = self.surveys[survey_at]
        if not media_file:
            media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )
        with open(path, "rb") as f:
            self._make_submission(
                os.path.join(
                    self.main_directory,
                    "fixtures",
                    "transportation",
                    "instances",
                    s,
                    s + ".xml",
                ),
                media_file=f,
                forced_submission_time=forced_submission_time,
            )

        attachment = Attachment.objects.all().reverse()[0]
        # pylint: disable=attribute-defined-outside-init
        self.attachment = attachment

    def _post_metadata(self, data, test=True):
        count = MetaData.objects.count()
        view = MetaDataViewSet.as_view({"post": "create"})
        request = self.factory.post(
            "/",
            data=data,
            **self.extra,
            format="json" if "extra_data" in data else None,
        )

        response = view(request)

        if test:
            self.assertEqual(response.status_code, 201, response.data)
            another_count = MetaData.objects.count()
            self.assertEqual(another_count, count + 1)
            # pylint: disable=attribute-defined-outside-init
            self.metadata = MetaData.objects.get(pk=response.data["id"])
            self.metadata_data = response.data

        return response

    def _add_form_metadata(
        self,
        xform,
        data_type,
        data_value,
        path=None,
        test=True,
        extra_data=None,
    ):
        data = {"data_type": data_type, "data_value": data_value, "xform": xform.id}

        if extra_data:
            data.update({"extra_data": extra_data})

        if path and data_value:
            with open(path, "rb") as media_file:
                data.update(
                    {
                        "data_file": media_file,
                    }
                )
                return self._post_metadata(data, test)
        else:
            return self._post_metadata(data, test)

    def _get_digest_client(self):
        self.user.profile.require_auth = True
        self.user.profile.save()
        client = DigestClient()
        client.set_authorization(
            self.profile_data["username"], self.profile_data["password1"], "Digest"
        )
        return client

    def _create_dataview(self, data=None, project=None, xform=None):
        view = DataViewViewSet.as_view({"post": "create"})

        project = project if project else self.project
        xform = xform if xform else self.xform

        if not data:
            data = {
                "name": "My DataView",
                "xform": f"http://testserver/api/v1/forms/{xform.pk}",
                "project": f"http://testserver/api/v1/projects/{project.pk}",
                "columns": '["name", "age", "gender"]',
                "query": (
                    '[{"column":"age","filter":">","value":"20"},'
                    '{"column":"age","filter":"<","value":"50"}]'
                ),
            }
        request = self.factory.post("/", data=data, **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 201)

        # load the created dataview
        # pylint: disable=attribute-defined-outside-init
        self.data_view = DataView.objects.filter(xform=xform, project=project).last()

        self.assertEqual(response.data["name"], data["name"])
        self.assertEqual(response.data["xform"], data["xform"])
        self.assertEqual(response.data["project"], data["project"])
        self.assertEqual(response.data["columns"], json.loads(data["columns"]))
        self.assertEqual(
            response.data["query"], json.loads(data["query"]) if "query" in data else {}
        )
        self.assertEqual(
            response.data["url"],
            f"http://testserver/api/v1/dataviews/{self.data_view.pk}",
        )

    def _create_widget(self, data=None, group_by=""):
        view = WidgetViewSet.as_view({"post": "create"})

        if not data:
            data = {
                "title": "Widget that",
                "content_object": f"http://testserver/api/v1/forms/{self.xform.pk}",
                "description": "Test widget",
                "aggregation": "Sum",
                "widget_type": "charts",
                "view_type": "horizontal-bar",
                "column": "age",
                "group_by": group_by,
            }

        count = Widget.objects.all().count()

        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request)

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(count + 1, Widget.objects.all().count())

        # pylint: disable=attribute-defined-outside-init
        self.widget = Widget.objects.all().order_by("pk").reverse()[0]

        self.assertEqual(response.data["id"], self.widget.id)
        self.assertEqual(response.data["title"], data.get("title"))
        self.assertEqual(response.data["content_object"], data["content_object"])
        self.assertEqual(response.data["widget_type"], data["widget_type"])
        self.assertEqual(response.data["view_type"], data["view_type"])
        self.assertEqual(response.data["column"], data["column"])
        self.assertEqual(response.data["description"], data.get("description"))
        self.assertEqual(response.data["group_by"], data.get("group_by"))
        self.assertEqual(response.data["aggregation"], data.get("aggregation"))
        self.assertEqual(response.data["order"], self.widget.order)
        self.assertEqual(response.data["data"], [])
        self.assertEqual(response.data["metadata"], data.get("metadata", {}))

    def _team_create(self):
        self._org_create()

        view = TeamViewSet.as_view({"get": "list", "post": "create"})

        data = {"name": "dreamteam", "organization": self.company_data["org"]}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request)
        self.assertEqual(response.status_code, 201)
        # pylint: disable=attribute-defined-outside-init
        self.owner_team = Team.objects.get(
            organization=self.organization.user,
            name=f"{self.organization.user.username}#Owners",
        )
        team = Team.objects.get(
            organization=self.organization.user,
            name=f"{self.organization.user.username}#{data['name']}",
        )
        data["url"] = f"http://testserver/api/v1/teams/{team.pk}"
        data["teamid"] = team.id
        self.assertDictContainsSubset(data, response.data)
        self.team_data = response.data
        self.team = team

    def is_sorted_desc(self, s):
        """
        Returns True if a list is sorted in descending order.
        """
        if len(s) in [0, 1]:
            return True
        if s[0] >= s[1]:
            return self.is_sorted_desc(s[1:])
        return False

    def is_sorted_asc(self, s):
        """
        Returns True if a list is sorted in ascending order.
        """
        if len(s) in [0, 1]:
            return True
        if s[0] <= s[1]:
            return self.is_sorted_asc(s[1:])
        return False

    def _get_request_session_with_auth(self, view, auth, extra=None):
        request = self.factory.head("/")
        response = view(request)
        self.assertTrue(response.has_header("WWW-Authenticate"))
        self.assertTrue(response["WWW-Authenticate"].startswith("Digest "))
        self.assertIn("nonce=", response["WWW-Authenticate"])
        extra = {} if extra is None else extra
        request = self.factory.get("/", **extra)
        request.META.update(auth(request.META, response))
        request.session = self.client.session

        return request

    def _create_entity(self):
        self._publish_registration_form(self.user)
        self.entity_list = EntityList.objects.get(name="trees")
        self.entity = Entity.objects.create(
            entity_list=self.entity_list,
            json={
                "geometry": "-1.286905 36.772845 0 0",
                "species": "purpleheart",
                "circumference_cm": 300,
                "label": "300cm purpleheart",
            },
            uuid="dbee4c32-a922-451c-9df7-42f40bf78f48",
        )
