import logging
import boto3
from botocore.exceptions import ClientError

from django.core.files.storage import get_storage_class


def generate_presigned_download_url(file_path: str, expiration: int = 3600):
 # Generate a presigned URL for the S3 object
    s3 = get_storage_class('storages.backends.s3boto3.S3Boto3Storage')()
    bucket_name = s3.bucket.name
    s3_client = boto3.client('s3')

    try:
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': bucket_name,
                                                            'Key': file_path,
                                                            'ResponseContentDisposition': 'attachment;filename={}'.format(filename),
                                                            'ResponseContentType': 'application/octet-stream',},
                                                    ExpiresIn=expiration)
    except ClientError as e:
        logging.error(e)
        return None

    # The response contains the presigned URL
    return response
