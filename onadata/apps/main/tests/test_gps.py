import os

from onadata.apps.viewer.models.data_dictionary import DataDictionary
from onadata.apps.main.tests.test_base import TestBase


class TestGPS(TestBase):

    def test_gps(self):
        self._create_user_and_login()
        self._publish_survey()
        self._make_submissions()
        self._check_has_geopoints()
        self._check_link_to_map_view()

    def _publish_survey(self):
        self.this_directory = os.path.dirname(__file__)
        xls_path = os.path.join(
            self.this_directory, "fixtures", "gps", "gps.xls")
        TestBase._publish_xls_file(self, xls_path)

    def _make_submissions(self):
        surveys = ['gps_1980-01-23_20-52-08',
                   'gps_1980-01-23_21-21-33']
        for survey in surveys:
            path = os.path.join(
                self.this_directory,
                'fixtures', 'gps', 'instances', survey + '.xml')
            self._make_submission(path)

    def _check_has_geopoints(self):
        self.assertEqual(DataDictionary.objects.count(), 1)
        dd = DataDictionary.objects.all()[0]
        # should have been saved to dd.instances_with_geopoints during
        # submission
        self.assertTrue(dd.has_instances_with_geopoints)

    def _check_link_to_map_view(self):
        response = self.client.get("/%s/" % self.user.username)
        map_url = 'href="/%s/forms/gps/map"' % self.user.username
        self.assertContains(response, map_url)
