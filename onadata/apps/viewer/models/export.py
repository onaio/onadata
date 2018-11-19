# -*- coding=utf-8 -*-
"""
Export model.
"""
import os
from future.utils import python_2_unicode_compatible
from tempfile import NamedTemporaryFile

from django.core.files.storage import get_storage_class
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models.signals import post_delete
from django.utils.translation import ugettext as _

from onadata.libs.utils.common_tags import OSM
from onadata.libs.utils import async_status

EXPORT_QUERY_KEY = 'query'


# pylint: disable=unused-argument
def export_delete_callback(sender, **kwargs):
    """
    Delete export file when an export object is deleted.
    """
    export = kwargs['instance']
    storage = get_storage_class()()
    if export.filepath and storage.exists(export.filepath):
        storage.delete(export.filepath)


def get_export_options_query_kwargs(options):
    """
    Get dict with options JSONField lookups for export options field
    """
    options_kwargs = {}
    for field in Export.EXPORT_OPTION_FIELDS:
        if field in options:
            field_value = options.get(field)

            key = 'options__{}'.format(field)
            options_kwargs[key] = field_value

    return options_kwargs


@python_2_unicode_compatible
class ExportTypeError(Exception):
    """
    ExportTypeError exception class.
    """
    def __str__(self):
        return _(u'Invalid export type specified')


@python_2_unicode_compatible
class ExportConnectionError(Exception):
    """
    ExportConnectionError exception class.
    """
    def __str__(self):
        return _(u'Export server is down.')


