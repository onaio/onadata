#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import copy
import io
import mimetypes
from xml.parsers.expat import ExpatError

from django.contrib.auth.models import User
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.http import HttpRequest
from django.utils.translation import gettext as _

from onadata.apps.logger.models import XForm
from onadata.apps.logger.models.instance import FormInactiveError
from onadata.apps.logger.xform_instance_parser import DuplicateInstance
from onadata.apps.logger.xform_instance_parser import InstanceEmptyError
from onadata.apps.logger.xform_instance_parser import InstanceInvalidUserError
from onadata.libs.utils.log import Actions
from onadata.libs.utils.log import audit_log
from onadata.libs.utils.logger_tools import create_instance

SMS_API_ERROR = "SMS_API_ERROR"
SMS_PARSING_ERROR = "SMS_PARSING_ERROR"
SMS_SUBMISSION_ACCEPTED = "SMS_SUBMISSION_ACCEPTED"
SMS_SUBMISSION_REFUSED = "SMS_SUBMISSION_REFUSED"
SMS_INTERNAL_ERROR = "SMS_INTERNAL_ERROR"

BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" "abcdefghijklmnopqrstuvwxyz0123456789+/="
DEFAULT_SEPARATOR = "+"
DEFAULT_ALLOW_MEDIA = False
NA_VALUE = "n/a"
BASE64_ALPHABET = None
META_FIELDS = (
    "start",
    "end",
    "today",
    "deviceid",
    "subscriberid",
    "imei",
    "phonenumber",
)
MEDIA_TYPES = ("audio", "video", "photo")
DEFAULT_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_DATETIME_FORMAT = "%Y-%m-%d-%H:%M"
SENSITIVE_FIELDS = ("text", "select all that apply", "geopoint", "barcode")


def is_last(index, items):
    return index == len(items) - 1 or (
        items[-1].get("type") == "note" and index == len(items) - 2
    )


def get_sms_instance_id(instance):
    """Human-friendly unique ID of a submission for latter ref/update

    For now, we strip down to the first 8 chars of the UUID.
    Until we figure out what we really want (might as well be used
    by formhub XML)"""
    return instance.uuid[:8]


def sms_media_to_file(file_object, name):
    if isinstance(file_object, str):
        file_object = io.BytesIO(file_object)

    def getsize(f):
        f.seek(0)
        f.read()
        s = f.tell()
        f.seek(0)
        return s

    name = name.strip()
    content_type, charset = mimetypes.guess_type(name)
    size = getsize(file_object)
    return InMemoryUploadedFile(
        file=file_object,
        name=name,
        field_name=None,
        content_type=content_type,
        charset=charset,
        size=size,
    )


def generate_instance(username, xml_file, media_files, uuid=None):
    """Process an XForm submission as if done via HTTP

    :param IO xml_file: file-like object containing XML XForm
    :param string username: username of the Form's owner
    :param list media_files: a list of UploadedFile objects
    :param string uuid: an optionnal uuid for the instance.

    :returns a (status, message) tuple."""

    try:
        instance = create_instance(username, xml_file, media_files, uuid=uuid)
    except InstanceInvalidUserError:
        return {"code": SMS_SUBMISSION_REFUSED, "text": _("Username or ID required.")}
    except InstanceEmptyError:
        return {
            "code": SMS_INTERNAL_ERROR,
            "text": _("Received empty submission. " "No instance was created"),
        }
    except FormInactiveError:
        return {"code": SMS_SUBMISSION_REFUSED, "text": _("Form is not active")}
    except XForm.DoesNotExist:
        return {
            "code": SMS_SUBMISSION_REFUSED,
            "text": _("Form does not exist on this account"),
        }
    except ExpatError:
        return {"code": SMS_INTERNAL_ERROR, "text": _("Improperly formatted XML.")}
    except DuplicateInstance:
        return {"code": SMS_SUBMISSION_REFUSED, "text": _("Duplicate submission")}

    if instance is None:
        return {"code": SMS_INTERNAL_ERROR, "text": _("Unable to create submission.")}

    user = User.objects.get(username=username)

    audit = {"xform": instance.xform.id_string}
    audit_log(
        Actions.SUBMISSION_CREATED,
        user,
        instance.xform.user,
        _("Created submission on form %(id_string)s.")
        % {"id_string": instance.xform.id_string},
        audit,
        HttpRequest(),
    )

    xml_file.close()
    if len(media_files):
        [_file.close() for _file in media_files]

    return {
        "code": SMS_SUBMISSION_ACCEPTED,
        "text": _("[SUCCESS] Your submission has been accepted."),
        "id": get_sms_instance_id(instance),
    }


