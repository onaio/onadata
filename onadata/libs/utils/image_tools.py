import boto3
import urllib
import logging
from datetime import datetime, timedelta
from tempfile import NamedTemporaryFile

from PIL import Image
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import get_storage_class
from django.http import HttpResponse, HttpResponseRedirect
from botocore.exceptions import ClientError
from wsgiref.util import FileWrapper

from onadata.libs.utils.viewer_tools import get_path


def flat(*nums):
    """Build a tuple of ints from float or integer arguments.
    Useful because PIL crop and resize require integer points.
    source: https://gist.github.com/16a01455
    """

    return tuple(int(round(n)) for n in nums)


def generate_media_download_url(obj, expiration: int = 3600):
    file_path = obj.media_file.name
    default_storage = get_storage_class()()
    filename = file_path.split("/")[-1]
    s3 = None
    azure = None

    try:
        s3 = get_storage_class("storages.backends.s3boto3.S3Boto3Storage")()
    except ModuleNotFoundError:
        pass

    try:
        azure = get_storage_class("storages.backends.azure_storage.AzureStorage")()
    except ModuleNotFoundError:
        if s3 is None:
            return HttpResponseRedirect(obj.media_file.url)

    content_disposition = urllib.parse.quote(f"attachment; filename={filename}")
    if isinstance(default_storage, type(s3)):
        try:
            url = generate_aws_media_url(file_path, content_disposition, expiration)
        except ClientError as e:
            logging.error(e)
            return None
        else:
            return HttpResponseRedirect(url)
    elif isinstance(default_storage, type(azure)):
        media_url = generate_media_url_with_sas(file_path, expiration)
        return HttpResponseRedirect(media_url)
    else:
        file_obj = open(settings.MEDIA_ROOT + file_path, "rb")
        response = HttpResponse(FileWrapper(file_obj), content_type=obj.mimetype)
        response["Content-Disposition"] = content_disposition

        return response


def generate_aws_media_url(
    file_path: str, content_disposition: str, expiration: int = 3600
):
    s3 = get_storage_class("storage.backends.s3boto3.S3Boto3Storage")()
    bucket_name = s3.bucket.name
    s3_client = boto3.client("s3")

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
        expiry=datetime.utcnow() + timedelta(seconds=expiration),
    )
    return f"{media_url}?{sas_token}"


def get_dimensions(size, longest_side):
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
    nm = NamedTemporaryFile(suffix=".%s" % extension)
    default_storage = get_storage_class()()

    try:
        # Ensure conversion to float in operations
        image.thumbnail(get_dimensions(image.size, float(size)), Image.ANTIALIAS)
    except ZeroDivisionError:
        pass

    image.save(nm.name)
    default_storage.save(get_path(path, suffix), ContentFile(nm.read()))
    nm.close()


def resize(filename, extension):
    if extension == "non":
        extension = settings.DEFAULT_IMG_FILE_TYPE
    default_storage = get_storage_class()()

    try:
        with default_storage.open(filename) as image_file:
            image = Image.open(image_file)
            conf = settings.THUMB_CONF

            for key in settings.THUMB_ORDER:
                _save_thumbnails(
                    image, filename, conf[key]["size"], conf[key]["suffix"], extension
                )
    except IOError:
        raise Exception("The image file couldn't be identified")


def resize_local_env(filename, extension):
    if extension == "non":
        extension = settings.DEFAULT_IMG_FILE_TYPE
    default_storage = get_storage_class()()
    path = default_storage.path(filename)
    image = Image.open(path)
    conf = settings.THUMB_CONF

    [
        _save_thumbnails(image, path, conf[key]["size"], conf[key]["suffix"], extension)
        for key in settings.THUMB_ORDER
    ]


def image_url(attachment, suffix):
    """Return url of an image given size(@param suffix)
    e.g large, medium, small, or generate required thumbnail
    """
    url = attachment.media_file.url
    azure = None

    try:
        azure = get_storage_class("storages.backends.azure_storage.AzureStorage")()
    except ModuleNotFoundError:
        pass

    if suffix == "original":
        return url
    else:
        default_storage = get_storage_class()()
        fs = get_storage_class("django.core.files.storage.FileSystemStorage")()

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
                        if isinstance(default_storage, type(azure))
                        else default_storage.url(file_path)
                    )
                else:
                    if default_storage.__class__ != fs.__class__:
                        resize(filename, extension=attachment.extension)
                    else:
                        resize_local_env(filename, extension=attachment.extension)

                    return image_url(attachment, suffix)
            else:
                return None

    return url
