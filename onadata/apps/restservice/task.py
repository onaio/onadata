from celery import task
from onadata.apps.restservice.utils import call_service


@task()
def call_service_async(instance_pk):
    # load the parsed instance
    from onadata.apps.viewer.models.parsed_instance import ParsedInstance
    instance = ParsedInstance.objects.get(pk=instance_pk)
    call_service(instance)
