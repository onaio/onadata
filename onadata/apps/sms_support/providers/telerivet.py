""" Telerivet WebHook gateway

    Supports Receiving and replying SMS from/to Telerivet Service

    See: http://telerivet.com/help/api/webhook/receiving """

import datetime

from django.http import JsonResponse
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from onadata.apps.sms_support.tools import SMS_API_ERROR, SMS_SUBMISSION_ACCEPTED
from onadata.apps.sms_support.parser import process_incoming_smses


def autodoc(url_root, username, id_string):
    """Returns Telerivet integration documentation."""
    urla = url_root + reverse(
        "sms_submission_api", kwargs={"username": username, "service": "telerivet"}
    )
    urlb = url_root + reverse(
        "sms_submission_form_api",
        kwargs={"username": username, "id_string": id_string, "service": "telerivet"},
    )
    doc = (
        "<p>"
        + _("%(service)s Instructions:")
        % {"service": '<a href="https://telerivet.com">' "Telerivet's Webhook API</a>"}
        + "</p><ol><li>"
        + _("Sign in to Telerivet.com and go to Service Page.")
        + "</li><li>"
        + _("Follow instructions to add an application with either URL:")
        + '<br /><span class="sms_autodoc_example">%(urla)s'
        + "<br />%(urlb)s</span><br />"
        + "</li></ol><p>"
        + _(
            "That's it. Now Send an SMS Formhub submission to your Telerivet"
            " phone number. It will create a submission on Formhub."
        )
        + "</p>"
    ) % {"urla": urla, "urlb": urlb}

    return doc


def get_response(data):
    """Return a JSON formatted HttpResponse based on the ``data`` provided."""

    message = data.get("text")

    if data.get("code") == SMS_API_ERROR:
        message = None
    elif data.get("code") != SMS_SUBMISSION_ACCEPTED:
        message = _(f"[ERROR] {message}")

    response = {}

    if message:
        messages = [{"content": message}]
        sendouts = data.get("sendouts", [])
        if len(sendouts):
            messages += [{"content": text} for text in sendouts]
        response.update({"messages": messages})

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

    sms_identity = request.POST.get("from_number", "").strip()
    sms_text = request.POST.get("content", "").strip()
    now_timestamp = datetime.datetime.now().strftime("%s")
    sent_timestamp = request.POST.get("time_created", now_timestamp).strip()
    try:
        sms_time = datetime.datetime.fromtimestamp(float(sent_timestamp))
    except ValueError:
        sms_time = datetime.datetime.now()

    return process_message_for_telerivet(
        username=username,
        sms_identity=sms_identity,
        sms_text=sms_text,
        sms_time=sms_time,
        id_string=id_string,
    )


# pylint: disable=unused-argument
def process_message_for_telerivet(
    username, sms_identity, sms_text, sms_time, id_string
):
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
