# -*- coding: utf-8 -*-
"""
restservice async functions.
"""
from multidb.pinning import use_master

from onadata.apps.logger.models.instance import Instance
from onadata.apps.restservice.utils import call_service
from onadata.celeryapp import app


@app.task()
def call_service_async(instance_pk, latest_json=None):
    """Async function that calls call_service()."""
    # Pin to master just incase the Instance was created and is not available
    # in the replicas
    with use_master:
        try:
            instance = Instance.objects.get(pk=instance_pk)
        except Instance.DoesNotExist:
            # if the instance has already been removed we do not send it to the
            # service
            return

    if latest_json is None:
        instance.json = instance.get_full_dict()

    else:
        instance.json = latest_json

    call_service(instance)
