from optparse import make_option

from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import ugettext_lazy
from django.http import HttpRequest

from onadata.libs.utils.viewer_tools import get_form_url, enketo_url
from onadata.apps.main.views import get_enketo_preview_url
from onadata.apps.logger.models import XForm
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    help = ugettext_lazy("Create enketo url including preview")

    option_list = BaseCommand.option_list + (
        make_option(
            "-n", "--server_name", dest="server_name",
            default="api.ona.io"),
        make_option("-p", "--server_port", dest="server_port", default="443"),
        make_option("-r", "--protocol", dest="protocol", default="https"),
    )

    def handle(self, *args, **kwargs):
        request = HttpRequest()
        server_name = kwargs.get('server_name')
        server_port = kwargs.get('server_port')
        protocol = kwargs.get('protocol')

        if not server_name or not server_port or not protocol:
            raise CommandError(
                'please provide a server_name, a server_port and a protocol')

        if server_name not in ['api.ona.io', 'stage-api.ona.io', 'localhost']:
            raise CommandError('server name provided is not valid')

        if protocol not in ['http', 'https']:
            raise CommandError('protocol provided is not valid')

        # required for generation of enketo url
        request.META['HTTP_HOST'] = '%s:%s' % (server_name, server_port)\
            if server_port != '80' else server_name

        # required for generation of enketo preview url
        request.META['SERVER_NAME'] = server_name
        request.META['SERVER_PORT'] = server_port

        for xform in queryset_iterator(XForm.objects.all()):
            username = xform.user.username
            id_string = xform.id_string
            form_url = get_form_url(request, username, protocol=protocol)
            _url = enketo_url(form_url, id_string)
            _preview_url = get_enketo_preview_url(request, username, id_string)
            self.stdout.write(
                'enketo url: %s | preview url: %s' % (_url, _preview_url))
            self.stdout.write("enketo urls generation completed!!")
