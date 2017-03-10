import os
from datetime import date, datetime
from django.conf import settings
from django.core.files.storage import default_storage
from django.contrib.sites.models import Site
from pyxform.builder import create_survey_from_xls
from pyxform.tests_v1.pyxform_test_case import PyxformTestCase
from django.core.files.temp import NamedTemporaryFile

from savReaderWriter import SavWriter

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models.export import Export
from onadata.libs.utils.export_builder import encode_if_str
from onadata.libs.utils.export_tools import generate_export
from onadata.libs.utils.export_tools import generate_osm_export
from onadata.libs.utils.export_builder import get_value_or_attachment_uri
from onadata.libs.utils.export_tools import parse_request_export_options
from onadata.libs.utils.export_tools import should_create_new_export
from onadata.libs.utils.export_tools import str_to_bool
from onadata.libs.utils.export_tools import ExportBuilder
from onadata.libs.utils.export_tools import generate_kml_export
from onadata.apps.logger.models import Attachment
from onadata.apps.api import tests as api_tests


def _logger_fixture_path(*args):
    return os.path.join(settings.PROJECT_ROOT, 'libs', 'tests', 'fixtures',
                        *args)


class TestExportTools(PyxformTestCase, TestBase):

    def _create_old_export(self, xform, export_type, options):
        Export(xform=xform, export_type=export_type, options=options).save()
        self.export = Export.objects.filter(
            xform=xform, export_type=export_type)

    def test_encode_if_str(self):
        row = {"date": date(1899, 9, 9)}
        date_str = encode_if_str(row, "date", True)
        self.assertEqual(date_str, '1899-09-09')

        row = {"date": date(2001, 9, 9)}
        date_str = encode_if_str(row, "date", True)
        self.assertEqual(date_str, '2001-09-09')

        row = {"datetime": datetime(1899, 9, 9)}
        date_str = encode_if_str(row, "datetime", True)
        self.assertEqual(date_str, '1899-09-09T00:00:00')

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
        media_xpaths = ['photo']
        attachment_list = None
        key = 'photo'
        value = u'123.jpg'
        val_or_url = get_value_or_attachment_uri(
            key, value, row, self.xform, media_xpaths, attachment_list)
        self.assertTrue(val_or_url)

        current_site = Site.objects.get_current()
        url = 'http://%s%s' % (current_site.domain, download_url)
        self.assertEqual(url, val_or_url)

        # when include_images is False, you get the value
        media_xpaths = []
        val_or_url = get_value_or_attachment_uri(
            key, value, row, self.xform, media_xpaths, attachment_list)
        self.assertTrue(val_or_url)
        self.assertEqual(value, val_or_url)

        # test that when row is an empty dict, the function still returns a
        # value
        row.pop('_attachments', None)
        self.assertEqual(row, {})

        media_xpaths = ['photo']
        val_or_url = get_value_or_attachment_uri(
            key, value, row, self.xform, media_xpaths, attachment_list)
        self.assertTrue(val_or_url)
        self.assertEqual(value, val_or_url)

    def test_parse_request_export_options(self):
        request = self.factory.get(
            '/export_async', data={"do_not_split_select_multiples": "false",
                                   "remove_group_name": "false",
                                   "include_labels": "false",
                                   "include_labels_only": "false",
                                   "include_images": "false"})

        options = parse_request_export_options(request.GET)

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

        options = parse_request_export_options(request.GET)

        self.assertEqual(options['split_select_multiples'], False)
        self.assertEqual(options['include_labels'], True)
        self.assertEqual(options['include_labels_only'], True)
        self.assertEqual(options['remove_group_name'], True)
        self.assertEqual(options['include_images'], True)

    def test_export_not_found(self):
        export_type = "csv"
        options = {"group_delimiter": "/",
                   "remove_group_name": False,
                   "split_select_multiples": True}

        self._publish_transportation_form_and_submit_instance()
        self._create_old_export(self.xform, export_type, options)
        export = Export(xform=self.xform, export_type=export_type,
                        options=options)
        export.save()
        export_id = export.pk

        export.delete()
        export = generate_export(export_type, self.xform, export_id, options)

        self.assertIsNotNone(export)
        self.assertTrue(export.is_successful)
        self.assertNotEqual(export_id, export.pk)

    def test_kml_exports(self):
        export_type = "kml"
        options = {"group_delimiter": "/",  "remove_group_name": False,
                   "split_select_multiples": True, "extension": 'kml'}

        self._publish_transportation_form_and_submit_instance()
        username = self.xform.user.username
        id_string = self.xform.id_string

        export = generate_kml_export(export_type, username, id_string,
                                     options=options)
        self.assertIsNotNone(export)
        self.assertTrue(export.is_successful)

        export_id = export.id

        export.delete()

        export = generate_kml_export(export_type, username, id_string,
                                     export_id=export_id, options=options)

        self.assertIsNotNone(export)
        self.assertTrue(export.is_successful)

    def test_str_to_bool(self):
        self.assertTrue(str_to_bool(True))
        self.assertTrue(str_to_bool('True'))
        self.assertTrue(str_to_bool('TRUE'))
        self.assertTrue(str_to_bool('true'))
        self.assertTrue(str_to_bool('t'))
        self.assertTrue(str_to_bool('1'))
        self.assertTrue(str_to_bool(1))

        self.assertFalse(str_to_bool(False))
        self.assertFalse(str_to_bool('False'))
        self.assertFalse(str_to_bool('F'))
        self.assertFalse(str_to_bool('random'))
        self.assertFalse(str_to_bool(234))
        self.assertFalse(str_to_bool(0))
        self.assertFalse(str_to_bool('0'))

    def test_get_sav_value_labels(self):
        md = """
        | survey |
        |        | type              | name  | label |
        |        | select one fruits | fruit | Fruit |

        | choices |
        |         | list name | name   | label  |
        |         | fruits    | orange | Orange |
        |         | fruits    | mango  | Mango  |
        """
        survey = self.md_to_pyxform_survey(md)
        export_builder = ExportBuilder()
        export_builder.TRUNCATE_GROUP_TITLE = True
        export_builder.set_survey(survey)
        export_builder.INCLUDE_LABELS = True
        export_builder.set_survey(survey)
        expected_data = {'fruit': {'orange': 'Orange', 'mango': 'Mango'}}
        self.assertEqual(export_builder._get_sav_value_labels(), expected_data)

    def test_get_sav_value_labels_multi_language(self):
        md = """
        | survey |
        |        | type              | name  | label:English | label:Swahili |
        |        | select one fruits | fruit | Fruit         | Tunda         |

        | choices |
        |         | list name | name   | label: English | label:Swahili |
        |         | fruits    | orange | Orange         | Chungwa       |
        |         | fruits    | mango  | Mango          | Maembe        |
        """
        survey = self.md_to_pyxform_survey(md)
        export_builder = ExportBuilder()
        export_builder.TRUNCATE_GROUP_TITLE = True
        export_builder.set_survey(survey)
        export_builder.INCLUDE_LABELS = True
        export_builder.set_survey(survey)
        expected_data = {'fruit': {'orange': 'Orange', 'mango': 'Mango'}}
        self.assertEqual(export_builder._get_sav_value_labels(), expected_data)

        del export_builder._sav_value_labels
        export_builder.dd._default_language = 'Swahili'
        expected_data = {'fruit': {'orange': 'Chungwa', 'mango': 'Maembe'}}
        self.assertEqual(export_builder._get_sav_value_labels(), expected_data)

    def test_get_sav_value_labels_for_choice_filter(self):
        md = """
        | survey |
        |        | type              | name  | label | choice_filter |
        |        | select one fruits | fruit | Fruit | active=1      |

        | choices |
        |         | list name | name   | label  | active |
        |         | fruits    | orange | Orange | 1      |
        |         | fruits    | mango  | Mango  | 1      |
        """
        survey = self.md_to_pyxform_survey(md)
        export_builder = ExportBuilder()
        export_builder.TRUNCATE_GROUP_TITLE = True
        export_builder.set_survey(survey)
        export_builder.INCLUDE_LABELS = True
        export_builder.set_survey(survey)
        expected_data = {'fruit': {'orange': 'Orange', 'mango': 'Mango'}}
        self.assertEqual(export_builder._get_sav_value_labels(), expected_data)

    def test_sav_duplicate_columns(self):
        more_than_64_char = "akjasdlsakjdkjsadlsakjgdlsagdgdgdsajdgkjdsdgsj" \
                "adsasdasgdsahdsahdsadgsdf"
        md = """
        | survey |
        |        | type           | name | label | choice_filter |
        |        | select one fts | fruit| Fruit | active=1      |
        |	     | integer	      | age  | Age   |               |
        |	     | integer	      | {}   | Resp2 |               |
        |        | begin group    | {}   | Resp  |               |
        |	     | integer	      | age  | Resp  |               |
        |	     | text 	      | name | Name  |               |
        |        | begin group    | {}   | Resp2 |               |
        |	     | integer	      | age  | Resp2 |               |
        |	     | integer	      | {}   | Resp2 |               |
        |        | end group      |      |       |               |
        |        | end group      |      |       |               |


        | choices |
        |         | list name | name   | label  | active |
        |         | fts       | orange | Orange | 1      |
        |         | fts       | mango  | Mango  | 1      |
        """
        md = md.format(more_than_64_char, more_than_64_char, more_than_64_char,
                       more_than_64_char)
        survey = self.md_to_pyxform_survey(md)
        export_builder = ExportBuilder()
        export_builder.TRUNCATE_GROUP_TITLE = True
        export_builder.set_survey(survey)
        export_builder.INCLUDE_LABELS = True
        export_builder.set_survey(survey)

        for sec in export_builder.sections:
            sav_options = export_builder._get_sav_options(sec['elements'])
            sav_file = NamedTemporaryFile(suffix=".sav")
            # No exception is raised
            SavWriter(sav_file.name, **sav_options)

    def test_sav_special_char_columns(self):
        survey = create_survey_from_xls(_logger_fixture_path(
            'grains/grains.xls'))
        export_builder = ExportBuilder()
        export_builder.TRUNCATE_GROUP_TITLE = True
        export_builder.set_survey(survey)
        export_builder.INCLUDE_LABELS = True
        export_builder.set_survey(survey)

        for sec in export_builder.sections:
            sav_options = export_builder._get_sav_options(sec['elements'])
            sav_file = NamedTemporaryFile(suffix=".sav")
            # No exception is raised
            SavWriter(sav_file.name, **sav_options)
