from mock import patch

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.odk_logger.models import Instance
from onadata.libs.utils.common_tags import SUBMISSION_TIME


class TestInstance(TestBase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._publish_transportation_form_and_submit_instance()

    def test_stores_json(self):
        instances = Instance.objects.all()

        for instance in instances:
            self.assertNotEqual(instance.json, {})

    @patch('onadata.apps.odk_logger.models.instance.submission_time')
    def test_get_dict_assigns_submission_time(self, mock_time):
        self._set_mock_time(mock_time)

        instances = Instance.objects.all()

        for instance in instances:
            self.assertEqual(instance.get_dict()[SUBMISSION_TIME],
                             mock_time.return_value)
