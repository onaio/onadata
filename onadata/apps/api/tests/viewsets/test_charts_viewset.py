# -*- coding: utf-8 -*-
"""
Test ChartsViewSet.
"""
import json
import os
from unittest.mock import patch

from django.core.cache import cache
from django.db.utils import DataError
from django.test.utils import override_settings
from django.utils import timezone

from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from onadata.apps.api.viewsets.charts_viewset import ChartsViewSet
from onadata.apps.api.viewsets.merged_xform_viewset import MergedXFormViewSet
from onadata.apps.logger.models.instance import Instance
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.renderers.renderers import DecimalJSONRenderer
from onadata.libs.utils.cache_tools import XFORM_CHARTS
from onadata.libs.utils.timing import calculate_duration
from onadata.libs.utils.user_auth import get_user_default_project


def raise_data_error(a):
    raise DataError


MD = """
| survey  |
|         | type              | name  | label   |
|         | select one fruits | fruits | Fruit   |

| choices |
|         | list name         | name   | label  |
|         | fruits            | orange | Orange |
|         | fruits            | mango  | Mango  |
"""


MD2 = """
| survey  |
|         | type              | name  | label   |
|         | select one fruits | fruits | Fruit   |

| choices |
|         | list name         | name   | label  |
|         | fruits            | apple  | Apple  |
|         | fruits            | cherries  | Cherries  |
"""


