from celery import task
from onadata.apps.restservice.utils import call_service


@task()
def call_service_async(instance_pk):
    # load the parsed instance
    from onadata.apps.viewer.models.parsed_instance import ParsedInstance

    try:
        instance = ParsedInstance.objects.get(pk=instance_pk)
        call_service(instance)
    except ParsedInstance.DoesNotExist:
        # if the instance has already been removed we do not send it to the
        # service
        pass
