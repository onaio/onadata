# -*- coding: utf-8 -*-
"""
Instance model class
"""
# pylint: disable=too-many-lines

import importlib
import math
import sys
from datetime import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.gis.db import models
from django.contrib.gis.geos import GeometryCollection, Point
from django.core.cache import cache
from django.core.files.storage import storages
from django.db import connection, transaction
from django.db.models import Q
from django.db.models.signals import post_delete, post_save, pre_delete
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from celery import current_task
from deprecated import deprecated
from multidb.pinning import use_master
from taggit.managers import TaggableManager

from onadata.apps.logger.models.submission_review import SubmissionReview
from onadata.apps.logger.models.survey_type import SurveyType
from onadata.apps.logger.models.xform import (
    XFORM_TITLE_LENGTH,
    XForm,
)
from onadata.apps.logger.xform_instance_parser import (
    XFormInstanceParser,
    clean_and_parse_xml,
    get_uuid_from_xml,
)
from onadata.celeryapp import app
from onadata.libs.data.query import get_numeric_fields
from onadata.libs.utils.cache_tools import (
    DATAVIEW_COUNT,
    IS_ORG,
    PROJ_NUM_DATASET_CACHE,
    PROJ_SUB_DATE_CACHE,
    PROJECT_DATE_MODIFIED_CACHE,
    XFORM_COUNT,
    XFORM_DATA_VERSIONS,
    XFORM_SUBMISSION_COUNT_FOR_DAY,
    XFORM_SUBMISSION_COUNT_FOR_DAY_DATE,
    safe_delete,
)
from onadata.libs.utils.common_tags import (
    ATTACHMENTS,
    BAMBOO_DATASET_ID,
    DATE_MODIFIED,
    DELETEDAT,
    DURATION,
    EDITED,
    END,
    GEOLOCATION,
    ID,
    LAST_EDITED,
    MEDIA_ALL_RECEIVED,
    MEDIA_COUNT,
    NOTES,
    REVIEW_COMMENT,
    REVIEW_DATE,
    REVIEW_STATUS,
    START,
    STATUS,
    SUBMISSION_TIME,
    SUBMITTED_BY,
    TAGS,
    TOTAL_MEDIA,
    UUID,
    VERSION,
    XFORM_ID,
    XFORM_ID_STRING,
)
from onadata.libs.utils.common_tools import get_abbreviated_xpath, report_exception
from onadata.libs.utils.dict_tools import get_values_matching_key
from onadata.libs.utils.model_tools import queryset_iterator, set_uuid
from onadata.libs.utils.timing import calculate_duration

# pylint: disable=invalid-name
User = get_user_model()
storage = storages["default"]


def get_attachment_url(attachment, suffix=None):
    """
    Returns the attachment URL for a given suffix
    """
    kwargs = {"pk": attachment.pk}
    url = (
        f"{reverse('files-detail', kwargs=kwargs)}"
        f"?filename={attachment.media_file.name}"
    )
    if suffix:
        url += f"&suffix={suffix}"

    return url


def _get_attachments_from_instance(instance):
    attachments = []
    for item in instance.attachments.filter(deleted_at__isnull=True):
        attachment = {}
        attachment["download_url"] = get_attachment_url(item)
        attachment["small_download_url"] = get_attachment_url(item, "small")
        attachment["medium_download_url"] = get_attachment_url(item, "medium")
        attachment["mimetype"] = item.mimetype
        attachment["filename"] = item.media_file.name
        attachment["name"] = item.name
        attachment["instance"] = item.instance.pk
        attachment["xform"] = instance.xform.id
        attachment["id"] = item.id
        attachments.append(attachment)

    return attachments


def _get_tag_or_element_type_xpath(xform, tag):
    elems = xform.get_survey_elements_of_type(tag)

    return get_abbreviated_xpath(elems[0].get_xpath()) if elems else tag


class FormInactiveError(Exception):
    """Exception class for inactive forms"""

    def __str__(self):
        return _("Form is inactive")


class FormIsMergedDatasetError(Exception):
    """Exception class for merged datasets"""

    def __str__(self):
        return _("Submissions are not allowed on merged datasets.")


