#!/usr/bin/env python
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.storage import get_storage_class
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.image_tools import resize, resize_local_env
from onadata.libs.utils.model_tools import queryset_iterator
from onadata.libs.utils.viewer_tools import get_path

THUMB_CONF = settings.THUMB_CONF


class Command(BaseCommand):
    help = ugettext_lazy("Creates thumbnails for "
                         "all form images and stores them")

    def add_arguments(self, parser):
        parser.add_argument(
            '-u',
            '--username',
            help=ugettext_lazy("Username of the form user"))
        parser.add_argument(
            '-i', '--id_string', help=ugettext_lazy("id string of the form"))
        parser.add_argument(
            '-f',
            '--force',
            action='store_false',
            help=ugettext_lazy("regenerate thumbnails if they exist."))

    def handle(self, *args, **options):
        attachments_qs = Attachment.objects.select_related(
            'instance', 'instance__xform')
        if options.get('username'):
            username = options.get('username')
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                raise CommandError(
                    "Error: username %(username)s does not exist" %
                    {'username': username})
            attachments_qs = attachments_qs.filter(instance__user=user)
        if options.get('id_string'):
            id_string = options.get('id_string')
            try:
                xform = XForm.objects.get(id_string=id_string)
            except XForm.DoesNotExist:
                raise CommandError(
                    "Error: Form with id_string %(id_string)s does not exist" %
                    {'id_string': id_string})
            attachments_qs = attachments_qs.filter(instance__xform=xform)
        fs = get_storage_class('django.core.files.storage.FileSystemStorage')()
        for att in queryset_iterator(attachments_qs):
            filename = att.media_file.name
            default_storage = get_storage_class()()
            full_path = get_path(filename,
                                 settings.THUMB_CONF['small']['suffix'])
            if options.get('force') is not None:
                for s in ['small', 'medium', 'large']:
                    fp = get_path(filename, settings.THUMB_CONF[s]['suffix'])
                    if default_storage.exists(fp):
                        default_storage.delete(fp)
            if not default_storage.exists(full_path):
                try:
                    if default_storage.__class__ != fs.__class__:
                        resize(filename, att.extension)
                    else:
                        resize_local_env(filename, att.extension)
                    path = get_path(
                        filename, '%s' % THUMB_CONF['small']['suffix'])
                    if default_storage.exists(path):
                        self.stdout.write(
                            _(u'Thumbnails created for %(file)s') %
                            {'file': filename})
                    else:
                        self.stdout.write(
                            _(u'Problem with the file %(file)s') %
                            {'file': filename})
                except (IOError, OSError) as e:
                    self.stderr.write(_(
                        u'Error on %(filename)s: %(error)s')
                        % {'filename': filename, 'error': e})
