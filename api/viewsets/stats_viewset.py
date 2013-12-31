from rest_framework import viewsets
from rest_framework import exceptions
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.reverse import reverse

from api.tools import get_accessible_forms, get_all_stats, get_xform


from odk_logger.models import Instance


class StatsViewSet(viewsets.ViewSet):
    """
Stats summary for median, mean, mode, range, max, min

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
        if owner is None and not request.user.is_anonymous():
            owner = request.user.username

        data = []

        if formid:
            xform = get_xform(formid, request)
            try:
                field = request.QUERY_PARAMS.get('field', None)
                data = get_all_stats(xform, field)
            except ValueError as e:
                raise exceptions.ParseError(detail=e.message)
        else:
            data = self._get_formlist_data_points(request, owner)

        return Response(data)
