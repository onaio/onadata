# -*- coding: utf-8 -*-
"""
OrganizationField serializer field.
"""
from django.utils.translation import gettext as _

from rest_framework import serializers

from onadata.apps.api.models.organization_profile import OrganizationProfile


class OrganizationField(serializers.Field):
    """organization serializer field"""

    # pylint: disable=no-self-use
    def to_representation(self, value):
        """Return the organization pk."""
        return value.pk

    # pylint: disable=no-self-use
    def to_internal_value(self, data):
        """Validate the organization exists."""
        if data is not None:
            try:
                organization = OrganizationProfile.objects.get(pk=data)
            except OrganizationProfile.DoesNotExist as e:
                raise serializers.ValidationError(
                    _(
                        "Organization with id '%(value)s' does not exist."
                        % {"value": data}
                    )
                ) from e
            except ValueError as e:
                raise serializers.ValidationError(str(e)) from e

            return organization
        return data
