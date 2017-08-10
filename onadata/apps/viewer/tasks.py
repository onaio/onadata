import sys
from datetime import timedelta

from celery import task
from celery.task.schedules import crontab
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from requests import ConnectionError

from onadata.apps.viewer.models.export import Export
from onadata.libs.exceptions import NoRecordsFoundError
from onadata.libs.utils.common_tools import get_boolean_value, report_exception
from onadata.libs.utils.export_tools import (
    generate_attachments_zip_export, generate_export, generate_external_export,
    generate_kml_export, generate_osm_export)

EXPORT_QUERY_KEY = 'query'


def _get_export_object(id):
    try:
        return Export.objects.get(id=id)
    except Export.DoesNotExist:
        if len(getattr(settings, 'SLAVE_DATABASES', [])):
            from multidb.pinning import use_master

            with use_master:
                return Export.objects.get(id=id)

    raise Export.DoesNotExist


def _get_export_details(username, id_string, export_id):
    details = {
        'export_id': export_id,
        'username': username,
        'id_string': id_string
    }
    return details


def create_async_export(xform, export_type, query, force_xlsx, options=None):
    username = xform.user.username
    id_string = xform.id_string

    def _create_export(xform, export_type, options):
        export_options = {
            key: get_boolean_value(value, default=True)
            for key, value in options.iteritems()
            if key in Export.EXPORT_OPTION_FIELDS
        }

        return Export.objects.create(
            xform=xform, export_type=export_type, options=export_options)

    export = _create_export(xform, export_type, options)
    result = None

    export_id = export.id

    options.update({
        'username': username,
        'id_string': id_string,
        'export_id': export_id,
        'query': query,
        'force_xlsx': force_xlsx
    })

    export_types = {
        Export.XLS_EXPORT: create_xls_export,
        Export.GOOGLE_SHEETS_EXPORT: create_google_sheet_export,
        Export.CSV_EXPORT: create_csv_export,
        Export.CSV_ZIP_EXPORT: create_csv_zip_export,
        Export.SAV_ZIP_EXPORT: create_sav_zip_export,
        Export.ZIP_EXPORT: create_zip_export,
        Export.KML_EXPORT: create_kml_export,
        Export.OSM_EXPORT: create_osm_export,
        Export.EXTERNAL_EXPORT: create_external_export
    }

    # start async export
    if export_type in export_types:
        result = export_types[export_type].apply_async((), kwargs=options)
    else:
        raise Export.ExportTypeError

    if result:
        # when celery is running eager, the export has been generated by the
        # time we get here so lets retrieve the export object a fresh before we
        # save
        if settings.CELERY_ALWAYS_EAGER:
            export = get_object_or_404(Export, id=export.id)
        export.task_id = result.task_id
        export.save()
        return export, result
    return None


@task(track_started=True)
def create_xls_export(username, id_string, export_id, **options):
    # we re-query the db instead of passing model objects according to
    # http://docs.celeryproject.org/en/latest/userguide/tasks.html#state
    force_xlsx = options.get("force_xlsx", True)
    options["extension"] = 'xlsx' if force_xlsx else 'xls'

    try:
        export = _get_export_object(id=export_id)
    except Export.DoesNotExist:
        # no export for this ID return None.
        return None

    # though export is not available when for has 0 submissions, we
    # catch this since it potentially stops celery

    try:
        gen_export = generate_export(Export.XLS_EXPORT, export.xform,
                                     export_id, options)
    except (Exception, NoRecordsFoundError) as e:
        export.internal_status = Export.FAILED
        export.save()
        # mail admins
        details = _get_export_details(username, id_string, export_id)

        report_exception("XLS Export Exception: Export ID - "
                         "%(export_id)s, /%(username)s/%(id_string)s" %
                         details, e, sys.exc_info())
        # Raise for now to let celery know we failed
        # - doesnt seem to break celery`
        raise
    else:
        return gen_export.id


