# -*- coding: utf-8 -*-
"""
RestService signals module
"""
import django.dispatch
from django.conf import settings

from onadata.apps.restservice.tasks import call_service_async

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
        call_service_async(instance_id)


trigger_webhook.connect(call_webhooks, dispatch_uid="call_webhooks")
