from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.restservice.models import RestService
from django.conf import settings

METADATA_SEPARATOR = settings.METADATA_SEPARATOR


class TextItService(object):

    def __init__(self, xform, service_url=None, name=None, auth_token=None,
                 flow_uuid=None, contacts=None,
                 remove=False):
        self.xform = xform
        self.auth_token = auth_token
        self.flow_uuid = flow_uuid
        self.contacts = contacts
        self.remove = remove
        self.name = name
        self.service_url = service_url

    def save(self, **kwargs):

        if self.remove:
            meta = MetaData.textit(self.xform)
            meta.delete()
        else:
            RestService.objects.get_or_create(
                name=self.name,
                service_url=self.service_url,
                xform=self.xform)
            data_value = '{}|{}|{}'.format(self.auth_token,
                                           self.flow_uuid,
                                           self.contacts)

            MetaData.textit(self.xform, data_value=data_value)

    def retrieve(self):
        meta = MetaData.textit(self.xform)

        self.auth_token, self.flow_uuid, self.contacts = \
            meta.data_value.split(METADATA_SEPARATOR)
