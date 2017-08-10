from datetime import timedelta

from celery import current_app
from django.conf import settings
from django.utils import timezone
from django.core.files.storage import get_storage_class

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models.export import Export
from onadata.apps.viewer.tasks import create_async_export
from onadata.apps.viewer.tasks import check_pending_exports
from onadata.apps.viewer.tasks import delete_old_failed_exports


class TestExportTasks(TestBase):

    def setUp(self):
        super(TestExportTasks, self).setUp()
        settings.CELERY_ALWAYS_EAGER = True
        current_app.conf.CELERY_ALWAYS_EAGER = True

    def delete_export_file(self, filepath):
        storage = get_storage_class()()
        if filepath and storage.exists(filepath):
            storage.delete(filepath)

    def test_create_async(self):

        self._publish_transportation_form_and_submit_instance()
        options = {"group_delimiter": "/",
                   "remove_group_name": False,
                   "split_select_multiples": True}
        export_types = ((Export.XLS_EXPORT, {}),
                        (Export.GOOGLE_SHEETS_EXPORT, {}),
                        (Export.CSV_EXPORT, {}),
                        (Export.CSV_ZIP_EXPORT, {}),
                        (Export.SAV_ZIP_EXPORT, {}),
                        (Export.ZIP_EXPORT, {}),
                        (Export.KML_EXPORT, {}),
                        (Export.OSM_EXPORT, {}),
                        (Export.EXTERNAL_EXPORT, {"meta": "j2x.ona.io"}),
                        )

        for export_type, extra_options in export_types:
            result = create_async_export(
                self.xform, export_type, None, False, options)
            export = result[0]
            self.assertTrue(export.id)
            self.assertIn("username", options)
            self.assertEquals(options.get("id_string"), self.xform.id_string)

    def test_check_pending_exports(self):
        self._publish_transportation_form_and_submit_instance()
        options = {"group_delimiter": "/",
                   "remove_group_name": False,
                   "split_select_multiples": True}
        result = create_async_export(
            self.xform, Export.CSV_EXPORT, None, False, options)
        export = result[0]
        filepath = export.filepath
        export.filename = ""
        over_threshold = settings.EXPORT_TASK_LIFESPAN + 2
        export.internal_status = Export.PENDING
        export.created_on = timezone.now() - timedelta(hours=over_threshold)
        export.save()
        final_result = check_pending_exports.delay()
        self.delete_export_file(filepath)
        self.assertTrue(final_result)
        export = Export.objects.filter(pk=export.pk).first()
        self.assertEquals(export.internal_status, Export.FAILED)

    def test_delete_old_failed_exports(self):
        self._publish_transportation_form_and_submit_instance()
        options = {"group_delimiter": "/",
                   "remove_group_name": False,
                   "split_select_multiples": True}
        result = create_async_export(
            self.xform, Export.CSV_EXPORT, None, False, options)
        export = result[0]
        pk = export.pk
        filepath = export.filepath
        export.filename = ""
        over_threshold = settings.EXPORT_TASK_LIFESPAN + 2
        export.internal_status = Export.FAILED
        export.created_on = timezone.now() - timedelta(hours=over_threshold)
        export.save()
        final_result = delete_old_failed_exports.delay()
        self.delete_export_file(filepath)
        self.assertTrue(final_result)
        self.assertEquals(Export.objects.filter(pk=pk).first(), None)
