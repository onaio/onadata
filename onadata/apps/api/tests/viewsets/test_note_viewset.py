import os
from datetime import datetime

from django.conf import settings
from django.utils.timezone import make_aware
from django.test import RequestFactory
from guardian.shortcuts import assign_perm

from onadata.apps.api.viewsets.note_viewset import NoteViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.logger.models import Note
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.serializers.note_serializer import NoteSerializer


class TestNoteViewSet(TestBase):
    """
    Test NoteViewSet
    """
    def setUp(self):
        super(TestNoteViewSet, self).setUp()
        self._create_user_and_login()
        self._publish_transportation_form()
        self._make_submissions()
        self.view = NoteViewSet.as_view({
            'get': 'list',
            'post': 'create',
            'delete': 'destroy'
        })
        self.factory = RequestFactory()
        self.extra = {'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

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
        view = NoteViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['owner'], self.user.username)
        self.assertDictContainsSubset(self.note, response.data)

    def test_get_note_for_specific_instance(self):
        self._add_notes_to_data_point()
        view = NoteViewSet.as_view({'get': 'retrieve'})

        instance = self.xform.instances.first()

        query_params = {"instance": instance.id}
        request = self.factory.get('/', data=query_params, **self.extra)
        response = view(request, pk=self.pk)
        self.assertEqual(response.status_code, 200)
        self.assertDictContainsSubset(self.note, response.data)

        second_instance = self.xform.instances.last()
        query_params = {"instance": second_instance.id}
        request = self.factory.get('/', data=query_params, **self.extra)
        response = view(request, pk=self.pk)

        self.assertEqual(response.status_code, 200)
        self.assertListEqual(response.data, [])

    def test_add_notes_to_data_point(self):
        self._add_notes_to_data_point()
        self.assertEquals(len(self._first_xform_instance.json["_notes"]), 1)

    def test_other_user_notes_access(self):
        self._create_user_and_login('lilly', '1234')
        extra = {'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}
        note = {'note': u"Road Warrior"}
        dataid = self.xform.instances.first().pk
        note['instance'] = dataid

        # Other user 'lilly' should not be able to create notes
        # to xform instance owned by 'bob'
        request = self.factory.post('/', data=note)
        self.assertTrue(self.xform.instances.count())
        response = self.view(request)
        self.assertEqual(response.status_code, 401)

        # save some notes
        self._add_notes_to_data_point()

        # access to /notes endpoint,should be empty list
        request = self.factory.get('/', **extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data, [])

        # Other user 'lilly' sees an empty list when accessing bob's notes
        view = NoteViewSet.as_view({'get': 'retrieve'})
        query_params = {"instance": dataid}
        request = self.factory.get('/', data=query_params, **extra)
        response = view(request, pk=self.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_collaborator_with_readonly_permission_can_add_comment(self):
        self._create_user_and_login('lilly', '1234')
        extra = {'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

        # save some notes
        self._add_notes_to_data_point()

        # post note to submission as lilly without permissions
        note = {'note': u"Road Warrior"}
        dataid = self._first_xform_instance.pk
        note['instance'] = dataid
        request = self.factory.post('/', data=note)
        self.assertTrue(self.xform.instances.count())
        response = self.view(request)

        self.assertEqual(response.status_code, 401)

        # post note to submission with permissions to form
        assign_perm('view_xform', self.user, self._first_xform_instance.xform)

        note = {'note': u"Road Warrior"}
        dataid = self._first_xform_instance.pk
        note['instance'] = dataid
        request = self.factory.post('/', data=note, **extra)
        self.assertTrue(self.xform.instances.count())
        response = self.view(request)

        self.assertEqual(response.status_code, 201)

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
        note = {
            'note': "Road Warrior",
            'instance': dataid,
            'instance_field': field
        }
        request = self.factory.post('/', data=note, **self.extra)
        self.assertTrue(self.xform.instances.count())
        response = self.view(request)
        self.assertEqual(response.status_code, 201)

        instance = self.xform.instances.all()[0]
        self.assertEquals(len(instance.json["_notes"]), 1)

        note = instance.json["_notes"][0]
        self.assertEquals(note['instance_field'], field)

    def test_only_add_question_notes_to_existing_fields(self):
        field = "bla"
        dataid = self.xform.instances.all()[0].pk
        note = {
            'note': "Road Warrior",
            'instance': dataid,
            'instance_field': field
        }
        request = self.factory.post('/', data=note, **self.extra)
        self.assertTrue(self.xform.instances.count())
        response = self.view(request)
        self.assertEqual(response.status_code, 400)

        instance = self.xform.instances.all()[0]
        self.assertEquals(len(instance.json["_notes"]), 0)

    def test_csv_export_form_w_notes(self):
        """
        Test CSV exports include notes for submissions that have notes.
        """
        self._add_notes_to_data_point()
        self._add_notes_to_data_point()

        time = make_aware(datetime(2016, 7, 1))
        for instance in self.xform.instances.all():
            instance.date_created = time
            instance.save()
            instance.parsed_instance.save()

        view = XFormViewSet.as_view({'get': 'retrieve'})

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.xform.pk, format='csv')
        self.assertTrue(response.status_code, 200)

        test_file_path = os.path.join(settings.PROJECT_ROOT, 'apps', 'viewer',
                                      'tests', 'fixtures',
                                      'transportation_w_notes.csv')

        self._test_csv_response(response, test_file_path)

    def test_attribute_error_bug(self):
        """NoteSerializer: Should not raise AttributeError exeption"""
        note = Note(note='Hello', instance=self._first_xform_instance)
        note.save()
        data = NoteSerializer(note).data
        self.assertDictContainsSubset({
            'created_by': None,
            'note': u'Hello',
            'instance': note.instance_id,
            'owner': None
        }, data)
