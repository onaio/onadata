# -*- coding: utf-8 -*-
"""
Viewer signals module.
"""
import django.dispatch
from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save

from onadata.apps.logger.models import Instance
from onadata.apps.restservice.signals import trigger_webhook
from onadata.apps.viewer.models import ParsedInstance
from onadata.libs.utils.osm import save_osm_data_async

ASYNC_POST_SUBMISSION_PROCESSING_ENABLED = getattr(
    settings, "ASYNC_POST_SUBMISSION_PROCESSING_ENABLED", False
)

# pylint: disable=invalid-name
process_submission = django.dispatch.Signal()


def post_save_osm_data(instance_id):  # pylint: disable=unused-argument
    """
    Process OSM data post submission.
    """
    if ASYNC_POST_SUBMISSION_PROCESSING_ENABLED:
        save_osm_data_async.apply_async(args=[instance_id], countdown=1)
    else:
        save_osm_data_async(instance_id)


def _post_process_submissions(instance):
    trigger_webhook.send(sender=instance.__class__, instance=instance)
    if instance.xform.instances_with_osm:
        post_save_osm_data(instance.pk)


def post_save_submission(sender, **kwargs):  # pylint: disable=unused-argument
    """
    Calls webhooks and OSM data processing for ParsedInstance/Instance model.
    """
    created = kwargs.get("created")
    instance = kwargs.get("instance")

    if created and isinstance(instance, ParsedInstance):
        # Get submission from ParsedInstance
        instance = instance.instance

    if isinstance(instance, Instance):
        # Trigger webhooks only if the Instance has been commited by using
        # transaction.on_commit. In case, the transaction is rolled back,
        # the webhooks will not be called. Also, ensures getting the Instance
        # again from the database later will not return stale data
        transaction.on_commit(lambda: _post_process_submissions(instance))


post_save.connect(
    post_save_submission, sender=ParsedInstance, dispatch_uid="post_save_submission"
)
process_submission.connect(
    post_save_submission, sender=Instance, dispatch_uid="process_saved_submission"
)
