# -*- coding: utf-8 -*-
"""
Messaging /messaging viewsets.
"""
from __future__ import unicode_literals

from actstream.models import Action
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from onadata.apps.messaging.constants import MESSAGE
from onadata.apps.messaging.filters import (TargetIDFilterBackend,
                                            TargetTypeFilterBackend)
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
    queryset = Action.objects.filter(verb=MESSAGE)
    permission_classes = [IsAuthenticated, TargetObjectPermissions]
    filter_backends = (TargetTypeFilterBackend, TargetIDFilterBackend)
