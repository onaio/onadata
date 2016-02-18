from django.contrib.contenttypes.models import ContentType

from test_base import TestBase
from onadata.apps.main.models.meta_data import (
    MetaData,
    ProjectMetaData,
    XFormMetaData)


class TestProjectMetaData(TestBase):
    def setUp(self):
        TestBase.setUp(self)
        self._create_user_and_login()
        self._publish_transportation_form_and_submit_instance()

    def test_create_project_metadata(self):
        count = MetaData.objects.filter(object_id=self.project.id,
                                        data_type='supporting_docs').count()
        xform_metadata_count = XFormMetaData.objects.count()
        project_metadata_count = ProjectMetaData.objects.count()

        content_type = ContentType.objects.get_for_model(self.project)

        MetaData.objects.create(
            content_type=content_type,
            data_type='supporting_docs',
            data_value='tutorial.xls',
            data_file='fixtures/tutorial.xls',
            data_file_type='xls',
            object_id=self.project.id
        )

        self.assertEquals(count + 1, MetaData.objects.filter(
            object_id=self.project.id, data_type='supporting_docs').count())
        self.assertEquals(xform_metadata_count, XFormMetaData.objects.count())
        self.assertEquals(project_metadata_count + 1,
                          ProjectMetaData.objects.count())
