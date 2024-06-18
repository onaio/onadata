"""Tests for module onadata.apps.logger.tasks"""

import sys

from unittest.mock import patch

from celery.exceptions import Retry

from django.db import DatabaseError

from onadata.apps.logger.models import EntityList
from onadata.apps.logger.tasks import set_entity_list_perms_async
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.user_auth import get_user_default_project


@patch("onadata.apps.logger.tasks.set_project_perms_to_entity_list")
class SetEntityListPermsAsyncTestCase(TestBase):
    """Tests for set_entity_list_perms_async"""

    def setUp(self):
        super().setUp()

        self.project = get_user_default_project(self.user)
        self.entity_list = EntityList.objects.create(name="trees", project=self.project)

    def test_set_perms(self, mock_set_perms):
        """Permissions are applied"""
        set_entity_list_perms_async.delay(self.entity_list.pk)
        mock_set_perms.assert_called_once_with(self.entity_list)

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
