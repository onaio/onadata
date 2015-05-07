import os
import requests

from django.core.urlresolvers import reverse

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models.instance import Instance
from onadata.apps.logger.views import edit_data
from onadata.apps.logger.xform_instance_parser import get_uuid_from_xml
from onadata.libs.utils.logger_tools import inject_instanceid

from httmock import urlmatch, HTTMock


@urlmatch(netloc=r'(.*\.)?enketo\.ona\.io$')
def enketo_edit_mock(url, request):
    response = requests.Response()
    response.status_code = 201
    response._content = '{"edit_url": "https://hmh2a.enketo.ona.io"}'
    return response


class TestWebforms(TestBase):
    def setUp(self):
        super(TestWebforms, self).setUp()
        self._publish_transportation_form_and_submit_instance()

    def __load_fixture(self, *path):
        with open(os.path.join(os.path.dirname(__file__), *path), 'r') as f:
            return f.read()

    def test_edit_url(self):
        instance = Instance.objects.order_by('id').reverse()[0]
        edit_url = reverse(edit_data, kwargs={
            'username': self.user.username,
            'id_string': self.xform.id_string,
            'data_id': instance.id
        })
        with HTTMock(enketo_edit_mock):
            response = self.client.get(edit_url)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response['location'],
                             'https://hmh2a.enketo.ona.io')

    def test_inject_instanceid(self):
        """
        Test that 1 and only 1 instance id exists or is injected
        """
        instance = Instance.objects.all().reverse()[0]
        xml_str = self.__load_fixture("..", "fixtures", "tutorial",
                                      "instances",
                                      "tutorial_2012-06-27_11-27-53.xml")
        # test that we dont have an instance id
        uuid = get_uuid_from_xml(xml_str)
        self.assertIsNone(uuid)
        injected_xml_str = inject_instanceid(xml_str, instance.uuid)
        # check that xml has the instanceid tag
        uuid = get_uuid_from_xml(injected_xml_str)
        self.assertEqual(uuid, instance.uuid)

    def test_dont_inject_instanceid_if_exists(self):
        xls_file_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'fixtures',
            'tutorial',
            'tutorial.xls')
        self._publish_xls_file_and_set_xform(xls_file_path)
        xml_file_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'fixtures',
            'tutorial',
            'instances',
            'tutorial_2012-06-27_11-27-53_w_uuid.xml')
        self._make_submission(xml_file_path)
        instance = Instance.objects.order_by('id').reverse()[0]
        injected_xml_str = inject_instanceid(instance.xml, instance.uuid)
        # check that the xml is unmodified
        self.assertEqual(instance.xml, injected_xml_str)
