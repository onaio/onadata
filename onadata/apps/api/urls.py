# -*- coding=utf-8 -*-
"""
Custom rest_framework Router - MultiLookupRouter.
"""
from django.conf.urls import url
from django.contrib import admin
from rest_framework import routers
from rest_framework.urlpatterns import format_suffix_patterns

from onadata.apps.api.viewsets.attachment_viewset import AttachmentViewSet
from onadata.apps.api.viewsets.briefcase_viewset import BriefcaseViewset
from onadata.apps.api.viewsets.charts_viewset import ChartsViewSet
from onadata.apps.api.viewsets.connect_viewset import ConnectViewSet
from onadata.apps.api.viewsets.data_viewset import (AuthenticatedDataViewSet,
                                                    DataViewSet)
from onadata.apps.api.viewsets.dataview_viewset import DataViewViewSet
from onadata.apps.api.viewsets.export_viewset import ExportViewSet
from onadata.apps.api.viewsets.floip_viewset import FloipViewSet
from onadata.apps.api.viewsets.media_viewset import MediaViewSet
from onadata.apps.api.viewsets.merged_xform_viewset import MergedXFormViewSet
from onadata.apps.api.viewsets.metadata_viewset import MetaDataViewSet
from onadata.apps.api.viewsets.note_viewset import NoteViewSet
from onadata.apps.api.viewsets.open_data_viewset import OpenDataViewSet
from onadata.apps.api.viewsets.organization_profile_viewset import \
    OrganizationProfileViewSet
from onadata.apps.api.viewsets.osm_viewset import OsmViewSet
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.stats_viewset import StatsViewSet
from onadata.apps.api.viewsets.submission_review_viewset import \
    SubmissionReviewViewSet
from onadata.apps.api.viewsets.submissionstats_viewset import \
    SubmissionStatsViewSet
from onadata.apps.api.viewsets.team_viewset import TeamViewSet
from onadata.apps.api.viewsets.user_profile_viewset import UserProfileViewSet
from onadata.apps.api.viewsets.user_viewset import UserViewSet
from onadata.apps.api.viewsets.widget_viewset import WidgetViewSet
from onadata.apps.api.viewsets.xform_list_viewset import XFormListViewSet
from onadata.apps.api.viewsets.xform_submission_viewset import \
    XFormSubmissionViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.restservice.viewsets.restservices_viewset import \
    RestServicesViewSet

admin.autodiscover()


class MultiLookupRouter(routers.DefaultRouter):
    """
    Support multiple lookup keys e.g. /parent_pk/pk
    """
    multi = False

    def get_lookup_regex(self, viewset, lookup_prefix=''):
        """
        Returns a lookup regex, this extends the default to allow for multiple
        lookup keys as defined by a viewset.lookup_fields property.
        """
        result = super(MultiLookupRouter, self).get_lookup_regex(
            viewset, lookup_prefix)
        lookup_fields = getattr(viewset, 'lookup_fields', None)
        if lookup_fields and not self.multi:
            lookup_value = getattr(viewset, 'lookup_value_regex', '[^/.]+')
            for lookup_field in lookup_fields[1:]:
                result += '/(?P<{lookup_url_kwarg}>{lookup_value})'.format(
                    lookup_url_kwarg=lookup_field, lookup_value=lookup_value)

        return result

    def get_urls(self):
        """
        Return a list of URL regexs, this extends the default by adding a
        {prefix}-list route that accepts a lookup url kwarg.
        """
        urls = super(MultiLookupRouter, self).get_urls()

        extra_urls = []
        for prefix, viewset, basename in self.registry:
            lookup_fields = getattr(viewset, 'lookup_fields', None)
            if lookup_fields:
                route = routers.Route(
                    url=r'^{prefix}/{lookup}{trailing_slash}$',
                    mapping={
                        'delete': 'destroy',
                        'get': 'list',
                        'post': 'create',
                    },
                    name='{basename}-list',
                    detail=False,
                    initkwargs={'suffix': 'List'})
                self.multi = True
                lookup = self.get_lookup_regex(viewset)
                # reset
                self.multi = False
                regex = route.url.format(
                    prefix=prefix,
                    lookup=lookup,
                    trailing_slash=self.trailing_slash)

                mapping = self.get_method_map(viewset, route.mapping)
                if not mapping:
                    continue
                initkwargs = route.initkwargs.copy()
                initkwargs.update({
                    'basename': basename,
                    'detail': route.detail,
                })
                view = viewset.as_view(mapping, **initkwargs)
                name = route.name.format(basename=basename)
                extra_urls.append(url(regex, view, name=name))

        if self.include_format_suffixes:
            extra_urls = format_suffix_patterns(extra_urls)
        urls.extend(extra_urls)
        return urls


router = MultiLookupRouter(trailing_slash=False)  # pylint: disable=c0103
router.register(r'briefcase', BriefcaseViewset, base_name='briefcase')
router.register(r'charts', ChartsViewSet, base_name='chart')
router.register(r'data', DataViewSet, base_name='data')
router.register(r'dataviews', DataViewViewSet, base_name='dataviews')
router.register(r'export', ExportViewSet, base_name='export')
router.register(r'files', MediaViewSet, base_name='files')
router.register(
    r'flow-results/packages', FloipViewSet, base_name='flow-results')
router.register(r'formlist', XFormListViewSet, base_name='formlist')
router.register(r'forms', XFormViewSet)
router.register(r'media', AttachmentViewSet, base_name='attachment')
router.register(
    r'merged-datasets', MergedXFormViewSet, base_name='merged-xform')
router.register(r'metadata', MetaDataViewSet, base_name='metadata')
router.register(r'notes', NoteViewSet)
router.register(r'open-data', OpenDataViewSet, base_name='open-data')
router.register(r'orgs', OrganizationProfileViewSet)
router.register(r'osm', OsmViewSet, base_name='osm')
router.register(
    r'private-data', AuthenticatedDataViewSet, base_name='private-data')
router.register(r'profiles', UserProfileViewSet)
router.register(r'projects', ProjectViewSet)
router.register(r'restservices', RestServicesViewSet, base_name='restservices')
router.register(r'stats', StatsViewSet, base_name='stats')
router.register(
    r'submissionreview', SubmissionReviewViewSet, base_name='submissionreview')
router.register(
    r'stats/submissions', SubmissionStatsViewSet, base_name='submissionstats')
router.register(
    r'submissions', XFormSubmissionViewSet, base_name='submissions')
router.register(r'teams', TeamViewSet)
router.register(r'user', ConnectViewSet)
router.register(r'users', UserViewSet, base_name='user')
router.register(r'widgets', WidgetViewSet, base_name='widgets')
