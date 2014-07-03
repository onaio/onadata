from rest_framework import filters


class AnonDjangoObjectPermissionFilter(filters.DjangoObjectPermissionsFilter):
    def filter_queryset(self, request, queryset, view):
        """
        Anonymous user has no object permissions, return queryset as it is.
        """
        user = request.user
        if user.is_anonymous():
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
