from onadata.apps.main.models.meta_data import MetaData
from onadata.settings.common import METADATA_SEPARATOR


class TextitService(object):

    def __init__(self, xform, auth_token=None, flow_uuid=None, contacts=None,
                 remove=False):
        self.xform = xform
        self.auth_token = auth_token
        self.flow_uuid = flow_uuid
        self.contacts = contacts
        self.remove = remove

    def save(self, **kwargs):

        if self.remove:
            meta = MetaData.textit(self.xform)
            meta.delete()
        else:
            data_value = '{}|{}|{}'.format(self.auth_token,
                                           self.flow_uuid,
                                           self.contacts)

            MetaData.textit(self.xform, data_value=data_value)

    def retrieve(self):
        meta = MetaData.textit(self.xform)

        self.auth_token, self.flow_uuid, self.contacts = \
            meta.data_value.split(METADATA_SEPARATOR)
