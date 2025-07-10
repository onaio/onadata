"""Tests for module onadata.apps.logger.tasks"""

import sys
from unittest.mock import patch

from django.core.cache import cache
from django.db import DatabaseError, OperationalError
from django.utils import timezone

from celery.exceptions import MaxRetriesExceededError
from valigetta.exceptions import ConnectionException as ValigettaConnectionException

from onadata.apps.logger.models import EntityList
from onadata.apps.logger.tasks import (
    adjust_xform_num_of_decrypted_submissions_async,
    apply_project_date_modified_async,
    commit_cached_elist_num_entities_async,
    commit_cached_xform_num_of_decrypted_submissions_async,
    decrypt_instance_async,
    disable_expired_keys_async,
    reconstruct_xform_export_register_async,
    register_instance_repeat_columns_async,
    rotate_expired_keys_async,
    send_key_grace_expiry_reminder_async,
    send_key_rotation_reminder_async,
    set_entity_list_perms_async,
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
    def test_retry_exceptions(self, mock_retry, mock_set_perms):
        """ConnectionError, DatabaseError, OperationalError exceptions are retried"""
        test_cases = [
            (ConnectionError, "ConnectionError"),
            (DatabaseError, "DatabaseError"),
            (OperationalError, "OperationalError"),
        ]

        for exception_class, exception_name in test_cases:
            with self.subTest(exception=exception_name):
                mock_set_perms.side_effect = exception_class
                set_entity_list_perms_async.delay(self.entity_list.pk)

                self.assertTrue(mock_retry.called)

                _, kwargs = mock_retry.call_args_list[0]
                self.assertTrue(isinstance(kwargs["exc"], exception_class))

                mock_retry.reset_mock()
                mock_set_perms.reset_mock()

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
        self.assertIsNone(
            cache.get(PROJECT_DATE_MODIFIED_CACHE)
        )  # Cache should remain empty


@patch("onadata.apps.logger.tasks.commit_cached_elist_num_entities")
class CommitEListNumEntitiesAsyncTestCase(TestBase):
    """Tests for method `commit_cached_elist_num_entities_async`"""

    def setUp(self):
        super().setUp()

        self.project = get_user_default_project(self.user)
        self.entity_list = EntityList.objects.create(
            name="trees", project=self.project, num_entities=10
        )

    def test_counter_commited(self, mock_commit):
        """Cached counter is commited in the database"""
        # pylint: disable=no-member
        commit_cached_elist_num_entities_async.delay()
        mock_commit.assert_called_once()

    @patch("onadata.apps.logger.tasks.commit_cached_elist_num_entities_async.retry")
    def test_retry_exceptions(self, mock_retry, mock_commit):
        """ConnectionError and DatabaseError exceptions are retried"""
        test_cases = [
            (ConnectionError, "ConnectionError"),
            (DatabaseError, "DatabaseError"),
            (OperationalError, "OperationalError"),
        ]

        for exception_class, exception_name in test_cases:
            with self.subTest(exception=exception_name):
                mock_commit.side_effect = exception_class
                # pylint: disable=no-member
                commit_cached_elist_num_entities_async.delay()

                self.assertTrue(mock_retry.called)

                _, kwargs = mock_retry.call_args_list[0]
                self.assertTrue(isinstance(kwargs["exc"], exception_class))

                # Reset mocks for next iteration
                mock_retry.reset_mock()
                mock_commit.reset_mock()


@patch("onadata.apps.logger.tasks.register_instance_repeat_columns")
class RegisterInstanceRepeatColumnsAsyncTestCase(TestBase):
    """Tests for register_instance_repeat_columns_async"""

    def setUp(self):
        super().setUp()

        self._publish_transportation_form()
        self._submit_transport_instance()
        self.instance = self.xform.instances.first()

    def test_register_columns(self, mock_register):
        """Columns are registered"""
        register_instance_repeat_columns_async.delay(self.instance.pk)
        mock_register.assert_called_once_with(self.instance)

    @patch("onadata.apps.logger.tasks.register_instance_repeat_columns_async.retry")
    def test_retry_exceptions(self, mock_retry, mock_register):
        """ConnectionError and DatabaseError exceptions are retried"""
        test_cases = [
            (ConnectionError, "ConnectionError"),
            (DatabaseError, "DatabaseError"),
            (OperationalError, "OperationalError"),
        ]

        for exception_class, exception_name in test_cases:
            with self.subTest(exception=exception_name):
                mock_register.side_effect = exception_class
                register_instance_repeat_columns_async.delay(self.instance.pk)

                self.assertTrue(mock_retry.called)

                _, kwargs = mock_retry.call_args_list[0]
                self.assertTrue(isinstance(kwargs["exc"], exception_class))

                # Reset mocks for next iteration
                mock_retry.reset_mock()
                mock_register.reset_mock()

    @patch("onadata.apps.logger.tasks.logger.exception")
    def test_invalid_pk(self, mock_logger, mock_register):
        """Invalid Instance primary key is handled"""
        register_instance_repeat_columns_async.delay(sys.maxsize)
        mock_register.assert_not_called()
        mock_logger.assert_called_once()


@patch("onadata.apps.logger.tasks.reconstruct_xform_export_register")
class ReconstructXFormExportRegisterAsyncTestCase(TestBase):
    """Tests for register_xform_export_register_async"""

    def setUp(self):
        super().setUp()

        self._publish_transportation_form()
        self._submit_transport_instance()

    def test_register_columns(self, mock_register):
        """Columns are registered"""
        reconstruct_xform_export_register_async.delay(self.xform.pk)
        mock_register.assert_called_once_with(self.xform)

    @patch("onadata.apps.logger.tasks.reconstruct_xform_export_register_async.retry")
    def test_retry_exceptions(self, mock_retry, mock_register):
        """ConnectionError and DatabaseError exceptions are retried"""
        test_cases = [
            (ConnectionError, "ConnectionError"),
            (DatabaseError, "DatabaseError"),
            (OperationalError, "OperationalError"),
        ]

        for exception_class, exception_name in test_cases:
            with self.subTest(exception=exception_name):
                mock_register.side_effect = exception_class
                reconstruct_xform_export_register_async.delay(self.xform.pk)

                self.assertTrue(mock_retry.called)

                _, kwargs = mock_retry.call_args_list[0]
                self.assertTrue(isinstance(kwargs["exc"], exception_class))

                # Reset mocks for next iteration
                mock_retry.reset_mock()
                mock_register.reset_mock()

    @patch("onadata.apps.logger.tasks.logger.exception")
    def test_invalid_pk(self, mock_logger, mock_register):
        """Invalid XForm primary key is handled"""
        reconstruct_xform_export_register_async.delay(sys.maxsize)
        mock_register.assert_not_called()
        mock_logger.assert_called_once()


@patch("onadata.apps.logger.tasks.rotate_expired_keys")
class RotateExpiredKeysAsyncTestCase(TestBase):
    """Tests for rotate_expired_keys_async"""

    def test_rotate_expired_keys(self, mock_rotate):
        """Rotate expired keys"""
        rotate_expired_keys_async.delay()
        mock_rotate.assert_called_once()

    @patch("onadata.apps.logger.tasks.rotate_expired_keys_async.retry")
    def test_retry_exceptions(self, mock_retry, mock_rotate):
        """ConnectionError and DatabaseError exceptions are retried"""
        test_cases = [
            (ConnectionError, "ConnectionError"),
            (DatabaseError, "DatabaseError"),
            (OperationalError, "OperationalError"),
        ]

        for exception_class, exception_name in test_cases:
            with self.subTest(exception=exception_name):
                mock_rotate.side_effect = exception_class
                rotate_expired_keys_async.delay()

                self.assertTrue(mock_retry.called)

                _, kwargs = mock_retry.call_args_list[0]
                self.assertTrue(isinstance(kwargs["exc"], exception_class))

                # Reset mocks for next iteration
                mock_retry.reset_mock()
                mock_rotate.reset_mock()


@patch("onadata.apps.logger.tasks.disable_expired_keys")
class DisableExpiredKeysAsyncTestCase(TestBase):
    """Tests for disable_expired_keys_async"""

    def test_disable_expired_keys(self, mock_disable):
        """Disable expired keys"""
        disable_expired_keys_async.delay()
        mock_disable.assert_called_once()

    @patch("onadata.apps.logger.tasks.disable_expired_keys_async.retry")
    def test_retry_exceptions(self, mock_retry, mock_disable):
        """ConnectionError and DatabaseError exceptions are retried"""
        test_cases = [
            (ConnectionError, "ConnectionError"),
            (DatabaseError, "DatabaseError"),
            (OperationalError, "OperationalError"),
        ]

        for exception_class, exception_name in test_cases:
            with self.subTest(exception=exception_name):
                mock_disable.side_effect = exception_class
                disable_expired_keys_async.delay()

                self.assertTrue(mock_retry.called)

                _, kwargs = mock_retry.call_args_list[0]
                self.assertTrue(isinstance(kwargs["exc"], exception_class))

                # Reset mocks for next iteration
                mock_retry.reset_mock()
                mock_disable.reset_mock()


@patch("onadata.apps.logger.tasks.send_key_rotation_reminder")
class SendKeyRotationReminderAsyncTestCase(TestBase):
    """Tests for send_key_rotation_reminder_async"""

    def test_send_key_rotation_reminder(self, mock_send):
        """Send key rotation reminder"""
        send_key_rotation_reminder_async.delay()
        mock_send.assert_called_once()

    @patch("onadata.apps.logger.tasks.send_key_rotation_reminder_async.retry")
    def test_retry_exceptions(self, mock_retry, mock_send):
        """ConnectionError and DatabaseError exceptions are retried"""
        test_cases = [
            (ConnectionError, "ConnectionError"),
            (DatabaseError, "DatabaseError"),
            (OperationalError, "OperationalError"),
        ]

        for exception_class, exception_name in test_cases:
            with self.subTest(exception=exception_name):
                mock_send.side_effect = exception_class
                send_key_rotation_reminder_async.delay()

                self.assertTrue(mock_retry.called)

                _, kwargs = mock_retry.call_args_list[0]
                self.assertTrue(isinstance(kwargs["exc"], exception_class))

                # Reset mocks for next iteration
                mock_retry.reset_mock()
                mock_send.reset_mock()


@patch("onadata.apps.logger.tasks.adjust_xform_num_of_decrypted_submissions")
class AdjustXFormDecryptedSubmissionCountAsyncTestCase(TestBase):
    """Tests for adjust_xform_num_of_decrypted_submissions_async"""

    def setUp(self):
        super().setUp()
        self._publish_transportation_form()

    def test_adjust_xform_num_of_decrypted_submissions(self, mock_adjust):
        """Adjust XForm decrypted submission count"""
        adjust_xform_num_of_decrypted_submissions_async.delay(self.xform.pk, delta=-1)
        mock_adjust.assert_called_once_with(self.xform, delta=-1)

    @patch(
        "onadata.apps.logger.tasks.adjust_xform_num_of_decrypted_submissions_async.retry"
    )
    def test_retry_exceptions(self, mock_retry, mock_adjust):
        """ConnectionError and DatabaseError exceptions are retried"""
        test_cases = [
            (ConnectionError, "ConnectionError"),
            (DatabaseError, "DatabaseError"),
            (OperationalError, "OperationalError"),
        ]

        for exception_class, exception_name in test_cases:
            with self.subTest(exception=exception_name):
                mock_adjust.side_effect = exception_class
                adjust_xform_num_of_decrypted_submissions_async.delay(
                    self.xform.pk, delta=-1
                )

                self.assertTrue(mock_retry.called)

                _, kwargs = mock_retry.call_args_list[0]
                self.assertTrue(isinstance(kwargs["exc"], exception_class))

                # Reset mocks for next iteration
                mock_retry.reset_mock()
                mock_adjust.reset_mock()

    @patch("onadata.apps.logger.tasks.logger.exception")
    def test_invalid_pk(self, mock_logger, mock_adjust):
        """Invalid XForm primary key is handled"""
        adjust_xform_num_of_decrypted_submissions_async.delay(sys.maxsize, delta=-1)
        mock_adjust.assert_not_called()
        mock_logger.assert_called_once()


@patch("onadata.apps.logger.tasks.commit_cached_xform_num_of_decrypted_submissions")
class CommitCachedXFormDecryptedSubmissionCountAsyncTestCase(TestBase):
    """Tests for commit_cached_xform_num_of_decrypted_submissions_async"""

    def test_commit_cached_xform_num_of_decrypted_submissions(self, mock_commit):
        """Commit cached XForm decrypted submission count"""
        commit_cached_xform_num_of_decrypted_submissions_async.delay()
        mock_commit.assert_called_once()

    @patch(
        "onadata.apps.logger.tasks.commit_cached_xform_num_of_decrypted_submissions_async.retry"
    )
    def test_retry_exceptions(self, mock_retry, mock_commit):
        """ConnectionError and DatabaseError exceptions are retried"""
        test_cases = [
            (ConnectionError, "ConnectionError"),
            (DatabaseError, "DatabaseError"),
            (OperationalError, "OperationalError"),
        ]

        for exception_class, exception_name in test_cases:
            with self.subTest(exception=exception_name):
                mock_commit.side_effect = exception_class
                commit_cached_xform_num_of_decrypted_submissions_async.delay()

                self.assertTrue(mock_retry.called)

                _, kwargs = mock_retry.call_args_list[0]
                self.assertTrue(isinstance(kwargs["exc"], exception_class))

                # Reset mocks for next iteration
                mock_retry.reset_mock()
                mock_commit.reset_mock()


@patch("onadata.apps.logger.tasks.send_key_grace_expiry_reminder")
class SendKeyGraceExpiryReminderAsyncTestCase(TestBase):
    """Tests for send_key_grace_expiry_reminder_async"""

    def test_send_key_grace_expiry_reminder(self, mock_send):
        """Send key grace expiry reminder"""
        send_key_grace_expiry_reminder_async.delay()
        mock_send.assert_called_once()

    @patch("onadata.apps.logger.tasks.send_key_grace_expiry_reminder_async.retry")
    def test_retry_exceptions(self, mock_retry, mock_send):
        """ConnectionError and DatabaseError exceptions are retried"""
        test_cases = [
            (ConnectionError, "ConnectionError"),
            (DatabaseError, "DatabaseError"),
            (OperationalError, "OperationalError"),
        ]

        for exception_class, exception_name in test_cases:
            with self.subTest(exception=exception_name):
                mock_send.side_effect = exception_class
                send_key_grace_expiry_reminder_async.delay()

                self.assertTrue(mock_retry.called)

                _, kwargs = mock_retry.call_args_list[0]
                self.assertTrue(isinstance(kwargs["exc"], exception_class))

                # Reset mocks for next iteration
                mock_retry.reset_mock()
                mock_send.reset_mock()


@patch("onadata.apps.logger.tasks.decrypt_instance")
class DecryptInstanceAsyncTestCase(TestBase):
    """Tests for decrypt_instance_async"""

    def setUp(self):
        super().setUp()
        self._publish_transportation_form()
        self._submit_transport_instance()
        self.instance = self.xform.instances.first()

    def test_decrypt_instance(self, mock_decrypt):
        """Decrypt instance"""
        decrypt_instance_async.delay(self.instance.pk)
        mock_decrypt.assert_called_once_with(self.instance)

    @patch("onadata.apps.logger.tasks.decrypt_instance_async.retry")
    def test_retry_exceptions(self, mock_retry, mock_decrypt):
        """ConnectionError and DatabaseError exceptions are retried"""
        test_cases = [
            (ConnectionError, "ConnectionError"),
            (DatabaseError, "DatabaseError"),
            (OperationalError, "OperationalError"),
            (ValigettaConnectionException, "ValigettaConnectionException"),
        ]

        for exception_class, exception_name in test_cases:
            with self.subTest(exception=exception_name):
                mock_decrypt.side_effect = exception_class
                decrypt_instance_async.delay(self.instance.pk)

                self.assertTrue(mock_retry.called)

                _, kwargs = mock_retry.call_args_list[0]
                self.assertTrue(isinstance(kwargs["exc"], exception_class))
                # Reset mocks for next iteration
                mock_retry.reset_mock()
                mock_decrypt.reset_mock()

    @patch("onadata.apps.logger.tasks.logger.exception")
    def test_invalid_pk(self, mock_logger, mock_decrypt):
        """Invalid Instance primary key is handled"""
        decrypt_instance_async.delay(sys.maxsize)
        mock_decrypt.assert_not_called()
        mock_logger.assert_called_once()

    @patch("onadata.apps.logger.tasks.save_decryption_error")
    def test_max_retries_exceeded(self, mock_save_decryption_error, mock_decrypt):
        """Instance is tagged as failed decryption if max retries exceeded"""
        decrypt_instance_async.on_failure(
            MaxRetriesExceededError(),
            "task_id",
            (self.instance.pk,),
            {},
            None,
        )

        mock_save_decryption_error.assert_called_once_with(
            self.instance, "MAX_RETRIES_EXCEEDED"
        )
