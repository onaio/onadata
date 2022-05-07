#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu
"""
sms_support.providers
"""
from __future__ import absolute_import

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from onadata.apps.sms_support.providers.smssync import autodoc as autodoc_smssync
from onadata.apps.sms_support.providers.smssync import (
    import_submission as imp_sub_smssync,
)
from onadata.apps.sms_support.providers.smssync import (
    import_submission_for_form as imp_sub_form_smssync,
)
from onadata.apps.sms_support.providers.telerivet import autodoc as autodoc_telerivet
from onadata.apps.sms_support.providers.telerivet import (
    import_submission as imp_sub_telerivet,
)
from onadata.apps.sms_support.providers.telerivet import (
    import_submission_for_form as imp_sub_form_telerivet,
)
from onadata.apps.sms_support.providers.textit import autodoc as autodoc_textit
from onadata.apps.sms_support.providers.textit import (
    import_submission as imp_sub_textit,
)
from onadata.apps.sms_support.providers.textit import (
    import_submission_for_form as imp_sub_form_textit,
)
from onadata.apps.sms_support.providers.twilio import autodoc as autodoc_twilio
from onadata.apps.sms_support.providers.twilio import (
    import_submission as imp_sub_twilio,
)
from onadata.apps.sms_support.providers.twilio import (
    import_submission_for_form as imp_sub_form_twilio,
)

SMSSYNC = "smssync"
TELERIVET = "telerivet"
TWILIO = "twilio"
TEXTIT = "textit"

PROVIDERS = {
    SMSSYNC: {
        "name": "SMS Sync",
        "imp": imp_sub_smssync,
        "imp_form": imp_sub_form_smssync,
        "doc": autodoc_smssync,
    },
    TELERIVET: {
        "name": "Telerivet",
        "imp": imp_sub_telerivet,
        "imp_form": imp_sub_form_telerivet,
        "doc": autodoc_telerivet,
    },
    TWILIO: {
        "name": "Twilio",
        "imp": imp_sub_twilio,
        "imp_form": imp_sub_form_twilio,
        "doc": autodoc_twilio,
    },
    TEXTIT: {
        "name": "Text It",
        "imp": imp_sub_textit,
        "imp_form": imp_sub_form_textit,
        "doc": autodoc_textit,
    },
}


# pylint: disable=unused-argument
def unknown_service(request, username=None, id_string=None):
    """400 view for request with unknown service name"""
    response = HttpResponse("Unknown SMS Gateway Service", content_type="text/plain")
    response.status_code = 400
    return response


@csrf_exempt
def import_submission(request, username, service):
    """Proxy to the service's import_submission view"""
    return PROVIDERS.get(service.lower(), {}).get("imp", unknown_service)(
        request, username
    )


@csrf_exempt
def import_submission_for_form(request, username, id_string, service):
    """Proxy to the service's import_submission_for_form view"""
    return PROVIDERS.get(service.lower(), {}).get("imp_form", unknown_service)(
        request, username, id_string
    )


def providers_doc(url_root, username, id_string):
    return [
        {
            "id": pid,
            "name": p.get("name"),
            "doc": p.get("doc")(url_root, username, id_string),
        }
        for pid, p in PROVIDERS.items()
    ]
