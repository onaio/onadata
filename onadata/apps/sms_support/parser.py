# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu
"""
SMS parser module - utility functionality to process SMS messages.
"""
import base64
import binascii
import logging
import re
from datetime import date, datetime
from io import BytesIO

from django.utils.translation import gettext as _

from onadata.apps.logger.models import XForm
from onadata.apps.sms_support.tools import (
    DEFAULT_DATE_FORMAT,
    DEFAULT_DATETIME_FORMAT,
    DEFAULT_SEPARATOR,
    MEDIA_TYPES,
    META_FIELDS,
    NA_VALUE,
    SMS_API_ERROR,
    SMS_PARSING_ERROR,
    SMS_SUBMISSION_ACCEPTED,
    SMS_SUBMISSION_REFUSED,
    generate_instance,
    is_last,
    sms_media_to_file,
)
from onadata.libs.utils.logger_tools import dict2xform


class SMSSyntaxError(ValueError):
    """A custom SMS syntax error exception class."""


class SMSCastingError(ValueError):
    """A custom SMS type casting error exception class."""

    def __init__(self, message, question=None):
        if question:
            message = _("%(question)s: %(message)s") % {
                "question": question,
                "message": message,
            }
        super().__init__(message)


# pylint: disable=too-many-locals,too-many-branches,too-many-statements
# pylint: disable=too-many-return-statements
def parse_sms_text(xform, identity, sms_text):
    """Parses an SMS text to return XForm specific answers, media, notes."""

    json_survey = xform.json_dict()

    separator = json_survey.get("sms_separator", DEFAULT_SEPARATOR) or DEFAULT_SEPARATOR

    allow_media = bool(json_survey.get("sms_allow_media", False))

    xlsf_date_fmt = (
        json_survey.get("sms_date_format", DEFAULT_DATE_FORMAT) or DEFAULT_DATE_FORMAT
    )
    xlsf_datetime_fmt = (
        json_survey.get("sms_date_format", DEFAULT_DATETIME_FORMAT)
        or DEFAULT_DATETIME_FORMAT
    )

    # extract SMS data into indexed groups of values
    groups = {}
    for group in sms_text.split(separator)[1:]:
        group_id, group_text = [s.strip() for s in group.split(None, 1)]
        groups.update({group_id: [s.strip() for s in group_text.split(None)]})

    def cast_sms_value(value, question, medias=None):
        """Check data type of value and return cleaned version"""

        medias = [] if medias is None else medias
        xlsf_type = question.get("type")
        xlsf_name = question.get("name")
        xlsf_choices = question.get("children")
        xlsf_required = bool(
            question.get("bind", {}).get("required", "").lower() in ("yes", "true")
        )

        # we don't handle constraint for now as it's a little complex and
        # unsafe.
        # xlsf_constraint=question.get('constraint')

        if xlsf_required and not value:
            raise SMSCastingError(_("Required field missing"), xlsf_name)

        def safe_wrap(func):
            try:
                return func()
            except Exception as error:
                raise SMSCastingError(
                    _("%(error)s") % {"error": error}, xlsf_name
                ) from error

        def media_value(value, medias):
            """handle media values

            extract name and base64 data.
            fills the media holder with (name, data) tuple"""
            try:
                filename, b64content = value.split(";", 1)
                medias.append((filename, base64.b64decode(b64content)))
                return filename
            except (AttributeError, TypeError, binascii.Error) as error:
                raise SMSCastingError(
                    _("Media file format incorrect. %(except)r") % {"except": error},
                    xlsf_name,
                ) from error

        if xlsf_type == "text":
            return safe_wrap(lambda: str(value))
        if xlsf_type == "integer":
            return safe_wrap(lambda: int(value))
        if xlsf_type == "decimal":
            return safe_wrap(lambda: float(value))
        if xlsf_type == "select one":
            for choice in xlsf_choices:
                if choice.get("sms_option") == value:
                    return choice.get("name")
            raise SMSCastingError(
                _("No matching choice for '%(input)s'") % {"input": value}, xlsf_name
            )
        if xlsf_type == "select all that apply":
            values = [s.strip() for s in value.split()]
            ret_values = []
            for indiv_value in values:
                for choice in xlsf_choices:
                    if choice.get("sms_option") == indiv_value:
                        ret_values.append(choice.get("name"))
            return " ".join(ret_values)
        if xlsf_type == "geopoint":
            err_msg = _("Incorrect geopoint coordinates.")
            geodata = [s.strip() for s in value.split()]
            if len(geodata) < 2 and len(geodata) > 4:
                raise SMSCastingError(err_msg, xlsf_name)
            try:
                # check that latitude and longitude are floats
                lat, lon = [float(v) for v in geodata[:2]]
                # and within sphere boundaries
                if -90 > lat > 90 or -180 > lon > 180:
                    raise SMSCastingError(err_msg, xlsf_name)
                if len(geodata) == 4:
                    # check that altitude and accuracy are integers
                    for geo_value in geodata[2:4]:
                        int(geo_value)
                elif len(geodata) == 3:
                    # check that altitude is integer
                    int(geodata[2])
            except ValueError as error:
                raise SMSCastingError(error, xlsf_name) from error
            return " ".join(geodata)
        if xlsf_type in MEDIA_TYPES:
            # media content (image, video, audio) must be formatted as:
            # file_name;base64 encodeed content.
            # Example: hello.jpg;dGhpcyBpcyBteSBwaWN0dXJlIQ==
            return media_value(value, medias)
        if xlsf_type == "barcode":
            return safe_wrap(lambda: str(value))
        if xlsf_type == "date":
            return safe_wrap(lambda: datetime.strptime(value, xlsf_date_fmt).date())
        if xlsf_type == "datetime":
            return safe_wrap(lambda: datetime.strptime(value, xlsf_datetime_fmt))
        if xlsf_type == "note":
            return safe_wrap(lambda: "")
        raise SMSCastingError(
            _("Unsuported column '%(type)s'") % {"type": xlsf_type}, xlsf_name
        )

    def get_meta_value(xlsf_type, identity):
        """XLSForm Meta field value"""
        if xlsf_type in ("deviceid", "subscriberid", "imei"):
            return NA_VALUE
        if xlsf_type in ("start", "end"):
            return datetime.now().isoformat()
        if xlsf_type == "today":
            return date.today().isoformat()
        if xlsf_type == "phonenumber":
            return identity
        return NA_VALUE

    # holder for all properly formated answers
    survey_answers = {}
    # list of (name, data) tuples for media contents
    medias = []
    # keep track of required questions
    notes = []

    # loop on all XLSForm questions
    for expected_group in json_survey.get("children", [{}]):
        if not expected_group.get("type") == "group":
            # non-grouped questions are not valid for SMS
            continue

        # retrieve part of SMS text for this group
        group_id = expected_group.get("sms_field")
        answers = groups.get(group_id)
        if not group_id or (not answers and not group_id.startswith("meta")):
            # group is not meant to be filled by SMS
            # or hasn't been filled
            continue

        # Add a holder for this group's answers data
        survey_answers.update({expected_group.get("name"): {}})

        # retrieve question definition for each answer
        egroups = expected_group.get("children", [{}])

        # number of intermediate, omited questions (medias)
        step_back = 0
        for idx, question in enumerate(egroups):

            real_value = None

            question_type = question.get("type")
            if question_type == "calculate":
                # 'calculate' question are not implemented.
                # 'note' ones are just meant to be displayed on device
                continue

            if question_type == "note":
                if not question.get("constraint", ""):
                    notes.append(question.get("label"))
                continue

            if not allow_media and question_type in MEDIA_TYPES:
                # if medias for SMS has not been explicitly allowed
                # they are considered excluded.
                step_back += 1
                continue

            # pop the number of skipped questions
            # so that out index is valid even if the form
            # contain medias questions (and medias are disabled)
            sidx = idx - step_back

            answer = ""
            if question_type in META_FIELDS:
                # some question are not to be fed by users
                real_value = get_meta_value(xlsf_type=question_type, identity=identity)
            else:
                # actual SMS-sent answer.
                # Only last answer/question of each group is allowed
                # to have multiple spaces
                if is_last(idx, egroups):
                    answer = " ".join(answers[idx:])
                else:
                    answer = answers[sidx]

            if real_value is None:
                # retrieve actual value and fail if it doesn't meet reqs.
                real_value = cast_sms_value(answer, question=question, medias=medias)

            # set value to its question name
            survey_answers[expected_group.get("name")].update(
                {question.get("name"): real_value}
            )

    return survey_answers, medias, notes


