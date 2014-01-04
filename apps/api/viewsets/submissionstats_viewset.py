from rest_framework import viewsets
from rest_framework import exceptions
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.reverse import reverse

from apps.api.tools import get_accessible_forms,\
    get_form_submissions_grouped_by_field, get_xform
from apps.odk_logger.models import Instance


class SubmissionStatsViewSet(viewsets.ViewSet):
    """
Provides submissions counts grouped by a specified field.
It accepts query parameters `group` and `name`. Default result
is grouped by `_submission_time`, hence you get submission counts per day.
If a date field is used as the group, the result will be grouped by day.

* *group* - field to group submission counts by
* *name* - name to be applied to the group on results

Example:

    GET /api/v1/stats/submissions/ukanga/1?
    group=_submission_time&name=day_of_submission

Response:

    [
        {
            "count": 8,
            "day_of_submission": "2013-11-15",
        },
        {
            "count": 99,
            "day_of_submission": "2013-11-16",
        },
        {
            "count": 133,
            "day_of_submission": "2013-11-17",
        },
        {
            "count": 162,
            "day_of_submission": "2013-11-18",
        },
        {
            "count": 102,
            "day_of_submission": "2013-11-19",
        }
    ]
"""
    permission_classes = [permissions.IsAuthenticated, ]
    lookup_field = 'owner'
    lookup_fields = ('owner', 'formid', 'dataid')
    extra_lookup_fields = None
    queryset = Instance.objects.all()

    def _get_formlist_data_points(self, request, owner=None):
        xforms = get_accessible_forms(owner)
        # filter by tags if available.
        tags = self.request.QUERY_PARAMS.get('tags', None)
        if tags and isinstance(tags, basestring):
            tags = tags.split(',')
            xforms = xforms.filter(tags__name__in=tags).distinct()
        rs = {}
        for xform in xforms.distinct():
            point = {u"%s" % xform.id_string:
                     reverse("submissionstats-list", kwargs={
                             "formid": xform.pk,
                             "owner": xform.user.username},
                             request=request)}
            rs.update(point)
        return rs

    def list(self, request, owner=None, formid=None, **kwargs):
        if owner is None and not request.user.is_anonymous():
            owner = request.user.username

        data = []

        if formid:
            xform = get_xform(formid, request)

            field = '_submission_time'
            name = 'date_of_submission'
            group = request.QUERY_PARAMS.get('group', None)
            alt_name = request.QUERY_PARAMS.get('name', None)

            if group:
                name = field = group
            if alt_name:
                name = alt_name

            try:
                data = get_form_submissions_grouped_by_field(
                    xform, field, name)
            except ValueError as e:
                raise exceptions.ParseError(detail=e.message)
        else:
            data = self._get_formlist_data_points(request, owner)

        return Response(data)
