# -*- coding: utf-8 -*-
"""
Implements the AnonymousUserPublicFormsMixin class

Filters only public forms.
"""

from onadata.apps.logger.models.xform import XForm


class AnonymousUserPublicFormsMixin:  # pylint: disable=too-few-public-methods
    """
    Implements the AnonymousUserPublicFormsMixin class

    Filters only public forms.
    """

    def _get_public_forms_queryset(self):
        return XForm.objects.filter(
            shared=True,
            deleted_at__isnull=True,
            project__organization__is_active=True,
        )

    def get_queryset(self):
        """Public forms only for anonymous Users."""
        if self.request and self.request.user.is_anonymous:
            return self._get_public_forms_queryset()

        return super().get_queryset()
