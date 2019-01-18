# -*- coding: utf-8 -*-
"""
Test export_tools module
"""
import os
import shutil
import tempfile
import zipfile
from datetime import date, datetime, timedelta

from builtins import open
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.files.storage import default_storage
from django.core.files.temp import NamedTemporaryFile
from django.test.utils import override_settings
from django.utils import timezone
from pyxform.builder import create_survey_from_xls
from rest_framework import exceptions
from savReaderWriter import SavWriter

from onadata.apps.api import tests as api_tests
from onadata.apps.logger.models import Attachment, Instance, XForm
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models.export import Export
from onadata.apps.viewer.models.parsed_instance import query_data
from onadata.libs.serializers.merged_xform_serializer import \
    MergedXFormSerializer
from onadata.libs.utils.export_builder import (encode_if_str,
                                               get_value_or_attachment_uri)
from onadata.libs.utils.export_tools import (
    ExportBuilder, check_pending_export, generate_attachments_zip_export,
    generate_export, generate_kml_export, generate_osm_export,
    get_repeat_index_tags, kml_export_data, parse_request_export_options,
    should_create_new_export, str_to_bool)


def _logger_fixture_path(*args):
    return os.path.join(settings.PROJECT_ROOT, 'libs', 'tests', 'fixtures',
                        *args)


