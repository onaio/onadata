import unittest

from onadata.libs.utils.qrcode import generate_qrcode


class TestGenerateQrCode(unittest.TestCase):
    def test_generate_qrcode(self):
        url = "https://hmh2a.enketo.formhub.org"
        self.assertTrue(
            generate_qrcode(url).find("data:image/png;base64,") > -1
        )
