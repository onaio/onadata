# -*- coding: utf-8 -*-
"""
Post submisison XML data to an external service that accepts an XML post.
"""
import requests

from onadata.apps.restservice.RestServiceInterface import RestServiceInterface


class ServiceDefinition(RestServiceInterface):
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
        requests.post(url, data=data.xml, headers=headers)
