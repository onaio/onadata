import os
from django.core.urlresolvers import reverse
from odk_logger.models import Instance
from odk_viewer.views import kml_export
from main.tests.test_base import MainTestCase


class TestKMLExport(MainTestCase):
    def _publish_survey(self):
        self.this_directory = os.path.dirname(__file__)
        xls_path = self._fixture_path("gps", "gps.xls")
        MainTestCase._publish_xls_file(self, xls_path)

    def _make_submissions(self):
        surveys = ['gps_1980-01-23_20-52-08',
                   'gps_1980-01-23_21-21-33', ]
        for survey in surveys:
            path = self._fixture_path('gps', 'instances', survey + '.xml')
            self._make_submission(path)

    def test_kml_export(self):
        self._publish_survey()
        self._make_submissions()
        self.fixtures = os.path.join(
            self.this_directory, 'fixtures', 'kml_export')
        url = reverse(
            kml_export,
            kwargs={'username': self.user.username, 'id_string': 'gps'})
        response = self.client.get(url)
        instances = Instance.objects.filter(
            xform__id_string='gps').order_by('id')

        self.assertEqual(instances.count(), 2)

        first, second = [str(i.pk) for i in instances]

        with open(os.path.join(self.fixtures, 'export.kml')) as f:
            expected_content = f.read()
            expected_content = expected_content.replace('{{first}}', first)
            expected_content = expected_content.replace('{{second}}', second)

            self.assertMultiLineEqual(
                response.content, expected_content.strip())
