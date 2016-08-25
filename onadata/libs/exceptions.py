from rest_framework.exceptions import APIException
from rest_framework.views import set_rollback, exception_handler, Response
from rest_framework import status
from django.utils import six
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ObjectDoesNotExist


class NoRecordsFoundError(Exception):
    pass


class J2XException(Exception):
    pass


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = 'Service temporarily unavailable, try again later.'


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if isinstance(exc, ObjectDoesNotExist):
        msg = _('Record not found.')
        data = {'detail': six.text_type(msg)}

        set_rollback()
        return Response(data, status=status.HTTP_404_NOT_FOUND)
    else:
        return response
