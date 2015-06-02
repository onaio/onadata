from rest_framework import serializers
from rest_framework.reverse import reverse

from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.models.data_view import DataView

class WidgetRelatedField(serializers.RelatedField):

    def to_representation(self, value):
        import ipdb
        ipdb.set_trace()
        if isinstance(value, XForm):
            return 'Bookmark: ' + value.pk
        elif isinstance(value, DataView):
            return 'Note: ' + value.xform
        raise Exception('Unexpected type of tagged object')



    #def to_internal_value(self, data):
    #    import ipdb
        ipdb.set_trace()