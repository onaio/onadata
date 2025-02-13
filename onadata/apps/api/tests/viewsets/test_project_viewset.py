# -*- coding: utf-8 -*-
"""
Test ProjectViewSet module.
"""

import json
import os
from collections import OrderedDict
from datetime import datetime
from datetime import timezone as tz
from operator import itemgetter
from unittest.mock import MagicMock, Mock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Q
from django.test import override_settings
from django.utils import timezone

import dateutil.parser
import requests
from httmock import HTTMock, urlmatch
from rest_framework.authtoken.models import Token
from six import iteritems

from onadata.apps.api import tools
from onadata.apps.api.tests.viewsets.test_abstract_viewset import (
    TestAbstractViewSet,
    get_mocked_response_for_file,
)
from onadata.apps.api.tools import get_or_create_organization_owners_team
from onadata.apps.api.viewsets.organization_profile_viewset import (
    OrganizationProfileViewSet,
)
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.team_viewset import TeamViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.logger.models import (
    EntityList,
    Project,
    ProjectInvitation,
    XForm,
    XFormVersion,
)
from onadata.apps.main.models import MetaData
from onadata.libs import permissions as role
from onadata.libs.models.share_project import ShareProject
from onadata.libs.permissions import (
    ROLES_ORDERED,
    DataEntryMinorRole,
    DataEntryOnlyRole,
    DataEntryRole,
    EditorMinorRole,
    EditorRole,
    ManagerRole,
    OwnerRole,
    ReadOnlyRole,
    ReadOnlyRoleNoDownload,
)
from onadata.libs.serializers.project_serializer import (
    BaseProjectSerializer,
    ProjectSerializer,
)
from onadata.libs.utils.cache_tools import PROJ_OWNER_CACHE, safe_key
from onadata.libs.utils.user_auth import get_user_default_project

User = get_user_model()

ROLES = [
    ReadOnlyRoleNoDownload,
    ReadOnlyRole,
    DataEntryRole,
    EditorRole,
    ManagerRole,
    OwnerRole,
]


# pylint: disable=unused-argument
@urlmatch(netloc=r"(.*\.)?enketo\.ona\.io$")
def enketo_mock(url, request):
    """Mock Enketo responses"""
    response = requests.Response()
    response.status_code = 201
    setattr(
        response,
        "_content",
        ('{\n  "url": "https:\\/\\/dmfrm.enketo.org\\/webform",\n  "code": "200"\n}'),
    )

    return response


def get_latest_tags(project):
    """Return given project tags as a list."""
    project.refresh_from_db()
    return [tag.name for tag in project.tags.all()]


