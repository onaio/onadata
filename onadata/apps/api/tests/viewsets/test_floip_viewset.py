# -*- coding: utf-8 -*-
"""
Test FloipViewset module.
"""
import json
import os
import uuid as uu
from builtins import open

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.viewsets.floip_viewset import FloipViewSet
from onadata.apps.api.viewsets.merged_xform_viewset import MergedXFormViewSet
from onadata.apps.logger.models import Instance, XForm
from onadata.libs.utils.user_auth import get_user_default_project


class TestFloipViewSet(TestAbstractViewSet):
    """
    Test FloipViewSet class.
    """

    def _publish_floip(self, path="flow-results-example-2-api.json", test=True):
        self.skipTest("FLOIP package out of date with pyxform 3.0.0")
        view = FloipViewSet.as_view({"post": "create"})
        path = os.path.join(os.path.dirname(__file__), "../", "fixtures", path)
        with open(path, encoding="utf-8") as json_file:
            post_data = json_file.read()
            request = self.factory.post(
                "/",
                data=post_data,
                content_type="application/vnd.api+json",
                **self.extra,
            )
            response = view(request)
            if test:
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response["Content-Type"], "application/vnd.api+json")
                self.assertEqual(
                    response["Location"],
                    "http://testserver/api/v1/flow-results/packages/"
                    + response.data["id"],
                )
                self.assertEqual(response.data["profile"], "flow-results-package")
            return response.data

    def test_publishing_descriptor(self):
        """
        Tests publishing a Flow results descriptor file creates a form.
        """
        xforms = XForm.objects.count()
        self._publish_floip()
        self.assertEqual(xforms + 1, XForm.objects.count())

    def test_publishing_descriptor_w_id(self):
        """
        Tests publishing a Flow results descriptor file creates a form and
        maintains user defined id.
        """
        xforms = XForm.objects.count()
        data = self._publish_floip(path="flow-results-example-w-uuid.json")
        self.assertEqual(data["id"], "ee21fa6f-3027-4bdd-a534-1bb324782b6f")
        response = self._publish_floip(
            path="flow-results-example-w-uuid.json", test=False
        )
        self.assertEqual(
            response["text"],
            "An xform with uuid: ee21fa6f-3027-4bdd-a534-1bb324782b6f already"
            " exists",
        )
        self.assertEqual(xforms + 1, XForm.objects.count())

    def test_list_package(self):
        """
        Test list endpoint for packages.
        """
        view = FloipViewSet.as_view({"get": "list"})
        data = self._publish_floip(path="flow-results-example-w-uuid.json")
        request = self.factory.get(
            "/flow-results/packages",
            content_type="application/vnd.api+json",
            **self.extra,
        )
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("created", response.data[0])
        self.assertIn("modified", response.data[0])
        self.assertEqual(response.data[0]["name"], data["name"])
        self.assertEqual(response.data[0]["title"], data["title"])
        self.assertEqual(response.data[0]["id"], data["id"])

        # render and change that JSON API returns the same id/uuid
        response.render()
        rendered_data = json.loads(response.rendered_content)
        self.assertEqual(rendered_data["data"][0]["id"], data["id"])
        self.assertEqual(rendered_data["data"][0]["type"], "packages")

    def test_retrieve_package(self):
        """
        Test retrieving a specific package.
        """
        view = FloipViewSet.as_view({"get": "retrieve"})
        data = self._publish_floip(path="flow-results-example-w-uuid.json")
        request = self.factory.get(
            "/flow-results/packages/" + data["id"],
            content_type="application/vnd.api+json",
            **self.extra,
        )
        response = view(request, uuid=data["id"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data)

        # render and change that JSON API returns the same id/uuid
        response.render()
        rendered_data = json.loads(response.rendered_content)
        self.assertEqual(rendered_data["data"]["id"], data["id"])

        # Test able to retrieve package using a complete uuid4 string
        data_id = uu.UUID(data["id"], version=4)
        response = view(request, uuid=str(data_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data)

        # Test able to retrieve package using only the hex
        # characters of a uuid string
        response = view(request, uuid=data_id.hex)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data)

        # Test able to retrieve public package
        form: XForm = XForm.objects.filter(uuid=data["id"]).first()
        form.shared = True
        form.shared_data = True
        form.save()
        data["modified"] = form.date_modified
        response = view(request, uuid=str(data_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data)

    def test_update_package(self):
        """
        Test updating a specific package.
        """
        view = FloipViewSet.as_view({"put": "update"})
        data = self._publish_floip(path="flow-results-example-w-uuid.json")
        question = "f1448506774982_01"
        self.assertNotIn(question, data["resources"][0]["schema"]["questions"])
        path = os.path.join(
            os.path.dirname(__file__),
            "../",
            "fixtures",
            "flow-results-example-w-uuid-update.json",
        )
        with open(path, encoding="utf-8") as json_file:
            post_data = json_file.read()
            request = self.factory.put(
                "/flow-results/packages/" + data["id"],
                data=post_data,
                content_type="application/vnd.api+json",
                **self.extra,
            )
            response = view(request, uuid=data["id"])
            self.assertEqual(response.status_code, 200)
            response.render()
            self.assertEqual(response["Content-Type"], "application/vnd.api+json")
            self.assertEqual(response.data["profile"], "flow-results-package")
            self.assertIn(
                question, response.data["resources"][0]["schema"]["questions"]
            )

    def test_publishing_responses(self):
        """
        Test publishing Flow results.
        """
        count = Instance.objects.count()
        floip_data = self._publish_floip()
        view = FloipViewSet.as_view({"post": "responses"})
        path = os.path.join(
            os.path.dirname(__file__),
            "../",
            "fixtures",
            "flow-results-example-2-api-data.json",
        )
        with open(path, encoding="utf-8") as json_file:
            descriptor = json.load(json_file)
            descriptor["data"]["id"] = floip_data["id"]
            request = self.factory.post(
                "/",
                data=json.dumps(descriptor),
                content_type="application/vnd.api+json",
                **self.extra,
            )
            response = view(request, uuid=floip_data["id"])
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response["Content-Type"], "application/vnd.api+json")
            self.assertEqual(
                response["Location"],
                "http://testserver/api/v1/flow-results/packages/"
                + floip_data["id"]
                + "/responses",
            )
            self.assertEqual(count + 2, Instance.objects.count())

            request = self.factory.post(
                "/",
                data=json.dumps(descriptor),
                content_type="application/vnd.api+json",
                **self.extra,
            )
            response = view(request, uuid=floip_data["id"])
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response["Content-Type"], "application/vnd.api+json")
            self.assertEqual(
                response["Location"],
                "http://testserver/api/v1/flow-results/packages/"
                + floip_data["id"]
                + "/responses",
            )
            self.assertEqual(count + 2, Instance.objects.count())

    def test_publish_number_question_names(self):  # pylint: disable=C0103
        """
        Test publishing a descriptor with question identifiers that start with
        a number.
        """
        self.skipTest("FLOIP package out of date with pyxform 3.0.0")
        view = FloipViewSet.as_view({"post": "create"})
        path = os.path.join(
            os.path.dirname(__file__),
            "../",
            "fixtures",
            "flow-results-number-question-names.json",
        )
        with open(path, encoding="utf-8") as json_file:
            post_data = json_file.read()
            request = self.factory.post(
                "/",
                data=post_data,
                content_type="application/vnd.api+json",
                **self.extra,
            )
            response = view(request)
            response.render()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response["Content-Type"], "application/vnd.api+json")
            self.assertIn(
                "The name '1448506769745_42' contains an invalid character '1'",
                response.data["text"],
            )

    def test_responses_endpoint_format(self):
        """
        Test that the responses endpoint returns flow results in the correct
        format following the flow-results-spec
        """
        floip_data = self._publish_floip()
        view = FloipViewSet.as_view({"post": "responses", "get": "responses"})

        correct_response_format = {
            "data": {
                "type": "flow-results-data",
                "id": floip_data["id"],
                "attributes": {"responses": []},
            }
        }

        request = self.factory.get(
            "/flow-results/packages/" + floip_data["id"] + "/responses",
            content_type="application/vnd.api+json",
            **self.extra,
        )
        response = view(request, uuid=floip_data["id"])
        self.assertEqual(response.status_code, 200)

        # Convert the return generator object into a list
        response.data["attributes"]["responses"] = list(
            response.data["attributes"]["responses"]
        )

        self.assertEqual(response.data, correct_response_format["data"])
        # The FLOIP Endpoint should always return the complete uuid
        # hex digits + dashes
        self.assertEqual(len(response.data["id"]), 36)

    # pylint:disable=invalid-name
    def test_retrieve_responses_merged_dataset(self):
        """
        Test that a user is able to retrieve FLOIP Responses for Merged
        XForms
        """
        MD = """
            | survey  |
            |         | type  | name   | label   |
            |         | photo | image1 | Photo   |
            """
        # Create Merged XForm
        merged_dataset_view = MergedXFormViewSet.as_view(
            {
                "post": "create",
            }
        )

        project = get_user_default_project(self.user)
        self._publish_xls_form_to_project()
        self._make_submissions()
        xform = self._publish_markdown(MD, self.user, id_string="a")

        data = {
            "xforms": [
                f"http://testserver/api/v1/forms/{self.xform.pk}",
                f"http://testserver/api/v1/forms/{xform.pk}",
            ],
            "name": "Merged Dataset",
            "project": f"http://testserver/api/v1/projects/{project.pk}",
        }

        request = self.factory.post("/", data=data, **self.extra)
        response = merged_dataset_view(request)
        self.assertEqual(response.status_code, 201)
        dataset_uuid = response.data["uuid"]

        # Assert that it's possible to retrieve the responses
        view = FloipViewSet.as_view({"get": "responses"})
        request = self.factory.get(
            f"/flow-results/packages/{dataset_uuid}/responses",
            content_type="application/vnd.api+json",
            **self.extra,
        )
        response = view(request, uuid=dataset_uuid)
        self.assertEqual(response.status_code, 200)

        # Convert the returned generator object into a list
        response.data["attributes"]["responses"] = list(
            response.data["attributes"]["responses"]
        )
        # The transportation form(self.xform) contains 11 responses
        # Assert that the responses are returned
        self.assertEqual(len(response.data["attributes"]["responses"]), 11)
