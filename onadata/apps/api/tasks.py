import os
import sys
from builtins import str
from io import BytesIO
from past.builtins import basestring

from celery import task
from celery.result import AsyncResult
from django.core.files.uploadedfile import (InMemoryUploadedFile,
                                            TemporaryUploadedFile)
from django.utils.datastructures import MultiValueDict
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from onadata.apps.api import tools
from onadata.apps.logger.models.xform import XForm


def recreate_tmp_file(name, path, mime_type):
    tmp_file = TemporaryUploadedFile(name, mime_type, 0, None)
    tmp_file.file = open(path)
    tmp_file.size = os.fstat(tmp_file.fileno()).st_size
    return tmp_file


@task(bind=True)
def publish_xlsform_async(self, user, post_data, owner, file_data):
    try:
        files = MultiValueDict()
        files[u'xls_file'] = \
            (InMemoryUploadedFile(
                BytesIO(file_data.get('data')), None,
                file_data.get('name'), u'application/octet-stream',
                len(file_data.get('data')), None)
             if file_data.get('data') else
             recreate_tmp_file(file_data.get('name'),
                               file_data.get('path'),
                               u'application/octet-stream'))

        survey = tools.do_publish_xlsform(user, post_data, files, owner)

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


@task()
def delete_xform_async(xform_id):
    """Soft delete an XForm asynchrounous task"""
    xform = XForm.objects.get(pk=xform_id)
    xform.soft_delete()


def get_async_status(job_uuid):
    """ Gets progress status or result """

    if not job_uuid:
        return {u'error': u'Empty job uuid'}

    job = AsyncResult(job_uuid)
    result = job.result or job.state
    if isinstance(result, basestring):
        return {'JOB_STATUS': result}

    return result


@task()
def send_verification_email(email, message_txt, subject):
    """
    Sends a verification email
    """
    if any(a in [None, ''] for a in [email, message_txt, subject]):
        raise ValueError(
            "email, message_txt amd subject arguments are ALL required."
        )

    from_email = settings.DEFAULT_FROM_EMAIL
    email_message = EmailMultiAlternatives(
        subject,
        message_txt,
        from_email,
        [email]
    )

    email_message.send()
