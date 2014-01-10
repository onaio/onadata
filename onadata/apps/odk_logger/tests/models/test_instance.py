from mock import patch

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.odk_logger.models import XForm, Instance
from onadata.libs.utils.common_tags import SUBMISSION_TIME, XFORM_ID_STRING


class TestInstance(TestBase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._publish_transportation_form_and_submit_instance()

    def test_stores_json(self):
        instances = Instance.objects.all()

        for instance in instances:
            self.assertNotEqual(instance.json, {})

    @patch('onadata.apps.odk_logger.models.instance.submission_time')
    def test_json_assigns_attributes(self, mock_time):
        self._set_mock_time(mock_time)

        xform_id_string = XForm.objects.all()[0].id_string
        instances = Instance.objects.all()

        for instance in instances:
            self.assertEqual(instance.json[SUBMISSION_TIME],
                             mock_time.return_value)
            self.assertEqual(instance.json[XFORM_ID_STRING],
                             xform_id_string)