def numeric_checker(string_value):
    """
    Checks if a ``string_value`` is a numeric value.
    """
    try:
        return int(string_value)
    except ValueError:
        try:
            value = float(string_value)
        except ValueError:
            pass
        else:
            return 0 if math.isnan(value) else value

    return string_value


# need to establish id_string of the xform before we run get_dict since
# we now rely on data dictionary to parse the xml


def get_id_string_from_xml_str(xml_str):
    """
    Parses an XML ``xml_str`` and returns the top level id string.
    """
    xml_obj = clean_and_parse_xml(xml_str)
    root_node = xml_obj.documentElement
    id_string = root_node.getAttribute("id")

    if not id_string:
        # may be hidden in submission/data/id_string
        elems = root_node.getElementsByTagName("data")

        for data in elems:
            id_string = data.childNodes[0].getAttribute("id")

            if id_string:
                break

    return id_string


def now():
    """Returns current timestamp via timezone.now()."""
    return timezone.now()


def _update_submission_count_for_today(
    form_id: int, incr: bool = True, date_created=None
):
    # Track submissions made today
    current_date = timezone.localdate().isoformat()
    date_cache_key = f"{XFORM_SUBMISSION_COUNT_FOR_DAY_DATE}{form_id}"
    count_cache_key = f"{XFORM_SUBMISSION_COUNT_FOR_DAY}{form_id}"

    if not cache.get(date_cache_key) == current_date:
        cache.set(date_cache_key, current_date, 86400)

    if date_created:
        date_created = (
            date_created.astimezone(timezone.get_current_timezone()).date().isoformat()
        )

    current_count = cache.get(count_cache_key)
    if not current_count and incr:
        cache.set(count_cache_key, 1, 86400)
    elif incr:
        cache.incr(count_cache_key)
    elif current_count and current_count > 0 and date_created == current_date:
        cache.decr(count_cache_key)


@app.task(bind=True, max_retries=3)
def update_xform_submission_count_async(self, instance_id, created):
    """
    Celery task to asynchrounously update an XForms Submission count
    once a submission has been made
    """
    try:
        update_xform_submission_count(instance_id, created)
    except Instance.DoesNotExist as e:
        if self.request.retries > 2:
            msg = f"Failed to update XForm submission count for Instance {instance_id}"
            report_exception(msg, e, sys.exc_info())
        self.retry(exc=e, countdown=60 * self.request.retries)


@transaction.atomic()
def update_xform_submission_count(instance_id, created):
    """Updates the XForm submissions count on a new submission being created."""
    if created:
        with use_master:
            try:
                instance = (
                    Instance.objects.select_related("xform")
                    .only("xform__user_id", "date_created")
                    .get(pk=instance_id)
                )
            except Instance.DoesNotExist as e:
                # Retry if run asynchrounously
                if current_task.request.id:
                    raise e
            else:
                # update xform.num_of_submissions
                cursor = connection.cursor()
                sql = (
                    "UPDATE logger_xform SET "
                    "num_of_submissions = num_of_submissions + 1, "
                    "last_submission_time = %s "
                    "WHERE id = %s"
                )
                params = [instance.date_created, instance.xform_id]

                # update user profile.num_of_submissions
                cursor.execute(sql, params)
                sql = (
                    "UPDATE main_userprofile SET "
                    "num_of_submissions = num_of_submissions + 1 "
                    "WHERE user_id = %s"
                )
                cursor.execute(sql, [instance.xform.user_id])

                # Track submissions made today
                _update_submission_count_for_today(instance.xform_id)

                safe_delete(f"{XFORM_DATA_VERSIONS}{instance.xform_id}")
                safe_delete(f"{DATAVIEW_COUNT}{instance.xform_id}")
                safe_delete(f"{XFORM_COUNT}{instance.xform_id}")
                # Clear project cache
                # pylint: disable=import-outside-toplevel
                from onadata.apps.logger.models.xform import clear_project_cache

                clear_project_cache(instance.xform.project_id)


