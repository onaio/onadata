# -*- coding: utf-8 -*-
"""
Test XFormSubmissionViewSet module.
"""
import os
from builtins import open  # pylint: disable=redefined-builtin

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.http import UnreadablePostError
from django.test import TransactionTestCase

import mock
import simplejson as json
from django_digest.test import DigestAuth

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.xform_submission_viewset import \
    XFormSubmissionViewSet
from onadata.apps.logger.models import Attachment, Instance
from onadata.libs.permissions import DataEntryRole


# pylint: disable=W0201,R0904,C0103
class TestXFormSubmissionViewSet(TestAbstractViewSet, TransactionTestCase):
    """
    TestXFormSubmissionViewSet test class.
    """
    def setUp(self):
        super(TestXFormSubmissionViewSet, self).setUp()
        self.view = XFormSubmissionViewSet.as_view({
            "head": "create",
            "post": "create"
        })
        self._publish_xls_form_to_project()

    def test_unique_instanceid_per_form_only(self):
        """
        Test unique instanceID submissions per form.
        """
        self._make_submissions()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice = self._create_user_profile(alice_data)
        self.user = alice.user
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}
        self._publish_xls_form_to_project()
        self._make_submissions()

    def test_post_submission_anonymous(self):
        """
        Test anonymous user can make a submission.
        """
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(self.main_directory, 'fixtures',
                            'transportation', 'instances', s, media_file)
        with open(path, 'rb') as f:
            f = InMemoryUploadedFile(f, 'media_file', media_file, 'image/jpg',
                                     os.path.getsize(path), None)
            submission_path = os.path.join(
                self.main_directory, 'fixtures',
                'transportation', 'instances', s, s + '.xml')
            with open(submission_path, 'rb') as sf:
                data = {'xml_submission_file': sf, 'media_file': f}
                request = self.factory.post(
                    '/%s/submission' % self.user.username, data)
                request.user = AnonymousUser()
                response = self.view(request, username=self.user.username)
                self.assertContains(response, 'Successful submission',
                                    status_code=201)
                self.assertTrue(response.has_header('X-OpenRosa-Version'))
                self.assertTrue(
                    response.has_header('X-OpenRosa-Accept-Content-Length'))
                self.assertTrue(response.has_header('Date'))
                self.assertEqual(response['Content-Type'],
                                 'text/xml; charset=utf-8')
                self.assertEqual(response['Location'],
                                 'http://testserver/%s/submission'
                                 % self.user.username)

    def test_post_submission_authenticated(self):
        """
        Test authenticated user can make a submission.
        """
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(self.main_directory, 'fixtures',
                            'transportation', 'instances', s, media_file)
        with open(path, 'rb') as f:
            f = InMemoryUploadedFile(f, 'media_file', media_file, 'image/jpg',
                                     os.path.getsize(path), None)
            submission_path = os.path.join(
                self.main_directory, 'fixtures',
                'transportation', 'instances', s, s + '.xml')
            with open(submission_path, 'rb') as sf:
                data = {'xml_submission_file': sf, 'media_file': f}
                request = self.factory.post('/submission', data)
                response = self.view(request)
                self.assertEqual(response.status_code, 401)
                auth = DigestAuth('bob', 'bobbob')
                request.META.update(auth(request.META, response))
                response = self.view(request, username=self.user.username)
                self.assertContains(response, 'Successful submission',
                                    status_code=201)
                self.assertTrue(response.has_header('X-OpenRosa-Version'))
                self.assertTrue(
                    response.has_header('X-OpenRosa-Accept-Content-Length'))
                self.assertTrue(response.has_header('Date'))
                self.assertEqual(response['Content-Type'],
                                 'text/xml; charset=utf-8')
                self.assertEqual(response['Location'],
                                 'http://testserver/submission')

    def test_post_submission_uuid_other_user_username_not_provided(self):
        """
        Test submission without formhub/uuid done by a different user who has
        no permission to the form fails.
        """
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._create_user_profile(alice_data)
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(self.main_directory, 'fixtures',
                            'transportation', 'instances', s, media_file)
        with open(path, 'rb') as f:
            f = InMemoryUploadedFile(f, 'media_file', media_file, 'image/jpg',
                                     os.path.getsize(path), None)
            path = os.path.join(
                self.main_directory, 'fixtures',
                'transportation', 'instances', s, s + '.xml')
            path = self._add_uuid_to_submission_xml(path, self.xform)

            with open(path, 'rb') as sf:
                data = {'xml_submission_file': sf, 'media_file': f}
                request = self.factory.post('/submission', data)
                response = self.view(request)
                self.assertEqual(response.status_code, 401)
                auth = DigestAuth('alice', 'bobbob')
                request.META.update(auth(request.META, response))
                response = self.view(request)
                self.assertEqual(response.status_code, 403)

    def test_post_submission_authenticated_json(self):
        """
        Test authenticated user can make a JSON submission.
        """
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..',
            'fixtures',
            'transport_submission.json')
        with open(path, encoding='utf-8') as f:
            data = json.loads(f.read())
            request = self.factory.post('/submission', data, format='json')
            response = self.view(request)
            self.assertEqual(response.status_code, 401)

            auth = DigestAuth('bob', 'bobbob')
            request.META.update(auth(request.META, response))
            response = self.view(request)
            self.assertContains(response, 'Successful submission',
                                status_code=201)
            self.assertTrue(response.has_header('X-OpenRosa-Version'))
            self.assertTrue(
                response.has_header('X-OpenRosa-Accept-Content-Length'))
            self.assertTrue(response.has_header('Date'))
            self.assertEqual(response['Content-Type'],
                             'application/json')
            self.assertEqual(response['Location'],
                             'http://testserver/submission')

    def test_post_submission_authenticated_bad_json_list(self):
        """
        Test authenticated user cannot make a badly formatted JSON list
        submision.
        """
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..',
            'fixtures',
            'transport_submission.json')
        with open(path, encoding='utf-8') as f:
            data = json.loads(f.read())
            request = self.factory.post('/submission', [data], format='json')
            response = self.view(request)
            self.assertEqual(response.status_code, 401)

            auth = DigestAuth('bob', 'bobbob')
            request.META.update(auth(request.META, response))
            response = self.view(request)
            self.assertContains(response, 'Invalid data',
                                status_code=400)
            self.assertTrue(response.has_header('X-OpenRosa-Version'))
            self.assertTrue(
                response.has_header('X-OpenRosa-Accept-Content-Length'))
            self.assertTrue(response.has_header('Date'))
            self.assertEqual(response['Content-Type'],
                             'application/json')
            self.assertEqual(response['Location'],
                             'http://testserver/submission')

    def test_post_submission_authenticated_bad_json_submission_list(self):
        """
        Test authenticated user cannot make a badly formatted JSON submission
        list.
        """
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..',
            'fixtures',
            'transport_submission.json')
        with open(path, encoding='utf-8') as f:
            data = json.loads(f.read())
            data['submission'] = [data['submission']]
            request = self.factory.post('/submission', data, format='json')
            response = self.view(request)
            self.assertEqual(response.status_code, 401)

            auth = DigestAuth('bob', 'bobbob')
            request.META.update(auth(request.META, response))
            response = self.view(request)
            self.assertContains(response, 'Incorrect format',
                                status_code=400)
            self.assertTrue(response.has_header('X-OpenRosa-Version'))
            self.assertTrue(
                response.has_header('X-OpenRosa-Accept-Content-Length'))
            self.assertTrue(response.has_header('Date'))
            self.assertEqual(response['Content-Type'],
                             'application/json')
            self.assertEqual(response['Location'],
                             'http://testserver/submission')

    def test_post_submission_authenticated_bad_json(self):
        """
        Test authenticated user cannot make a badly formatted JSON submission.
        """
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..',
            'fixtures',
            'transport_submission_bad.json')
        with open(path, encoding='utf-8') as f:
            data = json.loads(f.read())
            request = self.factory.post('/submission', data, format='json')
            response = self.view(request)
            self.assertEqual(response.status_code, 401)

            request = self.factory.post('/submission', data, format='json')
            auth = DigestAuth('bob', 'bobbob')
            request.META.update(auth(request.META, response))
            response = self.view(request)
            self.assertContains(response, 'Received empty submission',
                                status_code=400)
            self.assertTrue(response.has_header('X-OpenRosa-Version'))
            self.assertTrue(
                response.has_header('X-OpenRosa-Accept-Content-Length'))
            self.assertTrue(response.has_header('Date'))
            self.assertEqual(response['Content-Type'],
                             'application/json')
            self.assertEqual(response['Location'],
                             'http://testserver/submission')

    def test_post_submission_require_auth(self):
        """
        Test require_auth on submission post.
        """
        self.user.profile.require_auth = True
        self.user.profile.save()
        submission = self.surveys[0]
        submission_path = os.path.join(
            self.main_directory, 'fixtures',
            'transportation', 'instances', submission, submission + '.xml')
        with open(submission_path, 'rb') as submission_file:
            data = {'xml_submission_file': submission_file}
            request = self.factory.post('/submission', data)
            response = self.view(request)
            self.assertEqual(response.status_code, 401)
            response = self.view(request, username=self.user.username)
            self.assertEqual(response.status_code, 401)
            auth = DigestAuth('bob', 'bobbob')
            request.META.update(auth(request.META, response))
            response = self.view(request, username=self.user.username)
            self.assertContains(response, 'Successful submission',
                                status_code=201)
            self.assertTrue(response.has_header('X-OpenRosa-Version'))
            self.assertTrue(
                response.has_header('X-OpenRosa-Accept-Content-Length'))
            self.assertTrue(response.has_header('Date'))
            self.assertEqual(response['Content-Type'],
                             'text/xml; charset=utf-8')
            self.assertEqual(response['Location'],
                             'http://testserver/submission')

    def test_post_submission_require_auth_anonymous_user(self):
        """
        Test anonymous user cannot make a submission if the form requires
        authentication.
        """
        self.user.profile.require_auth = True
        self.user.profile.save()
        count = Attachment.objects.count()
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(self.main_directory, 'fixtures',
                            'transportation', 'instances', s, media_file)
        with open(path, 'rb') as f:
            f = InMemoryUploadedFile(f, 'media_file', media_file, 'image/jpg',
                                     os.path.getsize(path), None)
            submission_path = os.path.join(
                self.main_directory, 'fixtures',
                'transportation', 'instances', s, s + '.xml')
            with open(submission_path, 'rb') as sf:
                data = {'xml_submission_file': sf, 'media_file': f}
                request = self.factory.post('/submission', data)
                response = self.view(request)
                self.assertEqual(response.status_code, 401)
                response = self.view(request, username=self.user.username)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(count, Attachment.objects.count())

    def test_post_submission_require_auth_other_user(self):
        """
        Test another authenticated user without permission to the form cannot
        make a submission if the form requires authentication.
        """
        self.user.profile.require_auth = True
        self.user.profile.save()

        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._create_user_profile(alice_data)

        count = Attachment.objects.count()
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(self.main_directory, 'fixtures',
                            'transportation', 'instances', s, media_file)
        with open(path, 'rb') as f:
            f = InMemoryUploadedFile(f, 'media_file', media_file, 'image/jpg',
                                     os.path.getsize(path), None)
            submission_path = os.path.join(
                self.main_directory, 'fixtures',
                'transportation', 'instances', s, s + '.xml')
            with open(submission_path, 'rb') as sf:
                data = {'xml_submission_file': sf, 'media_file': f}
                request = self.factory.post('/submission', data)
                response = self.view(request)
                self.assertEqual(response.status_code, 401)
                response = self.view(request, username=self.user.username)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(count, Attachment.objects.count())
                auth = DigestAuth('alice', 'bobbob')
                request.META.update(auth(request.META, response))
                response = self.view(request, username=self.user.username)
                self.assertContains(
                    response,
                    'alice is not allowed to make submissions to bob',
                    status_code=403)

    def test_post_submission_require_auth_data_entry_role(self):
        """
        Test authenticated user with the DataEntryRole role can make
        submissions to a form with require_auth = True.
        """
        self.user.profile.require_auth = True
        self.user.profile.save()

        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)
        DataEntryRole.add(alice_profile.user, self.xform)

        count = Attachment.objects.count()
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(self.main_directory, 'fixtures',
                            'transportation', 'instances', s, media_file)
        with open(path, 'rb') as f:
            f = InMemoryUploadedFile(f, 'media_file', media_file, 'image/jpg',
                                     os.path.getsize(path), None)
            submission_path = os.path.join(
                self.main_directory, 'fixtures',
                'transportation', 'instances', s, s + '.xml')
            with open(submission_path, 'rb') as sf:
                data = {'xml_submission_file': sf, 'media_file': f}
                request = self.factory.post('/submission', data)
                response = self.view(request)
                self.assertEqual(response.status_code, 401)
                response = self.view(request, username=self.user.username)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(count, Attachment.objects.count())
                auth = DigestAuth('alice', 'bobbob')
                request.META.update(auth(request.META, response))
                response = self.view(request, username=self.user.username)
                self.assertContains(response, 'Successful submission',
                                    status_code=201)

    def test_post_submission_json_without_submission_key(self):
        """
        Tesut JSON submission without the submission key fails.
        """
        data = {"id": "transportation_2011_07_25"}
        request = self.factory.post('/submission', data, format='json')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)

        auth = DigestAuth('bob', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request)
        self.assertContains(response, 'No submission key provided.',
                            status_code=400)

    def test_NaN_in_submission(self):
        """
        Test submissions with uuid as NaN are successful.
        """
        xlsform_path = os.path.join(
            settings.PROJECT_ROOT, 'libs', 'tests', "utils", "fixtures",
            "tutorial.xls")

        self._publish_xls_form_to_project(xlsform_path=xlsform_path)

        path = os.path.join(
            settings.PROJECT_ROOT, 'libs', 'tests', "utils", 'fixtures',
            'tutorial', 'instances', 'uuid_NaN', 'submission.xml')
        self._make_submission(path)

    def test_rapidpro_post_submission(self):
        """
        Test a Rapidpro Webhook POST submission.
        """
        # pylint: disable=C0301
        data = 'run=76250&text=orange&flow_uuid=9da5e439-35af-4ecb-b7fc-2911659f6b04&phone=%2B12065550100&step=3b15df81-a0bd-4de7-8186-145ea3bb6c43&contact_name=Antonate+Maritim&flow_name=fruit&header=Authorization&urn=tel%3A%2B12065550100&flow=1166&relayer=-1&contact=fe4df540-39c1-4647-b4bc-1c93833e22e0&values=%5B%7B%22category%22%3A+%7B%22base%22%3A+%22All+Responses%22%7D%2C+%22node%22%3A+%228037c12f-a277-4255-b630-6a03b035767a%22%2C+%22time%22%3A+%222017-10-04T07%3A18%3A08.171069Z%22%2C+%22text%22%3A+%22orange%22%2C+%22rule_value%22%3A+%22orange%22%2C+%22value%22%3A+%22orange%22%2C+%22label%22%3A+%22fruit_name%22%7D%5D&time=2017-10-04T07%3A18%3A08.205524Z&steps=%5B%7B%22node%22%3A+%220e18202f-9ec4-4756-b15b-e9f152122250%22%2C+%22arrived_on%22%3A+%222017-10-04T07%3A15%3A17.548657Z%22%2C+%22left_on%22%3A+%222017-10-04T07%3A15%3A17.604668Z%22%2C+%22text%22%3A+%22Fruit%3F%22%2C+%22type%22%3A+%22A%22%2C+%22value%22%3A+null%7D%2C+%7B%22node%22%3A+%228037c12f-a277-4255-b630-6a03b035767a%22%2C+%22arrived_on%22%3A+%222017-10-04T07%3A15%3A17.604668Z%22%2C+%22left_on%22%3A+%222017-10-04T07%3A18%3A08.171069Z%22%2C+%22text%22%3A+%22orange%22%2C+%22type%22%3A+%22R%22%2C+%22value%22%3A+%22orange%22%7D%2C+%7B%22node%22%3A+%223b15df81-a0bd-4de7-8186-145ea3bb6c43%22%2C+%22arrived_on%22%3A+%222017-10-04T07%3A18%3A08.171069Z%22%2C+%22left_on%22%3A+null%2C+%22text%22%3A+null%2C+%22type%22%3A+%22A%22%2C+%22value%22%3A+null%7D%5D&flow_base_language=base&channel=-1'  # noqa
        request = self.factory.post(
            '/submission', data,
            content_type='application/x-www-form-urlencoded')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('bob', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request, username=self.user.username,
                             xform_pk=self.xform.pk)
        self.assertContains(response, 'Successful submission', status_code=201)
        self.assertTrue(response.has_header('Date'))
        self.assertEqual(response['Location'], 'http://testserver/submission')

    def test_post_empty_submission(self):
        """
        Test empty submission fails.
        """
        request = self.factory.post(
            '/%s/submission' % self.user.username, {})
        request.user = AnonymousUser()
        response = self.view(request, username=self.user.username)
        self.assertContains(response, 'No XML submission file.',
                            status_code=400)

    def test_auth_submission_head_request(self):
        """
        Test HEAD submission request.
        """
        request = self.factory.head('/submission')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('bob', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request, username=self.user.username)
        self.assertEqual(response.status_code, 204, response.data)
        self.assertTrue(response.has_header('X-OpenRosa-Version'))
        self.assertTrue(
            response.has_header('X-OpenRosa-Accept-Content-Length'))
        self.assertTrue(response.has_header('Date'))
        self.assertEqual(response['Location'], 'http://testserver/submission')

    def test_head_submission_anonymous(self):
        """
        Test HEAD submission request for anonymous user.
        """
        request = self.factory.head('/%s/submission' % self.user.username)
        request.user = AnonymousUser()
        response = self.view(request, username=self.user.username)
        self.assertEqual(response.status_code, 204, response.data)
        self.assertTrue(response.has_header('X-OpenRosa-Version'))
        self.assertTrue(
            response.has_header('X-OpenRosa-Accept-Content-Length'))
        self.assertTrue(response.has_header('Date'))
        self.assertEqual(response['Location'],
                         'http://testserver/%s/submission'
                         % self.user.username)

    def test_floip_format_submission(self):
        """
        Test receiving a row of FLOIP submission.
        """
        # pylint: disable=C0301
        data = '[["2017-05-23T13:35:37.119-04:00", 20394823948, 923842093, "ae54d3", "female", {"option_order": ["male", "female"]}]]'  # noqa
        request = self.factory.post(
            '/submission', data,
            content_type='application/vnd.org.flowinterop.results+json')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('bob', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request, username=self.user.username,
                             xform_pk=self.xform.pk)
        self.assertContains(response, 'Successful submission', status_code=201)
        self.assertTrue(response.has_header('Date'))
        self.assertEqual(response['Location'], 'http://testserver/submission')

    def test_floip_format_submission_missing_column(self):
        """
        Test receiving a row of FLOIP submission.
        """
        # pylint: disable=C0301
        data = '[["2017-05-23T13:35:37.119-04:00", 923842093, "ae54d3", "female", {"option_order": ["male", "female"]}]]'  # noqa
        request = self.factory.post(
            '/submission', data,
            content_type='application/vnd.org.flowinterop.results+json')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('bob', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request, username=self.user.username,
                             xform_pk=self.xform.pk)
        self.assertContains(response, "Wrong number of values (5) in row 0, "
                            "expecting 6 values", status_code=400)

    def test_floip_format_submission_not_list(self):
        """
        Test receiving a row of FLOIP submission.
        """
        # pylint: disable=C0301
        data = '{"option_order": ["male", "female"]}'  # noqa
        request = self.factory.post(
            '/submission', data,
            content_type='application/vnd.org.flowinterop.results+json')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('bob', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request, username=self.user.username,
                             xform_pk=self.xform.pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {u'non_field_errors': [
            u'Invalid format. Expecting a list.']})

    def test_floip_format_submission_is_valid_json(self):
        """
        Test receiving a row of FLOIP submission.
        """
        # pylint: disable=C0301
        data = '"2017-05-23T13:35:37.119-04:00", 923842093, "ae54d3", "female", {"option_order": ["male", "female"]}'  # noqa
        request = self.factory.post(
            '/submission', data,
            content_type='application/vnd.org.flowinterop.results+json')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('bob', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request, username=self.user.username,
                             xform_pk=self.xform.pk)
        self.assertContains(response, "Extra data", status_code=400)

    def test_floip_format_multiple_rows_submission(self):
        """
        Test FLOIP multiple rows submission
        """
        # pylint: disable=C0301
        data = '[["2017-05-23T13:35:37.119-04:00", 20394823948, 923842093, "ae54d3", "female", {"option_order": ["male", "female"]}], ["2017-05-23T13:35:47.822-04:00", 20394823950, 923842093, "ae54d7", "chocolate", null ]]'  # noqa
        request = self.factory.post(
            '/submission', data,
            content_type='application/vnd.org.flowinterop.results+json')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('bob', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request, username=self.user.username,
                             xform_pk=self.xform.pk)
        self.assertContains(response, 'Successful submission', status_code=201)
        self.assertTrue(response.has_header('Date'))
        self.assertEqual(response['Location'], 'http://testserver/submission')

    def test_floip_format_multiple_rows_instance(self):
        """
        Test data responses exist in instance values.
        """
        # pylint: disable=C0301
        data = '[["2017-05-23T13:35:37.119-04:00", 20394823948, 923842093, "ae54d3", "female", {"option_order": ["male", "female"]}], ["2017-05-23T13:35:47.822-04:00", 20394823950, 923842093, "ae54d7", "chocolate", null ]]'  # noqa
        request = self.factory.post(
            '/submission', data,
            content_type='application/vnd.org.flowinterop.results+json')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('bob', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request, username=self.user.username,
                             xform_pk=self.xform.pk)
        instance_json = Instance.objects.last().json
        data_responses = [i[4] for i in json.loads(data)]
        self.assertTrue(any(i in data_responses
                            for i in instance_json.values()))

    @mock.patch('onadata.apps.api.viewsets.xform_submission_viewset.SubmissionSerializer')  # noqa
    def test_post_submission_unreadable_post_error(self, MockSerializer):
        """
        Test UnreadablePostError exception during submission..
        """
        MockSerializer.side_effect = UnreadablePostError()
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(self.main_directory, 'fixtures',
                            'transportation', 'instances', s, media_file)
        with open(path, 'rb') as f:
            f = InMemoryUploadedFile(f, 'media_file', media_file, 'image/jpg',
                                     os.path.getsize(path), None)
            submission_path = os.path.join(
                self.main_directory, 'fixtures',
                'transportation', 'instances', s, s + '.xml')
            with open(submission_path, 'rb') as sf:
                data = {'xml_submission_file': sf, 'media_file': f}
                request = self.factory.post(
                    '/%s/submission' % self.user.username, data)
                request.user = AnonymousUser()
                response = self.view(request, username=self.user.username)
                self.assertContains(response, 'Unable to read submitted file',
                                    status_code=400)
                self.assertTrue(response.has_header('X-OpenRosa-Version'))
