# -*- coding: utf-8 -*-
"""
Submission Review Model Module
"""
from __future__ import unicode_literals

from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _


class SubmissionReview(models.Model):
    """
    SubmissionReview Model Class
    """

    APPROVED = '1'
    REJECTED = '2'
    PENDING = '3'

    STATUS_CHOICES = (
        (APPROVED, _('Approved')),
        (PENDING, _('Pending')),
        (REJECTED, _('Rejected'))
    )

    instance = models.ForeignKey(
        'logger.Instance',
        related_name='reviews',
        on_delete=models.CASCADE)
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
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    class Meta:
        """
        Meta Options for SubmissionReview
        """
        app_label = 'logger'

    def get_note_text(self):
        """
        Custom Method Gets the SubmissionReviews Related
        Note Text
        """
        if self.notes is not None:
            return self.notes.note
        return None

    @property
    def note_text(self):
        """
        Custom Property Returns the Text for the Submission Reviews
        Associated Note
        """
        return self.get_note_text
