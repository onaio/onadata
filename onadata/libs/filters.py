from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import User
from django.http import Http404
from django.utils import six
from rest_framework import filters


from onadata.apps.api.models import Team, OrganizationProfile
from onadata.apps.logger.models import Project, XForm, Instance
from onadata.libs.utils.numeric import int_or_parse_error


class AnonDjangoObjectPermissionFilter(filters.DjangoObjectPermissionsFilter):

    def filter_queryset(self, request, queryset, view):
        """
        Anonymous user has no object permissions, return queryset as it is.
        """
        form_id = view.kwargs.get(view.lookup_field)
        queryset = queryset.filter(deleted_at=None)
        if request.user.is_anonymous():
            return queryset

        if form_id:
            int_or_parse_error(form_id, u'Invalid form ID: %s')

            # check if form is public and return it
            try:
                form = queryset.get(id=form_id)
            except ObjectDoesNotExist:
                raise Http404

            if form.shared:
                return queryset.filter(Q(id=form_id))

        return super(AnonDjangoObjectPermissionFilter, self)\
            .filter_queryset(request, queryset, view)


class XFormListObjectPermissionFilter(AnonDjangoObjectPermissionFilter):
    perm_format = '%(app_label)s.report_%(model_name)s'


class XFormListXFormPKFilter(object):

    def filter_queryset(self, request, queryset, view):
        xform_pk = view.kwargs.get('xform_pk')
        if xform_pk:
            try:
                xform_pk = int(xform_pk)
            except ValueError:
                pass
            else:
                return queryset.filter(pk=xform_pk)

        return queryset


class OrganizationPermissionFilter(filters.DjangoObjectPermissionsFilter):

    def filter_queryset(self, request, queryset, view):
        """Return a filtered queryset or all profiles if a getting a specific
           profile."""
        if view.action == 'retrieve' and request.method == 'GET':
            return queryset.model.objects.all()

        filtered_queryset = super(self.__class__, self).filter_queryset(
            request, queryset, view)
        org_users = set([group.team.organization
                         for group in request.user.groups.all()] + [
            o.user for o in filtered_queryset])

        return queryset.model.objects.filter(user__in=org_users)


class XFormOwnerFilter(filters.BaseFilterBackend):

    owner_prefix = 'user'

    def filter_queryset(self, request, queryset, view):
        owner = request.query_params.get('owner')

        if owner:
            kwargs = {
                self.owner_prefix + '__username__iexact': owner
            }

            return queryset.filter(**kwargs)

        return queryset


class DataFilter(filters.DjangoObjectPermissionsFilter):

    def filter_queryset(self, request, queryset, view):
        if request.user.is_anonymous():
            return queryset.filter(Q(shared_data=True))
        return queryset


class ProjectOwnerFilter(filters.BaseFilterBackend):
    owner_prefix = 'organization'

    def filter_queryset(self, request, queryset, view):
        owner = request.query_params.get('owner')

        if owner:
            kwargs = {
                self.owner_prefix + '__username__iexact': owner
            }

            return queryset.filter(**kwargs) | Project.objects.filter(
                shared=True, deleted_at__isnull=True, **kwargs)

        return queryset


class AnonUserProjectFilter(filters.DjangoObjectPermissionsFilter):
    owner_prefix = 'organization'

    def filter_queryset(self, request, queryset, view):
        """
        Anonymous user has no object permissions, return queryset as it is.
        """
        user = request.user
        project_id = view.kwargs.get(view.lookup_field)

        if user.is_anonymous():
            return queryset.filter(Q(shared=True))

        if project_id:
            int_or_parse_error(project_id,
                               u"Invalid value for project_id '%s' must be a"
                               " positive integer.")

            # check if project is public and return it
            try:
                project = queryset.get(id=project_id)
            except ObjectDoesNotExist:
                raise Http404

            if project.shared:
                return queryset.filter(Q(id=project_id))

        return super(AnonUserProjectFilter, self)\
            .filter_queryset(request, queryset, view)