class TestProjectViewSet(TestAbstractViewSet):
    """Test ProjectViewSet."""

    def setUp(self):
        super().setUp()
        self.view = ProjectViewSet.as_view({"get": "list", "post": "create"})

    def tearDown(self):
        cache.clear()
        super().tearDown()

    # pylint: disable=invalid-name
    @patch("onadata.apps.main.forms.requests")
    def test_publish_xlsform_using_url_upload(self, mock_requests):
        with HTTMock(enketo_mock):
            self._project_create()
            view = ProjectViewSet.as_view({"post": "forms"})

            pre_count = XForm.objects.count()
            project_id = self.project.pk
            xls_url = "https://ona.io/examples/forms/tutorial/form.xlsx"
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
                response = view(request, pk=project_id)

                mock_requests.get.assert_called_with(xls_url, timeout=30)
                xls_file.close()
                self.assertEqual(response.status_code, 201)
                self.assertEqual(XForm.objects.count(), pre_count + 1)
                self.assertEqual(
                    XFormVersion.objects.filter(
                        xform__pk=response.data.get("formid")
                    ).count(),
                    1,
                )

    @override_settings(TIME_ZONE="UTC")
    def test_projects_list(self):
        self._publish_xls_form_to_project()
        self.project.refresh_from_db()
        request = self.factory.get("/", **self.extra)
        request.user = self.user
        response = self.view(request)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        expected_data = [
            OrderedDict(
                [
                    ("url", f"http://testserver/api/v1/projects/{self.project.pk}"),
                    ("projectid", self.project.pk),
                    ("owner", "http://testserver/api/v1/users/bob"),
                    ("created_by", "http://testserver/api/v1/users/bob"),
                    (
                        "metadata",
                        {
                            "category": "governance",
                            "location": "Naivasha, Kenya",
                            "description": "Some description",
                        },
                    ),
                    ("starred", False),
                    (
                        "users",
                        [
                            {
                                "is_org": False,
                                "metadata": {},
                                "first_name": "Bob",
                                "last_name": "erama",
                                "user": "bob",
                                "role": "owner",
                            }
                        ],
                    ),
                    (
                        "forms",
                        [
                            OrderedDict(
                                [
                                    ("name", "transportation_2011_07_25"),
                                    ("formid", self.xform.pk),
                                    ("id_string", "transportation_2011_07_25"),
                                    ("is_merged_dataset", False),
                                    ("encrypted", False),
                                    ("contributes_entities_to", None),
                                    ("consumes_entities_from", []),
                                ]
                            )
                        ],
                    ),
                    ("public", False),
                    ("tags", []),
                    ("num_datasets", 1),
                    ("last_submission_date", None),
                    ("teams", []),
                    ("name", "demo"),
                    (
                        "date_created",
                        self.project.date_created.isoformat().replace("+00:00", "Z"),
                    ),
                    (
                        "date_modified",
                        self.project.date_modified.isoformat().replace("+00:00", "Z"),
                    ),
                    ("deleted_at", None),
                ]
            )
        ]
        self.assertEqual(response.data, expected_data)
        self.assertIn("created_by", list(response.data[0]))

    def test_projects_list_with_pagination(self):
        view = ProjectViewSet.as_view(
            {
                "get": "list",
            }
        )
        self._project_create()
        # create second project
        username = self.user.username
        self._project_create(
            {
                "name": "proj one",
                "owner": f"http://testserver/api/v1/users/{username}",
                "public": False,
            }
        )
        # test without pagination
        request = self.factory.get("/", **self.extra)
        request.user = self.user
        response = view(request)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        # test with pagination enabled
        params = {"page": 1, "page_size": 1}
        request = self.factory.get("/", data=params, **self.extra)
        request.user = self.user
        response = view(request)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    # pylint: disable=invalid-name
    def test_project_list_returns_projects_for_active_users_only(self):
        """Test project list returns projects of active users only."""
        self._project_create()
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        alice_user = alice_profile.user
        shared_project = Project(
            name="demo2",
            shared=True,
            metadata=json.dumps({"description": ""}),
            created_by=alice_user,
            organization=alice_user,
        )
        shared_project.save()

        # share project with self.user
        shareProject = ShareProject(shared_project, self.user.username, "manager")
        shareProject.save()

        # ensure when alice_user isn't active we can NOT
        # see the project she shared
        alice_user.is_active = False
        alice_user.save()
        request = self.factory.get("/", **self.extra)
        request.user = self.user
        response = self.view(request)
        self.assertEqual(len(response.data), 1)
        self.assertNotEqual(response.data[0].get("projectid"), shared_project.id)

        # ensure when alice_user is active we can
        # see the project she shared
        alice_user.is_active = True
        alice_user.save()
        request = self.factory.get("/", **self.extra)
        request.user = self.user
        response = self.view(request)
        self.assertEqual(len(response.data), 2)

        shared_project_in_response = False
        for project in response.data:
            if project.get("projectid") == shared_project.id:
                shared_project_in_response = True
                break
        self.assertTrue(shared_project_in_response)

    # pylint: disable=invalid-name
    def test_project_list_returns_users_own_project_is_shared_to(self):
        """
        Ensure that the project list responses for project owners
        contains all the users the project has been shared too
        """
        self._project_create()
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)

        share_project = ShareProject(self.project, "alice", "manager")
        share_project.save()

        # Ensure alice is in the list of users
        # When an owner requests for the project data
        req = self.factory.get("/", **self.extra)
        resp = self.view(req)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data[0]["users"]), 2)
        shared_users = [user["user"] for user in resp.data[0]["users"]]
        self.assertIn(alice_profile.user.username, shared_users)

        # Ensure project managers can view all users the project was shared to
        davis_data = {"username": "davis", "email": "davis@localhost.com"}
        davis_profile = self._create_user_profile(davis_data)
        dave_extras = {"HTTP_AUTHORIZATION": f"Token {davis_profile.user.auth_token}"}
        share_project = ShareProject(
            self.project, davis_profile.user.username, "manager"
        )
        share_project.save()

        req = self.factory.get("/", **dave_extras)
        resp = self.view(req)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data[0]["users"]), 3)
        shared_users = [user["user"] for user in resp.data[0]["users"]]
        self.assertIn(alice_profile.user.username, shared_users)
        self.assertIn(self.user.username, shared_users)

    def test_projects_get(self):
        self._project_create()
        view = ProjectViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.project.pk)
        user_props = ["user", "first_name", "last_name", "role", "is_org", "metadata"]
        user_props.sort()

        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)

        # test serialized data
        serializer = ProjectSerializer(self.project, context={"request": request})
        self.assertEqual(response.data, serializer.data)

        self.assertIsNotNone(self.project_data)
        self.assertEqual(response.data, self.project_data)
        res_user_props = list(response.data["users"][0])
        res_user_props.sort()
        self.assertEqual(res_user_props, user_props)

    def test_project_get_deleted_form(self):
        self._publish_xls_form_to_project()

        # set the xform in this project to deleted
        self.xform.deleted_at = self.xform.date_created
        self.xform.save()

        view = ProjectViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.project.pk)

        self.assertEqual(len(response.data.get("forms")), 0)
        self.assertEqual(response.status_code, 200)

    def test_xform_delete_project_forms_endpoint(self):
        self._publish_xls_form_to_project()

        view = ProjectViewSet.as_view({"get": "forms"})
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        # soft delete form
        self.xform.soft_delete(user=self.user)

        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    # pylint: disable=invalid-name
    def test_none_empty_forms_and_dataview_properties_in_returned_json(self):
        self._publish_xls_form_to_project()
        self._create_dataview()

        view = ProjectViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.project.pk)

        self.assertGreater(len(response.data.get("forms")), 0)
        self.assertGreater(len(response.data.get("data_views")), 0)

        form_obj_keys = list(response.data.get("forms")[0])
        data_view_obj_keys = list(response.data.get("data_views")[0])
        self.assertEqual(
            [
                "consumes_entities_from",
                "contributes_entities_to",
                "date_created",
                "downloadable",
                "encrypted",
                "formid",
                "id_string",
                "is_merged_dataset",
                "last_submission_time",
                "last_updated_at",
                "name",
                "num_of_submissions",
                "published_by_formbuilder",
                "url",
            ],
            sorted(form_obj_keys),
        )
        self.assertEqual(
            [
                "columns",
                "dataviewid",
                "date_created",
                "date_modified",
                "instances_with_geopoints",
                "matches_parent",
                "name",
                "project",
                "query",
                "url",
                "xform",
            ],
            sorted(data_view_obj_keys),
        )
        self.assertEqual(response.status_code, 200)

    def test_projects_tags(self):
        self._project_create()
        view = ProjectViewSet.as_view(
            {"get": "labels", "post": "labels", "delete": "labels"}
        )
        list_view = ProjectViewSet.as_view(
            {
                "get": "list",
            }
        )
        project_id = self.project.pk
        # no tags
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=project_id)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.data, [])
        self.assertEqual(get_latest_tags(self.project), [])
        # add tag "hello"
        request = self.factory.post("/", data={"tags": "hello"}, **self.extra)
        response = view(request, pk=project_id)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, ["hello"])
        self.assertEqual(get_latest_tags(self.project), ["hello"])

        # check filter by tag
        request = self.factory.get("/", data={"tags": "hello"}, **self.extra)

        self.project.refresh_from_db()
        request.user = self.user
        self.project_data = BaseProjectSerializer(
            self.project, context={"request": request}
        ).data
        response = list_view(request, pk=project_id)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0], self.project_data)

        request = self.factory.get("/", data={"tags": "goodbye"}, **self.extra)
        response = list_view(request, pk=project_id)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        # remove tag "hello"
        request = self.factory.delete("/", **self.extra)
        response = view(request, pk=project_id, label="hello")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.data, [])
        self.assertEqual(get_latest_tags(self.project), [])

    def test_projects_create(self):
        self._project_create()
        self.assertIsNotNone(self.project_data)

        projects = Project.objects.all()
        self.assertEqual(len(projects), 1)

        for project in projects:
            self.assertEqual(self.user, project.created_by)
            self.assertEqual(self.user, project.organization)

    def test_project_create_other_account(self):  # pylint: disable=invalid-name
        """
        Test that a user cannot create a project in a different user account
        without the right permission.
        """
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        bob = self.user
        self._login_user_and_profile(alice_data)
        data = {
            "name": "Example Project",
            "owner": "http://testserver/api/v1/users/bob",  # Bob
        }

        # Alice should not be able to create the form in bobs account.
        request = self.factory.post("/projects", data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {
                "owner": [
                    f"You do not have permission to create a project "
                    f"in the organization {bob}."
                ]
            },
        )
        self.assertEqual(Project.objects.count(), 0)

        # Give Alice the permission to create a project in Bob's account.
        ManagerRole.add(alice_profile.user, bob.profile)
        request = self.factory.post("/projects", data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)

        projects = Project.objects.all()
        self.assertEqual(len(projects), 1)

        for project in projects:
            # Created by Alice
            self.assertEqual(alice_profile.user, project.created_by)
            # But under Bob's account
            self.assertEqual(bob, project.organization)

    def test_many_projects_are_returned_in_reverse_order_of_creation(self):
        projects = [
            {
                "name": "HealthTrack",
                "owner": f"http://testserver/api/v1/users/{self.user.username}",
            },
            {
                "name": "EduInsights",
                "owner": f"http://testserver/api/v1/users/{self.user.username}",
            },
            {
                "name": "FoodSecure",
                "owner": f"http://testserver/api/v1/users/{self.user.username}",
            },
            {
                "name": "WaterWatch",
                "owner": f"http://testserver/api/v1/users/{self.user.username}",
            },
            {
                "name": "GenderEquity",
                "owner": f"http://testserver/api/v1/users/{self.user.username}",
            },
            {
                "name": "RefugeeAid",
                "owner": f"http://testserver/api/v1/users/{self.user.username}",
            },
            {
                "name": "ClimateResilience",
                "owner": f"http://testserver/api/v1/users/{self.user.username}",
            },
            {
                "name": "HousingForAll",
                "owner": f"http://testserver/api/v1/users/{self.user.username}",
            },
            {
                "name": "YouthEmpower",
                "owner": f"http://testserver/api/v1/users/{self.user.username}",
            },
            {
                "name": "DisasterResponse",
                "owner": f"http://testserver/api/v1/users/{self.user.username}",
            },
        ]

        for project_data in projects:
            self._project_create(project_data=project_data)

        dates_created = [
            {"year": 2019, "month": 7},
            {"year": 2022, "month": 11},
            {"year": 2016, "month": 3},
            {"year": 2021, "month": 5},
            {"year": 2018, "month": 9},
            {"year": 2024, "month": 2},
            {"year": 2017, "month": 12},
            {"year": 2020, "month": 6},
            {"year": 2015, "month": 8},
            {"year": 2023, "month": 4},
        ]

        for date_created, project in zip(
            dates_created,
            Project.objects.filter(organization__username=self.user.username),
        ):
            new_date = datetime(
                year=date_created["year"],
                month=date_created["month"],
                day=1,
                hour=project.date_created.hour,  # Preserve the original hour
                minute=project.date_created.minute,  # Preserve the original minute
                second=project.date_created.second,  # Preserve the original second
            )
            project.date_created = new_date
            project.save()

        # get all projects
        request = self.factory.get(
            "/",
            content_type="application/json",
            **self.extra,
        )
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [
                "2024-02",
                "2023-04",
                "2022-11",
                "2021-05",
                "2020-06",
                "2019-07",
                "2018-09",
                "2017-12",
                "2016-03",
                "2015-08",
            ],
            [project["date_created"][:7] for project in response.data],
        )

        # get paginated projects(page 1)
        request = self.factory.get(
            "/?page=1&page_size=2",
            content_type="application/json",
            **self.extra,
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            ["2024-02", "2023-04"],
            [project["date_created"][:7] for project in response.data],
        )
        self.assertEqual(
            ["RefugeeAid", "DisasterResponse"],
            [project["name"] for project in response.data],
        )

        # get paginated projects(page 4)
        request = self.factory.get(
            "/?page=4&page_size=2",
            content_type="application/json",
            **self.extra,
        )
        self.assertEqual(response.status_code, 200)
        response = self.view(request)
        self.assertEqual(
            ["2018-09", "2017-12"],
            [project["date_created"][:7] for project in response.data],
        )
        self.assertEqual(
            ["GenderEquity", "ClimateResilience"],
            [project["name"] for project in response.data],
        )

        # get paginated projects(page 6)
        request = self.factory.get(
            "/?page=6&page_size=2",
            content_type="application/json",
            **self.extra,
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 404)

    # pylint: disable=invalid-name
    def test_create_duplicate_project(self):
        """
        Test creating a project with the same name
        """
        # data to create project
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

        # current number of projects
        count = Project.objects.count()

        # create project using data
        view = ProjectViewSet.as_view({"post": "create"})
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, owner=self.user.username)
        self.assertEqual(response.status_code, 201)
        after_count = Project.objects.count()
        self.assertEqual(after_count, count + 1)

        # create another project using the same data
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, owner=self.user.username)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {"non_field_errors": ["The fields name, owner must make a unique set."]},
        )
        final_count = Project.objects.count()
        self.assertEqual(after_count, final_count)

    # pylint: disable=invalid-name
    def test_projects_create_no_metadata(self):
        data = {
            "name": "demo",
            "owner": f"http://testserver/api/v1/users/{self.user.username}",
            "public": False,
        }
        self._project_create(project_data=data, merge=False)
        self.assertIsNotNone(self.project)
        self.assertIsNotNone(self.project_data)

        projects = Project.objects.all()
        self.assertEqual(len(projects), 1)

        for project in projects:
            self.assertEqual(self.user, project.created_by)
            self.assertEqual(self.user, project.organization)

    # pylint: disable=invalid-name
    def test_projects_create_many_users(self):
        self._project_create()
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._login_user_and_profile(alice_data)
        self._project_create()
        projects = Project.objects.filter(created_by=self.user)
        self.assertEqual(len(projects), 1)

        for project in projects:
            self.assertEqual(self.user, project.created_by)
            self.assertEqual(self.user, project.organization)

    def test_form_publish_odk_validation_errors(self):
        self._project_create()
        path = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "main",
            "tests",
            "fixtures",
            "transportation",
            "error_test_form.xlsx",
        )
        with open(path, "rb") as xlsx_file:
            view = ProjectViewSet.as_view({"post": "forms"})
            post_data = {"xls_file": xlsx_file}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = view(request, pk=self.project.pk)
            self.assertEqual(response.status_code, 400)
            self.assertIn("ODK Validate Errors:", response.data.get("text"))

    # pylint: disable=invalid-name
    def test_publish_xls_form_to_project(self):
        self._publish_xls_form_to_project()
        project_name = "another project"
        self._project_create({"name": project_name})
        self._publish_xls_form_to_project()

    def test_num_datasets(self):
        self._publish_xls_form_to_project()
        self.project.refresh_from_db()
        request = self.factory.post("/", data={}, **self.extra)
        request.user = self.user
        project_data = ProjectSerializer(
            self.project, context={"request": request}
        ).data
        self.assertEqual(project_data["num_datasets"], 1)

    def test_last_submission_date(self):
        self._publish_xls_form_to_project()
        self._make_submissions()
        request = self.factory.post("/", data={}, **self.extra)
        request.user = self.user
        self.project.refresh_from_db()
        project_data = ProjectSerializer(
            self.project, context={"request": request}
        ).data
        date_created = self.xform.instances.order_by("-date_created").values_list(
            "date_created", flat=True
        )[0]
        self.assertEqual(str(project_data["last_submission_date"]), str(date_created))

    def test_view_xls_form(self):
        self._publish_xls_form_to_project()
        view = ProjectViewSet.as_view({"get": "forms"})
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.project.pk)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)

        resultset = MetaData.objects.filter(
            Q(object_id=self.xform.pk),
            Q(data_type="enketo_url")
            | Q(data_type="enketo_preview_url")  # noqa W503
            | Q(data_type="enketo_single_submit_url"),  # noqa W503
        )
        url = resultset.get(data_type="enketo_url")
        preview_url = resultset.get(data_type="enketo_preview_url")
        single_submit_url = resultset.get(data_type="enketo_single_submit_url")
        form_metadata = sorted(
            [
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
                        ("url", f"http://testserver/api/v1/metadata/{url.pk}"),
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
                            f"http://testserver/api/v1/metadata/{preview_url.pk}",
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
                            f"http://testserver/api/v1/metadata/{single_submit_url.pk}",
                        ),
                        ("date_created", single_submit_url.date_created),
                    ]
                ),
            ],
            key=itemgetter("id"),
        )

        # test metadata content separately
        response_metadata = sorted(
            [dict(item) for item in response.data[0].pop("metadata")],
            key=itemgetter("id"),
        )

        self.assertEqual(response_metadata, form_metadata)

        # remove metadata and date_modified
        self.form_data.pop("metadata")
        self.form_data.pop("date_modified")
        self.form_data.pop("last_updated_at")
        response.data[0].pop("date_modified")
        response.data[0].pop("last_updated_at")
        self.form_data.pop("has_id_string_changed")

        self.assertDictEqual(dict(response.data[0]), dict(self.form_data))

    def test_assign_form_to_project(self):
        view = ProjectViewSet.as_view({"post": "forms", "get": "retrieve"})
        self._publish_xls_form_to_project()
        formid = self.xform.pk
        old_project = self.project
        project_name = "another project"
        self._project_create({"name": project_name})
        self.assertTrue(self.project.name == project_name)

        request = self.factory.get("/", **self.extra)
        response = view(request, pk=old_project.pk)
        self.assertEqual(response.status_code, 200)
        self.assertIn("forms", list(response.data))
        old_project_form_count = len(response.data["forms"])
        old_project_num_datasets = response.data["num_datasets"]

        project_id = self.project.pk
        post_data = {"formid": formid}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = view(request, pk=project_id)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(self.project.xform_set.filter(pk=self.xform.pk))
        self.assertFalse(old_project.xform_set.filter(pk=self.xform.pk))

        # check if form added appears in the project details
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.project.pk)
        self.assertIn("forms", list(response.data))
        self.assertEqual(len(response.data["forms"]), 1)
        self.assertEqual(response.data["num_datasets"], 1)

        # Check if form transferred doesn't appear in the old project
        # details
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=old_project.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["forms"]), old_project_form_count - 1)
        self.assertEqual(response.data["num_datasets"], old_project_num_datasets - 1)

    # pylint: disable=invalid-name
    def test_project_manager_can_assign_form_to_project(self):
        view = ProjectViewSet.as_view({"post": "forms", "get": "retrieve"})
        self._publish_xls_form_to_project()
        # alice user as manager to both projects
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        ShareProject(self.project, "alice", "manager").save()
        self.assertTrue(ManagerRole.user_has_role(alice_profile.user, self.project))

        formid = self.xform.pk
        old_project = self.project
        project_name = "another project"
        self._project_create({"name": project_name})
        self.assertTrue(self.project.name == project_name)
        ShareProject(self.project, "alice", "manager").save()
        self.assertTrue(ManagerRole.user_has_role(alice_profile.user, self.project))
        self._login_user_and_profile(alice_data)

        project_id = self.project.pk
        post_data = {"formid": formid}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = view(request, pk=project_id)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(self.project.xform_set.filter(pk=self.xform.pk))
        self.assertFalse(old_project.xform_set.filter(pk=self.xform.pk))

        # check if form added appears in the project details
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.project.pk)
        self.assertIn("forms", list(response.data))
        self.assertEqual(len(response.data["forms"]), 1)

    # pylint: disable=invalid-name
    def test_project_manager_can_assign_form_to_project_no_perm(self):
        # user must have owner/manager permissions
        view = ProjectViewSet.as_view({"post": "forms", "get": "retrieve"})
        self._publish_xls_form_to_project()
        # alice user is not manager to both projects
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        self.assertFalse(ManagerRole.user_has_role(alice_profile.user, self.project))

        formid = self.xform.pk
        project_name = "another project"
        self._project_create({"name": project_name})
        self.assertTrue(self.project.name == project_name)
        ManagerRole.add(alice_profile.user, self.project)
        self.assertTrue(ManagerRole.user_has_role(alice_profile.user, self.project))
        self._login_user_and_profile(alice_data)

        project_id = self.project.pk
        post_data = {"formid": formid}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = view(request, pk=project_id)
        self.assertEqual(response.status_code, 403)

    # pylint: disable=invalid-name
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_project_users_get_readonly_role_on_add_form(self):
        self._project_create()
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        ReadOnlyRole.add(alice_profile.user, self.project)
        self.assertTrue(ReadOnlyRole.user_has_role(alice_profile.user, self.project))

        with self.captureOnCommitCallbacks(execute=True):
            self._publish_xls_form_to_project()

        alice_profile.refresh_from_db()
        self.assertTrue(ReadOnlyRole.user_has_role(alice_profile.user, self.xform))
        self.assertFalse(OwnerRole.user_has_role(alice_profile.user, self.xform))

    # pylint: disable=invalid-name,too-many-locals
    @patch("onadata.apps.api.viewsets.project_viewset.send_mail")
    def test_reject_form_transfer_if_target_account_has_id_string_already(
        self, mock_send_mail
    ):
        """Test transfer form fails when a form with same id_string exists."""
        # create bob's project and publish a form to it
        self._publish_xls_form_to_project()
        projectid = self.project.pk
        bobs_project = self.project

        # create user alice
        alice_data = {
            "username": "alice",
            "email": "alice@localhost.com",
            "name": "alice",
            "first_name": "alice",
        }
        alice_profile = self._create_user_profile(alice_data)

        # share bob's project with alice
        self.assertFalse(ManagerRole.user_has_role(alice_profile.user, bobs_project))

        data = {
            "username": "alice",
            "role": ManagerRole.name,
            "email_msg": "I have shared the project with you",
        }
        request = self.factory.post("/", data=data, **self.extra)
        view = ProjectViewSet.as_view({"post": "share"})
        response = view(request, pk=projectid)
        self.assertEqual(response.status_code, 204)
        self.assertTrue(mock_send_mail.called)
        self.assertTrue(ManagerRole.user_has_role(alice_profile.user, self.project))
        self.assertTrue(ManagerRole.user_has_role(alice_profile.user, self.xform))

        # log in as alice
        self._login_user_and_profile(extra_post_data=alice_data)

        # publish a form to alice's project that shares an id_string with
        # form published by bob
        publish_data = {"owner": "http://testserver/api/v1/users/alice"}
        self._publish_xls_form_to_project(publish_data=publish_data)

        alices_form = XForm.objects.filter(
            user__username="alice", id_string="transportation_2011_07_25"
        )[0]
        alices_project = alices_form.project
        bobs_form = XForm.objects.filter(
            user__username="bob", id_string="transportation_2011_07_25"
        )[0]
        formid = bobs_form.id

        # try transfering bob's form from bob's project to alice's project
        view = ProjectViewSet.as_view(
            {
                "post": "forms",
            }
        )
        post_data = {"formid": formid}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = view(request, pk=alices_project.id)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data.get("detail"),
            "Form with the same id_string already exists in this account",
        )

        # try transfering bob's form from to alice's other project with
        # no forms
        self._project_create({"name": "another project"})
        new_project_id = self.project.id
        view = ProjectViewSet.as_view(
            {
                "post": "forms",
            }
        )
        post_data = {"formid": formid}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = view(request, pk=new_project_id)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data.get("detail"),
            "Form with the same id_string already exists in this account",
        )

    # pylint: disable=invalid-name
    @patch("onadata.apps.api.viewsets.project_viewset.send_mail")
    def test_allow_form_transfer_if_org_is_owned_by_user(self, mock_send_mail):
        # create bob's project and publish a form to it
        self._publish_xls_form_to_project()
        bobs_project = self.project

        view = ProjectViewSet.as_view({"get": "retrieve"})
        # access bob's project initially to cache the forms list
        request = self.factory.get("/", **self.extra)
        view(request, pk=bobs_project.pk)

        # create an organization with a project
        self._org_create()
        self._project_create(
            {
                "name": "organization_project",
                "owner": "http://testserver/api/v1/users/denoinc",
                "public": False,
            }
        )
        org_project = self.project

        self.assertNotEqual(bobs_project.id, org_project.id)

        # try transfering bob's form to an organization project he created
        view = ProjectViewSet.as_view({"post": "forms", "get": "retrieve"})
        post_data = {"formid": self.xform.id}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = view(request, pk=self.project.id)

        self.assertEqual(response.status_code, 201)

        # test that cached forms of a source project are cleared. Bob had one
        # forms initially and now it's been moved to the org project.
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=bobs_project.pk)
        bobs_results = response.data
        self.assertListEqual(bobs_results.get("forms"), [])

    # pylint: disable=invalid-name
    @patch("onadata.apps.api.viewsets.project_viewset.send_mail")
    def test_handle_integrity_error_on_form_transfer(self, mock_send_mail):
        # create bob's project and publish a form to it
        self._publish_xls_form_to_project()
        xform = self.xform

        # create an organization with a project
        self._org_create()
        self._project_create(
            {
                "name": "organization_project",
                "owner": "http://testserver/api/v1/users/denoinc",
                "public": False,
            }
        )

        # publish form to organization project
        self._publish_xls_form_to_project()

        # try transfering bob's form to an organization project he created
        view = ProjectViewSet.as_view(
            {
                "post": "forms",
            }
        )
        post_data = {"formid": xform.id}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = view(request, pk=self.project.id)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data.get("detail"),
            "Form with the same id_string already exists in this account",
        )

    # pylint: disable=invalid-name
    @patch("onadata.apps.api.viewsets.project_viewset.send_mail")
    def test_form_transfer_when_org_creator_creates_project(self, mock_send_mail):
        projects_count = Project.objects.count()
        xform_count = XForm.objects.count()
        user_bob = self.user

        # create user alice with a project
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        self._login_user_and_profile(alice_data)
        self._project_create(
            {
                "name": "alice's project",
                "owner": (
                    f"http://testserver/api/v1/users/{alice_profile.user.username}"
                ),
                "public": False,
            },
            merge=False,
        )
        self.assertEqual(self.project.created_by, alice_profile.user)
        alice_project = self.project

        # create org owned by bob then make alice admin
        self._login_user_and_profile(
            {"username": user_bob.username, "email": user_bob.email}
        )
        self._org_create()
        self.assertEqual(self.organization.created_by, user_bob)
        view = OrganizationProfileViewSet.as_view({"post": "members"})
        data = {"username": alice_profile.user.username, "role": OwnerRole.name}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, user=self.organization.user.username)
        self.assertEqual(response.status_code, 201)

        owners_team = get_or_create_organization_owners_team(self.organization)
        self.assertIn(alice_profile.user, owners_team.user_set.all())

        # let bob create a project in org
        self._project_create(
            {
                "name": "organization_project",
                "owner": "http://testserver/api/v1/users/denoinc",
                "public": False,
            }
        )
        self.assertEqual(self.project.created_by, user_bob)
        org_project = self.project
        self.assertEqual(Project.objects.count(), projects_count + 2)

        # let alice create a form in her personal project
        self._login_user_and_profile(alice_data)
        self.project = alice_project
        data = {
            "owner": ("http://testserver/api/v1/users/{alice_profile.user.username}"),
            "public": True,
            "public_data": True,
            "description": "transportation_2011_07_25",
            "downloadable": True,
            "allows_sms": False,
            "encrypted": False,
            "sms_id_string": "transportation_2011_07_25",
            "id_string": "transportation_2011_07_25",
            "title": "transportation_2011_07_25",
            "bamboo_dataset": "",
        }
        self._publish_xls_form_to_project(publish_data=data, merge=False)
        self.assertEqual(self.xform.created_by, alice_profile.user)
        self.assertEqual(XForm.objects.count(), xform_count + 1)

        # let alice transfer the form to the organization project
        view = ProjectViewSet.as_view(
            {
                "post": "forms",
            }
        )
        post_data = {"formid": self.xform.id}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = view(request, pk=org_project.id)
        self.assertEqual(response.status_code, 201)

    # pylint: disable=invalid-name
    def test_project_transfer_upgrades_permissions(self):
        """
        Test that existing project permissions are updated when necessary
        on project owner change
        """
        bob = self.user

        # create user alice with a project
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        self._login_user_and_profile(alice_data)
        alice_url = f'http://testserver/api/v1/users/{alice_data["username"]}'
        self._project_create(
            {
                "name": "test project",
                "owner": alice_url,
                "public": False,
            },
            merge=False,
        )
        self.assertEqual(self.project.created_by, alice_profile.user)
        alice_project = self.project

        # Publish a form to Alice's project
        self._publish_xls_form_to_project()
        alice_xform = self.xform

        # Create organization owned by Bob
        self._login_user_and_profile({"username": bob.username, "email": bob.email})
        self._org_create()
        self.assertEqual(self.organization.created_by, bob)

        # Add Alice as admin to Bob's organization
        view = OrganizationProfileViewSet.as_view({"post": "members"})
        data = {"username": alice_profile.user.username, "role": OwnerRole.name}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, user=self.organization.user.username)
        self.assertEqual(response.status_code, 201)

        owners_team = get_or_create_organization_owners_team(self.organization)
        self.assertIn(alice_profile.user, owners_team.user_set.all())

        # Add Jane to Bob's organization with dataentry role
        jane_data = {"username": "jane", "email": "janedoe@example.com"}
        jane_profile = self._create_user_profile(jane_data)
        data = {"username": jane_profile.user.username, "role": DataEntryRole.name}
        request = self.factory.post("/", data=data, **self.extra)
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, user=self.organization.user.username)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            DataEntryRole.user_has_role(jane_profile.user, self.organization)
        )

        # Share project to bob as editor
        data = {"username": bob.username, "role": EditorRole.name}
        view = ProjectViewSet.as_view({"post": "share"})
        alice_auth_token = Token.objects.get(user=alice_profile.user).key
        auth_credentials = {"HTTP_AUTHORIZATION": f"Token {alice_auth_token}"}
        request = self.factory.post("/", data=data, **auth_credentials)
        response = view(request, pk=alice_project.pk)
        self.assertEqual(response.status_code, 204)

        # Transfer project to Bobs Organization
        org_url = f"http://testserver/api/v1/users/{self.organization.user.username}"
        data = {"owner": org_url, "name": alice_project.name}
        view = ProjectViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch("/", data=data, **auth_credentials)
        response = view(request, pk=alice_project.pk)
        self.assertEqual(response.status_code, 200)

        # Admins have owner privileges to the transferred project
        # and forms
        self.assertTrue(OwnerRole.user_has_role(bob, alice_project))
        self.assertTrue(OwnerRole.user_has_role(bob, alice_xform))
        self.assertTrue(OwnerRole.user_has_role(alice_profile.user, alice_project))
        self.assertTrue(OwnerRole.user_has_role(alice_profile.user, alice_xform))

        # Non-admins have readonly privileges to the transferred project
        # and forms
        self.assertTrue(ReadOnlyRole.user_has_role(jane_profile.user, alice_project))
        self.assertTrue(ReadOnlyRole.user_has_role(jane_profile.user, alice_xform))

    # pylint: disable=invalid-name
    @override_settings(ALLOW_PUBLIC_DATASETS=False)
    def test_disallow_public_project_creation(self):
        """
        Test that an error is raised when a user tries to create a public
        project when public projects are disabled.
        """
        view = ProjectViewSet.as_view({"post": "create"})
        data = {
            "name": "demo",
            "owner": f"http://testserver/api/v1/users/{self.user.username}",
            "public": True,
        }
        request = self.factory.post("/", data=data, **self.extra)
        response = view(request, owner=self.user.username)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["public"][0], "Public projects are currently disabled."
        )

    # pylint: disable=invalid-name
    @patch("onadata.apps.api.viewsets.project_viewset.send_mail")
    def test_form_transfer_when_org_admin_not_creator_creates_project(
        self, mock_send_mail
    ):
        projects_count = Project.objects.count()
        xform_count = XForm.objects.count()
        user_bob = self.user

        # create user alice with a project
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        self._login_user_and_profile(alice_data)
        self._project_create(
            {
                "name": "alice's project",
                "owner": (
                    f"http://testserver/api/v1/users/{alice_profile.user.username}"
                ),
                "public": False,
            },
            merge=False,
        )
        self.assertEqual(self.project.created_by, alice_profile.user)
        alice_project = self.project

        # create org owned by bob then make alice admin
        self._login_user_and_profile(
            {"username": user_bob.username, "email": user_bob.email}
        )
        self._org_create()
        self.assertEqual(self.organization.created_by, user_bob)
        view = OrganizationProfileViewSet.as_view({"post": "members"})
        data = {"username": alice_profile.user.username, "role": OwnerRole.name}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, user=self.organization.user.username)
        self.assertEqual(response.status_code, 201)

        owners_team = get_or_create_organization_owners_team(self.organization)
        self.assertIn(alice_profile.user, owners_team.user_set.all())

        # let alice create a project in org
        self._login_user_and_profile(alice_data)
        self._project_create(
            {
                "name": "organization_project",
                "owner": "http://testserver/api/v1/users/denoinc",
                "public": False,
            }
        )
        self.assertEqual(self.project.created_by, alice_profile.user)
        org_project = self.project
        self.assertEqual(Project.objects.count(), projects_count + 2)

        # let alice create a form in her personal project
        self.project = alice_project
        data = {
            "owner": ("http://testserver/api/v1/users/{alice_profile.user.username}"),
            "public": True,
            "public_data": True,
            "description": "transportation_2011_07_25",
            "downloadable": True,
            "allows_sms": False,
            "encrypted": False,
            "sms_id_string": "transportation_2011_07_25",
            "id_string": "transportation_2011_07_25",
            "title": "transportation_2011_07_25",
            "bamboo_dataset": "",
        }
        self._publish_xls_form_to_project(publish_data=data, merge=False)
        self.assertEqual(self.xform.created_by, alice_profile.user)
        self.assertEqual(XForm.objects.count(), xform_count + 1)

        # let alice transfer the form to the organization project
        view = ProjectViewSet.as_view(
            {
                "post": "forms",
            }
        )
        post_data = {"formid": self.xform.id}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = view(request, pk=org_project.id)
        self.assertEqual(response.status_code, 201)

    # pylint: disable=invalid-name
    @patch("onadata.apps.api.viewsets.project_viewset.send_mail")
    def test_project_share_endpoint(self, mock_send_mail):
        # create project and publish form to project
        self._publish_xls_form_to_project()
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        projectid = self.project.pk

        for role_class in ROLES:
            self.assertFalse(role_class.user_has_role(alice_profile.user, self.project))

            data = {
                "username": "alice",
                "role": role_class.name,
                "email_msg": "I have shared the project with you",
            }
            request = self.factory.post("/", data=data, **self.extra)

            view = ProjectViewSet.as_view({"post": "share"})
            response = view(request, pk=projectid)

            self.assertEqual(response.status_code, 204)
            self.assertTrue(mock_send_mail.called)

            self.assertTrue(role_class.user_has_role(alice_profile.user, self.project))
            self.assertTrue(role_class.user_has_role(alice_profile.user, self.xform))
            # Reset the mock called value to False
            mock_send_mail.called = False

            data = {"username": "alice", "role": ""}
            request = self.factory.post("/", data=data, **self.extra)
            response = view(request, pk=projectid)

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get("Cache-Control"), None)
            self.assertFalse(mock_send_mail.called)

            # pylint: disable=protected-access
            role_class._remove_obj_permissions(alice_profile.user, self.project)

    # pylint: disable=invalid-name
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch("onadata.apps.api.viewsets.project_viewset.send_mail")
    def test_project_share_endpoint_form_published_later(self, mock_send_mail):
        # create project
        self._project_create()
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        projectid = self.project.pk

        for role_class in ROLES:
            self.assertFalse(role_class.user_has_role(alice_profile.user, self.project))

            data = {
                "username": "alice",
                "role": role_class.name,
                "email_msg": "I have shared the project with you",
            }
            request = self.factory.post("/", data=data, **self.extra)

            view = ProjectViewSet.as_view({"post": "share"})
            response = view(request, pk=projectid)

            self.assertEqual(response.status_code, 204)
            self.assertTrue(mock_send_mail.called)

            self.assertTrue(role_class.user_has_role(alice_profile.user, self.project))

            # publish form after project sharing
            with self.captureOnCommitCallbacks(execute=True):
                self._publish_xls_form_to_project()

            alice_profile.user.refresh_from_db()
            self.assertTrue(role_class.user_has_role(alice_profile.user, self.xform))
            # Reset the mock called value to False
            mock_send_mail.called = False

            data = {"username": "alice", "role": ""}
            request = self.factory.post("/", data=data, **self.extra)
            response = view(request, pk=projectid)

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get("Cache-Control"), None)
            self.assertFalse(mock_send_mail.called)

            # pylint: disable=protected-access
            role_class._remove_obj_permissions(alice_profile.user, self.project)
            self.xform.delete()

    def test_project_share_remove_user(self):
        self._project_create()
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        view = ProjectViewSet.as_view({"post": "share"})
        projectid = self.project.pk
        role_class = ReadOnlyRole
        data = {"username": "alice", "role": role_class.name}
        request = self.factory.post("/", data=data, **self.extra)
        response = view(request, pk=projectid)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(role_class.user_has_role(alice_profile.user, self.project))

        data["remove"] = True
        request = self.factory.post("/", data=data, **self.extra)
        response = view(request, pk=projectid)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(role_class.user_has_role(alice_profile.user, self.project))

    # pylint: disable=too-many-statements
    def test_project_filter_by_owner(self):
        """
        Test projects endpoint filter by owner.
        """
        self._project_create()
        alice_data = {
            "username": "alice",
            "email": "alice@localhost.com",
            "first_name": "Alice",
            "last_name": "Alice",
        }
        self._login_user_and_profile(alice_data)

        ShareProject(self.project, self.user.username, "readonly").save()

        view = ProjectViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", {"owner": "bob"}, **self.extra)
        response = view(request, pk=self.project.pk)
        request.user = self.user
        self.project.refresh_from_db()
        bobs_project_data = BaseProjectSerializer(
            self.project, context={"request": request}
        ).data

        self._project_create({"name": "another project"})

        # both bob's and alice's projects
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        request = self.factory.get("/", {"owner": "alice"}, **self.extra)
        request.user = self.user
        alice_project_data = BaseProjectSerializer(
            self.project, context={"request": request}
        ).data
        result = [
            {"owner": p.get("owner"), "projectid": p.get("projectid")}
            for p in response.data
        ]
        bob_data = {
            "owner": "http://testserver/api/v1/users/bob",
            "projectid": bobs_project_data.get("projectid"),
        }
        alice_data = {
            "owner": "http://testserver/api/v1/users/alice",
            "projectid": alice_project_data.get("projectid"),
        }
        self.assertIn(bob_data, result)
        self.assertIn(alice_data, result)

        # only bob's project
        request = self.factory.get("/", {"owner": "bob"}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn(bobs_project_data, response.data)
        self.assertNotIn(alice_project_data, response.data)

        # only alice's project
        request = self.factory.get("/", {"owner": "alice"}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(bobs_project_data, response.data)
        self.assertIn(alice_project_data, response.data)

        # none existent user
        request = self.factory.get("/", {"owner": "noone"}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        # authenticated user can view public project
        joe_data = {"username": "joe", "email": "joe@localhost.com"}
        self._login_user_and_profile(joe_data)

        # should not show private projects when filtered by owner
        request = self.factory.get("/", {"owner": "alice"}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(bobs_project_data, response.data)
        self.assertNotIn(alice_project_data, response.data)

        # should show public project when filtered by owner
        self.project.shared = True
        self.project.save()
        request.user = self.user
        alice_project_data = BaseProjectSerializer(
            self.project, context={"request": request}
        ).data

        request = self.factory.get("/", {"owner": "alice"}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn(alice_project_data, response.data)

        # should show deleted project public project when filtered by owner
        self.project.soft_delete()
        request = self.factory.get("/", {"owner": "alice"}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([], response.data)

    def test_project_partial_updates(self):
        self._project_create()
        view = ProjectViewSet.as_view({"patch": "partial_update"})
        projectid = self.project.pk
        metadata = (
            '{"description": "Lorem ipsum",'
            '"location": "Nakuru, Kenya",'
            '"category": "water"'
            "}"
        )
        json_metadata = json.loads(metadata)
        data = {"metadata": metadata}
        request = self.factory.patch("/", data=data, **self.extra)
        response = view(request, pk=projectid)
        project = Project.objects.get(pk=projectid)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(project.metadata, json_metadata)

    # pylint: disable=invalid-name
    def test_cache_updated_on_project_update(self):
        view = ProjectViewSet.as_view({"get": "retrieve", "patch": "partial_update"})
        self._project_create()
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(False, response.data.get("public"))
        cached_project = cache.get(f"{PROJ_OWNER_CACHE}{self.project.pk}")
        self.assertEqual(cached_project, response.data)

        projectid = self.project.pk
        data = {"public": True}
        request = self.factory.patch("/", data=data, **self.extra)
        response = view(request, pk=projectid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(True, response.data.get("public"))
        cached_project = cache.get(f"{PROJ_OWNER_CACHE}{self.project.pk}")
        self.assertEqual(cached_project, response.data)

        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(True, response.data.get("public"))
        cached_project = cache.get(f"{PROJ_OWNER_CACHE}{self.project.pk}")
        self.assertEqual(cached_project, response.data)

    def test_project_put_updates(self):
        self._project_create()
        view = ProjectViewSet.as_view({"put": "update"})
        projectid = self.project.pk
        data = {
            "name": "updated name",
            "owner": f"http://testserver/api/v1/users/{self.user.username}",
            "metadata": {
                "description": "description",
                "location": "Nairobi, Kenya",
                "category": "health",
            },
        }
        data.update({"metadata": json.dumps(data.get("metadata"))})
        request = self.factory.put("/", data=data, **self.extra)
        response = view(request, pk=projectid)
        data.update({"metadata": json.loads(data.get("metadata"))})
        self.assertDictContainsSubset(data, response.data)

    # pylint: disable=invalid-name
    def test_project_partial_updates_to_existing_metadata(self):
        self._project_create()
        view = ProjectViewSet.as_view({"patch": "partial_update"})
        projectid = self.project.pk
        metadata = '{"description": "Changed description"}'
        json_metadata = json.loads(metadata)
        data = {"metadata": metadata}
        request = self.factory.patch("/", data=data, **self.extra)
        response = view(request, pk=projectid)
        project = Project.objects.get(pk=projectid)
        json_metadata.update(project.metadata)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(project.metadata, json_metadata)

    # pylint: disable=invalid-name
    def test_project_update_shared_cascades_to_xforms(self):
        self._publish_xls_form_to_project()
        view = ProjectViewSet.as_view({"patch": "partial_update"})
        projectid = self.project.pk
        data = {"public": "true"}
        request = self.factory.patch("/", data=data, **self.extra)
        response = view(request, pk=projectid)
        xforms_status = XForm.objects.filter(project__pk=projectid).values_list(
            "shared", flat=True
        )
        self.assertTrue(xforms_status[0])
        self.assertEqual(response.status_code, 200)

    def test_project_add_star(self):
        self._project_create()
        self.assertEqual(len(self.project.user_stars.all()), 0)

        view = ProjectViewSet.as_view({"post": "star"})
        request = self.factory.post("/", **self.extra)
        response = view(request, pk=self.project.pk)
        self.project.refresh_from_db()

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.get("Cache-Control"), None)
        self.assertEqual(len(self.project.user_stars.all()), 1)
        self.assertEqual(self.project.user_stars.all()[0], self.user)

    # pylint: disable=invalid-name
    def test_create_project_invalid_metadata(self):
        """
        Make sure that invalid metadata values are outright rejected
        Test fix for: https://github.com/onaio/onadata/issues/977
        """
        view = ProjectViewSet.as_view({"post": "create"})
        data = {
            "name": "demo",
            "owner": f"http://testserver/api/v1/users/{self.user.username}",
            "metadata": "null",
            "public": False,
        }
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, owner=self.user.username)
        self.assertEqual(response.status_code, 400)

    def test_project_delete_star(self):
        self._project_create()

        view = ProjectViewSet.as_view({"delete": "star", "post": "star"})
        request = self.factory.post("/", **self.extra)
        response = view(request, pk=self.project.pk)
        self.project.refresh_from_db()
        self.assertEqual(len(self.project.user_stars.all()), 1)
        self.assertEqual(self.project.user_stars.all()[0], self.user)

        request = self.factory.delete("/", **self.extra)
        response = view(request, pk=self.project.pk)
        self.project.refresh_from_db()

        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(self.project.user_stars.all()), 0)

    def test_project_get_starred_by(self):
        self._project_create()

        # add star as bob
        view = ProjectViewSet.as_view({"get": "star", "post": "star"})
        request = self.factory.post("/", **self.extra)
        response = view(request, pk=self.project.pk)

        # ensure email not shared
        user_profile_data = self.user_profile_data()
        del user_profile_data["email"]
        del user_profile_data["metadata"]

        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._login_user_and_profile(alice_data)

        # add star as alice
        request = self.factory.post("/", **self.extra)
        response = view(request, pk=self.project.pk)

        # get star users as alice
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        alice_profile, bob_profile = sorted(response.data, key=itemgetter("username"))
        self.assertEqual(sorted(bob_profile.items()), sorted(user_profile_data.items()))
        self.assertEqual(alice_profile["username"], "alice")

    def test_user_can_view_public_projects(self):
        public_project = Project(
            name="demo",
            shared=True,
            metadata=json.dumps({"description": ""}),
            created_by=self.user,
            organization=self.user,
        )
        public_project.save()
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._login_user_and_profile(alice_data)

        view = ProjectViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=public_project.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["public"], True)
        self.assertEqual(response.data["projectid"], public_project.pk)
        self.assertEqual(response.data["name"], "demo")

    def test_projects_same_name_diff_case(self):
        data1 = {
            "name": "demo",
            "owner": f"http://testserver/api/v1/users/{self.user.username}",
            "metadata": {
                "description": "Some description",
                "location": "Naivasha, Kenya",
                "category": "governance",
            },
            "public": False,
        }
        self._project_create(project_data=data1, merge=False)
        self.assertIsNotNone(self.project)
        self.assertIsNotNone(self.project_data)

        projects = Project.objects.all()
        self.assertEqual(len(projects), 1)

        data2 = {
            "name": "DEMO",
            "owner": f"http://testserver/api/v1/users/{self.user.username}",
            "metadata": {
                "description": "Some description",
                "location": "Naivasha, Kenya",
                "category": "governance",
            },
            "public": False,
        }
        view = ProjectViewSet.as_view({"post": "create"})

        request = self.factory.post(
            "/", data=json.dumps(data2), content_type="application/json", **self.extra
        )

        response = view(request, owner=self.user.username)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get("Cache-Control"), None)
        projects = Project.objects.all()
        self.assertEqual(len(projects), 1)

        for project in projects:
            self.assertEqual(self.user, project.created_by)
            self.assertEqual(self.user, project.organization)

    def test_projects_get_exception(self):
        view = ProjectViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)

        # does not exists
        response = view(request, pk=11111)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"detail": "Not found."})

        # invalid id
        response = view(request, pk="1w")
        self.assertEqual(response.status_code, 400)
        error_msg = "Invalid value for project_id. It must be a positive integer."
        self.assertEqual(str(response.data["detail"]), error_msg)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_publish_to_public_project(self):
        public_project = Project(
            name="demo",
            shared=True,
            metadata=json.dumps({"description": ""}),
            created_by=self.user,
            organization=self.user,
        )
        public_project.save()
        self.project = public_project

        with self.captureOnCommitCallbacks(execute=True):
            self._publish_xls_form_to_project(public=True)

        self.xform.refresh_from_db()
        self.assertTrue(self.xform.shared)
        self.assertTrue(self.xform.shared_data)

    def test_public_form_private_project(self):
        self.project = Project(
            name="demo",
            shared=False,
            metadata=json.dumps({"description": ""}),
            created_by=self.user,
            organization=self.user,
        )
        self.project.save()
        self._publish_xls_form_to_project()

        self.assertFalse(self.xform.shared)
        self.assertFalse(self.xform.shared_data)
        self.assertFalse(self.project.shared)

        # when xform.shared is true, project settings does not override
        self.xform.shared = True
        self.xform.save()
        self.project.save()
        self.xform.refresh_from_db()
        self.project.refresh_from_db()
        self.assertTrue(self.xform.shared)
        self.assertFalse(self.xform.shared_data)
        self.assertFalse(self.project.shared)

        # when xform.shared_data is true, project settings does not override
        self.xform.shared = False
        self.xform.shared_data = True
        self.xform.save()
        self.project.save()
        self.xform.refresh_from_db()
        self.project.refresh_from_db()
        self.assertFalse(self.xform.shared)
        self.assertTrue(self.xform.shared_data)
        self.assertFalse(self.project.shared)

        # when xform.shared is true, submissions are made,
        # project settings does not override
        self.xform.shared = True
        self.xform.shared_data = False
        self.xform.save()
        self.project.save()
        self._make_submissions()
        self.xform.refresh_from_db()
        self.project.refresh_from_db()
        self.assertTrue(self.xform.shared)
        self.assertFalse(self.xform.shared_data)
        self.assertFalse(self.project.shared)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_publish_to_public_project_public_form(self):
        public_project = Project(
            name="demo",
            shared=True,
            metadata=json.dumps({"description": ""}),
            created_by=self.user,
            organization=self.user,
        )
        public_project.save()
        self.project = public_project
        data = {
            "owner": f"http://testserver/api/v1/users/{self.project.organization.username}",
            "public": True,
            "public_data": True,
            "description": "transportation_2011_07_25",
            "downloadable": True,
            "allows_sms": False,
            "encrypted": False,
            "sms_id_string": "transportation_2011_07_25",
            "id_string": "transportation_2011_07_25",
            "title": "transportation_2011_07_25",
            "bamboo_dataset": "",
        }

        with self.captureOnCommitCallbacks(execute=True):
            self._publish_xls_form_to_project(publish_data=data, merge=False)

        self.xform.refresh_from_db()
        self.assertTrue(self.xform.shared)
        self.assertTrue(self.xform.shared_data)

    def test_project_all_users_can_share_remove_themselves(self):
        self._publish_xls_form_to_project()
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._login_user_and_profile(alice_data)

        view = ProjectViewSet.as_view({"put": "share"})

        data = {"username": "alice", "remove": True}
        for role_name, role_class in iteritems(role.ROLES):
            ShareProject(self.project, "alice", role_name).save()

            self.assertTrue(role_class.user_has_role(self.user, self.project))
            self.assertTrue(role_class.user_has_role(self.user, self.xform))
            data["role"] = role_name

            request = self.factory.put("/", data=data, **self.extra)
            response = view(request, pk=self.project.pk)

            self.assertEqual(response.status_code, 204)

            self.assertFalse(role_class.user_has_role(self.user, self.project))
            self.assertFalse(role_class.user_has_role(self.user, self.xform))

    def test_owner_cannot_remove_self_if_no_other_owner(self):
        self._project_create()

        view = ProjectViewSet.as_view({"put": "share"})

        ManagerRole.add(self.user, self.project)

        tom_data = {"username": "tom", "email": "tom@localhost.com"}
        bob_profile = self._create_user_profile(tom_data)

        OwnerRole.add(bob_profile.user, self.project)

        data = {"username": "tom", "remove": True, "role": "owner"}

        request = self.factory.put("/", data=data, **self.extra)
        response = view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 400)
        error = {"remove": ["Project requires at least one owner"]}
        self.assertEqual(response.data, error)

        self.assertTrue(OwnerRole.user_has_role(bob_profile.user, self.project))

        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        profile = self._create_user_profile(alice_data)

        OwnerRole.add(profile.user, self.project)

        view = ProjectViewSet.as_view({"put": "share"})

        data = {"username": "tom", "remove": True, "role": "owner"}

        request = self.factory.put("/", data=data, **self.extra)
        response = view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 204)

        self.assertFalse(OwnerRole.user_has_role(bob_profile.user, self.project))

    def test_last_date_modified_changes_when_adding_new_form(self):
        self._project_create()
        last_date = self.project.date_modified
        self._publish_xls_form_to_project()

        self.project.refresh_from_db()
        current_last_date = self.project.date_modified

        self.assertNotEqual(last_date, current_last_date)

    def test_anon_project_form_endpoint(self):
        self._project_create()
        self._publish_xls_form_to_project()

        view = ProjectViewSet.as_view({"get": "forms"})

        request = self.factory.get("/")
        response = view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 404)

    def test_anon_project_list_endpoint(self):
        self._project_create()
        self._publish_xls_form_to_project()

        view = ProjectViewSet.as_view({"get": "list"})
        self.project.shared = True
        self.project.save()

        public_projects = Project.objects.filter(shared=True).count()

        request = self.factory.get("/")
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), public_projects)

    def test_project_manager_can_delete_xform(self):
        # create project and publish form to project
        self._publish_xls_form_to_project()
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        alice = alice_profile.user
        projectid = self.project.pk

        self.assertFalse(ManagerRole.user_has_role(alice, self.project))

        data = {
            "username": "alice",
            "role": ManagerRole.name,
            "email_msg": "I have shared the project with you",
        }
        request = self.factory.post("/", data=data, **self.extra)

        view = ProjectViewSet.as_view({"post": "share"})
        response = view(request, pk=projectid)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(ManagerRole.user_has_role(alice, self.project))
        self.assertTrue(alice.has_perm("delete_xform", self.xform))

    def test_move_project_owner(self):
        # create project and publish form to project
        self._publish_xls_form_to_project()

        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        alice = alice_profile.user
        projectid = self.project.pk

        self.assertFalse(OwnerRole.user_has_role(alice, self.project))

        view = ProjectViewSet.as_view({"patch": "partial_update"})

        data_patch = {"owner": f"http://testserver/api/v1/users/{alice.username}"}
        request = self.factory.patch("/", data=data_patch, **self.extra)
        response = view(request, pk=projectid)

        # bob cannot move project if he does not have can_add_project project
        # permission on alice's account.c
        self.assertEqual(response.status_code, 400)

        # Give bob permission.
        ManagerRole.add(self.user, alice_profile)
        request = self.factory.patch("/", data=data_patch, **self.extra)
        response = view(request, pk=projectid)
        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(self.project.organization, alice)
        self.assertTrue(OwnerRole.user_has_role(alice, self.project))

    def test_cannot_share_project_to_owner(self):
        # create project and publish form to project
        self._publish_xls_form_to_project()

        data = {
            "username": self.user.username,
            "role": ManagerRole.name,
            "email_msg": "I have shared the project with you",
        }
        request = self.factory.post("/", data=data, **self.extra)

        view = ProjectViewSet.as_view({"post": "share"})
        response = view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["username"], ["Cannot share project with the owner (bob)"]
        )
        self.assertTrue(OwnerRole.user_has_role(self.user, self.project))

    def test_project_share_readonly(self):
        # create project and publish form to project
        self._publish_xls_form_to_project()
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        projectid = self.project.pk

        self.assertFalse(ReadOnlyRole.user_has_role(alice_profile.user, self.project))

        data = {"username": "alice", "role": ReadOnlyRole.name}
        request = self.factory.put("/", data=data, **self.extra)

        view = ProjectViewSet.as_view({"put": "share"})
        response = view(request, pk=projectid)

        self.assertEqual(response.status_code, 204)

        self.assertTrue(ReadOnlyRole.user_has_role(alice_profile.user, self.project))
        self.assertTrue(ReadOnlyRole.user_has_role(alice_profile.user, self.xform))

        perms = role.get_object_users_with_permissions(self.project)
        for p in perms:
            user = p.get("user")

            if user == alice_profile.user:
                r = p.get("role")
                self.assertEqual(r, ReadOnlyRole.name)

    def test_move_project_owner_org(self):
        # create project and publish form to project
        self._org_create()
        self._publish_xls_form_to_project()

        projectid = self.project.pk

        view = ProjectViewSet.as_view({"patch": "partial_update"})
        old_org = self.project.organization

        data_patch = {
            "owner": f"http://testserver/api/v1/users/{self.organization.user.username}"
        }
        request = self.factory.patch("/", data=data_patch, **self.extra)
        response = view(request, pk=projectid)
        for a in response.data.get("teams"):
            self.assertIsNotNone(a.get("role"))

        self.assertEqual(response.status_code, 200)
        project = Project.objects.get(pk=projectid)

        self.assertNotEqual(old_org, project.organization)

    def test_project_share_inactive_user(self):
        # create project and publish form to project
        self._publish_xls_form_to_project()
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)

        # set the user inactive
        self.assertTrue(alice_profile.user.is_active)
        alice_profile.user.is_active = False
        alice_profile.user.save()

        projectid = self.project.pk

        self.assertFalse(ReadOnlyRole.user_has_role(alice_profile.user, self.project))

        data = {"username": "alice", "role": ReadOnlyRole.name}
        request = self.factory.put("/", data=data, **self.extra)

        view = ProjectViewSet.as_view({"put": "share"})
        response = view(request, pk=projectid)

        self.assertEqual(response.status_code, 400)
        self.assertIsNone(cache.get(safe_key(f"{PROJ_OWNER_CACHE}{self.project.pk}")))
        self.assertEqual(
            response.data,
            {"username": ["The following user(s) is/are not active: alice"]},
        )

        self.assertFalse(ReadOnlyRole.user_has_role(alice_profile.user, self.project))
        self.assertFalse(ReadOnlyRole.user_has_role(alice_profile.user, self.xform))

    def test_project_share_remove_inactive_user(self):
        # create project and publish form to project
        self._publish_xls_form_to_project()
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)

        projectid = self.project.pk

        self.assertFalse(ReadOnlyRole.user_has_role(alice_profile.user, self.project))

        data = {"username": "alice", "role": ReadOnlyRole.name}
        request = self.factory.put("/", data=data, **self.extra)

        view = ProjectViewSet.as_view({"put": "share"})
        response = view(request, pk=projectid)

        self.assertEqual(response.status_code, 204)
        self.assertIsNone(cache.get(safe_key(f"{PROJ_OWNER_CACHE}{self.project.pk}")))

        self.assertTrue(ReadOnlyRole.user_has_role(alice_profile.user, self.project))
        self.assertTrue(ReadOnlyRole.user_has_role(alice_profile.user, self.xform))

        # set the user inactive
        self.assertTrue(alice_profile.user.is_active)
        alice_profile.user.is_active = False
        alice_profile.user.save()

        data = {"username": "alice", "role": ReadOnlyRole.name, "remove": True}
        request = self.factory.put("/", data=data, **self.extra)

        self.assertEqual(response.status_code, 204)

        self.assertFalse(ReadOnlyRole.user_has_role(alice_profile.user, self.project))
        self.assertFalse(ReadOnlyRole.user_has_role(alice_profile.user, self.xform))

    def test_project_share_readonly_no_downloads(self):
        # create project and publish form to project
        self._publish_xls_form_to_project()
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)

        tom_data = {"username": "tom", "email": "tom@localhost.com"}
        tom_data = self._create_user_profile(tom_data)
        projectid = self.project.pk

        self.assertFalse(
            ReadOnlyRoleNoDownload.user_has_role(alice_profile.user, self.project)
        )

        data = {"username": "alice", "role": ReadOnlyRoleNoDownload.name}
        request = self.factory.post("/", data=data, **self.extra)

        view = ProjectViewSet.as_view({"post": "share", "get": "retrieve"})
        response = view(request, pk=projectid)

        self.assertEqual(response.status_code, 204)

        data = {"username": "tom", "role": ReadOnlyRole.name}
        request = self.factory.post("/", data=data, **self.extra)

        response = view(request, pk=projectid)

        self.assertEqual(response.status_code, 204)

        request = self.factory.get("/", **self.extra)

        response = view(request, pk=self.project.pk)

        # get the users
        users = response.data.get("users")

        self.assertEqual(len(users), 3)

        for user in users:
            if user.get("user") == "bob":
                self.assertEqual(user.get("role"), "owner")
            elif user.get("user") == "alice":
                self.assertEqual(user.get("role"), "readonly-no-download")
            elif user.get("user") == "tom":
                self.assertEqual(user.get("role"), "readonly")

    def test_team_users_in_a_project(self):
        self._team_create()
        project = Project.objects.create(
            name="Test Project",
            organization=self.team.organization,
            created_by=self.user,
            metadata="{}",
        )

        chuck_data = {"username": "chuck", "email": "chuck@localhost.com"}
        chuck_profile = self._create_user_profile(chuck_data)
        user_chuck = chuck_profile.user

        view = TeamViewSet.as_view({"post": "share"})

        self.assertFalse(EditorRole.user_has_role(user_chuck, project))
        data = {"role": EditorRole.name, "project": project.pk}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 204)
        tools.add_user_to_team(self.team, user_chuck)
        self.assertTrue(EditorRole.user_has_role(user_chuck, project))

        view = ProjectViewSet.as_view({"get": "retrieve"})

        request = self.factory.get("/", **self.extra)

        response = view(request, pk=project.pk)

        self.assertIsNotNone(response.data["teams"])
        self.assertEqual(3, len(response.data["teams"]))
        self.assertEqual(response.data["teams"][2]["role"], "editor")
        self.assertEqual(
            response.data["teams"][2]["users"][0], str(chuck_profile.user.username)
        )

    def test_project_accesible_by_admin_created_by_diff_admin(self):
        self._org_create()

        # user 1
        chuck_data = {"username": "chuck", "email": "chuck@localhost.com"}
        chuck_profile = self._create_user_profile(chuck_data)

        # user 2
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)

        view = OrganizationProfileViewSet.as_view(
            {
                "post": "members",
            }
        )

        # save the org creator
        bob = self.user

        data = json.dumps(
            {"username": alice_profile.user.username, "role": OwnerRole.name}
        )
        # create admin 1
        request = self.factory.post(
            "/", data=data, content_type="application/json", **self.extra
        )
        response = view(request, user="denoinc")

        self.assertEqual(201, response.status_code)
        data = json.dumps(
            {"username": chuck_profile.user.username, "role": OwnerRole.name}
        )
        # create admin 2
        request = self.factory.post(
            "/", data=data, content_type="application/json", **self.extra
        )
        response = view(request, user="denoinc")

        self.assertEqual(201, response.status_code)

        # admin 2 creates a project
        self.user = chuck_profile.user
        self.extra = {"HTTP_AUTHORIZATION": f"Token {self.user.auth_token}"}
        data = {
            "name": "demo",
            "owner": f"http://testserver/api/v1/users/{self.organization.user.username}",
            "metadata": {
                "description": "Some description",
                "location": "Naivasha, Kenya",
                "category": "governance",
            },
            "public": False,
        }
        self._project_create(project_data=data)

        view = ProjectViewSet.as_view({"get": "retrieve"})

        # admin 1 tries to access project created by admin 2
        self.user = alice_profile.user
        self.extra = {"HTTP_AUTHORIZATION": f"Token {self.user.auth_token}"}
        request = self.factory.get("/", **self.extra)

        response = view(request, pk=self.project.pk)

        self.assertEqual(200, response.status_code)

        # assert admin can add colaborators
        tompoo_data = {"username": "tompoo", "email": "tompoo@localhost.com"}
        self._create_user_profile(tompoo_data)

        data = {"username": "tompoo", "role": ReadOnlyRole.name}
        request = self.factory.put("/", data=data, **self.extra)

        view = ProjectViewSet.as_view({"put": "share"})
        response = view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 204)

        self.user = bob
        self.extra = {"HTTP_AUTHORIZATION": f"Token {bob.auth_token}"}

        # remove from admin org
        data = json.dumps({"username": alice_profile.user.username})
        view = OrganizationProfileViewSet.as_view({"delete": "members"})

        request = self.factory.delete(
            "/", data=data, content_type="application/json", **self.extra
        )
        response = view(request, user="denoinc")
        self.assertEqual(200, response.status_code)

        view = ProjectViewSet.as_view({"get": "retrieve"})

        self.user = alice_profile.user
        self.extra = {"HTTP_AUTHORIZATION": f"Token {self.user.auth_token}"}
        request = self.factory.get("/", **self.extra)

        response = view(request, pk=self.project.pk)

        # user cant access the project removed from org
        self.assertEqual(404, response.status_code)

    def test_public_project_on_creation(self):
        view = ProjectViewSet.as_view({"post": "create"})

        data = {
            "name": "demopublic",
            "owner": f"http://testserver/api/v1/users/{self.user.username}",
            "metadata": {
                "description": "Some description",
                "location": "Naivasha, Kenya",
                "category": "governance",
            },
            "public": True,
        }

        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, owner=self.user.username)
        self.assertEqual(response.status_code, 201)
        project = Project.prefetched.filter(name=data["name"], created_by=self.user)[0]

        self.assertTrue(project.shared)

    def test_permission_passed_to_dataview_parent_form(self):
        self._project_create()
        project1 = self.project
        self._publish_xls_form_to_project()
        data = {
            "name": "demo2",
            "owner": f"http://testserver/api/v1/users/{self.user.username}",
            "metadata": {
                "description": "Some description",
                "location": "Naivasha, Kenya",
                "category": "governance",
            },
            "public": False,
        }
        self._project_create(data)
        project2 = self.project

        columns = json.dumps(self.xform.get_field_name_xpaths_only())

        data = {
            "name": "My DataView",
            "xform": f"http://testserver/api/v1/forms/{self.xform.pk}",
            "project": f"http://testserver/api/v1/projects/{project2.pk}",
            "columns": columns,
            "query": "[ ]",
        }
        self._create_dataview(data)

        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._login_user_and_profile(alice_data)

        view = ProjectViewSet.as_view({"put": "share"})

        data = {"username": "alice", "remove": True}
        for role_name, role_class in iteritems(role.ROLES):
            ShareProject(self.project, "alice", role_name).save()

            self.assertFalse(role_class.user_has_role(self.user, project1))
            self.assertTrue(role_class.user_has_role(self.user, project2))
            self.assertTrue(role_class.user_has_role(self.user, self.xform))
            data["role"] = role_name

            request = self.factory.put("/", data=data, **self.extra)
            response = view(request, pk=self.project.pk)

            self.assertEqual(response.status_code, 204)

            self.assertFalse(role_class.user_has_role(self.user, project1))
            self.assertFalse(role_class.user_has_role(self.user, self.project))
            self.assertFalse(role_class.user_has_role(self.user, self.xform))

    def test_permission_not_passed_to_dataview_parent_form(self):
        self._project_create()
        project1 = self.project
        self._publish_xls_form_to_project()
        data = {
            "name": "demo2",
            "owner": f"http://testserver/api/v1/users/{self.user.username}",
            "metadata": {
                "description": "Some description",
                "location": "Naivasha, Kenya",
                "category": "governance",
            },
            "public": False,
        }
        self._project_create(data)
        project2 = self.project

        data = {
            "name": "My DataView",
            "xform": f"http://testserver/api/v1/forms/{self.xform.pk}",
            "project": f"http://testserver/api/v1/projects/{project2.pk}",
            "columns": '["name", "age", "gender"]',
            "query": '[{"column":"age","filter":">","value":"20"},'
            '{"column":"age","filter":"<","value":"50"}]',
        }

        self._create_dataview(data)

        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._login_user_and_profile(alice_data)

        view = ProjectViewSet.as_view({"put": "share"})

        data = {"username": "alice", "remove": True}
        for role_name, role_class in iteritems(role.ROLES):
            ShareProject(self.project, "alice", role_name).save()

            self.assertFalse(role_class.user_has_role(self.user, project1))
            self.assertTrue(role_class.user_has_role(self.user, project2))
            self.assertFalse(role_class.user_has_role(self.user, self.xform))
            data["role"] = role_name

            request = self.factory.put("/", data=data, **self.extra)
            response = view(request, pk=self.project.pk)

            self.assertEqual(response.status_code, 204)

            self.assertFalse(role_class.user_has_role(self.user, project1))
            self.assertFalse(role_class.user_has_role(self.user, self.project))
            self.assertFalse(role_class.user_has_role(self.user, self.xform))

    def test_project_share_xform_meta_perms(self):
        # create project and publish form to project
        self._publish_xls_form_to_project()
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        projectid = self.project.pk

        data_value = "editor-minor|dataentry"

        MetaData.xform_meta_permission(self.xform, data_value=data_value)

        for role_class in ROLES_ORDERED:
            self.assertFalse(role_class.user_has_role(alice_profile.user, self.project))

            data = {"username": "alice", "role": role_class.name}
            request = self.factory.post("/", data=data, **self.extra)

            view = ProjectViewSet.as_view({"post": "share"})
            response = view(request, pk=projectid)

            self.assertEqual(response.status_code, 204)

            self.assertTrue(role_class.user_has_role(alice_profile.user, self.project))

            if role_class in [EditorRole, EditorMinorRole]:
                self.assertFalse(
                    EditorRole.user_has_role(alice_profile.user, self.xform)
                )
                self.assertTrue(
                    EditorMinorRole.user_has_role(alice_profile.user, self.xform)
                )

            elif role_class in [DataEntryRole, DataEntryMinorRole, DataEntryOnlyRole]:
                self.assertTrue(
                    DataEntryRole.user_has_role(alice_profile.user, self.xform)
                )

            else:
                self.assertTrue(
                    role_class.user_has_role(alice_profile.user, self.xform)
                )

    @patch("onadata.apps.api.viewsets.project_viewset.send_mail")
    def test_project_share_atomicity(self, mock_send_mail):
        # create project and publish form to project
        self._publish_xls_form_to_project()
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        alice = alice_profile.user
        projectid = self.project.pk

        role_class = DataEntryOnlyRole
        self.assertFalse(role_class.user_has_role(alice_profile.user, self.project))

        data = {
            "username": "alice",
            "role": role_class.name,
            "email_msg": "I have shared the project with you",
        }
        request = self.factory.post("/", data=data, **self.extra)

        view = ProjectViewSet.as_view({"post": "share"})
        response = view(request, pk=projectid)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(mock_send_mail.called)

        self.assertTrue(role_class.user_has_role(alice, self.project))
        self.assertTrue(role_class.user_has_role(alice, self.xform))

        data["remove"] = True
        request = self.factory.post("/", data=data, **self.extra)

        mock_rm_xform_perms = MagicMock()
        with patch(
            "onadata.libs.models.share_project.remove_xform_permissions",
            mock_rm_xform_perms,
        ):  # noqa
            mock_rm_xform_perms.side_effect = Exception()
            response = view(request, pk=projectid)
            # permissions have not changed for both xform and project
            self.assertTrue(role_class.user_has_role(alice, self.xform))
            self.assertTrue(role_class.user_has_role(alice, self.project))
            self.assertTrue(mock_rm_xform_perms.called)

        request = self.factory.post("/", data=data, **self.extra)
        response = view(request, pk=projectid)
        self.assertEqual(response.status_code, 204)
        # permissions have changed for both project and xform
        self.assertFalse(role_class.user_has_role(alice, self.project))
        self.assertFalse(role_class.user_has_role(alice, self.xform))

    def test_project_list_by_owner(self):
        # create project and publish form to project
        sluggie_data = {"username": "sluggie", "email": "sluggie@localhost.com"}
        self._login_user_and_profile(sluggie_data)
        self._publish_xls_form_to_project()

        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)

        projectid = self.project.pk

        self.assertFalse(ReadOnlyRole.user_has_role(alice_profile.user, self.project))

        data = {"username": "alice", "role": ReadOnlyRole.name}
        request = self.factory.put("/", data=data, **self.extra)

        view = ProjectViewSet.as_view({"put": "share", "get": "list"})
        response = view(request, pk=projectid)

        self.assertEqual(response.status_code, 204)
        self.assertIsNone(cache.get(safe_key(f"{PROJ_OWNER_CACHE}{self.project.pk}")))

        self.assertTrue(ReadOnlyRole.user_has_role(alice_profile.user, self.project))
        self.assertTrue(ReadOnlyRole.user_has_role(alice_profile.user, self.xform))

        # Should list collaborators
        data = {"owner": "sluggie"}
        request = self.factory.get("/", data=data, **self.extra)
        response = view(request)

        users = response.data[0]["users"]
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            {
                "first_name": "Bob",
                "last_name": "erama",
                "is_org": False,
                "role": "readonly",
                "user": "alice",
                "metadata": {},
            },
            users,
        )

    def test_projects_soft_delete(self):
        self._project_create()

        view = ProjectViewSet.as_view({"get": "list", "delete": "destroy"})

        request = self.factory.get("/", **self.extra)
        request.user = self.user
        response = view(request)

        project_id = self.project.pk

        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        serializer = BaseProjectSerializer(self.project, context={"request": request})

        self.assertEqual(response.data, [serializer.data])
        self.assertIn("created_by", list(response.data[0]))

        request = self.factory.delete("/", **self.extra)
        request.user = self.user
        response = view(request, pk=project_id)
        self.assertEqual(response.status_code, 204)

        self.project = Project.objects.get(pk=project_id)

        self.assertIsNotNone(self.project.deleted_at)
        self.assertTrue("deleted-at" in self.project.name)
        self.assertEqual(self.project.deleted_by, self.user)

        request = self.factory.get("/", **self.extra)
        request.user = self.user
        response = view(request)

        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)

        self.assertFalse(serializer.data in response.data)

    def test_project_share_multiple_users(self):
        """
        Test that the project can be shared to multiple users
        """
        self._publish_xls_form_to_project()
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)

        tom_data = {"username": "tom", "email": "tom@localhost.com"}
        tom_profile = self._create_user_profile(tom_data)
        projectid = self.project.pk

        self.assertFalse(ReadOnlyRole.user_has_role(alice_profile.user, self.project))
        self.assertFalse(ReadOnlyRole.user_has_role(tom_profile.user, self.project))

        data = {"username": "alice,tom", "role": ReadOnlyRole.name}
        request = self.factory.post("/", data=data, **self.extra)

        view = ProjectViewSet.as_view({"post": "share", "get": "retrieve"})
        response = view(request, pk=projectid)

        self.assertEqual(response.status_code, 204)

        request = self.factory.get("/", **self.extra)

        response = view(request, pk=self.project.pk)

        # get the users
        users = response.data.get("users")

        self.assertEqual(len(users), 3)

        for user in users:
            if user.get("user") == "bob":
                self.assertEqual(user.get("role"), "owner")
            else:
                self.assertEqual(user.get("role"), "readonly")

    @patch("onadata.apps.api.viewsets.project_viewset.send_mail")
    def test_sends_mail_on_multi_share(self, mock_send_mail):
        """
        Test that on sharing a projects to multiple users mail is sent to all
        of them
        """
        # create project and publish form to project
        self._publish_xls_form_to_project()
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        tom_data = {"username": "tom", "email": "tom@localhost.com"}
        tom_profile = self._create_user_profile(tom_data)
        projectid = self.project.pk

        self.assertFalse(ReadOnlyRole.user_has_role(alice_profile.user, self.project))
        self.assertFalse(ReadOnlyRole.user_has_role(tom_profile.user, self.project))

        data = {
            "username": "alice,tom",
            "role": ReadOnlyRole.name,
            "email_msg": "I have shared the project with you",
        }
        request = self.factory.post("/", data=data, **self.extra)

        view = ProjectViewSet.as_view({"post": "share"})
        response = view(request, pk=projectid)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(mock_send_mail.called)
        self.assertEqual(mock_send_mail.call_count, 2)

        self.assertTrue(ReadOnlyRole.user_has_role(alice_profile.user, self.project))
        self.assertTrue(ReadOnlyRole.user_has_role(alice_profile.user, self.xform))
        self.assertTrue(ReadOnlyRole.user_has_role(tom_profile.user, self.project))
        self.assertTrue(ReadOnlyRole.user_has_role(tom_profile.user, self.xform))

    def test_project_caching(self):
        """
        Test project viewset caching always keeps the latest version of
        the project in cache
        """
        view = ProjectViewSet.as_view({"post": "forms", "get": "retrieve"})
        self._publish_xls_form_to_project()

        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["forms"]), 1)
        self.assertEqual(response.data["forms"][0]["name"], self.xform.title)
        self.assertEqual(
            response.data["forms"][0]["last_submission_time"],
            self.xform.time_of_last_submission(),
        )
        self.assertEqual(
            response.data["forms"][0]["num_of_submissions"],
            self.xform.num_of_submissions,
        )
        self.assertEqual(response.data["num_datasets"], 1)

        # Test on form detail update data returned from project viewset is
        # updated
        form_view = XFormViewSet.as_view({"patch": "partial_update"})
        post_data = {"title": "new_name"}
        request = self.factory.patch("/", data=post_data, **self.extra)
        response = form_view(request, pk=self.xform.pk)
        self.assertEqual(response.status_code, 200)
        self.xform.refresh_from_db()

        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["forms"]), 1)
        self.assertEqual(response.data["forms"][0]["name"], self.xform.title)
        self.assertEqual(
            response.data["forms"][0]["last_submission_time"],
            self.xform.time_of_last_submission(),
        )
        self.assertEqual(
            response.data["forms"][0]["num_of_submissions"],
            self.xform.num_of_submissions,
        )
        self.assertEqual(response.data["num_datasets"], 1)

        # Test that last_submission_time is updated correctly
        self._make_submissions()
        self.xform.refresh_from_db()
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["forms"]), 1)
        self.assertEqual(response.data["forms"][0]["name"], self.xform.title)
        self.assertIsNotNone(response.data["forms"][0]["last_submission_time"])
        returned_date = dateutil.parser.parse(
            response.data["forms"][0]["last_submission_time"]
        )
        self.assertEqual(returned_date, self.xform.time_of_last_submission())
        self.assertEqual(
            response.data["forms"][0]["num_of_submissions"],
            self.xform.num_of_submissions,
        )
        self.assertEqual(response.data["num_datasets"], 1)

    def test_get_project_w_registration_form(self):
        """Retrieve project with Entity registtraton form"""
        self._publish_registration_form(self.user)
        view = ProjectViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.project.pk)
        entity_list = EntityList.objects.first()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["forms"][0]["contributes_entities_to"],
            {
                "id": entity_list.pk,
                "name": "trees",
                "is_active": True,
            },
        )
        # Soft delete dataset
        entity_list.soft_delete()
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["forms"][0]["contributes_entities_to"])

    def test_get_project_w_follow_up_form(self):
        """Retrieve project with Entity follow up form"""
        self.project = get_user_default_project(self.user)
        entity_list = EntityList.objects.create(name="trees", project=self.project)
        self._publish_follow_up_form(self.user)
        view = ProjectViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["forms"][0]["consumes_entities_from"],
            [
                {
                    "id": entity_list.pk,
                    "name": "trees",
                    "is_active": True,
                }
            ],
        )
        # Soft delete dataset
        entity_list.soft_delete()
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["forms"][0]["consumes_entities_from"], [])


