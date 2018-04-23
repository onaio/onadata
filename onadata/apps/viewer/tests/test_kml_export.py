import os
from future.utils import iteritems

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

        # create a tuple of replacement data per instance
        replacement_data = [["{:,}".format(x) for x in [
            i.pk, i.point.x, i.point.y]] for i in instances]
        # assuming 2 instances, flatten and assign to template names
        replacement_dict = dict(zip(['pk1', 'x1', 'y1', 'pk2', 'x2', 'y2'],
                                [i for s in replacement_data for i in s]))

        with open(os.path.join(self.fixtures, 'export.kml')) as f:
            expected_content = f.read()
            for (template_name, template_data) in iteritems(replacement_dict):
                expected_content = expected_content.replace(
                    '{{%s}}' % template_name, template_data)

            self.assertMultiLineEqual(
                expected_content.strip(),
                response.content.decode('utf-8').strip())
