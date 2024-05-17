"""Tests for module onadata.apps.logger.models.merged_xform"""

from pyxform.builder import create_survey_element_from_dict
from unittest.mock import call, patch

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models.merged_xform import MergedXForm
from onadata.apps.logger.models.xform import XForm


class MergedXFormTestCase(TestBase):
    @patch("onadata.libs.utils.project_utils.set_project_perms_to_xform_async.delay")
    def test_perms_applied_async_on_create(self, mock_set_perms):
        """Permissions are applied asynchronously on create"""
        md = """
        | survey  |
        |         | type              | name  | label   |
        |         | select one fruits | fruit | Fruit   |

        | choices |
        |         | list name         | name   | label  |
        |         | fruits            | orange | Orange |
        |         | fruits            | mango  | Mango  |
        """
        self._publish_markdown(md, self.user, id_string="a")
        self._publish_markdown(md, self.user, id_string="b")
        xf1 = XForm.objects.get(id_string="a")
        xf2 = XForm.objects.get(id_string="b")
        survey = create_survey_element_from_dict(xf1.json_dict())
        survey["id_string"] = "c"
        survey["sms_keyword"] = survey["id_string"]
        survey["title"] = "Merged XForm"
        merged_xf = MergedXForm.objects.create(
            id_string=survey["id_string"],
            sms_id_string=survey["id_string"],
            title=survey["title"],
            user=self.user,
            created_by=self.user,
            is_merged_dataset=True,
            project=self.project,
            xml=survey.to_xml(),
            json=survey.to_json(),
        )
        merged_xf.xforms.add(xf1)
        merged_xf.xforms.add(xf2)
        calls = [
            call(xf1.pk, self.project.pk),
            call(xf2.pk, self.project.pk),
            call(merged_xf.pk, self.project.pk),
        ]
        mock_set_perms.assert_has_calls(calls, any_order=True)
