from builtins import str as text
from django.utils.translation import ugettext as _
from rest_framework import serializers

from onadata.apps.api.models.organization_profile import OrganizationProfile


class OrganizationField(serializers.Field):
    def to_representation(self, obj):
        return obj.pk

    def to_internal_value(self, data):
        if data is not None:
            try:
                organization = OrganizationProfile.objects.get(pk=data)
            except OrganizationProfile.DoesNotExist:
                raise serializers.ValidationError(_(
                    u"Organization with id '%(value)s' does not exist." %
                    {"value": data}
                ))
            except ValueError as e:
                raise serializers.ValidationError(text(e))

            return organization
