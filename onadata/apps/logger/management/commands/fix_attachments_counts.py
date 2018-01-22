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
from onadata.libs.utils.dict_tools import get_values_matching_key
from onadata.libs.utils.model_tools import queryset_iterator


def get_expected_media(instance):
    """
    Returns a list of expected media files from the submission data.
    """
    if not hasattr(instance, '_expected_media'):
        data = instance.get_dict()
        media_list = []
        if 'encryptedXmlFile' in data and instance.xform.encrypted:
            media_list.append(data['encryptedXmlFile'])
            if 'media' in data:
                media_list.extend([i['media/file'] for i in data['media']])
        else:
            media_xpaths = instance.xform.get_media_survey_xpaths()
            for media_xpath in media_xpaths:
                media_list.extend(
                    get_values_matching_key(data, media_xpath))
        # pylint: disable=protected-access
        instance._expected_media = list(set(media_list))

    return instance._expected_media  # pylint: disable=protected-access


def num_of_media(instance):
    """
    Returns number of media attachments expected in the submission.
    """
    if not hasattr(instance, '_num_of_media'):
        # pylint: disable=protected-access
        instance._num_of_media = len(get_expected_media(instance))

    return instance._num_of_media  # pylint: disable=protected-access


def update_attachment_tracking(instance):
    """
    Takes an Instance object and updates attachment tracking fields
    """
    for attachment in instance.attachments.all():
        attachment.name = os.path.basename(
            get_original_filename(attachment.media_file.name))
        attachment.save()

    instance.total_media = num_of_media(instance)
    instance.media_count = instance.attachments.filter(
        name__in=get_expected_media(instance)
    ).distinct('name').order_by('name').count()
    instance.media_all_received = instance.media_count == instance.total_media
    instance.save(update_fields=['total_media',
                                 'media_count',
                                 'media_all_received'])


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
                    update_attachment_tracking(submission)
                not_processed = xform.instances.filter(
                    media_all_received=False).count()
                self.stdout.write("%s to process %s - %s = %s processed" % (
                    xform, to_process, not_processed,
                    (to_process - not_processed)))
