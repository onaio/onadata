import unittest

from rest_framework.test import APIRequestFactory
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.qrcode import (
    generate_qrcode, generate_odk_qrcode)


class TestGenerateQrCode(TestBase, unittest.TestCase):
    def setUp(self):
        self.user = self._create_user('bob', 'bob', create_profile=True)

    def test_generate_qrcode(self):
        url = "https://hmh2a.enketo.formhub.org"
        self.assertTrue(
            generate_qrcode(url).find("data:image/png;base64,") > -1
        )

    def test_generate_qrcode_json(self):
        request = APIRequestFactory().get('/')
        request.user = self.user
        self.assertTrue(
            generate_odk_qrcode(
                request, None).find("data:image/png;base64,") > -1
        )
