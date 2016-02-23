from django.test import RequestFactory

from onadata.apps.api.viewsets.note_viewset import NoteViewSet
from onadata.apps.main.tests.test_base import TestBase


class TestNoteViewSet(TestBase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._create_user_and_login()
        self._publish_transportation_form()
        self._make_submissions()
        self.view = NoteViewSet.as_view({
            'get': 'list',
            'post': 'create',
            'delete': 'destroy'
        })
        self.factory = RequestFactory()
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

    @property
    def _first_xform_instance(self):
        return self.xform.instances.all().order_by('pk')[0]

    def _add_notes_to_data_point(self):
        # add a note to a specific data point
        note = {'note': u"Road Warrior"}
        dataid = self._first_xform_instance.pk
        note['instance'] = dataid
        request = self.factory.post('/', data=note, **self.extra)
        self.assertTrue(self.xform.instances.count())
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        self.pk = response.data['id']
        note['id'] = self.pk
        self.note = note

    def test_note_list(self):
        self._add_notes_to_data_point()
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(response.data) > 0)
        self.assertDictContainsSubset(self.note, response.data[0])

    def test_note_get(self):
        self._add_notes_to_data_point()
        view = NoteViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.pk)
        self.assertEqual(response.status_code, 200)
        self.assertDictContainsSubset(self.note, response.data)

    def test_add_notes_to_data_point(self):
        self._add_notes_to_data_point()
        self.assertEquals(len(self._first_xform_instance.json["_notes"]), 1)

    def test_other_user_notes_access(self):
        self._create_user_and_login('lilly', '1234')
        extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}
        note = {'note': u"Road Warrior"}
        dataid = self.xform.instances.all()[0].pk
        note['instance'] = dataid

        # Other user 'lilly' should not be able to create notes
        # to xform instance owned by 'bob'
        request = self.factory.post('/', data=note, **extra)
        self.assertTrue(self.xform.instances.count())
        response = self.view(request)
        self.assertEqual(response.status_code, 403)

        # save some notes
        self._add_notes_to_data_point()

        # access to /notes endpoint,should be empty list
        request = self.factory.get('/', **extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data, [])
        # Other user 'lilly' should not have access to bob's instance notes
        view = NoteViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **extra)
        response = view(request, pk=self.pk)
        self.assertEqual(response.status_code, 404)

    def test_delete_note(self):
        self._add_notes_to_data_point()
        request = self.factory.delete('/', **self.extra)
        response = self.view(request, pk=self.pk)
        self.assertEqual(response.status_code, 204)
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEquals(response.data, [])

    def test_question_level_notes(self):
        field = "transport"
        dataid = self.xform.instances.all()[0].pk
        note = {'note': "Road Warrior",
                'instance': dataid,
                'instance_field': field}
        request = self.factory.post('/', data=note, **self.extra)
        self.assertTrue(self.xform.instances.count())
        response = self.view(request)
        self.assertEqual(response.status_code, 201)

        instance = self.xform.instances.all()[0]
        self.assertEquals(len(instance.json["_notes"]), 1)

        note = instance.json["_notes"][0]
        self.assertEquals(note['field'], field)

    def test_only_add_question_notes_to_existing_fields(self):
        field = "bla"
        dataid = self.xform.instances.all()[0].pk
        note = {'note': "Road Warrior",
                'instance': dataid,
                'instance_field': field}
        request = self.factory.post('/', data=note, **self.extra)
        self.assertTrue(self.xform.instances.count())
        response = self.view(request)
        self.assertEqual(response.status_code, 400)

        instance = self.xform.instances.all()[0]
        self.assertEquals(len(instance.json["_notes"]), 0)
