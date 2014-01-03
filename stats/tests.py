import os

from django.test import TestCase
from mock import patch

from main.tests.test_base import MainTestCase
from odk_logger.models import XForm

from stats.models import StatsCount
from stats.tasks import stat_log
from stats.utils import get_form_submissions_per_day


class StatsTest(TestCase):

    def setUp(self):
        pass

    def test_statscount(self):
        StatsCount.objects.create(key="*", value=1)
        self.assertEqual(
            StatsCount.stats.count(key="*"), 1)

    def test_task_stat_log(self):
        result = stat_log.delay("*", 1)
        self.assertEqual(
            (result.get().key, result.get().value), (u"*", 1))
        self.assertTrue(result.successful())


class TestUtils(MainTestCase):
    def setUp(self):
        self._create_user_and_login()

    def _publish_xls_file(self):
        xls_path = os.path.join(self.this_directory, "fixtures",
                                "transportation", "transportation.xls")
        response = super(TestUtils, self)._publish_xls_file(xls_path)
        self.assertEqual(response.status_code, 200)
        self.xform = XForm.objects.latest('date_created')
        self.assertEqual(self.xform.id_string, "transportation_2011_07_25")

    @patch('odk_logger.models.instance.submission_time')
    def test_form_submission_count_by_day(self, mock_time):
        self._set_mock_time(mock_time)
        self._publish_xls_file()
        self._make_submissions()
        data = get_form_submissions_per_day(self.xform)
        self.assertTrue(len(data) > 0)
        self.assertEqual(data[0]['count'], 4)
