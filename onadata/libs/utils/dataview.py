
from rest_framework.exceptions import ParseError
from onadata.apps.logger.models import DataView
from django.core.cache import cache
from onadata.libs.utils.cache_tools import DATAVIEW_COUNT


def get_dataview_count(dataview):
    count = cache.get('{}{}'.format(DATAVIEW_COUNT, dataview.xform.pk))

    if count:
        return count

    count = DataView.query_data(dataview, count=True)
    if 'error' in count:
        raise ParseError(count.get('error'))

    if 'count' in count[0]:
        count = count[0].get('count')
        cache.set('{}{}'.format(DATAVIEW_COUNT, dataview.xform.pk),
                  count)

        return count
