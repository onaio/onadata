import os

from django.core.files.storage import get_storage_class

from onadata.apps.viewer.models.export import Export
from onadata.libs.utils.export_tools import generate_export
from test_base import TestBase


class TestSavExport(TestBase):

    def setUp(self):
        self._create_user_and_login()

    def test_sav_zip_export(self):
        self._publish_transportation_form_and_submit_instance()
        export = generate_export(Export.SAV_ZIP_EXPORT, 'zip',
                                 self.user.username,
                                 self.xform.id_string)
        import ipdb
        ipdb.set_trace()

        storage = get_storage_class()()
        self.assertTrue(storage.exists(export.filepath))
        path, ext = os.path.splitext(export.filename)
        self.assertEqual(ext, '.zip')
