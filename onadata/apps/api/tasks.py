from celery import task
from celery.result import AsyncResult
from django.core.files.uploadedfile import (InMemoryUploadedFile,
                                            TemporaryUploadedFile)
from django.utils.datastructures import MultiValueDict
from io import BytesIO
from onadata.apps.api import tools


@task()
def publish_xlsform_async(user, post_data, owner, file_data):
    try:
        files = MultiValueDict(
            {u'xls_file':
             (InMemoryUploadedFile(BytesIO(file_data.get('data')), None,
                                   file_data.get('name'),
                                   u'application/vnd.ms-excel',
                                   len(file_data.get('data')), None)
              if file_data.get('data') else
              TemporaryUploadedFile(file_data.get('path'),
                                    u'application/vnd.ms-excel', 0))})

        return tools.do_publish_xlsform(user, post_data, files, owner)
    except e:
        return {u'error': str(e)}


def get_async_creation_status(job_uuid):
    """ Gets form creation progress or result """

    if not job_uuid:
        return {u'error': u'Empty job uuid'}

    job = AsyncResult(job_uuid)
    result = (job.result or job.state)
    if isinstance(result, basestring):
        return {'JOB_STATUS': result}

    return result
