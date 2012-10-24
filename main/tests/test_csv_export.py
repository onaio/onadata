import os
import csv
from StringIO import StringIO
from django.core.urlresolvers import reverse
from odk_logger.models.xform import XForm
from odk_viewer.views import csv_export
from odk_viewer.models import DataDictionary
from test_base import MainTestCase

class TestExport(MainTestCase):

    def setUp(self):
        self._create_user_and_login()
        self.fixture_dir = os.path.join(self.this_directory, 'fixtures',
                'csv_export')

    def test_csv_export(self):
        path = os.path.join(self.fixture_dir, 'double_repeat.xls')
        self._publish_xls_file(path)
        path = os.path.join(self.fixture_dir, 'instance.xml')
        self._make_submission(path)
        self.maxDiff = None
        dd = DataDictionary.objects.all()[0]
        xpaths = [
            u'/double_repeat/bed_net[1]/member[1]/name',
            u'/double_repeat/bed_net[1]/member[2]/name',
            u'/double_repeat/bed_net[2]/member[1]/name',
            u'/double_repeat/bed_net[2]/member[2]/name',
            ]
        self.assertEquals(dd.xpaths(repeat_iterations=2), xpaths)
        url = reverse(csv_export, kwargs={'username': self.user.username,
                'id_string': 'double_repeat'})
        response = self.client.get(url)
        with open(os.path.join(self.fixture_dir, 'export.csv')) as f:
            expected_content = f.read()
        self.assertEquals(response.content, expected_content)

    def test_csv_split_geo(self):
        path = os.path.join(self.fixture_dir, 'tutorial.xls')
        self._publish_xls_file(path)
        path = os.path.join(self.fixture_dir, 'tutorial.xml')
        self._make_submission(path)
        url = reverse(csv_export, kwargs={'username': self.user.username,
                'id_string': 'tutorial'})
        response = self.client.get(url)
        with open(os.path.join(self.fixture_dir, 'tutorial.csv')) as f:
            expected_content = f.read()
        self.assertEquals(response.content, expected_content)

    def test_flat_csv_export(self):
        self.maxDiff = None
        path = os.path.join(self.fixture_dir, 'tutorial_w_repeats.xls')
        count = XForm.objects.count()
        self._publish_xls_file(path)
        self.assertEqual(XForm.objects.count(), count + 1)
        self.xform = XForm.objects.order_by('-id')[:1][0]
        path = os.path.join(self.fixture_dir, 'tutorial_w_repeats.xml')
        self._make_submission(path)
        self.assertEqual(self.response.status_code, 201)
        url = reverse('flat-csv',
            kwargs={'username': self.user.username,
                    'id_string': self.xform.id_string})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        reader = csv.reader(StringIO(response.content))
        returned_csv = [row for row in reader]
        path = os.path.join(self.fixture_dir, 'tutorial_w_repeats_flattened.csv')
        with open(path, "r") as f:
            expected_csv = [row for row in csv.reader(f)]
        # check that we have all the column headers
        self.assertEqual(sorted(returned_csv[0]), sorted(expected_csv[0]))