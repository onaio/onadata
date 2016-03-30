#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 fileencoding=utf-8

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.translation import ugettext_lazy

from onadata.apps.logger.models import Instance
from onadata.apps.logger.models import XForm
from onadata.apps.main.models import UserProfile


class Command(BaseCommand):
    help = ugettext_lazy("Fix num of submissions")

    def handle(self, *args, **kwargs):
        i = 0
        xform_count = XForm.objects.filter(downloadable=True).count()
        for xform in XForm.objects.filter(downloadable=True).iterator():
            with transaction.atomic():
                instance_count = xform.instances.filter(deleted_at=None)\
                    .count()
                xform.num_of_submissions = instance_count
                xform.save(update_fields=['num_of_submissions'])
            i += 1
            self.stdout.write('Processing {} of {}: {} ({})'.format(
                i, xform_count, xform.id_string, instance_count))

        i = 0
        profile_count = UserProfile.objects.count()
        for profile in UserProfile.objects.select_related('user__username')\
                .iterator():
            with transaction.atomic():
                instance_count = Instance.objects.filter(
                    deleted_at=None,
                    xform__user_id=profile.user_id
                ).count()
                profile.num_of_submissions = instance_count
                profile.save(update_fields=['num_of_submissions'])
            i += 1
            self.stdout.write('Processing {} of {}: {} ({})'.format(
                i, profile_count, profile.user.username, instance_count))
