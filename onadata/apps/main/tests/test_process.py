import csv
import fnmatch
import json
import os
import re
import pytz
from builtins import open
from datetime import datetime
from future.utils import iteritems
from hashlib import md5
from mock import patch

from django.core.urlresolvers import reverse
from django.conf import settings
from django_digest.test import Client as DigestClient
from django.core.files.uploadedfile import UploadedFile
from xlrd import open_workbook
from xml.dom import minidom, Node

from onadata.apps.logger.models import XForm
from onadata.apps.logger.models.xform import XFORM_TITLE_LENGTH
from onadata.apps.logger.xform_instance_parser import clean_and_parse_xml
from onadata.apps.main.models import MetaData
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models.data_dictionary import DataDictionary
from onadata.libs.utils.common_tags import MONGO_STRFTIME
from onadata.libs.utils.common_tools import get_response_content


uuid_regex = re.compile(
    r'(</instance>.*uuid[^//]+="\')([^\']+)(\'".*)', re.DOTALL)


class TestProcess(TestBase):
    loop_str = 'loop_over_transport_types_frequency'
    frequency_str = 'frequency_to_referral_facility'
    ambulance_key = '%s/ambulance/%s' % (loop_str, frequency_str)
    bicycle_key = '%s/bicycle/%s' % (loop_str, frequency_str)
    other_key = '%s/other/%s' % (loop_str, frequency_str)
    taxi_key = '%s/taxi/%s' % (loop_str, frequency_str)
    transport_ambulance_key = u'transport/%s' % ambulance_key
    transport_bicycle_key = u'transport/%s' % bicycle_key
    uuid_to_submission_times = {
        '5b2cc313-fc09-437e-8149-fcd32f695d41': '2013-02-14T15:37:21',
        'f3d8dc65-91a6-4d0f-9e97-802128083390': '2013-02-14T15:37:22',
        '9c6f3468-cfda-46e8-84c1-75458e72805d': '2013-02-14T15:37:23',
        '9f0a1508-c3b7-4c99-be00-9b237c26bcbf': '2013-02-14T15:37:24'
    }

    def setUp(self):
        super(TestProcess, self).setUp()

    def tearDown(self):
        super(TestProcess, self).tearDown()

    def test_process(self, username=None, password=None):
        self._publish_xls_file()
        self._check_formlist()
        self._download_xform()
        self._make_submissions()
        self._update_dynamic_data()
        self._check_csv_export()
        self._check_delete()

    def _update_dynamic_data(self):
        """
        Update stuff like submission time so we can compare within out fixtures
        """
        for (uuid, submission_time) in iteritems(
                self.uuid_to_submission_times):
            i = self.xform.instances.get(uuid=uuid)
            i.date_created = pytz.timezone('UTC').localize(
                datetime.strptime(submission_time, MONGO_STRFTIME))
            i.json = i.get_full_dict()
            i.save()

    def test_uuid_submit(self):
        self._publish_xls_file()
        survey = 'transport_2011-07-25_19-05-49'
        path = os.path.join(
            self.this_directory, 'fixtures', 'transportation',
            'instances', survey, survey + '.xml')
        with open(path) as f:
            post_data = {'xml_submission_file': f, 'uuid': self.xform.uuid}
            url = '/submission'
            self.response = self.client.post(url, post_data)

    def test_publish_xlsx_file(self):
        self._publish_xlsx_file()

    @patch('onadata.apps.main.forms.urlopen')
    def test_google_url_upload(self, mock_urlopen):
        if self._internet_on(url="http://google.com"):
            xls_url = "https://docs.google.com/spreadsheet/pub?"\
                "key=0AvhZpT7ZLAWmdDhISGhqSjBOSl9XdXd5SHZHUUE2RFE&output=xls"
            pre_count = XForm.objects.count()

            path = os.path.join(
                settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
                "transportation", "transportation.xls")

            xls_file = open(path, 'rb')
            mock_urlopen.return_value = xls_file

            response = self.client.post('/%s/' % self.user.username,
                                        {'xls_url': xls_url})

            mock_urlopen.assert_called_with(xls_url)
            # cleanup the resources
            xls_file.close()
            # make sure publishing the survey worked
            self.assertEqual(response.status_code, 200)
            self.assertEqual(XForm.objects.count(), pre_count + 1)

    @patch('onadata.apps.main.forms.urlopen')
    def test_url_upload(self, mock_urlopen):
        if self._internet_on(url="http://google.com"):
            xls_url = 'https://ona.io/examples/forms/tutorial/form.xls'
            pre_count = XForm.objects.count()

            path = os.path.join(
                settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
                "transportation", "transportation.xls")

            xls_file = open(path, 'rb')
            mock_urlopen.return_value = xls_file

            response = self.client.post('/%s/' % self.user.username,
                                        {'xls_url': xls_url})

            mock_urlopen.assert_called_with(xls_url)
            # cleanup the resources
            xls_file.close()

            # make sure publishing the survey worked
            self.assertEqual(response.status_code, 200)
            self.assertEqual(XForm.objects.count(), pre_count + 1)

    def test_bad_url_upload(self):
        xls_url = 'formhuborg/pld/forms/transportation_2011_07_25/form.xls'
        pre_count = XForm.objects.count()
        response = self.client.post('/%s/' % self.user.username,
                                    {'xls_url': xls_url})
        # make sure publishing the survey worked
        self.assertEqual(response.status_code, 200)
        self.assertEqual(XForm.objects.count(), pre_count)

    # This method tests a large number of xls files.
    # create a directory /main/test/fixtures/online_xls
    # containing the files you would like to test.
    # DO NOT CHECK IN PRIVATE XLS FILES!!
    def test_upload_all_xls(self):
        root_dir = os.path.join(self.this_directory, "fixtures", "online_xls")
        if os.path.exists(root_dir):
            success = True
            for root, sub_folders, filenames in os.walk(root_dir):
                # ignore files that don't end in '.xls'
                for filename in fnmatch.filter(filenames, '*.xls'):
                    success = self._publish_file(os.path.join(root, filename),
                                                 False)
                    if success:
                        # delete it so we don't have id_string conflicts
                        if self.xform:
                            self.xform.delete()
                            self.xform = None
                print('finished sub-folder %s' % root)
            self.assertEqual(success, True)

    def test_url_upload_non_dot_xls_path(self):
        if self._internet_on():
            xls_url = 'http://formhub.org/formhub_u/forms/tutorial/form.xls'
            pre_count = XForm.objects.count()
            response = self.client.post('/%s/' % self.user.username,
                                        {'xls_url': xls_url})
            # make sure publishing the survey worked
            self.assertEqual(response.status_code, 200)
            self.assertEqual(XForm.objects.count(), pre_count + 1)

    def test_not_logged_in_cannot_upload(self):
        path = os.path.join(self.this_directory, "fixtures", "transportation",
                            "transportation.xls")
        if not path.startswith('/%s/' % self.user.username):
            path = os.path.join(self.this_directory, path)
        with open(path, 'rb') as xls_file:
            post_data = {'xls_file': xls_file}
            return self.client.post('/%s/' % self.user.username, post_data)

    def _publish_file(self, xls_path, strict=True):
        """
        Return False if not strict and publish fails
        """
        pre_count = XForm.objects.count()
        TestBase._publish_xls_file(self, xls_path)
        # make sure publishing the survey worked
        if XForm.objects.count() != pre_count + 1:
            print('\nPublish Failure for file: %s' % xls_path)
            if strict:
                self.assertEqual(XForm.objects.count(), pre_count + 1)
            else:
                return False
        self.xform = list(XForm.objects.all())[-1]
        return True

    def _publish_xls_file(self):
        xls_path = os.path.join(self.this_directory, "fixtures",
                                "transportation", "transportation.xls")
        self._publish_file(xls_path)
        self.assertEqual(self.xform.id_string, "transportation_2011_07_25")

    def _check_formlist(self):
        url = '/%s/formList' % self.user.username
        client = DigestClient()
        client.set_authorization('bob', 'bob')
        response = client.get(url)
        self.download_url = \
            'http://testserver/%s/forms/%s/form.xml'\
            % (self.user.username, self.xform.pk)
        md5_hash = md5(self.xform.xml.encode('utf-8')).hexdigest()
        expected_content = """<?xml version="1.0" encoding="utf-8"?>
<xforms xmlns="http://openrosa.org/xforms/xformsList"><xform><formID>transportation_2011_07_25</formID><name>transportation_2011_07_25</name><version>2014111</version><hash>md5:%(hash)s</hash><descriptionText></descriptionText><downloadUrl>%(download_url)s</downloadUrl><manifestUrl></manifestUrl></xform></xforms>"""  # noqa
        expected_content = expected_content % {
            'download_url': self.download_url,
            'hash': md5_hash
        }
        self.assertEqual(response.content.decode('utf-8'), expected_content)
        self.assertTrue(response.has_header('X-OpenRosa-Version'))
        self.assertTrue(response.has_header('Date'))

    def _download_xform(self):
        client = DigestClient()
        client.set_authorization('bob', 'bob')
        response = client.get(self.download_url)
        response_doc = minidom.parseString(response.content)

        xml_path = os.path.join(self.this_directory, "fixtures",
                                "transportation", "transportation.xml")
        with open(xml_path, 'rb') as xml_file:
            expected_doc = minidom.parse(xml_file)

        model_node = [
            n for n in
            response_doc.getElementsByTagName("h:head")[0].childNodes
            if n.nodeType == Node.ELEMENT_NODE and
            n.tagName == "model"][0]

        # check for UUID and remove
        uuid_nodes = [node for node in model_node.childNodes
                      if node.nodeType == Node.ELEMENT_NODE and
                      node.getAttribute("nodeset") ==
                      "/transportation/formhub/uuid"]
        self.assertEqual(len(uuid_nodes), 1)
        uuid_node = uuid_nodes[0]
        uuid_node.setAttribute("calculate", "''")

        response_xml = response_doc.toxml().replace(
            self.xform.version, u"201411120717")
        # check content without UUID
        self.assertEqual(response_xml, expected_doc.toxml())

    def _check_csv_export(self):
        self._check_data_dictionary()
        self._check_data_for_csv_export()
        self._check_group_xpaths_do_not_appear_in_dicts_for_export()
        self._check_csv_export_first_pass()
        self._check_csv_export_second_pass()

    def _check_data_dictionary(self):
        # test to make sure the data dictionary returns the expected headers
        qs = DataDictionary.objects.filter(user=self.user)
        self.assertEqual(qs.count(), 1)
        self.data_dictionary = DataDictionary.objects.all()[0]
        with open(os.path.join(self.this_directory, "fixtures",
                               "transportation", "headers.json")) as f:
            expected_list = json.load(f)
        self.assertEqual(self.data_dictionary.get_headers(), expected_list)

        # test to make sure the headers in the actual csv are as expected
        actual_csv = self._get_csv_()
        self.assertEqual(sorted(next(actual_csv)), sorted(expected_list))

    def _check_data_for_csv_export(self):

        data = [
            {"available_transportation_types_to_referral_facility/ambulance":
             True,
             "available_transportation_types_to_referral_facility/bicycle":
                True,
             self.ambulance_key: "daily",
             self.bicycle_key: "weekly"
             },
            {},
            {"available_transportation_types_to_referral_facility/ambulance":
             True,
             self.ambulance_key: "weekly",
             },
            {"available_transportation_types_to_referral_facility/taxi": True,
             "available_transportation_types_to_referral_facility/other": True,
             "available_transportation_types_to_referral_facility_other":
             "camel",
             self.taxi_key: "daily",
             self.other_key: "other",
             }
        ]
        for d_from_db in self.data_dictionary.get_data_for_excel():
            test_dict = {}
            for (k, v) in iteritems(d_from_db):
                if (k not in [u'_xform_id_string', u'meta/instanceID',
                              '_version', '_id', 'image1']) and v:
                    new_key = k[len('transport/'):]
                    test_dict[new_key] = d_from_db[k]
            self.assertTrue(test_dict in data, (test_dict, data))
            data.remove(test_dict)
        self.assertEquals(data, [])

    def _check_group_xpaths_do_not_appear_in_dicts_for_export(self):
        uuid = u'uuid:f3d8dc65-91a6-4d0f-9e97-802128083390'
        instance = self.xform.instances.get(uuid=uuid.split(':')[1])
        expected_dict = {
            u"transportation": {
                u"meta": {
                    u"instanceID": uuid
                },
                u"transport": {
                    u"loop_over_transport_types_frequency": {u"bicycle": {
                        u"frequency_to_referral_facility": u"weekly"
                    },
                        u"ambulance": {
                            u"frequency_to_referral_facility": u"daily"
                    }
                    },
                    u"available_transportation_types_to_referral_facility":
                    u"ambulance bicycle",
                }
            }
        }
        self.assertEqual(instance.get_dict(flat=False), expected_dict)
        expected_dict = {
            u"transport/available_transportation_types_to_referral_facility":
            u"ambulance bicycle",
            self.transport_ambulance_key: u"daily",
            self.transport_bicycle_key: u"weekly",
            u"_xform_id_string": u"transportation_2011_07_25",
            u"_version": u"2014111",
            u"meta/instanceID": uuid
        }
        self.assertEqual(instance.get_dict(), expected_dict)

    def _get_csv_(self):
        # todo: get the csv.reader to handle unicode as done here:
        # http://docs.python.org/library/csv.html#examples
        url = reverse('csv_export', kwargs={
            'username': self.user.username, 'id_string': self.xform.id_string})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        actual_csv = get_response_content(response)
        actual_lines = actual_csv.split("\n")
        return csv.reader(actual_lines)

    def _check_csv_export_first_pass(self):
        url = reverse('csv_export', kwargs={
            'username': self.user.username, 'id_string': self.xform.id_string})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        test_file_path = os.path.join(
            self.this_directory, "fixtures",
            "transportation", "transportation.csv")
        self._test_csv_response(response, test_file_path)

    def _check_csv_export_second_pass(self):
        url = reverse('csv_export', kwargs={
            'username': self.user.username, 'id_string': self.xform.id_string})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        actual_csv = get_response_content(response)
        actual_lines = actual_csv.split("\n")
        actual_csv = csv.reader(actual_lines)
        headers = next(actual_csv)
        data = [
            {"image1": "1335783522563.jpg",
             'meta/instanceID': 'uuid:5b2cc313-fc09-437e-8149-fcd32f695d41',
             '_uuid': '5b2cc313-fc09-437e-8149-fcd32f695d41',
             '_submission_time': '2013-02-14T15:37:21',
             '_tags': '', '_notes': '', '_version': '2014111', '_duration': '',
             '_submitted_by': 'bob', '_total_media': '1', '_media_count': '0',
             },
            {"available_transportation_types_to_referral_facility/ambulance":
             "True",
             "available_transportation_types_to_referral_facility/bicycle":
             "True",
             self.ambulance_key: "daily",
             self.bicycle_key: "weekly",
             "meta/instanceID": "uuid:f3d8dc65-91a6-4d0f-9e97-802128083390",
             '_uuid': 'f3d8dc65-91a6-4d0f-9e97-802128083390',
             '_submission_time': '2013-02-14T15:37:22',
             '_tags': '', '_notes': '', '_version': '2014111', '_duration': '',
             '_submitted_by': 'bob', '_total_media': '0', '_media_count': '0',
             '_media_all_received': 'True'
             },
            {"available_transportation_types_to_referral_facility/ambulance":
             "True",
             self.ambulance_key: "weekly",
             "meta/instanceID": "uuid:9c6f3468-cfda-46e8-84c1-75458e72805d",
             '_uuid': '9c6f3468-cfda-46e8-84c1-75458e72805d',
             '_submission_time': '2013-02-14T15:37:23',
             '_tags': '', '_notes': '', '_version': '2014111', '_duration': '',
             '_submitted_by': 'bob', '_total_media': '0', '_media_count': '0',
             '_media_all_received': 'True'
             },
            {"available_transportation_types_to_referral_facility/taxi":
             "True",
             "available_transportation_types_to_referral_facility/other":
             "True",
             "available_transportation_types_to_referral_facility_other":
             "camel",
             self.taxi_key: "daily",
             "meta/instanceID": "uuid:9f0a1508-c3b7-4c99-be00-9b237c26bcbf",
             '_uuid': '9f0a1508-c3b7-4c99-be00-9b237c26bcbf',
             '_submission_time': '2013-02-14T15:37:24',
             '_tags': '', '_notes': '', '_version': '2014111', '_duration': '',
             '_submitted_by': 'bob', '_total_media': '0', '_media_count': '0',
             '_media_all_received': 'True'
             }
        ]

        dd = DataDictionary.objects.get(pk=self.xform.pk)
        additional_headers = dd._additional_headers() + ['_id']
        for row, expected_dict in zip(actual_csv, data):
            test_dict = {}
            d = dict(zip(headers, row))
            for (k, v) in iteritems(d):
                if not (v in ["n/a", "False"] or k in additional_headers):
                    test_dict[k] = v
            this_list = []
            for k, v in expected_dict.items():
                if k in ['image1', 'meta/instanceID'] or k.startswith("_"):
                    this_list.append((k, v))
                else:
                    this_list.append(("transport/" + k, v))
            self.assertEqual(test_dict, dict(this_list))

    def test_xls_export_content(self):
        self._publish_xls_file()
        self._make_submissions()
        self._update_dynamic_data()
        self._check_xls_export()

    def _check_xls_export(self):
        xls_export_url = reverse(
            'xls_export', kwargs={'username': self.user.username,
                                  'id_string': self.xform.id_string})
        response = self.client.get(xls_export_url)
        expected_xls = open_workbook(os.path.join(
            self.this_directory, "fixtures", "transportation",
            "transportation_export.xls"))
        content = get_response_content(response, decode=False)
        actual_xls = open_workbook(file_contents=content)
        actual_sheet = actual_xls.sheet_by_index(0)
        expected_sheet = expected_xls.sheet_by_index(0)

        # check headers
        self.assertEqual(actual_sheet.row_values(0),
                         expected_sheet.row_values(0))

        # check cell data
        self.assertEqual(actual_sheet.ncols, expected_sheet.ncols)
        self.assertEqual(actual_sheet.nrows, expected_sheet.nrows)
        for i in range(1, actual_sheet.nrows):
            actual_row = actual_sheet.row_values(i)
            expected_row = expected_sheet.row_values(i)

            # remove _id from result set, varies depending on the database
            del actual_row[23]
            del expected_row[23]
            self.assertEqual(actual_row, expected_row)

    def _check_delete(self):
        self.assertEquals(self.user.xforms.count(), 1)
        self.user.xforms.all()[0].delete()
        self.assertEquals(self.user.xforms.count(), 0)

    def test_405_submission(self):
        url = reverse('submissions')
        response = self.client.get(url)
        self.assertContains(
            response, 'Method "GET" not allowed', status_code=405)

    def test_publish_bad_xls_with_unicode_in_error(self):
        """
        Publish an xls where the error has a unicode character

        Return a 200, thus showing a readable error to the user
        """
        self._create_user_and_login()
        path = os.path.join(
            self.this_directory, 'fixtures',
            'form_with_unicode_in_relevant_column.xlsx')
        with open(path, 'rb') as xls_file:
            post_data = {'xls_file': xls_file}
            response = self.client.post('/%s/' % self.user.username, post_data)
            self.assertEqual(response.status_code, 200)

    def test_metadata_file_hash(self):
        self._publish_transportation_form()
        src = os.path.join(self.this_directory, "fixtures",
                           "transportation", "screenshot.png")
        uf = UploadedFile(file=open(src, 'rb'), content_type='image/png')
        count = MetaData.objects.count()
        MetaData.media_upload(self.xform, uf)
        # assert successful insert of new metadata record
        self.assertEqual(MetaData.objects.count(), count + 1)
        md = MetaData.objects.get(object_id=self.xform.id,
                                  data_value='screenshot.png')
        # assert checksum string has been generated, hash length > 1
        self.assertTrue(len(md.hash) > 16)

    def test_uuid_injection_in_cascading_select(self):
        """
        Uuid is injected in the right instance for forms with cascading select
        """
        pre_count = XForm.objects.count()
        xls_path = os.path.join(
            self.this_directory, "fixtures", "cascading_selects",
            "new_cascading_select.xls")
        file_name, file_ext = os.path.splitext(os.path.split(xls_path)[1])
        TestBase._publish_xls_file(self, xls_path)
        post_count = XForm.objects.count()
        self.assertEqual(post_count, pre_count + 1)
        xform = XForm.objects.latest('date_created')

        # check that the uuid is within the main instance/
        # the one without an id attribute
        xml = clean_and_parse_xml(xform.xml)

        # check for instance nodes that are direct children of the model node
        model_node = xml.getElementsByTagName("model")[0]
        instance_nodes = [node for node in model_node.childNodes if
                          node.nodeType == Node.ELEMENT_NODE and
                          node.tagName.lower() == "instance" and
                          not node.hasAttribute("id")]
        self.assertEqual(len(instance_nodes), 1)
        instance_node = instance_nodes[0]

        # get the first element whose id attribute is equal to our form's
        # id_string
        form_nodes = [node for node in instance_node.childNodes if
                      node.nodeType == Node.ELEMENT_NODE and
                      node.getAttribute("id") == xform.id_string]
        form_node = form_nodes[0]

        # find the formhub node that has a uuid child node
        formhub_nodes = form_node.getElementsByTagName("formhub")
        self.assertEqual(len(formhub_nodes), 1)
        uuid_nodes = formhub_nodes[0].getElementsByTagName("uuid")
        self.assertEqual(len(uuid_nodes), 1)

        # check for the calculate bind
        calculate_bind_nodes = [node for node in model_node.childNodes if
                                node.nodeType == Node.ELEMENT_NODE and
                                node.tagName == "bind" and
                                node.getAttribute("nodeset") ==
                                "/%s/formhub/uuid" % file_name]
        self.assertEqual(len(calculate_bind_nodes), 1)
        calculate_bind_node = calculate_bind_nodes[0]
        self.assertEqual(
            calculate_bind_node.getAttribute("calculate"), "'%s'" % xform.uuid)

    def test_csv_publishing(self):
        csv_text = '\n'.join([
            'survey,,', ',type,name,label',
            ',text,whatsyourname,"What is your name?"', 'choices,,'])
        url = reverse('user_profile',
                      kwargs={'username': self.user.username})
        num_xforms = XForm.objects.count()
        params = {
            'text_xls_form': csv_text
        }
        self.response = self.client.post(url, params)
        self.assertEqual(XForm.objects.count(), num_xforms + 1)

    def test_truncate_xform_title_to_255(self):
        self._publish_transportation_form()
        title = "a" * (XFORM_TITLE_LENGTH + 1)
        groups = re.match(
            r"(.+<h:title>)([^<]+)(</h:title>.*)",
            self.xform.xml, re.DOTALL).groups()
        self.xform.xml = "{0}{1}{2}".format(
            groups[0], title, groups[2])
        self.xform.title = title
        self.xform.save()
        self.assertEqual(self.xform.title, "a" * XFORM_TITLE_LENGTH)

    def test_multiple_submissions_by_different_users(self):
        """
        Two users publishing the same form breaks the CSV export.
        """
        TestProcess.test_process(self)
        TestProcess.test_process(self, "doug", "doug")
