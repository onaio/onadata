# -*- coding: utf-8 -*-
"""
Post submission data to a textit/rapidpro server.
"""
import json
import requests
from six import iteritems
from six import string_types

from onadata.apps.main.models import MetaData
from onadata.apps.restservice.RestServiceInterface import RestServiceInterface
from onadata.libs.utils.common_tags import TEXTIT
from onadata.settings.common import METADATA_SEPARATOR


class ServiceDefinition(RestServiceInterface):
    """
    Post submission data to a textit/rapidpro server.
    """

    # pylint: disable=invalid-name
    id = TEXTIT
    verbose_name = "TextIt POST"

    def send(self, url, data=None):
        """
        Sends the submission to the configured rest service
        :param url:
        :param data:
        :return:
        """
        # We use Instance.get_full_dict() instead of Instance.json because
        # when asynchronous processing is enabled, the json may not be upto date
        extra_data = self.clean_keys_of_slashes(data.get_full_dict())
        data_value = MetaData.textit(data.xform)

        if data_value:
            token, flow, contacts = data_value.split(METADATA_SEPARATOR)
            post_data = {
                "extra": extra_data,
                "flow": flow,
                "contacts": contacts.split(","),
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Token {token}",
            }

            requests.post(url, headers=headers, data=json.dumps(post_data))

    def clean_keys_of_slashes(self, record):
        """
        Replaces the slashes found in a dataset keys with underscores
        :param record: list containing a couple of dictionaries
        :return: record with keys without slashes
        """
        for key in list(record):
            value = record[key]
            # Ensure both key and value are string
            if not isinstance(value, string_types):
                record[key] = str(value)

            if "/" in key:
                # replace with _
                record[key.replace("/", "_")] = record.pop(key)
            # Check if the value is a list containing nested dict and apply
            # same
            if value and isinstance(value, list) and isinstance(value[0], dict):
                for v in value:
                    self.clean_keys_of_slashes(v)

        # remove elements with no value
        return {k: v for (k, v) in iteritems(record) if v}