class TagFilter(filters.BaseFilterBackend):

    def filter_queryset(self, request, queryset, view):
        # filter by tags if available.
        tags = request.query_params.get('tags', None)

        if tags and isinstance(tags, six.string_types):
            tags = tags.split(',')
            return queryset.filter(tags__name__in=tags)

        return queryset


class XFormPermissionFilterMixin(object):

    def _xform_filter(self, request, view, keyword):
        """Use XForm permissions"""
        xform = request.query_params.get('xform')
        if xform:
            int_or_parse_error(xform, u"Invalid value for formid %s.")
            xform = get_object_or_404(XForm, pk=xform)
            xform_qs = XForm.objects.filter(pk=xform.pk)
        else:
            xform_qs = XForm.objects.all()

        xform_qs = xform_qs.filter(deleted_at=None)

        if request.user.is_anonymous():
            xforms = xform_qs.filter(shared_data=True)
        else:
            xforms = super(XFormPermissionFilterMixin, self).filter_queryset(
                request, xform_qs, view)

        return {"%s__in" % keyword: xforms}

    def _xform_filter_queryset(self, request, queryset, view, keyword):
        kwarg = self._xform_filter(request, view, keyword)

        return queryset.filter(**kwarg)


class ProjectPermissionFilterMixin(object):

    def _project_filter(self, request, view, keyword):
        project_id = request.query_params.get("project")

        if project_id:
            int_or_parse_error(project_id, u"Invalid value for projectid %s.")

            project = get_object_or_404(Project, pk=project_id)
            project_qs = Project.objects.filter(pk=project.id)
        else:
            project_qs = Project.objects.all()

        projects = super(ProjectPermissionFilterMixin, self).filter_queryset(
            request, project_qs, view)

        return {"%s__in" % keyword: projects}

    def _project_filter_queryset(self, request, queryset, view, keyword):
        """Use Project Permissions"""
        kwarg = self._project_filter(request, view, keyword)

        return queryset.filter(**kwarg)


class InstancePermissionFilterMixin(object):

    def _instance_filter(self, request, view, keyword):
        instance_kwarg = {}
        instance_content_type = ContentType.objects.get_for_model(Instance)
        instance_kwarg["content_type"] = instance_content_type

        instance_id = request.query_params.get("instance")
        project_id = request.query_params.get("project")
        xform_id = request.query_params.get('xform')

        if instance_id and project_id and xform_id:
            for object_id in [instance_id, project_id]:
                int_or_parse_error(object_id,
                                   u"Invalid value for instanceid %s.")

            instance = get_object_or_404(Instance, pk=instance_id)
            # test if user has permissions on the project

            if xform_id:
                xform = get_object_or_404(XForm, pk=xform_id)
                parent = xform.instances.filter(id=instance.id) and xform

            else:
                return {}

            project = get_object_or_404(Project, pk=project_id)
            project_qs = Project.objects.filter(pk=project.id)

            if parent and parent.project == project:
                projects = super(
                    InstancePermissionFilterMixin, self).filter_queryset(
                        request, project_qs, view)

                instances = [instance.id] if projects else []

                instance_kwarg["%s__in" % keyword] = instances

                return instance_kwarg

            else:
                return {}

        else:
            return instance_kwarg

    def _instance_filter_queryset(self, request, queryset, view, keyword):
        kwarg = self._instance_filter(request, view, keyword)

        return queryset.filter(**kwarg)


class RestServiceFilter(XFormPermissionFilterMixin,
                        filters.DjangoObjectPermissionsFilter):

    def filter_queryset(self, request, queryset, view):
        return self._xform_filter_queryset(
            request, queryset, view, 'xform_id')


