import httplib2
import json
from six import string_types

from onadata.apps.restservice.RestServiceInterface import RestServiceInterface
from onadata.apps.main.models import MetaData
from onadata.settings.common import METADATA_SEPARATOR
from onadata.libs.utils.common_tags import TEXTIT


class ServiceDefinition(RestServiceInterface):
    id = TEXTIT
    verbose_name = u'TextIt POST'

    def send(self, url, submission_instance):
        """
        Sends the submission to the configured rest service
        :param url:
        :param submission_instance:
        :return:
        """
        extra_data = self.clean_keys_of_slashes(submission_instance.json)

        data_value = MetaData.textit(submission_instance.xform)

        if data_value:
            token, flow, contacts = data_value.split(METADATA_SEPARATOR)
            post_data = {
                "extra": extra_data,
                "flow": flow,
                "contacts": contacts.split(',')
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
            if not isinstance(value, string_types):
                record[key] = str(value)

            if '/' in key:
                # replace with _
                record[key.replace('/', '_')]\
                    = record.pop(key)
            # Check if the value is a list containing nested dict and apply
            # same
            if value and isinstance(value, list)\
                    and isinstance(value[0], dict):
                for v in value:
                    self.clean_keys_of_slashes(v)

        # remove elements with no value
        return dict((k, v) for k, v in record.iteritems() if v)
