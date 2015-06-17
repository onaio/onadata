from rest_framework.exceptions import APIException


class NoRecordsFoundError(Exception):
    pass


class J2XException(Exception):
    pass


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = 'Service temporarily unavailable, try again later.'
