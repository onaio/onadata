import os
import unittest

from onadata.libs.utils.qrcode import generate_qrcode

url = "https://hmh2a.enketo.formhub.org"


class TestGenerateQrCode(unittest.TestCase):
    def test_generate_qrcode(self):
        path = os.path.join(os.path.dirname(__file__), "fixtures",
                            "qrcode.txt")
        with open(path) as f:
            qrcode = f.read()
            self.assertEqual(generate_qrcode(url), qrcode.strip())
