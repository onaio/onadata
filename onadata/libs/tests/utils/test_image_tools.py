import requests
from httmock import urlmatch, HTTMock

from onadata.libs.utils.image_tools import resize
from onadata.apps.main.tests.test_base import TestBase


@urlmatch(netloc=r'(.*\.)?localhost:8000$', path='/media/test.jpg')
def image_url_mock(url, request):
    response = requests.Response()
    response.status_code = 200
    response._content = "test.jpg"
    return response


class TestImageTools(TestBase):
    def test_resize_exception_is_handled(self):
        with HTTMock(image_url_mock):
            with self.assertRaises(Exception) as io_error:
                resize('test.jpg')

        self.assertEqual(io_error.exception.message,
                         u'The image file couldn\'t be identified')
