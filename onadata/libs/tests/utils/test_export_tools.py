import os
from datetime import date, datetime
from django.core.files.storage import default_storage
from django.contrib.sites.models import Site

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models.export import Export

from onadata.libs.utils.export_tools import (
    encode_if_str,
    get_value_or_attachment_uri,
    generate_osm_export,
    should_create_new_export,
    parse_request_export_options)
from onadata.apps.logger.models import Attachment
from onadata.apps.api import tests as api_tests


class TestExportTools(TestBase):

    def _create_old_export(self, xform, export_type, options):
        Export(xform=xform, export_type=export_type, options=options).save()
        self.export = Export.objects.filter(
            xform=xform, export_type=export_type)

    def test_invalid_date_format_is_caught(self):
        row = {"date": date(0201, 9, 9)}
        with self.assertRaises(Exception) as error:
            encode_if_str(row, "date", True)

        self.assertEqual(error.exception.message,
                         u'0129-09-09 has an invalid date format')

        row = {"date": date(2001, 9, 9)}
        date_str = encode_if_str(row, "date", True)
        self.assertEqual(date_str, '2001-09-09')

    def test_invalid_datetime_format_is_caught(self):
        row = {"datetime": datetime(0201, 9, 9)}
        with self.assertRaises(Exception) as error:
            encode_if_str(row, "datetime", True)

        self.assertEqual(error.exception.message,
                         u'0129-09-09 00:00:00 has an invalid datetime format')

        row = {"datetime": datetime(2001, 9, 9)}
        date_str = encode_if_str(row, "datetime", True)
        self.assertEqual(date_str, '2001-09-09T00:00:00')

    def test_generate_osm_export(self):
        filenames = [
            'OSMWay234134797.osm',
            'OSMWay34298972.osm',
        ]
        osm_fixtures_dir = os.path.realpath(os.path.join(
            os.path.dirname(api_tests.__file__), 'fixtures', 'osm'))
        paths = [
            os.path.join(osm_fixtures_dir, filename)
            for filename in filenames]
        xlsform_path = os.path.join(osm_fixtures_dir, 'osm.xlsx')
        combined_osm_path = os.path.join(osm_fixtures_dir, 'combined.osm')
        self._publish_xls_file_and_set_xform(xlsform_path)
        submission_path = os.path.join(osm_fixtures_dir, 'instance_a.xml')
        count = Attachment.objects.filter(extension='osm').count()
        self._make_submission_w_attachment(submission_path, paths)
        self.assertTrue(
            Attachment.objects.filter(extension='osm').count() > count)

        options = {"extension": Attachment.OSM}

        export = generate_osm_export(
            Attachment.OSM,
            self.user.username,
            self.xform.id_string,
            None,
            options)
        self.assertTrue(export.is_successful)
        with open(combined_osm_path) as f:
            osm = f.read()
            with default_storage.open(export.filepath) as f2:
                content = f2.read()
                self.assertMultiLineEqual(content.strip(), osm.strip())

    def test_should_create_new_export(self):
        # should only create new export if filter is defined
        # Test setup
        export_type = "csv"
        options = {"group_delimiter": "."}
        self._publish_transportation_form_and_submit_instance()

        will_create_new_export = should_create_new_export(
            self.xform, export_type, options)

        self.assertTrue(will_create_new_export)

    def test_should_not_create_new_export_when_old_exists(self):
        export_type = "csv"
        self._publish_transportation_form_and_submit_instance()
        options = {"group_delimiter": "/",
                   "remove_group_name": False,
                   "split_select_multiples": True}
        self._create_old_export(self.xform, export_type, options)

        will_create_new_export = should_create_new_export(
            self.xform, export_type, options)

        self.assertFalse(will_create_new_export)

    def test_should_create_new_export_when_filter_defined(self):
        export_type = "csv"
        options = {"group_delimiter": "/",
                   "remove_group_name": False,
                   "split_select_multiples": True}

        self._publish_transportation_form_and_submit_instance()
        self._create_old_export(self.xform, export_type, options)

        # Call should_create_new_export with updated options
        options['remove_group_name'] = True

        will_create_new_export = should_create_new_export(
            self.xform, export_type, options)

        self.assertTrue(will_create_new_export)

    def test_get_value_or_attachment_uri(self):
        path = os.path.join(
            os.path.dirname(__file__),
            'fixtures', 'photo_type_in_repeat_group.xlsx')
        self._publish_xls_file_and_set_xform(path)

        filename = u'bob/attachments/123.jpg'
        download_url = u'/api/v1/files/1?filename=%s' % filename

        # used a smaller version of row because we only using _attachmets key
        row = {
            u'_attachments': [{
                u'mimetype': u'image/jpeg',
                u'medium_download_url': u'%s&suffix=medium' % download_url,
                u'download_url': download_url,
                u'filename': filename,
                u'instance': 1,
                u'small_download_url': u'%s&suffix=small' % download_url,
                u'id': 1,
                u'xform': 1
            }]
        }

        # when include_images is True, you get the attachment url
        include_images = True
        attachment_list = None
        key = 'photo'
        value = u'123.jpg'
        val_or_url = get_value_or_attachment_uri(
            key, value, row, self.xform, include_images, attachment_list)
        self.assertTrue(val_or_url)

        current_site = Site.objects.get_current()
        url = 'http://%s%s' % (current_site.domain, download_url)
        self.assertEqual(url, val_or_url)

        # when include_images is False, you get the value
        include_images = False
        val_or_url = get_value_or_attachment_uri(
            key, value, row, self.xform, include_images, attachment_list)
        self.assertTrue(val_or_url)
        self.assertEqual(value, val_or_url)

        # test that when row is an empty dict, the function still returns a
        # value
        row.pop('_attachments', None)
        self.assertEqual(row, {})

        include_images = True
        val_or_url = get_value_or_attachment_uri(
            key, value, row, self.xform, include_images, attachment_list)
        self.assertTrue(val_or_url)
        self.assertEqual(value, val_or_url)

    def test_parse_request_export_options(self):
        request = self.factory.get(
            '/export_async', data={"do_not_split_select_multiples": "false",
                                   "remove_group_name": "false",
                                   "include_labels": "false",
                                   "include_labels_only": "false",
                                   "include_images": "false"})

        options = parse_request_export_options(request)

        self.assertEqual(options['split_select_multiples'], True)
        self.assertEqual(options['include_labels'], False)
        self.assertEqual(options['include_labels_only'], False)
        self.assertEqual(options['remove_group_name'], False)
        self.assertEqual(options['include_images'], False)

        request = self.factory.get(
            '/export_async', data={"do_not_split_select_multiples": "true",
                                   "remove_group_name": "true",
                                   "include_labels": "true",
                                   "include_labels_only": "true",
                                   "include_images": "true"})

        options = parse_request_export_options(request)

        self.assertEqual(options['split_select_multiples'], False)
        self.assertEqual(options['include_labels'], True)
        self.assertEqual(options['include_labels_only'], True)
        self.assertEqual(options['remove_group_name'], True)
        self.assertEqual(options['include_images'], True)