@task(track_started=True)
def create_csv_export(username, id_string, export_id, **options):
    # we re-query the db instead of passing model objects according to
    # http://docs.celeryproject.org/en/latest/userguide/tasks.html#state
    export = _get_export_object(id=export_id)

    try:
        # though export is not available when for has 0 submissions, we
        # catch this since it potentially stops celery
        gen_export = generate_export(Export.CSV_EXPORT, export.xform,
                                     export_id, options)
    except NoRecordsFoundError:
        # not much we can do but we don't want to report this as the user
        # should not even be on this page if the survey has no records
        export.internal_status = Export.FAILED
        export.save()
    except Exception as e:
        export.internal_status = Export.FAILED
        export.save()
        # mail admins
        details = _get_export_details(username, id_string, export_id)

        report_exception("CSV Export Exception: Export ID - "
                         "%(export_id)s, /%(username)s/%(id_string)s" %
                         details, e, sys.exc_info())
        raise
    else:
        return gen_export.id


@task(track_started=True)
def create_kml_export(username, id_string, export_id, **options):
    # we re-query the db instead of passing model objects according to
    # http://docs.celeryproject.org/en/latest/userguide/tasks.html#state

    export = _get_export_object(id=export_id)
    try:
        # though export is not available when for has 0 submissions, we
        # catch this since it potentially stops celery
        gen_export = generate_kml_export(
            Export.KML_EXPORT,
            username,
            id_string,
            export_id,
            options,
            xform=export.xform)
    except (Exception, NoRecordsFoundError) as e:
        export.internal_status = Export.FAILED
        export.save()
        # mail admins
        details = _get_export_details(username, id_string, export_id)
        report_exception("KML Export Exception: Export ID - "
                         "%(export_id)s, /%(username)s/%(id_string)s" %
                         details, e, sys.exc_info())
        raise
    else:
        return gen_export.id


@task(track_started=True)
def create_osm_export(username, id_string, export_id, **options):
    # we re-query the db instead of passing model objects according to
    # http://docs.celeryproject.org/en/latest/userguide/tasks.html#state

    export = _get_export_object(id=export_id)
    try:
        # though export is not available when for has 0 submissions, we
        # catch this since it potentially stops celery
        gen_export = generate_osm_export(
            Export.OSM_EXPORT,
            username,
            id_string,
            export_id,
            options,
            xform=export.xform)
    except (Exception, NoRecordsFoundError) as e:
        export.internal_status = Export.FAILED
        export.save()
        # mail admins
        details = _get_export_details(username, id_string, export_id)
        report_exception("OSM Export Exception: Export ID - "
                         "%(export_id)s, /%(username)s/%(id_string)s" %
                         details, e, sys.exc_info())
        raise
    else:
        return gen_export.id


@task(track_started=True)
def create_zip_export(username, id_string, export_id, **options):
    export = _get_export_object(id=export_id)
    try:
        gen_export = generate_attachments_zip_export(
            Export.ZIP_EXPORT,
            username,
            id_string,
            export_id,
            options,
            xform=export.xform)
    except (Exception, NoRecordsFoundError) as e:
        export.internal_status = Export.FAILED
        export.save()
        # mail admins
        details = _get_export_details(username, id_string, export_id)
        report_exception("Zip Export Exception: Export ID - "
                         "%(export_id)s, /%(username)s/%(id_string)s" %
                         details, e)
        raise
    else:
        if not settings.TESTING_MODE:
            delete_export.apply_async(
                (), {'export_id': gen_export.id},
                countdown=settings.ZIP_EXPORT_COUNTDOWN)
        return gen_export.id


@task(track_started=True)
def create_csv_zip_export(username, id_string, export_id, **options):
    export = _get_export_object(id=export_id)
    options["extension"] = Export.ZIP_EXPORT
    try:
        # though export is not available when for has 0 submissions, we
        # catch this since it potentially stops celery
        gen_export = generate_export(Export.CSV_ZIP_EXPORT, export.xform,
                                     export_id, options)
    except (Exception, NoRecordsFoundError) as e:
        export.internal_status = Export.FAILED
        export.save()
        # mail admins
        details = _get_export_details(username, id_string, export_id)
        report_exception("CSV ZIP Export Exception: Export ID - "
                         "%(export_id)s, /%(username)s/%(id_string)s" %
                         details, e, sys.exc_info())
        raise
    else:
        return gen_export.id


