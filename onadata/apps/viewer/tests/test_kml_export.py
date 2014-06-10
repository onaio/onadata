import os

from django.core.urlresolvers import reverse

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models.instance import Instance
from onadata.apps.viewer.views import kml_export


class TestKMLExport(TestBase):
    def _publish_survey(self):
        self.this_directory = os.path.dirname(__file__)
        xls_path = self._fixture_path("gps", "gps.xls")
        TestBase._publish_xls_file(self, xls_path)

    def test_kml_export(self):
        id_string = 'gps'

        self._publish_survey()
        self._make_submissions_gps()
        self.fixtures = os.path.join(
            self.this_directory, 'fixtures', 'kml_export')
        url = reverse(
            kml_export,
            kwargs={'username': self.user.username, 'id_string': id_string})
        response = self.client.get(url)
        instances = Instance.objects.filter(
            xform__user=self.user, xform__id_string=id_string,
            geom__isnull=False
        ).order_by('id')

        self.assertEqual(instances.count(), 2)

        first, second = [str(i.pk) for i in instances]

        with open(os.path.join(self.fixtures, 'export.kml')) as f:
            expected_content = f.read()
            expected_content = expected_content.replace('{{first}}', first)
            expected_content = expected_content.replace('{{second}}', second)

            self.assertMultiLineEqual(
                expected_content.strip(), response.content.strip())
