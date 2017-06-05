import requests

from onadata.apps.restservice.RestServiceInterface import RestServiceInterface


class ServiceDefinition(RestServiceInterface):
    id = u'xml'
    verbose_name = u'XML POST'

    def send(self, url, submission_instance):
        headers = {"Content-Type": "application/xml"}
        requests.post(url, data=submission_instance.xml, headers=headers)
