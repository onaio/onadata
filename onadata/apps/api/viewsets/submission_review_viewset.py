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
from onadata.apps.messaging.constants import XFORM, SUBMISSION_REVIEWED
from onadata.apps.messaging.serializers import send_message
from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.mixins.bulk_create_mixin import BulkCreateMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
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
    filterset_fields = ('instance', 'created_by', 'status')

    def destroy(self, request, *args, **kwargs):
        """
        Custom destroy method
        """
        obj = self.get_object()
        user = request.user
        obj.set_deleted(user=user)

        return Response(status=status.HTTP_204_NO_CONTENT)

    def create(self, request, *args, **kwargs):
        """
        Custom create method. Handle bulk create
        """

        if isinstance(request.data, list):
            serializer = self.get_serializer(data=request.data, many=True)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            instance_ids = [sub_review['instance'] for sub_review in
                            serializer.data]
            headers = self.get_success_headers(serializer.data)
            xform = SubmissionReview.objects.get(
                id=serializer.data[0]['id']).instance.xform

        else:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            instance_ids = serializer.data['instance']
            headers = self.get_success_headers(serializer.data)
            xform = SubmissionReview.objects.get(
                id=serializer.data['id']).instance.xform
        send_message(
            instance_id=instance_ids,
            target_id=xform.id,
            target_type=XFORM, user=request.user,
            message_verb=SUBMISSION_REVIEWED)
        return Response(serializer.data, status=status.HTTP_201_CREATED,
                        headers=headers)
