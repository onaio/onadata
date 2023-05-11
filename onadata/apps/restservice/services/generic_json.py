# -*- coding: utf-8 -*-
"""
Post submisison JSON data to an external service that accepts a JSON post.
"""
import json

from django.conf import settings

import requests
from requests.exceptions import ConnectionError as RequestsConnectionError

from onadata.apps.restservice.RestServiceInterface import RestServiceInterface

WEBHOOK_TIMEOUT = getattr(settings, "WEBHOOK_TIMEOUT", 30)


class ServiceDefinition(RestServiceInterface):
    """Post submisison JSON data to an external service that accepts a JSON post."""

    # pylint: disable=invalid-name
    id = "json"
    verbose_name = "JSON POST"

    def send(self, url, data=None):
        """Post submisison JSON data to an external service that accepts a JSON post."""
        if data:
            post_data = json.dumps(data.json)
            headers = {"Content-Type": "application/json"}
            try:
                requests.post(
                    url, headers=headers, data=post_data, timeout=WEBHOOK_TIMEOUT
                )
            except RequestsConnectionError:
                pass
