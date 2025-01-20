#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4
# -*- coding: utf-8 -*-
"""
change_s3_media_permissions - makes all s3 files private.
"""

from django.core.files.storage import storages
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy


class Command(BaseCommand):
    """Makes all s3 files private"""

    help = gettext_lazy("Makes all s3 files private")

    def handle(self, *args, **kwargs):
        """Makes all s3 files private"""
        permissions = ("private", "public-read", "authenticated-read")

        if len(args) < 1:
            raise CommandError(_("Missing permission argument"))

        permission = args[0]

        if permission not in permissions:
            raise CommandError(_(f"Expected {' or '.join(permissions)} as permission"))

        s3_storage = storages.create_storage(
            {"BACKEND": "storages.backends.s3boto.S3BotoStorage"}
        )
        all_files = s3_storage.bucket.list()

        num = 0
        for i, a_file in enumerate(all_files):
            a_file.set_acl(permission)
            if i % 1000 == 0:
                self.stdout.write(_(f"{i} file objects processed"))
            num = i

        self.stdout.write(_(f"A total of {num} file objects processed"))
