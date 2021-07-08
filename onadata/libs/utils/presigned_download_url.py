import boto3
import urllib
import logging
from botocore.exceptions import ClientError

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
    except ModuleNotFoundError:
        return HttpResponseRedirect(obj.media_file.url)

    content_disposition = urllib.parse.quote(
        f'attachment; filename={filename}'
    )
    if not isinstance(default_storage, type(s3)):
        file_obj = open(settings.MEDIA_ROOT + file_path, 'rb')
        response = HttpResponse(FileWrapper(file_obj),
                                content_type=obj.mimetype)
        response['Content-Disposition'] = content_disposition

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
                    'ResponseContentDisposition': content_disposition,
                    'ResponseContentType': 'application/octet-stream', },
                ExpiresIn=expiration)
        except ClientError as e:
            logging.error(e)
            return None

        return HttpResponseRedirect(response)
