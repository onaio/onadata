# -*- coding -*-
"""
webhooks command.
"""

from django.core.management.base import BaseCommand
from django.utils.translation import ugettext as _

from onadata.apps.logger.models import XForm
from onadata.apps.restservice.tasks import call_service_async
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    """
    webhooks command.
    """
    help = _("Webhooks command to resend submissions.")

    def add_arguments(self, parser):
        parser.add_argument('action', help=_("The action to take."))
        parser.add_argument(
            'formid', help=_("The form id to apply the action."))

    def handle(self, *args, **options):
        action = options.get('action')
        xform = XForm.objects.get(pk=options.get('formid'))
        self.stdout.write(
            _("Going to resend %(no_of_submissions)d submissions for the"
              " form %(xform)s." % {
                  'no_of_submissions': xform.instances.count(),
                  'xform': xform
              }))

        submissions = xform.instances.filter(deleted_at__isnull=True)
        if action == 'resend':
            for i in queryset_iterator(submissions):
                call_service_async.delay(i)
        elif action == 'googlesheets':
            try:
                from google_export.signals import google_sync_submissions
            except ImportError:
                pass
            else:
                for i in queryset_iterator(submissions):
                    google_sync_submissions(i.parsed_instance, False)
        else:
            self.stdout.write(
                _("Unknown action %(action)s." % {'action': action}))
