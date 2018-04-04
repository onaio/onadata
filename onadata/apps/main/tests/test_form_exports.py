import os
import time
import csv
import tempfile

from django.core.urlresolvers import reverse
from django.utils import timezone
from xlrd import open_workbook

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models.export import Export
from onadata.apps.viewer.views import zip_export, kml_export, export_download
from onadata.libs.utils.common_tools import get_response_content
from onadata.libs.utils.export_tools import generate_export
from onadata.libs.utils.user_auth import http_auth_string


class TestFormExports(TestBase):

    def setUp(self):
        TestBase.setUp(self)
        self._create_user_and_login()
        self._publish_transportation_form_and_submit_instance()
        self.csv_url = reverse('csv_export', kwargs={
            'username': self.user.username,
            'id_string': self.xform.id_string})
        self.xls_url = reverse('xls_export', kwargs={
            'username': self.user.username,
            'id_string': self.xform.id_string})

    def _num_rows(self, content, export_format):
        def xls_rows(f):
            return open_workbook(file_contents=f).sheets()[0].nrows

        def csv_rows(f):
            with tempfile.TemporaryFile('w+') as tmp:
                tmp.write(f.decode('utf-8'))
                tmp.seek(0)
                return len([line for line in csv.reader(tmp)])
        num_rows_fn = {
            'xls': xls_rows,
            'csv': csv_rows,
        }
        return num_rows_fn[export_format](content)

    def test_csv_raw_export_name(self):
        response = self.client.get(self.csv_url + '?raw=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Disposition'], 'attachment;')

    def _filter_export_test(self, url, export_format):
        """
        Test filter exports.  Use sleep to ensure we don't have unique seconds.
        Number of rows equals number of surveys plus 1, the header row.
        """
        time.sleep(1)
        # 1 survey exists before this time
        start_time = timezone.now().strftime('%y_%m_%d_%H_%M_%S')
        time.sleep(1)
        s = self.surveys[1]
        self._make_submission(
            os.path.join(self.this_directory, 'fixtures',
                         'transportation', 'instances', s, s + '.xml'))
        time.sleep(1)
        # 2 surveys exist before this time
        end_time = timezone.now().strftime('%y_%m_%d_%H_%M_%S')
        time.sleep(1)
        # 3 surveys exist in total
        s = self.surveys[2]
        self._make_submission(
            os.path.join(self.this_directory, 'fixtures',
                         'transportation', 'instances', s, s + '.xml'))
        # test restricting to before end time
        params = {'end': end_time}
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        content = get_response_content(response, decode=False)
        self.assertEqual(self._num_rows(content, export_format), 3)
        # test restricting to after start time, thus excluding the initial
        # submission
        params = {'start': start_time}
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        content = get_response_content(response, decode=False)
        self.assertEqual(self._num_rows(content, export_format), 3)
        # test no time restriction
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = get_response_content(response, decode=False)
        self.assertEqual(self._num_rows(content, export_format), 4)
        # test restricting to between start time and end time
        params = {'start': start_time, 'end': end_time}
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        content = get_response_content(response, decode=False)
        self.assertEqual(self._num_rows(content, export_format), 2)

    def test_filter_by_date_csv(self):
        self._filter_export_test(self.csv_url, 'csv')

    def test_filter_by_date_xls(self):
        self._filter_export_test(self.xls_url, 'xls')

    def test_restrict_csv_export_if_not_shared(self):
        response = self.anon.get(self.csv_url)
        self.assertEqual(response.status_code, 403)

    def test_xls_raw_export_name(self):
        response = self.client.get(self.xls_url + '?raw=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Disposition'], 'attachment;')

    def test_restrict_xls_export_if_not_shared(self):
        response = self.anon.get(self.xls_url)
        self.assertEqual(response.status_code, 403)

    def test_zip_raw_export_name(self):
        url = reverse(zip_export, kwargs={'username': self.user.username,
                                          'id_string': self.xform.id_string})
        response = self.client.get(url + '?raw=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Disposition'], 'attachment;')

    def test_restrict_zip_export_if_not_shared(self):
        url = reverse(zip_export, kwargs={'username': self.user.username,
                                          'id_string': self.xform.id_string})
        response = self.anon.get(url)
        self.assertEqual(response.status_code, 403)

    def test_restrict_kml_export_if_not_shared(self):
        url = reverse(kml_export, kwargs={'username': self.user.username,
                                          'id_string': self.xform.id_string})
        response = self.anon.get(url)
        self.assertEqual(response.status_code, 403)

    def test_allow_csv_export_if_shared(self):
        self.xform.shared_data = True
        self.xform.save()
        response = self.anon.get(self.csv_url)
        self.assertEqual(response.status_code, 200)

    def test_allow_xls_export_if_shared(self):
        self.xform.shared_data = True
        self.xform.save()
        response = self.anon.get(self.xls_url)
        self.assertEqual(response.status_code, 200)

    def test_allow_zip_export_if_shared(self):
        self.xform.shared_data = True
        self.xform.save()
        url = reverse(zip_export, kwargs={'username': self.user.username,
                                          'id_string': self.xform.id_string})
        response = self.anon.get(url)
        self.assertEqual(response.status_code, 200)

    def test_allow_kml_export_if_shared(self):
        self.xform.shared_data = True
        self.xform.save()
        url = reverse(kml_export, kwargs={'username': self.user.username,
                                          'id_string': self.xform.id_string})
        response = self.anon.get(url)
        self.assertEqual(response.status_code, 200)

    def test_allow_csv_export(self):
        response = self.client.get(self.csv_url)
        self.assertEqual(response.status_code, 200)

    def test_allow_xls_export(self):
        response = self.client.get(self.xls_url)
        self.assertEqual(response.status_code, 200)

    def test_allow_zip_export(self):
        url = reverse(zip_export, kwargs={'username': self.user.username,
                                          'id_string': self.xform.id_string})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_allow_kml_export(self):
        url = reverse(kml_export, kwargs={'username': self.user.username,
                                          'id_string': self.xform.id_string})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_allow_csv_export_for_basic_auth(self):
        extra = {
            'HTTP_AUTHORIZATION': http_auth_string(self.login_username,
                                                   self.login_password)
        }
        response = self.anon.get(self.csv_url, **extra)
        self.assertEqual(response.status_code, 200)

    def test_allow_xls_export_for_basic_auth(self):
        extra = {
            'HTTP_AUTHORIZATION': http_auth_string(self.login_username,
                                                   self.login_password)
        }
        response = self.anon.get(self.xls_url, **extra)
        self.assertEqual(response.status_code, 200)

    def test_allow_zip_export_for_basic_auth(self):
        extra = {
            'HTTP_AUTHORIZATION': http_auth_string(self.login_username,
                                                   self.login_password)
        }
        url = reverse(zip_export, kwargs={'username': self.user.username,
                                          'id_string': self.xform.id_string})
        response = self.anon.get(url, **extra)
        self.assertEqual(response.status_code, 200)

    def test_allow_kml_export_for_basic_auth(self):
        extra = {
            'HTTP_AUTHORIZATION': http_auth_string(self.login_username,
                                                   self.login_password)
        }
        url = reverse(kml_export, kwargs={'username': self.user.username,
                                          'id_string': self.xform.id_string})
        response = self.anon.get(url, **extra)
        self.assertEqual(response.status_code, 200)

    def test_allow_export_download_for_basic_auth(self):
        extra = {
            'HTTP_AUTHORIZATION': http_auth_string(self.login_username,
                                                   self.login_password)
        }
        # create export
        options = {"extension": "csv"}

        export = generate_export(
            Export.CSV_EXPORT,
            self.xform,
            None,
            options)
        self.assertTrue(isinstance(export, Export))
        url = reverse(export_download, kwargs={
            'username': self.user.username,
            'id_string': self.xform.id_string,
            'export_type': export.export_type,
            'filename': export.filename
        })
        response = self.anon.get(url, **extra)
        self.assertEqual(response.status_code, 200)