@python_2_unicode_compatible
class Export(models.Model):
    """
    Class representing a data export from an XForm
    """
    XLS_EXPORT = 'xls'
    CSV_EXPORT = 'csv'
    KML_EXPORT = 'kml'
    ZIP_EXPORT = 'zip'
    CSV_ZIP_EXPORT = 'csv_zip'
    SAV_ZIP_EXPORT = 'sav_zip'
    SAV_EXPORT = 'sav'
    EXTERNAL_EXPORT = 'external'
    OSM_EXPORT = OSM
    GOOGLE_SHEETS_EXPORT = 'gsheets'

    EXPORT_MIMES = {
        'xls': 'vnd.ms-excel',
        'xlsx': 'vnd.openxmlformats',
        'csv': 'csv',
        'zip': 'zip',
        'csv_zip': 'zip',
        'sav_zip': 'zip',
        'sav': 'sav',
        'kml': 'vnd.google-earth.kml+xml',
        OSM: OSM
    }

    EXPORT_TYPES = [
        (XLS_EXPORT, 'Excel'),
        (CSV_EXPORT, 'CSV'),
        (ZIP_EXPORT, 'ZIP'),
        (KML_EXPORT, 'kml'),
        (CSV_ZIP_EXPORT, 'CSV ZIP'),
        (SAV_ZIP_EXPORT, 'SAV ZIP'),
        (SAV_EXPORT, 'SAV'),
        (EXTERNAL_EXPORT, 'Excel'),
        (OSM, OSM),
        (GOOGLE_SHEETS_EXPORT, 'Google Sheets'),
    ]

    EXPORT_OPTION_FIELDS = [
        "binary_select_multiples",
        "dataview_pk",
        "group_delimiter",
        "include_images",
        "include_labels",
        "include_labels_only",
        "include_hxl",
        "language",
        "query",
        "remove_group_name",
        "show_choice_labels",
        "include_reviews",
        "split_select_multiples",
        "value_select_multiples",
        "win_excel_utf8",
    ]

    EXPORT_TYPE_DICT = dict(export_type for export_type in EXPORT_TYPES)

    PENDING = async_status.PENDING
    SUCCESSFUL = async_status.SUCCESSFUL
    FAILED = async_status.FAILED

    # max no. of export files a user can keep
    MAX_EXPORTS = 10

    # Required fields
    xform = models.ForeignKey('logger.XForm')
    export_type = models.CharField(
        max_length=10, choices=EXPORT_TYPES, default=XLS_EXPORT
    )

    # optional fields
    created_on = models.DateTimeField(auto_now_add=True)
    filename = models.CharField(max_length=255, null=True, blank=True)

    # need to save an the filedir since when an xform is deleted, it cascades
    # its exports which then try to delete their files and try to access the
    # deleted xform - bad things happen
    filedir = models.CharField(max_length=255, null=True, blank=True)
    task_id = models.CharField(max_length=255, null=True, blank=True)
    # time of last submission when this export was created
    time_of_last_submission = models.DateTimeField(null=True, default=None)
    # status
    internal_status = models.SmallIntegerField(default=PENDING)
    export_url = models.URLField(null=True, default=None)

    options = JSONField(default=dict, null=False)
    error_message = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        app_label = "viewer"
        unique_together = (("xform", "filename"),)

    def __str__(self):
        return u'%s - %s (%s)' % (self.export_type, self.xform, self.filename)

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        if not self.pk and self.xform:
            # if new, check if we've hit our limit for exports for this form,
            # if so, delete oldest
            num_existing_exports = Export.objects.filter(
                xform=self.xform, export_type=self.export_type).count()

            if num_existing_exports >= self.MAX_EXPORTS:
                Export._delete_oldest_export(self.xform, self.export_type)

            # update time_of_last_submission with
            # xform.time_of_last_submission_update
            # pylint: disable=E1101
            self.time_of_last_submission = self.xform.\
                time_of_last_submission_update()
        if self.filename:
            self.internal_status = Export.SUCCESSFUL
        super(Export, self).save(*args, **kwargs)

    @classmethod
    def _delete_oldest_export(cls, xform, export_type):
        oldest_export = Export.objects.filter(
            xform=xform, export_type=export_type).order_by('created_on')[0]
        oldest_export.delete()

    @property
    def is_pending(self):
        """
        Return True if an export status is pending.
        """
        return self.status == Export.PENDING

    @property
    def is_successful(self):
        """
        Return True if an export status successful.
        """
        return self.status == Export.SUCCESSFUL

    @property
    def status(self):
        """
        Return the status [FAILED|PENDING|SUCCESSFUL] of an export.
        """
        if self.filename:
            # need to have this since existing models will have their
            # internal_status set to PENDING - the default
            return Export.SUCCESSFUL
        elif self.internal_status == Export.FAILED:
            return Export.FAILED

        return Export.PENDING

    def set_filename(self, filename):
        """
        Set the filename of an export and mark internal_status as
        Export.SUCCESSFUL.
        """
        self.filename = filename
        self.internal_status = Export.SUCCESSFUL
        self._update_filedir()

    def _update_filedir(self):
        if not self.filename:
            raise AssertionError()
        # pylint: disable=E1101
        self.filedir = os.path.join(self.xform.user.username,
                                    'exports', self.xform.id_string,
                                    self.export_type)

    @property
    def filepath(self):
        """
        Return the file path of an export file, None if the file does not
        exist.
        """
        if self.filedir and self.filename:
            return os.path.join(self.filedir, self.filename)
        return None

    @property
    def full_filepath(self):
        """
        Return the full filepath of an export file, None if the file does not
        exist.
        """
        if self.filepath:
            default_storage = get_storage_class()()
            try:
                return default_storage.path(self.filepath)
            except NotImplementedError:
                # read file from s3
                _name, ext = os.path.splitext(self.filepath)
                tmp = NamedTemporaryFile(suffix=ext, delete=False)
                f = default_storage.open(self.filepath)
                tmp.write(f.read())
                tmp.close()
                return tmp.name
        return None

    @classmethod
    def exports_outdated(cls, xform, export_type, options=None):
        """
        Return True if export is outdated or there is no export matching the
        export_type with the specified options.
        """
        if options is None:
            options = {}
        # get newest export for xform
        try:
            export_options = get_export_options_query_kwargs(options)
            latest_export = Export.objects.filter(
                xform=xform, export_type=export_type,
                internal_status__in=[Export.SUCCESSFUL, Export.PENDING],
                **export_options).latest('created_on')
        except cls.DoesNotExist:
            return True
        else:
            if latest_export.time_of_last_submission is not None \
                    and xform.time_of_last_submission_update() is not None:
                return latest_export.time_of_last_submission <\
                    xform.time_of_last_submission_update()

            # return true if we can't determine the status, to force
            # auto-generation
            return True

    @classmethod
    def is_filename_unique(cls, xform, filename):
        """
        Return True if the filename is unique.
        """
        return Export.objects.filter(
            xform=xform, filename=filename).count() == 0


post_delete.connect(export_delete_callback, sender=Export)
