import json

import requests
from six import string_types

from onadata.apps.main.models import MetaData
from onadata.apps.restservice.RestServiceInterface import RestServiceInterface
from onadata.libs.utils.common_tags import TEXTIT
from onadata.settings.common import METADATA_SEPARATOR


class ServiceDefinition(RestServiceInterface):
    id = SLACK
    verbose_name = u'Slack Webhook'
    channel = "#general"
    username = "Ona Bot"
    avatar = 'https://ona.io/img/favicon-32x32.png'

    def send(self, url, submission_instance):
        """
        Sends the submission to the configured rest service
        :param url:
        :param submission_instance:
        :return:
        """
        
        ona_data = json.dumps(submission_instance.json)
        post_data = {
            "channel": self.channel
            "username": self.username
            "icon_url": self.avatar
            "text": "A new form {form_name} has been submitted by {form_user}".format(form_name=ona_data[], form_user=ona_data[])
        }
        headers = {"Content-Type": "application/json"}
        requests.post(url, headers=headers, data=post_data)