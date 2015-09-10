from django.core.exceptions import ImproperlyConfigured
from guardian.shortcuts import get_objects_for_user


class ViewPermissionMixin(object):

    def get_queryset(self):
        """
        Get the list of items for this view
        based on user's view_%(model_name)s permissions.
        """
        self.model = self.model if self.model is not None else \
            self.queryset.model if self.queryset is not None else None
        if self.request is not None and self.model is not None:
            kwargs = {
                'app_label': self.model._meta.app_label,
                'model_name': self.model._meta.module_name
            }
            perms = ['%(app_label)s.view_%(model_name)s' % kwargs]
            return get_objects_for_user(self.request.user, perms, self.model,
                                        with_superuser=False)

        if self.model is not None:
            return self.model._default_manager.all()

        raise ImproperlyConfigured("'%s' must define 'queryset' or 'model'"
                                   % self.__class__.__name__)
