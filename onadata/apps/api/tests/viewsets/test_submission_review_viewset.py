"""
Submission Review ViewSet Tests Module
"""
from __future__ import unicode_literals

from django.test import RequestFactory

from onadata.apps.api.viewsets.submission_review_viewset import \
    SubmissionReviewViewSet
from onadata.apps.logger.models import SubmissionReview
from onadata.apps.main.tests.test_base import TestBase


class TestSubmissionReviewViewSet(TestBase):
    """
    Test SubmissionReviewViewset Class
    """

    def setUp(self):
        super(TestSubmissionReviewViewSet, self).setUp()
        self._create_user_and_login()
        self._publish_transportation_form()
        self._make_submissions()
        self.factory = RequestFactory()
        self.extra = {'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

    @property
    def _first_xform_instance(self):
        """
        Retuns the first instance for an xform
        """
        return self.xform.instances.all().order_by('pk')[0]

    def _create_submission_review(self):
        """
        Utility method creates Submission Review
        """
        instance_id = self._first_xform_instance.pk
        submission_data = {
            'note_text': "Supreme Overload!",
            'instance': instance_id
        }

        view = SubmissionReviewViewSet.as_view({'post': 'create'})
        request = self.factory.post('/', data=submission_data, **self.extra)
        response = view(request=request)

        self.assertEqual(201, response.status_code)
        self.assertEqual("Supreme Overload!", response.data['note_text'])
        self.assertEqual(instance_id, response.data['instance'])

        return response.data

    def test_submission_review_create(self):
        """
        Test we can create a submission review
        """
        self._create_submission_review()

    def test_submission_review_list(self):
        """
        Test we can list submission reviews
        """
        submission_review_data = self._create_submission_review()
        self._create_submission_review()

        view = SubmissionReviewViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)

        response = view(request=request)

        self.assertEqual(200, response.status_code)
        self.assertEqual(2, len(response.data))
        self.assertEqual(submission_review_data['id'], response.data[0]['id'])

    def test_retrieve_submission_review(self):
        """
        Test we can retrieve a submission review
        """
        submission_review_data = self._create_submission_review()

        view = SubmissionReviewViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get('/', **self.extra)
        response = view(request=request, pk=submission_review_data['id'])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(submission_review_data['id'], response.data['id'])

    def test_submission_review_update(self):
        """
        Test that we can update submission_reviews
        """
        # TODO: Pass Test
        data = self._create_submission_review()

        new_data = {
            'note_text': "My name is Davis!",
            'status': SubmissionReview.APPROVED
        }

        view = SubmissionReviewViewSet.as_view({'patch': 'partial_update'})
        request = self.factory.patch('/', data=new_data)
        response = view(request=request, pk=data['id'])

        self.assertEqual(200, response.status_code)

    def test_delete_submission_review(self):
        """
        Test:
            - Soft-Deletes Submission Review
            - Deleted Submission Reviews Do not show up on
              on list
        """
        # TODO: Pass Test
        submission_review_data = self._create_submission_review()

        submission_review = SubmissionReview.objects.get(
            id=submission_review_data['id'])

        # Shows up on list
        view = SubmissionReviewViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)

        response = view(request=request)

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.data))

        view = SubmissionReviewViewSet.as_view({'delete': 'destroy'})
        request = self.factory.delete('/', **self.extra)
        response = view(request=request, pk=submission_review.id)

        self.assertEqual(response.status_code, 200)

        # Doesn't show up on list after deletion
        view = SubmissionReviewViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)

        response = view(request=request)

        self.assertEqual(200, response.status_code)
        self.assertEqual(0, len(response.data))
