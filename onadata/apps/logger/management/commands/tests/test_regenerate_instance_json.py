"""Tests for management command regenerate_instance_json"""
from io import StringIO

from unittest.mock import patch, call

from celery.result import AsyncResult

from django.core.management import call_command
from django.core.cache import cache

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import XForm

# pylint: disable=line-too-long


class RegenerateInstanceJsonTestCase(TestBase):
    """Tests for management command regenerate_instance_json"""

    def setUp(self):
        super().setUp()

        self._publish_transportation_form()
        self._make_submissions()
        self.cache_key = f"xfm-regenerate_instance_json_task-{self.xform.pk}"
        self.out = StringIO()

    @patch(
        "onadata.apps.logger.management.commands.regenerate_instance_json.regenerate_form_instance_json"
    )
    def test_regenerates_instance_json(self, mock_regenerate):
        """Json data for form submissions is regenerated

        Regeneration should be asynchronous
        """
        task_id = "f78ef7bb-873f-4a28-bc8a-865da43a741f"
        mock_async_result = AsyncResult(task_id)
        mock_regenerate.apply_async.return_value = mock_async_result
        call_command("regenerate_instance_json", (self.xform.pk), stdout=self.out)
        self.assertIn(f"Regeneration for {self.xform.pk} STARTED", self.out.getvalue())
        mock_regenerate.apply_async.assert_called_once_with(args=[self.xform.pk])
        self.assertEqual(cache.get(self.cache_key), task_id)

    @patch(
        "onadata.apps.logger.management.commands.regenerate_instance_json.regenerate_form_instance_json"
    )
    def test_multiple_form_ids(self, mock_regenerate):
        """Command supports multiple forms"""
        self._publish_xlsx_file_with_external_choices()
        form2 = XForm.objects.all()[1]
        mock_regenerate.apply_async.side_effect = [
            AsyncResult("f78ef7bb-873f-4a28-bc8a-865da43a741f"),
            AsyncResult("ca760839-d2d9-4244-938f-e884880ac0b4"),
        ]
        call_command(
            "regenerate_instance_json", (self.xform.pk, form2.pk), stdout=self.out
        )
        self.assertIn(f"Regeneration for {self.xform.pk} STARTED", self.out.getvalue())
        self.assertIn(f"Regeneration for {form2.pk} STARTED", self.out.getvalue())
        mock_regenerate.apply_async.assert_has_calls(
            [call(args=[self.xform.pk]), call(args=[form2.pk])]
        )
        self.assertEqual(
            cache.get(self.cache_key), "f78ef7bb-873f-4a28-bc8a-865da43a741f"
        )
        form2_cache = f"xfm-regenerate_instance_json_task-{form2.pk}"
        self.assertEqual(cache.get(form2_cache), "ca760839-d2d9-4244-938f-e884880ac0b4")

    @patch(
        "onadata.apps.logger.management.commands.regenerate_instance_json.regenerate_form_instance_json"
    )
    def test_no_duplicate_work(self, mock_regenerate):
        """If a regeneration finished successfully, we do not run it again"""
        self.xform.is_instance_json_regenerated = True
        self.xform.save()
        call_command("regenerate_instance_json", (self.xform.pk), stdout=self.out)
        self.assertIn(f"Regeneration for {self.xform.pk} COMPLETE", self.out.getvalue())
        mock_regenerate.apply_async.assert_not_called()
        self.assertFalse(cache.get(self.cache_key))

    def _mock_get_task_meta_failure(self) -> dict[str, str]:
        return {"status": "FAILURE"}

    @patch.object(AsyncResult, "_get_task_meta", _mock_get_task_meta_failure)
    @patch(
        "onadata.apps.logger.management.commands.regenerate_instance_json.regenerate_form_instance_json"
    )
    def test_task_state_failed(self, mock_regenerate):
        """We regenerate if old celery task failed"""
        old_task_id = "796dc413-e6ea-42b8-b658-e4ac9e22b02b"
        cache.set(self.cache_key, old_task_id)
        new_task_id = "f78ef7bb-873f-4a28-bc8a-865da43a741f"
        mock_async_result = AsyncResult(new_task_id)
        mock_regenerate.apply_async.return_value = mock_async_result
        call_command("regenerate_instance_json", (self.xform.pk), stdout=self.out)
        self.assertIn(f"Regeneration for {self.xform.pk} STARTED", self.out.getvalue())
        mock_regenerate.apply_async.assert_called_once_with(args=[self.xform.pk])
        self.assertEqual(cache.get(self.cache_key), new_task_id)

    def _mock_get_task_meta_non_failure(self) -> dict[str, str]:
        return {"status": "FOO"}

    @patch.object(AsyncResult, "_get_task_meta", _mock_get_task_meta_non_failure)
    @patch(
        "onadata.apps.logger.management.commands.regenerate_instance_json.regenerate_form_instance_json"
    )
    def test_task_state_not_failed(self, mock_regenerate):
        """We do not regenerate if last celery task is in a state other than FAILURE

        FAILURE is the only state that should trigger regeneration if a regeneration
        had earlier been triggered
        """
        old_task_id = "796dc413-e6ea-42b8-b658-e4ac9e22b02b"
        cache.set(self.cache_key, old_task_id)
        mock_async_result = AsyncResult(old_task_id)
        mock_regenerate.apply_async.return_value = mock_async_result
        call_command("regenerate_instance_json", (self.xform.pk), stdout=self.out)
        self.assertIn(
            f"Regeneration for {self.xform.pk} IN PROGRESS", self.out.getvalue()
        )
        mock_regenerate.apply_async.assert_not_called()
        self.assertEqual(cache.get(self.cache_key), old_task_id)
