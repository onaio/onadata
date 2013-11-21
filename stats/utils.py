from django.db import connection
from django.db.models import Count


def get_form_submissions_per_day(xform):
    """Number of submissions per day for the form."""
    day = connection.ops.date_trunc_sql('day', 'date_created')
    qs = xform.surveys.extra({'date': day}).values('date')
    return qs.annotate(count=Count('pk'))
