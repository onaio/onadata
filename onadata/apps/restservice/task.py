from celery import task
from onadata.apps.restservice.utils import call_service
from django.shortcuts import get_object_or_404


@task()
def call_service_async(instance_pk):
    # load the parsed instance
    from onadata.apps.viewer.models.parsed_instance import ParsedInstance
    instance = get_object_or_404(ParsedInstance, pk=instance_pk)
    call_service(instance)
