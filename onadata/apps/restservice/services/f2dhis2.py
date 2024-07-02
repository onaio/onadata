# -*- coding: utf-8 -*-
"""
Formhub/Ona Data to DHIS2 service - push submissions to DHIS2 instance.
"""
from django.conf import settings

import requests

from onadata.apps.restservice.interface import RestServiceInterface

WEBHOOK_TIMEOUT = getattr(settings, "WEBHOOK_TIMEOUT", 30)


class ServiceDefinition(RestServiceInterface):  # pylint: disable=too-few-public-methods
    """Post submission to DHIS2 instance."""

    # pylint: disable=invalid-name
    id = "f2dhis2"
    verbose_name = "Formhub to DHIS2"

    def send(self, url, data=None):
        """Post submission to DHIS2 instance."""
        if data:
            info = {
                "id_string": data.xform.id_string,
                "uuid": data.uuid,
            }
            valid_url = url % info
            requests.get(valid_url, timeout=WEBHOOK_TIMEOUT)
