# -*- coding: utf-8 -*-
"""
TextItService model: sets up all properties for interaction with TextIt or
RapidPro.
"""
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.restservice.models import RestService
from django.conf import settings
from django.utils.translation import ugettext as _
from django.db import IntegrityError
from rest_framework import serializers

METADATA_SEPARATOR = settings.METADATA_SEPARATOR


# pylint: disable=R0902
class TextItService(object):
    """
    TextItService model: access/create/update RestService and MetaData objects
    with all properties for TextIt or RapidPro like services.
    """

    # pylint: disable=R0913
    def __init__(self, xform, service_url=None, name=None, auth_token=None,
                 flow_uuid=None, contacts=None,
                 pk=None):
        self.pk = pk  # pylint: disable=C0103
        self.xform = xform
        self.auth_token = auth_token
        self.flow_uuid = flow_uuid
        self.contacts = contacts
        self.name = name
        self.service_url = service_url
        self.date_created = None
        self.date_modified = None
        self.active = True
        self.inactive_reason = ""

    def save(self):
        """
        Creates and updates RestService and MetaData objects with textit or
        rapidpro service properties.
        """
        service = RestService() if not self.pk else \
            RestService.objects.get(pk=self.pk)

        service.name = self.name
        service.service_url = self.service_url
        service.xform = self.xform
        try:
            service.save()
        except IntegrityError as e:
            if str(e).startswith("duplicate key value violates unique "
                                 "constraint"):
                msg = _(u"The service already created for this form.")
            else:
                msg = _(str(e))
            raise serializers.ValidationError(msg)

        self.pk = service.pk
        self.date_created = service.date_created
        self.date_modified = service.date_modified
        self.active = service.active
        self.inactive_reason = service.inactive_reason

        data_value = '{}|{}|{}'.format(self.auth_token,
                                       self.flow_uuid,
                                       self.contacts)

        MetaData.textit(self.xform, data_value=data_value)

        if self.xform.is_merged_dataset:
            for xform in self.xform.mergedxform.xforms.all():
                MetaData.textit(xform, data_value=data_value)

    def retrieve(self):
        """
        Sets the textit or rapidpro properties from the MetaData object.
        The properties are:
            - auth_token
            - flow_uuid
            - contacts
        """
        data_value = MetaData.textit(self.xform)

        try:
            self.auth_token, self.flow_uuid, self.contacts = \
                data_value.split(METADATA_SEPARATOR)
        except ValueError:
            raise serializers.ValidationError(
                _("Error occurred when loading textit service."
                  "Resolve by updating auth_token, flow_uuid and contacts"
                  " fields"))
