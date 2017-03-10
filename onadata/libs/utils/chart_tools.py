import re

import six
from django.db.utils import DataError
from django.http import Http404
from rest_framework.exceptions import ParseError

from onadata.apps.logger.models.data_view import DataView
from onadata.apps.logger.models.xform import XForm
from onadata.libs.data.query import (
    get_form_submissions_aggregated_by_select_one,
    get_form_submissions_grouped_by_field,
    get_form_submissions_grouped_by_select_one)
from onadata.libs.utils import common_tags

# list of fields we can chart
CHART_FIELDS = [
    'select one', 'integer', 'decimal', 'date', 'datetime', 'start', 'end',
    'today'
]
# numeric, categorized
DATA_TYPE_MAP = {
    'integer': 'numeric',
    'decimal': 'numeric',
    'datetime': 'time_based',
    'date': 'time_based',
    'start': 'time_based',
    'end': 'time_based',
    'today': 'time_based',
    'calculate': 'numeric',
}

FIELD_DATA_MAP = {
    common_tags.SUBMISSION_TIME:
    ('Submission Time', '_submission_time', 'datetime'),
    common_tags.SUBMITTED_BY: ('Submission By', '_submitted_by', 'text'),
    common_tags.DURATION: ('Duration', '_duration', 'integer')
}

CHARTS_PER_PAGE = 20

POSTGRES_ALIAS_LENGTH = 63

timezone_re = re.compile(r'(.+)\+(\d+)')


def utc_time_string_for_javascript(date_string):
    """
    Convert 2014-01-16T12:07:23.322+03 to 2014-01-16T12:07:23.322+03:00

    Cant use datetime.str[fp]time here since python 2.7's %z is platform
    dependant - http://stackoverflow.com/questions/2609259/converting-string-t\
        o-datetime-object-in-python

    """
    match = timezone_re.match(date_string)
    if not match:
        raise ValueError(
            "{} fos not match the format 2014-01-16T12:07:23.322+03".format(
                date_string))

    date_time = match.groups()[0]
    tz = match.groups()[1]
    if len(tz) == 2:
        tz += '00'
    elif len(tz) != 4:
        raise ValueError("len of {} must either be 2 or 4")

    return "{}+{}".format(date_time, tz)


def find_choice_label(choices, string):
    for choice in choices:
        if choice['name'] == string:
            return choice['label']


def get_field_choices(field, xform):
    """
    Retrieve field choices from a form survey element
    :param field:
    :param xform:
    :return: Form field choices
    """
    choices = xform.survey.get('choices')

    if isinstance(field, basestring):
        choices = choices.get(field)
    elif 'name' in field and field.name in choices:
        choices = choices.get(field.name)
    elif 'itemset' in field:
        choices = choices.get(field.itemset)

    return choices


def get_choice_label(choices, string):
    """
    `string` is the name value found in the choices sheet.

    Select one names should not contain spaces but some do and this conflicts
    with Select Multiple fields which use spaces to distinguish multiple
    choices.

    A temporal fix to this is to search the choices list for both the
    full-string and the split keys.
    """
    labels = []

    if string and choices:
        label = find_choice_label(choices, string)

        if label:
            labels.append(label)
        else:
            # Try to get labels by splitting the string
            labels = [
                find_choice_label(choices, name) for name in string.split(" ")
            ]

            # If any split string does not have a label it is not a multiselect
            # but a missing label, use string
            if None in labels:
                labels = [string]
    elif not choices:
        labels = [string]

    return labels


def _flatten_multiple_dict_into_one(field_name, group_by_name, data):
    # truncate field name to 63 characters to fix #354
    truncated_field_name = field_name[0:POSTGRES_ALIAS_LENGTH]
    truncated_group_by_name = group_by_name[0:POSTGRES_ALIAS_LENGTH]
    final = [{
        truncated_field_name: b,
        'items': []
    } for b in list({a.get(truncated_field_name)
                     for a in data})]

    for a in data:
        for b in final:
            if a.get(truncated_field_name) == b.get(truncated_field_name):
                b['items'].append({
                    truncated_group_by_name:
                    a.get(truncated_group_by_name),
                    'count':
                    a.get('count')
                })

    return final


