import os
import shutil

import requests
from django.core.files.storage import get_storage_class
from httmock import urlmatch, HTTMock

from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.image_tools import resize

storage = get_storage_class()()


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
                resize('test.jpg', 'jpg')

        self.assertEqual(str(io_error.exception),
                         u'The image file couldn\'t be identified')

    def test_resize(self):
        self._publish_transportation_form()
        self._submit_transport_instance_w_attachment()
        attachment = Attachment.objects.first()
        media_filename = attachment.media_file.name
        resize(media_filename, attachment.extension)
        # small
        path = os.path.join(
            storage.path(''), media_filename[0:-4] + '-small.jpg')
        assert os.path.exists(path)
        # medium
        path = os.path.join(
            storage.path(''), media_filename[0:-4] + '-medium.jpg')
        assert os.path.exists(path)
        # large
        path = os.path.join(
            storage.path(''), media_filename[0:-4] + '-large.jpg')
        assert os.path.exists(path)

    def tearDown(self):
        if self.user:
            if storage.exists(self.user.username):
                shutil.rmtree(storage.path(self.user.username))
