from onadata.libs.data.query import get_form_submissions_grouped_by_field


def get_form_submissions_per_day(xform):
    """Number of submissions per day for the form."""
    return get_form_submissions_grouped_by_field(xform, '_submission_time',
                                                 'date')