def _use_labels_from_field_name(field_name,
                                field,
                                data_type,
                                data,
                                choices=None):
    # truncate field name to 63 characters to fix #354
    truncated_name = field_name[0:POSTGRES_ALIAS_LENGTH]
    truncated_name = truncated_name.encode('utf-8')

    if data_type == 'categorized' and field_name != common_tags.SUBMITTED_BY:
        if data:
            if field.children:
                choices = field.children

            for item in data:
                item[truncated_name] = get_choice_label(choices,
                                                        item[truncated_name])

    # replace truncated field names in the result set with the field name key
    field_name = field_name.encode('utf-8')

    for item in data:
        if field_name != truncated_name:
            item[field_name] = item[truncated_name]
            del (item[truncated_name])

    return data


def _use_labels_from_group_by_name(field_name,
                                   field,
                                   data_type,
                                   data,
                                   choices=None):
    # truncate field name to 63 characters to fix #354
    truncated_name = field_name[0:POSTGRES_ALIAS_LENGTH]
    truncated_name = truncated_name.encode('utf-8')

    if data_type == 'categorized':
        if data:
            if field.children:
                choices = field.children

            for item in data:
                if 'items' in item:
                    for i in item.get('items'):
                        i[truncated_name] = get_choice_label(choices,
                                                             i[truncated_name])
                else:
                    item[truncated_name] = \
                        get_choice_label(choices, item[truncated_name])

    # replace truncated field names in the result set with the field name key
    field_name = field_name.encode('utf-8')

    for item in data:
        if 'items' in item:
            for i in item.get('items'):
                if field_name != truncated_name:
                    i[field_name] = i[truncated_name]
                    del (i[truncated_name])
        else:
            if field_name != truncated_name:
                item[field_name] = item[truncated_name]
                del (item[truncated_name])

    return data


def build_chart_data_for_field(xform,
                               field,
                               language_index=0,
                               choices=None,
                               group_by=None,
                               data_view=None):
    # check if its the special _submission_time META
    if isinstance(field, basestring):
        field_label, field_xpath, field_type = FIELD_DATA_MAP.get(field)
    else:
        # TODO: merge choices with results and set 0's on any missing fields,
        # i.e. they didn't have responses

        field_label = get_field_label(field, language_index)
        field_xpath = field.get_abbreviated_xpath()
        field_type = field.type

    data_type = DATA_TYPE_MAP.get(field_type, 'categorized')
    field_name = field.name if not isinstance(field, basestring) else field

    if group_by:
        group_by_name = group_by.get_abbreviated_xpath() \
            if not isinstance(group_by, basestring) else group_by

        if (field_type == common_tags.SELECT_ONE or
                field_name == common_tags.SUBMITTED_BY) and \
                isinstance(group_by, six.string_types):
            result = get_form_submissions_grouped_by_select_one(
                xform, field_xpath, group_by_name, field_name, data_view)
        elif field_type in common_tags.NUMERIC_LIST and \
                isinstance(group_by, six.string_types):
            result = get_form_submissions_aggregated_by_select_one(
                xform, field_xpath, field_name, group_by_name, data_view)
        elif (field_type == common_tags.SELECT_ONE or
              field_name == common_tags.SUBMITTED_BY) and \
                group_by.type == common_tags.SELECT_ONE:
            result = get_form_submissions_grouped_by_select_one(
                xform, field_xpath, group_by_name, field_name, data_view)

            result = _flatten_multiple_dict_into_one(field_name, group_by_name,
                                                     result)
        elif field_type in common_tags.NUMERIC_LIST \
                and group_by.type == common_tags.SELECT_ONE:
            result = get_form_submissions_aggregated_by_select_one(
                xform, field_xpath, field_name, group_by_name, data_view)
        else:
            raise ParseError(u'Cannot group by %s' % group_by_name)
    else:
        result = get_form_submissions_grouped_by_field(xform, field_xpath,
                                                       field_name, data_view)

    result = _use_labels_from_field_name(
        field_name, field, data_type, result, choices=choices)

    if group_by and not isinstance(group_by, six.string_types):
        group_by_data_type = DATA_TYPE_MAP.get(group_by.type, 'categorized')
        grp_choices = get_field_choices(group_by, xform)
        result = _use_labels_from_group_by_name(
            group_by_name,
            group_by,
            group_by_data_type,
            result,
            choices=grp_choices)

    if not group_by:
        result = sorted(result, key=lambda d: d['count'])

    # for date fields, strip out None values
    if data_type == 'time_based':
        result = [r for r in result if r.get(field_name) is not None]
        # for each check if it matches the timezone regexp and convert for js
        for r in result:
            if timezone_re.match(r[field_name]):
                try:
                    r[field_name] = utc_time_string_for_javascript(
                        r[field_name])
                except ValueError:
                    pass

    return {
        'data': result,
        'data_type': data_type,
        'field_label': field_label,
        'field_xpath': field_xpath,
        'field_name': field_name,
        'field_type': field_type,
        'grouped_by': group_by_name if group_by else None
    }