class GetProjectInvitationListTestCase(TestAbstractViewSet):
    """Tests for get project invitation list"""

    def setUp(self):
        super().setUp()
        self._project_create()
        self.view = ProjectViewSet.as_view({"get": "invitations"})

    def test_authentication(self):
        """Authentication is required"""
        request = self.factory.get("/")
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 404)

    def test_invalid_project(self):
        """Invalid project is handled"""
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=817)
        self.assertEqual(response.status_code, 404)

    def test_only_admins_allowed(self):
        """Only project admins are allowed to get invitation list"""
        # login as editor alice
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        self._login_user_and_profile(alice_data)
        request = self.factory.get("/", **self.extra)

        # only owner and manager roles have permission
        for role_class in ROLES_ORDERED:
            ShareProject(self.project, "alice", role_class.name).save()
            self.assertTrue(role_class.user_has_role(alice_profile.user, self.project))
            response = self.view(request, pk=self.project.pk)

            if role_class.name in [ManagerRole.name, OwnerRole.name]:
                self.assertEqual(response.status_code, 200)
            else:
                self.assertEqual(response.status_code, 403)

    def test_invitation_list(self):
        """Returns project invitation list"""
        jane_invitation = ProjectInvitation.objects.create(
            email="janedoe@example.com",
            project=self.project,
            role="editor",
            status=ProjectInvitation.Status.PENDING,
        )
        john_invitation = ProjectInvitation.objects.create(
            email="johndoe@example.com",
            project=self.project,
            role="editor",
            status=ProjectInvitation.Status.ACCEPTED,
        )
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.project.pk)
        expected_response = [
            {
                "id": jane_invitation.pk,
                "email": "janedoe@example.com",
                "role": "editor",
                "status": 1,
            },
            {
                "id": john_invitation.pk,
                "email": "johndoe@example.com",
                "role": "editor",
                "status": 2,
            },
        ]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected_response)

    def test_no_invitations_available(self):
        """Returns an empty list if no invitations available"""
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_status_query_param_works(self):
        """Filtering by status query parameter works"""
        jane_invitation = ProjectInvitation.objects.create(
            email="janedoe@example.com",
            project=self.project,
            role="editor",
            status=ProjectInvitation.Status.PENDING,
        )
        ProjectInvitation.objects.create(
            email="johndoe@example.com",
            project=self.project,
            role="editor",
            status=ProjectInvitation.Status.ACCEPTED,
        )
        request = self.factory.get("/", data={"status": "1"}, **self.extra)
        response = self.view(request, pk=self.project.pk)
        expected_response = [
            {
                "id": jane_invitation.pk,
                "email": "janedoe@example.com",
                "role": "editor",
                "status": 1,
            }
        ]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected_response)


