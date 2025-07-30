# -*- coding: utf-8 -*-
"""
Test onadata.libs.utils.cache_tools module.
"""

import socket
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http.request import HttpRequest
from django.test import TestCase

from onadata.apps.logger.models.project import Project
from onadata.apps.main.models.user_profile import UserProfile
from onadata.libs.serializers.project_serializer import ProjectSerializer
from onadata.libs.utils.cache_tools import (
    PROJ_BASE_FORMS_CACHE,
    PROJ_FORMS_CACHE,
    PROJ_NUM_DATASET_CACHE,
    PROJ_OWNER_CACHE,
    PROJ_PERM_CACHE,
    PROJ_SUB_DATE_CACHE,
    project_cache_prefixes,
    reset_project_cache,
    safe_cache_add,
    safe_cache_decr,
    safe_cache_delete,
    safe_cache_get,
    safe_cache_incr,
    safe_cache_set,
    safe_key,
)

User = get_user_model()


class TestCacheTools(TestCase):
    """Test onadata.libs.utils.cache_tools module class"""

    def test_safe_key(self):
        """Test safe_key() function returns a hashed key"""
        self.assertEqual(
            safe_key("hello world"),
            "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9",
        )

    def test_reset_project_cache(self):
        """
        Test reset_project_cache() function actually resets all project cache
        entries
        """
        bob = User.objects.create(username="bob", first_name="bob")
        UserProfile.objects.create(user=bob)
        project = Project.objects.create(
            name="Some Project", created_by=bob, organization=bob
        )

        # Set dummy values in cache
        for prefix in project_cache_prefixes:
            cache.set(f"{prefix}{project.pk}", "stale")

        request = HttpRequest()
        request.user = bob
        request.META = {"SERVER_NAME": "testserver", "SERVER_PORT": "80"}
        reset_project_cache(project, request, ProjectSerializer)

        expected_project_cache = {
            "url": f"http://testserver/api/v1/projects/{project.pk}",
            "projectid": project.pk,
            "owner": "http://testserver/api/v1/users/bob",
            "created_by": "http://testserver/api/v1/users/bob",
            "metadata": {},
            "starred": False,
            "users": [
                {
                    "is_org": False,
                    "metadata": {},
                    "first_name": "bob",
                    "last_name": "",
                    "user": "bob",
                    "role": "owner",
                }
            ],
            "forms": [],
            "public": False,
            "tags": [],
            "num_datasets": 0,
            "last_submission_date": None,
            "teams": [],
            "data_views": [],
            "name": "Some Project",
            "deleted_at": None,
        }

        self.assertEqual(
            cache.get(f"{PROJ_PERM_CACHE}{project.pk}"), expected_project_cache["users"]
        )
        self.assertEqual(
            cache.get(f"{PROJ_NUM_DATASET_CACHE}{project.pk}"),
            expected_project_cache["num_datasets"],
        )
        self.assertEqual(
            cache.get(f"{PROJ_SUB_DATE_CACHE}{project.pk}"),
            expected_project_cache["last_submission_date"],
        )
        self.assertEqual(
            cache.get(f"{PROJ_FORMS_CACHE}{project.pk}"),
            expected_project_cache["forms"],
        )
        self.assertEqual(cache.get(f"{PROJ_BASE_FORMS_CACHE}{project.pk}"), None)

        project_cache = cache.get(f"{PROJ_OWNER_CACHE}{project.pk}")
        project_cache.pop("date_created")
        project_cache.pop("date_modified")
        self.assertEqual(project_cache, expected_project_cache)


@patch("onadata.libs.utils.cache_tools.cache.set")
class SafeCacheSetTestCase(TestCase):
    """Test method `safe_cache_set`"""

    def test_safe_cache_set(self, mock_set):
        """Cache value is set"""
        safe_cache_set("test", "test", timeout=10)

        mock_set.assert_called_once_with("test", "test", 10)

    def test_safe_cache_set_default_timeout(self, mock_set):
        """Cache value is set with default timeout"""
        safe_cache_set("test", "test")

        mock_set.assert_called_once_with("test", "test", 300)

    @patch("onadata.libs.utils.cache_tools.logger.exception")
    def test_exception_is_logged(self, mock_logger, mock_set):
        """Exception is logged"""
        test_cases = [
            (ConnectionError, "ConnectionError"),
            (socket.error, "socket.error"),
            (ValueError, "ValueError"),
        ]

        for exception_class, exception_name in test_cases:
            with self.subTest(exception=exception_name):
                mock_set.side_effect = exception_class
                safe_cache_set("test", "test", timeout=10)

                mock_set.assert_called_once_with("test", "test", 10)
                args, _ = mock_logger.call_args
                self.assertTrue(isinstance(args[0], exception_class))
                # Reset mocks for next iteration
                mock_logger.reset_mock()
                mock_set.reset_mock()


@patch("onadata.libs.utils.cache_tools.cache.get")
class SafeCacheGetTestCase(TestCase):
    """Test method `safe_cache_get`"""

    def test_safe_cache_get(self, mock_get):
        """Cache value is retrieved"""
        mock_get.return_value = "test"
        result = safe_cache_get("test", default="default")

        mock_get.assert_called_once_with("test", "default")
        self.assertEqual(result, "test")

    def test_cache_get_default_value(self, mock_get):
        """Default value is None"""
        safe_cache_get("test")

        mock_get.assert_called_once_with("test", None)

    @patch("onadata.libs.utils.cache_tools.logger.exception")
    def test_exception_is_logged(self, mock_logger, mock_get):
        """Exception is logged"""
        test_cases = [
            (ConnectionError, "ConnectionError"),
            (socket.error, "socket.error"),
            (ValueError, "ValueError"),
        ]

        for exception_class, exception_name in test_cases:
            with self.subTest(exception=exception_name):
                mock_get.side_effect = exception_class
                result = safe_cache_get("test", default="default")

                mock_get.assert_called_once_with("test", "default")
                args, _ = mock_logger.call_args
                self.assertTrue(isinstance(args[0], exception_class))
                self.assertEqual(result, "default")
                # Reset mocks for next iteration
                mock_logger.reset_mock()
                mock_get.reset_mock()


