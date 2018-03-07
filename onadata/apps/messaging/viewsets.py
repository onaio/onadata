# -*- coding: utf-8 -*-
"""
Messaging /messaging viewsets.
"""
from __future__ import unicode_literals

from rest_framework import mixins, viewsets

from onadata.apps.messaging.serializers import MessageSerializer


class MessagingViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    ViewSet for the Messaging app - implements /messaging API endpoint
    """

    serializer_class = MessageSerializer
