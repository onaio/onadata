import os
import sys
from builtins import str

from celery.result import AsyncResult
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.contrib.auth.models import User
from django.utils.datastructures import MultiValueDict
from past.builtins import basestring

from onadata.apps.api import tools
from onadata.libs.utils.email import send_generic_email
from onadata.apps.logger.models.xform import XForm
from onadata.celery import app
from onadata.libs.utils.cache_tools import XFORM_SUBMISSION_STAT
from onadata.libs.data.query import get_form_submissions_grouped_by_field


def recreate_tmp_file(name, path, mime_type):
    tmp_file = TemporaryUploadedFile(name, mime_type, 0, None)
    tmp_file.file = open(path)
    tmp_file.size = os.fstat(tmp_file.fileno()).st_size
    return tmp_file


@app.task(bind=True)
def publish_xlsform_async(self, user_id, post_data, owner_id, file_data):
    try:
        files = MultiValueDict()
        files[u'xls_file'] = default_storage.open(file_data.get('path'))

        owner = User.objects.get(id=owner_id)
        if owner_id == user_id:
            user = owner
        else:
            user = User.objects.get(id=user_id)
        survey = tools.do_publish_xlsform(user, post_data, files, owner)
        default_storage.delete(file_data.get('path'))

        if isinstance(survey, XForm):
            return {"pk": survey.pk}

        return survey
    except Exception as exc:
        if isinstance(exc, MemoryError):
            if self.request.retries < 3:
                self.retry(exc=exc, countdown=1)
            else:
                error_message = (
                    u'Service temporarily unavailable, please try to '
                    'publish the form again'
                )
        else:
            error_message = str(sys.exc_info()[1])

        return {u'error': error_message}


@app.task()
def delete_xform_async(xform_id, user_id):
    """Soft delete an XForm asynchrounous task"""
    xform = XForm.objects.get(pk=xform_id)
    user = User.objects.get(pk=user_id)
    xform.soft_delete(user)


@app.task()
def delete_user_async():
    """Delete inactive user accounts"""
    users = User.objects.filter(active=False,
                                username__contains="deleted-at",
                                email__contains="deleted-at")
    for user in users:
        user.delete()


def get_async_status(job_uuid):
    """ Gets progress status or result """

    if not job_uuid:
        return {u'error': u'Empty job uuid'}

    job = AsyncResult(job_uuid)
    result = job.result or job.state
    if isinstance(result, basestring):
        return {'JOB_STATUS': result}

    return result


@app.task()
def send_verification_email(email, message_txt, subject):
    """
    Sends a verification email
    """
    send_generic_email(email, message_txt, subject)


@app.task()
def send_account_lockout_email(email, message_txt, subject):
    send_generic_email(email, message_txt, subject)


@app.task()
def get_form_submissions_stats_async(xform_id, field, name=None,
                                     data_view=None):
    xform = XForm.objects.get(pk=xform_id)
    data = {
        "STATE": "INITIALIZED",
        "DATA": []
    }
    cache.set('{}{}{}{}'.format(XFORM_SUBMISSION_STAT, xform.pk, field, name), data)

    try:
        data = get_form_submissions_grouped_by_field(xform, field, name, data_view)
    except ValueError as e:
            raise exceptions.ParseError(detail=e)
    else:
        if data:
            element = xform.get_survey_element(field)

            if element and element.type in SELECT_FIELDS:
                for record in data:
                    label = xform.get_choice_label(element, record[name])
                    record[name] = label

    data_to_cache = {
            "STATE": "PROCESSED",
            "DATA": data
    }

    # update the cache
    cache.set('{}{}{}{}'.format(XFORM_SUBMISSION_STAT, xform.pk, field, name), data_to_cache)