@patch("onadata.libs.utils.cache_tools.cache.add")
class SafeCacheAddTestCase(TestCase):
    """Test method `safe_cache_add`"""

    def test_safe_cache_add(self, mock_add):
        """Cache value is added"""
        mock_add.return_value = True
        result = safe_cache_add("test", "test", timeout=10)

        mock_add.assert_called_once_with("test", "test", 10)
        self.assertEqual(result, True)

    def test_safe_cache_add_default_timeout(self, mock_add):
        """Cache value is added with default timeout"""
        safe_cache_add("test", "test")

        mock_add.assert_called_once_with("test", "test", 300)

    @patch("onadata.libs.utils.cache_tools.logger.exception")
    def test_exception_is_logged(self, mock_logger, mock_add):
        """Exception is logged"""
        test_cases = [
            (ConnectionError, "ConnectionError"),
            (socket.error, "socket.error"),
            (ValueError, "ValueError"),
        ]

        for exception_class, exception_name in test_cases:
            with self.subTest(exception=exception_name):
                mock_add.side_effect = exception_class
                result = safe_cache_add("test", "test", timeout=10)

                mock_add.assert_called_once_with("test", "test", 10)
                args, _ = mock_logger.call_args
                self.assertTrue(isinstance(args[0], exception_class))
                self.assertEqual(result, False)
                # Reset mocks for next iteration
                mock_logger.reset_mock()
                mock_add.reset_mock()


@patch("onadata.libs.utils.cache_tools.cache.incr")
class SafeCacheIncrTestCase(TestCase):
    """Test method `safe_cache_incr`"""

    def test_safe_cache_incr(self, mock_incr):
        """Cache value is incremented"""
        mock_incr.return_value = 1
        result = safe_cache_incr("test", delta=1)

        mock_incr.assert_called_once_with("test", 1)
        self.assertEqual(result, 1)

    def test_safe_cache_incr_default_delta(self, mock_incr):
        """Cache value is incremented with default delta"""
        safe_cache_incr("test")

        mock_incr.assert_called_once_with("test", 1)

    @patch("onadata.libs.utils.cache_tools.logger.exception")
    def test_exception_is_logged(self, mock_logger, mock_incr):
        """Exception is logged"""
        test_cases = [
            (ConnectionError, "ConnectionError"),
            (socket.error, "socket.error"),
            (ValueError, "ValueError"),
        ]

        for exception_class, exception_name in test_cases:
            with self.subTest(exception=exception_name):
                mock_incr.side_effect = exception_class
                result = safe_cache_incr("test", delta=1)

                mock_incr.assert_called_once_with("test", 1)
                args, _ = mock_logger.call_args
                self.assertTrue(isinstance(args[0], exception_class))
                self.assertIsNone(result)
                # Reset mocks for next iteration
                mock_logger.reset_mock()
                mock_incr.reset_mock()


@patch("onadata.libs.utils.cache_tools.cache.decr")
class SafeCacheDecrTestCase(TestCase):
    """Test method `safe_cache_decr`"""

    def test_safe_cache_decr(self, mock_decr):
        """Cache value is decremented"""
        mock_decr.return_value = 1
        result = safe_cache_decr("test", delta=1)

        mock_decr.assert_called_once_with("test", 1)
        self.assertEqual(result, 1)

    def test_safe_cache_decr_default_delta(self, mock_decr):
        """Cache value is decremented with default delta"""
        safe_cache_decr("test")

        mock_decr.assert_called_once_with("test", 1)

    @patch("onadata.libs.utils.cache_tools.logger.exception")
    def test_exception_is_logged(self, mock_logger, mock_decr):
        """Exception is logged"""
        test_cases = [
            (ConnectionError, "ConnectionError"),
            (socket.error, "socket.error"),
            (ValueError, "ValueError"),
        ]

        for exception_class, exception_name in test_cases:
            with self.subTest(exception=exception_name):
                mock_decr.side_effect = exception_class
                result = safe_cache_decr("test", delta=1)

                mock_decr.assert_called_once_with("test", 1)
                args, _ = mock_logger.call_args
                self.assertTrue(isinstance(args[0], exception_class))
                self.assertIsNone(result)
                # Reset mocks for next iteration
                mock_logger.reset_mock()
                mock_decr.reset_mock()


@patch("onadata.libs.utils.cache_tools.cache.delete")
class SafeCacheDeleteTestCase(TestCase):
    """Test method `safe_cache_delete`"""

    def test_safe_cache_delete(self, mock_delete):
        """Cache value is deleted"""
        safe_cache_delete("test")

        mock_delete.assert_called_once_with("test")

    @patch("onadata.libs.utils.cache_tools.logger.exception")
    def test_exception_is_logged(self, mock_logger, mock_delete):
        """Exception is logged"""
        test_cases = [
            (ConnectionError, "ConnectionError"),
            (socket.error, "socket.error"),
            (ValueError, "ValueError"),
        ]

        for exception_class, exception_name in test_cases:
            with self.subTest(exception=exception_name):
                mock_delete.side_effect = exception_class
                safe_cache_delete("test")

                mock_delete.assert_called_once_with("test")
                args, _ = mock_logger.call_args
                self.assertTrue(isinstance(args[0], exception_class))
                # Reset mocks for next iteration
                mock_logger.reset_mock()
                mock_delete.reset_mock()
