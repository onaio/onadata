from odk_viewer.models import ParsedInstance


def get_form_submissions_per_day(xform):
    """Number of submissions per day for the form."""
    query = {}
    query[ParsedInstance.USERFORM_ID] =\
        u'%s_%s' % (xform.user.username, xform.id_string)
    pipeline = [
        {
            "$group": {
                "_id": {
                    "$substr": ['$_submission_time', 0, 10]
                },
                "count": {"$sum": 1}
            }
        },
        {
            "$sort": {"_id": 1}
        },
        {
            "$project": {
                "date": "$_id",
                "count": 1
            }
        }
    ]
    kargs = {
        'query': query,
        'pipeline': pipeline
    }
    return ParsedInstance.mongo_aggregate(**kargs)
