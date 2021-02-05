import boto3
from botocore.exceptions import ClientError
import logging

from django.conf import settings
from django.core.files.storage import get_storage_class
from django.http import HttpResponse, HttpResponseRedirect

from wsgiref.util import FileWrapper


def generate_media_download_url(obj, expiration: int = 3600):
    file_path = obj.media_file.name
    default_storage = get_storage_class()()
    filename = file_path.split("/")[-1]

    try:
        s3 = get_storage_class('storages.backends.s3boto3.S3Boto3Storage')()
    except Exception:
        return obj.media_file.url

    if default_storage.__class__ != s3.__class__:
        file_obj = open(settings.MEDIA_ROOT + file_path, 'rb')
        response = HttpResponse(FileWrapper(file_obj),
                                content_type=obj.mimetype)
        response['Content-Disposition'] = 'attachment; filename=' + filename

        return response

    else:
        try:
            bucket_name = s3.bucket.name
            s3_client = boto3.client('s3')

            # Generate a presigned URL for the S3 object
            response = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': file_path,
                    'ResponseContentDisposition':
                    'attachment;filename={}'.format(filename),
                    'ResponseContentType': 'application/octet-stream', },
                ExpiresIn=expiration)
        except ClientError as e:
            logging.error(e)
            return None

        return HttpResponseRedirect(response)
