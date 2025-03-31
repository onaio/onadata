#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
move_media_to_s3 - Moves all XLSForm file from local storage to S3 storage.
"""

import sys

from django.core.files.storage import storages
from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _, gettext_lazy

from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.logger.models.attachment import upload_to as attachment_upload_to
from onadata.apps.logger.models.xform import XForm, upload_to as xform_upload_to


class Command(BaseCommand):
    """Moves all XLSForm file from local storage to S3 storage."""

    help = gettext_lazy(
        "Moves all attachments and xls files "
        "to s3 from the local file system storage."
    )

    # pylint: disable=unused-argument
    def handle(self, *args, **kwargs):
        """Moves all XLSForm file from local storage to S3 storage."""
        local_fs = storages.create_storage(
            {"BACKEND": "django.core.files.storage.FileSystemStorage"}
        )
        s3_fs = storages.create_storage(
            {"BACKEND": "storages.backends.s3boto.S3BotoStorage"}
        )

        default_storage = storages["default"]
        if default_storage.__class__ != s3_fs.__class__:
            self.stderr.write(
                _(
                    "You must first set your default storage to s3 in your "
                    "local_settings.py file."
                )
            )
            sys.exit(1)

        classes_to_move = [
            (Attachment, "media_file", attachment_upload_to),
            (XForm, "xls", xform_upload_to),
        ]

        for cls, file_field, upload_to in classes_to_move:
            self.stdout.write(_("Moving %(class)ss to s3...") % {"class": cls.__name__})
            for i in cls.objects.all():
                media_file = getattr(i, file_field)
                old_filename = media_file.name
                if (
                    old_filename
                    and local_fs.exists(old_filename)
                    and not s3_fs.exists(upload_to(i, old_filename))
                ):
                    media_file.name.save(
                        local_fs.path(old_filename),
                        local_fs.open(local_fs.path(old_filename)),
                    )
                    self.stdout.write(
                        _("\t+ '%(fname)s'\n\t---> '%(url)s'")
                        % {
                            "fname": local_fs.path(old_filename),
                            "url": media_file.url,
                        }
                    )
                else:
                    exists_locally = local_fs.exists(old_filename)
                    exists_s3 = not s3_fs.exists(upload_to(i, old_filename))
                    self.stderr.write(
                        f"\t- (old_filename={old_filename}, "
                        f"fs.exists(old_filename)={exists_locally},"
                        f" not s3.exist s3upload_to(i, old_filename))={exists_s3})"
                    )