@patch(
    "onadata.libs.serializers.project_invitation_serializer.send_project_invitation_email_async.delay"
)
class CreateProjectInvitationTestCase(TestAbstractViewSet):
    """Tests for create project invitation"""

    def setUp(self):
        super().setUp()
        self._project_create()
        self.view = ProjectViewSet.as_view({"post": "invitations"})

    def test_authentication(self, mock_send_mail):
        """Authentication is required"""
        request = self.factory.post("/", data={})
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 401)

    def test_invalid_project(self, mock_send_mail):
        """Invalid project is handled"""
        request = self.factory.post("/", data={}, **self.extra)
        response = self.view(request, pk=817)
        self.assertEqual(response.status_code, 404)

    def test_only_admins_allowed(self, mock_send_mail):
        """Only project admins are allowed to create project invitation"""
        # login as editor alice
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        self._login_user_and_profile(alice_data)
        request = self.factory.post("/", data={}, **self.extra)

        # only owner and manager roles have permission
        for role_class in ROLES_ORDERED:
            ShareProject(self.project, "alice", role_class.name).save()
            self.assertTrue(role_class.user_has_role(alice_profile.user, self.project))
            response = self.view(request, pk=self.project.pk)

            if role_class.name in [ManagerRole.name, OwnerRole.name]:
                self.assertEqual(response.status_code, 400)
            else:
                self.assertEqual(response.status_code, 403)

    @override_settings(
        PROJECT_INVITATION_URL={
            "*": "https://example.com/register",
            "onadata.com": "https://onadata.com/register",
        }
    )
    @override_settings(ALLOWED_HOSTS=["*"])
    def test_create_invitation(self, mock_send_mail):
        """Project invitation can be created"""
        post_data = {
            "email": "janedoe@example.com",
            "role": "editor",
        }
        request = self.factory.post(
            "/",
            data=json.dumps(post_data),
            content_type="application/json",
            **self.extra,
        )
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.project.invitations.count(), 1)
        invitation = self.project.invitations.first()
        self.assertEqual(
            response.data,
            {
                "id": invitation.pk,
                "email": "janedoe@example.com",
                "role": "editor",
                "status": 1,
            },
        )
        mock_send_mail.assert_called_once_with(
            invitation.pk, "https://example.com/register"
        )
        self.assertEqual(invitation.invited_by, self.user)

        # duplicate invitation not allowed
        request = self.factory.post(
            "/",
            data=json.dumps(post_data),
            content_type="application/json",
            **self.extra,
        )
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 400)

        # Project invitations are created for non-default host
        post_data = {
            "email": "bobalice@onadata.com",
            "role": "editor",
        }
        request = self.factory.post(
            "/",
            data=json.dumps(post_data),
            content_type="application/json",
            **self.extra,
        )
        request.META["HTTP_HOST"] = "onadata.com"
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.project.invitations.count(), 2)
        invitation = self.project.invitations.last()
        self.assertEqual(
            response.data,
            {
                "id": invitation.pk,
                "email": "bobalice@onadata.com",
                "role": "editor",
                "status": 1,
            },
        )
        mock_send_mail.assert_called_with(invitation.pk, "https://onadata.com/register")

    def test_email_required(self, mock_send_mail):
        """email is required"""
        # blank string
        post_data = {"email": "", "role": "editor"}
        request = self.factory.post(
            "/",
            data=json.dumps(post_data),
            content_type="application/json",
            **self.extra,
        )
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 400)

        # missing field
        post_data = {"role": "editor"}
        request = self.factory.post(
            "/",
            data=json.dumps(post_data),
            content_type="application/json",
            **self.extra,
        )
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 400)
        mock_send_mail.assert_not_called()

    def test_email_valid(self, mock_send_mail):
        """email should be a valid email"""
        # a valid email
        post_data = {"email": "akalkal", "role": "editor"}
        request = self.factory.post(
            "/",
            data=json.dumps(post_data),
            content_type="application/json",
            **self.extra,
        )
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 400)
        mock_send_mail.assert_not_called()

    @override_settings(PROJECT_INVITATION_EMAIL_DOMAIN_WHITELIST=["foo.com"])
    def test_email_whitelist(self, mock_send_mail):
        """Email address domain whitelist works"""
        # email domain should be in whitelist
        post_data = {"email": "janedoe@xample.com", "role": "editor"}
        request = self.factory.post(
            "/",
            data=json.dumps(post_data),
            content_type="application/json",
            **self.extra,
        )
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 400)

        # email in whitelist is successful
        post_data = {"email": "janedoe@foo.com", "role": "editor"}
        request = self.factory.post(
            "/",
            data=json.dumps(post_data),
            content_type="application/json",
            **self.extra,
        )
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        mock_send_mail.assert_called_once()

    @override_settings(PROJECT_INVITATION_EMAIL_DOMAIN_WHITELIST=["FOo.com"])
    def test_email_whitelist_case_insenstive(self, mock_send_mail):
        """Email domain whitelist check should be case insenstive"""
        post_data = {"email": "janedoe@FOO.com", "role": "editor"}
        request = self.factory.post(
            "/",
            data=json.dumps(post_data),
            content_type="application/json",
            **self.extra,
        )
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        mock_send_mail.assert_called_once()

    def test_user_unregistered(self, mock_send_mail):
        """You cannot invite an existing user

        The email should be of a user who is not registered
        """
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._create_user_profile(alice_data)
        post_data = {"email": alice_data["email"], "role": "editor"}
        request = self.factory.post(
            "/",
            data=json.dumps(post_data),
            content_type="application/json",
            **self.extra,
        )
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 400)
        mock_send_mail.assert_not_called()

    def test_role_required(self, mock_send_mail):
        """role field is required"""
        # blank role
        post_data = {"email": "janedoe@example.com", "role": ""}
        request = self.factory.post(
            "/",
            data=json.dumps(post_data),
            content_type="application/json",
            **self.extra,
        )
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 400)

        # missing role
        post_data = {"email": "janedoe@example.com"}
        request = self.factory.post(
            "/",
            data=json.dumps(post_data),
            content_type="application/json",
            **self.extra,
        )
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 400)
        mock_send_mail.assert_not_called()

    def test_role_valid(self, mock_send_mail):
        """Role should be a valid choice"""
        post_data = {"email": "janedoe@example.com", "role": "abracadbra"}
        request = self.factory.post(
            "/",
            data=json.dumps(post_data),
            content_type="application/json",
            **self.extra,
        )
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 400)
        mock_send_mail.assert_not_called()