class TestChartsViewSet(TestBase):
    def setUp(self):
        super(self.__class__, self).setUp()
        # publish tutorial form as it has all the different field types
        self._publish_xls_file_and_set_xform(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "fixtures",
                "forms",
                "tutorial",
                "tutorial.xlsx",
            )
        )
        self.api_client = APIClient()
        self.api_client.login(
            username=self.login_username, password=self.login_password
        )
        self.view = ChartsViewSet.as_view({"get": "retrieve"})
        self.factory = APIRequestFactory()
        self._make_submission(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "fixtures",
                "forms",
                "tutorial",
                "instances",
                "1.xml",
            )
        )
        self._make_submission(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "fixtures",
                "forms",
                "tutorial",
                "instances",
                "2.xml",
            )
        )
        self._make_submission(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "fixtures",
                "forms",
                "tutorial",
                "instances",
                "3.xml",
            )
        )

    def test_correct_merged_dataset_data_for_charts(self):
        """Return correct data from the charts endpoint"""
        view = MergedXFormViewSet.as_view(
            {
                "post": "create",
            }
        )
        # pylint: disable=attribute-defined-outside-init
        self.project = get_user_default_project(self.user)
        xform_a = self._publish_markdown(MD, self.user, id_string="a")
        xform_b = self._publish_markdown(MD2, self.user, id_string="b")

        data = {
            "xforms": [
                "http://testserver/api/v1/forms/%s" % xform_a.pk,
                "http://testserver/api/v1/forms/%s" % xform_b.pk,
            ],
            "name": "Merged Dataset",
            "project": f"http://testserver/api/v1/projects/{self.project.pk}",
        }
        # anonymous user
        request = self.factory.post("/", data=data)
        response = view(request)
        self.assertEqual(response.status_code, 401)

        request = self.factory.post("/", data=data)
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertEqual(response.status_code, 201)

        # make submission to form a
        xml = '<data id="b"><fruits>orange mango</fruits></data>'
        Instance(xform=xform_a, xml=xml).save()

        # make submission to form b
        xml = '<data id="b"><fruits>apple cherries</fruits></data>'
        Instance(xform=xform_b, xml=xml).save()

        data = {"field_xpath": "fruits"}
        request = self.factory.get("/charts", data=data)
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=response.data["id"])
        self.assertEqual(response.status_code, 200)
        # check that the data is correct
        expected_data = [
            {"fruits": ["Apple", "Cherries"], "count": 1},
            {"fruits": ["Orange", "Mango"], "count": 1},
        ]
        self.assertEqual(response.data["data"], expected_data)
        # Ensure response is renderable
        response.render()
        cache.clear()

    def test_duration_field_on_metadata(self):
        # the instance below has valid start and end times
        instance = Instance.objects.all()[0]
        _dict = instance.parsed_instance.to_dict_for_mongo()
        self.assertIn("_duration", list(_dict))
        self.assertEqual(_dict.get("_duration"), 24.0)
        self.assertNotEqual(_dict.get("_duration"), None)

        _dict = instance.json
        duration = calculate_duration(_dict.get("start_time"), "invalid")
        self.assertIn("_duration", list(_dict))
        self.assertEqual(duration, "")
        self.assertNotEqual(duration, None)

    def test_get_on_categorized_field(self):
        data = {"field_name": "gender"}
        request = self.factory.get("/charts", data)
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=self.xform.id, format="html")
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.data["field_type"], "select one")
        self.assertEqual(response.data["field_name"], "gender")
        self.assertEqual(response.data["data_type"], "categorized")
        self.assertEqual(response.data["data"][0]["gender"], "Male")
        self.assertEqual(response.data["data"][1]["gender"], "Female")

    def test_get_on_date_field(self):
        data = {"field_name": "date"}
        request = self.factory.get("/charts", data)
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=self.xform.id)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.data["field_type"], "date")
        self.assertEqual(response.data["field_name"], "date")
        self.assertEqual(response.data["data_type"], "time_based")

    @patch("onadata.libs.data.query._execute_query", side_effect=raise_data_error)
    def test_get_on_date_field_with_invalid_data(self, mock_execute_query):
        data = {"field_name": "date"}
        request = self.factory.get("/charts", data)
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=self.xform.id)
        self.assertEqual(response.status_code, 400)

    def test_get_on_numeric_field(self):
        data = {"field_name": "age"}
        request = self.factory.get("/charts", data)
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=self.xform.id)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.data["field_type"], "integer")
        self.assertEqual(response.data["field_name"], "age")
        self.assertEqual(response.data["data_type"], "numeric")

    def test_get_on_select_field(self):
        data = {"field_name": "gender"}
        request = self.factory.get("/charts", data)
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=self.xform.id)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.data["field_type"], "select one")
        self.assertEqual(response.data["field_name"], "gender")
        self.assertEqual(response.data["data_type"], "categorized")

    def test_get_on_select_field_xpath(self):
        data = {"field_xpath": "gender"}
        request = self.factory.get("/charts", data)
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=self.xform.id)

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.data["field_type"], "select one")
        self.assertEqual(response.data["field_name"], "gender")
        self.assertEqual(response.data["data_type"], "categorized")

    def test_get_on_select_multi_field(self):
        field_name = "favorite_toppings"
        data = {"field_name": field_name}
        request = self.factory.get("/charts", data)
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=self.xform.id)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.data["field_type"], "select all that apply")
        self.assertEqual(response.data["field_name"], field_name)
        self.assertEqual(response.data["data_type"], "categorized")

        options = response.data["data"][0][field_name]
        self.assertEqual(options, ["Green Peppers", "Pepperoni"])

    def test_get_on_select_multi_field_html_format(self):
        field_name = "favorite_toppings"
        data = {"field_name": field_name}
        request = self.factory.get("/charts", data)
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=self.xform.id, format="html")
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.data["field_type"], "select all that apply")
        self.assertEqual(response.data["field_name"], field_name)
        self.assertEqual(response.data["data_type"], "categorized")

        options = response.data["data"][0][field_name]
        self.assertEqual(options, "Green Peppers, Pepperoni")

    def test_get_all_fields(self):
        data = {"fields": "all"}
        request = self.factory.get("/", data)
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=self.xform.id)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertIn("age", response.data)
        self.assertIn("date", response.data)
        self.assertIn("gender", response.data)
        self.assertEqual(response.data["age"]["field_type"], "integer")
        self.assertEqual(response.data["age"]["field_name"], "age")
        self.assertEqual(response.data["age"]["data_type"], "numeric")

    def test_get_specific_fields(self):
        data = {"fields": "date,age"}
        request = self.factory.get("/", data)
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=self.xform.id)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get("Cache-Control"), None)

        self.assertNotIn("gender", response.data)

        self.assertIn("age", response.data)
        data = response.data["age"]
        self.assertEqual(data["field_type"], "integer")
        self.assertEqual(data["field_name"], "age")
        self.assertEqual(data["data_type"], "numeric")

        self.assertIn("date", response.data)
        data = response.data["date"]
        self.assertEqual(data["field_type"], "date")
        self.assertEqual(data["field_name"], "date")
        self.assertEqual(data["data_type"], "time_based")

    def test_get_invalid_field_name(self):
        data = {"fields": "invalid_field_name"}
        request = self.factory.get("/", data)
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=self.xform.id)
        self.assertEqual(response.status_code, 404)

    def test_chart_list(self):
        self.view = ChartsViewSet.as_view({"get": "list"})
        request = self.factory.get("/charts")
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        data = {
            "id": self.xform.pk,
            "id_string": self.xform.id_string,
            "url": "http://testserver/api/v1/charts/%s" % self.xform.pk,
        }
        self.assertEqual(response.data, [data])

        request = self.factory.get("/charts")
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_chart_list_with_xform_in_delete_async(self):
        self.view = ChartsViewSet.as_view({"get": "list"})
        request = self.factory.get("/charts")
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        data = {
            "id": self.xform.pk,
            "id_string": self.xform.id_string,
            "url": "http://testserver/api/v1/charts/%s" % self.xform.pk,
        }
        self.assertEqual(response.data, [data])

        self.xform.deleted_at = timezone.now()
        self.xform.save()
        request = self.factory.get("/charts")
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_cascading_select(self):
        # publish tutorial form as it has all the different field types
        self._publish_xls_file_and_set_xform(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "fixtures",
                "forms",
                "cascading",
                "cascading.xlsx",
            )
        )

        self._make_submission(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "fixtures",
                "forms",
                "cascading",
                "instances",
                "1.xml",
            )
        )
        self._make_submission(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "fixtures",
                "forms",
                "cascading",
                "instances",
                "2.xml",
            )
        )
        self._make_submission(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "fixtures",
                "forms",
                "cascading",
                "instances",
                "3.xml",
            )
        )
        self._make_submission(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "fixtures",
                "forms",
                "cascading",
                "instances",
                "4.xml",
            )
        )

        data = {"field_name": "cities"}
        request = self.factory.get("/charts", data)
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=self.xform.id, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data)
        expected = [
            {"cities": ["Nice"], "count": 1},
            {"cities": ["Seoul"], "count": 1},
            {"cities": ["Cape Town"], "count": 2},
        ]
        self.assertEqual(expected, response.data["data"])

    @override_settings(XFORM_CHARTS_CACHE_TIME=0)
    def test_deleted_submission_not_in_chart_endpoint(self):
        data = {"field_name": "gender"}
        request = self.factory.get("/charts", data)
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=self.xform.id, format="html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sum([i["count"] for i in response.data["data"]]), 3)

        # soft delete one instance

        inst = self.xform.instances.all()[0]
        inst.set_deleted(timezone.now())

        response = self.view(request, pk=self.xform.id, format="html")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(sum([i["count"] for i in response.data["data"]]), 2)

    def test_nan_not_json_response(self):
        self._make_submission(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "fixtures",
                "forms",
                "tutorial",
                "instances",
                "nan_net_worth.xml",
            )
        )

        data = {"field_name": "networth_calc", "group_by": "pizza_fan"}
        request = self.factory.get("/charts", data)
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=self.xform.id, format="json")
        renderer = DecimalJSONRenderer()
        res = json.loads(renderer.render(response.data).decode("utf-8"))

        expected = {
            "field_type": "calculate",
            "data_type": "numeric",
            "field_xpath": "networth_calc",
            "data": [
                {"count": 2, "sum": 150000.0, "pizza_fan": ["No"], "mean": 75000.0},
                {"count": 2, "sum": None, "pizza_fan": ["Yes"], "mean": None},
            ],
            "grouped_by": "pizza_fan",
            "field_label": "Networth Calc",
            "field_name": "networth_calc",
            "xform": self.xform.pk,
        }
        self.assertEqual(expected, res)

    def test_on_charts_with_content_type(self):
        request = self.factory.get("/charts", content_type="application/json")
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=self.xform.pk, id_string=self.xform.id_string)
        expected = {
            "id": self.xform.pk,
            "id_string": self.xform.id_string,
            "url": "http://testserver/api/v1/charts/{}".format(self.xform.pk),
        }
        self.assertEqual(200, response.status_code)
        self.assertDictContainsSubset(expected, response.data)

        # If content-type is not returned; Assume that the desired
        # response is JSON
        request = self.factory.get("/")
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=self.xform.pk)
        self.assertEqual(200, response.status_code)
        self.assertDictContainsSubset(expected, response.data)

    def test_charts_caching(self):
        """
        Test that the chart endpoints caching works as expected
        """
        data = {"field_name": "gender"}
        request = self.factory.get("/charts", data)
        force_authenticate(request, user=self.user)
        cache_key = f"{XFORM_CHARTS}{self.xform.id}NonegenderNonehtml"
        initial_data = {"some_data": "some_value"}
        cache.set(cache_key, initial_data)

        response = self.view(request, pk=self.xform.id, format="html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, initial_data)

        # Ensure that the initially cached data is refreshed
        # when `refresh` query param is true
        data["refresh"] = "true"
        request = self.factory.get("/charts", data)
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=self.xform.id, format="html")
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.data, initial_data)

    def test_charts_group_by_select_one(self):
        """
        Test that the chart endpoint works correctly
        when grouping with select one field
        """
        data = {"field_name": "gender", "group_by": "pizza_fan"}
        request = self.factory.get("/charts", data)
        force_authenticate(request, user=self.user)
        initial_data = {
            "data": [
                {
                    "gender": ["Male"],
                    "items": [
                        {"pizza_fan": ["No"], "count": 1},
                    ],
                },
                {
                    "gender": ["Female"],
                    "items": [
                        {"pizza_fan": ["No"], "count": 1},
                        {"pizza_fan": ["Yes"], "count": 1},
                    ],
                },
            ],
            "data_type": "categorized",
            "field_label": "Gender",
            "field_xpath": "gender",
            "field_name": "gender",
            "field_type": "select one",
            "grouped_by": "pizza_fan",
            "xform": self.xform.pk,
        }

        response = self.view(request, pk=self.xform.id)
        self.assertEqual(response.status_code, 200)
        # response.data['data'] items can be in any order
        self.assertCountEqual(response.data.pop("data"), initial_data.pop("data"))
        self.assertEqual(response.data, initial_data)
