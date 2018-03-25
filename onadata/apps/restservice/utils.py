import logging

from django.utils.translation import ugettext as _

from onadata.apps.restservice.models import RestService
from onadata.libs.utils.common_tags import GOOGLE_SHEET


def call_service(submission_instance):
    # lookup service which is not google sheet service
    services = RestService.objects.filter(
        xform_id=submission_instance.xform_id).exclude(name=GOOGLE_SHEET)
    # call service send with url and data parameters
    for sv in services:
        # TODO: Queue service
        try:
            service = sv.get_service_definition()()
            service.send(sv.service_url, submission_instance)
        except Exception as e:
            # TODO: Handle gracefully | requeue/resend
            logging.exception(_(u'Service threw exception: %s' % str(e)))
