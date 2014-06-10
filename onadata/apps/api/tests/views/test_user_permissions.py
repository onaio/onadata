import json
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.renderers import JSONRenderer

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.libs.permissions import ManagerRole
from onadata.libs.serializers.xform_serializer import XFormSerializer


class TestUserPermissions(TestAbstractViewSet):
    def setUp(self):
        super(self.__class__, self).setUp()

    def test_can_add_xform_to_other_account(self):
        view = XFormViewSet.as_view({
            'post': 'create'
        })
        data = {
            'owner': 'http://testserver/api/v1/users/bob',
            'public': False,
            'public_data': False,
            'description': u'',
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

        bob = self.user
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(extra_post_data=alice_data)

        with open(path) as xls_file:
            post_data = {'xls_file': xls_file}
            request = self.factory.post('/', data=post_data, **self.extra)
            response = view(request, owner='bob')
            self.assertEqual(response.status_code, 403)
            ManagerRole.add(self.user, bob.profile)
            response = view(request, owner='bob')
            self.assertEqual(response.status_code, 201)
            xform = bob.xforms.all()[0]
            data.update({
                'url':
                'http://testserver/api/v1/forms/bob/%s' % xform.pk
            })
            self.assertDictContainsSubset(data, response.data)

    def test_put_update_manager(self):
        self._publish_xls_form_to_project()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(extra_post_data=alice_data)
        view = XFormViewSet.as_view({
            'put': 'update'
        })
        description = 'DESCRIPTION'
        xfs = XFormSerializer(instance=self.xform)
        data = json.loads(JSONRenderer().render(xfs.data))
        data.update({'public': True, 'description': description})

        self.assertFalse(self.xform.shared)

        request = self.factory.put('/', data=data, **self.extra)
        with self.assertRaises(ValidationError):
            response = view(request, owner='bob', pk=self.xform.id)
        self.assertFalse(self.xform.shared)
        ManagerRole.add(self.user, self.xform)
        request = self.factory.put('/', data=data, **self.extra)
        response = view(request, owner='bob', pk=self.xform.id)

        self.xform.reload()
        self.assertTrue(self.xform.shared)
        self.assertEqual(self.xform.description, description)
        self.assertEqual(response.data['public'], True)
        self.assertEqual(response.data['description'], description)
