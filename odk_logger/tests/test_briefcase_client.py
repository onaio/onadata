from main.tests.test_base import MainTestCase


class TestBriefcaseAPI(MainTestCase):

    def setUp(self):
        super(MainTestCase, self).setUp()

    def test_download_xform_xml(self):
        """
        Download xform via briefcase api
        """
        # check that [user]/briefcase/forms folder is created for user deno
        # check that [user]/briefcase/forms/[id_string].xml is created
        pass

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
