# -*- coding: utf-8 -*-
"""
Post submisison XML data to an external service that accepts an XML post.
"""
from django.conf import settings
import requests

from onadata.apps.restservice.interface import RestServiceInterface

WEBHOOK_TIMEOUT = getattr(settings, "WEBHOOK_TIMEOUT", 30)


class ServiceDefinition(RestServiceInterface):  # pylint: disable=too-few-public-methods
    """
    Post submisison XML data to an external service that accepts an XML post.
    """

    # pylint: disable=invalid-name
    id = "xml"
    verbose_name = "XML POST"

    def send(self, url, data=None):
        """
        Post submisison XML data to an external service that accepts an XML post.
        """
        headers = {"Content-Type": "application/xml"}
        requests.post(url, data=data.xml, headers=headers, timeout=WEBHOOK_TIMEOUT)