@task(track_started=True)
def create_sav_zip_export(username, id_string, export_id, **options):
    export = _get_export_object(id=export_id)
    options["extension"] = Export.ZIP_EXPORT
    try:
        # though export is not available when for has 0 submissions, we
        # catch this since it potentially stops celery
        gen_export = generate_export(Export.SAV_ZIP_EXPORT, export.xform,
                                     export_id, options)
    except (Exception, NoRecordsFoundError, TypeError) as e:
        export.internal_status = Export.FAILED
        export.save()
        # mail admins
        details = _get_export_details(username, id_string, export_id)
        report_exception("SAV ZIP Export Exception: Export ID - "
                         "%(export_id)s, /%(username)s/%(id_string)s" %
                         details, e, sys.exc_info())
        raise
    else:
        return gen_export.id


@task(track_started=True)
def create_external_export(username, id_string, export_id, **options):
    export = get_object_or_404(Export, id=export_id)

    try:
        # though export is not available when for has 0 submissions, we
        # catch this since it potentially stops celery
        gen_export = generate_external_export(
            Export.EXTERNAL_EXPORT,
            username,
            id_string,
            export_id,
            options,
            xform=export.xform)
    except (Exception, NoRecordsFoundError, ConnectionError) as e:
        export.internal_status = Export.FAILED
        export.save()
        # mail admins
        details = _get_export_details(username, id_string, export_id)
        report_exception("External Export Exception: Export ID - "
                         "%(export_id)s, /%(username)s/%(id_string)s" %
                         details, e, sys.exc_info())
        raise
    else:
        return gen_export.id


@task(track_started=True)
def create_google_sheet_export(username, id_string, export_id, **options):
    # we re-query the db instead of passing model objects according to
    # http://docs.celeryproject.org/en/latest/userguide/tasks.html#state
    try:
        export = _get_export_object(id=export_id)
        # though export is not available when for has 0 submissions, we
        # catch this since it potentially stops celery
        gen_export = generate_export(Export.GOOGLE_SHEETS_EXPORT, export.xform,
                                     export_id, options)
    except (Exception, NoRecordsFoundError, ConnectionError) as e:
        export.internal_status = Export.FAILED
        export.save()
        # mail admins
        details = _get_export_details(username, id_string, export_id)
        report_exception("Google Export Exception: Export ID - "
                         "%(export_id)s, /%(username)s/%(id_string)s" %
                         details, e, sys.exc_info())
        raise
    else:
        return gen_export.id


@task(track_started=True)
def delete_export(export_id):
    try:
        export = _get_export_object(id=export_id)
    except Export.DoesNotExist:
        pass
    else:
        export.delete()
        return True
    return False


@task.periodic_task(
    run_every=(crontab(hour='*/7')),
    ignore_result=True
)
def mark_expired_pending_exports_as_failed():
    """
    Exports that have not completed within a set time should be marked as
    failed
    """
    # import pdb; pdb.set_trace()
    task_lifespan = settings.EXPORT_TASK_LIFESPAN
    time_threshold = timezone.now() - timedelta(hours=task_lifespan)
    exports = Export.objects.filter(internal_status=Export.PENDING,
                                    created_on__lt=time_threshold)
    exports.update(internal_status=Export.FAILED)


@task.periodic_task(
    run_every=(crontab(hour='*/7')),
    ignore_result=True
)
def delete_old_failed_exports():
    """
    Delete old failed exports
    """
    task_lifespan = settings.EXPORT_TASK_LIFESPAN
    time_threshold = timezone.now() - timedelta(hours=task_lifespan)
    exports = Export.objects.filter(internal_status=Export.FAILED,
                                    created_on__lt=time_threshold)
    for export in exports:
        export.delete()