def is_sms_related(json_survey):
    """Whether a form is considered to want sms Support

    return True if one sms-related field is defined."""

    def treat(value, key=None):
        if key is None:
            return False
        if key in ("sms_field", "sms_option") and value:
            if not value.lower() in ("no", "false"):
                return True

    def walk(dl):
        if not isinstance(dl, (dict, list)):
            return False
        iterator = [(None, e) for e in dl] if isinstance(dl, list) else dl.items()
        for k, v in iterator:
            if k == "parent":
                continue
            if treat(v, k):
                return True
            if walk(v):
                return True
        return False

    return walk(json_survey)


def check_form_sms_compatibility(form, json_survey=None):
    """Tests all SMS related rules on the XForm representation

    Returns a view-compatible dict(type, text) with warnings or
    a success message"""

    if json_survey is None:
        json_survey = form.get("form_o", {})

    def prep_return(msg, comp=None):

        from django.urls import reverse

        error = "alert-info"
        warning = "alert-info"
        success = "alert-success"
        outro = (
            '<br />Please check the <a href="%(syntax_url)s'
            '#9-sms-support">'
            "SMS Syntax Page</a>." % {"syntax_url": reverse("syntax")}
        )

        # no compatibility at all
        if not comp:
            alert = error
            msg = "%(prefix)s %(msg)s" % {
                "prefix": "Your Form is <strong>not SMS-compatible"
                "</strong>. If you want to later enable "
                "SMS Support, please fix:<br />",
                "msg": msg,
            }
        # no blocker but could be improved
        elif comp == 1:
            alert = warning
            msg = "%(prefix)s <ul>%(msg)s</ul>" % {
                "prefix": "Your form can be used with SMS, " "knowing that:",
                "msg": msg,
            }
        # SMS compatible
        else:
            outro = ""
            alert = success

        return {
            "type": alert,
            "text": "%(msg)s%(outro)s" % {"msg": msg, "outro": outro},
        }

    # first level children. should be groups
    groups = json_survey.get("children", [{}])

    # BLOCKERS
    # overload SENSITIVE_FIELDS if date or datetime format contain spaces.
    sensitive_fields = copy.copy(SENSITIVE_FIELDS)
    date_format = (
        json_survey.get("sms_date_format", DEFAULT_DATE_FORMAT) or DEFAULT_DATE_FORMAT
    )
    datetime_format = (
        json_survey.get("sms_datetime_format", DEFAULT_DATETIME_FORMAT)
        or DEFAULT_DATETIME_FORMAT
    )
    if len(date_format.split()) > 1:
        sensitive_fields += ("date",)
    if len(datetime_format.split()) > 1:
        sensitive_fields += ("datetime",)

    # must not contain out-of-group questions
    if sum([1 for e in groups if e.get("type") != "group"]):
        return prep_return(_("All your questions must be in groups."))
    # all groups must have an sms_field
    bad_groups = [
        e.get("name")
        for e in groups
        if not e.get("sms_field", "") and not e.get("name", "") == "meta"
    ]
    if len(bad_groups):
        return prep_return(
            _(
                "All your groups must have an 'sms_field' "
                "(use 'meta' prefixed ones for non-fillable "
                "groups). %s" % bad_groups[-1]
            )
        )
    # all select_one or select_multiple fields muts have sms_option for each.
    for group in groups:
        fields = group.get("children", [{}])
        for field in fields:
            xlsf_type = field.get("type")
            xlsf_name = field.get("name")
            xlsf_choices = field.get("children")
            if xlsf_type in ("select one", "select all that apply"):
                nb_choices = len(xlsf_choices)
                options = list(
                    set([c.get("sms_option", "") or None for c in xlsf_choices])
                )
                try:
                    options.remove(None)
                except ValueError:
                    pass
                nb_options = len(options)
                if nb_choices != nb_options:
                    return prep_return(
                        _(
                            "Not all options in the choices list for "
                            "<strong>%s</strong> have an "
                            "<em>sms_option</em> value."
                        )
                        % xlsf_name
                    )

    # has sensitive (space containing) fields in non-last position
    for group in groups:
        fields = group.get("children", [{}])
        last_pos = len(fields) - 1
        # consider last field to be last before note if there's a trailing note
        if fields[last_pos].get("type") == "note":
            if len(fields) - 1:
                last_pos -= 1
        for idx, field in enumerate(fields):
            if idx != last_pos and field.get("type", "") in sensitive_fields:
                return prep_return(
                    _(
                        "Questions for which values can contain "
                        "spaces are only allowed on last "
                        "position of group (%s)" % field.get("name")
                    )
                )
    # separator is not set or is within BASE64 alphabet and sms_allow_media
    separator = json_survey.get("sms_separator", DEFAULT_SEPARATOR) or DEFAULT_SEPARATOR
    sms_allow_media = bool(
        json_survey.get("sms_allow_media", DEFAULT_ALLOW_MEDIA) or DEFAULT_ALLOW_MEDIA
    )
    if sms_allow_media and separator in BASE64_ALPHABET:
        return prep_return(
            _(
                "When allowing medias ('sms_allow_media'), your "
                "separator (%s) must be outside Base64 alphabet "
                "(letters, digits and +/=). "
                "You case use '#' instead." % separator
            )
        )

    # WARNINGS
    warnings = []
    # sms_separator not set
    if not json_survey.get("sms_separator", ""):
        warnings.append(
            "<li>You have not set a separator. Default '+' "
            "separator will be used.</li>"
        )
    # has date field with no sms_date_format
    if not json_survey.get("sms_date_format", ""):
        for group in groups:
            if sum([1 for e in group.get("children", [{}]) if e.get("type") == "date"]):
                warnings.append(
                    "<li>You have 'date' fields without "
                    "explicitly setting a date format. "
                    "Default (%s) will be used.</li>" % DEFAULT_DATE_FORMAT
                )
                break
    # has datetime field with no datetime format
    if not json_survey.get("sms_date_format", ""):
        for group in groups:
            if sum(
                [1 for e in group.get("children", [{}]) if e.get("type") == "datetime"]
            ):
                warnings.append(
                    "<li>You have 'datetime' fields without "
                    "explicitly setting a datetime format. "
                    "Default (%s) will be used.</li>" % DEFAULT_DATETIME_FORMAT
                )
                break

    # date or datetime format contain space
    if "date" in sensitive_fields:
        warnings.append(
            "<li>'sms_date_format' contains space which will "
            "require 'date' questions to be positioned at "
            "the end of groups (%s).</li>" % date_format
        )
    if "datetime" in sensitive_fields:
        warnings.append(
            "<li>'sms_datetime_format' contains space which will "
            "require 'datetime' questions to be positioned at "
            "the end of groups (%s).</li>" % datetime_format
        )

    if len(warnings):
        return prep_return("".join(warnings), comp=1)

    # Good to go
    return prep_return(_("Note that your form is also SMS comptatible."), 2)
