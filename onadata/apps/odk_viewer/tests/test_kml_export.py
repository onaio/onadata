import os

from django.core.urlresolvers import reverse

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.odk_viewer.models.parsed_instance import ParsedInstance
from onadata.apps.odk_viewer.views import kml_export


class TestKMLExport(TestBase):
    def _publish_survey(self):
        self.this_directory = os.path.dirname(__file__)
        xls_path = self._fixture_path("gps", "gps.xls")
        TestBase._publish_xls_file(self, xls_path)

    def _make_submissions(self):
        surveys = ['gps_1980-01-23_20-52-08',
                   'gps_1980-01-23_21-21-33', ]
        for survey in surveys:
            path = self._fixture_path('gps', 'instances', survey + '.xml')
            self._make_submission(path)

    def test_kml_export(self):
        id_string = 'gps'

        self._publish_survey()
        self._make_submissions()
        self.fixtures = os.path.join(
            self.this_directory, 'fixtures', 'kml_export')
        url = reverse(
            kml_export,
            kwargs={'username': self.user.username, 'id_string': id_string})
        response = self.client.get(url)
        pis = ParsedInstance.objects.filter(
            instance__user=self.user, instance__xform__id_string=id_string,
            lat__isnull=False, lng__isnull=False).order_by('id')

        self.assertEqual(pis.count(), 2)

        first, second = [str(i.pk) for i in pis]

        with open(os.path.join(self.fixtures, 'export.kml')) as f:
            expected_content = f.read()
            expected_content = expected_content.replace('{{first}}', first)
            expected_content = expected_content.replace('{{second}}', second)

            self.assertMultiLineEqual(
                expected_content.strip(), response.content.strip())
