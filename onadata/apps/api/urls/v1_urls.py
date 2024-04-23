# -*- coding: utf-8 -*-
"""
Custom rest_framework Router - MultiLookupRouter.
"""
from django.contrib import admin
from django.urls import re_path

from rest_framework import routers
from rest_framework.urlpatterns import format_suffix_patterns

from onadata.apps.api.viewsets.attachment_viewset import AttachmentViewSet
from onadata.apps.api.viewsets.briefcase_viewset import BriefcaseViewset
from onadata.apps.api.viewsets.charts_viewset import ChartsViewSet
from onadata.apps.api.viewsets.connect_viewset import ConnectViewSet
from onadata.apps.api.viewsets.data_viewset import AuthenticatedDataViewSet, DataViewSet
from onadata.apps.api.viewsets.dataview_viewset import DataViewViewSet
from onadata.apps.api.viewsets.export_viewset import ExportViewSet
from onadata.apps.api.viewsets.floip_viewset import FloipViewSet
from onadata.apps.api.viewsets.media_viewset import MediaViewSet
from onadata.apps.api.viewsets.merged_xform_viewset import MergedXFormViewSet
from onadata.apps.api.viewsets.metadata_viewset import MetaDataViewSet
from onadata.apps.api.viewsets.note_viewset import NoteViewSet
from onadata.apps.api.viewsets.open_data_viewset import OpenDataViewSet
from onadata.apps.api.viewsets.organization_profile_viewset import (
    OrganizationProfileViewSet,
)
from onadata.apps.api.viewsets.osm_viewset import OsmViewSet
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.stats_viewset import StatsViewSet
from onadata.apps.api.viewsets.submission_review_viewset import SubmissionReviewViewSet
from onadata.apps.api.viewsets.submissionstats_viewset import SubmissionStatsViewSet
from onadata.apps.api.viewsets.team_viewset import TeamViewSet
from onadata.apps.api.viewsets.user_profile_viewset import UserProfileViewSet
from onadata.apps.api.viewsets.user_viewset import UserViewSet
from onadata.apps.api.viewsets.widget_viewset import WidgetViewSet
from onadata.apps.api.viewsets.xform_list_viewset import XFormListViewSet
from onadata.apps.api.viewsets.xform_submission_viewset import XFormSubmissionViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.api.viewsets.messaging_stats_viewset import MessagingStatsViewSet
from onadata.apps.messaging.viewsets import MessagingViewSet
from onadata.apps.restservice.viewsets.restservices_viewset import RestServicesViewSet

admin.autodiscover()


class MultiLookupRouter(routers.DefaultRouter):
    """
    Support multiple lookup keys e.g. /parent_pk/pk
    """

    multi = False

    def get_lookup_regex(self, viewset, lookup_prefix=""):
        """
        Returns a lookup regex, this extends the default to allow for multiple
        lookup keys as defined by a viewset.lookup_fields property.
        """
        result = super().get_lookup_regex(viewset, lookup_prefix)
        lookup_fields = getattr(viewset, "lookup_fields", None)
        if lookup_fields and not self.multi:
            lookup_value = getattr(viewset, "lookup_value_regex", "[^/.]+")
            for lookup_field in lookup_fields[1:]:
                result += f"/(?P<{lookup_field}>{lookup_value})"

        return result

    def get_urls(self):
        """
        Return a list of URL regexs, this extends the default by adding a
        {prefix}-list route that accepts a lookup url kwarg.
        """
        urls = super().get_urls()

        extra_urls = []
        for prefix, viewset, basename in self.registry:
            lookup_fields = getattr(viewset, "lookup_fields", None)
            if lookup_fields:
                route = routers.Route(
                    url=r"^{prefix}/{lookup}{trailing_slash}$",
                    mapping={
                        "delete": "destroy",
                        "get": "list",
                        "post": "create",
                    },
                    name="{basename}-list",
                    detail=False,
                    initkwargs={"suffix": "List"},
                )
                self.multi = True
                lookup = self.get_lookup_regex(viewset)
                # reset
                self.multi = False
                regex = route.url.format(
                    prefix=prefix, lookup=lookup, trailing_slash=self.trailing_slash
                )

                mapping = self.get_method_map(viewset, route.mapping)
                if not mapping:
                    continue
                initkwargs = route.initkwargs.copy()
                initkwargs.update(
                    {
                        "basename": basename,
                        "detail": route.detail,
                    }
                )
                view = viewset.as_view(mapping, **initkwargs)
                name = route.name.format(basename=basename)
                extra_urls.append(re_path(regex, view, name=name))

        if self.include_format_suffixes:
            extra_urls = format_suffix_patterns(extra_urls)
        urls.extend(extra_urls)
        return urls


router = MultiLookupRouter(trailing_slash=False)  # pylint: disable=invalid-name
router.register(r"briefcase", BriefcaseViewset, basename="briefcase")
router.register(r"charts", ChartsViewSet, basename="chart")
router.register(r"data", DataViewSet, basename="data")
router.register(r"dataviews", DataViewViewSet, basename="dataviews")
router.register(r"export", ExportViewSet, basename="export")
router.register(r"files", MediaViewSet, basename="files")
router.register(r"flow-results/packages", FloipViewSet, basename="flow-results")
router.register(r"formlist", XFormListViewSet, basename="formlist")
router.register(r"forms", XFormViewSet)
router.register(r"media", AttachmentViewSet, basename="attachment")
router.register(r"merged-datasets", MergedXFormViewSet, basename="merged-xform")
router.register(r"messaging", MessagingViewSet, basename="messaging")
router.register(r"metadata", MetaDataViewSet, basename="metadata")
router.register(r"notes", NoteViewSet)
router.register(r"open-data", OpenDataViewSet, basename="open-data")
router.register(r"orgs", OrganizationProfileViewSet)
router.register(r"osm", OsmViewSet, basename="osm")
router.register(r"private-data", AuthenticatedDataViewSet, basename="private-data")
router.register(r"profiles", UserProfileViewSet, basename="userprofile")
router.register(r"projects", ProjectViewSet)
router.register(r"restservices", RestServicesViewSet, basename="restservices")
router.register(r"stats/messaging", MessagingStatsViewSet, basename="messagingstats")
router.register(r"stats", StatsViewSet, basename="stats")
router.register(
    r"submissionreview", SubmissionReviewViewSet, basename="submissionreview"
)
router.register(
    r"stats/submissions", SubmissionStatsViewSet, basename="submissionstats"
)
router.register(r"submissions", XFormSubmissionViewSet, basename="submissions")
router.register(r"teams", TeamViewSet)
router.register(r"user", ConnectViewSet, basename="connect")
router.register(r"users", UserViewSet, basename="user")
router.register(r"widgets", WidgetViewSet, basename="widgets")
