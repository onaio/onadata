# -*- coding: utf-8 -*-
"""
create_image_thumbnails - creates thumbnails for all form images and stores them.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.storage import storages
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.image_tools import resize, resize_local_env
from onadata.libs.utils.model_tools import queryset_iterator
from onadata.libs.utils.viewer_tools import get_path

THUMB_CONF = settings.THUMB_CONF

User = get_user_model()


class Command(BaseCommand):
    """Creates thumbnails for all form images and stores them"""

    help = gettext_lazy("Creates thumbnails for all form images and stores them")

    def add_arguments(self, parser):
        parser.add_argument(
            "-u", "--username", help=gettext_lazy("Username of the form user")
        )
        parser.add_argument(
            "-i", "--id_string", help=gettext_lazy("id string of the form")
        )
        parser.add_argument(
            "-f",
            "--force",
            action="store_false",
            help=gettext_lazy("regenerate thumbnails if they exist."),
        )

    # pylint: disable=too-many-branches,too-many-locals
    def handle(self, *args, **options):
        attachments_qs = Attachment.objects.select_related(
            "instance", "instance__xform"
        )
        if options.get("username"):
            username = options.get("username")
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist as error:
                raise CommandError(
                    f"Error: username {username} does not exist"
                ) from error
            attachments_qs = attachments_qs.filter(instance__user=user)
        if options.get("id_string"):
            id_string = options.get("id_string")
            try:
                xform = XForm.objects.get(id_string=id_string)
            except XForm.DoesNotExist as error:
                raise CommandError(
                    f"Error: Form with id_string {id_string} does not exist"
                ) from error
            attachments_qs = attachments_qs.filter(instance__xform=xform)
        file_storage = storages.create_storage(
            {"BACKEND": "django.core.files.storage.FileSystemStorage"}
        )
        for att in queryset_iterator(attachments_qs):
            filename = att.media_file.name
            default_storage = storages["default"]
            full_path = get_path(filename, settings.THUMB_CONF["small"]["suffix"])
            if options.get("force") is not None:
                for suffix in ["small", "medium", "large"]:
                    file_path = get_path(
                        filename, settings.THUMB_CONF[suffix]["suffix"]
                    )
                    if default_storage.exists(file_path):
                        default_storage.delete(file_path)
            if not default_storage.exists(full_path):
                try:
                    if default_storage.__class__ != file_storage.__class__:
                        resize(filename, att.extension)
                    else:
                        resize_local_env(filename, att.extension)
                    path = get_path(filename, f'{THUMB_CONF["small"]["suffix"]}')
                    if default_storage.exists(path):
                        self.stdout.write(_(f"Thumbnails created for {filename}"))
                    else:
                        self.stdout.write(_(f"Problem with the file {filename}"))
                except (IOError, OSError) as error:
                    self.stderr.write(_(f"Error on {filename}: {error}"))
