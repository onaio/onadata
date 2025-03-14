# -*- coding: utf-8 -*-
"""
Image utility functions module.
"""

from tempfile import NamedTemporaryFile
from urllib.parse import quote
from wsgiref.util import FileWrapper

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.http import HttpResponse, HttpResponseRedirect

from PIL import Image

from onadata.libs.utils.logger_tools import (
    generate_media_url_with_sas,
    get_storages_media_download_url,
)
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
    filename = quote(file_path.split("/")[-1])
    # The filename is enclosed in quotes because it ensures that special characters,
    # spaces, or punctuation in the filename are correctly interpreted by browsers
    # and clients. This is particularly important for filenames that may contain
    # spaces or non-ASCII characters.
    content_disposition = f'attachment; filename="{filename}"'
    download_url = get_storages_media_download_url(
        file_path, content_disposition, expiration
    )
    if download_url is not None:
        return HttpResponseRedirect(download_url)

    # pylint: disable=consider-using-with
    file_obj = open(settings.MEDIA_ROOT + file_path, "rb")
    response = HttpResponse(FileWrapper(file_obj), content_type=obj.mimetype)
    response["Content-Disposition"] = content_disposition

    return response


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


def _save_thumbnails(image, filename, size, suffix, extension):
    with NamedTemporaryFile(suffix=f".{extension}") as temp_file:
        default_storage = storages["default"]

        try:
            # Ensure conversion to float in operations
            # pylint: disable=no-member
            image.thumbnail(get_dimensions(image.size, float(size)), Image.LANCZOS)
        except ZeroDivisionError:
            pass

        image.save(temp_file.name)
        default_storage.save(get_path(filename, suffix), ContentFile(temp_file.read()))
        temp_file.close()


def resize(filename, extension):
    """Resize an image into multiple sizes."""
    default_storage = storages["default"]

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
        raise ValueError("The image file couldn't be identified") from exc


def resize_local_env(filename, extension):
    """Resize images in a local environment."""
    default_storage = storages["default"]
    path = default_storage.path(filename)
    image = Image.open(path)
    conf = settings.THUMB_CONF

    for key in settings.THUMB_ORDER:
        _save_thumbnails(
            image,
            filename,
            conf[key]["size"],
            conf[key]["suffix"],
            settings.DEFAULT_IMG_FILE_TYPE if extension == "non" else extension,
        )


def is_azure_storage():
    """Checks if azure storage is in use"""
    default_storage = storages["default"]
    azure = None
    try:
        azure = storages.create_storage(
            {"BACKEND": "storages.backends.azure_storage.AzureStorage"}
        )
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

    default_storage = storages["default"]
    file_storage = storages.create_storage(
        {"BACKEND": "django.core.files.storage.FileSystemStorage"}
    )

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
