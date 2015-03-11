import httplib2
import json

from onadata.apps.restservice.RestServiceInterface import RestServiceInterface
from onadata.apps.main.models import MetaData


class ServiceDefinition(RestServiceInterface):
    id = u'textit'
    verbose_name = u'TextIt POST'

    def send(self, url, parsed_instance):
        """
        Sends the submission to the configured rest service
        :param url:
        :param parsed_instance:
        :return:
        """
        extra_data = parsed_instance.instance.json
        # Ensure both key and value are string
        for key in extra_data:
            value = extra_data[key]

            if not isinstance(value, basestring):
                extra_data[key] = str(value)

        meta = MetaData.objects.get(xform=parsed_instance.instance.xform,
                                    data_type="textit")
        textit_value = meta.data_value.split('|')
        post_data = {
            "extra": extra_data,
            "flow_uuid": textit_value[1],
            "contacts": textit_value[2]
        }
        headers = {"Content-Type": "application/json",
                   "Authorization": "Token {}".format(textit_value[0])}
        http = httplib2.Http()

        resp, content = http.request(uri=url, method='POST',
                                     headers=headers,
                                     body=json.dumps(post_data))
