import re

from onadata.libs.data.query import get_form_submissions_grouped_by_field
from onadata.libs.utils import common_tags


# list of fields we can chart
CHART_FIELDS = ['select one', 'integer', 'decimal', 'date', 'datetime',
                'start', 'end', 'today']
# numeric, categorized
DATA_TYPE_MAP = {
    'integer': 'numeric',
    'decimal': 'numeric',
    'datetime': 'time_based',
    'date': 'time_based',
    'start': 'time_based',
    'end': 'time_based',
    'today': 'time_based',
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


def get_choice_label(choices, string):
    labels = []

    if string and choices:
        for name in string.split(' '):
            for choice in choices:
                if choice['name'] == name:
                    labels.append(choice['label'])
                    break

    return labels


def build_chart_data_for_field(xform, field, language_index=0):
    # check if its the special _submission_time META
    if isinstance(field, basestring) and field == common_tags.SUBMISSION_TIME:
        field_label = 'Submission Time'
        field_xpath = '_submission_time'
        field_type = 'datetime'
    else:
        # TODO: merge choices with results and set 0's on any missing fields,
        # i.e. they didn't have responses

        # check if label is dict i.e. multilang
        if isinstance(field.label, dict) and len(field.label.keys()) > 0:
            languages = field.label.keys()
            language_index = min(language_index, len(languages) - 1)
            field_label = field.label[languages[language_index]]
        else:
            field_label = field.label or field.name

        field_xpath = field.get_abbreviated_xpath()
        field_type = field.type

    data_type = DATA_TYPE_MAP.get(field_type, 'categorized')
    field_name = field.name if not isinstance(field, basestring) else field

    result = get_form_submissions_grouped_by_field(
        xform, field_xpath, field_name)

    # truncate field name to 63 characters to fix #354
    truncated_name = field_name[0:POSTGRES_ALIAS_LENGTH]
    truncated_name = truncated_name.encode('utf-8')

    if data_type == 'categorized':
        if result:
            choices = []
            if field.children:
                choices = field.children
            else:
                if field.get('parent') and field.get('parent').get('choices'):
                    choices = field.get('parent').get('choices')\
                        .get(truncated_name.lower(), [])

            for item in result:
                item[truncated_name] = get_choice_label(
                    choices, item[truncated_name])

    # replace truncated field names in the result set with the field name key
    field_name = field_name.encode('utf-8')
    for item in result:
        if field_name != truncated_name:
            item[field_name] = item[truncated_name]
            del(item[truncated_name])

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
        'field_xpath': field_name,
        'field_name': field_xpath.replace('/', '-'),
        'field_type': field_type
    }


def calculate_ranges(page, items_per_page, total_items):
    """Return the offset and end indices for a slice."""
    # offset  cannot be more than total_items
    offset = min(page * items_per_page, total_items)

    end = min(offset + items_per_page, total_items)
    # returns the offset and the end for a slice
    return offset, end


def build_chart_data(xform, language_index=0, page=0):
    dd = xform.data_dictionary()
    # only use chart-able fields

    fields = filter(
        lambda f: f.type in CHART_FIELDS, [e for e in dd.survey_elements])

    # prepend submission time
    fields[:0] = [common_tags.SUBMISSION_TIME]

    # get chart data for fields within this `page`
    start, end = calculate_ranges(page, CHARTS_PER_PAGE, len(fields))
    fields = fields[start:end]

    return [build_chart_data_for_field(xform, field, language_index)
            for field in fields]
