from test_base import TestBase
from onadata.apps.logger.models import Instance, Project, XForm
from onadata.apps.main.models.meta_data import (
    MetaData,
    unique_type_for_form,
    upload_to)


class TestMetaData(TestBase):

    def setUp(self):
        TestBase.setUp(self)
        self._create_user_and_login()
        self._publish_transportation_form_and_submit_instance()

    def test_create_metadata(self):
        count = len(MetaData.objects.filter(object_id=self.xform.id,
                    data_type='enketo_url'))
        enketo_url = "https://dmfrm.enketo.org/webform"
        MetaData.enketo_url(self.xform, enketo_url)
        self.assertEquals(count + 1, len(MetaData.objects.filter(
            object_id=self.xform.id, data_type='enketo_url')))

    def test_create_gsheet_metadata_object(self):
        count = len(MetaData.objects.filter(object_id=self.xform.id,
                    data_type='google_sheet'))
        gsheets_actions = (
            'GOOGLE_SHEET_ID ABC100 | '
            'UPDATE_OR_DELETE_GSHEET_DATA True | '
            'USER_ID 123'
        )
        MetaData.set_gsheet_details(self.xform, gsheets_actions)
        # change
        self.assertEquals(count + 1, MetaData.objects.filter(
            object_id=self.xform.id, data_type='google_sheet').count())

        gsheet_details = MetaData.get_gsheet_details(self.xform)
        self.assertEqual({
            'GOOGLE_SHEET_ID': 'ABC100',
            'UPDATE_OR_DELETE_GSHEET_DATA': 'True',
            'USER_ID': '123'}, gsheet_details)

    def test_saving_same_metadata_object_doesnt_trigger_integrity_error(self):
        count = len(MetaData.objects.filter(object_id=self.xform.id,
                    data_type='enketo_url'))
        enketo_url = "https://dmfrm.enketo.org/webform"
        MetaData.enketo_url(self.xform, enketo_url)
        count += 1
        self.assertEquals(count, len(MetaData.objects.filter(
            object_id=self.xform.id, data_type='enketo_url')))

        MetaData.enketo_url(self.xform, enketo_url)
        self.assertEquals(count, len(MetaData.objects.filter(
            object_id=self.xform.id, data_type='enketo_url')))

    def test_unique_type_for_form(self):
        metadata = unique_type_for_form(
            self.xform, data_type='enketo_url',
            data_value="https://dmfrm.enketo.org/webform")

        self.assertIsInstance(metadata, MetaData)

        metadata_1 = unique_type_for_form(
            self.xform, data_type='enketo_url',
            data_value="https://dmerm.enketo.org/webform")

        self.assertIsInstance(metadata_1, MetaData)
        self.assertNotEqual(metadata.data_value, metadata_1.data_value)
        self.assertEqual(metadata.data_type, metadata_1.data_type)
        self.assertEqual(metadata.content_object, metadata_1.content_object)

    def test_upload_to_with_anonymous_user(self):
        instance = Instance(user=self.user, xform=self.xform)
        metadata = MetaData(data_type="media")
        metadata.content_object = instance
        filename = "filename"
        self.assertEquals(upload_to(metadata, filename),
                          "{}/{}/{}".format(self.user.username,
                                            'formid-media',
                                            filename))
        # test instance with anonymous user

        instance_without_user = Instance(xform=self.xform)
        metadata.content_object = instance_without_user
        self.assertEquals(upload_to(metadata, filename),
                          "{}/{}/{}".format(self.xform.user.username,
                                            'formid-media',
                                            filename))

    def test_upload_to_with_project_and_xform_instance(self):
        models = [Project, XForm]

        for model in models:
            model_instance = model(user=self.user, created_by=self.user)
            metadata = MetaData(data_type="media")
            metadata.content_object = model_instance

            filename = "filename"

            self.assertEquals(upload_to(metadata, filename),
                              "{}/{}/{}".format(self.user.username,
                                                'formid-media',
                                                filename))
