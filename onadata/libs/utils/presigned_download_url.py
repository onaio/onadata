import boto3
import urllib
import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.core.files.storage import get_storage_class
from django.http import HttpResponse, HttpResponseRedirect
from botocore.exceptions import ClientError

from wsgiref.util import FileWrapper


def generate_media_download_url(obj, expiration: int = 3600):
    file_path = obj.media_file.name
    default_storage = get_storage_class()()
    filename = file_path.split("/")[-1]
    s3 = None
    azure = None

    try:
        s3 = get_storage_class('storages.backends.s3boto3.S3Boto3Storage')()
    except ModuleNotFoundError:
        pass

    try:
        azure = get_storage_class(
            'storages.backends.azure_storage.AzureStorage')()
    except ModuleNotFoundError:
        if s3 is None:
            return HttpResponseRedirect(obj.media_file.url)

    content_disposition = urllib.parse.quote(
        f'attachment; filename={filename}'
    )
    if isinstance(default_storage, type(s3)):
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
    elif isinstance(default_storage, type(azure)):
        from azure.storage.blob import generate_blob_sas, AccountSasPermissions
        account_name = getattr(settings, "AZURE_ACCOUNT_NAME", "")
        container_name = getattr(settings, "AZURE_CONTAINER", "")
        media_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{file_path}"  # noqa
        sas_token = generate_blob_sas(
            account_name=account_name,
            account_key=getattr(settings, "AZURE_ACCOUNT_KEY", ""),
            container_name=container_name,
            blob_name=file_path,
            permission=AccountSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(seconds=expiration)
        )
        return HttpResponseRedirect(f"{media_url}?{sas_token}")
    else:
        file_obj = open(settings.MEDIA_ROOT + file_path, 'rb')
        response = HttpResponse(FileWrapper(file_obj),
                                content_type=obj.mimetype)
        response['Content-Disposition'] = content_disposition

        return response
