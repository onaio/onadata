from django.http import HttpResponseBadRequest
from django.utils.translation import ugettext as _
from rest_framework import viewsets
from rest_framework import exceptions
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.reverse import reverse

from onadata.apps.api.tools import get_accessible_forms, get_all_stats,\
    get_xform, get_mode_for_numeric_fields_in_form,\
    get_mean_for_numeric_fields_in_form,\
    get_median_for_numeric_fields_in_form, get_min_max_range
from onadata.apps.logger.models import Instance


STATS_FUNCTIONS = {
    'mean': get_mean_for_numeric_fields_in_form,
    'median': get_median_for_numeric_fields_in_form,
    'mode': get_mode_for_numeric_fields_in_form,
    'range': get_min_max_range
}


class StatsViewSet(viewsets.ViewSet):
    """
Stats summary for median, mean, mode, range, max, min.
A query parameter `method` can be used to limit the results to either
`mean`, `median`, `mode` or `range` only results.

Example:

    GET /api/v1/stats/ukanga/1?

Response:

    [
        {
            "age":
                {
                    "median": 8,
                    "mean": 23.4,
                    "mode": 23,
                    "range": 24,
                    "max": 28,
                    "min": 4
                },
        ...
    ]

Example:

    GET /api/v1/stats/ukanga/1?method=median

Response:

    [
        {
            "age":
                {
                    "median": 8,
                },
        ...
    ]
"""
    permission_classes = [permissions.IsAuthenticated, ]
    lookup_field = 'owner'
    lookup_fields = ('owner', 'formid')
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
                     reverse("stats-list", kwargs={
                             "formid": xform.pk,
                             "owner": xform.user.username},
                             request=request)}
            rs.update(point)
        return rs

    def list(self, request, owner=None, formid=None, **kwargs):
        owner = owner is None and (
            not request.user.is_anonymous() and request.user.username)

        data = []

        if formid:
            xform = get_xform(formid, request)
            try:
                method = request.QUERY_PARAMS.get('method', None)
                field = request.QUERY_PARAMS.get('field', None)

                # check that field is in XForm
                if field and field not in xform.data_dictionary().get_keys():
                    return HttpResponseBadRequest(_("Field not in XForm."))

                data = get_all_stats(xform, field) if method is None else\
                    STATS_FUNCTIONS[method.lower()](xform, field)
            except ValueError as e:
                raise exceptions.ParseError(detail=e.message)
        else:
            data = self._get_formlist_data_points(request, owner)

        return Response(data)
