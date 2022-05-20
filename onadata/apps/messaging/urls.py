# -*- coding: utf-8 -*-
"""
Messaging urls module.
"""
from django.urls import include, re_path
from rest_framework import routers

from onadata.apps.messaging.viewsets import MessagingViewSet

router = routers.DefaultRouter(trailing_slash=False)  # pylint: disable=C0103
router.register(r'messaging', MessagingViewSet)

urlpatterns = [  # pylint: disable=C0103
    re_path(r'^api/v1/', include(router.urls)),
]
