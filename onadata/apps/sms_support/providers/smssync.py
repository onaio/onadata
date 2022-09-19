#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Ushaidi's SMSSync gateway

    Supports Receiving and replying SMS from/to the SMSSync App.

    See: http://smssync.ushahidi.com/doc """

import datetime

from django.http import JsonResponse
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from onadata.apps.sms_support.parser import process_incoming_smses
from onadata.apps.sms_support.tools import SMS_API_ERROR, SMS_SUBMISSION_ACCEPTED


def autodoc(url_root, username, id_string):
    """Returns SMSSync integration documentation."""
    urla = url_root + reverse(
        "sms_submission_api", kwargs={"username": username, "service": "smssync"}
    )
    urlb = url_root + reverse(
        "sms_submission_form_api",
        kwargs={"username": username, "id_string": id_string, "service": "smssync"},
    )
    doc = (
        "<p>"
        + _("%(service)s Instructions:")
        % {
            "service": '<a href="http://smssync.ushahidi.com/">'
            "Ushaidi's SMS Sync</a>"
        }
        + "</p><ol><li>"
        + _("Download the SMS Sync App on your phone serving as a gateway.")
        + "</li><li>"
        + _("Configure the app to point to one of the following URLs")
        + '<br /><span class="sms_autodoc_example">%(urla)s'
        + "<br />%(urlb)s</span><br />"
        + _("Optionnaly set a keyword to prevent non-formhub messages to be sent.")
        + "</li><li>"
        + _("In the preferences, tick the box to allow replies from the server.")
        + "</li></ol><p>"
        + _(
            "That's it. Now Send an SMS Formhub submission to the number "
            "of that phone. It will create a submission on Formhub."
        )
        + "</p>"
    ) % {"urla": urla, "urlb": urlb}

    return doc


def get_response(data):
    """Return a JSON formatted HttpResponse based on the ``data`` provided."""
    message = data.get("text")
    if data.get("code") == SMS_API_ERROR:
        success = False
        message = None
    elif data.get("code") != SMS_SUBMISSION_ACCEPTED:
        success = True
        message = _("[ERROR] %s") % message
    else:
        success = True

    response = {"payload": {"success": success, "task": "send"}}

    if message:
        messages = [{"to": data.get("identity"), "message": message}]
        sendouts = data.get("sendouts", [])
        if len(sendouts):
            messages += [
                {"to": data.get("identity"), "message": text} for text in sendouts
            ]
        response["payload"].update({"messages": messages})

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

    sms_identity = request.POST.get("from", "").strip()
    sms_text = request.POST.get("message", "").strip()
    now_timestamp = datetime.datetime.now().strftime("%s")
    sent_timestamp = request.POST.get("sent_timestamp", now_timestamp).strip()
    try:
        sms_time = datetime.datetime.fromtimestamp(float(sent_timestamp))
    except ValueError:
        sms_time = datetime.datetime.now()

    return process_message_for_smssync(
        username=username,
        sms_identity=sms_identity,
        sms_text=sms_text,
        sms_time=sms_time,
        id_string=id_string,
    )


# pylint: disable=unused-argument
def process_message_for_smssync(username, sms_identity, sms_text, sms_time, id_string):
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
    response.update({"identity": sms_identity})

    return get_response(response)
