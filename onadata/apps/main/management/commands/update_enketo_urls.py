from optparse import make_option

from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import ugettext_lazy
from django.http import HttpRequest
from django.db.models import Q

from onadata.libs.utils.viewer_tools import _get_form_url, enketo_url
from onadata.apps.main.views import get_enketo_preview_url
from onadata.apps.main.models.meta_data import MetaData


class Command(BaseCommand):
    help = ugettext_lazy("Updates enketo preview urls in MetaData model")

    option_list = BaseCommand.option_list + (
        make_option("-n", "--server_name", dest="server_name", default=False),
        make_option("-p", "--server_port", dest="server_port", default=False),
        make_option("-r", "--protocol", dest="protocol", default=False),
        )

    def handle(self, *args, **kwargs):
        request = HttpRequest()
        server_name = kwargs.get('server_name')
        server_port = kwargs.get('server_port')
        protocol = kwargs.get('protocol')

        if not server_name or not server_port or not protocol:
            raise CommandError(
                'please provide a server_name, a server_port and a protocol')

        if server_name not in ['ona.io', 'stage.ona.io', 'localhost']:
            raise CommandError('server name provided is not valid')

        if protocol not in ['http', 'https']:
            raise CommandError('protocol provided is not valid')

        # required for generation of enketo url
        request.META['HTTP_HOST'] = '%s:%s' % (server_name, server_port)

        # required for generation of enketo preview url
        request.META['SERVER_NAME'] = server_name
        request.META['SERVER_PORT'] = server_port

        resultset = MetaData.objects.filter(
            Q(data_type='enketo_url') | Q(data_type='enketo_preview_url'),
            xform__user__username='ivermac')
        for meta_data in resultset:
            username = meta_data.xform.user.username
            id_string = meta_data.xform.id_string
            data_type = meta_data.data_type
            xform = meta_data.xform

            if data_type == 'enketo_url':
                form_url = _get_form_url(request, username, protocol='http')
                _enketo_url = enketo_url(form_url, id_string)
                MetaData.enketo_url(xform, _enketo_url)
            elif data_type == 'enketo_preview_url':
                _enketo_preview_url = get_enketo_preview_url(
                    request, username, id_string)
                MetaData.enketo_preview_url(xform, _enketo_preview_url)

            self.stdout.write('url: %s' % meta_data.data_value)

        self.stdout.write("enketo urls update complete!!")
