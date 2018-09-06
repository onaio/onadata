# -*- coding: utf-8 -*-
"""
Submission Review Model Module
"""
from __future__ import unicode_literals

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _


def update_instance_json_on_save(sender, instance, **kwargs):
    """
    Signal handler to update Instance Json with the submission review on save
    """
    submission_instance = instance.instance
    if not submission_instance.has_a_review:
        submission_instance.has_a_review = True
    submission_instance.save()


class SubmissionReview(models.Model):
    """
    SubmissionReview Model Class
    """

    APPROVED = '1'
    REJECTED = '2'
    PENDING = '3'

    STATUS_CHOICES = ((APPROVED, _('Approved')), (PENDING, _('Pending')),
                      (REJECTED, _('Rejected')))

    instance = models.ForeignKey(
        'logger.Instance', related_name='reviews', on_delete=models.CASCADE)
    note = models.ForeignKey(
        'logger.Note',
        related_name='notes',
        blank=True,
        null=True,
        default=None,
        on_delete=models.SET_NULL)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        default=None,
        on_delete=models.CASCADE)
    status = models.CharField(
        'Status',
        max_length=1,
        choices=STATUS_CHOICES,
        default=PENDING,
        db_index=True)
    deleted_at = models.DateTimeField(null=True, default=None, db_index=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='deleted_reviews',
        null=True,
        on_delete=models.SET_NULL)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    class Meta:
        """
        Meta Options for SubmissionReview
        """
        app_label = 'logger'

    def get_note_text(self):
        """
        Custom Property returns associated note text
        """
        if self.note:
            return self.note.note  # pylint: disable=no-member
        return None

    def set_deleted(self, deleted_at=timezone.now(), user=None):
        """
        Sets the deleted_at and deleted_by fields
        """
        if user:
            self.deleted_by = user
        self.deleted_at = deleted_at
        self.save()

    note_text = property(get_note_text)


post_save.connect(
    update_instance_json_on_save, sender=SubmissionReview,
    dispatch_uid='update_instance_json_on_save')
