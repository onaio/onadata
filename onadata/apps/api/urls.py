from django.conf.urls import url
from django.conf import settings
from django.contrib import admin
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework import routers
from rest_framework.urlpatterns import format_suffix_patterns
from rest_framework.views import APIView

from onadata.apps.api.viewsets.charts_viewset import ChartsViewSet
from onadata.apps.api.viewsets.connect_viewset import ConnectViewSet
from onadata.apps.api.viewsets.data_viewset import DataViewSet
from onadata.apps.api.viewsets.open_data_viewset import OpenDataViewSet
from onadata.apps.api.viewsets.data_viewset import AuthenticatedDataViewSet
from onadata.apps.api.viewsets.dataview_viewset import DataViewViewSet
from onadata.apps.api.viewsets.export_viewset import ExportViewSet
from onadata.apps.api.viewsets.metadata_viewset import MetaDataViewSet
from onadata.apps.api.viewsets.note_viewset import NoteViewSet
from onadata.apps.api.viewsets.organization_profile_viewset import\
    OrganizationProfileViewSet
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.stats_viewset import StatsViewSet
from onadata.apps.api.viewsets.team_viewset import TeamViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.api.viewsets.user_profile_viewset import UserProfileViewSet
from onadata.apps.api.viewsets.user_viewset import UserViewSet
from onadata.apps.api.viewsets.submissionstats_viewset import\
    SubmissionStatsViewSet
from onadata.apps.api.viewsets.attachment_viewset import AttachmentViewSet
from onadata.apps.api.viewsets.xform_list_viewset import XFormListViewSet
from onadata.apps.api.viewsets.xform_submission_viewset import\
    XFormSubmissionViewSet
from onadata.apps.api.viewsets.briefcase_viewset import BriefcaseViewset
from onadata.apps.api.viewsets.osm_viewset import OsmViewSet
from onadata.apps.restservice.viewsets.restservices_viewset import \
    RestServicesViewSet
from onadata.apps.api.viewsets.media_viewset import MediaViewSet
from onadata.apps.api.viewsets.widget_viewset import WidgetViewSet


admin.autodiscover()


def make_routes(template_text):
    return routers.Route(
        url=r'^{prefix}/{%s}{trailing_slash}$' % template_text,
        mapping={
            'get': 'list',
            'post': 'create'
        },
        name='{basename}-list',
        initkwargs={'suffix': 'List'})


