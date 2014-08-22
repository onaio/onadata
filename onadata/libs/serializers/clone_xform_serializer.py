from django.core.validators import ValidationError
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _

from rest_framework import serializers
from onadata.libs.models.clone_xform import CloneXForm
from onadata.libs.permissions import ROLES
from onadata.libs.serializers.fields.xform_field import XFormField
from onadata.apps.viewer.models.data_dictionary import DataDictionary, upload_to
from django.core.files.storage import default_storage
from onadata.apps.logger.models.xform import XForm


class CloneXFormSerializer(serializers.Serializer):
    xform = XFormField()
    username = serializers.CharField(max_length=255)

    def restore_object(self, attrs, instance=None):
        if instance is not None:
            instance.xform = attrs.get('xform', instance.xform)
            instance.username = attrs.get('username', instance.username)

            return instance

        return CloneXForm(**attrs)

    def validate_username(self, attrs, source):
        """Check that the username exists"""
        value = attrs[source]
        try:
            User.objects.get(username=value)
        except User.DoesNotExist:
            raise ValidationError(_(u"User '%(value)s' does not exist."
                                    % {"value": value}))

        return attrs