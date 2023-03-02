# -*- coding: utf-8 -*-
"""
Image utility functions module.
"""
import logging
import urllib
from datetime import datetime, timedelta
from tempfile import NamedTemporaryFile
from wsgiref.util import FileWrapper

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import get_storage_class
from django.http import HttpResponse, HttpResponseRedirect

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from PIL import Image

from onadata.libs.utils.viewer_tools import get_path


def flat(*nums):
    """Build a tuple of ints from float or integer arguments.
    Useful because PIL crop and resize require integer points.
    source: https://gist.github.com/16a01455
    """

    return tuple(int(round(n)) for n in nums)


def generate_media_download_url(obj, expiration: int = 3600):
    """
    Returns a HTTP response of a media object or a redirect to the image URL for S3 and
    Azure storage objects.
    """
    file_path = obj.media_file.name
    default_storage = get_storage_class()()
    filename = file_path.split("/")[-1]
    content_disposition = urllib.parse.quote(f"attachment; filename={filename}")
    s3_class = None
    azure = None

    try:
        s3_class = get_storage_class("storages.backends.s3boto3.S3Boto3Storage")()
    except ModuleNotFoundError:
        pass

    try:
        azure = get_storage_class("storages.backends.azure_storage.AzureStorage")()
    except ModuleNotFoundError:
        pass

    if isinstance(default_storage, type(s3_class)):
        try:
            url = generate_aws_media_url(file_path, content_disposition, expiration)
        except ClientError as e:
            logging.error(e)
            return None
        else:
            return HttpResponseRedirect(url)

    if isinstance(default_storage, type(azure)):
        media_url = generate_media_url_with_sas(file_path, expiration)
        return HttpResponseRedirect(media_url)

    # pylint: disable=consider-using-with
    file_obj = open(settings.MEDIA_ROOT + file_path, "rb")
    response = HttpResponse(FileWrapper(file_obj), content_type=obj.mimetype)
    response["Content-Disposition"] = content_disposition

    return response


def generate_aws_media_url(
    file_path: str, content_disposition: str, expiration: int = 3600
):
    """Generate S3 URL."""
    s3_class = get_storage_class("storages.backends.s3boto3.S3Boto3Storage")()
    bucket_name = s3_class.bucket.name
    s3_config = Config(
        signature_version=getattr(settings, "AWS_S3_SIGNATURE_VERSION", "s3v4"),
        region_name=getattr(settings, "AWS_S3_REGION_NAME", ""),
    )
    s3_client = boto3.client("s3", config=s3_config)

    # Generate a presigned URL for the S3 object
    return s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket_name,
            "Key": file_path,
            "ResponseContentDisposition": content_disposition,
            "ResponseContentType": "application/octet-stream",
        },
        ExpiresIn=expiration,
    )


def generate_media_url_with_sas(file_path: str, expiration: int = 3600):
    """
    Generate Azure storage URL.
    """
    # pylint: disable=import-outside-toplevel
    from azure.storage.blob import AccountSasPermissions, generate_blob_sas

    account_name = getattr(settings, "AZURE_ACCOUNT_NAME", "")
    container_name = getattr(settings, "AZURE_CONTAINER", "")
    media_url = (
        f"https://{account_name}.blob.core.windows.net/{container_name}/{file_path}"
    )
    sas_token = generate_blob_sas(
        account_name=account_name,
        account_key=getattr(settings, "AZURE_ACCOUNT_KEY", ""),
        container_name=container_name,
        blob_name=file_path,
        permission=AccountSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(seconds=expiration),
    )
    return f"{media_url}?{sas_token}"


def get_dimensions(size, longest_side):
    """Return integer tuple of width and height given size and longest_side length."""
    width, height = size

    if width > height:
        width = longest_side
        height = (height / width) * longest_side
    elif height > width:
        height = longest_side
        width = (width / height) * longest_side
    else:
        height = longest_side
        width = longest_side

    return flat(width, height)


def _save_thumbnails(image, path, size, suffix, extension):
    with NamedTemporaryFile(suffix=f".{extension}") as temp_file:
        default_storage = get_storage_class()()

        try:
            # Ensure conversion to float in operations
            image.thumbnail(get_dimensions(image.size, float(size)), Image.ANTIALIAS)
        except ZeroDivisionError:
            pass

        image.save(temp_file.name)
        default_storage.save(get_path(path, suffix), ContentFile(temp_file.read()))
        temp_file.close()


def resize(filename, extension):
    """Resize an image into multiple sizes."""
    default_storage = get_storage_class()()

    try:
        with default_storage.open(filename) as image_file:
            image = Image.open(image_file)
            conf = settings.THUMB_CONF

            for key in settings.THUMB_ORDER:
                _save_thumbnails(
                    image,
                    filename,
                    conf[key]["size"],
                    conf[key]["suffix"],
                    settings.DEFAULT_IMG_FILE_TYPE if extension == "non" else extension,
                )
    except IOError as exc:
        raise Exception("The image file couldn't be identified") from exc


def resize_local_env(filename, extension):
    """Resize images in a local environment."""
    default_storage = get_storage_class()()
    path = default_storage.path(filename)
    image = Image.open(path)
    conf = settings.THUMB_CONF

    for key in settings.THUMB_ORDER:
        _save_thumbnails(
            image,
            path,
            conf[key]["size"],
            conf[key]["suffix"],
            settings.DEFAULT_IMG_FILE_TYPE if extension == "non" else extension,
        )


def is_azure_storage():
    """Checks if azure storage is in use"""
    default_storage = get_storage_class()()
    azure = None
    try:
        azure = get_storage_class("storages.backends.azure_storage.AzureStorage")()
    except ModuleNotFoundError:
        pass
    return isinstance(default_storage, type(azure))


def image_url(attachment, suffix):
    """Return url of an image given size(@param suffix)
    e.g large, medium, small, or generate required thumbnail
    """
    url = attachment.media_file.url

    if suffix == "original":
        return url

    default_storage = get_storage_class()()
    file_storage = get_storage_class("django.core.files.storage.FileSystemStorage")()

    if suffix in settings.THUMB_CONF:
        size = settings.THUMB_CONF[suffix]["suffix"]
        filename = attachment.media_file.name

        if default_storage.exists(filename):
            if (
                default_storage.exists(get_path(filename, size))
                and default_storage.size(get_path(filename, size)) > 0
            ):
                file_path = get_path(filename, size)
                url = (
                    generate_media_url_with_sas(file_path)
                    if is_azure_storage()
                    else default_storage.url(file_path)
                )
            else:
                if default_storage.__class__ != file_storage.__class__:
                    resize(filename, extension=attachment.extension)
                else:
                    resize_local_env(filename, extension=attachment.extension)

                return image_url(attachment, suffix)
        else:
            return None

    return url
