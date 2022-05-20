#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu
"""
sms_support views.
"""
from __future__ import absolute_import

import json

from django.http import JsonResponse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from onadata.apps.sms_support.parser import process_incoming_smses
from onadata.apps.sms_support.tools import SMS_API_ERROR


def get_response(data):
    """Returns a JsonResponse object with `status`, `message`, `instanceID` and
    `sendouts` based on the input ``data`` object."""
    response = {
        "status": data.get("code"),
        "message": data.get("text"),
        "instanceID": data.get("id"),
        "sendouts": data.get("sendouts"),
    }
    return JsonResponse(response)


@require_GET
def import_submission(request, username):
    """Process an SMS text as a form submission

    :param string identity: phone number of the sender
    :param string text: SMS content

    :returns: a JSON dict with:
        'status': one of 'ACCEPTED', 'REJECTED', 'PARSING_FAILED'
        'message': Error message if not ACCEPTED.
        'id: Unique submission ID if ACCEPTED.

    """

    return import_submission_for_form(request, username, None)


@require_POST
@csrf_exempt
def import_multiple_submissions(request, username):
    """Process several POSTED SMS texts as XForm submissions

    :param json messages: JSON list of {"identity": "x", "text": "x"}
    :returns json list of {"status": "x", "message": "x", "id": "x"}

    """

    return import_multiple_submissions_for_form(request, username, None)


@require_GET
def import_submission_for_form(request, username, id_string):
    """idem import_submission with a defined id_string"""

    sms_identity = request.GET.get("identity", "").strip()
    sms_text = request.GET.get("text", "").strip()

    if not sms_identity or not sms_text:
        return get_response(
            {
                "code": SMS_API_ERROR,
                "text": _(
                    "`identity` and `message` are "
                    "both required and must not be "
                    "empty."
                ),
            }
        )
    incomings = [(sms_identity, sms_text)]
    response = process_incoming_smses(username, incomings, id_string)[-1]

    return get_response(response)


# pylint: disable=invalid-name
@require_POST
@csrf_exempt
def import_multiple_submissions_for_form(request, username, id_string):
    """idem import_multiple_submissions with a defined id_string"""

    messages = json.loads(request.POST.get("messages", "[]"))
    incomings = [(m.get("identity", ""), m.get("text", "")) for m in messages]

    responses = [
        {
            "status": d.get("code"),
            "message": d.get("text"),
            "instanceID": d.get("id"),
            "sendouts": d.get("sendouts"),
        }
        for d in process_incoming_smses(username, incomings, id_string)
    ]

    return JsonResponse(responses, safe=False)
