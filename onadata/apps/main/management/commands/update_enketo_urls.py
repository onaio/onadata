from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.http import HttpRequest
from django.utils.translation import ugettext_lazy

from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.utils.viewer_tools import (
    enketo_url, get_enketo_preview_url, get_form_url)


class Command(BaseCommand):
    help = ugettext_lazy("Updates enketo preview urls in MetaData model")

    def add_arguments(self, parser):
        parser.add_argument(
            "-n", "--server_name", dest="server_name", default="enketo.ona.io")
        parser.add_argument(
            "-p", "--server_port", dest="server_port", default="443")
        parser.add_argument(
            "-r", "--protocol", dest="protocol", default="https")

    def handle(self, *args, **options):
        request = HttpRequest()
        server_name = options.get('server_name')
        server_port = options.get('server_port')
        protocol = options.get('protocol')

        if not server_name or not server_port or not protocol:
            raise CommandError(
                'please provide a server_name, a server_port and a protocol')

        if server_name not in ['ona.io', 'stage.ona.io', 'localhost']:
            raise CommandError('server name provided is not valid')

        if protocol not in ['http', 'https']:
            raise CommandError('protocol provided is not valid')

        # required for generation of enketo url
        request.META['HTTP_HOST'] = '%s:%s' % (server_name, server_port)\
            if server_port != '80' else server_name

        # required for generation of enketo preview url
        request.META['SERVER_NAME'] = server_name
        request.META['SERVER_PORT'] = server_port

        resultset = MetaData.objects.filter(
            Q(data_type='enketo_url') | Q(data_type='enketo_preview_url'))
        for meta_data in resultset:
            username = meta_data.content_object.user.username
            id_string = meta_data.content_object.id_string
            data_type = meta_data.data_type
            data_value = meta_data.data_value
            xform = meta_data.content_object
            with open('/tmp/enketo_url', 'a') as f:

                if data_type == 'enketo_url':
                    form_url = get_form_url(
                        request, username, protocol=protocol,
                        xform_pk=xform.pk)
                    _enketo_url = enketo_url(form_url, id_string)
                    MetaData.enketo_url(xform, _enketo_url)
                elif data_type == 'enketo_preview_url':
                    _enketo_preview_url = get_enketo_preview_url(
                        request, username, id_string, xform_pk=xform.pk)
                    MetaData.enketo_preview_url(xform, _enketo_preview_url)
                f.write('%s : %s \n' % (id_string, data_value))

            self.stdout.write('%s: %s' % (data_type, meta_data.data_value))

        self.stdout.write("enketo urls update complete!!")
