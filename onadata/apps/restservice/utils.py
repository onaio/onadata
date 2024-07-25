# -*- coding: utf-8 -*-
"""
restservice utility functions.
"""
import logging
import sys

from onadata.apps.restservice.models import RestService
from onadata.libs.utils.common_tags import GOOGLE_SHEET
from onadata.libs.utils.common_tools import report_exception


def call_service(submission_instance):
    """Sends submissions to linked services."""
    # lookup service which is not google sheet service
    services = RestService.objects.filter(
        xform_id=submission_instance.xform_id
    ).exclude(name=GOOGLE_SHEET)
    # call service send with url and data parameters
    for service_def in services:
        # pylint: disable=broad-except
        try:
            service = service_def.get_service_definition()()
            service.send(service_def.service_url, submission_instance)
        except Exception as error:
            report_exception(f"Service call failed: {error}", error, sys.exc_info())
            logging.exception("Service threw exception: %s", error)
