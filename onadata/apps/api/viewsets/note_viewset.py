# -*- coding: utf-8 -*-
"""
The /api/v1/notes API implementation.

List, Create, Update, Delete Note objects.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework_guardian.filters import ObjectPermissionsFilter

from onadata.apps.api import permissions
from onadata.apps.api.tools import get_baseviewset_class
from onadata.apps.logger.models import Note
from onadata.libs import filters
from onadata.libs.mixins.authenticate_header_mixin import AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.serializers.note_serializer import NoteSerializer

BaseViewset = get_baseviewset_class()


# pylint: disable=too-many-ancestors
class NoteViewSet(
    AuthenticateHeaderMixin, CacheControlMixin, ETagsMixin, BaseViewset, ModelViewSet
):
    """
    The /api/v1/notes API implementation.

    List, Create, Update, Delete Note objects."""

    queryset = Note.objects.all()
    filter_backends = (filters.NoteFilter, ObjectPermissionsFilter)
    serializer_class = NoteSerializer
    permission_classes = [
        permissions.ViewDjangoObjectPermissions,
        permissions.IsAuthenticated,
    ]

    def get_object(self):
        obj = []
        queryset = self.filter_queryset(self.get_queryset())

        if queryset:
            obj = super().get_object()

        return obj

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance:
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        return Response(data=[])

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        instance = obj.instance
        obj.delete()
        # should update Instance.json
        instance.parsed_instance.save()

        return Response(status=status.HTTP_204_NO_CONTENT)
