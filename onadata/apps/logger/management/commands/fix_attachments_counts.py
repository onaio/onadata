# -*- coding=utf-8 -*-
"""
Fix submission media count command.
"""
import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from multidb.pinning import use_master

from onadata.apps.logger.models.attachment import get_original_filename
from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.logger_tools import update_attachment_tracking
from onadata.libs.utils.model_tools import queryset_iterator


def update_attachments(instance):
    """
    Takes an Instance object and updates attachment tracking fields
    """
    for attachment in instance.attachments.all():
        attachment.name = os.path.basename(
            get_original_filename(attachment.media_file.name))
        attachment.save()
    update_attachment_tracking(instance)


class Command(BaseCommand):
    """
    Fix attachments count command.
    """
    args = 'username'
    help = ugettext_lazy("Fix attachments count.")

    def add_arguments(self, parser):
        parser.add_argument('username')

    def handle(self, *args, **options):
        try:
            username = options['username']
        except KeyError:
            raise CommandError(
                _("You must provide the username to publish the form to."))
        # make sure user exists
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(_("The user '%s' does not exist.") % username)

        self.process_attachments(user)

    @use_master
    def process_attachments(self, user):
        """
        Process attachments for submissions where media_all_received is False.
        """
        xforms = XForm.objects.filter(user=user, deleted_at__isnull=True,
                                      downloadable=True)
        for xform in queryset_iterator(xforms):
            submissions = xform.instances.filter(media_all_received=False)
            to_process = submissions.count()
            if to_process:
                for submission in queryset_iterator(submissions):
                    update_attachments(submission)
                not_processed = xform.instances.filter(
                    media_all_received=False).count()
                self.stdout.write("%s to process %s - %s = %s processed" % (
                    xform, to_process, not_processed,
                    (to_process - not_processed)))
