from rest_framework import viewsets

from onadata.apps.logger.models import MergedXForm
from onadata.libs.serializers.merged_xform_serializer import \
    MergedXFormSerializer


class MergedXFormViewSet(viewsets.ModelViewSet):
    """
    Merged XForms viewset: create, list, retrieve, destroy
    """

    queryset = MergedXForm.objects.all()
    serializer_class = MergedXFormSerializer
