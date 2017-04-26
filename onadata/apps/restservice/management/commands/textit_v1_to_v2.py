#!/usr/bin/env python

import re

from django.core.management.base import BaseCommand
from django.utils.translation import ugettext as _

from onadata.apps.restservice.models import RestService
from onadata.libs.utils.common_tags import TEXTIT


class Command(BaseCommand):
    help = _("Migrate TextIt/RapidPro v1 URLS to v2 URLS.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', default=False, help=_("Apply changes to database."))

    def handle(self, *args, **options):
        services = RestService.objects.filter(name=TEXTIT)
        force = options.get('apply')
        if force and force.lower() != 'true':
            self.stderr.write("--apply expects 'true' as a parameter value.")

            return

        v1 = re.compile(r'\/v1/runs')
        v2 = '/v2/flow_starts'

        for service in services:
            if v1.findall(service.service_url):
                original = service.service_url
                new_uri = re.sub(v1, v2, service.service_url)
                params = {'v1_url': original, 'v2_url': new_uri}
                if force.lower() == 'true':
                    service.service_url = new_uri
                    service.save()
                    self.stdout.write(
                        _("Changed %(v1_url)s to %(v2_url)s" % params))
                else:
                    self.stdout.write(
                        _("Will change %(v1_url)s to %(v2_url)s" % params))
