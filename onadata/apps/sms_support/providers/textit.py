#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Nyaruka's TextIt gateway

    Supports Receiving and sending reply SMS from/to the TextIt App.

    See: https://textit.in/api/v1/webhook/ """

import datetime

from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

import dateutil

from onadata.apps.sms_support.parser import process_incoming_smses
from onadata.apps.sms_support.tools import SMS_API_ERROR, SMS_SUBMISSION_ACCEPTED

TEXTIT_URL = "https://api.textit.in/api/v1/sms.json"


def autodoc(url_root, username, id_string):
    """Returns the documentation string for the provider."""
    urla = url_root + reverse(
        "sms_submission_api", kwargs={"username": username, "service": "textit"}
    )
    urlb = url_root + reverse(
        "sms_submission_form_api",
        kwargs={"username": username, "id_string": id_string, "service": "textit"},
    )
    doc = (
        "<p>"
        + _("%(service)s Instructions:")
        % {"service": '<a href="https://textit.in">' "TextIt's Webhook API</a>"}
        + "</p><ol><li>"
        + _("Sign in to TextIt.in and go to Account Page.")
        + "</li><li>"
        + _("Tick “Incoming SMS Messages” and set Webhook URL to either:")
        + '<br /><span class="sms_autodoc_example">%(urla)s'
        + "<br />%(urlb)s</span><br />"
        + "</li></ol><p>"
        + _(
            "That's it. Now Send an SMS Formhub submission to your TextIt"
            " phone number. It will create a submission on Formhub."
        )
        + "</p>"
    ) % {"urla": urla, "urlb": urlb}

    return doc


def get_response(data):
    """Sends SMS ``data`` to textit via send_sms_via_textit() function."""

    message = data.get("text")
    if data.get("code") == SMS_API_ERROR:
        message = None
    elif data.get("code") != SMS_SUBMISSION_ACCEPTED:
        message = _("[ERROR] %s") % message

    # send a response
    if message:
        messages = [
            message,
        ]
        sendouts = data.get("sendouts", [])
        if len(sendouts):
            messages += sendouts
        for text in messages:
            payload = data.get("payload", {})
            payload.update({"text": text})
            if payload.get("phone"):
                send_sms_via_textit(payload)

    return HttpResponse()


def send_sms_via_textit(payload):
    """Returns the JsonResponse of the SMS JSOn payload for text it."""
    response = {"phone": [payload.get("phone")], "text": payload.get("text")}

    return JsonResponse(response)


@require_POST
@csrf_exempt
def import_submission(request, username):
    """Proxy to import_submission_for_form with None as id_string"""
    return import_submission_for_form(request, username, None)


@require_POST
@csrf_exempt
def import_submission_for_form(request, username, id_string):
    """Retrieve and process submission from SMSSync Request"""

    sms_event = request.POST.get("event", "").strip()

    if not sms_event == "mo_sms":
        return HttpResponse()

    sms_identity = request.POST.get("phone", "").strip()
    sms_relayer = request.POST.get("relayer", "").strip()
    sms_text = request.POST.get("text", "").strip()
    now_time = datetime.datetime.now().isoformat()
    sent_time = request.POST.get("time", now_time).strip()

    try:
        sms_time = dateutil.parser.parse(sent_time)
    except ValueError:
        sms_time = datetime.datetime.now()

    return process_message_for_textit(
        username=username,
        sms_identity=sms_identity,
        sms_text=sms_text,
        sms_time=sms_time,
        id_string=id_string,
        payload={"phone": sms_identity, "relayer": sms_relayer},
    )


# pylint: disable=unused-argument,too-many-arguments, too-many-positional-arguments
def process_message_for_textit(
    username, sms_identity, sms_text, sms_time, id_string, payload=None
):
    """Process a text instance and return in SMSSync expected format"""

    payload = {} if payload is None else payload
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
    response.update({"payload": payload})

    return get_response(response)
