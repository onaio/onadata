from django.utils.translation import ugettext_lazy as _

from rest_framework.exceptions import APIException


class EnketoError(Exception):

    default_message = _("There was a problem with your submissionor"
                        " form. Please contact support.")

    def __init__(self, message=None):
        if message is None:
            self.message = self.default_message
        else:
            self.message = message

    def __str__(self):
        return "{}".format(self.message)


class NoRecordsFoundError(Exception):
    pass


class NoRecordsPermission(Exception):
    pass


class J2XException(Exception):
    pass


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = 'Service temporarily unavailable, try again later.'
