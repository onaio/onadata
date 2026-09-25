# -*- coding: utf-8 -*-
"""
Test /widgets API endpoint implementation.
"""

import json
import os
from unittest.mock import patch

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.utils import timezone

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.tools import get_or_create_organization_owners_team
from onadata.apps.api.viewsets.organization_profile_viewset import (
    OrganizationProfileViewSet,
)
from onadata.apps.api.viewsets.widget_viewset import WidgetViewSet
from onadata.apps.logger.models.project import Project
from onadata.apps.logger.models.widget import Widget
from onadata.libs.permissions import DataEntryOnlyRole, OwnerRole, ReadOnlyRole


# pylint: disable=too-many-public-methods
class TestWidgetViewSet(TestAbstractViewSet):
    """
    Test /widgets API endpoint implementation.
    """

    def setUp(self):
        super(self.__class__, self).setUp()
        xlsform_path = os.path.join(
            settings.PROJECT_ROOT, "libs", "tests", "utils", "fixtures", "tutorial.xlsx"
        )
        self._org_create()
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

        self.view = WidgetViewSet.as_view(
            {
                "post": "create",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
                "get": "retrieve",
            }
        )

    def test_create_widget(self):
        self._create_widget()

    def test_create_only_mandatory_fields(self):
        data = {
            "content_object": "http://testserver/api/v1/forms/%s" % self.xform.pk,
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "_submission_time",
        }

        self._create_widget(data)

    def test_create_using_dataview(self):
        data = {
            "content_object": "http://testserver/api/v1/dataviews/%s"
            % self.data_view.pk,
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "_submission_time",
        }

        self._create_widget(data)

    def test_create_using_unsupported_model_source(self):
        data = {
            "content_object": "http://testserver/api/v1/projects/%s" % self.project.pk,
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "_submission_time",
        }

        count = Widget.objects.all().count()

        request = self.factory.post("/", data=data, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(count, Widget.objects.all().count())
        self.assertEqual(
            response.data["content_object"],
            ["`%s` is not a valid relation." % data["content_object"]],
        )

    def test_create_without_required_field(self):
        data = {
            "content_object": "http://testserver/api/v1/forms/%s" % self.xform.pk,
            "widget_type": "charts",
            "view_type": "horizontal-bar",
        }

        count = Widget.objects.all().count()

        request = self.factory.post("/", data=data, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(count, Widget.objects.all().count())
        self.assertEqual(response.data["column"], ["This field is required."])

    def test_create_unsupported_widget_type(self):
        data = {
            "content_object": "http://testserver/api/v1/forms/%s" % self.xform.pk,
            "widget_type": "table",
            "view_type": "horizontal-bar",
            "column": "_submission_time",
        }

        count = Widget.objects.all().count()

        request = self.factory.post("/", data=data, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(count, Widget.objects.all().count())
        self.assertEqual(
            response.data["widget_type"],
            ['"%s" is not a valid choice.' % data["widget_type"]],
        )

    def test_update_widget(self):
        self._create_widget()

        key = self.widget.key

        data = {
            "title": "My new title updated",
            "description": "new description",
            "aggregation": "new aggregation",
            "content_object": "http://testserver/api/v1/forms/%s" % self.xform.pk,
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "_submission_time",
        }

        request = self.factory.put("/", data=data, **self.extra)
        response = self.view(request, pk=self.widget.pk)

        self.widget = Widget.objects.all().order_by("pk").reverse()[0]

        self.assertEqual(key, self.widget.key)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["title"], "My new title updated")
        self.assertEqual(response.data["key"], key)
        self.assertEqual(response.data["description"], "new description")
        self.assertEqual(response.data["aggregation"], "new aggregation")

    def test_patch_widget(self):
        self._create_widget()

        data = {
            "column": "_submitted_by",
        }

        request = self.factory.patch("/", data=data, **self.extra)
        response = self.view(request, pk=self.widget.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["column"], "_submitted_by")

    def test_patch_rejects_invalid_group_by_without_persisting_it(self):
        """A group_by-only PATCH validates against the existing XForm."""
        self._create_widget(group_by="gender")
        original_group_by = self.widget.group_by
        payload = "a' , (SELECT 1) , 'b"

        request = self.factory.patch("/", data={"group_by": payload}, **self.extra)
        response = self.view(request, pk=self.widget.pk)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["group_by"], [f"'{payload}' not in the form."])
        self.widget.refresh_from_db()
        self.assertEqual(self.widget.group_by, original_group_by)

    def test_patch_rejects_invalid_column_without_persisting_it(self):
        """A column-only PATCH validates against the existing XForm."""
        self._create_widget()
        original_column = self.widget.column
        payload = "a' , (SELECT 1) , 'b"

        request = self.factory.patch("/", data={"column": payload}, **self.extra)
        response = self.view(request, pk=self.widget.pk)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["column"], [f"'{payload}' not in the form."])
        self.widget.refresh_from_db()
        self.assertEqual(self.widget.column, original_column)

    def test_delete_widget(self):
        ct = ContentType.objects.get(model="xform", app_label="logger")
        self._create_widget()
        count = Widget.objects.filter(content_type=ct, object_id=self.xform.pk).count()

        request = self.factory.delete("/", **self.extra)
        response = self.view(request, pk=self.widget.pk)

        self.assertEqual(response.status_code, 204)

        after_count = Widget.objects.filter(
            content_type=ct, object_id=self.xform.pk
        ).count()
        self.assertEqual(count - 1, after_count)

    def test_list_widgets(self):
        self._create_widget()
        self._publish_xls_form_to_project()

        data = {
            "content_object": "http://testserver/api/v1/forms/%s" % self.xform.pk,
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "_submitted_by",
        }

        self._create_widget(data=data)

        view = WidgetViewSet.as_view(
            {
                "get": "list",
            }
        )

        # empty - no xform filter
        request = self.factory.get("/", **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        # not empty - xform filter
        request = self.factory.get("/", data={"xform": self.xform.pk}, **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_list_public_widgets_excludes_deleted_forms(self):
        self._create_widget()
        self.xform.shared_data = True
        self.xform.save()

        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._login_user_and_profile(alice_data)

        view = WidgetViewSet.as_view({"get": "list"})
        request = self.factory.get("/", data={"xform": self.xform.pk}, **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        self.xform.soft_delete()
        request = self.factory.get("/", data={"xform": self.xform.pk}, **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_widget_permission_create(self):
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._login_user_and_profile(alice_data)

        view = WidgetViewSet.as_view({"post": "create"})

        data = {
            "title": "Widget that",
            "content_object": "http://testserver/api/v1/forms/%s" % self.xform.pk,
            "description": "Test widget",
            "aggregation": "Sum",
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "age",
            "group_by": "",
        }

        # to do: test random user with auth but no perms
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request)
        self.assertEqual(response.status_code, 400)

        # owner
        OwnerRole.add(self.user, self.project)
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request)
        self.assertEqual(response.status_code, 201)

        # readonly
        ReadOnlyRole.add(self.user, self.project)
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request)
        self.assertEqual(response.status_code, 201)

        # dataentryonlyrole
        DataEntryOnlyRole.add(self.user, self.project)
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request)
        self.assertEqual(response.status_code, 201)

    def test_widget_permission_change(self):
        self._create_widget()

        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._login_user_and_profile(alice_data)

        data = {
            "title": "Widget those",
        }

        OwnerRole.add(self.user, self.project)
        OwnerRole.add(self.user, self.xform)
        request = self.factory.patch("/", data=data, **self.extra)
        response = self.view(request, pk=self.widget.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["title"], "Widget those")

        ReadOnlyRole.add(self.user, self.project)
        ReadOnlyRole.add(self.user, self.xform)

        request = self.factory.patch("/", data=data, **self.extra)
        response = self.view(request, pk=self.widget.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["title"], "Widget those")

    def test_widget_permission_list(self):
        self._create_widget()

        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._login_user_and_profile(alice_data)

        view = WidgetViewSet.as_view(
            {
                "get": "list",
            }
        )

        request = self.factory.get("/", **self.extra)
        response = view(request, formid=self.xform.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        # assign alice the perms
        ReadOnlyRole.add(self.user, self.xform)

        request = self.factory.get("/", **self.extra)
        response = view(request, formid=self.xform.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_widget_permission_get(self):
        self._create_widget()

        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._login_user_and_profile(alice_data)

        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.widget.pk)

        self.assertEqual(response.status_code, 404)

        # assign alice the perms
        ReadOnlyRole.add(self.user, self.project)

        request = self.factory.get("/", **self.extra)
        response = self.view(request, formid=self.xform.pk, pk=self.widget.pk)

        self.assertEqual(response.status_code, 200)

    def test_widget_data(self):
        self._create_widget()

        data = {"data": True}

        request = self.factory.get("/", data=data, **self.extra)
        response = self.view(request, pk=self.widget.pk)

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data.get("data"))
        self.assertIn("data", response.data.get("data"))
        self.assertEqual(len(response.data.get("data")["data"]), 8)
        self.assertIn("age", response.data.get("data")["data"][0])
        self.assertIn("count", response.data.get("data")["data"][0])

        self.assertEqual(response.data.get("data")["data_type"], "numeric")
        self.assertEqual(response.data.get("data")["field_label"], "How old are you?")
        self.assertEqual(response.data.get("data")["field_type"], "integer")
        self.assertEqual(response.data.get("data")["field_xpath"], "age")

    def test_widget_data_preserves_submission_time_granularity(self):
        submission_times = [f"2026-01-15T{hour:02d}:00:00+00:00" for hour in range(8)]
        for instance, submission_time in zip(
            self.xform.instances.order_by("pk"), submission_times
        ):
            instance_json = dict(instance.json)
            instance_json["_submission_time"] = submission_time
            self.xform.instances.filter(pk=instance.pk).update(json=instance_json)

        self._create_widget(
            {
                "content_object": f"http://testserver/api/v1/forms/{self.xform.pk}",
                "widget_type": "charts",
                "view_type": "horizontal-bar",
                "column": "_submission_time",
            }
        )

        request = self.factory.get("/", data={"data": True}, **self.extra)
        response = self.view(request, pk=self.widget.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["data"]["data"],
            [
                {"_submission_time": submission_time, "count": 1}
                for submission_time in submission_times
            ],
        )

    def test_widget_data_with_group_by(self):
        self._create_widget(group_by="gender")

        data = {"data": True}

        request = self.factory.get("/", data=data, **self.extra)
        response = self.view(request, pk=self.widget.pk)

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data.get("data"))
        self.assertIn("data", response.data.get("data"))
        self.assertEqual(len(response.data.get("data")["data"]), 2)
        self.assertIn("gender", response.data.get("data")["data"][0])
        self.assertIn("sum", response.data.get("data")["data"][0])
        self.assertIn("mean", response.data.get("data")["data"][0])

    def test_widget_data_widget(self):
        data = {
            "content_object": "http://testserver/api/v1/forms/%s" % self.xform.pk,
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "gender",
        }

        self._create_widget(data)

        data = {"data": True}
        request = self.factory.get("/", data=data, **self.extra)
        response = self.view(request, pk=self.widget.pk)

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data.get("data"))
        self.assertEqual(
            response.data.get("data"),
            {
                "field_type": "select one",
                "data_type": "categorized",
                "field_xpath": "gender",
                "field_label": "Gender",
                "grouped_by": None,
                "data": [
                    {"count": 1, "gender": "female"},
                    {"count": 7, "gender": "male"},
                ],
            },
        )

    def test_widget_with_key(self):
        self._create_widget()

        view = WidgetViewSet.as_view(
            {
                "get": "list",
            }
        )

        data = {"key": self.widget.key}

        request = self.factory.get("/", data=data, **self.extra)
        response = view(request, formid=self.xform.pk)

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data.get("data"))
        self.assertIn("data", response.data.get("data"))
        self.assertEqual(len(response.data.get("data")["data"]), 8)
        self.assertIn("age", response.data.get("data")["data"][0])
        self.assertIn("count", response.data.get("data")["data"][0])

    def test_widget_with_key_anon(self):
        self._create_widget()

        view = WidgetViewSet.as_view(
            {
                "get": "list",
            }
        )

        data = {"key": self.widget.key}

        # Anonymous user can access the widget
        self.extra = {}

        request = self.factory.get("/", data=data, **self.extra)
        response = view(request, formid=self.xform.pk)

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data.get("data"))
        self.assertIn("data", response.data.get("data"))
        self.assertEqual(len(response.data.get("data")["data"]), 8)
        self.assertIn("age", response.data.get("data")["data"][0])
        self.assertIn("count", response.data.get("data")["data"][0])

    def test_widget_with_nonexistance_key(self):
        self._create_widget()

        view = WidgetViewSet.as_view(
            {
                "get": "list",
            }
        )

        data = {"key": "randomkeythatdoesnotexist"}

        self.extra = {}

        request = self.factory.get("/", data=data, **self.extra)
        response = view(request, pk=self.xform.pk)

        self.assertEqual(response.status_code, 404)

    def test_widget_data_public_form(self):
        self._create_widget()

        view = WidgetViewSet.as_view(
            {
                "get": "list",
            }
        )
        self.extra = {}

        request = self.factory.get("/", **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        # Anonymous user can access widget in public form
        self.xform.shared_data = True
        self.xform.save()

        request = self.factory.get("/", **self.extra)
        response = view(request, formid=self.xform.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_widget_pk_formid_required(self):
        self._create_widget()

        data = {
            "title": "My new title updated",
            "description": "new description",
            "content_object": "http://testserver/api/v1/forms/%s" % self.xform.pk,
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "_submission_time",
        }

        request = self.factory.put("/", data=data, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"detail": "'pk' required for this" " action"})

    def test_list_widgets_with_formid(self):
        self._create_widget()
        self._publish_xls_form_to_project()

        data = {
            "content_object": "http://testserver/api/v1/forms/%s" % self.xform.pk,
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "_submitted_by",
        }

        self._create_widget(data=data)

        view = WidgetViewSet.as_view(
            {
                "get": "list",
            }
        )

        data = {"xform": self.xform.pk}

        request = self.factory.get("/", data=data, **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_create_column_not_in_form(self):
        data = {
            "content_object": "http://testserver/api/v1/forms/%s" % self.xform.pk,
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "doesnotexists",
        }

        count = Widget.objects.all().count()

        request = self.factory.post("/", data=data, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(count, Widget.objects.all().count())
        self.assertEqual(response.data["column"], ["'doesnotexists' not in the form."])

    def test_create_group_by_not_in_form(self):
        """A widget whose group_by is not a form field is rejected."""
        data = {
            "content_object": "http://testserver/api/v1/forms/%s" % self.xform.pk,
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "_submission_time",
            "group_by": "doesnotexists",
        }

        count = Widget.objects.all().count()

        request = self.factory.post("/", data=data, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(count, Widget.objects.all().count())
        self.assertEqual(
            response.data["group_by"], ["'doesnotexists' not in the form."]
        )

    def test_create_widget_with_xform_no_perms(self):
        data = {
            "content_object": "http://testserver/api/v1/forms/%s" % self.xform.pk,
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "age",
        }

        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._login_user_and_profile(alice_data)

        request = self.factory.post("/", data=data, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["content_object"],
            ["You don't have permission to the Project."],
        )

    def test_filter_widgets_by_dataview(self):
        self._create_widget()
        self._publish_xls_form_to_project()

        data = {
            "content_object": "http://testserver/api/v1/dataviews/%s"
            % self.data_view.pk,
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "_submitted_by",
        }

        self._create_widget(data=data)

        data = {
            "content_object": "http://testserver/api/v1/dataviews/%s"
            % self.data_view.pk,
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "_submission_time",
        }

        self._create_widget(data)

        view = WidgetViewSet.as_view(
            {
                "get": "list",
            }
        )

        data = {"dataview": self.data_view.pk}

        request = self.factory.get("/", data=data, **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        data = {"dataview": "so_invalid"}

        request = self.factory.get("/", data=data, **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            "Invalid value for dataview ID. It must be a positive integer.",
        )

    def test_dataview_widget_list_uses_destination_project_permissions(self):
        """DataView widgets follow the destination-project read contract."""
        destination_project = Project.objects.create(
            name="Widget destination project",
            organization=self.user,
            created_by=self.user,
            metadata={},
        )
        self.data_view.project = destination_project
        self.data_view.save(update_fields=["project", "date_modified"])
        widget = Widget.objects.create(
            content_object=self.data_view,
            widget_type="charts",
            view_type="horizontal-bar",
            column="age",
        )
        view = WidgetViewSet.as_view({"get": "list"})

        with patch.object(Widget, "query_data") as query_data:
            request = self.factory.get(
                "/", data={"dataview": self.data_view.pk, "data": True}
            )
            response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        self.assertNotIn(widget.key, json.dumps(response.data))
        query_data.assert_not_called()

        outsider = self._create_user("widget-outsider", "password")
        request = self.factory.get(
            "/",
            data={"dataview": self.data_view.pk, "data": True},
            HTTP_AUTHORIZATION=f"Token {outsider.auth_token}",
        )
        self.assertEqual(view(request).data, [])

        source_reader = self._create_user("widget-source-reader", "password")
        ReadOnlyRole.add(source_reader, self.project)
        request = self.factory.get(
            "/",
            data={"dataview": self.data_view.pk, "data": True},
            HTTP_AUTHORIZATION=f"Token {source_reader.auth_token}",
        )
        self.assertEqual(view(request).data, [])

        destination_reader = self._create_user("widget-destination-reader", "password")
        ReadOnlyRole.add(destination_reader, destination_project)
        request = self.factory.get(
            "/",
            data={"dataview": self.data_view.pk, "data": True},
            HTTP_AUTHORIZATION=f"Token {destination_reader.auth_token}",
        )
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], [widget.pk])
        self.assertEqual(
            {item["age"] for item in response.data[0]["data"]["data"]},
            {"22", "28", "45"},
        )

        destination_project.shared = True
        destination_project.save(update_fields=["shared", "date_modified"])
        request = self.factory.get("/", data={"dataview": self.data_view.pk})
        response = view(request)
        self.assertEqual([item["id"] for item in response.data], [widget.pk])

    def test_dataview_widget_key_applies_integer_filter_numerically(self):
        """A widget key cannot expose rows outside an integer DataView filter."""
        instances = {
            str(instance.json["age"]): instance
            for instance in self.xform.instances.all()
        }
        for old_age, new_age in (("14", 5), ("87", 100)):
            instance = instances[old_age]
            instance_json = dict(instance.json)
            instance_json["age"] = new_age
            self.xform.instances.filter(pk=instance.pk).update(json=instance_json)

        self.data_view.query = [{"column": "age", "filter": ">", "value": "20"}]
        self.data_view.save(update_fields=["query", "date_modified"])
        widget = Widget.objects.create(
            content_object=self.data_view,
            widget_type="charts",
            view_type="horizontal-bar",
            column="age",
        )
        view = WidgetViewSet.as_view({"get": "list"})

        request = self.factory.get("/", data={"key": widget.key})
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {item["age"] for item in response.data["data"]["data"]},
            {"22", "28", "45", "55", "56", "66", "100"},
        )

    def test_widget_filters_constrain_generic_content_type(self):
        """Equal XForm and DataView IDs cannot collide in widget lists."""
        collision_dataview, _ = type(self.data_view).objects.get_or_create(
            pk=self.xform.pk,
            defaults={
                "name": "Colliding DataView",
                "xform": self.xform,
                "project": self.project,
                "columns": ["age"],
            },
        )
        xform_widget = Widget.objects.create(
            content_object=self.xform,
            widget_type="charts",
            view_type="horizontal-bar",
            column="age",
        )
        dataview_widget = Widget.objects.create(
            content_object=collision_dataview,
            widget_type="charts",
            view_type="horizontal-bar",
            column="age",
        )
        view = WidgetViewSet.as_view({"get": "list"})

        request = self.factory.get("/", data={"xform": self.xform.pk}, **self.extra)
        response = view(request)
        self.assertEqual([item["id"] for item in response.data], [xform_widget.pk])

        request = self.factory.get(
            "/", data={"dataview": collision_dataview.pk}, **self.extra
        )
        response = view(request)
        self.assertEqual([item["id"] for item in response.data], [dataview_widget.pk])

    def test_deleted_dataview_widget_is_unavailable(self):
        """Deleted DataViews are unavailable through list, detail, and key reads."""
        widget = Widget.objects.create(
            content_object=self.data_view,
            widget_type="charts",
            view_type="horizontal-bar",
            column="age",
        )
        self.data_view.soft_delete(self.user)
        list_view = WidgetViewSet.as_view({"get": "list"})

        request = self.factory.get(
            "/", data={"dataview": self.data_view.pk}, **self.extra
        )
        self.assertEqual(list_view(request).status_code, 404)
        request = self.factory.get("/", **self.extra)
        self.assertEqual(self.view(request, pk=widget.pk).status_code, 404)
        request = self.factory.get("/", data={"key": widget.key})
        self.assertEqual(list_view(request).status_code, 404)

    def test_deleted_destination_project_widget_is_unavailable(self):
        """A deleted destination project closes every DataView widget read."""
        widget = Widget.objects.create(
            content_object=self.data_view,
            widget_type="charts",
            view_type="horizontal-bar",
            column="age",
        )
        self.data_view.project.deleted_at = timezone.now()
        self.data_view.project.save(update_fields=["deleted_at", "date_modified"])
        list_view = WidgetViewSet.as_view({"get": "list"})

        request = self.factory.get(
            "/", data={"dataview": self.data_view.pk}, **self.extra
        )
        self.assertEqual(list_view(request).status_code, 404)
        request = self.factory.get("/", **self.extra)
        self.assertEqual(self.view(request, pk=widget.pk).status_code, 404)
        request = self.factory.get("/", data={"key": widget.key})
        self.assertEqual(list_view(request).status_code, 404)

    def test_inactive_destination_organization_widget_is_unavailable(self):
        """An inactive destination organization closes every widget read."""
        organization = self._create_user("inactive-widget-org", "password")
        destination_project = Project.objects.create(
            name="Inactive organization destination",
            organization=organization,
            created_by=self.user,
            metadata={},
        )
        self.data_view.project = destination_project
        self.data_view.save(update_fields=["project", "date_modified"])
        widget = Widget.objects.create(
            content_object=self.data_view,
            widget_type="charts",
            view_type="horizontal-bar",
            column="age",
        )
        organization.is_active = False
        organization.save(update_fields=["is_active"])
        list_view = WidgetViewSet.as_view({"get": "list"})

        request = self.factory.get(
            "/", data={"dataview": self.data_view.pk}, **self.extra
        )
        self.assertEqual(list_view(request).status_code, 404)
        request = self.factory.get("/", **self.extra)
        self.assertEqual(self.view(request, pk=widget.pk).status_code, 404)
        request = self.factory.get("/", data={"key": widget.key})
        self.assertEqual(list_view(request).status_code, 404)

    def test_dataview_widget_rejects_unselected_fields(self):
        """DataView chart fields are limited to its selected projection."""
        data = {
            "content_object": (
                f"http://testserver/api/v1/dataviews/{self.data_view.pk}"
            ),
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "pizza_fan",
        }
        request = self.factory.post("/", data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["column"], ["'pizza_fan' not in the DataView."])

        data.update({"column": "age", "group_by": "pizza_fan"})
        request = self.factory.post("/", data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["group_by"], ["'pizza_fan' not in the DataView."]
        )

        widget = Widget.objects.create(
            content_object=self.data_view,
            widget_type="charts",
            view_type="horizontal-bar",
            column="age",
        )
        request = self.factory.patch("/", data={"group_by": "pizza_fan"}, **self.extra)
        response = self.view(request, pk=widget.pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["group_by"], ["'pizza_fan' not in the DataView."]
        )
        widget.refresh_from_db()
        self.assertIsNone(widget.group_by)

    def test_invalid_stored_widget_fields_fail_before_querying(self):
        """Legacy invalid fields raise 404 before an aggregation executes."""
        widget = Widget.objects.create(
            content_object=self.xform,
            widget_type="charts",
            view_type="horizontal-bar",
            column="age",
            group_by="a' , (SELECT 1) , 'b",
        )
        with patch(
            "onadata.apps.logger.models.widget."
            "get_form_submissions_aggregated_by_select_one"
        ) as aggregate:
            with self.assertRaises(Http404):
                Widget.query_data(widget)
        aggregate.assert_not_called()

        widget.column = "a' , (SELECT 1) , 'b"
        widget.group_by = None
        widget.save(update_fields=["column", "group_by", "date_modified"])
        with patch(
            "onadata.apps.logger.models.widget." "get_form_submissions_grouped_by_field"
        ) as grouped:
            with self.assertRaises(Http404):
                Widget.query_data(widget)
        grouped.assert_not_called()

    def test_order_widget(self):
        self._create_widget()
        self._create_widget()
        self._create_widget()

        data = {"column": "_submission_time", "order": 1}

        request = self.factory.patch("/", data=data, **self.extra)
        response = self.view(request, pk=self.widget.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["order"], 1)

        widget = Widget.objects.all().order_by("pk")[0]
        self.assertEqual(widget.order, 0)

        widget = Widget.objects.all().order_by("pk")[1]
        self.assertEqual(widget.order, 2)

    def test_widget_data_case_sensitive(self):
        xlsform_path = os.path.join(
            settings.PROJECT_ROOT,
            "libs",
            "tests",
            "utils",
            "fixtures",
            "tutorial_2.xlsx",
        )

        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        for x in range(1, 9):
            path = os.path.join(
                settings.PROJECT_ROOT,
                "libs",
                "tests",
                "utils",
                "fixtures",
                "tutorial_2",
                "instances",
                "uuid{}".format(x),
                "submission.xml",
            )
            self._make_submission(path)
            x += 1

        data = {
            "content_object": "http://testserver/api/v1/forms/%s" % self.xform.pk,
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "Gender",
            "metadata": {"test metadata": "percentage"},
        }

        self._create_widget(data)

        data = {"data": True}
        request = self.factory.get("/", data=data, **self.extra)
        response = self.view(request, pk=self.widget.pk)

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data.get("data"))
        self.assertEqual(
            response.data.get("data"),
            {
                "field_type": "select one",
                "data_type": "categorized",
                "field_xpath": "Gender",
                "field_label": "Gender",
                "grouped_by": None,
                "data": [
                    {"count": 1, "Gender": "female"},
                    {"count": 7, "Gender": "male"},
                ],
            },
        )

    def test_widget_create_by_org_admin(self):
        self.project.organization = self.organization.user
        self.project.save()
        chuck_data = {"username": "chuck", "email": "chuck@localhost.com"}
        chuck_profile = self._create_user_profile(chuck_data)

        view = OrganizationProfileViewSet.as_view({"post": "members"})

        data = {"username": chuck_profile.user.username, "role": OwnerRole.name}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user=self.organization.user.username)

        self.assertEqual(response.status_code, 201)

        owners_team = get_or_create_organization_owners_team(self.organization)
        self.assertIn(chuck_profile.user, owners_team.user_set.all())

        extra = {"HTTP_AUTHORIZATION": "Token %s" % chuck_profile.user.auth_token}

        view = WidgetViewSet.as_view({"post": "create"})

        data = {
            "content_object": "http://testserver/api/v1/dataviews/%s"
            % self.data_view.pk,
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "_submission_time",
        }

        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **extra
        )
        response = view(request)

        self.assertEqual(response.status_code, 201)

    def test_create_multiple_choice(self):
        data = {
            "content_object": "http://testserver/api/v1/forms/%s" % self.xform.pk,
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "favorite_toppings/pepperoni",
        }

        self._create_widget(data)

        data = {"data": True}
        pk = self.widget.pk
        request = self.factory.get("/", data=data, **self.extra)
        response = self.view(request, pk=pk)

        self.assertEqual(response.status_code, 200)

        form_pk = self.xform.pk
        expected = {
            "content_object": "http://testserver/api/v1/forms/{}".format(form_pk),
            "description": None,
            "title": None,
            "url": "http://testserver/api/v1/widgets/{}".format(pk),
            "view_type": "horizontal-bar",
            "aggregation": None,
            "order": 0,
            "widget_type": "charts",
            "column": "favorite_toppings/pepperoni",
            "group_by": None,
            "key": self.widget.key,
            "data": {
                "field_type": "",
                "data_type": "categorized",
                "field_xpath": "favorite_toppings/pepperoni",
                "grouped_by": None,
                "field_label": "Pepperoni",
                "data": [{"" "count": 0, "favorite_toppings/pepperoni": None}],
            },
            "id": pk,
            "metadata": {},
        }
        self.assertEqual(expected, response.data)

    def test_create_long_title(self):
        data = {
            "title": "When editing grouped charts titles, much as the title "
            "can be edited, it cant be saved as the title exceeds 50",
            "content_object": "http://testserver/api/v1/dataviews/%s"
            % self.data_view.pk,
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "_submission_time",
        }

        self._create_widget(data)
