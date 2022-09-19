# -*- coding: utf-8 -*-
"""
restservice async functions.
"""
from onadata.apps.logger.models.instance import Instance
from onadata.apps.restservice.utils import call_service
from onadata.celeryapp import app


@app.task()
def call_service_async(instance_pk):
    """Async function that calls call_service()."""
    # load the parsed instance

    try:
        instance = Instance.objects.get(pk=instance_pk)
    except Instance.DoesNotExist:
        # if the instance has already been removed we do not send it to the
        # service
        pass
    else:
        call_service(instance)