class MetaDataFilter(ProjectPermissionFilterMixin,
                     InstancePermissionFilterMixin,
                     XFormPermissionFilterMixin,
                     filters.DjangoObjectPermissionsFilter):

    def filter_queryset(self, request, queryset, view):
        keyword = "object_id"

        xform_id = request.query_params.get('xform')
        project_id = request.query_params.get("project")
        instance_id = request.query_params.get("instance")

        # generate queries
        xform_content_type = ContentType.objects.get_for_model(XForm)
        xform_kwarg = self._xform_filter(request, view, keyword)
        xform_kwarg["content_type"] = xform_content_type

        project_content_type = ContentType.objects.get_for_model(Project)
        project_kwarg = self._project_filter(request, view, keyword)
        project_kwarg["content_type"] = project_content_type

        instance_kwarg = self._instance_filter(request, view, keyword)

        # return instance specific metadata
        if instance_id:
            return (queryset.filter(Q(**instance_kwarg))
                    if (xform_id and instance_kwarg) else [])
        elif xform_id:
            # return xform specific metadata
            return queryset.filter(Q(**xform_kwarg))

        # return project specific metadata
        elif project_id:
            return queryset.filter(Q(**project_kwarg))

        # return all project,instance and xform metadata information
        return queryset.filter(Q(**xform_kwarg) | Q(**project_kwarg) |
                               Q(**instance_kwarg))


class AttachmentFilter(XFormPermissionFilterMixin,
                       filters.DjangoObjectPermissionsFilter):

    def filter_queryset(self, request, queryset, view):

        queryset = self._xform_filter_queryset(request, queryset, view,
                                               'instance__xform')
        instance_id = request.query_params.get('instance')
        if instance_id:
            int_or_parse_error(instance_id,
                               u"Invalid value for instance %s.")
            instance = get_object_or_404(Instance, pk=instance_id)
            queryset = queryset.filter(instance=instance)

        return queryset


class TeamOrgFilter(filters.BaseFilterBackend):

    def filter_queryset(self, request, queryset, view):
        org = request.data.get('org') or request.query_params.get('org')

        # Get all the teams for the organization
        if org:
            kwargs = {
                'organization__username__iexact': org
            }

            return Team.objects.filter(**kwargs)

        return queryset


class UserNoOrganizationsFilter(filters.BaseFilterBackend):

    def filter_queryset(self, request, queryset, view):
        if str(request.query_params.get('orgs')).lower() == 'false':
            organization_user_ids = OrganizationProfile.objects.values_list(
                'user__id',
                flat=True)
            queryset = queryset.exclude(id__in=organization_user_ids)

        return queryset


class OrganizationsSharedWithUserFilter(filters.BaseFilterBackend):

    def filter_queryset(self, request, queryset, view):
        """
        This returns a queryset containing only organizations to which
        the passed user belongs.
        """

        username = request.query_params.get('shared_with')

        if username:
            try:
                # The Team model extends the built-in Django Group model
                # Groups a User belongs to are available as a queryset property
                # of a User object, which this code takes advantage of

                organization_user_ids = User.objects\
                                            .get(username=username)\
                                            .groups\
                                            .all()\
                                            .values_list(
                                                'team__organization',
                                                flat=True)\
                                            .distinct()

                filtered_queryset = queryset.filter(
                    user_id__in=organization_user_ids)

                return filtered_queryset

            except ObjectDoesNotExist:
                raise Http404

        return queryset


class WidgetFilter(XFormPermissionFilterMixin,
                   filters.DjangoObjectPermissionsFilter):

    def filter_queryset(self, request, queryset, view):

        if view.action == 'list':
            # Return widgets from xform user has perms to
            return self._xform_filter_queryset(request, queryset, view,
                                               'object_id')

        return super(WidgetFilter, self).filter_queryset(request, queryset,
                                                         view)


class UserProfileFilter(filters.BaseFilterBackend):

    def filter_queryset(self, request, queryset, view):
        if view.action == 'list':
            users = request.GET.get('users')
            if users:
                users = users.split(',')
                return queryset.filter(user__username__in=users)
            elif not request.user.is_anonymous():
                return queryset.filter(user__username=request.user.username)

            return queryset.none()

        return queryset


class NoteFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        instance_id = request.query_params.get('instance')

        if instance_id:
            int_or_parse_error(instance_id,
                               u"Invalid value for instance %s.")

            instance = get_object_or_404(Instance, pk=instance_id)
            queryset = queryset.filter(instance=instance)

        return queryset


class ExportFilter(XFormPermissionFilterMixin,
                   filters.DjangoObjectPermissionsFilter):
    def filter_queryset(self, request, queryset, view):
        return self._xform_filter_queryset(
            request, queryset, view, 'xform_id')
