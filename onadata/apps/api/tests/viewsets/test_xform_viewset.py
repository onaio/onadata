import os
import requests

from django.conf import settings
from httmock import urlmatch, HTTMock

from xml.dom import minidom, Node

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.logger.models import XForm
from onadata.libs.permissions import (
    OwnerRole, ReadOnlyRole, ManagerRole, DataEntryRole, EditorRole)


@urlmatch(netloc=r'(.*\.)?enketo\.formhub\.org$')
def enketo_mock(url, request):
    response = requests.Response()
    response.status_code = 201
    response._content = \
        '{\n  "url": "https:\\/\\/dmfrm.enketo.org\\/webform",\n'\
        '  "code": "200"\n}'
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
        self.assertEqual(response.status_code, 200)

    def test_form_list_anon(self):
        self._publish_xls_form_to_project()
        request = self.factory.get('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_public_form_list(self):
        self._publish_xls_form_to_project()
        self.view = XFormViewSet.as_view({
            'get': 'retrieve',
        })
        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk='public')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        # public shared form
        self.xform.shared = True
        self.xform.save()
        response = self.view(request, pk='public')
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
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_form_list_other_user_access(self):
        """Test that a different user has no access to bob's form"""
        self._publish_xls_form_to_project()
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
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
        self.assertEqual(response.status_code, 200)
        # should be both bob's and alice's form
        self.assertEqual(response.data, [bobs_form_data, self.form_data])

        # apply filter, see only bob's forms
        request = self.factory.get('/', data={'owner': 'bob'}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [bobs_form_data])

        # apply filter, see only alice's forms
        request = self.factory.get('/', data={'owner': 'alice'}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [self.form_data])

        # apply filter, see a non existent user
        request = self.factory.get('/', data={'owner': 'noone'}, **self.extra)
        response = self.view(request)
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
        response = view(request, pk=formid, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertDictContainsSubset(data, response.data)
        response = view(request, pk=formid, format='xml')
        self.assertEqual(response.status_code, 200)
        response_doc = minidom.parseString(response.data)

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
        self.assertEqual(response_doc.toxml(), expected_doc.toxml())

    def test_form_tags(self):
        self._publish_xls_form_to_project()
        view = XFormViewSet.as_view({
            'get': 'labels',
            'post': 'labels',
            'delete': 'labels'
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
        # remove tag "hello"
        request = self.factory.delete('/', data={"tags": "hello"},
                                      **self.extra)
        response = view(request, pk=formid, label='hello')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

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
            self.assertTrue(OwnerRole.has_role(self.user, xform))

    def test_partial_update(self):
        self._publish_xls_form_to_project()
        view = XFormViewSet.as_view({
            'patch': 'partial_update'
        })
        description = 'DESCRIPTION'
        data = {'public': True, 'description': description}

        self.assertFalse(self.xform.shared)

        request = self.factory.patch('/', data=data, **self.extra)
        response = view(request, pk=self.xform.id)

        self.xform.reload()
        self.assertTrue(self.xform.shared)
        self.assertEqual(self.xform.description, description)
        self.assertEqual(response.data['public'], True)
        self.assertEqual(response.data['description'], description)

    def test_set_form_private(self):
        key = 'shared'
        self._publish_xls_form_to_project()
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
            self.assertFalse(role_class.has_role(alice_profile.user,
                                                 self.xform))

            data = {'username': 'alice', 'role': role_class.name}
            request = self.factory.post('/', data=data, **self.extra)
            response = view(request, pk=formid)

            self.assertEqual(response.status_code, 204)
            self.assertTrue(role_class.has_role(alice_profile.user,
                                                self.xform))
