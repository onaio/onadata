# -*- coding: utf-8 -*-
"""
Test onadata.libs.utils.analytics module.
"""
import os
from unittest.mock import MagicMock

from django.contrib.auth.models import User, AnonymousUser
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.conf import settings
from django.test import override_settings

import onadata.libs.utils.analytics
from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.xform_submission_viewset import \
    XFormSubmissionViewSet
from onadata.libs.utils.analytics import get_user_id


class TestAnalytics(TestAbstractViewSet):
    def test_get_user_id(self):
        """Test get_user_id()"""
        self.assertEqual(get_user_id(None), 'anonymous')

        # user1 has no email set
        user1 = User(username='abc')
        self.assertEqual(get_user_id(user1), user1.username)

        # test returns user2 username even when has email set
        user2 = User(username='abc', email='abc@example.com')
        self.assertTrue(len(user2.email) > 0)
        self.assertEqual(get_user_id(user2), user2.username)

    @override_settings(SEGMENT_WRITE_KEY='123')
    def test_track(self):
        """Test analytics.track() function.
        """
        segment_mock = MagicMock()
        onadata.libs.utils.analytics.segment_analytics = segment_mock
        onadata.libs.utils.analytics.init_analytics()
        self.assertEqual(segment_mock.write_key, '123')

        user1 = User(username='abc')
        onadata.libs.utils.analytics.track(user1, 'testing track function')
        segment_mock.track.assert_called_with(
            user1.username,
            'testing track function',
            {'value': 1},
            {'page': {}, 'campaign': {}, 'active': True})

    @override_settings(
            SEGMENT_WRITE_KEY='123')
    def test_submission_tracking(self):
        """Test that submissions are tracked"""
        segment_mock = MagicMock()
        onadata.libs.utils.analytics.segment_analytics = segment_mock
        onadata.libs.utils.analytics.init_analytics()
        self.assertEqual(segment_mock.write_key, '123')

        # Test out that the TrackObjectEvent decorator
        # Tracks created submissions, XForms and Projects
        view = XFormSubmissionViewSet.as_view({
            'post': 'create',
            'head': 'create'
        })
        self._publish_xls_form_to_project()
        segment_mock.track.assert_called_with(
            self.xform.user.username,
            'XForm created',
            {
                'created_by': self.xform.user,
                'xform_id': self.xform.pk,
                'xform_name': self.xform.title,
                'from': 'Publish XLS Form',
                'value': 1
            },
            {
                'page': {},
                'campaign': {},
                'active': True
            })
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(self.main_directory, 'fixtures',
                            'transportation', 'instances', s, media_file)
        request_path = f"/{self.user.username}/submission"
        with open(path, 'rb') as f:
            f = InMemoryUploadedFile(f, 'media_file', media_file, 'image/jpg',
                                     os.path.getsize(path), None)
            submission_path = os.path.join(
                self.main_directory, 'fixtures',
                'transportation', 'instances', s, s + '.xml')
            with open(submission_path, 'rb') as sf:
                data = {'xml_submission_file': sf, 'media_file': f}
                request = self.factory.post(request_path, data)
                request.user = AnonymousUser()
                request.META['HTTP_DATE'] = '2020-09-10T11:56:32.424726+00:00'
                request.META['HTTP_REFERER'] = settings.HOSTNAME +\
                    ':8000'
                request.META['HTTP_USER_AGENT'] =\
                    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit'\
                    '/537.36 (KHTML, like Gecko) Chrome'\
                    '/83.0.4103.61 Safari/537.36'
                response = view(request, username=self.user.username)
                self.assertContains(response, 'Successful submission',
                                    status_code=201)
                self.assertTrue(response.has_header('X-OpenRosa-Version'))
                self.assertTrue(
                    response.has_header('X-OpenRosa-Accept-Content-Length'))
                self.assertTrue(response.has_header('Date'))
                self.assertEqual(response['Content-Type'],
                                 'text/xml; charset=utf-8')
                self.assertEqual(response['Location'],
                                 'http://testserver' + request_path)
        form_id = self.xform.pk
        username = self.user.username
        segment_mock.track.assert_called_with(
            username,
            'Submission created',
            {
                'xform_id': self.xform.pk,
                'project_id': self.xform.project.pk,
                'organization': 'Bob Inc.',
                'from': 'Submission collected from Enketo',
                'label': f'form-{form_id}-owned-by-{username}',
                'value': 1,
                'event_by': 'anonymous'
            },
            {'page': {
                'path': '/bob/submission',
                'referrer': settings.HOSTNAME + ':8000',
                'url': 'http://testserver/bob/submission'
                },
                'campaign': {
                    'source': settings.HOSTNAME},
                'active': True,
                'ip': '127.0.0.1',
                'userId': self.xform.user.pk,
                'receivedAt': '2020-09-10T11:56:32.424726+00:00',
                'userAgent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit'
                '/537.36 (KHTML, like Gecko) Chrome'
                '/83.0.4103.61 Safari/537.36'}
            )

    @override_settings(
            SEGMENT_WRITE_KEY='123')
    # pylint: disable=invalid-name
    def test_submission_tracking_postman_user_agent(self):
        """
        Test that submissions are tracked for submissions made
        via an agent thats not a browser nor ODK collect
        """
        segment_mock = MagicMock()
        onadata.libs.utils.analytics.segment_analytics = segment_mock
        onadata.libs.utils.analytics.init_analytics()
        self.assertEqual(segment_mock.write_key, '123')

        # Test out that the TrackObjectEvent decorator
        # Tracks created submissions, XForms and Projects
        view = XFormSubmissionViewSet.as_view({
            'post': 'create',
            'head': 'create'
        })
        self._publish_xls_form_to_project()
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(self.main_directory, 'fixtures',
                            'transportation', 'instances', s, media_file)
        request_path = f"/{self.user.username}/submission"
        with open(path, 'rb') as f:
            f = InMemoryUploadedFile(f, 'media_file', media_file, 'image/jpg',
                                     os.path.getsize(path), None)
            submission_path = os.path.join(
                self.main_directory, 'fixtures',
                'transportation', 'instances', s, s + '.xml')
            with open(submission_path, 'rb') as sf:
                data = {'xml_submission_file': sf, 'media_file': f}
                request = self.factory.post(request_path, data)
                request.user = AnonymousUser()
                request.META['HTTP_DATE'] = '2020-09-10T11:56:32.424726+00:00'
                request.META['HTTP_REFERER'] = settings.HOSTNAME +\
                    ':8000'
                # set user agent to postman
                request.META['HTTP_USER_AGENT'] = 'PostmanRuntime/7.30.0'
                response = view(request, username=self.user.username)
                self.assertContains(response, 'Successful submission',
                                    status_code=201)
                self.assertTrue(response.has_header('X-OpenRosa-Version'))
                self.assertTrue(
                    response.has_header('X-OpenRosa-Accept-Content-Length'))
                self.assertTrue(response.has_header('Date'))
                self.assertEqual(response['Content-Type'],
                                 'text/xml; charset=utf-8')
                self.assertEqual(response['Location'],
                                 'http://testserver' + request_path)
        form_id = self.xform.pk
        username = self.user.username
        segment_mock.track.assert_called_with(
            username,
            'Submission created',
            {
                'xform_id': self.xform.pk,
                'project_id': self.xform.project.pk,
                'organization': 'Bob Inc.',
                'from': 'Submission collected from Web',
                'label': f'form-{form_id}-owned-by-{username}',
                'value': 1,
                'event_by': 'anonymous'
            },
            {'page': {
                'path': '/bob/submission',
                'referrer': settings.HOSTNAME + ':8000',
                'url': 'http://testserver/bob/submission'
                },
                'campaign': {
                    'source': settings.HOSTNAME},
                'active': True,
                'ip': '127.0.0.1',
                'userId': self.xform.user.pk,
                'receivedAt': '2020-09-10T11:56:32.424726+00:00',
                'userAgent': 'PostmanRuntime/7.30.0'}
            )
