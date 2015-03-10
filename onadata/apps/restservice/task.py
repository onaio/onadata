from celery import task

from onadata.apps.restservice.utils import call_service


@task()
def call_service_async(instance):
    call_service(instance)
