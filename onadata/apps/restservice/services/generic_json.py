# -*- coding: utf-8 -*-
"""
Post submisison JSON data to an external service that accepts a JSON post.
"""
import json

import requests

from onadata.apps.restservice.RestServiceInterface import RestServiceInterface


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
            requests.post(url, headers=headers, data=post_data)
