"""
Submission Review ViewSet Tests Module
"""
from __future__ import unicode_literals

from guardian.shortcuts import assign_perm

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.submission_review_viewset import \
    SubmissionReviewViewSet
from onadata.apps.logger.models import SubmissionReview


class TestSubmissionReviewViewSet(TestAbstractViewSet):
    """
    Test SubmissionReviewViewset Class
    """

    def setUp(self):
        super(TestSubmissionReviewViewSet, self).setUp()
        self._publish_form_with_hxl_support()

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
        # TODO: Pass Text
        data = self._create_submission_review()

        assign_perm('logger.change_submissionreview', self.user)

        new_data = {
            'note_text': "My name is Davis!",
            'status': SubmissionReview.APPROVED
        }

        view = SubmissionReviewViewSet.as_view({'patch': 'partial_update'})
        request = self.factory.patch('/', data=new_data, **self.extra)
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

        assign_perm('logger.delete_submissionreview', self.user)

        # Shows up on list
        view = SubmissionReviewViewSet.as_view({
            'get': 'list',
            'delete': 'destroy'
        })
        request = self.factory.get('/', **self.extra)

        response = view(request=request)

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.data))

        request = self.factory.delete('/', **self.extra)
        response = view(request=request, pk=submission_review_data['id'])

        self.assertEqual(200, response.status_code)

        # Doesn't show up on list after deletion
        request = self.factory.get('/', **self.extra)
        response = view(request=request)

        self.assertEqual(200, response.status_code)
        self.assertEqual(0, len(response.data))
