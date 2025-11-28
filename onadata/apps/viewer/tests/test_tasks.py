from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.utils import timezone

from celery import current_app

from onadata.apps.logger.models import EntityList
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models import GenericExport
from onadata.apps.viewer.models.export import Export
from onadata.apps.viewer.tasks import (
    create_async_export,
    delete_expired_failed_exports,
    generate_entity_list_export_async,
    mark_expired_pending_exports_as_failed,
)
from onadata.libs.utils.user_auth import get_user_default_project


class TestExportTasks(TestBase):
    def setUp(self):
        super(TestExportTasks, self).setUp()
        settings.CELERY_TASK_ALWAYS_EAGER = True
        current_app.conf.CELERY_TASK_ALWAYS_EAGER = True

    def test_create_async(self):
        self._publish_transportation_form_and_submit_instance()
        self.xform.refresh_from_db()
        options = {
            "group_delimiter": "/",
            "remove_group_name": False,
            "split_select_multiples": True,
        }
        export_types = (
            (Export.XLSX_EXPORT, {}),
            (Export.GOOGLE_SHEETS_EXPORT, {}),
            (Export.CSV_EXPORT, {}),
            (Export.CSV_ZIP_EXPORT, {}),
            (Export.SAV_ZIP_EXPORT, {}),
            (Export.ZIP_EXPORT, {}),
            (Export.KML_EXPORT, {}),
            (Export.OSM_EXPORT, {}),
            (Export.EXTERNAL_EXPORT, {"meta": "j2x.ona.io"}),
            (Export.GEOJSON_EXPORT, {}),
        )

        for export_type, extra_options in export_types:
            result = create_async_export(self.xform, export_type, None, False, options)
            export = result[0]
            self.assertTrue(export.id)
            self.assertIn("username", options)
            self.assertEqual(options.get("id_string"), self.xform.id_string)

    def test_mark_expired_pending_exports_as_failed(self):
        self._publish_transportation_form_and_submit_instance()
        over_threshold = settings.EXPORT_TASK_LIFESPAN + 2
        export = Export.objects.create(
            xform=self.xform,
            export_type=Export.CSV_EXPORT,
            internal_status=Export.PENDING,
            filename="",
        )
        # we set created_on here because Export.objects.create() overrides it
        export.created_on = timezone.now() - timedelta(hours=over_threshold)
        export.save()
        mark_expired_pending_exports_as_failed()
        export = Export.objects.filter(pk=export.pk).first()
        self.assertEqual(export.internal_status, Export.FAILED)

    def test_delete_expired_failed_exports(self):
        self._publish_transportation_form_and_submit_instance()
        over_threshold = settings.EXPORT_TASK_LIFESPAN + 2
        export = Export.objects.create(
            xform=self.xform,
            export_type=Export.CSV_EXPORT,
            internal_status=Export.FAILED,
            filename="",
        )
        # we set created_on here because Export.objects.create() overrides it
        export.created_on = timezone.now() - timedelta(hours=over_threshold)
        export.save()
        pk = export.pk
        delete_expired_failed_exports()
        self.assertEqual(Export.objects.filter(pk=pk).first(), None)


@patch("onadata.apps.viewer.tasks.generate_entity_list_export")
class GenEntityListExportTestCase(TestBase):
    def setUp(self):
        super().setUp()

        self.project = get_user_default_project(self.user)
        self.entity_list = EntityList.objects.create(name="trees", project=self.project)

    def test_entity_list_export_gen(self, mock_gen):
        """EntityList export is generated"""
        generate_entity_list_export_async.delay(self.entity_list.pk)

        self.assertTrue(
            GenericExport.objects.filter(object_id=self.entity_list.pk).exists()
        )

        export = GenericExport.objects.get(object_id=self.entity_list.pk)

        mock_gen.assert_called_once_with(self.entity_list, export=export)
