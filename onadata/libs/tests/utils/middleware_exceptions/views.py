from django.db import OperationalError
from django.http import HttpResponse
from django.urls import path
from django.conf.urls import url

def normal_view(request):
    return HttpResponse('OK')


def server_error(request):
    raise Exception('Error in view')


def operational_error(request):
    raise OperationalError


app_name = 'middleware_exceptions'
urlpatterns = [
    url('middleware_exceptions/view/', normal_view, name='normal'),
    url('middleware_exceptions/error/', server_error, name='other'),
    url('middleware_exceptions/operational_error/', operational_error, name='operational'),
]