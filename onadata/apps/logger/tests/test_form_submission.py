import os
import re

from django.http import Http404
from django_digest.test import DigestAuth
from django_digest.test import Client as DigestClient
from guardian.shortcuts import assign_perm
from mock import patch
from nose import SkipTest

from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.main.models.user_profile import UserProfile
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import Instance
from onadata.apps.logger.models.instance import InstanceHistory
from onadata.apps.logger.xform_instance_parser import clean_and_parse_xml
from onadata.apps.viewer.models.parsed_instance import ParsedInstance
from onadata.libs.utils.common_tags import GEOLOCATION


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
        test submission to a private form by non-owner without perm is
        forbidden.
        """
        view = XFormViewSet.as_view({
            'patch': 'partial_update'
        })
        data = {'require_auth': True}
        self.assertFalse(self.xform.require_auth)
        request = self.factory.patch('/', data=data, **{
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token})
        view(request, pk=self.xform.id)
        self.xform.reload()
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
        test submission to a private form by non-owner without perm is
        forbidden.
        """
        view = XFormViewSet.as_view({
            'patch': 'partial_update'
        })
        data = {'require_auth': True}
        self.assertFalse(self.xform.require_auth)
        request = self.factory.patch('/', data=data, **{
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token})
        view(request, pk=self.xform.id)
        self.xform.reload()
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
        test submission to a private form by non-owner is forbidden.

        TODO send authentication challenge when xform.require_auth is set.
        This is non-trivial because we do not know the xform until we have
        parsed the XML.
        """
        raise SkipTest

        view = XFormViewSet.as_view({
            'patch': 'partial_update'
        })
        data = {'require_auth': True}
        self.assertFalse(self.xform.require_auth)
        request = self.factory.patch('/', data=data, **{
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token})
        view(request, pk=self.xform.id)
        self.xform.reload()
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

    def test_duplicate_submission_with_same_instanceID(self):
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

    def test_edited_submission(self):
        """
        Test submissions that have been edited
        """
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid.xml"
        )
        num_instances_history = InstanceHistory.objects.count()
        num_instances = Instance.objects.count()
        query_args = {
            'username': self.user.username,
            'id_string': self.xform.id_string,
            'query': '{}',
            'fields': '[]',
            'sort': '[]',
            'count': True
        }

        cursor = ParsedInstance.query_mongo(**query_args)
        num_mongo_instances = cursor[0]['count']
        # make first submission
        self._make_submission(xml_submission_file_path)
        self.assertEqual(self.response.status_code, 201)
        self.assertEqual(Instance.objects.count(), num_instances + 1)
        # no new record in instances history
        self.assertEqual(
            InstanceHistory.objects.count(), num_instances_history)
        # check count of mongo instances after first submission
        cursor = ParsedInstance.query_mongo(**query_args)
        self.assertEqual(cursor[0]['count'], num_mongo_instances + 1)
        # edited submission
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid_edited.xml"
        )
        client = DigestClient()
        client.set_authorization('bob', 'bob', 'Digest')
        self._make_submission(xml_submission_file_path, client=client)
        self.assertEqual(self.response.status_code, 201)
        # we must have the same number of instances
        self.assertEqual(Instance.objects.count(), num_instances + 1)
        # should be a new record in instances history
        self.assertEqual(
            InstanceHistory.objects.count(), num_instances_history + 1)
        cursor = ParsedInstance.query_mongo(**query_args)
        self.assertEqual(cursor[0]['count'], num_mongo_instances + 1)
        # make sure we edited the mongo db record and NOT added a new row
        query_args['count'] = False
        cursor = ParsedInstance.query_mongo(**query_args)
        record = cursor[0]
        with open(xml_submission_file_path, "r") as f:
            xml_str = f.read()
        xml_str = clean_and_parse_xml(xml_str).toxml()
        edited_name = re.match(ur"^.+?<name>(.+?)</name>", xml_str).groups()[0]
        self.assertEqual(record['name'], edited_name)

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
            'username': self.user.username,
            'id_string': self.xform.id_string,
            'query': '{}',
            'fields': '[]',
            'sort': '[]',
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
        records = ParsedInstance.query_mongo(**query_args)
        self.assertEqual(len(records), 1)
        # submit the edited instance
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid_edited.xml"
        )
        self._make_submission(xml_submission_file_path)
        self.assertEqual(self.response.status_code, 201)
        records = ParsedInstance.query_mongo(**query_args)
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
            'username': self.user.username,
            'id_string': self.xform.id_string,
            'query': '{}',
            'fields': '[]',
            'sort': '[]',
            'count': True
        }
        cursor = ParsedInstance.query_mongo(**query_args)
        num_mongo_instances = cursor[0]['count']
        # make first submission
        self._make_submission(xml_submission_file_path)

        self.assertEqual(self.response.status_code, 201)
        self.assertEqual(Instance.objects.count(), num_instances + 1)
        # no new record in instances history
        self.assertEqual(
            InstanceHistory.objects.count(), num_instances_history)
        # check count of mongo instances after first submission
        cursor = ParsedInstance.query_mongo(**query_args)
        self.assertEqual(cursor[0]['count'], num_mongo_instances + 1)

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
        cursor = ParsedInstance.query_mongo(**query_args)
        self.assertEqual(cursor[0]['count'], num_mongo_instances + 1)
        # make sure we edited the mongo db record and NOT added a new row
        query_args['count'] = False
        cursor = ParsedInstance.query_mongo(**query_args)
        record = cursor[0]
        with open(xml_submission_file_path, "r") as f:
            xml_str = f.read()
        xml_str = clean_and_parse_xml(xml_str).toxml()
        edited_name = re.match(ur"^.+?<name>(.+?)</name>", xml_str).groups()[0]
        self.assertEqual(record['name'], edited_name)
