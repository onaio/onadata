"""
Submission Review Viewset Module
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from onadata.apps.api import permissions
from onadata.apps.api.tools import get_baseviewset_class
from onadata.apps.logger.models import SubmissionReview
from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.serializers.submission_review_serializer import \
    SubmissionReviewSerializer

BaseViewset = get_baseviewset_class()


# pylint: disable=too-many-ancestors
class SubmissionReviewViewSet(AuthenticateHeaderMixin, CacheControlMixin,
                              ETagsMixin, BaseViewset, ModelViewSet):
    """
    Submission Review ViewSet class
    """
    queryset = SubmissionReview.objects.filter(deleted_at__isnull=True)
    serializer_class = SubmissionReviewSerializer
    permission_classes = [
        permissions.ViewDjangoObjectPermissions, permissions.IsAuthenticated
    ]
    filter_fields = ['instance', 'created_by', 'status']

    def destroy(self, request, *args, **kwards):
        """
        Custom destroy method
        """
        obj = self.get_object()
        obj.set_deleted()

        return Response(status=status.HTTP_204_NO_CONTENT)
