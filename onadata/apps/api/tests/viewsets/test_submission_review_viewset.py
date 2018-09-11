"""
Submission Review ViewSet Tests Module
"""
from __future__ import unicode_literals

from guardian.shortcuts import assign_perm
from rest_framework.test import APIRequestFactory

from onadata.apps.api.viewsets.submission_review_viewset import \
    SubmissionReviewViewSet
from onadata.apps.logger.models import SubmissionReview, Instance
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import CAN_CHANGE_XFORM
from onadata.libs.utils.common_tags import REVIEW_STATUS, REVIEW_COMMENT


class TestSubmissionReviewViewSet(TestBase):
    """
    Test SubmissionReviewViewset Class
    """

    def setUp(self):
        super(TestSubmissionReviewViewSet, self).setUp()
        self._create_user_and_login()
        self._publish_transportation_form()
        self._make_submissions()
        self.factory = APIRequestFactory()
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
        instance_id = self._first_xform_instance.id
        submission_data = {
            'note': "Supreme Overload!",
            'instance': instance_id
        }

        view = SubmissionReviewViewSet.as_view({'post': 'create'})
        request = self.factory.post('/', data=submission_data, **self.extra)
        response = view(request=request)

        self.assertEqual(201, response.status_code)
        self.assertEqual("Supreme Overload!", response.data['note'])
        self.assertEqual(instance_id, response.data['instance'])

        return response.data

    def test_submission_review_create(self):
        """
        Test we can create a submission review
        """
        self._create_submission_review()

    def test_bulk_create_submission_review(self):
        """
        Test that we can bulk create submission reviews
        """
        instances = self.xform.instances.all()
        submission_data = [
            {
                'note': 'This is not very good, is it?',
                'instance': _.id,
                'status': SubmissionReview.REJECTED
            } for _ in instances
        ]
        view = SubmissionReviewViewSet.as_view({'post': 'create'})

        # get DRF to use the JSON renderer as other renderes are likely to fail
        self.extra['format'] = 'json'

        request = self.factory.post('/', data=submission_data, **self.extra)
        response = view(request=request)

        self.assertEqual(201, response.status_code)
        self.assertEqual(4, len(response.data))
        already_seen = []
        for item in response.data:
            # the note should match what we provided
            self.assertEqual('This is not very good, is it?', item['note'])
            # the status should be rejected
            self.assertEqual(SubmissionReview.REJECTED, item['status'])
            # the instance id must be valid
            self.assertTrue(instances.filter(id=item['instance']).exists())
            # all the submission reviews must have different instance fields
            self.assertFalse(item['instance'] in already_seen)
            already_seen.append(item['instance'])
            # ensure that the instance JSON has the submission fields
            instance = Instance.objects.get(pk=item['instance'])
            self.assertEqual(
                'This is not very good, is it?',
                instance.json[REVIEW_COMMENT])
            self.assertEqual(
                SubmissionReview.REJECTED, instance.json[REVIEW_STATUS])

    def test_bulk_create_submission_review_permissions(self):
        """
        Test that bulk create fails when the user has no permission to
        any submission
        """
        instances = self.xform.instances.all()
        submission_data = [
            {
                'note': 'Nope!!',
                'instance': _.id,
                'status': SubmissionReview.REJECTED
            } for _ in instances
        ]

        self._create_user_and_login('dave', '1234')
        extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token,
            'format': 'json'
        }

        view = SubmissionReviewViewSet.as_view({'post': 'create'})

        # dave should not be able to bulk create submission reviews
        request = self.factory.post('/', data=submission_data, **extra)
        response = view(request=request)

        self.assertEqual(403, response.status_code)

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
        data = self._create_submission_review()

        new_data = {
            'note': "My name is Davis!",
            'status': SubmissionReview.APPROVED
        }

        view = SubmissionReviewViewSet.as_view({'patch': 'partial_update'})
        request = self.factory.patch('/', data=new_data, **self.extra)
        response = view(request=request, pk=data['id'])

        self.assertEqual(200, response.status_code)

    def test_submission_review_permission(self):
        """
        Test that submission review access to unauthorized users
        """
        data = self._create_submission_review()
        self._create_user_and_login('dave', '1234')
        extra = {'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

        view = SubmissionReviewViewSet.as_view({
            'post': 'create',
            'get': 'list',
            'patch': 'partial_update',
            'delete': 'destroy'
        })

        # `dave` user should not be able to create reviews on
        # an xform where he/she has no Admin privileges
        review = {
            'note': "Hey there!",
            'status': SubmissionReview.APPROVED,
            'instance': data['instance']
        }

        request = self.factory.post('/', data=review, **extra)
        response = view(request=request)

        self.assertEqual(403, response.status_code)

        # `dave` user should not be able to update reviews on
        # an xform where he/she has no Admin privileges
        new_data = {
            'note': "Hey there!",
            'status': SubmissionReview.APPROVED
        }

        request = self.factory.patch('/', data=new_data, **extra)
        response = view(request=request, pk=data['id'])

        self.assertEqual(403, response.status_code)

        # `dave` user should not be able to delete reviews on
        # an xform they have no Admin Privileges on
        request = self.factory.delete('/', **extra)
        response = view(request=request, pk=data['id'])

        self.assertEqual(403, response.status_code)

    def test_delete_submission_review(self):
        """
        Test:
            - Soft-Deletes Submission Review
            - Deleted Submission Reviews Do not show up on
              on list
        """
        submission_review_data = self._create_submission_review()

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

        self.assertEqual(204, response.status_code)

        # Doesn't show up on list after deletion
        request = self.factory.get('/', **self.extra)
        response = view(request=request)

        self.assertEqual(200, response.status_code)
        self.assertEqual(0, len(response.data))

    def test_submission_review_instance_filter(self):
        """
        Test can filter Submission Reviews By Instance
        """
        review_one_data = self._create_submission_review()

        review_two_data = {
            'note': "Sup ?",
            'instance': self.xform.instances.all().order_by('pk')[1].id
        }

        view = SubmissionReviewViewSet.as_view({
            'post': 'create',
            'get': 'list'
        })
        request = self.factory.post('/', data=review_two_data, **self.extra)
        response = view(request=request)

        self.assertEqual(201, response.status_code)
        self.assertEqual(2, len(SubmissionReview.objects.all()))

        # Can filter submission review list by instance
        request = self.factory.get(
            '/', {'instance': review_one_data['instance']}, **self.extra)
        response = view(request=request)
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.data))
        self.assertEqual(review_one_data['id'], response.data[0]['id'])

    def test_submission_review_status_filter(self):
        """
        Test can filter Submission Reviews By Status
        """
        review_one_data = self._create_submission_review()

        review_two_data = {
            'note': "Sup ?",
            'instance': review_one_data['instance'],
            'status': SubmissionReview.APPROVED
        }

        view = SubmissionReviewViewSet.as_view({
            'post': 'create',
            'get': 'list'
        })
        request = self.factory.post('/', data=review_two_data, **self.extra)
        response = view(request=request)

        self.assertEqual(201, response.status_code)
        self.assertEqual(2, len(SubmissionReview.objects.all()))

        # Can filter submission review list by instance
        request = self.factory.get('/', {'status': SubmissionReview.PENDING},
                                   **self.extra)
        response = view(request=request)
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.data))
        self.assertEqual(review_one_data['id'], response.data[0]['id'])

    def test_submission_review_created_by_filter(self):
        """
        Test we can filter by created_by
        """
        review_one_data = self._create_submission_review()
        submission_review = SubmissionReview.objects.get(
            id=review_one_data['id'])
        self._create_user_and_login('dave', '1234')
        extra = {'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

        assign_perm(CAN_CHANGE_XFORM, self.user,
                    submission_review.instance.xform)

        review_two_data = {
            'note': "Sup ?",
            'instance': review_one_data['instance'],
            'status': SubmissionReview.APPROVED
        }

        view = SubmissionReviewViewSet.as_view({
            'post': 'create',
            'get': 'list'
        })
        request = self.factory.post('/', data=review_two_data, **extra)
        response = view(request=request)

        self.assertEqual(201, response.status_code)
        review_two_data = response.data
        self.assertEqual(2, len(SubmissionReview.objects.all()))

        # Can filter submission review list by created_by
        request = self.factory.get('/', {'created_by': self.user.id},
                                   **self.extra)
        response = view(request=request)
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.data))
        self.assertEqual(review_two_data['id'], response.data[0]['id'])
