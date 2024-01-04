# -*- coding: utf-8 -*-
"""
Instance model class
"""

from django.contrib.auth import get_user_model
from django.contrib.gis.db import models
from django.utils import timezone
from django.utils.translation import gettext as _

from psqlextra.models import PostgresPartitionedModel
from psqlextra.types import PostgresPartitioningMethod
from taggit.managers import TaggableManager

from onadata.apps.logger.models.xform import XFORM_TITLE_LENGTH

User = get_user_model()  # pylint: disable=invalid-name


class Submission(PostgresPartitionedModel):
    """
    Model representing a single submission to an XForm
    """

    json = models.JSONField(default=dict, null=False)
    xml = models.TextField()

    organization = models.ForeignKey(
        User, related_name="org_submissions", null=False, on_delete=models.CASCADE
    )
    submitted_by = models.ForeignKey(
        User, related_name="submissions", null=True, on_delete=models.SET_NULL
    )

    instance_id = models.ForeignKey(
        "logger.Instance",
        null=False,
        related_name="submission",
        on_delete=models.CASCADE,
    )
    project = models.ForeignKey("Project", on_delete=models.CASCADE)
    xform = models.ForeignKey(
        "logger.XForm", null=False, related_name="submissions", on_delete=models.CASCADE
    )
    survey_type = models.ForeignKey("logger.SurveyType", on_delete=models.PROTECT)
    # shows when we first received this instance
    date_created = models.DateTimeField(
        default=timezone.now,
        editable=False,
        blank=True,
    )
    # this will end up representing "date last parsed"
    date_modified = models.DateTimeField(
        default=timezone.now,
        editable=False,
        blank=True,
    )
    # this will end up representing "date instance was deleted"
    deleted_at = models.DateTimeField(null=True, default=None)
    deleted_by = models.ForeignKey(
        User, related_name="deleted_submissions", null=True, on_delete=models.SET_NULL
    )

    # this will be edited when we need to create a new InstanceHistory object
    last_edited = models.DateTimeField(null=True, default=None)

    # ODK keeps track of three statuses for an instance:
    # incomplete, submitted, complete
    # we add the following additional statuses:
    # - submitted_via_web
    # - imported_via_csv
    status = models.CharField(max_length=20, default="submitted_via_web")
    uuid = models.CharField(max_length=249, default="", db_index=True)
    version = models.CharField(max_length=XFORM_TITLE_LENGTH, null=True)

    # store a geographic objects associated with this instance
    geom = models.GeometryCollectionField(null=True)

    # Keep track of whether all media attachments have been received
    media_all_received = models.BooleanField(
        _("Received All Media Attachemts"), null=True, default=True
    )
    total_media = models.PositiveIntegerField(
        _("Total Media Attachments"), null=True, default=0
    )
    media_count = models.PositiveIntegerField(
        _("Received Media Attachments"), null=True, default=0
    )
    checksum = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    # Keep track of submission reviews, only query reviews if True
    has_a_review = models.BooleanField(_("has_a_review"), default=False)

    tags = TaggableManager()

    class Meta:
        app_label = "logger"
        unique_together = ("organization", "xform", "uuid")
        indexes = [
            models.Index(fields=["date_created"]),
            models.Index(fields=["date_modified"]),
            models.Index(fields=["deleted_at"]),
        ]

    class PartitioningMeta:
        """psqlextra partitioning meta class."""

        method = PostgresPartitioningMethod.LIST
        key = ["organization_id"]
