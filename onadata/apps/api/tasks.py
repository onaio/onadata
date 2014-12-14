import os
import sys
from celery import task
from celery.result import AsyncResult
from django.core.files.uploadedfile import (InMemoryUploadedFile,
                                            TemporaryUploadedFile)
from django.utils.datastructures import MultiValueDict
from io import BytesIO
from onadata.apps.api import tools


def recreate_tmp_file(name, path, mime_type):
    tmp_file = TemporaryUploadedFile(name, mime_type, 0, None)
    tmp_file.file = open(path)
    tmp_file.size = os.fstat(tmp_file.fileno()).st_size
    return tmp_file


@task()
def publish_xlsform_async(user, post_data, owner, file_data):
    try:
        files = MultiValueDict()
        files[u'xls_file'] = \
            (InMemoryUploadedFile(
                BytesIO(file_data.get('data')), None,
                file_data.get('name'), u'application/octet-stream',
                len(file_data.get('data')), None)
             if file_data.get('data') else
             recreate_tmp_file(
                file_data.get('name'), file_data.get('path'),
                u'application/octet-stream'))

        return tools.do_publish_xlsform(user, post_data, files, owner)
    except:
        e = sys.exc_info()[0]
        return {u'error': str(e)}


def get_async_creation_status(job_uuid):
    """ Gets form creation progress or result """

    if not job_uuid:
        return {u'error': u'Empty job uuid'}

    job = AsyncResult(job_uuid)
    result = job.result or job.state
    if isinstance(result, basestring):
        return {'JOB_STATUS': result}

    return result
