from django.core.management.base import BaseCommand, CommandError
from django.http import HttpRequest
from django.utils.translation import ugettext_lazy

from onadata.apps.logger.models import XForm
from onadata.libs.utils.model_tools import queryset_iterator
from onadata.libs.utils.viewer_tools import (
    enketo_url, get_enketo_preview_url, get_form_url)


class Command(BaseCommand):
    help = ugettext_lazy("Create enketo url including preview")

    def add_arguments(self, parser):
        parser.add_argument(
            "-n", "--server_name", dest="server_name", default="api.ona.io")
        parser.add_argument(
            "-p", "--server_port", dest="server_port", default="80")
        parser.add_argument(
            "-r", "--protocol", dest="protocol", default="https")
        parser.add_argument("-u", "--username", dest="username", default=None)
        parser.add_argument(
            "-x", "--id_string", dest="id_string", default=None)

    def handle(self, *args, **options):
        request = HttpRequest()
        server_name = options.get('server_name')
        server_port = options.get('server_port')
        protocol = options.get('protocol')
        username = options.get('username')
        id_string = options.get('id_string')

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

        if username and id_string:
            try:
                xform = XForm.objects.get(
                    user__username=username, id_string=id_string)
                form_url = get_form_url(request, username, protocol=protocol,
                                        xform_pk=xform.pk)
                id_string = xform.id_string
                _url = enketo_url(form_url, id_string)
                _preview_url = get_enketo_preview_url(request, username,
                                                      id_string,
                                                      xform_pk=xform.pk)
                self.stdout.write('enketo url: %s | preview url: %s' %
                                  (_url, _preview_url))
                self.stdout.write("enketo urls generation completed!!")
            except XForm.DoesNotExist:
                self.stdout.write(
                    "No xform matching the provided username and id_string")
        elif username and id_string is None:
            xforms = XForm.objects.filter(user__username=username)
            num_of_xforms = xforms.count()
            if xforms:
                for xform in queryset_iterator(xforms):
                    form_url = get_form_url(request, username,
                                            protocol=protocol,
                                            xform_pk=xform.pk)
                    id_string = xform.id_string
                    _url = enketo_url(form_url, id_string)
                    _preview_url = get_enketo_preview_url(
                        request, username, id_string, xform_pk=xform.pk)
                    num_of_xforms -= 1
                    self.stdout.write(
                        'enketo url: %s | preview url: %s | remaining: %s' %
                        (_url, _preview_url, num_of_xforms))
                self.stdout.write("enketo urls generation completed!!")
            else:
                self.stdout.write("Username doesn't own any form")
        else:
            xforms = XForm.objects.all()
            num_of_xforms = xforms.count()
            for xform in queryset_iterator(xforms):
                username = xform.user.username
                id_string = xform.id_string
                form_url = get_form_url(request, username, protocol=protocol,
                                        xform_pk=xform.pk)
                _url = enketo_url(form_url, id_string)
                _preview_url = get_enketo_preview_url(request, username,
                                                      id_string,
                                                      xform_pk=xform.pk)
                num_of_xforms -= 1
                self.stdout.write(
                    'enketo url: %s | preview url: %s | remaining: %s' %
                    (_url, _preview_url, num_of_xforms))
            self.stdout.write("enketo urls generation completed!!")
