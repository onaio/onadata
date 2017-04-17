from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.restservice.models import RestService
from django.conf import settings
from django.utils.translation import ugettext as _
from django.db import IntegrityError
from rest_framework import serializers

METADATA_SEPARATOR = settings.METADATA_SEPARATOR


class TextItService(object):

    def __init__(self, xform, service_url=None, name=None, auth_token=None,
                 flow_uuid=None, contacts=None,
                 pk=None):
        self.pk = pk
        self.xform = xform
        self.auth_token = auth_token
        self.flow_uuid = flow_uuid
        self.contacts = contacts
        self.name = name
        self.service_url = service_url
        self.date_created = None
        self.date_modified = None

    def save(self, **kwargs):

        rs = RestService() if not self.pk else \
            RestService.objects.get(pk=self.pk)

        rs.name = self.name
        rs.service_url = self.service_url
        rs.xform = self.xform
        try:
            rs.save()
        except IntegrityError as e:
            if str(e).startswith("duplicate key value violates unique "
                                 "constraint"):
                msg = _(u"The service already created for this form.")
            else:
                msg = _(str(e))
            raise serializers.ValidationError(msg)

        self.date_created = rs.date_created
        self.date_modified = rs.date_modified

        data_value = '{}|{}|{}'.format(self.auth_token,
                                       self.flow_uuid,
                                       self.contacts)

        MetaData.textit(self.xform, data_value=data_value)
        self.pk = rs.pk

    def retrieve(self):
        data_value = MetaData.textit(self.xform)

        try:
            self.auth_token, self.flow_uuid, self.contacts = \
                data_value.split(METADATA_SEPARATOR)
        except ValueError:
            raise serializers.ValidationError(
                _("Error occurred when loading textit service."
                  "Resolve by updating auth_token, flow_uuid and contacts"
                  " fields"))
