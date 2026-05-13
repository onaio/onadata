# -*- coding: utf-8 -*-
"""
Geometry bbox helpers for tile-based map views.

Mirrors the filter shape of the `form_tiles()` PostGIS function so the frontend
can fit the map to the same dataset Martin serves: non-deleted instances whose
`xform_id` is in the requested set, optionally filtered by a DataView's query
JSON (same semantics `form_tiles()` applies server-side).
"""

from django.contrib.gis.db.models import Extent

from onadata.apps.logger.models import Instance
from onadata.libs.utils.dataview_filters import apply_filters


def compute_instance_bbox(xform_ids, dataview=None):
    """Return ``[min_lng, min_lat, max_lng, max_lat]`` for the requested forms.

    ``xform_ids`` is an iterable of XForm primary keys; for regular forms this
    is a single-element list, for merged datasets it's the underlying xforms.

    ``dataview``, when supplied, applies its ``query`` JSON as additional
    filters via the same ``apply_filters`` helper used by the data endpoint.

    Returns ``None`` when no instances match (empty dataset or all rows have
    NULL geoms) so callers can render a fallback view.
    """
    ids = list(xform_ids)
    if not ids:
        return None

    queryset = Instance.objects.filter(
        xform_id__in=ids,
        deleted_at__isnull=True,
        geom__isnull=False,
    )

    if dataview is not None:
        queryset = apply_filters(queryset, dataview.query)

    extent = queryset.aggregate(extent=Extent("geom")).get("extent")
    if not extent:
        return None
    return list(extent)
