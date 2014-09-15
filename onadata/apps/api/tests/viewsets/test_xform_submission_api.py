import os

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.test import TransactionTestCase
from django_digest.test import DigestAuth

from onadata.apps.api.tests.viewsets.test_abstract_viewset import\
    TestAbstractViewSet
from onadata.apps.api.viewsets.xform_submission_api import XFormSubmissionApi
from onadata.apps.logger.models import Attachment


class TestXFormSubmissionApi(TestAbstractViewSet, TransactionTestCase):
    def setUp(self):
        super(self.__class__, self).setUp()
        self.view = XFormSubmissionApi.as_view({
            "get": "list",
            "post": "create"
        })
        self._publish_xls_form_to_project()

    def test_post_submission_username_required(self):
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(self.main_directory, 'fixtures',
                            'transportation', 'instances', s, media_file)
        with open(path) as f:
            submission_path = os.path.join(
                self.main_directory, 'fixtures',
                'transportation', 'instances', s, s + '.xml')
            with open(submission_path) as sf:
                data = {'xml_submission_file': sf, 'media_file': f}
                request = self.factory.post('/submission', data)
                response = self.view(request)
                self.assertEqual(response.status_code, 401)
                auth = DigestAuth('bob', 'bobbob')
                request.META.update(auth(request.META, response))
                response = self.view(request)
                self.assertContains(response, 'Username or ID required',
                                    status_code=400)
                self.assertTrue(response.has_header('X-OpenRosa-Version'))
                self.assertTrue(
                    response.has_header('X-OpenRosa-Accept-Content-Length'))
                self.assertTrue(response.has_header('Date'))
                self.assertEqual(response['Content-Type'],
                                 'text/xml; charset=utf-8')

    def test_post_submission_anonymous(self):
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(self.main_directory, 'fixtures',
                            'transportation', 'instances', s, media_file)
        with open(path) as f:
            f = InMemoryUploadedFile(f, 'media_file', media_file, 'image/jpg',
                                     os.path.getsize(path), None)
            submission_path = os.path.join(
                self.main_directory, 'fixtures',
                'transportation', 'instances', s, s + '.xml')
            with open(submission_path) as sf:
                data = {'xml_submission_file': sf, 'media_file': f}
                request = self.factory.post('/submission', data)
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

    def test_post_submission_authenticated(self):
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(self.main_directory, 'fixtures',
                            'transportation', 'instances', s, media_file)
        with open(path) as f:
            f = InMemoryUploadedFile(f, 'media_file', media_file, 'image/jpg',
                                     os.path.getsize(path), None)
            submission_path = os.path.join(
                self.main_directory, 'fixtures',
                'transportation', 'instances', s, s + '.xml')
            with open(submission_path) as sf:
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

    def test_post_submission_require_auth(self):
        self.user.profile.require_auth = True
        self.user.profile.save()
        count = Attachment.objects.count()
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(self.main_directory, 'fixtures',
                            'transportation', 'instances', s, media_file)
        with open(path) as f:
            f = InMemoryUploadedFile(f, 'media_file', media_file, 'image/jpg',
                                     os.path.getsize(path), None)
            submission_path = os.path.join(
                self.main_directory, 'fixtures',
                'transportation', 'instances', s, s + '.xml')
            with open(submission_path) as sf:
                data = {'xml_submission_file': sf, 'media_file': f}
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
                self.assertEqual(count + 1, Attachment.objects.count())
                self.assertTrue(response.has_header('X-OpenRosa-Version'))
                self.assertTrue(
                    response.has_header('X-OpenRosa-Accept-Content-Length'))
                self.assertTrue(response.has_header('Date'))
                self.assertEqual(response['Content-Type'],
                                 'text/xml; charset=utf-8')
                self.assertEqual(response['Location'],
                                 'http://testserver/submission')
