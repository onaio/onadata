"""Tests for module onadata.apps.logger.models.merged_xform"""

from unittest.mock import call, patch

from onadata.apps.main.tests.test_base import TestBase


class MergedXFormTestCase(TestBase):
    @patch("onadata.libs.utils.project_utils.set_project_perms_to_xform_async.delay")
    def test_perms_applied_async_on_create(self, mock_set_perms):
        """Permissions are applied asynchronously on create"""
        merged_xf = self._create_merged_dataset()
        xf1 = merged_xf.xforms.get(id_string="a")
        xf2 = merged_xf.xforms.get(id_string="b")
        calls = [
            call(xf1.pk, self.project.pk),
            call(xf2.pk, self.project.pk),
            call(merged_xf.pk, self.project.pk),
        ]
        mock_set_perms.assert_has_calls(calls, any_order=True)
