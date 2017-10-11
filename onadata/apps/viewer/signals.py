# -*- coding=utf-8 -*-
"""
Viewer signals module.
"""
import django.dispatch
from django.conf import settings
from django.db.models.signals import post_save

from onadata.apps.logger.models import Instance
from onadata.apps.restservice.signals import trigger_webhook
from onadata.apps.viewer.models import ParsedInstance
from onadata.libs.utils.osm import save_osm_data_async

ASYNC_POST_SUBMISSION_PROCESSING_ENABLED = \
    getattr(settings, 'ASYNC_POST_SUBMISSION_PROCESSING_ENABLED', False)

# pylint: disable=C0103
process_submission = django.dispatch.Signal(providing_args=['instance'])


def post_save_osm_data(instance_id):  # pylint: disable=W0613
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


def post_save_submission(sender, **kwargs):  # pylint: disable=W0613
    """
    Calls webhooks and OSM data processing for ParsedInstance model.
    """
    parsed_instance = kwargs.get('instance')
    created = kwargs.get('created')

    if created:
        _post_process_submissions(parsed_instance.instance)


post_save.connect(
    post_save_submission,
    sender=ParsedInstance,
    dispatch_uid='post_save_submission')


def process_saved_submission(sender, **kwargs):  # pylint: disable=W0613
    """
    Calls webhooks and OSM data processing for Instance model.
    """
    instance = kwargs.get('instance')
    if instance:
        _post_process_submissions(instance)


process_submission.connect(process_saved_submission, sender=Instance,
                           dispatch_uid='process_saved_submission')