class TestExportTools(TestBase):
    """
    Test export_tools functions.
    """
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
        osm_fixtures_dir = os.path.realpath(
            os.path.join(
                os.path.dirname(api_tests.__file__), 'fixtures', 'osm'))
        paths = [
            os.path.join(osm_fixtures_dir, filename) for filename in filenames
        ]
        xlsform_path = os.path.join(osm_fixtures_dir, 'osm.xlsx')
        combined_osm_path = os.path.join(osm_fixtures_dir, 'combined.osm')
        self._publish_xls_file_and_set_xform(xlsform_path)
        submission_path = os.path.join(osm_fixtures_dir, 'instance_a.xml')
        count = Attachment.objects.filter(extension='osm').count()
        self._make_submission_w_attachment(submission_path, paths)
        self.assertTrue(
            Attachment.objects.filter(extension='osm').count() > count)

        options = {"extension": Attachment.OSM}

        export = generate_osm_export(Attachment.OSM, self.user.username,
                                     self.xform.id_string, None, options)
        self.assertTrue(export.is_successful)
        with open(combined_osm_path, encoding='utf-8') as f:
            osm = f.read()
            with default_storage.open(export.filepath) as f2:
                content = f2.read().decode('utf-8')
                self.assertMultiLineEqual(content.strip(), osm.strip())

        # delete submission and check that content is no longer in export
        submission = self.xform.instances.filter().first()
        submission.deleted_at = timezone.now()
        submission.save()

        export = generate_osm_export(Attachment.OSM, self.user.username,
                                     self.xform.id_string, None, options)
        self.assertTrue(export.is_successful)
        with default_storage.open(export.filepath) as f2:
            content = f2.read()
            self.assertEqual(content, b'')

    def test_generate_attachments_zip_export(self):
        filenames = [
            'OSMWay234134797.osm',
            'OSMWay34298972.osm',
        ]
        osm_fixtures_dir = os.path.realpath(
            os.path.join(
                os.path.dirname(api_tests.__file__), 'fixtures', 'osm'))
        paths = [
            os.path.join(osm_fixtures_dir, filename) for filename in filenames
        ]
        xlsform_path = os.path.join(osm_fixtures_dir, 'osm.xlsx')
        self._publish_xls_file_and_set_xform(xlsform_path)
        submission_path = os.path.join(osm_fixtures_dir, 'instance_a.xml')
        count = Attachment.objects.filter(extension='osm').count()
        self._make_submission_w_attachment(submission_path, paths)
        self.assertTrue(
            Attachment.objects.filter(extension='osm').count() > count)

        options = {"extension": Export.ZIP_EXPORT}

        export = generate_attachments_zip_export(
            Export.ZIP_EXPORT, self.user.username, self.xform.id_string, None,
            options)

        self.assertTrue(export.is_successful)

        temp_dir = tempfile.mkdtemp()
        zip_file = zipfile.ZipFile(default_storage.path(export.filepath), "r")
        zip_file.extractall(temp_dir)
        zip_file.close()

        for a in Attachment.objects.all():
            self.assertTrue(
                os.path.exists(os.path.join(temp_dir, a.media_file.name)))
        shutil.rmtree(temp_dir)

        # deleted submission
        submission = self.xform.instances.filter().first()
        submission.deleted_at = timezone.now()
        submission.save()

        export = generate_attachments_zip_export(
            Export.ZIP_EXPORT, self.user.username, self.xform.id_string, None,
            options)
        self.assertTrue(export.is_successful)
        temp_dir = tempfile.mkdtemp()
        zip_file = zipfile.ZipFile(default_storage.path(export.filepath), "r")
        zip_file.extractall(temp_dir)
        zip_file.close()

        for a in Attachment.objects.all():
            self.assertFalse(
                os.path.exists(os.path.join(temp_dir, a.media_file.name)))
        shutil.rmtree(temp_dir)

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
        options = {
            "group_delimiter": "/",
            "remove_group_name": False,
            "split_select_multiples": True
        }
        self._create_old_export(self.xform, export_type, options)

        will_create_new_export = should_create_new_export(
            self.xform, export_type, options)

        self.assertFalse(will_create_new_export)

    def test_should_create_new_export_when_filter_defined(self):
        export_type = "csv"
        options = {
            "group_delimiter": "/",
            "remove_group_name": False,
            "split_select_multiples": True
        }

        self._publish_transportation_form_and_submit_instance()
        self._create_old_export(self.xform, export_type, options)

        # Call should_create_new_export with updated options
        options['remove_group_name'] = True

        will_create_new_export = should_create_new_export(
            self.xform, export_type, options)

        self.assertTrue(will_create_new_export)

    def test_get_value_or_attachment_uri(self):
        path = os.path.join(
            os.path.dirname(__file__), 'fixtures',
            'photo_type_in_repeat_group.xlsx')
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
                u'name': '123.jpg',
                u'instance': 1,
                u'small_download_url': u'%s&suffix=small' % download_url,
                u'id': 1,
                u'xform': 1
            }]
        }  # yapf: disable

        # when include_images is True, you get the attachment url
        media_xpaths = ['photo']
        attachment_list = None
        key = 'photo'
        value = u'123.jpg'
        val_or_url = get_value_or_attachment_uri(key, value, row, self.xform,
                                                 media_xpaths, attachment_list)
        self.assertTrue(val_or_url)

        current_site = Site.objects.get_current()
        url = 'http://%s%s' % (current_site.domain, download_url)
        self.assertEqual(url, val_or_url)

        # when include_images is False, you get the value
        media_xpaths = []
        val_or_url = get_value_or_attachment_uri(key, value, row, self.xform,
                                                 media_xpaths, attachment_list)
        self.assertTrue(val_or_url)
        self.assertEqual(value, val_or_url)

        # test that when row is an empty dict, the function still returns a
        # value
        row.pop('_attachments', None)
        self.assertEqual(row, {})

        media_xpaths = ['photo']
        val_or_url = get_value_or_attachment_uri(key, value, row, self.xform,
                                                 media_xpaths, attachment_list)
        self.assertTrue(val_or_url)
        self.assertEqual(value, val_or_url)

    def test_get_attachment_uri_for_filename_with_space(self):
        path = os.path.join(
            os.path.dirname(__file__), 'fixtures',
            'photo_type_in_repeat_group.xlsx')
        self._publish_xls_file_and_set_xform(path)

        filename = u'bob/attachments/1_2_3.jpg'
        download_url = u'/api/v1/files/1?filename=%s' % filename

        # used a smaller version of row because we only using _attachmets key
        row = {
            u'_attachments': [{
                u'mimetype': u'image/jpeg',
                u'medium_download_url': u'%s&suffix=medium' % download_url,
                u'download_url': download_url,
                u'filename': filename,
                u'name': '1 2 3.jpg',
                u'instance': 1,
                u'small_download_url': u'%s&suffix=small' % download_url,
                u'id': 1,
                u'xform': 1
            }]
        }  # yapf: disable

        # when include_images is True, you get the attachment url
        media_xpaths = ['photo']
        attachment_list = None
        key = 'photo'
        value = u'1 2 3.jpg'
        val_or_url = get_value_or_attachment_uri(key, value, row, self.xform,
                                                 media_xpaths, attachment_list)

        self.assertTrue(val_or_url)

        current_site = Site.objects.get_current()
        url = 'http://%s%s' % (current_site.domain, download_url)
        self.assertEqual(url, val_or_url)

    def test_parse_request_export_options(self):
        request = self.factory.get(
            '/export_async',
            data={
                "binary_select_multiples": "true",
                "do_not_split_select_multiples": "false",
                "remove_group_name": "false",
                "include_labels": "false",
                "include_labels_only": "false",
                "include_images": "false"
            })

        options = parse_request_export_options(request.GET)

        self.assertEqual(options['split_select_multiples'], True)
        self.assertEqual(options['binary_select_multiples'], True)
        self.assertEqual(options['include_labels'], False)
        self.assertEqual(options['include_labels_only'], False)
        self.assertEqual(options['remove_group_name'], False)
        self.assertEqual(options['include_images'], False)

        request = self.factory.get(
            '/export_async',
            data={
                "do_not_split_select_multiples": "true",
                "remove_group_name": "true",
                "include_labels": "true",
                "include_labels_only": "true",
                "include_images": "true"
            })

        options = parse_request_export_options(request.GET)

        self.assertEqual(options['split_select_multiples'], False)
        self.assertEqual(options['include_labels'], True)
        self.assertEqual(options['include_labels_only'], True)
        self.assertEqual(options['remove_group_name'], True)
        self.assertEqual(options['include_images'], True)

    def test_export_not_found(self):
        export_type = "csv"
        options = {
            "group_delimiter": "/",
            "remove_group_name": False,
            "split_select_multiples": True
        }

        self._publish_transportation_form_and_submit_instance()
        self._create_old_export(self.xform, export_type, options)
        export = Export(
            xform=self.xform, export_type=export_type, options=options)
        export.save()
        export_id = export.pk

        export.delete()
        export = generate_export(export_type, self.xform, export_id, options)

        self.assertIsNotNone(export)
        self.assertTrue(export.is_successful)
        self.assertNotEqual(export_id, export.pk)

    def test_kml_export_data(self):
        """
        Test kml_export_data(id_string, user, xform=None).
        """
        kml_md = """
        | survey |
        |        | type              | name  | label |
        |        | geopoint          | gps   | GPS   |
        |        | select one fruits | fruit | Fruit |

        | choices |
        |         | list name | name   | label  |
        |         | fruits    | orange | Orange |
        |         | fruits    | mango  | Mango  |
        """
        xform1 = self._publish_markdown(kml_md, self.user, id_string='a')
        xform2 = self._publish_markdown(kml_md, self.user, id_string='b')
        xml = '<data id="a"><gps>-1.28 36.83</gps><fruit>orange</fruit></data>'
        Instance(xform=xform1, xml=xml).save()
        xml = '<data id="b"><gps>32.85 13.04</gps><fruit>mango</fruit></data>'
        Instance(xform=xform2, xml=xml).save()
        data = {
            'xforms': [
                "http://testserver/api/v1/forms/%s" % xform1.pk,
                "http://testserver/api/v1/forms/%s" % xform2.pk,
            ],
            'name': 'Merged Dataset',
            'project':
            "http://testserver/api/v1/projects/%s" % xform1.project.pk,
        }  # yapf: disable
        request = self.factory.post('/')
        request.user = self.user
        serializer = MergedXFormSerializer(
            data=data, context={'request': request})
        self.assertTrue(serializer.is_valid())
        serializer.save()
        xform = XForm.objects.filter(
            pk__gt=xform2.pk, is_merged_dataset=True).first()
        expected_data = [{
            'name': u'a',
            'image_urls': [],
            'lat': -1.28,
            'table': u'<table border="1"><a href="#"><img width="210" class="thumbnail" src="" alt=""></a><tr><td>GPS</td><td>-1.28 36.83</td></tr><tr><td>Fruit</td><td>orange</td></tr></table>',  # noqa pylint: disable=C0301
            'lng': 36.83,
            'id': xform1.instances.all().first().pk
        }, {
            'name': u'b',
            'image_urls': [],
            'lat': 32.85,
            'table':
            u'<table border="1"><a href="#"><img width="210" class="thumbnail" src="" alt=""></a><tr><td>GPS</td><td>32.85 13.04</td></tr><tr><td>Fruit</td><td>mango</td></tr></table>',  # noqa pylint: disable=C0301
            'lng': 13.04,
            'id': xform2.instances.all().first().pk
        }]  # yapf: disable
        self.assertEqual(
            kml_export_data(xform.id_string, xform.user), expected_data)

    def test_kml_exports(self):
        """
        Test generate_kml_export()
        """
        export_type = "kml"
        options = {
            "group_delimiter": "/",
            "remove_group_name": False,
            "split_select_multiples": True,
            "extension": 'kml'
        }

        self._publish_transportation_form_and_submit_instance()
        username = self.xform.user.username
        id_string = self.xform.id_string

        export = generate_kml_export(
            export_type, username, id_string, options=options)
        self.assertIsNotNone(export)
        self.assertTrue(export.is_successful)

        export_id = export.id

        export.delete()

        export = generate_kml_export(
            export_type,
            username,
            id_string,
            export_id=export_id,
            options=options)

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
        survey = create_survey_from_xls(
            _logger_fixture_path('grains/grains.xls'))
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

    @override_settings(PENDING_EXPORT_TIME=1)
    def test_retrieving_pending_export(self):
        self._create_user_and_login()
        self._publish_transportation_form()

        export = Export(
            xform=self.xform,
            export_type=Export.CSV_EXPORT,
            options={},
            task_id="abcsde")

        export.save()

        test_export = check_pending_export(self.xform, Export.CSV_EXPORT, {})

        self.assertEqual(export, test_export)

        test_export = check_pending_export(self.xform, Export.XLS_EXPORT, {})

        self.assertIsNone(test_export)

        export.created_on = export.created_on - timedelta(minutes=6)
        export.save()

        test_export = check_pending_export(self.xform, Export.CSV_EXPORT, {})

        self.assertIsNone(test_export)

    def test_get_repeat_index_tags(self):
        """
        Test get_repeat_index_tags(index_tags) function.
        """
        self.assertIsNone(get_repeat_index_tags(None))

        self.assertEqual(get_repeat_index_tags('.'), ('.', '.'))
        self.assertEqual(get_repeat_index_tags('{,}'), ('{', '}'))

        with self.assertRaises(exceptions.ParseError):
            get_repeat_index_tags('p')

    def test_generate_filtered_attachments_zip_export(self):
        """Test media zip file export filters attachments"""
        filenames = [
            'OSMWay234134797.osm',
            'OSMWay34298972.osm',
        ]
        osm_fixtures_dir = os.path.realpath(
            os.path.join(
                os.path.dirname(api_tests.__file__), 'fixtures', 'osm'))
        paths = [
            os.path.join(osm_fixtures_dir, filename) for filename in filenames
        ]
        xlsform_path = os.path.join(osm_fixtures_dir, 'osm.xlsx')
        self._publish_xls_file_and_set_xform(xlsform_path)
        submission_path = os.path.join(osm_fixtures_dir, 'instance_a.xml')
        count = Attachment.objects.filter(extension='osm').count()
        self._make_submission_w_attachment(submission_path, paths)
        self._make_submission_w_attachment(submission_path, paths)
        self.assertTrue(
            Attachment.objects.filter(extension='osm').count() > count)

        options = {
            "extension": Export.ZIP_EXPORT,
            "query": u'{"_submission_time": {"$lte": "2019-01-13T00:00:00"}}'}
        filter_query = options.get("query")
        instance_ids = query_data(
            self.xform, fields='["_id"]', query=filter_query)

        export = generate_attachments_zip_export(
            Export.ZIP_EXPORT, self.user.username, self.xform.id_string, None,
            options)

        self.assertTrue(export.is_successful)

        temp_dir = tempfile.mkdtemp()
        zip_file = zipfile.ZipFile(default_storage.path(export.filepath), "r")
        zip_file.extractall(temp_dir)
        zip_file.close()

        filtered_attachments = Attachment.objects.filter(
            instance__xform_id=self.xform.pk).filter(
            instance_id__in=[i_id['_id'] for i_id in instance_ids])

        self.assertNotEqual(
            Attachment.objects.count(), filtered_attachments.count())

        for a in filtered_attachments:
            self.assertTrue(
                os.path.exists(os.path.join(temp_dir, a.media_file.name)))
        shutil.rmtree(temp_dir)

        # export with no query
        options.pop('query')
        export1 = generate_attachments_zip_export(
            Export.ZIP_EXPORT, self.user.username, self.xform.id_string, None,
            options)

        self.assertTrue(export1.is_successful)

        temp_dir = tempfile.mkdtemp()
        zip_file = zipfile.ZipFile(default_storage.path(export1.filepath), "r")
        zip_file.extractall(temp_dir)
        zip_file.close()

        for a in Attachment.objects.all():
            self.assertTrue(
                os.path.exists(os.path.join(temp_dir, a.media_file.name)))
        shutil.rmtree(temp_dir)
