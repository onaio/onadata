from django.core.management.base import BaseCommand
from django.http import HttpRequest
from django.utils.translation import ugettext_lazy

from onadata.apps.logger.models.xform import XForm
from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.utils.viewer_tools import enketo_url, EnketoError
from onadata.libs.utils.viewer_tools import _get_form_url
from onadata.apps.main.views import get_enketo_preview_url


def get_enketo_urls(request, xform):
    form_url = _get_form_url(request, xform.user.username)
    url, preview_url = "", ""

    try:
        url = enketo_url(form_url, xform.id_string)
        preview_url = get_enketo_preview_url(request,
                                             xform.user.username,
                                             xform.id_string)
    except EnketoError:
        pass

    return "{}|{}".format(url, preview_url)


class Command(BaseCommand):
    help = ugettext_lazy("Adds metadata objects containing xforms enketo urls")

    def handle(self, *args, **kwargs):
        request = HttpRequest()

        for xform in XForm.objects.all():
            enketo_urls = get_enketo_urls(request, xform)
            # MetaData.enketo_urls(xform, enketo_urls)
            self.stdout.write('ENKETO URLS >>> %s' % enketo_urls)
