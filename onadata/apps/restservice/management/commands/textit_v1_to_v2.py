#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
textit_v1_to_v2 - converts RapidPro/textit urls from v1 to v2 urls.
"""

import re

from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from onadata.apps.restservice.models import RestService
from onadata.libs.utils.common_tags import TEXTIT


class Command(BaseCommand):
    """Migrate TextIt/RapidPro v1 URLS to v2 URLS."""

    help = _("Migrate TextIt/RapidPro v1 URLS to v2 URLS.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", default=False, help=_("Apply changes to database.")
        )

    # pylint: disable=unused-argument
    def handle(self, *args, **options):
        """Migrate TextIt/RapidPro v1 URLS to v2 URLS."""
        services = RestService.objects.filter(name=TEXTIT)
        force = options.get("apply")
        if force and force.lower() != "true":
            self.stderr.write("--apply expects 'true' as a parameter value.")
        else:
            version_1 = re.compile(r"\/v1/runs")
            version_2 = "/v2/flow_starts"

            for service in services:
                if version_1.findall(service.service_url):
                    original = service.service_url
                    new_uri = re.sub(version_1, version_2, service.service_url)
                    params = {"v1_url": original, "v2_url": new_uri}
                    if force.lower() == "true":
                        service.service_url = new_uri
                        service.save()
                        self.stdout.write(
                            _("Changed %(v1_url)s to %(v2_url)s" % params)
                        )
                    else:
                        self.stdout.write(
                            _("Will change %(v1_url)s to %(v2_url)s" % params)
                        )
