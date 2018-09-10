# -*- coding: utf-8 -*-
"""
Submission Review Viewset Module
"""
from __future__ import unicode_literals

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from onadata.apps.api.permissions import SubmissionReviewPermissions
from onadata.apps.api.tools import get_baseviewset_class
from onadata.apps.logger.models import SubmissionReview
from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.mixins.bulk_create_mixin import BulkCreateMixin
from onadata.libs.serializers.submission_review_serializer import \
    SubmissionReviewSerializer

BaseViewset = get_baseviewset_class()


# pylint: disable=too-many-ancestors
class SubmissionReviewViewSet(AuthenticateHeaderMixin, CacheControlMixin,
                              ETagsMixin, BulkCreateMixin, BaseViewset,
                              ModelViewSet):
    """
    Submission Review ViewSet class
    """
    queryset = SubmissionReview.objects.filter(deleted_at__isnull=True)
    serializer_class = SubmissionReviewSerializer
    permission_classes = [SubmissionReviewPermissions]
    filter_backends = (DjangoFilterBackend, )
    filter_fields = ('instance', 'created_by', 'status')

    def destroy(self, request, *args, **kwargs):
        """
        Custom destroy method
        """
        obj = self.get_object()
        user = request.user
        obj.set_deleted(user=user)

        return Response(status=status.HTTP_204_NO_CONTENT)
