from rest_framework.test import APIRequestFactory
from django_digest.test import DigestAuth
from django.http import Http404

from onadata.apps.api.viewsets.xform_submission_viewset import XFormSubmissionViewSet
from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.libs.serializers.data_serializer import SubmissionSerializer, get_request_and_username


class SubmissionViewMock:
    """ Mocks XFormSubmissionViewSet class """

    def __init__(self, kwargs_object):
        self.kwargs = kwargs_object


class TestDataSerializer(TestAbstractViewSet):
    """
    Test Data serializer and support methods
    """

    def setUp(self):
        self._login_user_and_profile()
        self.factory = APIRequestFactory()
  
    def test_get_request_and_username(self):
        """
        Test get_request_and_username works as expected
        """
        self._publish_xls_form_to_project()
        user = self.xform.user
        project = self.xform.project
        view = SubmissionViewMock({"username": user.username})

        request = self.factory.post(f"/projects/{project.pk}/submission", {})
        response = get_request_and_username(
            {"request": request, "view": view}
        )
        self.assertEqual(response, (request, user.username))

        view.kwargs = {"project_pk": project.pk}
        response = get_request_and_username(
            {"request": request, "view": view}
        )
        self.assertEqual(response, (request, user.username))

        view.kwargs = {"project_pk": 1000}
        with self.assertRaises(Http404):
            get_request_and_username(
                {"request": request, "view": view}
            )

        view.kwargs = {"xform_pk": self.xform.pk}
        request = self.factory.post(f"/projects/{self.xform.pk}/submission", {})
        response = get_request_and_username(
            {"request": request, "view": view}
        )
        self.assertEqual(response, (request, user.username))

        view.kwargs = {"xform_pk": 1000}
        with self.assertRaises(Http404):
            get_request_and_username(
                {"request": request, "view": view}
            )
        
        view.kwargs = {}
        request.user = user
        response = get_request_and_username(
            {"request": request, "view": view}
        )
        self.assertEqual(response, (request, user.username))