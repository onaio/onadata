from celery import current_app
from django.conf import settings

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models.export import Export
from onadata.apps.viewer.tasks import create_async_export


class TestExportTasks(TestBase):

    def setUp(self):
        super(TestExportTasks, self).setUp()
        settings.CELERY_ALWAYS_EAGER = True
        current_app.conf.CELERY_ALWAYS_EAGER = True

    def test_create_async(self):

        self._publish_transportation_form_and_submit_instance()
        options = {"group_delimiter": "/",
                   "remove_group_name": False,
                   "split_select_multiples": True}
        export_types = ((Export.XLS_EXPORT, {}),
                        (Export.GDOC_EXPORT, {}),
                        (Export.CSV_EXPORT, {}),
                        (Export.CSV_ZIP_EXPORT, {}),
                        (Export.SAV_ZIP_EXPORT, {}),
                        (Export.ZIP_EXPORT, {}),
                        (Export.KML_EXPORT, {}),
                        (Export.OSM_EXPORT, {}),
                        # (Export.EXTERNAL_EXPORT, {"meta": "j2x.ona.io"}),
                        )

        for export_type, extra_options in export_types:
            result = create_async_export(
                self.xform, export_type, None, False, options)

            export = result[0]
            self.assertTrue(export.id)
            self.assertIn("username", options)
            self.assertEquals(options.get("id_string"), self.xform.id_string)