@use_master
@transaction.atomic()
def _update_xform_submission_count_delete(instance):
    """Updates the XForm submissions count on deletion of a submission."""
    try:
        xform = XForm.objects.select_for_update().get(pk=instance.xform.pk)
    except XForm.DoesNotExist:
        pass
    else:
        xform.num_of_submissions -= 1

        xform.num_of_submissions = max(xform.num_of_submissions, 0)
        xform.save(update_fields=["num_of_submissions"])
        profile_qs = User.profile.get_queryset()
        try:
            profile = profile_qs.select_for_update().get(pk=xform.user.profile.pk)
        except profile_qs.model.DoesNotExist:
            pass
        else:
            profile.num_of_submissions -= 1
            profile.num_of_submissions = max(profile.num_of_submissions, 0)
            profile.save()

        # Track submissions made today
        _update_submission_count_for_today(
            xform.id, incr=False, date_created=instance.date_created
        )

        for cache_prefix in [PROJ_NUM_DATASET_CACHE, PROJ_SUB_DATE_CACHE]:
            safe_delete(f"{cache_prefix}{xform.project.pk}")

        safe_delete(f"{IS_ORG}{xform.pk}")
        safe_delete(f"{XFORM_DATA_VERSIONS}{xform.pk}")
        safe_delete(f"{DATAVIEW_COUNT}{xform.pk}")
        safe_delete(f"{XFORM_COUNT}{xform.pk}")

        # update xform if no instance has geoms
        if (
            instance.xform.instances.filter(deleted_at__isnull=True)
            .exclude(geom=None)
            .count()
            < 1
        ):
            if instance.xform.polygon_xpaths() or instance.xform.geotrace_xpaths():
                instance.xform.instances_with_geopoints = True
            else:
                instance.xform.instances_with_geopoints = False
            instance.xform.save()


# pylint: disable=unused-argument,invalid-name
def update_xform_submission_count_delete(sender, instance, **kwargs):
    """Updates the XForm submissions count on deletion of a submission."""
    if instance:
        _update_xform_submission_count_delete(instance)


@app.task(bind=True, max_retries=3)
def save_full_json_async(self, instance_id):
    """
    Celery task to asynchrounously generate and save an Instances JSON
    once a submission has been made
    """
    with use_master:
        try:
            instance = Instance.objects.get(pk=instance_id)
        except Instance.DoesNotExist as e:
            if self.request.retries > 2:
                msg = f"Failed to save full JSON for Instance {instance_id}"
                report_exception(msg, e, sys.exc_info())
            self.retry(exc=e, countdown=60 * self.request.retries)
        else:
            save_full_json(instance)


@use_master
def save_full_json(instance: "Instance", include_related=True):
    """Save full json dict

    Args:
        include_related (bool): Whether to include related objects
    """
    # Queryset.update ensures the model's save is not called and
    # the pre_save and post_save signals aren't sent
    Instance.objects.filter(pk=instance.pk).update(
        json=instance.get_full_dict(include_related)
    )


@app.task(bind=True, max_retries=3)
def update_project_date_modified_async(self, instance_id, created):
    """
    Celery task to asynchrounously update a Projects last modified date
    once a submission has been made
    """
    try:
        update_project_date_modified(instance_id, created)
    except Instance.DoesNotExist as e:
        if self.request.retries > 2:
            msg = f"Failed to update project date modified for Instance {instance_id}"
            report_exception(msg, e, sys.exc_info())
        self.retry(exc=e, countdown=60 * self.request.retries)


@use_master
def update_project_date_modified(instance_id, _):
    """Update the project's date_modified

    Changes the etag value of the projects endpoint.
    """
    # update the date modified field of the project which will change
    # the etag value of the projects endpoint
    try:
        instance = (
            Instance.objects.select_related("xform__project")
            .only("xform__project__date_modified")
            .get(pk=instance_id)
        )
    except Instance.DoesNotExist as e:
        # Retry if run asynchrounously
        if current_task.request.id:
            raise e
    else:
        timeout = getattr(settings, "PROJECT_IDS_CACHE_TIMEOUT", 3600)
        project_id = instance.xform.project_id

        # Log project id and date motified in cache with timeout
        project_ids = cache.get(PROJECT_DATE_MODIFIED_CACHE, {})
        project_ids[project_id] = instance.date_modified
        cache.set(PROJECT_DATE_MODIFIED_CACHE, project_ids, timeout=timeout)


def convert_to_serializable_date(date):
    """Returns the ISO format of a date object if it has the attribute 'isoformat'."""
    if hasattr(date, "isoformat"):
        return date.isoformat()

    return date


