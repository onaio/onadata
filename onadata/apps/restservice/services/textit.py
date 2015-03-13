import httplib2
import json

from onadata.apps.restservice.RestServiceInterface import RestServiceInterface
from onadata.apps.main.models import MetaData
from onadata.settings.common import METADATA_SEPARATOR


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
        extra_data = self.clean_keys_of_slashes(parsed_instance.instance.json)

        meta = MetaData.textit(parsed_instance.instance.xform)

        token, flow_uuid, contacts = meta.data_value.split(METADATA_SEPARATOR)
        post_data = {
            "extra": extra_data,
            "flow_uuid": flow_uuid,
            "contacts": contacts
        }
        headers = {"Content-Type": "application/json",
                   "Authorization": "Token {}".format(token)}
        http = httplib2.Http()

        resp, content = http.request(uri=url, method='POST',
                                     headers=headers,
                                     body=json.dumps(post_data))

    def clean_keys_of_slashes(self, record):
        """
        Replaces the slashes found in a dataset keys with underscores
        :param record: list containing a couple of dictionaries
        :return: record with keys without slashes
        """
        for key in record:
            value = record[key]
            # Ensure both key and value are string
            if not isinstance(value, basestring):
                record[key] = str(value)

            if '/' in key:
                # replace with _
                record[key.replace('/', '_')]\
                    = record.pop(key)
            # Check if the value is a list containing nested dict and apply same
            if value:
                if isinstance(value, list) and isinstance(value[0], dict):
                    for v in value:
                        self.clean_keys_of_slashes(v)

        return record