# pylint: disable=too-many-statements
def process_incoming_smses(username, incomings, id_string=None):  # noqa C901
    """Process Incoming (identity, text[, id_string]) SMS"""

    xforms = []
    medias = []
    xforms_notes = []
    responses = []
    json_submissions = []
    resp_str = {
        "success": _(
            "[SUCCESS] Your submission has been accepted. It's ID is {{ id }}."
        )
    }

    # pylint: disable=too-many-branches
    def process_incoming(incoming, id_string):
        # assign variables
        if len(incoming) >= 2:
            identity = incoming[0].strip().lower()
            text = incoming[1].strip().lower()
            # if the tuple contains an id_string, use it, otherwise default
            if id_string is None and len(incoming) >= 3:
                id_string = incoming[2]
        else:
            responses.append(
                {
                    "code": SMS_API_ERROR,
                    "text": _("Missing 'identity' or 'text' field."),
                }
            )
            return

        if not identity.strip() or not text.strip():
            responses.append(
                {
                    "code": SMS_API_ERROR,
                    "text": _("'identity' and 'text' fields can not be empty."),
                }
            )
            return

        # if no id_string has been supplied
        # we expect the SMS to be prefixed with the form's sms_id_string
        if id_string is None:
            keyword, text = [s.strip() for s in text.split(None, 1)]
            xform = XForm.objects.get(user__username=username, sms_id_string=keyword)
        else:
            xform = XForm.objects.get(user__username=username, id_string=id_string)

        if not xform.allows_sms:
            responses.append(
                {
                    "code": SMS_SUBMISSION_REFUSED,
                    "text": _(
                        "The form '%(id_string)s' does not accept SMS submissions."
                    )
                    % {"id_string": xform.id_string},
                }
            )
            return

        # parse text into a dict object of groups with values
        json_submission, medias_submission, notes = parse_sms_text(
            xform, identity, text
        )

        # retrieve sms_response if exist in the form.
        json_survey = xform.json_dict()
        if json_survey.get("sms_response"):
            resp_str.update({"success": json_survey.get("sms_response")})

        # check that the form contains at least one filled group
        meta_groups = sum(1 for k in list(json_submission) if k.startswith("meta"))
        if len(list(json_submission)) <= meta_groups:
            responses.append(
                {
                    "code": SMS_PARSING_ERROR,
                    "text": _("There must be at least one group of questions filled."),
                }
            )
            return

        # check that required fields have been filled
        required_fields = [
            f.get("name")
            for g in json_survey.get("children", {})
            for f in g.get("children", {})
            if f.get("bind", {}).get("required", "no") == "yes"
        ]
        submitted_fields = {}
        for group in json_submission.values():
            submitted_fields.update(group)

        for field in required_fields:
            if not submitted_fields.get(field):
                responses.append(
                    {
                        "code": SMS_SUBMISSION_REFUSED,
                        "text": _(f"Required field `{field}` is  missing."),
                    }
                )
                return

        # convert dict object into an XForm string
        xml_submission = dict2xform(jsform=json_submission, form_id=xform.id_string)

        # compute notes
        data = {}
        for group in json_submission.values():
            data.update(group)
        for idx, note in enumerate(notes):
            try:
                notes[idx] = note.replace("${", "{").format(**data)
            except AttributeError as error:
                logging.exception("Updating note threw exception: %s", str(error))

        # process_incoming expects submission to be a file-like object
        xforms.append(BytesIO(xml_submission.encode("utf-8")))
        medias.append(medias_submission)
        json_submissions.append(json_submission)
        xforms_notes.append(notes)

    for incoming in incomings:
        try:
            process_incoming(incoming, id_string)
        except (SMSCastingError, SMSSyntaxError, ValueError) as error:
            responses.append({"code": SMS_PARSING_ERROR, "text": str(error)})

    for idx, xform in enumerate(xforms):
        # generate_instance expects media as a request.FILES.values() list
        xform_medias = [sms_media_to_file(f, n) for n, f in medias[idx]]
        # create the instance in the data base
        response = generate_instance(
            username=username, xml_file=xform, media_files=xform_medias
        )
        if response.get("code") == SMS_SUBMISSION_ACCEPTED:
            success_response = re.sub(
                r"{{\s*[i,d,I,D]{2}\s*}}",
                response.get("id"),
                resp_str.get("success"),
                re.I,
            )

            # extend success_response with data from the answers
            data = {}
            for group in json_submissions[idx].values():
                data.update(group)
            success_response = success_response.replace("${", "{").format(**data)
            response.update({"text": success_response})
            # add sendouts (notes)
            response.update({"sendouts": xforms_notes[idx]})
        responses.append(response)

    return responses
