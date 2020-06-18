# -*- coding: utf-8 -*-
"""
Messaging /messaging viewsets.
"""
from __future__ import unicode_literals

from actstream.models import Action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from onadata.apps.messaging.constants import MESSAGE_VERBS
from onadata.apps.messaging.filters import (TargetIDFilterBackend,
                                            TargetTypeFilterBackend,
                                            UserFilterBackend)
from onadata.apps.messaging.permissions import TargetObjectPermissions
from onadata.apps.messaging.serializers import MessageSerializer


# pylint: disable=too-many-ancestors
class MessagingViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                       mixins.RetrieveModelMixin, mixins.DestroyModelMixin,
                       viewsets.GenericViewSet):
    """
    ViewSet for the Messaging app - implements /messaging API endpoint
    """

    serializer_class = MessageSerializer
    queryset = Action.objects.filter(verb__in=MESSAGE_VERBS)
    permission_classes = [IsAuthenticated, TargetObjectPermissions]
    filter_backends = (TargetTypeFilterBackend, TargetIDFilterBackend,
                       UserFilterBackend, DjangoFilterBackend)
    filter_fields = ['verb']
