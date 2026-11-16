import json

from django.test import RequestFactory

from onadata.apps.api.viewsets.note_viewset import NoteViewSet
from onadata.apps.logger.models import Note
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import DataEntryMinorRole, ReadOnlyRole
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
        self.view = NoteViewSet.as_view(
            {"get": "list", "post": "create", "delete": "destroy"}
        )
        self.factory = RequestFactory()
        self.extra = {"HTTP_AUTHORIZATION": "Token %s" % self.user.auth_token}

    @property
    def _first_xform_instance(self):
        return self.xform.instances.all().order_by("pk")[0]

    def _add_notes_to_data_point(self):
        # add a note to a specific data point
        note = {"note": "Road Warrior"}
        dataid = self._first_xform_instance.pk
        note["instance"] = dataid
        request = self.factory.post("/", data=note, **self.extra)
        self.assertTrue(self.xform.instances.count())
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        self.pk = response.data["id"]
        note["id"] = self.pk
        self.note = note

    def test_note_list(self):
        self._add_notes_to_data_point()
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(response.data) > 0)
        self.assertLessEqual(self.note.items(), response.data[0].items())

    def test_note_get(self):
        self._add_notes_to_data_point()
        view = NoteViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["owner"], self.user.username)
        self.assertLessEqual(self.note.items(), response.data.items())

    def test_get_note_for_specific_instance(self):
        self._add_notes_to_data_point()
        view = NoteViewSet.as_view({"get": "retrieve"})

        instance = self.xform.instances.first()

        query_params = {"instance": instance.id}
        request = self.factory.get("/", data=query_params, **self.extra)
        response = view(request, pk=self.pk)
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(self.note.items(), response.data.items())

        second_instance = self.xform.instances.last()
        query_params = {"instance": second_instance.id}
        request = self.factory.get("/", data=query_params, **self.extra)
        response = view(request, pk=self.pk)

        self.assertEqual(response.status_code, 200)
        self.assertListEqual(response.data, [])

    def test_add_notes_to_data_point(self):
        self._add_notes_to_data_point()
        self.assertEqual(len(self._first_xform_instance.json["_notes"]), 1)

    def test_other_user_notes_access(self):
        self._create_user_and_login("lilly", "1234")
        extra = {"HTTP_AUTHORIZATION": "Token %s" % self.user.auth_token}
        note = {"note": "Road Warrior"}
        dataid = self.xform.instances.first().pk
        note["instance"] = dataid

        # Other user 'lilly' should not be able to create notes
        # to xform instance owned by 'bob'
        request = self.factory.post("/", data=note)
        self.assertTrue(self.xform.instances.count())
        response = self.view(request)
        self.assertEqual(response.status_code, 401)

        # save some notes
        self._add_notes_to_data_point()

        # access to /notes endpoint,should be empty list
        request = self.factory.get("/", **extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data, [])

        # Other user 'lilly' sees an empty list when accessing bob's notes
        view = NoteViewSet.as_view({"get": "retrieve"})
        query_params = {"instance": dataid}
        request = self.factory.get("/", data=query_params, **extra)
        response = view(request, pk=self.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_cannot_add_note_to_instance_on_inaccessible_form(self):
        """An authenticated user cannot add a note to a submission they
        cannot view."""
        dataid = self._first_xform_instance.pk
        unknown_dataid = dataid + 1000
        self._create_user_and_login("lilly", "1234")
        extra = {"HTTP_AUTHORIZATION": "Token %s" % self.user.auth_token}

        note = {"note": "Snooping", "instance": dataid}
        request = self.factory.post("/", data=note, **extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["instance"][0],
            'Invalid pk "%s" - object does not exist.' % dataid,
        )
        self.assertEqual(Note.objects.count(), 0)

        # same response as a submission id that does not exist
        note = {"note": "Snooping", "instance": unknown_dataid}
        request = self.factory.post("/", data=note, **extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["instance"][0],
            'Invalid pk "%s" - object does not exist.' % unknown_dataid,
        )

    def test_padded_id_reveals_nothing_about_a_hidden_submission(self):
        """The rejection echoes the submitted value, so a padded id of a
        hidden submission reads the same as a padded unknown id."""
        padded_dataid = "0%s" % self._first_xform_instance.pk
        padded_unknown_dataid = "0%s" % (self._first_xform_instance.pk + 1000)
        self._create_user_and_login("lilly", "1234")
        extra = {"HTTP_AUTHORIZATION": "Token %s" % self.user.auth_token}

        for dataid in [padded_dataid, padded_unknown_dataid]:
            note = {"note": "Snooping", "instance": dataid}
            request = self.factory.post("/", data=note, **extra)
            response = self.view(request)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                response.data["instance"][0],
                'Invalid pk "%s" - object does not exist.' % dataid,
            )
        self.assertEqual(Note.objects.count(), 0)

    def test_cannot_add_note_to_public_form_instance_without_grant(self):
        """A submission on a publicly shared form does not accept notes from
        users without a view permission grant on the form."""
        self.xform.shared_data = True
        self.xform.save()
        dataid = self._first_xform_instance.pk
        self._create_user_and_login("lilly", "1234")
        extra = {"HTTP_AUTHORIZATION": "Token %s" % self.user.auth_token}

        note = {"note": "Public snooping", "instance": dataid}
        request = self.factory.post("/", data=note, **extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["instance"][0],
            'Invalid pk "%s" - object does not exist.' % dataid,
        )
        self.assertEqual(Note.objects.count(), 0)

    def test_data_access_limits_apply_to_notes(self):
        """A user whose role grants access only to their own submissions
        can add a note to their own submission but not to another user's."""
        # forms are published with meta permissions enabled by default
        self.assertTrue(
            self.xform.metadata_set.filter(data_type="xform_meta_perms").exists()
        )
        own_instance = self._first_xform_instance
        other_instance = self.xform.instances.all().order_by("pk")[1]
        alice = self._create_user("alice", "alice")
        DataEntryMinorRole.add(alice, self.xform)
        own_instance.user = alice
        own_instance.save()
        extra = {"HTTP_AUTHORIZATION": "Token %s" % alice.auth_token}

        note = {"note": "On my own submission", "instance": own_instance.pk}
        request = self.factory.post("/", data=note, **extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)

        note = {"note": "On another submission", "instance": other_instance.pk}
        request = self.factory.post("/", data=note, **extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["instance"][0],
            'Invalid pk "%s" - object does not exist.' % other_instance.pk,
        )
        self.assertEqual(Note.objects.count(), 1)

    def test_cannot_move_note_to_instance_on_inaccessible_form(self):
        """A user cannot move their note to a submission of a form they have
        no view permission on."""
        foreign_dataid = self._first_xform_instance.pk
        self._create_user_and_login("lilly", "1234")
        extra = {"HTTP_AUTHORIZATION": "Token %s" % self.user.auth_token}
        self._publish_transportation_form()
        self._submit_transport_instance()
        dataid = self._first_xform_instance.pk

        note = {"note": "On my own data", "instance": dataid}
        request = self.factory.post("/", data=note, **extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        note_pk = response.data["id"]

        view = NoteViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/",
            data=json.dumps({"instance": foreign_dataid}),
            content_type="application/json",
            **extra,
        )
        response = view(request, pk=note_pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["instance"][0],
            'Invalid pk "%s" - object does not exist.' % foreign_dataid,
        )
        self.assertEqual(Note.objects.get(pk=note_pk).instance_id, dataid)

    def test_author_cannot_edit_note_after_losing_form_access(self):
        """A note's author cannot edit the note once they can no longer
        view the form."""
        dataid = self._first_xform_instance.pk
        xform = self._first_xform_instance.xform
        self._create_user_and_login("lilly", "1234")
        extra = {"HTTP_AUTHORIZATION": "Token %s" % self.user.auth_token}
        ReadOnlyRole.add(self.user, xform)

        note = {"note": "While a collaborator", "instance": dataid}
        request = self.factory.post("/", data=note, **extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        note_pk = response.data["id"]

        ReadOnlyRole.remove_obj_permissions(self.user, xform)

        view = NoteViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/",
            data=json.dumps({"note": "Edited after access was removed"}),
            content_type="application/json",
            **extra,
        )
        response = view(request, pk=note_pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["instance"][0],
            'Invalid pk "%s" - object does not exist.' % dataid,
        )
        self.assertEqual(Note.objects.get(pk=note_pk).note, "While a collaborator")

    def test_author_can_delete_note_after_losing_form_access(self):
        """A note's author can delete their own note once they can no
        longer view the form."""
        dataid = self._first_xform_instance.pk
        xform = self._first_xform_instance.xform
        self._create_user_and_login("lilly", "1234")
        extra = {"HTTP_AUTHORIZATION": "Token %s" % self.user.auth_token}
        ReadOnlyRole.add(self.user, xform)

        note = {"note": "While a collaborator", "instance": dataid}
        request = self.factory.post("/", data=note, **extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        note_pk = response.data["id"]

        ReadOnlyRole.remove_obj_permissions(self.user, xform)

        view = NoteViewSet.as_view({"delete": "destroy"})
        request = self.factory.delete("/", **extra)
        response = view(request, pk=note_pk)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Note.objects.filter(pk=note_pk).exists())

    def test_author_can_move_note_away_after_losing_form_access(self):
        """A note's author can move their note onto a submission they can
        view once they can no longer view the note's current form, just as
        they can delete it and write a new one."""
        dataid = self._first_xform_instance.pk
        xform = self._first_xform_instance.xform
        self._create_user_and_login("lilly", "1234")
        extra = {"HTTP_AUTHORIZATION": "Token %s" % self.user.auth_token}
        ReadOnlyRole.add(self.user, xform)

        note = {"note": "While a collaborator", "instance": dataid}
        request = self.factory.post("/", data=note, **extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        note_pk = response.data["id"]

        self._publish_transportation_form()
        self._submit_transport_instance()
        own_dataid = self._first_xform_instance.pk
        ReadOnlyRole.remove_obj_permissions(self.user, xform)

        view = NoteViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/",
            data=json.dumps({"note": "On my own data", "instance": own_dataid}),
            content_type="application/json",
            **extra,
        )
        response = view(request, pk=note_pk)
        self.assertEqual(response.status_code, 200)
        note = Note.objects.get(pk=note_pk)
        self.assertEqual(note.instance_id, own_dataid)
        self.assertEqual(note.note, "On my own data")

    def test_collaborator_with_readonly_permission_can_add_comment(self):
        self._create_user_and_login("lilly", "1234")
        extra = {"HTTP_AUTHORIZATION": "Token %s" % self.user.auth_token}

        # save some notes
        self._add_notes_to_data_point()

        # post note to submission as lilly without permissions
        note = {"note": "Road Warrior"}
        dataid = self._first_xform_instance.pk
        note["instance"] = dataid
        request = self.factory.post("/", data=note)
        self.assertTrue(self.xform.instances.count())
        response = self.view(request)

        self.assertEqual(response.status_code, 401)

        # post note to submission with read-only access to the form
        ReadOnlyRole.add(self.user, self._first_xform_instance.xform)

        note = {"note": "Road Warrior"}
        dataid = self._first_xform_instance.pk
        note["instance"] = dataid
        request = self.factory.post("/", data=note, **extra)
        self.assertTrue(self.xform.instances.count())
        response = self.view(request)

        self.assertEqual(response.status_code, 201)

    def test_delete_note(self):
        self._add_notes_to_data_point()
        request = self.factory.delete("/", **self.extra)
        response = self.view(request, pk=self.pk)
        self.assertEqual(response.status_code, 204)
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_question_level_notes(self):
        field = "transport"
        dataid = self.xform.instances.all()[0].pk
        note = {"note": "Road Warrior", "instance": dataid, "instance_field": field}
        request = self.factory.post("/", data=note, **self.extra)
        self.assertTrue(self.xform.instances.count())
        response = self.view(request)
        self.assertEqual(response.status_code, 201)

        instance = self.xform.instances.get(pk=dataid)
        self.assertEqual(len(instance.json["_notes"]), 1, instance.json)

        note = instance.json["_notes"][0]
        self.assertEqual(note["instance_field"], field)

    def test_only_add_question_notes_to_existing_fields(self):
        field = "bla"
        dataid = self.xform.instances.all()[0].pk
        note = {"note": "Road Warrior", "instance": dataid, "instance_field": field}
        request = self.factory.post("/", data=note, **self.extra)
        self.assertTrue(self.xform.instances.count())
        response = self.view(request)
        self.assertEqual(response.status_code, 400)

        instance = self.xform.instances.all()[0]
        self.assertEqual(len(instance.json["_notes"]), 0)

    def test_can_update_note_field_without_resending_instance(self):
        """A note's instance_field can be updated without resending the
        submission id, and an unknown field is still rejected."""
        self._add_notes_to_data_point()
        view = NoteViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/",
            data=json.dumps({"instance_field": "transport"}),
            content_type="application/json",
            **self.extra,
        )
        response = view(request, pk=self.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["instance_field"], "transport")

        request = self.factory.patch(
            "/",
            data=json.dumps({"instance_field": "bla"}),
            content_type="application/json",
            **self.extra,
        )
        response = view(request, pk=self.pk)
        self.assertEqual(response.status_code, 400)

    def test_updating_or_deleting_an_invisible_note_returns_404(self):
        """A user with no visible notes gets a 404 when updating or
        deleting a note, not a server error."""
        self._add_notes_to_data_point()
        note_pk = self.pk
        self._create_user_and_login("lilly", "1234")
        extra = {"HTTP_AUTHORIZATION": "Token %s" % self.user.auth_token}

        view = NoteViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/",
            data=json.dumps({"instance_field": "transport"}),
            content_type="application/json",
            **extra,
        )
        response = view(request, pk=note_pk)
        self.assertEqual(response.status_code, 404)

        request = self.factory.delete("/", **extra)
        response = self.view(request, pk=note_pk)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Note.objects.count(), 1)

    def test_attribute_error_bug(self):
        """NoteSerializer: Should not raise AttributeError exeption"""
        note = Note(note="Hello", instance=self._first_xform_instance)
        note.save()
        data = NoteSerializer(note).data
        self.assertLessEqual(
            {
                "created_by": None,
                "note": "Hello",
                "instance": note.instance_id,
                "owner": None,
            }.items(),
            data.items(),
        )
