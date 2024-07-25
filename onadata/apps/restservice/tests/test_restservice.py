# -*- coding: utf-8 -*-
"""
Test RestService model
"""
import os
import time
from unittest.mock import patch

from django.test.utils import override_settings
from django.urls import reverse

from onadata.apps.logger.models.xform import XForm
from onadata.apps.main.models import MetaData
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.main.views import show
from onadata.apps.restservice.models import RestService
from onadata.apps.restservice.interface import RestServiceInterface
from onadata.apps.restservice.services.textit import ServiceDefinition
from onadata.apps.restservice.views import add_service, delete_service


class RestServiceTest(TestBase):
    """
    Test RestService model
    """

    def setUp(self):
        self.service_url = "http://0.0.0.0:8001/%(id_string)s/post/%(uuid)s"
        self.service_name = "f2dhis2"
        self._create_user_and_login()
        filename = "dhisform.xlsx"
        self.this_directory = os.path.dirname(__file__)
        path = os.path.join(self.this_directory, "fixtures", filename)
        self._publish_xls_file(path)
        self.xform = XForm.objects.all().reverse()[0]

    def wait(self, duration=1):
        """Sleep for 1 second or as defined by ``duration``."""
        time.sleep(duration)

    def _create_rest_service(self):
        service = RestService(
            service_url=self.service_url, xform=self.xform, name=self.service_name
        )
        service.save()

        return service

    def _add_rest_service(self, service_url, service_name):
        add_service_url = reverse(
            add_service,
            kwargs={"username": self.user.username, "id_string": self.xform.id_string},
        )
        response = self.client.get(add_service_url, {})
        count = RestService.objects.all().count()
        self.assertEqual(response.status_code, 200)
        post_data = {"service_url": service_url, "service_name": service_name}
        response = self.client.post(add_service_url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(RestService.objects.all().count(), count + 1)

    # pylint: disable=invalid-name
    def add_rest_service_with_username_and_id_string_in_uppercase(self):
        """Test that the service url is not case sensitive"""
        add_service_url = reverse(
            add_service,
            kwargs={
                "username": self.user.username.upper(),
                "id_string": self.xform.id_string.upper(),
            },
        )
        response = self.client.get(add_service_url, {})
        self.assertEqual(response.status_code, 200)

    def test_create_rest_service(self):
        """Test the RestService model."""
        count = RestService.objects.all().count()
        self._create_rest_service()
        self.assertEqual(RestService.objects.all().count(), count + 1)

    def test_service_definition(self):
        """Test the service_definition is an instance of RestServiceInterface"""
        restservice = self._create_rest_service()
        service = restservice.get_service_definition()()
        self.assertEqual(isinstance(service, RestServiceInterface), True)

    def test_add_service(self):
        """Test adding a restservice."""
        self._add_rest_service(self.service_url, self.service_name)

    def test_anon_service_view(self):
        """Test the rest service section is not available to asynchronous users."""
        self.xform.shared = True
        self.xform.save()
        self._logout()
        url = reverse(
            show,
            kwargs={
                "username": self.xform.user.username,
                "id_string": self.xform.id_string,
            },
        )
        response = self.client.get(url)
        self.assertNotContains(
            response,
            '<h3 data-toggle="collapse" class="toggler" data-target='
            '"#restservice_tab">Rest Services</h3>',
        )

    def test_delete_service(self):
        """Test deletion of a service."""
        self._add_rest_service(self.service_url, self.service_name)
        count = RestService.objects.all().count()
        service = RestService.objects.reverse()[0]
        post_data = {"service-id": service.pk}
        del_service_url = reverse(
            delete_service,
            kwargs={"username": self.user.username, "id_string": self.xform.id_string},
        )
        response = self.client.post(del_service_url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(RestService.objects.all().count(), count - 1)

    # pylint: disable=invalid-name
    def test_add_rest_service_with_wrong_id_string(self):
        """Test the id_string is validated when adding a service url."""
        add_service_url = reverse(
            add_service,
            kwargs={"username": self.user.username, "id_string": "wrong_id_string"},
        )
        post_data = {"service_url": self.service_url, "service_name": self.service_name}
        response = self.client.post(add_service_url, post_data)
        self.assertEqual(response.status_code, 404)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch("requests.post")
    def test_textit_service(self, mock_http):
        """Test the textit service."""
        service_url = "https://textit.io/api/v1/runs.json"
        service_name = "textit"

        self._add_rest_service(service_url, service_name)

        # add metadata
        api_token = "asdaasda"
        flow_uuid = "getvdgdfd"
        default_contact = "sadlsdfskjdfds"

        MetaData.textit(
            self.xform,
            data_value=f"{api_token}|{flow_uuid}|{default_contact}",
        )

        xml_submission = os.path.join(
            self.this_directory, "fixtures", "dhisform_submission1.xml"
        )

        self.assertFalse(mock_http.called)
        self._make_submission(xml_submission)
        self.assertTrue(mock_http.called)
        self.assertEqual(mock_http.call_count, 1)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch("requests.post")
    def test_rest_service_not_set(self, mock_http):
        """Test a requests.post is not called when a service is not defined."""
        xml_submission = os.path.join(
            self.this_directory, "fixtures", "dhisform_submission1.xml"
        )

        self.assertFalse(mock_http.called)
        self._make_submission(xml_submission)
        self.assertFalse(mock_http.called)
        self.assertEqual(mock_http.call_count, 0)

    def test_clean_keys_of_slashes(self):
        """Test ServiceDefinition.clean_keys_of_slashes() function."""
        service = ServiceDefinition()

        test_data = {
            "hh/group/data_set": "22",
            "empty_column": "",
            "false_column": False,
            "zero_column": 0,
        }

        expected_data = {
            "hh_group_data_set": "22",
            "false_column": "False",
            "zero_column": "0",
        }

        self.assertEqual(expected_data, service.clean_keys_of_slashes(test_data))