class MultiLookupRouter(routers.DefaultRouter):
    def __init__(self, *args, **kwargs):
        super(MultiLookupRouter, self).__init__(*args, **kwargs)
        self.lookups_routes = []
        self.lookups_routes.append(routers.Route(
            url=r'^{prefix}/{lookups}{trailing_slash}$',
            mapping={
                'get': 'retrieve',
                'put': 'update',
                'patch': 'partial_update',
                'delete': 'destroy'
            },
            name='{basename}-detail',
            initkwargs={'suffix': 'Instance'}
        ))
        self.lookups_routes.append(make_routes('lookup'))
        self.lookups_routes.append(make_routes('lookups'))
        # Dynamically generated routes.
        # Generated using @action or @link decorators on methods of the viewset
        self.lookups_routes.append(routers.Route(
            url=[
                r'^{prefix}/{lookups}/{methodname}{trailing_slash}$',
                r'^{prefix}/{lookups}/{methodname}/{extra}{trailing_slash}$'],
            mapping={
                '{httpmethod}': '{methodname}',
            },
            name='{basename}-{methodnamehyphen}',
            initkwargs={}
        ))

    def get_extra_lookup_regexes(self, route):
        ret = []
        base_regex = '(?P<{lookup_field}>[^/]+)'
        if 'extra_lookup_fields' in route.initkwargs:
            for lookup_field in route.initkwargs['extra_lookup_fields']:
                ret.append(base_regex.format(lookup_field=lookup_field))
        return '/'.join(ret)

    def get_lookup_regexes(self, viewset):
        ret = []
        lookup_fields = getattr(viewset, 'lookup_fields', None)
        if lookup_fields:
            for i in range(1, len(lookup_fields)):
                tmp = []
                for lookup_field in lookup_fields[:i + 1]:
                    if lookup_field == lookup_fields[i]:
                        base_regex = '(?P<{lookup_field}>[^/.]+)'
                    else:
                        base_regex = '(?P<{lookup_field}>[^/]+)'
                    tmp.append(base_regex.format(lookup_field=lookup_field))
                ret.append(tmp)
        return ret

    def get_lookup_routes(self, viewset):
        ret = [self.routes[0]]
        # Determine any `@action` or `@link` decorated methods on the viewset
        dynamic_routes = []
        for methodname in dir(viewset):
            attr = getattr(viewset, methodname)
            httpmethods = getattr(attr, 'bind_to_methods', None)
            if httpmethods:
                httpmethods = [method.lower() for method in httpmethods]
                dynamic_routes.append((httpmethods, methodname))

        for route in self.lookups_routes:
            if route.mapping == {'{httpmethod}': '{methodname}'}:
                # Dynamic routes (@link or @action decorator)
                for httpmethods, methodname in dynamic_routes:
                    initkwargs = route.initkwargs.copy()
                    initkwargs.update(getattr(viewset, methodname).kwargs)
                    mapping = dict(
                        (httpmethod, methodname) for httpmethod in httpmethods)
                    name = routers.replace_methodname(route.name, methodname)
                    if 'extra_lookup_fields' in initkwargs:
                        uri = route.url[1]
                        uri = routers.replace_methodname(uri, methodname)
                        ret.append(routers.Route(
                            url=uri, mapping=mapping, name='%s-extra' % name,
                            initkwargs=initkwargs,
                        ))
                    uri = routers.replace_methodname(route.url[0], methodname)
                    ret.append(routers.Route(
                        url=uri, mapping=mapping, name=name,
                        initkwargs=initkwargs,
                    ))
            else:
                # Standard route
                ret.append(route)
        return ret

    def get_routes(self, viewset):
        ret = []
        lookup_fields = getattr(viewset, 'lookup_fields', None)
        if lookup_fields:
            ret = self.get_lookup_routes(viewset)
        else:
            ret = super(MultiLookupRouter, self).get_routes(viewset)
        return ret

    def get_api_root_view(self):
        """
        Return a view to use as the API root.
        """
        api_root_dict = {}
        list_name = self.routes[0].name
        for prefix, viewset, basename in self.registry:
            api_root_dict[prefix] = list_name.format(basename=basename)

        class OnaApi(APIView):
            """
## Ona JSON Rest API endpoints:

"""
            _ignore_model_permissions = True

            def get(self, request, format=None):
                ret = {}
                for key, url_name in api_root_dict.items():
                    ret[key] = reverse(
                        url_name, request=request, format=format)

                # Adding for static documentation
                ret['api-docs'] = \
                    request.build_absolute_uri(settings.STATIC_DOC)
                return Response(ret)

        return OnaApi.as_view()

    def get_urls(self):
        ret = []

        if self.include_root_view:
            root_url = url(r'^$', self.get_api_root_view(),
                           name=self.root_view_name)
            ret.append(root_url)
        for prefix, viewset, basename in self.registry:
            lookup = self.get_lookup_regex(viewset)
            lookup_list = self.get_lookup_regexes(viewset)
            if lookup_list:
                # lookup = lookups[0]
                lookup_list = [u'/'.join(k) for k in lookup_list]
            else:
                lookup_list = [u'']
            routes = self.get_routes(viewset)
            for route in routes:
                mapping = self.get_method_map(viewset, route.mapping)
                if not mapping:
                    continue
                for lookups in lookup_list:
                    regex = route.url.format(
                        prefix=prefix,
                        lookup=lookup,
                        lookups=lookups,
                        trailing_slash=self.trailing_slash,
                        extra=self.get_extra_lookup_regexes(route)
                    )
                    view = viewset.as_view(mapping, **route.initkwargs)
                    name = route.name.format(basename=basename)
                    ret.append(url(regex, view, name=name))
        if self.include_format_suffixes:
            ret = format_suffix_patterns(ret, allowed=['[a-z]+[0-9]*'])
        return ret


router = MultiLookupRouter(trailing_slash=False)
router.register(r'users', UserViewSet)
router.register(r'user', ConnectViewSet)
router.register(r'profiles', UserProfileViewSet)
router.register(r'orgs', OrganizationProfileViewSet)
router.register(r'forms', XFormViewSet)
router.register(r'projects', ProjectViewSet)
router.register(r'teams', TeamViewSet)
router.register(r'notes', NoteViewSet)
router.register(r'data', DataViewSet, base_name='data')
router.register(r'open-data', OpenDataViewSet, base_name='open-data')
router.register(r'private-data', AuthenticatedDataViewSet,
                base_name='private-data')
router.register(r'stats', StatsViewSet, base_name='stats')
router.register(r'stats/submissions', SubmissionStatsViewSet,
                base_name='submissionstats')
router.register(r'charts', ChartsViewSet, base_name='chart')
router.register(r'metadata', MetaDataViewSet, base_name='metadata')
router.register(r'media', AttachmentViewSet, base_name='attachment')
router.register(r'formlist', XFormListViewSet, base_name='formlist')
router.register(r'submissions', XFormSubmissionViewSet,
                base_name='submissions')
router.register(r'briefcase', BriefcaseViewset, base_name='briefcase')
router.register(r'osm', OsmViewSet, base_name='osm')
router.register(r'restservices', RestServicesViewSet, base_name='restservices')
router.register(r'files', MediaViewSet, base_name='files')
router.register(r'dataviews', DataViewViewSet, base_name='dataviews')
router.register(r'widgets', WidgetViewSet, base_name='widgets')
router.register(r'export', ExportViewSet, base_name='export')
