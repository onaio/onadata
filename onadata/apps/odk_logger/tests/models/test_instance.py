from datetime import datetime
from mock import patch

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.odk_logger.models import XForm, Instance
from onadata.libs.utils.common_tags import MONGO_STRFTIME, SUBMISSION_TIME,\
    XFORM_ID_STRING


class TestInstance(TestBase):

    def setUp(self):
        super(self.__class__, self).setUp()

    def test_stores_json(self):
        self._publish_transportation_form_and_submit_instance()
        instances = Instance.objects.all()

        for instance in instances:
            self.assertNotEqual(instance.json, {})

    @patch('django.utils.timezone.now')
    def test_json_assigns_attributes(self, mock_time):
        mock_time.return_value = datetime.now()
        self._publish_transportation_form_and_submit_instance()

        xform_id_string = XForm.objects.all()[0].id_string
        instances = Instance.objects.all()

        for instance in instances:
            self.assertEqual(instance.json[SUBMISSION_TIME],
                             mock_time.return_value.strftime(MONGO_STRFTIME))
            self.assertEqual(instance.json[XFORM_ID_STRING],
                             xform_id_string)

    def test_json_time_match_submission_time(self):
        self._publish_transportation_form_and_submit_instance()
        instances = Instance.objects.all()

        for instance in instances:
            self.assertEqual(instance.json[SUBMISSION_TIME],
                             instance.date_created.strftime(MONGO_STRFTIME))
