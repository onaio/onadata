# coding=utf-8
import json
import os
import re
import requests
import pytz

from datetime import datetime
from django.utils import timezone
from django.conf import settings
from httmock import urlmatch, HTTMock
from rest_framework import status
from xml.dom import minidom, Node

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.logger.models import XForm
from onadata.libs.permissions import (
    OwnerRole, ReadOnlyRole, ManagerRole, DataEntryRole, EditorRole)
from onadata.libs.serializers.xform_serializer import XFormSerializer
from onadata.apps.main.models import MetaData


@urlmatch(netloc=r'(.*\.)?enketo\.formhub\.org$')
def enketo_mock(url, request):
    response = requests.Response()
    response.status_code = 201
    response._content = \
        '{\n  "url": "https:\\/\\/dmfrm.enketo.org\\/webform",\n'\
        '  "code": "200"\n}'
    return response


@urlmatch(netloc=r'(.*\.)?enketo\.formhub\.org$')
def enketo_error_mock(url, request):
    response = requests.Response()
    response.status_code = 400
    response._content = \
        '{\n  "message": "no account exists for this OpenRosa server",\n'\
        '  "code": "200"\n}'
    return response


@urlmatch(netloc=r'(.*\.)?xls_server$')
def external_mock(url, request):
    json_str = '[{"transport_loop_over_transport_types_frequency_ambulance' \
               '_frequency_to_referral_facility": "daily",' \
               ' "transport_available_transportation_types_to_referral' \
               '_facility": "ambulance bicycle",' \
               ' "meta_instanceID": "uuid:7a9ba167019a4152a31e46049587d672",' \
               ' "transport_loop_over_transport_types_frequency_bicycle' \
               '_frequency_to_referral_facility": "weekly",' \
               ' "_xform_id_string": "transportation_2011_07_25"},' \
               ' {"transport_available_transportation_types_to_referral' \
               '_facility_other": "camel", "transport_available' \
               '_transportation_types_to_referral_facility": "taxi other",' \
               ' "transport_loop_over_transport_types_frequency_taxi' \
               '_frequency_to_referral_facility": "daily",' \
               ' "meta_instanceID": "uuid:9f0a1508-c3b7-4c99-be00-9b237c26bcbf",' \
               ' "transport_loop_over_transport_types_frequency_other' \
               '_frequency_to_referral_facility": "other",' \
               ' "_xform_id_string": "transportation_2011_07_25"},' \
               ' {"transport_loop_over_transport_types_frequency_ambulance' \
               '_frequency_to_referral_facility": "weekly",' \
               ' "transport_available_transportation_types_to_referral' \
               '_facility": "ambulance", "meta_instanceID": "uuid:9c6f3468-' \
               'cfda-46e8-84c1-75458e72805d", "_xform_id_string":' \
               ' "transportation_2011_07_25"}, {"transport_loop_over_' \
               'transport_types_frequency_ambulance_frequency_to_referral_' \
               'facility": "daily", "transport_available_transportation_types' \
               '_to_referral_facility": "ambulance bicycle", ' \
               '"meta_instanceID": "uuid:f3d8dc65-91a6-4d0f-9e97-802128083390",' \
               ' "transport_loop_over_transport_types_frequency_bicycle' \
               '_frequency_to_referral_facility": "weekly",' \
               ' "_xform_id_string": "transportation_2011_07_25"}, ' \
               '{"transport_available_transportation_types_to_referral' \
               '_facility": "none", "meta_instanceID": "uuid:5b2cc313-fc09-' \
               '437e-8149-fcd32f695d41", ' \
               '"_xform_id_string": "transportation_2011_07_25"}]'

    assert request.body == json_str, "json payload not as expected"
    response = requests.Response()
    response.status_code = 201
    response._content = \
        "/xls/ee3ff9d8f5184fc4a8fdebc2547cc059"
    return response


