# -*- coding=utf-8 -*-
"""
Test encrypted form submissions.
"""
import os
from builtins import open

from django.core.urlresolvers import reverse
from django.contrib.auth import authenticate

from rest_framework.test import APIRequestFactory

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import Attachment
from onadata.apps.logger.models import Instance
from onadata.apps.logger.models import XForm
from onadata.apps.logger.views import submission


class TestEncryptedForms(TestBase):
    """
    TestEncryptedForms test class.
    """

    def setUp(self):
        super(TestEncryptedForms, self).setUp()
        self._create_user_and_login()
        self._submission_url = reverse(
            'submissions', kwargs={'username': self.user.username})

    def test_encrypted_submissions(self):
        """
        Test encrypted submissions.
        """
        self._publish_xls_file(os.path.join(
            self.this_directory, 'fixtures', 'transportation',
            'transportation_encrypted.xls'
        ))
        xform = XForm.objects.get(id_string='transportation_encrypted')
        self.assertTrue(xform.encrypted)
        uuid = "c15252fe-b6f3-4853-8f04-bf89dc73985a"
        with self.assertRaises(Instance.DoesNotExist):
            Instance.objects.get(uuid=uuid)
        message = u"Successful submission."
        files = {}
        for filename in ['submission.xml', 'submission.xml.enc']:
            files[filename] = os.path.join(
                self.this_directory, 'fixtures', 'transportation',
                'instances_encrypted', filename)
        count = Instance.objects.count()
        acount = Attachment.objects.count()
        with open(files['submission.xml.enc'], 'rb') as encryped_file:
            with open(files['submission.xml'], 'rb') as f:
                post_data = {
                    'xml_submission_file': f,
                    'submission.xml.enc': encryped_file}
                self.factory = APIRequestFactory()
                request = self.factory.post(self._submission_url, post_data)
                request.user = authenticate(username='bob',
                                            password='bob')
                response = submission(request, username=self.user.username)
                self.assertContains(response, message, status_code=201)
                self.assertEqual(Instance.objects.count(), count + 1)
                self.assertEqual(Attachment.objects.count(), acount + 1)
                instance = Instance.objects.get(uuid=uuid)
                self.assertTrue(instance is not None)
                self.assertEqual(instance.total_media, 1)
                self.assertEqual(instance.media_count, 1)
                self.assertTrue(instance.media_all_received)

    def test_encrypted_multiple_files(self):
        """
        Test missing encrytped files has all_media_received=False.
        """
        self._create_user_and_login()
        # publish our form which contains some some repeats
        xls_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial_encrypted/tutorial_encrypted.xls"
        )
        count = XForm.objects.count()
        self._publish_xls_file_and_set_xform(xls_file_path)
        self.assertEqual(count + 1, XForm.objects.count())

        # submit an instance
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial_encrypted/instances/tutorial_encrypted.xml"
        )
        encrypted_xml_submission = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial_encrypted/instances/submission.xml.enc"
        )
        self._make_submission_w_attachment(xml_submission_file_path,
                                           encrypted_xml_submission)
        self.assertNotContains(self.response,
                               "Multiple nodes with the same name",
                               status_code=201)

        # load xml file to parse and compare
        # expected_list = [{u'file': u'1483528430996.jpg.enc'},
        #                  {u'file': u'1483528445767.jpg.enc'}]

        instance = Instance.objects.filter().order_by('id').last()
        self.assertEqual(instance.total_media, 3)
        self.assertEqual(instance.media_count, 1)
        self.assertFalse(instance.media_all_received)

        media_file_1 = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial_encrypted/instances/1483528430996.jpg.enc"
        )
        self._make_submission_w_attachment(xml_submission_file_path,
                                           media_file_1)
        self.assertNotContains(self.response,
                               "Multiple nodes with the same name",
                               status_code=202)
        instance.refresh_from_db()
        self.assertEqual(instance.total_media, 3)
        self.assertEqual(instance.media_count, 2)
        self.assertFalse(instance.media_all_received)

        media_file_2 = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial_encrypted/instances/1483528445767.jpg.enc"
        )
        self._make_submission_w_attachment(xml_submission_file_path,
                                           media_file_2)
        self.assertNotContains(self.response,
                               "Multiple nodes with the same name",
                               status_code=202)
        instance.refresh_from_db()
        self.assertEqual(instance.total_media, 3)
        self.assertEqual(instance.media_count, 3)
        self.assertTrue(instance.media_all_received)
