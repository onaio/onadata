from rest_framework import viewsets
from rest_framework import permissions

from onadata.apps.logger.models.xform import XForm
from onadata.libs import filters
from onadata.libs.authentication import DigestAuthentication
from onadata.libs.renderers.renderers import XFormListRenderer
from onadata.libs.serializers.xform_serializer import XFormListSerializer


class XFormListApi(viewsets.ReadOnlyModelViewSet):
    authentication_classes = (DigestAuthentication,)
    filter_backends = (filters.AnonDjangoObjectPermissionFilter,)
    model = XForm
    permission_classes = (permissions.IsAuthenticated,)
    renderer_classes = (XFormListRenderer,)
    serializer_class = XFormListSerializer
    template_name = 'api/xformsList.xml'
