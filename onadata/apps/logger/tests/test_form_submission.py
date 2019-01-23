import os
import re

from contextlib import contextmanager
from django.http import Http404
from django.http import UnreadablePostError
from django_digest.test import DigestAuth
from django_digest.test import Client as DigestClient
from guardian.shortcuts import assign_perm
from mock import patch, Mock, ANY
from nose import SkipTest

from onadata.apps.main.models.user_profile import UserProfile
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import Instance
from onadata.apps.logger.models.instance import InstanceHistory
from onadata.apps.logger.models.project import Project
from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.xform_instance_parser import clean_and_parse_xml
from onadata.apps.viewer.models.parsed_instance import query_data
from onadata.apps.viewer.signals import process_submission
from onadata.libs.utils.common_tags import GEOLOCATION, LAST_EDITED


# NOQA https://medium.freecodecamp.org/how-to-testing-django-signals-like-a-pro-c7ed74279311
@contextmanager
def catch_signal(signal):
    handler = Mock()
    signal.connect(handler)
    yield handler
    signal.disconnect(handler)


class TestFormSubmission(TestBase):
    """
    Testing POSTs to "/submission"
    """

    def setUp(self):
        TestBase.setUp(self)
        xls_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/tutorial.xls"
        )
        self._publish_xls_file_and_set_xform(xls_file_path)

    def test_form_post(self):
        """
        xml_submission_file is the field name for the posted xml file.
        """
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/instances/tutorial_2012-06-27_11-27-53.xml"
        )

        self._make_submission(xml_submission_file_path)
        self.assertEqual(self.response.status_code, 201)

    def test_duplicate_form_id(self):
        """
        Should return an error if submitting to a form with a duplicate ID.
        """
        project = Project.objects.create(name="another project",
                                              organization=self.user,
                                              created_by=self.user)
        first_xform = XForm.objects.first()
        first_xform.pk = None
        first_xform.project = project
        first_xform.save()

        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/instances/tutorial_2012-06-27_11-27-53.xml"
        )

        self._make_submission(xml_submission_file_path)
        self.assertEqual(self.response.status_code, 400)
        self.assertTrue(
            "Unable to submit because there are multiple forms with this form"
            in self.response.content.decode('utf-8'))

    @patch('django.utils.datastructures.MultiValueDict.pop')
    def test_fail_with_ioerror_read(self, mock_pop):
        mock_pop.side_effect = IOError(
            'request data read error')

        self.assertEquals(0, self.xform.instances.count())

        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/instances/tutorial_2012-06-27_11-27-53.xml"
        )
        self._make_submission(xml_submission_file_path)
        self.assertEqual(self.response.status_code, 400)

        self.assertEquals(0, self.xform.instances.count())

    @patch('django.utils.datastructures.MultiValueDict.pop')
    def test_fail_with_ioerror_wsgi(self, mock_pop):
        mock_pop.side_effect = IOError(
            'error during read(65536) on wsgi.input')

        self.assertEquals(0, self.xform.instances.count())

        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/instances/tutorial_2012-06-27_11-27-53.xml"
        )
        self._make_submission(xml_submission_file_path)
        self.assertEqual(self.response.status_code, 400)

        self.assertEquals(0, self.xform.instances.count())

    def test_submission_to_require_auth_anon(self):
        """
        Test submission to private form by non-owner without perm is forbidden
        """
        self.xform.require_auth = True
        self.xform.save()
        self.xform.refresh_from_db()
        self.assertTrue(self.xform.require_auth)

        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/instances/tutorial_2012-06-27_11-27-53.xml"
        )

        # create a new user
        username = 'alice'
        self._create_user(username, username)

        self._make_submission(xml_submission_file_path,
                              auth=DigestAuth('alice', 'alice'))
        self.assertEqual(self.response.status_code, 403)

    def test_submission_to_require_auth_without_perm(self):
        """
        Test submission to private form by non-owner without perm is forbidden
        """
        self.xform.require_auth = True
        self.xform.save()
        self.xform.refresh_from_db()
        self.assertTrue(self.xform.require_auth)

        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/instances/tutorial_2012-06-27_11-27-53.xml"
        )

        # create a new user
        username = 'alice'
        self._create_user(username, username)

        self._make_submission(xml_submission_file_path,
                              auth=DigestAuth('alice', 'alice'))

        self.assertEqual(self.response.status_code, 403)

    def test_submission_to_require_auth_with_perm(self):
        """
        Test submission to a private form by non-owner is forbidden.

        TODO send authentication challenge when xform.require_auth is set.
        This is non-trivial because we do not know the xform until we have
        parsed the XML.
        """
        raise SkipTest

        self.xform.require_auth = True
        self.xform.save()
        self.xform.refresh_from_db()
        self.assertTrue(self.xform.require_auth)

        # create a new user
        username = 'alice'
        alice = self._create_user(username, username)

        # assign report perms to user
        assign_perm('report_xform', alice, self.xform)
        auth = DigestAuth(username, username)

        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/instances/tutorial_2012-06-27_11-27-53.xml"
        )
        self._make_submission(xml_submission_file_path, auth=auth)
        self.assertEqual(self.response.status_code, 201)

    def test_form_post_to_missing_form(self):
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/instances/"
            "tutorial_invalid_id_string_2012-06-27_11-27-53.xml"
        )
        with self.assertRaises(Http404):
            self._make_submission(path=xml_submission_file_path)

    def test_duplicate_submissions(self):
        """
        Test submissions for forms with start and end
        """
        xls_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/test_forms/survey_names/survey_names.xls"
        )
        self._publish_xls_file(xls_file_path)
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/test_forms/survey_names/instances/"
            "survey_names_2012-08-17_11-24-53.xml"
        )

        self._make_submission(xml_submission_file_path)
        self.assertEqual(self.response.status_code, 201)
        self._make_submission(xml_submission_file_path)
        self.assertEqual(self.response.status_code, 202)

    def test_unicode_submission(self):
        """Test xml submissions that contain unicode characters
        """
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_unicode_submission.xml"
        )
        self.user.profile.require_auth = True
        self.user.profile.save()

        # create a new user
        alice = self._create_user('alice', 'alice')

        # assign report perms to user
        assign_perm('report_xform', alice, self.xform)
        client = DigestClient()
        client.set_authorization('alice', 'alice', 'Digest')

        self._make_submission(xml_submission_file_path)
        self.assertEqual(self.response.status_code, 201)

    def test_duplicate_submission_with_same_instanceid(self):
        """Test duplicate xml submissions
        """
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid.xml"
        )

        self._make_submission(xml_submission_file_path)
        self.assertEqual(self.response.status_code, 201)
        self._make_submission(xml_submission_file_path)
        self.assertEqual(self.response.status_code, 202)

    def test_duplicate_submission_with_different_content(self):
        """Test xml submissions with same instancID but different content
        """
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid.xml"
        )
        duplicate_xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid_same_instanceID.xml"
        )

        pre_count = Instance.objects.count()
        self._make_submission(xml_submission_file_path)
        self.assertEqual(self.response.status_code, 201)
        self.assertEqual(Instance.objects.count(), pre_count + 1)
        inst = Instance.objects.all().reverse()[0]
        self._make_submission(duplicate_xml_submission_file_path)
        self.assertEqual(self.response.status_code, 202)
        self.assertEqual(Instance.objects.count(), pre_count + 1)
        # this is exactly the same instance
        anothe_inst = Instance.objects.all().reverse()[0]
        # no change in xml content
        self.assertEqual(inst.xml, anothe_inst.xml)

    # @patch('onadata.apps.viewer.signals.process_submission')
    def test_edited_submission(self):
        """
        Test submissions that have been edited
        """

        # Delete all previous instance history objects
        InstanceHistory.objects.all().delete()

        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid.xml"
        )
        num_instances_history = InstanceHistory.objects.count()
        num_instances = Instance.objects.count()
        query_args = {
            'xform': self.xform,
            'query': '{}',
            'fields': '[]',
            'count': True
        }

        cursor = [r for r in query_data(**query_args)]
        num_data_instances = cursor[0]['count']
        # make first submission
        self._make_submission(xml_submission_file_path)
        self.assertEqual(self.response.status_code, 201)
        self.assertEqual(Instance.objects.count(), num_instances + 1)

        # Take initial instance from DB
        initial_instance = self.xform.instances.first()

        # check that '_last_edited' key is not in the json
        self.assertIsNone(initial_instance.json.get(LAST_EDITED))

        # no new record in instances history
        self.assertEqual(
            InstanceHistory.objects.count(), num_instances_history)
        # check count of mongo instances after first submission
        cursor = query_data(**query_args)
        self.assertEqual(cursor[0]['count'], num_data_instances + 1)
        # edited submission
        xml_edit_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid_edited.xml"
        )
        client = DigestClient()
        client.set_authorization('bob', 'bob', 'Digest')
        with catch_signal(process_submission) as handler:
            self._make_submission(xml_edit_submission_file_path, client=client)
        self.assertEqual(self.response.status_code, 201)
        # we must have the same number of instances
        self.assertEqual(Instance.objects.count(), num_instances + 1)
        # should be a new record in instances history
        self.assertEqual(
            InstanceHistory.objects.count(), num_instances_history + 1)

        instance_history_1 = InstanceHistory.objects.first()
        edited_instance = self.xform.instances.first()

        self.assertDictEqual(initial_instance.get_dict(),
                             instance_history_1.get_dict())
        handler.assert_called_once_with(instance=edited_instance,
                                        sender=Instance, signal=ANY)

        self.assertNotEqual(edited_instance.uuid, instance_history_1.uuid)

        # check that instance history's submission_date is equal to instance's
        # date_created - last_edited by default is null for an instance
        self.assertEquals(edited_instance.date_created,
                          instance_history_1.submission_date)
        # check that '_last_edited' key is not in the json
        self.assertIn(LAST_EDITED, edited_instance.json)

        cursor = query_data(**query_args)
        self.assertEqual(cursor[0]['count'], num_data_instances + 1)
        # make sure we edited the mongo db record and NOT added a new row
        query_args['count'] = False
        cursor = query_data(**query_args)
        record = cursor[0]
        with open(xml_edit_submission_file_path, "r") as f:
            xml_str = f.read()
        xml_str = clean_and_parse_xml(xml_str).toxml()
        edited_name = re.match(r"^.+?<name>(.+?)</name>", xml_str).groups()[0]
        self.assertEqual(record['name'], edited_name)
        instance_before_second_edit = edited_instance
        xml_edit_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid_edited_again.xml"
        )
        self._make_submission(xml_edit_submission_file_path)
        cursor = query_data(**query_args)
        record = cursor[0]
        edited_instance = self.xform.instances.first()
        instance_history_2 = InstanceHistory.objects.last()
        self.assertEquals(instance_before_second_edit.last_edited,
                          instance_history_2.submission_date)
        # check that '_last_edited' key is not in the json
        self.assertIn(LAST_EDITED, edited_instance.json)
        self.assertEqual(record['name'], 'Tom and Jerry')
        self.assertEqual(
            InstanceHistory.objects.count(), num_instances_history + 2)
        # submitting original submission is treated as a duplicate
        # does not add a new record
        # does not change data
        self._make_submission(xml_submission_file_path)
        self.assertEqual(self.response.status_code, 202)
        self.assertEqual(Instance.objects.count(), num_instances + 1)
        self.assertEqual(
            InstanceHistory.objects.count(), num_instances_history + 2)

    def test_submission_w_mismatched_uuid(self):
        """
        test allowing submissions where xml's form uuid doesnt match
        any form's uuid for a user, as long as id_string can be matched
        """
        # submit instance with uuid that would not match the forms
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_w_xform_uuid.xml"
        )

        self._make_submission(xml_submission_file_path)
        self.assertEqual(self.response.status_code, 201)

    def _test_fail_submission_if_no_username(self):
        """
        Test that a submission fails if no username is provided
        and the UUIDs don't match.
        """
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_w_xform_uuid.xml"
        )
        with self.assertRaises(Http404):
            self._make_submission(path=xml_submission_file_path, username='')

    def test_fail_submission_if_bad_id_string(self):
        """Test that a submission fails if the uuid's don't match.
        """
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_bad_id_string.xml"
        )
        with self.assertRaises(Http404):
            self._make_submission(path=xml_submission_file_path)

    def test_edit_updated_geopoint_cache(self):
        query_args = {
            'xform': self.xform,
            'query': '{}',
            'fields': '[]',
            'count': True
        }
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid.xml"
        )

        self._make_submission(xml_submission_file_path)
        self.assertEqual(self.response.status_code, 201)
        # query mongo for the _geopoint field
        query_args['count'] = False
        records = query_data(**query_args)
        self.assertEqual(len(records), 1)
        # submit the edited instance
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid_edited.xml"
        )
        self._make_submission(xml_submission_file_path)
        self.assertEqual(self.response.status_code, 201)
        records = query_data(**query_args)
        self.assertEqual(len(records), 1)
        cached_geopoint = records[0][GEOLOCATION]
        # the cached geopoint should equal the gps field
        gps = records[0]['gps'].split(" ")
        self.assertEqual(float(gps[0]), float(cached_geopoint[0]))
        self.assertEqual(float(gps[1]), float(cached_geopoint[1]))

    def test_submission_when_requires_auth(self):
        self.user.profile.require_auth = True
        self.user.profile.save()

        # create a new user
        alice = self._create_user('alice', 'alice')

        # assign report perms to user
        assign_perm('report_xform', alice, self.xform)

        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/instances/tutorial_2012-06-27_11-27-53.xml"
        )
        auth = DigestAuth('alice', 'alice')
        self._make_submission(
            xml_submission_file_path, auth=auth)
        self.assertEqual(self.response.status_code, 201)

    def test_submission_linked_to_reporter(self):
        self.user.profile.require_auth = True
        self.user.profile.save()

        # create a new user
        alice = self._create_user('alice', 'alice')
        UserProfile.objects.create(user=alice)

        # assign report perms to user
        assign_perm('report_xform', alice, self.xform)

        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/instances/tutorial_2012-06-27_11-27-53.xml"
        )
        auth = DigestAuth('alice', 'alice')
        self._make_submission(
            xml_submission_file_path, auth=auth)
        self.assertEqual(self.response.status_code, 201)
        instance = Instance.objects.all().reverse()[0]
        self.assertEqual(instance.user, alice)

    def test_edited_submission_require_auth(self):
        """
        Test submissions that have been edited
        """
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid.xml"
        )
        # require authentication
        self.user.profile.require_auth = True
        self.user.profile.save()

        num_instances_history = InstanceHistory.objects.count()
        num_instances = Instance.objects.count()
        query_args = {
            'xform': self.xform,
            'query': '{}',
            'fields': '[]',
            'count': True
        }
        cursor = query_data(**query_args)
        num_data_instances = cursor[0]['count']
        # make first submission
        self._make_submission(xml_submission_file_path)

        self.assertEqual(self.response.status_code, 201)
        self.assertEqual(Instance.objects.count(), num_instances + 1)
        # no new record in instances history
        self.assertEqual(
            InstanceHistory.objects.count(), num_instances_history)
        # check count of mongo instances after first submission
        cursor = query_data(**query_args)
        self.assertEqual(cursor[0]['count'], num_data_instances + 1)

        # create a new user
        alice = self._create_user('alice', 'alice')
        UserProfile.objects.create(user=alice)
        auth = DigestAuth('alice', 'alice')

        # edited submission
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid_edited.xml"
        )
        self._make_submission(xml_submission_file_path, auth=auth)
        self.assertEqual(self.response.status_code, 403)

        # assign report perms to user
        assign_perm('report_xform', alice, self.xform)
        assign_perm('logger.change_xform', alice, self.xform)

        self._make_submission(xml_submission_file_path, auth=auth)
        self.assertEqual(self.response.status_code, 201)
        # we must have the same number of instances
        self.assertEqual(Instance.objects.count(), num_instances + 1)
        # should be a new record in instances history
        self.assertEqual(
            InstanceHistory.objects.count(), num_instances_history + 1)
        cursor = query_data(**query_args)
        self.assertEqual(cursor[0]['count'], num_data_instances + 1)
        # make sure we edited the mongo db record and NOT added a new row
        query_args['count'] = False
        cursor = query_data(**query_args)
        record = cursor[0]
        with open(xml_submission_file_path, "r") as f:
            xml_str = f.read()
        xml_str = clean_and_parse_xml(xml_str).toxml()
        edited_name = re.match(r"^.+?<name>(.+?)</name>", xml_str).groups()[0]
        self.assertEqual(record['name'], edited_name)

    @patch('onadata.libs.utils.logger_tools.create_instance')
    def test_fail_with_unreadable_post_error(self, mock_create_instance):
        """Test UnreadablePostError is handled on form data submission"""
        mock_create_instance.side_effect = UnreadablePostError(
            'error during read(65536) on wsgi.input'
        )

        self.assertEquals(0, self.xform.instances.count())

        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/instances/tutorial_2012-06-27_11-27-53.xml"
        )
        self._make_submission(xml_submission_file_path)
        self.assertEqual(self.response.status_code, 400)

        self.assertEquals(0, self.xform.instances.count())

    def test_form_submission_with_infinity_values(self):
        """
        When using a calculate field in XLSForm the result may be an infinity
        value which would not be valid for a Postgres json field.
        This would result in a DataError exception being thrown by
        Django. Postgres Error would be `Invalid Token Infinity`

        This test confirms that we are handling such cases and they do not
        result in  500 response codes.
        """
        xls_file_path = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), "../tests/fixtures/infinity.xls"
        )
        self._publish_xls_file_and_set_xform(xls_file_path)
        xml_submission_file_path = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), "../tests/fixtures/infinity.xml"
        )

        self._make_submission(path=xml_submission_file_path)
        self.assertEquals(400, self.response.status_code)
        self.assertIn(
            'invalid input syntax for type json', str(self.response.message))