@patch(
    "onadata.libs.serializers.project_invitation_serializer.send_project_invitation_email_async.delay"
)
class UpdateProjectInvitationTestCase(TestAbstractViewSet):
    """Tests for update project invitation"""

    def setUp(self):
        super().setUp()
        self._project_create()
        self.view = ProjectViewSet.as_view({"put": "invitations"})
        self.invitation = self.project.invitations.create(
            email="janedoe@example.com",
            role="editor",
            status=ProjectInvitation.Status.PENDING,
        )

    def test_authentication(self, mock_send_mail):
        """Authentication is required"""
        request = self.factory.put("/", data={})
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 401)

    def test_invalid_project(self, mock_send_mail):
        """Invalid project is handled"""
        request = self.factory.put("/", data={}, **self.extra)
        response = self.view(request, pk=817)
        self.assertEqual(response.status_code, 404)

    def test_invalid_invitation_id(self, mock_send_mail):
        """Invalid project invitation is handled"""
        request = self.factory.put("/", data={}, **self.extra)
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 404)

    def test_only_admins_allowed(self, mock_send_mail):
        """Only project admins are allowed to update project invitation"""
        # login as editor alice
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        self._login_user_and_profile(alice_data)
        request = self.factory.put(
            "/", data={"invitation_id": self.invitation.id}, **self.extra
        )

        # only owner and manager roles have permission
        for role_class in ROLES_ORDERED:
            ShareProject(self.project, "alice", role_class.name).save()
            self.assertTrue(role_class.user_has_role(alice_profile.user, self.project))
            response = self.view(request, pk=self.project.pk)

            if role_class.name in [ManagerRole.name, OwnerRole.name]:
                self.assertEqual(response.status_code, 400)
            else:
                self.assertEqual(response.status_code, 403)

    @override_settings(PROJECT_INVITATION_URL={"*": "https://example.com/register"})
    def test_update(self, mock_send_mail):
        """We can update an invitation"""
        payload = {
            "email": "rihanna@example.com",
            "role": "readonly",
            "invitation_id": self.invitation.id,
        }
        request = self.factory.put(
            "/",
            data=json.dumps(payload),
            content_type="application/json",
            **self.extra,
        )
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.email, "rihanna@example.com")
        self.assertEqual(self.invitation.role, "readonly")
        self.assertEqual(
            response.data,
            {
                "id": self.invitation.pk,
                "email": "rihanna@example.com",
                "role": "readonly",
                "status": 1,
            },
        )
        mock_send_mail.assert_called_once_with(
            self.invitation.pk, "https://example.com/register"
        )

    def test_update_role_only(self, mock_send_mail):
        """We can update role only"""
        payload = {
            "email": self.invitation.email,
            "role": "readonly",
            "invitation_id": self.invitation.id,
        }
        request = self.factory.put(
            "/",
            data=json.dumps(payload),
            content_type="application/json",
            **self.extra,
        )
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.role, "readonly")
        self.assertEqual(
            response.data,
            {
                "id": self.invitation.pk,
                "email": "janedoe@example.com",
                "role": "readonly",
                "status": 1,
            },
        )
        mock_send_mail.assert_not_called()

    @override_settings(PROJECT_INVITATION_URL={"*": "https://example.com/register"})
    def test_update_email_only(self, mock_send_mail):
        """We can update email only"""
        payload = {
            "email": "rihanna@example.com",
            "role": self.invitation.role,
            "invitation_id": self.invitation.id,
        }
        request = self.factory.put(
            "/",
            data=json.dumps(payload),
            content_type="application/json",
            **self.extra,
        )
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.email, "rihanna@example.com")
        self.assertEqual(
            response.data,
            {
                "id": self.invitation.pk,
                "email": "rihanna@example.com",
                "role": "editor",
                "status": 1,
            },
        )
        mock_send_mail.assert_called_once_with(
            self.invitation.pk, "https://example.com/register"
        )

    def test_only_pending_allowed(self, mock_send_mail):
        """Only pending invitation can be updated"""
        for value, _ in ProjectInvitation.Status.choices:
            invitation = self.project.invitations.create(
                email=f"jandoe-{value}@example.com",
                role="editor",
                status=value,
            )
            payload = {
                "email": "rihanna@example.com",
                "role": "readonly",
                "invitation_id": invitation.id,
            }
            request = self.factory.put("/", data=payload, **self.extra)
            response = self.view(request, pk=self.project.pk)

            if value == ProjectInvitation.Status.PENDING:
                self.assertEqual(response.status_code, 200)

            else:
                self.assertEqual(response.status_code, 400)

    def test_user_unregistered(self, mock_send_mail):
        """Email cannot be updated to that of an existing user"""
        alice_data = {"username": "alice", "email": "alice@example.com"}
        self._create_user_profile(alice_data)
        post_data = {
            "email": alice_data["email"],
            "role": "editor",
            "invitation_id": self.invitation.id,
        }
        request = self.factory.put(
            "/",
            data=json.dumps(post_data),
            content_type="application/json",
            **self.extra,
        )
        response = self.view(request, pk=self.project.pk)
        print("Helleo", response.data)
        self.assertEqual(response.status_code, 400)
        self.invitation.refresh_from_db()
        # invitation email not updated
        self.assertEqual(self.invitation.email, "janedoe@example.com")


