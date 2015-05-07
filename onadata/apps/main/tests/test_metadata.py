from test_base import TestBase
from onadata.apps.main.models.meta_data import MetaData


class TestMetaData(TestBase):

    def setUp(self):
        TestBase.setUp(self)
        self._create_user_and_login()
        self._publish_transportation_form_and_submit_instance()

    def test_create_metadata(self):
        count = len(MetaData.objects.filter(xform=self.xform,
                    data_type='enketo_url'))
        enketo_url = "https://dmfrm.enketo.org/webform"
        MetaData.enketo_url(self.xform, enketo_url)
        self.assertEquals(count + 1, len(MetaData.objects.filter(
            xform=self.xform, data_type='enketo_url')))

    def test_saving_same_metadata_object_doesnt_trigger_integrity_error(self):
        count = len(MetaData.objects.filter(xform=self.xform,
                    data_type='enketo_url'))
        enketo_url = "https://dmfrm.enketo.org/webform"
        MetaData.enketo_url(self.xform, enketo_url)
        count += 1
        self.assertEquals(count, len(MetaData.objects.filter(
            xform=self.xform, data_type='enketo_url')))

        MetaData.enketo_url(self.xform, enketo_url)
        self.assertEquals(count, len(MetaData.objects.filter(
            xform=self.xform, data_type='enketo_url')))
