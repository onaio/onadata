# -*- coding=utf-8 -*-
"""
Custom rest_framework Router V2
"""
from onadata.apps.api.viewsets.v2.tableau_viewset import TableauViewSet

from .v1_urls import MultiLookupRouter

router = MultiLookupRouter(trailing_slash=False)
router.register(r"open-data", TableauViewSet, basename="open-data")