class RevokeInvitationTestCase(TestAbstractViewSet):
    """Tests for revoke invitation"""

    def setUp(self):
        super().setUp()
        self._project_create()
        self.view = ProjectViewSet.as_view({"post": "revoke_invitation"})

    def test_authentication(self):
        """Authentication is required"""
        request = self.factory.post("/", data={})
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 401)

    def test_invalid_project(self):
        """Invalid project is handled"""
        request = self.factory.post("/", data={}, **self.extra)
        response = self.view(request, pk=817)
        self.assertEqual(response.status_code, 404)

    def test_only_admins_allowed(self):
        """Only project admins are allowed to create project invitation"""
        # login as editor alice
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        self._login_user_and_profile(alice_data)
        request = self.factory.post("/", data={}, **self.extra)

        # only owner and manager roles have permission
        for role_class in ROLES_ORDERED:
            ShareProject(self.project, "alice", role_class.name).save()
            self.assertTrue(role_class.user_has_role(alice_profile.user, self.project))
            response = self.view(request, pk=self.project.pk)

            if role_class.name in [ManagerRole.name, OwnerRole.name]:
                self.assertEqual(response.status_code, 400)
            else:
                self.assertEqual(response.status_code, 403)

    def test_revoke_invite(self):
        """Invitation is revoked"""
        invitation = self.project.invitations.create(
            email="jandoe@example.com", role="editor"
        )
        post_data = {"invitation_id": invitation.pk}
        request = self.factory.post("/", data=post_data, **self.extra)
        mocked_now = datetime(2023, 5, 25, 10, 51, 0, tzinfo=tz.utc)

        with patch("django.utils.timezone.now", Mock(return_value=mocked_now)):
            response = self.view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, ProjectInvitation.Status.REVOKED)
        self.assertEqual(invitation.revoked_at, mocked_now)
        self.assertEqual(response.data, {"message": "Success"})

    def test_invitation_id_required(self):
        """`invitation_id` field is required"""
        # blank
        post_data = {"invitation_id": ""}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 400)
        # missing
        request = self.factory.post("/", data={}, **self.extra)
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 400)

    def test_invitation_id_valid(self):
        """`invitation_id` should valid"""
        post_data = {"invitation_id": "89"}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 400)

    def test_only_pending_allowed(self):
        """Only invitations whose status is pending can be revoked"""

        for value, _ in ProjectInvitation.Status.choices:
            invitation = self.project.invitations.create(
                email=f"jandoe-{value}@example.com",
                role="editor",
                status=value,
            )
            post_data = {"invitation_id": invitation.pk}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = self.view(request, pk=self.project.pk)

            if value == ProjectInvitation.Status.PENDING:
                self.assertEqual(response.status_code, 200)

            else:
                self.assertEqual(response.status_code, 400)


