from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.restservice.models import RestService
from django.conf import settings

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

    def save(self, **kwargs):

        rs = RestService() if not self.pk else \
            RestService.objects.get(pk=self.pk)

        rs.name = self.name
        rs.service_url = self.service_url
        rs.xform = self.xform
        rs.save()

        data_value = '{}|{}|{}'.format(self.auth_token,
                                       self.flow_uuid,
                                       self.contacts)

        MetaData.textit(self.xform, data_value=data_value)
        self.pk = rs.pk

    def retrieve(self):
        meta = MetaData.textit(self.xform)

        self.auth_token, self.flow_uuid, self.contacts = \
            meta.data_value.split(METADATA_SEPARATOR)
