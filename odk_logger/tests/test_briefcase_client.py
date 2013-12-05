import os.path
from django.core.files.storage import get_storage_class
from main.tests.test_base import MainTestCase

from utils.briefcase_client import BriefcaseClient


class TestBriefcaseAPI(MainTestCase):

    def setUp(self):
        super(MainTestCase, self).setUp()
        self._publish_transportation_form()
        self._submit_transport_instance_w_attachment()
        self._logout()
        self._create_user_and_login('deno', 'deno')
        self.bc = BriefcaseClient(
            username='bob', password='bob', url=self.base_url, user=self.user)

    def test_download_xform_xml(self):
        """
        Download xform via briefcase api
        """
        # check that [user]/briefcase/forms folder is created for user deno
        # check that [user]/briefcase/forms/[id_string].xml is created
        self.bc.download_forms()
        storage = get_storage_class()()
        forms_folder_path = os.path.join('deno', 'briefcase', 'forms')
        self.assertTrue(storage.exists(forms_folder_path))
        forms_path = os.path.join(forms_folder_path, 'tutorial.xml')
        self.assertTrue(storage.exists(forms_path))

    def test_download_form_media(self):
        """
        Download media via briefcase api
        """
        # check that [user]/briefcase/forms/[id_string]-media is created
        # check that media file is save in [id_string]-media
        pass

    def test_download_instance(self):
        """
        Download instance xml
        """
        # check that [user]/briefcase/forms/instances is created
        # check that instances/[uuid]/submission.xml is created
        pass

    def test_download_instance_with_attachment(self):
        """
        Download instance xmli and attachments
        """
        # check that instances/[uuid]/[media_file.ext] is created
        pass
