import httplib2

from onadata.apps.restservice.RestServiceInterface import RestServiceInterface


class ServiceDefinition(RestServiceInterface):
    id = u'f2dhis2'
    verbose_name = u'Formhub to DHIS2'

    def send(self, url, submission_instance):
        info = {
            "id_string": submission_instance.xform.id_string,
            "uuid": submission_instance.uuid
        }
        valid_url = url % info
        http = httplib2.Http()
        http.request(valid_url, 'GET')
