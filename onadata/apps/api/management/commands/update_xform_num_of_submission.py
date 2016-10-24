from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from optparse import make_option

from onadata.apps.logger.models import XForm
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    help = _(u"Update xform number of submission")
    option_list = BaseCommand.option_list + (
        make_option('--xform', '-f',
                    action='store_true',
                    dest='xform_id',
                    default=False,
                    help='Xform id to update'),
        )

    def handle(self, *args, **options):
        self.stdout.write("Updating xform number of submission", ending='\n')

        xform_id = None
        if len(args) > 0:
            xform_id = args[0]

        if xform_id:
            xforms = XForm.objects.filter(pk=xform_id)

        else:
            xforms = XForm.objects.all().order_by('id')

        for xform in queryset_iterator(xforms):
            self.stdout.write("Updating xform number of submission - {}"
                              .format(xform.id), ending='\n')
            xform.submission_count(force_update=True)

        self.stdout.write("Updating xform number of submission DONE",
                          ending='\n')
