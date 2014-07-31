from django.db.models import Q
from django.utils import six
from rest_framework import filters

from onadata.apps.logger.models import XForm


class AnonDjangoObjectPermissionFilter(filters.DjangoObjectPermissionsFilter):
    def filter_queryset(self, request, queryset, view):
        """
        Anonymous user has no object permissions, return queryset as it is.
        """
        if request.user.is_anonymous():
            return queryset

        return super(AnonDjangoObjectPermissionFilter, self)\
            .filter_queryset(request, queryset, view)


class XFormOwnerFilter(filters.BaseFilterBackend):

    owner_prefix = 'user'

    def filter_queryset(self, request, queryset, view):
        owner = request.QUERY_PARAMS.get('owner')

        if owner:
            kwargs = {
                self.owner_prefix + '__username': owner
            }

            return queryset.filter(**kwargs)

        return queryset


class ProjectOwnerFilter(XFormOwnerFilter):
    owner_prefix = 'organization'


class AnonUserProjectFilter(filters.DjangoObjectPermissionsFilter):
    def filter_queryset(self, request, queryset, view):
        """
        Anonymous user has no object permissions, return queryset as it is.
        """
        user = request.user
        if user.is_anonymous():
            return queryset.filter(Q(shared=True))

        return super(AnonUserProjectFilter, self)\
            .filter_queryset(request, queryset, view)


class TagFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        # filter by tags if available.
        tags = request.QUERY_PARAMS.get('tags', None)

        if tags and isinstance(tags, six.string_types):
            tags = tags.split(',')
            return queryset.filter(tags__name__in=tags)

        return queryset


class MetaDataFilter(filters.DjangoObjectPermissionsFilter):
    def filter_queryset(self, request, queryset, view):
        """Use XForm permissions"""
        xform_qs = XForm.objects.all()
        xforms = super(MetaDataFilter, self).filter_queryset(
            request, xform_qs, view)

        return queryset.filter(xform__in=xforms)
