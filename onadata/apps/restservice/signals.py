# -*- coding: utf-8 -*-
"""
RestService signals module
"""
import django.dispatch

from onadata.apps.restservice.tasks import call_service_async


# pylint: disable=invalid-name
trigger_webhook = django.dispatch.Signal()


def call_webhooks(sender, **kwargs):  # pylint: disable=unused-argument
    """
    Call webhooks signal.
    """
    instance = kwargs["instance"]

    call_service_async.apply_async(args=[instance.pk], countdown=1)


trigger_webhook.connect(call_webhooks, dispatch_uid="call_webhooks")
