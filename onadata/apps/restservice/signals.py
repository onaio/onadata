# -*- coding: utf-8 -*-
"""
RestService signals module
"""
import django.dispatch
from django.conf import settings
from multidb.pinning import use_master

from onadata.apps.restservice.tasks import call_service_async
from onadata.apps.restservice.utils import call_service
from onadata.apps.logger.models.instance import Instance

ASYNC_POST_SUBMISSION_PROCESSING_ENABLED = getattr(
    settings, "ASYNC_POST_SUBMISSION_PROCESSING_ENABLED", False
)

# pylint: disable=invalid-name
trigger_webhook = django.dispatch.Signal()


def call_webhooks(sender, **kwargs):  # pylint: disable=unused-argument
    """
    Call webhooks signal.
    """
    instance_id = kwargs["instance"].pk
    if ASYNC_POST_SUBMISSION_PROCESSING_ENABLED:
        call_service_async.apply_async(args=[instance_id], countdown=1)
    else:
        with use_master:
            try:
                instance = Instance.objects.get(pk=instance_id)
            except Instance.DoesNotExist:
                # if the instance has already been removed we do not send it to the
                # service
                pass
            else:
                call_service(instance)


trigger_webhook.connect(call_webhooks, dispatch_uid="call_webhooks")
