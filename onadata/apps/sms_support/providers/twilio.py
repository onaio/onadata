#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Twilio SMS gateway

    Supports Receiving and replying SMS from/to Twilio.
    URL must be set to POST method in Twilio.

    See: http://www.twilio.com/docs/api/twiml/sms/twilio_request
         http://www.twilio.com/docs/api/twiml/sms/your_response """

import datetime

from django.http import HttpResponse
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from dict2xml import dict2xml

from onadata.apps.sms_support.parser import process_incoming_smses
from onadata.apps.sms_support.tools import SMS_API_ERROR, SMS_SUBMISSION_ACCEPTED


def autodoc(url_root, username, id_string):
    """Returns Twilio integration documentation."""
    urla = url_root + reverse(
        "sms_submission_api", kwargs={"username": username, "service": "twilio"}
    )
    urlb = url_root + reverse(
        "sms_submission_form_api",
        kwargs={"username": username, "id_string": id_string, "service": "twilio"},
    )
    doc = (
        "<p>"
        + _("%(service)s Instructions:")
        % {"service": '<a href="https://twilio.com">' "Twilio's SMS Request</a>"}
        + "</p><ol><li>"
        + _("Sign in to Twilio.com and go your Application.")
        + "</li><li>"
        + _(
            "Follow instructions to add one of the following URLs, "
            "selecting the HTTP POST method:"
        )
        + '<br /><span class="sms_autodoc_example">%(urla)s'
        + "<br />%(urlb)s</span><br />"
        + "</li></ol><p>"
        + _(
            "That's it. Now Send an SMS Formhub submission to your Twilio"
            " phone number. It will create a submission on Formhub."
        )
        + "</p>"
    ) % {"urla": urla, "urlb": urlb}

    return doc


def get_response(data):
    """Return an XML formatted HttpResponse based on the ``data`` provided."""

    xml_head = '<?xml version="1.0" encoding="UTF-8" ?>'
    response_dict = {"Response": {}}
    message = data.get("text")

    if data.get("code") == SMS_API_ERROR:
        message = None
    elif data.get("code") != SMS_SUBMISSION_ACCEPTED:
        message = _("[ERROR] %s") % message

    if message:
        messages = [
            message,
        ]
        sendouts = data.get("sendouts", [])
        if len(sendouts):
            messages += sendouts
        response_dict.update({"Response": {"Sms": messages}})

    response = xml_head + dict2xml(response_dict)
    return HttpResponse(response, content_type="text/xml")


@require_POST
@csrf_exempt
def import_submission(request, username):
    """Proxy to import_submission_for_form with None as id_string"""

    return import_submission_for_form(request, username, None)


@require_POST
@csrf_exempt
def import_submission_for_form(request, username, id_string):
    """Retrieve and process submission from SMSSync Request"""

    sms_identity = request.POST.get("From", "").strip()
    sms_text = request.POST.get("Body", "").strip()
    now_timestamp = datetime.datetime.now().strftime("%s")
    sent_timestamp = request.POST.get("time_created", now_timestamp).strip()
    try:
        sms_time = datetime.datetime.fromtimestamp(float(sent_timestamp))
    except ValueError:
        sms_time = datetime.datetime.now()

    return process_message_for_twilio(
        username=username,
        sms_identity=sms_identity,
        sms_text=sms_text,
        sms_time=sms_time,
        id_string=id_string,
    )


# pylint: disable=unused-argument
def process_message_for_twilio(username, sms_identity, sms_text, sms_time, id_string):
    """Process a text instance and return in SMSSync expected format"""

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
