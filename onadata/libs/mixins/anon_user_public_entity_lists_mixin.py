# -*- coding: utf-8 -*-
"""
AnonymousUserPublicEntityListsMixin class

Filters only EntityLists under public projects
"""
from onadata.apps.logger.models.entity_list import EntityList


class AnonymousUserPublicEntityListsMixin:
    """Filters only public EntityLists"""

    def _get_public_entity_lists_queryset(self):
        return EntityList.objects.filter(project__shared=True).order_by("pk")

    def get_queryset(self):
        """Public EntityLists only for anonymous Users."""
        if self.request and self.request.user.is_anonymous:
            return self._get_public_entity_lists_queryset()

        return super().get_queryset()