class InstanceBaseClass:
    """Interface of functions for Instance and InstanceHistory model"""

    @property
    def point(self):
        """Returns the Point of the first geom if it is a collection."""
        geom_collection = self.geom

        if geom_collection and geom_collection.num_points:
            return geom_collection[0]
        return self.geom

    def numeric_converter(self, json_dict, numeric_fields=None):
        """Converts strings in a python object ``json_dict`` to their numeric value."""
        if numeric_fields is None:
            # pylint: disable=no-member
            numeric_fields = get_numeric_fields(self.xform)
        for key, value in json_dict.items():
            if isinstance(value, str) and key in numeric_fields:
                json_dict[key] = numeric_checker(value)
            elif isinstance(value, dict):
                json_dict[key] = self.numeric_converter(value, numeric_fields)
            elif isinstance(value, list):
                for k, v in enumerate(value):
                    if isinstance(v, str) and key in numeric_fields:
                        json_dict[key] = numeric_checker(v)
                    elif isinstance(v, dict):
                        value[k] = self.numeric_converter(v, numeric_fields)
        return json_dict

    def _set_geom(self):
        # pylint: disable=no-member
        xform = self.xform
        geo_xpaths = xform.geopoint_xpaths()
        doc = self.get_dict()
        points = []

        if geo_xpaths:
            for xpath in geo_xpaths:
                for gps in get_values_matching_key(doc, xpath):
                    try:
                        geometry = [float(s) for s in gps.split()]
                        lat, lng = geometry[0:2]
                        points.append(Point(lng, lat))
                    except ValueError:
                        return

            if not xform.instances_with_geopoints and points:
                xform.instances_with_geopoints = True
                xform.save()

            # pylint: disable=attribute-defined-outside-init
            if points:
                self.geom = GeometryCollection(points)
            else:
                self.geom = None

    def get_full_dict(self, include_related=True):
        """Returns the submission XML as a python dictionary object

        Include metadata

        Args:
            include_related (bool): Whether to include related objects
            or not
        """
        # Get latest dict
        doc = self.get_dict()
        # Update dict
        geopoint = [self.point.y, self.point.x] if self.point else [None, None]
        doc.update(
            {
                UUID: self.uuid,
                BAMBOO_DATASET_ID: self.xform.bamboo_dataset,
                STATUS: self.status,
                VERSION: self.version,
                DURATION: self.get_duration(),
                XFORM_ID_STRING: self._parser.get_xform_id_string(),
                XFORM_ID: self.xform.pk,
                GEOLOCATION: geopoint,
                SUBMITTED_BY: self.user.username if self.user else None,
                DATE_MODIFIED: self.date_modified.isoformat(),
                SUBMISSION_TIME: self.date_created.isoformat(),
                TOTAL_MEDIA: self.total_media,
                MEDIA_COUNT: self.media_count,
                MEDIA_ALL_RECEIVED: self.media_all_received,
            }
        )

        if isinstance(self.deleted_at, datetime):
            doc[DELETEDAT] = self.deleted_at.isoformat()

        edited = False

        if hasattr(self, "last_edited"):
            edited = self.last_edited is not None

        doc[EDITED] = edited

        if edited:
            doc.update({LAST_EDITED: convert_to_serializable_date(self.last_edited)})

        if self.id:
            doc[ID] = self.id

            if include_related:
                doc.update(
                    {
                        ATTACHMENTS: _get_attachments_from_instance(self),
                        TAGS: list(self.tags.names()),
                        NOTES: self.get_notes(),
                    }
                )

                for osm in self.osm_data.all():
                    doc.update(osm.get_tags_with_prefix())

                # pylint: disable=no-member
                if self.has_a_review:
                    review = self.get_latest_review()

                    if review:
                        doc[REVIEW_STATUS] = review.status
                        doc[REVIEW_DATE] = review.date_created.isoformat()

                        if review.get_note_text():
                            doc[REVIEW_COMMENT] = review.get_note_text()

        return doc

    def _set_parser(self):
        if not hasattr(self, "_parser"):
            # pylint: disable=no-member
            # pylint: disable=attribute-defined-outside-init
            self._parser = XFormInstanceParser(self.xml, self.xform)

    def _set_survey_type(self):
        # pylint: disable=attribute-defined-outside-init
        self.survey_type, _created = SurveyType.objects.get_or_create(
            slug=self.get_root_node_name()
        )

    def _set_uuid(self):
        # pylint: disable=no-member,attribute-defined-outside-init
        # pylint: disable=access-member-before-definition
        if self.xml and not self.uuid:
            # pylint: disable=no-member
            uuid = get_uuid_from_xml(self.xml)
            if uuid is not None:
                self.uuid = uuid
        set_uuid(self)

    def get(self, abbreviated_xpath):
        """Returns the XML element at the ``abbreviated_xpath``."""
        self._set_parser()
        return self._parser.get(abbreviated_xpath)

    # pylint: disable=unused-argument
    def get_dict(self, force_new=False, flat=True):
        """Return a python object representation of this instance's XML."""
        self._set_parser()

        instance_dict = (
            self._parser.get_flat_dict_with_attributes()
            if flat
            else self._parser.to_dict()
        )
        return self.numeric_converter(instance_dict)

    def get_notes(self):
        """Returns a list of notes."""
        # pylint: disable=no-member
        return [note.get_data() for note in self.notes.all()]

    @deprecated(version="2.5.3", reason="Deprecated in favour of `get_latest_review`")
    def get_review_status_and_comment(self):
        """
        Return a tuple of review status and comment.
        """
        try:
            # pylint: disable=no-member
            status = self.reviews.latest("date_modified").status
            comment = self.reviews.latest("date_modified").get_note_text()
            return status, comment
        except SubmissionReview.DoesNotExist:
            return None

    def get_root_node(self):
        """Returns the XML submission's root node."""
        self._set_parser()
        return self._parser.get_root_node()

    def get_root_node_name(self):
        """Returns the XML submission's root node name."""
        self._set_parser()
        return self._parser.get_root_node_name()

    def get_duration(self):
        """Returns the duration between the `start` and `end` questions of a form."""
        data = self.get_dict()
        # pylint: disable=no-member
        start_name = _get_tag_or_element_type_xpath(self.xform, START)
        end_name = _get_tag_or_element_type_xpath(self.xform, END)
        start_time, end_time = data.get(start_name), data.get(end_name)

        return calculate_duration(start_time, end_time)

    def get_latest_review(self):
        """
        Returns the latest review.
        Used in favour of `get_review_status_and_comment`.
        """
        try:
            # pylint: disable=no-member
            return self.reviews.latest("date_modified")
        except SubmissionReview.DoesNotExist:
            return None


