# -*- coding: utf-8 -*-
"""
Custom rest_framework Router V2
"""
from rest_framework import routers

from onadata.apps.api.viewsets.v2.tableau_viewset import TableauViewSet
from onadata.apps.api.viewsets.v2.imports_viewset import ImportsViewSet

from .v1_urls import MultiLookupRouter


class DetailedPostRouter(routers.DefaultRouter):
    """
    Custom router
    """
    routes = [
        # List route.
        routers.Route(
            url=r"^{prefix}{trailing_slash}$",
            mapping={"get": "list", "post": "create"},
            name="{basename}-list",
            detail=False,
            initkwargs={"suffix": "List"},
        ),
        # Dynamically generated list routes. Generated using
        # @action(detail=False) decorator on methods of the viewset.
        routers.DynamicRoute(
            url=r"^{prefix}/{url_path}{trailing_slash}$",
            name="{basename}-{url_name}",
            detail=False,
            initkwargs={},
        ),
        # Detail route.
        routers.Route(
            url=r"^{prefix}/{lookup}{trailing_slash}$",
            mapping={
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
                "post": "create",
            },
            name="{basename}-detail",
            detail=True,
            initkwargs={"suffix": "Instance"},
        ),
        # Dynamically generated detail routes. Generated using
        # @action(detail=True) decorator on methods of the viewset.
        routers.DynamicRoute(
            url=r"^{prefix}/{lookup}/{url_path}{trailing_slash}$",
            name="{basename}-{url_name}",
            detail=True,
            initkwargs={},
        ),
    ]

    # pylint: disable=redefined-outer-name
    def extend(self, router):
        """
        Extends the routers routes with the routes from another router
        """
        self.registry.extend(router.registry)


base_router = MultiLookupRouter(trailing_slash=False)
router = DetailedPostRouter(trailing_slash=False)
base_router.register(r"open-data", TableauViewSet, basename="open-data")
router.register(r"imports", ImportsViewSet, basename="imports")

router.extend(base_router)
