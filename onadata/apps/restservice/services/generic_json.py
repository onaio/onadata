import json

import requests

from onadata.apps.restservice.RestServiceInterface import RestServiceInterface


class ServiceDefinition(RestServiceInterface):
    id = u'json'
    verbose_name = u'JSON POST'

    def send(self, url, submission_instance):
        post_data = json.dumps(submission_instance.json)
        headers = {"Content-Type": "application/json"}
        requests.post(url, headers=headers, data=post_data)
