# -*- coding: utf-8 -*-
"""
Formhub/Ona Data to DHIS2 service - push submissions to DHIS2 instance.
"""
import requests

from onadata.apps.restservice.RestServiceInterface import RestServiceInterface


class ServiceDefinition(RestServiceInterface):
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
            requests.get(valid_url)
