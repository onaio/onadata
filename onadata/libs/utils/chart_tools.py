from onadata.apps.api.tools import get_form_submissions_grouped_by_field
from onadata.libs.utils import common_tags


# list of fields we can chart
CHART_FIELDS = ['select one', 'integer', 'decimal', 'date', 'datetime', 'start',
                'end']
# numeric, categorized
DATA_TYPE_MAP = {
    'integer': 'numeric',
    'decimal': 'numeric',
    'datetime': 'time_based',
    'date': 'time_based',
    'start': 'time_based',
    'end': 'time_based'
}


def build_chart_data_for_field(xform, field):
    # check if its the special _submission_time META
    if isinstance(field, basestring) and field == common_tags.SUBMISSION_TIME:
        field_type = 'datetime'
        field_name = common_tags.SUBMISSION_TIME
    else:
        # TODO: merge choices with results and set 0's on any missing fields, i.e. they didn't have responses
        field_type = field.type
        field_name = field.name

    if field_type == 'select one':
        # TODO: if the field is a select, get a summary of the choices
        choices = [c for c in field.get('children')]

    result = get_form_submissions_grouped_by_field(xform, field_name)
    data_type = DATA_TYPE_MAP.get(field_type, 'categorized')

    # for date fields, strip out None values
    if data_type == 'time_based':
        result = [r for r in result if r[field_name] is not None]

    data = {
        'field_name': field_name,
        'field_type': field_type,
        'data_type': data_type,
        'data': result
    }
    return data


def build_chart_data(xform):
    dd = xform.data_dictionary()
    # only use chart-able fields
    fields = filter(
        lambda f: f.type in CHART_FIELDS, [e for e in dd.survey_elements])

    data = []

    for field in fields:
        d = build_chart_data_for_field(xform, field)
        data.append(d)

    return data