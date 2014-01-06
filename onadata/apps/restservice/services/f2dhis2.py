import httplib2
import requests

from onadata.apps.restservice.RestServiceInterface import RestServiceInterface


class ServiceDefinition(RestServiceInterface):
    id = u'f2dhis2'
    verbose_name = u'Formhub to DHIS2'

    def send(self, url, parsed_instance):
        instance = parsed_instance.instance
        info = {"id_string": instance.xform.id_string, "uuid": instance.uuid}
        valid_url = url % info
        http = httplib2.Http()
        resp, content = http.request(valid_url, 'GET')

    def send_ziggy(self, url, ziggy_instance, uuid):
        info = {"id_string": ziggy_instance.xform.id_string, "uuid": uuid}
        valid_url = url % info
        response = requests.get(valid_url)
        return response
