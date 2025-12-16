"""Tests for module onadata.apps.logger.tasks"""

import sys
from io import StringIO
from types import SimpleNamespace
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
    import_entities_from_csv_async,
    rotate_expired_keys_async,
    send_key_grace_expiry_reminder_async,
    send_key_rotation_reminder_async,
    set_entity_list_perms_async,
)
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.exceptions import NotAllMediaReceivedError
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
            (NotAllMediaReceivedError, "NotAllMediaReceivedError"),
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
    # pylint: disable=unused-argument
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


@patch("onadata.apps.logger.tasks.default_storage.open")
@patch("onadata.apps.logger.tasks.import_entities_from_csv")
class ImportEntitiesFromCSVAsyncTestCase(TestBase):
    """Tests for import_entities_from_csv_async"""

    def setUp(self):
        super().setUp()
        self.project = get_user_default_project(self.user)
        self.entity_list = EntityList.objects.create(name="trees", project=self.project)
        self.csv_file = StringIO(
            "label,species,circumference_cm\n300cm purpleheart,purpleheart,300"
        )

    def test_import_entities_from_csv(self, mock_import, mock_open):
        """Import entities from CSV"""
        mock_open.return_value = self.csv_file
        fake_results = iter(
            [
                SimpleNamespace(index=2, status="created", error=None),
                SimpleNamespace(index=3, status="updated", error=None),
                SimpleNamespace(index=4, status="error", error="boom"),
            ]
        )
        mock_import.return_value = fake_results

        result = import_entities_from_csv_async.delay(
            "csv_file.csv",
            self.entity_list.pk,
            label_column="tree_name",
            uuid_column="tree_id",
            user_id=self.user.pk,
        )
        out = result.get()
        mock_import.assert_called_once_with(
            self.entity_list,
            self.csv_file,
            user=self.user,
            label_column="tree_name",
            uuid_column="tree_id",
        )

        self.assertEqual(out["processed"], 3)
        self.assertEqual(out["created"], 1)
        self.assertEqual(out["updated"], 1)
        self.assertEqual(out["errors"], [(4, "boom")])

    @patch("onadata.apps.logger.tasks.import_entities_from_csv_async.retry")
    def test_retry_connection_error(self, mock_retry, mock_import, mock_open):
        """ConnectionError exception is retried"""

        def _gen_raises():
            def _g():
                raise ConnectionError()
                yield  # pylint: disable=unreachable

            return _g()

        mock_open.return_value = self.csv_file
        mock_import.return_value = _gen_raises()

        import_entities_from_csv_async.delay(
            "csv_file.csv", self.entity_list.pk, user_id=self.user.pk
        )
        self.assertTrue(mock_retry.called)
        _, kwargs = mock_retry.call_args_list[0]
        self.assertTrue(isinstance(kwargs["exc"], ConnectionError))

    @patch("onadata.apps.logger.tasks.import_entities_from_csv_async.retry")
    def test_retry_database_error(self, mock_retry, mock_import, mock_open):
        """DatabaseError exception is retried"""

        def _gen_raises():
            def _g():
                raise DatabaseError()
                yield  # pylint: disable=unreachable

            return _g()

        mock_open.return_value = self.csv_file
        mock_import.return_value = _gen_raises()

        import_entities_from_csv_async.delay(
            "csv_file.csv", self.entity_list.pk, user_id=self.user.pk
        )
        self.assertTrue(mock_retry.called)
        _, kwargs = mock_retry.call_args_list[0]
        self.assertTrue(isinstance(kwargs["exc"], DatabaseError))

    @patch("onadata.apps.logger.tasks.import_entities_from_csv_async.retry")
    def test_retry_operational_error(self, mock_retry, mock_import, mock_open):
        """OperationalError exception is retried"""

        def _gen_raises():
            def _g():
                raise OperationalError()
                yield  # pylint: disable=unreachable

            return _g()

        mock_open.return_value = self.csv_file
        mock_import.return_value = _gen_raises()

        import_entities_from_csv_async.delay(
            "csv_file.csv", self.entity_list.pk, user_id=self.user.pk
        )
        self.assertTrue(mock_retry.called)
        _, kwargs = mock_retry.call_args_list[0]
        self.assertTrue(isinstance(kwargs["exc"], OperationalError))

    def test_default_label_column(self, mock_import, mock_open):
        """Default label column is 'label' if not provided"""
        mock_open.return_value = self.csv_file
        import_entities_from_csv_async.delay(
            "csv_file.csv",
            self.entity_list.pk,
            user_id=self.user.pk,
            uuid_column="tree_id",
        )
        mock_import.assert_called_once_with(
            self.entity_list,
            self.csv_file,
            user=self.user,
            label_column="label",
            uuid_column="tree_id",
        )

    def test_default_uuid_column(self, mock_import, mock_open):
        """Default uuid column is 'uuid' if not provided"""
        mock_open.return_value = self.csv_file
        import_entities_from_csv_async.delay(
            "csv_file.csv",
            self.entity_list.pk,
            user_id=self.user.pk,
            label_column="tree_name",
        )
        mock_import.assert_called_once_with(
            self.entity_list,
            self.csv_file,
            user=self.user,
            label_column="tree_name",
            uuid_column="uuid",
        )

    @patch("onadata.apps.logger.tasks.send_message")
    def test_audit_log_created(self, mock_send_message, mock_import, mock_open):
        """Creates an audit log when entities are imported"""
        mock_open.return_value = self.csv_file

        import_entities_from_csv_async.delay(
            "csv_file.csv", self.entity_list.pk, user_id=self.user.pk
        )

        mock_import.assert_called_once()
        mock_send_message.assert_called_once_with(
            instance_id=self.entity_list.pk,
            target_id=self.entity_list.pk,
            target_type="entitylist",
            user=self.user,
            message_verb="entitylist_imported",
        )