def calculate_ranges(page, items_per_page, total_items):
    """Return the offset and end indices for a slice."""
    # offset  cannot be more than total_items
    offset = min(page * items_per_page, total_items)

    end = min(offset + items_per_page, total_items)
    # returns the offset and the end for a slice
    return offset, end


def build_chart_data(xform, language_index=0, page=0):
    # only use chart-able fields

    fields = filter(lambda f: f.type in CHART_FIELDS,
                    [e for e in xform.survey_elements])

    # prepend submission time
    fields[:0] = [common_tags.SUBMISSION_TIME]

    # get chart data for fields within this `page`
    start, end = calculate_ranges(page, CHARTS_PER_PAGE, len(fields))
    fields = fields[start:end]

    return [
        build_chart_data_for_field(xform, field, language_index)
        for field in fields
    ]


def build_chart_data_from_widget(widget, language_index=0):

    if isinstance(widget.content_object, XForm):
        xform = widget.content_object
    elif isinstance(widget.content_object, DataView):
        xform = widget.content_object.xform
    else:
        raise ParseError("Model not supported")

    field_name = widget.column

    # check if its the special _submission_time META
    if field_name == common_tags.SUBMISSION_TIME:
        field = common_tags.SUBMISSION_TIME
    else:
        # use specified field to get summary
        fields = filter(lambda f: f.name == field_name,
                        [e for e in xform.survey_elements])

        if len(fields) == 0:
            raise ParseError("Field %s does not not exist on the form" %
                             field_name)

        field = fields[0]
    choices = xform.survey.get('choices')

    if choices:
        choices = choices.get(field_name)
    try:
        data = build_chart_data_for_field(
            xform, field, language_index, choices=choices)
    except DataError as e:
        raise ParseError(unicode(e))

    return data


def get_field_from_field_name(field_name, xform):
    # check if its the special _submission_time META
    if field_name == common_tags.SUBMISSION_TIME:
        field = common_tags.SUBMISSION_TIME
    elif field_name == common_tags.SUBMITTED_BY:
        field = common_tags.SUBMITTED_BY
    elif field_name == common_tags.DURATION:
        field = common_tags.DURATION
    else:
        # use specified field to get summary
        fields = filter(lambda f: f.name == field_name,
                        [e for e in xform.survey_elements])

        if len(fields) == 0:
            raise Http404("Field %s does not not exist on the form" %
                          field_name)

        field = fields[0]

    return field


def get_field_from_field_xpath(field_xpath, xform):
    # check if its the special _submission_time META
    if field_xpath == common_tags.SUBMISSION_TIME:
        field = common_tags.SUBMISSION_TIME
    elif field_xpath == common_tags.SUBMITTED_BY:
        field = common_tags.SUBMITTED_BY
    elif field_xpath == common_tags.DURATION:
        field = common_tags.DURATION
    else:
        # use specified field to get summary
        fields = filter(lambda f: f.get_abbreviated_xpath() == field_xpath,
                        [e for e in xform.survey_elements])

        if len(fields) == 0:
            raise Http404("Field %s does not not exist on the form" %
                          field_xpath)

        field = fields[0]

    return field


def get_field_label(field, language_index=0):
    # check if label is dict i.e. multilang
    if isinstance(field.label, dict) and len(field.label.keys()) > 0:
        languages = field.label.keys()
        language_index = min(language_index, len(languages) - 1)
        field_label = field.label[languages[language_index]]
    else:
        field_label = field.label or field.name

    return field_label


def get_chart_data_for_field(field_name,
                             xform,
                             accepted_format,
                             group_by,
                             field_xpath=None,
                             data_view=None):
    """
    Get chart data for a given xlsform field.
    """
    data = {}

    if field_name:
        field = get_field_from_field_name(field_name, xform)

    if group_by:
        group_by = get_field_from_field_xpath(group_by, xform)

    if field_xpath:
        field = get_field_from_field_xpath(field_xpath, xform)

    choices = get_field_choices(field, xform)

    try:
        data = build_chart_data_for_field(
            xform,
            field,
            choices=choices,
            group_by=group_by,
            data_view=data_view)
    except DataError as e:
        raise ParseError(unicode(e))
    else:
        if accepted_format == 'json':
            xform = xform.pk
        elif accepted_format == 'html' and 'data' in data:
            for item in data['data']:
                if isinstance(item[field_name], list):
                    item[field_name] = u', '.join(item[field_name])

        data.update({'xform': xform})

    return data