class Instance(models.Model, InstanceBaseClass):
    """
    Model representing a single submission to an XForm
    """

    json = models.JSONField(default=dict, null=False)
    xml = models.TextField()
    user = models.ForeignKey(
        User, related_name="instances", null=True, on_delete=models.SET_NULL
    )
    xform = models.ForeignKey(
        "logger.XForm", null=False, related_name="instances", on_delete=models.CASCADE
    )
    survey_type = models.ForeignKey("logger.SurveyType", on_delete=models.PROTECT)
    # shows when we first received this instance
    date_created = models.DateTimeField(
        default=now,
        editable=False,
        blank=True,
    )
    # this will end up representing "date last parsed"
    date_modified = models.DateTimeField(
        default=now,
        editable=False,
        blank=True,
    )
    # this will end up representing "date instance was deleted"
    deleted_at = models.DateTimeField(null=True, default=None)
    deleted_by = models.ForeignKey(
        User, related_name="deleted_instances", null=True, on_delete=models.SET_NULL
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
        unique_together = ("xform", "uuid")
        indexes = [
            models.Index(fields=["date_created"]),
            models.Index(fields=["date_modified"]),
            models.Index(fields=["deleted_at"]),
            models.Index(fields=["xform_id", "id"]),
        ]

    @classmethod
    def set_deleted_at(cls, instance_id, deleted_at=timezone.now(), user=None):
        """Set's the timestamp when a submission was deleted."""
        try:
            instance = cls.objects.get(id=instance_id)
        except cls.DoesNotExist:
            pass
        else:
            instance.set_deleted(deleted_at, user)

    def _check_active(self, force):
        """Check that form is active and raise exception if not.

        :param force: Ignore restrictions on saving.
        """
        # pylint: disable=no-member
        if not force and self.xform and not self.xform.downloadable:
            raise FormInactiveError()

    def _check_is_merged_dataset(self):
        """Check for merged datasets.

        Raises an exception to prevent datasubmissions
        """
        # pylint: disable=no-member
        if self.xform and self.xform.is_merged_dataset:
            raise FormIsMergedDatasetError()

    def get_expected_media(self):
        """
        Returns a list of expected media files from the submission data.
        """
        if not hasattr(self, "_expected_media"):
            # pylint: disable=no-member
            data = self.get_dict()
            media_list = []
            if "encryptedXmlFile" in data and self.xform.encrypted:
                media_list.append(data["encryptedXmlFile"])
                if "media" in data:
                    # pylint: disable=no-member
                    media_list.extend([i["media/file"] for i in data["media"]])
            else:
                media_xpaths = (
                    self.xform.get_media_survey_xpaths()
                    + self.xform.get_osm_survey_xpaths()
                )
                for media_xpath in media_xpaths:
                    media_list.extend(get_values_matching_key(data, media_xpath))
            # pylint: disable=attribute-defined-outside-init
            self._expected_media = list(set(media_list))

        return self._expected_media

    @property
    def num_of_media(self):
        """
        Returns number of media attachments expected in the submission.
        """
        if not hasattr(self, "_num_of_media"):
            # pylint: disable=attribute-defined-outside-init
            self._num_of_media = len(self.get_expected_media())

        return self._num_of_media

    @property
    def attachments_count(self):
        """Returns the number of attachments a submission has."""
        return (
            self.attachments.filter(name__in=self.get_expected_media())
            .distinct("name")
            .order_by("name")
            .count()
        )

    # pylint: disable=arguments-differ
    def save(self, *args, **kwargs):
        force = kwargs.get("force")
        self.date_modified = now()
        self.version = self.get_dict().get(VERSION, self.xform.version)

        if force:
            del kwargs["force"]

        self._check_is_merged_dataset()
        self._check_active(force)
        self._set_geom()
        self._set_survey_type()
        self._set_uuid()

        super().save(*args, **kwargs)

    # pylint: disable=no-member
    def set_deleted(self, deleted_at=timezone.now(), user=None):
        """Set the timestamp and user when a submission is deleted."""
        if user:
            self.deleted_by = user
        self.deleted_at = deleted_at
        self.save()
        # force submission count re-calculation
        self.xform.submission_count(force_update=True)
        self.parsed_instance.save()

    def soft_delete_attachments(self, user=None):
        """
        Soft deletes an attachment by adding a deleted_at timestamp.
        """
        queryset = self.attachments.filter(~Q(name__in=self.get_expected_media()))
        kwargs = {"deleted_at": timezone.now()}
        if user:
            kwargs.update({"deleted_by": user})
        queryset.update(**kwargs)


# pylint: disable=unused-argument
def post_save_submission(sender, instance=None, created=False, **kwargs):
    """Update XForm, Project, JSON field

    - XForm submission count & instances_with_geopoints field
    - Project date modified
    - Update the submission JSON field data. We save the full_json in
        post_save signal because some implementations in get_full_dict
        require the id to be available
    """
    if instance.deleted_at is not None:
        _update_xform_submission_count_delete(instance)
        # mark attachments also as deleted.
        instance.attachments.filter(deleted_at__isnull=True).update(
            deleted_at=instance.deleted_at, deleted_by=instance.deleted_by
        )

    if (
        hasattr(settings, "ASYNC_POST_SUBMISSION_PROCESSING_ENABLED")
        and settings.ASYNC_POST_SUBMISSION_PROCESSING_ENABLED
    ):
        # We first save metadata data without related objects
        # (metadata from non-performance intensive tasks) first since we
        # do not know when the async processing will complete
        save_full_json(instance, False)

        transaction.on_commit(
            lambda: update_xform_submission_count_async.apply_async(
                args=[instance.pk, created]
            )
        )
        transaction.on_commit(
            lambda: save_full_json_async.apply_async(args=[instance.pk])
        )
        transaction.on_commit(
            lambda: update_project_date_modified_async.apply_async(
                args=[instance.pk, created]
            )
        )

    else:
        update_xform_submission_count(instance.pk, created)
        save_full_json(instance)
        update_project_date_modified(instance.pk, created)


# pylint: disable=unused-argument
@use_master
def permanently_delete_attachments(sender, instance=None, created=False, **kwargs):
    if instance:
        attachments = instance.attachments.all()
        for attachment in queryset_iterator(attachments):
            # pylint: disable=expression-not-assigned
            storage.exists(attachment.media_file.name) and storage.delete(
                attachment.media_file.name
            )


@use_master
def register_instance_repeat_columns(sender, instance, created=False, **kwargs):
    # Avoid cyclic dependency errors
    logger_tasks = importlib.import_module("onadata.apps.logger.tasks")

    transaction.on_commit(
        lambda: logger_tasks.register_instance_repeat_columns_async.delay(instance.pk)
    )


post_save.connect(
    post_save_submission, sender=Instance, dispatch_uid="post_save_submission"
)

post_delete.connect(
    update_xform_submission_count_delete,
    sender=Instance,
    dispatch_uid="update_xform_submission_count_delete",
)

pre_delete.connect(
    permanently_delete_attachments,
    sender=Instance,
    dispatch_uid="permanently_delete_attachments",
)

post_save.connect(
    register_instance_repeat_columns,
    sender=Instance,
    dispatch_uid="register_instance_repeat_columns",
)


class InstanceHistory(models.Model, InstanceBaseClass):
    """Stores deleted submission XML to maintain a history of edits."""

    xform_instance = models.ForeignKey(
        Instance, related_name="submission_history", on_delete=models.CASCADE
    )
    user = models.ForeignKey(User, null=True, on_delete=models.CASCADE)

    xml = models.TextField()
    # old instance id
    uuid = models.CharField(max_length=249, default="", db_index=True)

    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    submission_date = models.DateTimeField(null=True, default=None)
    geom = models.GeometryCollectionField(null=True)
    checksum = models.CharField(max_length=64, null=True, blank=True, db_index=True)

    class Meta:
        app_label = "logger"
        indexes = [
            models.Index(fields=["checksum"]),
            models.Index(fields=["uuid"]),
        ]

    @property
    def xform(self):
        """Returns the XForm object linked to this submission."""
        return self.xform_instance.xform

    @property
    def attachments(self):
        """Returns the attachments linked to this submission."""
        return self.xform_instance.attachments.all()

    @property
    def json(self):
        """Returns the XML submission as a python dictionary object."""
        return self.get_full_dict()

    @property
    def status(self):
        """Returns the submission's status"""
        return self.xform_instance.status

    @property
    def tags(self):
        """Returns the tags linked to the submission."""
        return self.xform_instance.tags

    @property
    def notes(self):
        """Returns the notes attached to the submission."""
        return self.xform_instance.notes.all()

    @property
    def reviews(self):
        """Returns the submission reviews."""
        return self.xform_instance.reviews.all()

    @property
    def version(self):
        """Returns the XForm verison for the submission."""
        return self.xform_instance.version

    @property
    def osm_data(self):
        """Returns the OSM data for the submission."""
        return self.xform_instance.osm_data

    @property
    def deleted_at(self):
        """Mutes the deleted_at method for the history record."""
        return None

    @property
    def total_media(self):
        """Returns the number of attachments linked to submission."""
        return self.xform_instance.total_media

    @property
    def has_a_review(self):
        """Returns the value of a submission.has_a_review."""
        return self.xform_instance.has_a_review

    @property
    def media_count(self):
        """Returns the number of media attached to the submission."""
        return self.xform_instance.media_count

    @property
    def media_all_received(self):
        """Returns the value of the submission.media_all_received."""
        return self.xform_instance.media_all_received

    def _set_parser(self):
        if not hasattr(self, "_parser"):
            # pylint: disable=attribute-defined-outside-init
            self._parser = XFormInstanceParser(self.xml, self.xform_instance.xform)

    # pylint: disable=unused-argument
    @classmethod
    def set_deleted_at(cls, instance_id, deleted_at=timezone.now()):
        """Mutes the set_deleted_at method for the history record."""
        return None
