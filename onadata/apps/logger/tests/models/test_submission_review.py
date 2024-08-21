"""
Submission Review Model Tests Module
"""

from __future__ import unicode_literals

from django.utils import timezone


from onadata.apps.logger.models import Entity, Instance, Note, SubmissionReview
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.main.tests.test_base import TestBase

from onadata.libs.utils.user_auth import get_user_default_project


class TestSubmissionReview(TestBase):
    """
    TestSubmissionReview Class
    """

    def test_note_text_property_method(self):
        """
        Test :
            - note_text property
            - get_note_text method
        """
        self._publish_transportation_form_and_submit_instance()
        instance = Instance.objects.first()
        note = Note(
            instance=instance,
            note="Hey there",
            instance_field="",
        )

        submission_review = SubmissionReview(instance=instance)

        # Returns None if Submission_Review has no note_text
        self.assertIsNone(submission_review.get_note_text())
        self.assertIsNone(submission_review.note_text)

        submission_review = SubmissionReview(instance=instance, note=note)

        # Returns correct note text when note is present
        self.assertEqual(note.note, submission_review.get_note_text())
        self.assertEqual(note.note, submission_review.note_text)

    def test_set_deleted(self):
        """
        Test :
            - set_deleted method
        """
        self._publish_transportation_form_and_submit_instance()
        instance = Instance.objects.first()
        submission_review = SubmissionReview(instance=instance)

        time = timezone.now()

        submission_review.set_deleted(deleted_at=time)

        self.assertEqual(time, submission_review.deleted_at)
        self.assertEqual(None, submission_review.deleted_by)

    def test_entity_created(self):
        """Entity is created for when submission is approved"""
        self.project = get_user_default_project(self.user)
        xform = self._publish_registration_form(self.user)
        MetaData.submission_review(xform, "true")
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_registration" version="2022110901">'
            "<formhub><uuid>d156a2dce4c34751af57f21ef5c4e6cc</uuid></formhub>"
            "<location>-1.286905 36.772845 0 0</location>"
            "<species>purpleheart</species>"
            "<circumference>300</circumference>"
            "<intake_notes />"
            "<meta>"
            "<instanceID>uuid:9d3f042e-cfec-4d2a-8b5b-212e3b04802b</instanceID>"
            "<instanceName>300cm purpleheart</instanceName>"
            '<entity create="1" dataset="trees" id="dbee4c32-a922-451c-9df7-42f40bf78f48">'
            "<label>300cm purpleheart</label>"
            "</entity>"
            "</meta>"
            "</data>"
        )
        instance = Instance.objects.create(xml=xml, user=self.user, xform=xform)

        self.assertEqual(Entity.objects.count(), 0)

        SubmissionReview.objects.create(
            instance=instance, status=SubmissionReview.APPROVED
        )

        self.assertEqual(Entity.objects.count(), 1)

    def test_entity_created_approved_only(self):
        """Entity is only created if status is Approved"""
        self.project = get_user_default_project(self.user)
        xform = self._publish_registration_form(self.user)
        MetaData.submission_review(xform, "true")
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_registration" version="2022110901">'
            "<formhub><uuid>d156a2dce4c34751af57f21ef5c4e6cc</uuid></formhub>"
            "<location>-1.286905 36.772845 0 0</location>"
            "<species>purpleheart</species>"
            "<circumference>300</circumference>"
            "<intake_notes />"
            "<meta>"
            "<instanceID>uuid:9d3f042e-cfec-4d2a-8b5b-212e3b04802b</instanceID>"
            "<instanceName>300cm purpleheart</instanceName>"
            '<entity create="1" dataset="trees" id="dbee4c32-a922-451c-9df7-42f40bf78f48">'
            "<label>300cm purpleheart</label>"
            "</entity>"
            "</meta>"
            "</data>"
        )
        instance = Instance.objects.create(xml=xml, user=self.user, xform=xform)
        SubmissionReview.objects.create(
            instance=instance, status=SubmissionReview.REJECTED
        )

        self.assertEqual(Entity.objects.count(), 0)

        SubmissionReview.objects.create(
            instance=instance, status=SubmissionReview.PENDING
        )

        self.assertEqual(Entity.objects.count(), 0)

    def test_entity_created_approved_edit(self):
        """Entity created when submission review changes to Approved"""
        self.project = get_user_default_project(self.user)
        xform = self._publish_registration_form(self.user)
        MetaData.submission_review(xform, "true")
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_registration" version="2022110901">'
            "<formhub><uuid>d156a2dce4c34751af57f21ef5c4e6cc</uuid></formhub>"
            "<location>-1.286905 36.772845 0 0</location>"
            "<species>purpleheart</species>"
            "<circumference>300</circumference>"
            "<intake_notes />"
            "<meta>"
            "<instanceID>uuid:9d3f042e-cfec-4d2a-8b5b-212e3b04802b</instanceID>"
            "<instanceName>300cm purpleheart</instanceName>"
            '<entity create="1" dataset="trees" id="dbee4c32-a922-451c-9df7-42f40bf78f48">'
            "<label>300cm purpleheart</label>"
            "</entity>"
            "</meta>"
            "</data>"
        )
        instance = Instance.objects.create(xml=xml, user=self.user, xform=xform)
        review = SubmissionReview.objects.create(
            instance=instance, status=SubmissionReview.REJECTED
        )

        self.assertEqual(Entity.objects.count(), 0)

        review.status = SubmissionReview.APPROVED
        review.save()

        self.assertEqual(Entity.objects.count(), 1)
