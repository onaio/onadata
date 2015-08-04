from guardian.shortcuts import get_objects_for_user


class ViewPermissionMixin(object):

    def get_queryset(self):
        """
        Get the list of items for this view
        based on user's view_%(model_name)s permissions.
        """
        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method."
            % self.__class__.__name__
        )
        model = self.queryset.model

        kwargs = {
            'app_label': model._meta.app_label,
            'model_name': model._meta.model_name
        }
        perms = ['%(app_label)s.view_%(model_name)s' % kwargs]

        return get_objects_for_user(self.request.user, perms, model)
