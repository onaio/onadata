import os

from django.conf import settings
from tempfile import NamedTemporaryFile
from rest_framework.test import APIRequestFactory

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.viewer.models import Export
from onadata.libs.serializers.export_serializer import ExportSerializer
from onadata.apps.viewer.tasks import create_async_export


class TestExportSerializer(TestAbstractViewSet):
    def test_project_serializer(self):
        request = APIRequestFactory().get('/')
        self._publish_xls_form_to_project()
        temp_dir = settings.MEDIA_ROOT
        dummy_export_file = NamedTemporaryFile(suffix='.xlsx', dir=temp_dir)
        filename = os.path.basename(dummy_export_file.name)
        filedir = os.path.dirname(dummy_export_file.name)
        options = {"group_delimiter": "/",
                   "remove_group_name": False,
                   "split_select_multiples": True}
        export = Export.objects.create(xform=self.xform,
                                       filename=filename,
                                       filedir=filedir,
                                       options=options,
                                       internal_status=True)
        export.save()
        export = create_async_export(self.xform, 'csv', None, False, options)
        serializer = ExportSerializer(instance=export[0], context={'request':
                                                                   request})
        self.assertEqual(serializer.data.keys(), ['id', 'job_status', 'type',
                                                  'task_id', 'xform',
                                                  'date_created', 'filename',
                                                  'options'])