@patch(
    "onadata.libs.serializers.project_invitation_serializer.send_project_invitation_email_async.delay"
)
class ResendInvitationTestCase(TestAbstractViewSet):
    """Tests for resend invitation"""

    def setUp(self):
        super().setUp()
        self._project_create()
        self.view = ProjectViewSet.as_view({"post": "resend_invitation"})

    def test_authentication(self, mock_send_mail):
        """Authentication is required"""
        request = self.factory.post("/", data={})
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 401)
        mock_send_mail.assert_not_called()

    def test_invalid_project(self, mock_send_mail):
        """Invalid project is handled"""
        request = self.factory.post("/", data={}, **self.extra)
        response = self.view(request, pk=817)
        self.assertEqual(response.status_code, 404)
        mock_send_mail.assert_not_called()

    def test_only_admins_allowed(self, mock_send_mail):
        """Only project admins are allowed to create project invitation"""
        # login as editor alice
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        self._login_user_and_profile(alice_data)
        request = self.factory.post("/", data={}, **self.extra)

        # only owner and manager have permission
        for role_class in ROLES_ORDERED:
            ShareProject(self.project, "alice", role_class.name).save()
            self.assertTrue(role_class.user_has_role(alice_profile.user, self.project))
            response = self.view(request, pk=self.project.pk)

            if role_class.name in [ManagerRole.name, OwnerRole.name]:
                self.assertEqual(response.status_code, 400)
            else:
                self.assertEqual(response.status_code, 403)

        mock_send_mail.assert_not_called()

    @override_settings(PROJECT_INVITATION_URL={"*": "https://example.com/register"})
    def test_resend_invite(self, mock_send_mail):
        """Invitation is revoked"""
        invitation = self.project.invitations.create(
            email="jandoe@example.com", role="editor"
        )
        post_data = {"invitation_id": invitation.pk}
        mocked_now = datetime(2023, 5, 25, 10, 51, 0, tzinfo=tz.utc)
        request = self.factory.post("/", data=post_data, **self.extra)

        with patch("django.utils.timezone.now", Mock(return_value=mocked_now)):
            response = self.view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        invitation.refresh_from_db()
        self.assertEqual(invitation.resent_at, mocked_now)
        self.assertEqual(response.data, {"message": "Success"})
        mock_send_mail.assert_called_once_with(
            invitation.id,
            "https://example.com/register",
        )

    def test_invitation_id_required(self, mock_send_mail):
        """`invitation_id` field is required"""
        # blank
        post_data = {"invitation_id": ""}
        request = self.factory.post("/", data=post_data, **self.extra)
        view = ProjectViewSet.as_view({"post": "resend_invitation"})
        response = view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 400)
        # missing
        request = self.factory.post("/", data={}, **self.extra)
        view = ProjectViewSet.as_view({"post": "resend_invitation"})
        response = view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 400)
        mock_send_mail.assert_not_called()

    def test_invitation_id_valid(self, mock_send_mail):
        """`invitation_id` should valid"""
        post_data = {"invitation_id": "89"}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 400)
        mock_send_mail.assert_not_called()

    def test_only_pending_allowed(self, mock_send_mail):
        """Only invitations whose status is pending can be resent"""

        for value, _ in ProjectInvitation.Status.choices:
            invitation = self.project.invitations.create(
                email=f"jandoe-{value}@example.com",
                role="editor",
                status=value,
            )
            post_data = {"invitation_id": invitation.pk}
            request = self.factory.post("/", data=post_data, **self.extra)
            response = self.view(request, pk=self.project.pk)

            if value == ProjectInvitation.Status.PENDING:
                self.assertEqual(response.status_code, 200)

            else:
                self.assertEqual(response.status_code, 400)

        mock_send_mail.assert_called_once()