class TestXFormViewSet(TestAbstractViewSet):

    def setUp(self):
        super(self.__class__, self).setUp()
        self.view = XFormViewSet.as_view({
            'get': 'list',
        })

    def test_form_list(self):
        self._publish_xls_form_to_project()
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)

    def test_submission_count_for_today_in_form_list(self):

        self._publish_xls_form_to_project()
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertIn('submission_count_for_today', response.data[0].keys())
        self.assertEqual(response.data[0]['submission_count_for_today'], 0)
        self.assertEqual(response.data[0]['num_of_submissions'], 0)

        paths = [os.path.join(
            self.main_directory, 'fixtures', 'transportation',
            'instances_w_uuid', s, s + '.xml')
            for s in ['transport_2011-07-25_19-05-36']]

        # instantiate date that is NOT naive; timezone is enabled
        current_timzone_name = timezone.get_current_timezone_name()
        current_timezone = pytz.timezone(current_timzone_name)
        today = datetime.today()
        current_date = current_timezone.localize(
            datetime(today.year,
                     today.month,
                     today.day))
        self._make_submission(paths[0], forced_submission_time=current_date)
        self.assertEqual(self.response.status_code, 201)

        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['submission_count_for_today'], 1)
        self.assertEqual(response.data[0]['num_of_submissions'], 1)

    def test_form_list_anon(self):
        self._publish_xls_form_to_project()
        request = self.factory.get('/')
        response = self.view(request)
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_public_form_list(self):
        self._publish_xls_form_to_project()
        self.view = XFormViewSet.as_view({
            'get': 'retrieve',
        })
        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk='public')
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        # public shared form
        self.xform.shared = True
        self.xform.save()
        response = self.view(request, pk='public')
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.form_data['public'] = True
        del self.form_data['date_modified']
        del response.data[0]['date_modified']
        self.assertEqual(response.data, [self.form_data])

        # public shared form data
        self.xform.shared_data = True
        self.xform.shared = False
        self.xform.save()
        response = self.view(request, pk='public')
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_form_list_other_user_access(self):
        """Test that a different user has no access to bob's form"""
        self._publish_xls_form_to_project()
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [self.form_data])

        # test with different user
        previous_user = self.user
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(extra_post_data=alice_data)
        self.assertEqual(self.user.username, 'alice')
        self.assertNotEqual(previous_user,  self.user)
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        # should be empty
        self.assertEqual(response.data, [])

    def test_form_list_filter_by_user(self):
        # publish bob's form
        self._publish_xls_form_to_project()

        previous_user = self.user
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(extra_post_data=alice_data)
        self.assertEqual(self.user.username, 'alice')
        self.assertNotEqual(previous_user,  self.user)

        ReadOnlyRole.add(self.user, self.xform)
        view = XFormViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.xform.pk)
        bobs_form_data = response.data

        # publish alice's form
        self._publish_xls_form_to_project()

        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        # should be both bob's and alice's form
        self.assertEqual(sorted(response.data),
                         sorted([bobs_form_data, self.form_data]))

        # apply filter, see only bob's forms
        request = self.factory.get('/', data={'owner': 'bob'}, **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [bobs_form_data])

        # apply filter, see only alice's forms
        request = self.factory.get('/', data={'owner': 'alice'}, **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [self.form_data])

        # apply filter, see a non existent user
        request = self.factory.get('/', data={'owner': 'noone'}, **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_form_get(self):
        self._publish_xls_form_to_project()
        view = XFormViewSet.as_view({
            'get': 'retrieve'
        })
        formid = self.xform.pk
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.form_data)

    def test_form_format(self):
        self._publish_xls_form_to_project()
        view = XFormViewSet.as_view({
            'get': 'form'
        })
        formid = self.xform.pk
        data = {
            "name": "transportation",
            "title": "transportation_2011_07_25",
            "default_language": "default",
            "id_string": "transportation_2011_07_25",
            "type": "survey",
        }
        request = self.factory.get('/', **self.extra)
        # test for unsupported format
        response = view(request, pk=formid, format='csvzip')
        self.assertEqual(response.status_code, 400)

        # test for supported formats
        response = view(request, pk=formid, format='json')
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertDictContainsSubset(data, response.data)
        response = view(request, pk=formid, format='xml')
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        response_doc = minidom.parseString(response.data)
        response = view(request, pk=formid, format='xls')
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)

        xml_path = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation", "transportation.xml")
        with open(xml_path) as xml_file:
            expected_doc = minidom.parse(xml_file)

        model_node = [
            n for n in
            response_doc.getElementsByTagName("h:head")[0].childNodes
            if n.nodeType == Node.ELEMENT_NODE and
            n.tagName == "model"][0]

        # check for UUID and remove
        uuid_nodes = [
            node for node in model_node.childNodes
            if node.nodeType == Node.ELEMENT_NODE
            and node.getAttribute("nodeset") == "/transportation/formhub/uuid"]
        self.assertEqual(len(uuid_nodes), 1)
        uuid_node = uuid_nodes[0]
        uuid_node.setAttribute("calculate", "''")

        # check content without UUID
        response_xml = response_doc.toxml().replace(
            self.xform.version, u"201411120717")
        self.assertEqual(response_xml, expected_doc.toxml())

    def test_form_tags(self):
        self._publish_xls_form_to_project()
        view = XFormViewSet.as_view({
            'get': 'labels',
            'post': 'labels',
            'delete': 'labels'
        })
        list_view = XFormViewSet.as_view({
            'get': 'list',
        })
        formid = self.xform.pk

        # no tags
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.data, [])

        # add tag "hello"
        request = self.factory.post('/', data={"tags": "hello"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, [u'hello'])

        # check filter by tag
        request = self.factory.get('/', data={"tags": "hello"}, **self.extra)
        self.form_data = XFormSerializer(
            self.xform, context={'request': request}).data
        response = list_view(request, pk=formid)
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [self.form_data])

        request = self.factory.get('/', data={"tags": "goodbye"}, **self.extra)
        response = list_view(request, pk=formid)
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        # remove tag "hello"
        request = self.factory.delete('/', data={"tags": "hello"},
                                      **self.extra)
        response = view(request, pk=formid, label='hello')
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_enketo_url_no_account(self):
        self._publish_xls_form_to_project()
        view = XFormViewSet.as_view({
            'get': 'enketo'
        })
        formid = self.xform.pk
        # no tags
        request = self.factory.get('/', **self.extra)
        with HTTMock(enketo_error_mock):
            response = view(request, pk=formid)
            data = {'message': u"Enketo not properly configured."}

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data, data)

    def test_enketo_url(self):
        self._publish_xls_form_to_project()
        view = XFormViewSet.as_view({
            'get': 'enketo'
        })
        formid = self.xform.pk
        # no tags
        request = self.factory.get('/', **self.extra)
        with HTTMock(enketo_mock):
            response = view(request, pk=formid)
            data = {"enketo_url": "https://dmfrm.enketo.org/webform"}
            self.assertEqual(response.data, data)

    def test_publish_xlsform(self):
        view = XFormViewSet.as_view({
            'post': 'create'
        })
        data = {
            'owner': 'http://testserver/api/v1/users/bob',
            'public': False,
            'public_data': False,
            'description': u'transportation_2011_07_25',
            'downloadable': True,
            'allows_sms': False,
            'encrypted': False,
            'sms_id_string': u'transportation_2011_07_25',
            'id_string': u'transportation_2011_07_25',
            'title': u'transportation_2011_07_25',
            'bamboo_dataset': u''
        }
        path = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation", "transportation.xls")
        with open(path) as xls_file:
            post_data = {'xls_file': xls_file}
            request = self.factory.post('/', data=post_data, **self.extra)
            response = view(request)
            self.assertEqual(response.status_code, 201)
            xform = self.user.xforms.all()[0]
            data.update({
                'url':
                'http://testserver/api/v1/forms/%s' % xform.pk
            })
            self.assertDictContainsSubset(data, response.data)
            self.assertTrue(OwnerRole.user_has_role(self.user, xform))
            self.assertEquals("owner", response.data['users'][0]['role'])

    def test_publish_xlsform_anon(self):
        view = XFormViewSet.as_view({
            'post': 'create'
        })
        path = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation", "transportation.xls")
        username = 'Anon'
        error_msg = 'User with username %s does not exist.' % username
        with open(path) as xls_file:
            post_data = {'xls_file': xls_file, 'owner': username}
            request = self.factory.post('/', data=post_data, **self.extra)
            response = view(request)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data.get('message'), error_msg)

    def test_publish_invalid_xls_form(self):
        view = XFormViewSet.as_view({
            'post': 'create'
        })
        path = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation", "transportation.bad_id.xls")
        with open(path) as xls_file:
            post_data = {'xls_file': xls_file}
            request = self.factory.post('/', data=post_data, **self.extra)
            response = view(request)
            self.assertEqual(response.status_code, 400)
            error_msg = '[row : 5] Question or group with no name.'
            self.assertEqual(response.data.get('text'), error_msg)

    def test_publish_invalid_xls_form_no_choices(self):
        view = XFormViewSet.as_view({
            'post': 'create'
        })
        path = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation", "transportation.no_choices.xls")
        with open(path) as xls_file:
            post_data = {'xls_file': xls_file}
            request = self.factory.post('/', data=post_data, **self.extra)
            response = view(request)
            self.assertEqual(response.status_code, 400)
            error_msg = (
                'There should be a choices sheet in this xlsform. Please '
                'ensure that the choices sheet name is all in small caps.')
            self.assertEqual(response.data.get('text'), error_msg)

    def test_partial_update(self):
        self._publish_xls_form_to_project()
        view = XFormViewSet.as_view({
            'patch': 'partial_update'
        })
        title = u'مرحب'
        description = 'DESCRIPTION'
        data = {'description': description, 'title': title,
                'downloadable': True}

        self.assertFalse(self.xform.shared)

        request = self.factory.patch('/', data=data, **self.extra)
        response = view(request, pk=self.xform.id)

        self.xform.reload()
        self.assertTrue(self.xform.downloadable)
        self.assertFalse(self.xform.shared)
        self.assertEqual(self.xform.description, description)
        self.assertEqual(response.data['public'], False)
        self.assertEqual(response.data['description'], description)
        self.assertEqual(response.data['title'], title)
        matches = re.findall(r"<h:title>([^<]+)</h:title>", self.xform.xml)
        self.assertTrue(len(matches) > 0)
        self.assertEqual(matches[0], title)

    def test_partial_update_anon(self):
        self._publish_xls_form_to_project()
        view = XFormViewSet.as_view({
            'patch': 'partial_update'
        })
        title = u'مرحب'
        description = 'DESCRIPTION'
        username = 'Anon'
        error_msg = 'User with username %s does not exist.' % username
        data = {'public': True, 'description': description, 'title': title,
                'downloadable': True, 'owner': username}

        self.assertFalse(self.xform.shared)

        request = self.factory.patch('/', data=data, **self.extra)
        response = view(request, pk=self.xform.id)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('message'), error_msg)

    def test_set_form_private(self):
        key = 'shared'
        view = XFormViewSet.as_view({
            'post': 'create'
        })

        path = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation", "transportation.xls")
        with open(path) as xls_file:
            post_data = {'xls_file': xls_file}
            request = self.factory.post('/', data=post_data, **self.extra)
            response = view(request)
            self.assertEqual(response.status_code, 201)

        self.xform = XForm.objects.all().order_by('pk').reverse()[0]
        self.xform.__setattr__(key, True)
        self.xform.save()
        view = XFormViewSet.as_view({
            'patch': 'partial_update'
        })
        data = {'public': False}

        self.assertTrue(self.xform.__getattribute__(key))

        request = self.factory.patch('/', data=data, **self.extra)
        response = view(request, pk=self.xform.id)

        self.xform.reload()
        self.assertFalse(self.xform.__getattribute__(key))
        self.assertFalse(response.data['public'])

    def test_set_form_bad_value(self):
        key = 'shared'
        self._publish_xls_form_to_project()
        view = XFormViewSet.as_view({
            'patch': 'partial_update'
        })
        data = {'public': 'String'}

        request = self.factory.patch('/', data=data, **self.extra)
        response = view(request, pk=self.xform.id)

        self.xform.reload()
        self.assertFalse(self.xform.__getattribute__(key))
        self.assertEqual(response.data,
                         {'shared':
                          [u"'String' value must be either True or False."]})

    def test_set_form_bad_key(self):
        self._publish_xls_form_to_project()
        self.xform.save()
        view = XFormViewSet.as_view({
            'patch': 'partial_update'
        })
        data = {'nonExistentField': False}

        request = self.factory.patch('/', data=data, **self.extra)
        response = view(request, pk=self.xform.id)

        self.xform.reload()
        self.assertFalse(self.xform.shared)
        self.assertFalse(response.data['public'])

    def test_form_delete(self):
        self._publish_xls_form_to_project()
        self.xform.save()
        view = XFormViewSet.as_view({
            'delete': 'destroy'
        })
        formid = self.xform.pk
        request = self.factory.delete('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.data, None)
        self.assertEqual(response.status_code, 204)
        with self.assertRaises(XForm.DoesNotExist):
            self.xform.reload()

    def test_form_share_endpoint(self):
        self._publish_xls_form_to_project()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)

        view = XFormViewSet.as_view({
            'post': 'share'
        })
        formid = self.xform.pk

        ROLES = [ReadOnlyRole,
                 DataEntryRole,
                 EditorRole,
                 ManagerRole,
                 OwnerRole]
        for role_class in ROLES:
            self.assertFalse(role_class.user_has_role(alice_profile.user,
                                                      self.xform))

            data = {'username': 'alice', 'role': role_class.name}
            request = self.factory.post('/', data=data, **self.extra)
            response = view(request, pk=formid)

            self.assertEqual(response.status_code, 204)
            self.assertTrue(role_class.user_has_role(alice_profile.user,
                                                     self.xform))

    def test_form_clone_endpoint(self):
        self._publish_xls_form_to_project()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)
        view = XFormViewSet.as_view({
            'post': 'clone'
        })
        formid = self.xform.pk
        count = XForm.objects.count()

        data = {'username': 'mjomba'}
        request = self.factory.post('/', data=data, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 400)

        data = {'username': 'alice'}
        request = self.factory.post('/', data=data, **self.extra)
        response = view(request, pk=formid)
        self.assertFalse(self.user.has_perm('can_add_xform', alice_profile))
        self.assertEqual(response.status_code, 403)

        ManagerRole.add(self.user, alice_profile)
        request = self.factory.post('/', data=data, **self.extra)
        response = view(request, pk=formid)
        self.assertTrue(self.user.has_perm('can_add_xform', alice_profile))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(count + 1, XForm.objects.count())

    def test_xform_serializer_none(self):
        data = {
            'title': u'',
            'owner': None,
            'public': False,
            'public_data': False,
            'require_auth': False,
            'description': u'',
            'downloadable': False,
            'allows_sms': False,
            'uuid': u'',
            'instances_with_geopoints': False,
            'num_of_submissions': 0,
            'version': u'',
            'project': None,
            'created_by': None
        }
        self.assertEqual(data, XFormSerializer(None).data)

    def test_external_export(self):
        self._publish_xls_form_to_project()
        self._make_submissions()

        data_value = 'template 1|http://xls_server'
        self._add_form_metadata(self.xform, 'external_export',
                                data_value)
        metadata = MetaData.objects.get(xform=self.xform,
                                        data_type='external_export')
        paths = [os.path.join(
            self.main_directory, 'fixtures', 'transportation',
            'instances_w_uuid', s, s + '.xml')
            for s in ['transport_2011-07-25_19-05-36']]

        self._make_submission(paths[0])
        self.assertEqual(self.response.status_code, 201)

        view = XFormViewSet.as_view({
            'get': 'retrieve',
        })
        data = {'meta': metadata.pk}
        formid = self.xform.pk
        request = self.factory.get('/', data=data,
                                   **self.extra)
        with HTTMock(external_mock):
            # External export
            response = view(
                request,
                pk=formid,
                format='xls')
            self.assertEqual(response.status_code, 302)
            expected_url = \
                'http://xls_server/xls/ee3ff9d8f5184fc4a8fdebc2547cc059'
            self.assertEquals(response.url, expected_url)

    def test_external_export_error(self):
        self._publish_xls_form_to_project()

        data_value = 'template 1|http://xls_server'
        self._add_form_metadata(self.xform, 'external_export',
                                data_value)

        paths = [os.path.join(
            self.main_directory, 'fixtures', 'transportation',
            'instances_w_uuid', s, s + '.xml')
            for s in ['transport_2011-07-25_19-05-36']]

        self._make_submission(paths[0])
        self.assertEqual(self.response.status_code, 201)

        view = XFormViewSet.as_view({
            'get': 'retrieve',
        })
        formid = self.xform.pk
        token = 'http://xls_server/xls/' +\
            '8e86d4bdfa7f435ab89485aeae4ea6f5'
        data = {'token': token}
        request = self.factory.get('/', data=data, **self.extra)

        # External export
        response = view(
            request,
            pk=formid,
            format='xls')

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertTrue(data.get('error')
                        .startswith("J2X client could not generate report."))

    def test_csv_import(self):
        self._publish_xls_form_to_project()
        view = XFormViewSet.as_view({'post': 'csv_import'})
        csv_import = open(os.path.join(settings.PROJECT_ROOT, 'libs', 'utils',
                                       'tests', 'fixtures', 'good.csv'))
        post_data = {'csv_file': csv_import}
        request = self.factory.post('/', data=post_data, **self.extra)
        response = view(request, pk=self.xform.id)
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get('additions'), 9)
        self.assertEqual(response.data.get('updates'), 0)

    def test_csv_import_fail(self):
        self._publish_xls_form_to_project()
        view = XFormViewSet.as_view({'post': 'csv_import'})
        csv_import = open(os.path.join(settings.PROJECT_ROOT, 'libs', 'utils',
                                       'tests', 'fixtures', 'bad.csv'))
        post_data = {'csv_file': csv_import}
        request = self.factory.post('/', data=post_data, **self.extra)
        response = view(request, pk=self.xform.id)
        self.assertEqual(response.status_code, 400)
        self.assertIsNotNone(response.data.get('error'))

    def test_csv_import_fail_invalid_field_post(self):
        """Test that invalid post returns 400 with the error in json respone"""
        self._publish_xls_form_to_project()
        view = XFormViewSet.as_view({'post': 'csv_import'})
        csv_import = open(os.path.join(settings.PROJECT_ROOT, 'libs', 'utils',
                                       'tests', 'fixtures', 'bad.csv'))
        post_data = {'wrong_file_field': csv_import}
        request = self.factory.post('/', data=post_data, **self.extra)
        response = view(request, pk=self.xform.id)
        self.assertEqual(response.status_code, 400)
        self.assertIsNotNone(response.data.get('error'))

    def test_update_xform_xls_file(self):
        self._publish_xls_form_to_project()

        self.assertIsNotNone(self.xform.version)
        version = self.xform.version
        form_id = self.xform.pk

        view = XFormViewSet.as_view({
            'patch': 'partial_update',
        })

        path = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation", "transportation_version.xls")
        with open(path) as xls_file:
            post_data = {'xls_file': xls_file}
            request = self.factory.patch('/', data=post_data, **self.extra)
            response = view(request, pk=form_id)

            self.assertEqual(response.status_code, 200)

        self.xform.reload()
        new_version = self.xform.version

        # diff versions
        self.assertNotEquals(version, new_version)
        self.assertEquals(form_id, self.xform.pk)

    def test_update_xform_xls_bad_file(self):
        self._publish_xls_form_to_project()

        self.assertIsNotNone(self.xform.version)
        version = self.xform.version
        form_id = self.xform.pk

        view = XFormViewSet.as_view({
            'patch': 'partial_update',
        })

        path = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation", "transportation.bad_id.xls")
        with open(path) as xls_file:
            post_data = {'xls_file': xls_file}
            request = self.factory.patch('/', data=post_data, **self.extra)
            response = view(request, pk=form_id)

            self.assertEqual(response.status_code, 400)

        self.xform.reload()
        new_version = self.xform.version

        # fails to update the form
        self.assertEquals(version, new_version)
        self.assertEquals(form_id, self.xform.pk)

    def test_update_xform_xls_file_with_submissions(self):
        self._publish_xls_form_to_project()
        self._make_submissions()

        self.assertIsNotNone(self.xform.version)
        version = self.xform.version
        form_id = self.xform.pk

        view = XFormViewSet.as_view({
            'patch': 'partial_update',
        })

        path = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation", "transportation_updated.xls")
        with open(path) as xls_file:
            post_data = {'xls_file': xls_file}
            request = self.factory.patch('/', data=post_data, **self.extra)
            response = view(request, pk=form_id)

            self.assertEqual(response.status_code, 400)
            self.assertEquals(response.data, u"Cannot update the xls file in "
                                             u"a form that has submissions")

        self.xform.reload()
        new_version = self.xform.version

        # diff versions
        self.assertEquals(version, new_version)
        self.assertEquals(form_id, self.xform.pk)

    def test_update_xform_xls_file_with_version_set(self):
        self._publish_xls_form_to_project()
        form_id = self.xform.pk

        self.assertIsNotNone(self.xform.version)

        view = XFormViewSet.as_view({
            'patch': 'partial_update',
        })

        path = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation", "transportation_version.xls")
        with open(path) as xls_file:
            post_data = {'xls_file': xls_file}
            request = self.factory.patch('/', data=post_data, **self.extra)
            response = view(request, pk=form_id)

            self.assertEqual(response.status_code, 200)

        self.xform.reload()

        # diff versions
        self.assertEquals(self.xform.version, u"212121211")
        self.assertEquals(form_id, self.xform.pk)

    def test_update_xform_using_put(self):
        self._publish_xls_form_to_project()
        form_id = self.xform.pk

        version = self.xform.version
        view = XFormViewSet.as_view({
            'put': 'update',
        })

        post_data = {
            'uuid': 'ae631e898bd34ced91d2a309d8b72das',
            'description': 'Transport form',
            'downloadable': False,
            'owner': 'http://testserver/api/v1/users/{0}'.format(self.user),
            'created_by':
            'http://testserver/api/v1/users/{0}'.format(self.user),
            'public': False,
            'public_data': False,
            'project': 'http://testserver/api/v1/projects/{0}'.format(
                self.xform.project.pk),
            'title': 'Transport Form'
        }
        request = self.factory.put('/', data=post_data, **self.extra)
        response = view(request, pk=form_id)
        self.assertEqual(response.status_code, 200, response.data)

        self.xform.reload()

        self.assertEquals(version, self.xform.version)
        self.assertEquals(self.xform.description, u'Transport form')
        self.assertEquals(self.xform.title, u'Transport Form')
        self.assertEquals(form_id, self.xform.pk)

    def test_update_xform_using_put_without_required_field(self):
        self._publish_xls_form_to_project()
        form_id = self.xform.pk

        view = XFormViewSet.as_view({
            'put': 'update',
        })

        post_data = {
            'uuid': 'ae631e898bd34ced91d2a309d8b72das',
            'description': 'Transport form',
            'downloadable': False,
            'owner': 'http://testserver/api/v1/users/{0}'.format(self.user),
            'created_by':
            'http://testserver/api/v1/users/{0}'.format(self.user),
            'public': False,
            'public_data': False,
            'project': 'http://testserver/api/v1/projects/{0}'.format(
                self.xform.project.pk),
        }
        request = self.factory.put('/', data=post_data, **self.extra)
        response = view(request, pk=form_id)

        self.assertEqual(response.status_code, 400)
        self.assertEquals(response.data,
                          {'title': [u'This field is required.']})

    def test_user_cannot_add_public_form(self):
        self._project_create()
        self._publish_xls_form_to_project()

        view = XFormViewSet.as_view({
            'patch': 'partial_update'
        })
        data = {'public': 'True'}

        request = self.factory.patch('/', data=data, **self.extra)
        response = view(request, pk=self.xform.id)

        self.assertEqual(response.status_code, 400)
        error = {
            'detail': u'Check project share setting'
        }
        self.assertDictContainsSubset(response.data, error)

        self.xform.reload()
        self.assertEquals(self.xform.shared, False)

    def test_sharing_project_less_form(self):
        view = XFormViewSet.as_view({
            'post': 'create'
        })

        path = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation", "transportation.xls")
        with open(path) as xls_file:
            post_data = {'xls_file': xls_file}
            request = self.factory.post('/', data=post_data, **self.extra)
            response = view(request)
            self.assertEqual(response.status_code, 201)

        self.xform = XForm.objects.all().order_by('pk').reverse()[0]
        view = XFormViewSet.as_view({
            'patch': 'partial_update'
        })
        data = {'public': 'True'}
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}
        request = self.factory.patch('/', data=data, **self.extra)
        response = view(request, pk=self.xform.id)

        self.assertEqual(response.status_code, 200)
