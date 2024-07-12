"""Tests for module onadata.apps.logger.tasks"""

import sys

from unittest.mock import patch

from celery.exceptions import Retry

from django.core.cache import cache
from django.db import DatabaseError
from django.utils import timezone

from onadata.apps.logger.models import EntityList
from onadata.apps.logger.tasks import (
    set_entity_list_perms_async,
    apply_project_date_modified_async,
)
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.cache_tools import PROJECT_DATE_MODIFIED_CACHE
from onadata.libs.utils.user_auth import get_user_default_project


@patch("onadata.apps.logger.tasks.set_project_perms_to_object")
class SetEntityListPermsAsyncTestCase(TestBase):
    """Tests for set_entity_list_perms_async"""

    def setUp(self):
        super().setUp()

        self.project = get_user_default_project(self.user)
        self.entity_list = EntityList.objects.create(name="trees", project=self.project)

    def test_set_perms(self, mock_set_perms):
        """Permissions are applied"""
        set_entity_list_perms_async.delay(self.entity_list.pk)
        mock_set_perms.assert_called_once_with(self.entity_list, self.project)

    @patch("onadata.apps.logger.tasks.set_entity_list_perms_async.retry")
    def test_retry_connection_error(self, mock_retry, mock_set_perms):
        """ConnectionError exception is retried"""
        mock_retry.side_effect = Retry
        mock_set_perms.side_effect = ConnectionError

        set_entity_list_perms_async.delay(self.entity_list.pk)

        self.assertTrue(mock_retry.called)

        _, kwargs = mock_retry.call_args_list[0]
        self.assertTrue(isinstance(kwargs["exc"], ConnectionError))

    @patch("onadata.apps.logger.tasks.set_entity_list_perms_async.retry")
    def test_retry_database_error(self, mock_retry, mock_set_perms):
        """DatabaseError exception is retried"""
        mock_retry.side_effect = Retry
        mock_set_perms.side_effect = DatabaseError

        set_entity_list_perms_async.delay(self.entity_list.pk)

        self.assertTrue(mock_retry.called)

        _, kwargs = mock_retry.call_args_list[0]
        self.assertTrue(isinstance(kwargs["exc"], DatabaseError))

    @patch("onadata.apps.logger.tasks.logger.exception")
    def test_invalid_pk(self, mock_logger, mock_set_perms):
        """Invalid EntityList primary key is handled"""
        set_entity_list_perms_async.delay(sys.maxsize)
        mock_set_perms.assert_not_called()
        mock_logger.assert_called_once()


class UpdateProjectDateModified(TestBase):
    """Tests for apply_project_date_modified_async"""

    def setUp(self):
        super().setUp()
        self.project = get_user_default_project(self.user)

    def test_update_project_date_modified(self):
        """Test project date_modified field is updated"""
        project_ids = cache.get(PROJECT_DATE_MODIFIED_CACHE, {})
        project_ids[self.project.pk] = timezone.now()
        initial_date_modified = self.project.date_modified
        cache.set(PROJECT_DATE_MODIFIED_CACHE, project_ids, timeout=300)

        apply_project_date_modified_async.delay()
        self.project.refresh_from_db()
        current_date_modified = self.project.date_modified

        # check that date_modified has changed
        self.assertNotEqual(initial_date_modified, current_date_modified)

        # check if current date modified is greater than initial
        self.assertGreater(current_date_modified, initial_date_modified)

        # assert that cache is cleared once task completes
        self.assertIsNone(cache.get(PROJECT_DATE_MODIFIED_CACHE))

    def test_update_project_date_modified_empty_cache(self):
        """Test project date modified empty cache"""
        # Ensure the cache is empty, meaning no projects exist
        cache.delete(PROJECT_DATE_MODIFIED_CACHE)

        # Run cronjon
        apply_project_date_modified_async.delay()

        # Verify that no projects were updated
        self.assertIsNone(cache.get(PROJECT_DATE_MODIFIED_CACHE))  # Cache should remain empty
