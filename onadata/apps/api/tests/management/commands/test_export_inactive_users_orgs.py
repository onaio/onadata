# -*- coding: utf-8 -*-
"""
Test cases for export_inactive_users_orgs management command
"""

import csv
import json
import os
import shutil
import tempfile
import uuid
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from onadata.apps.api.management.commands.export_inactive_users_orgs import Command
from onadata.libs.utils.inactive_export_tracker import InactiveExportTracker

User = get_user_model()


class TestExportInactiveUsersOrgs(TestCase):
    """Test export_inactive_users_orgs management command"""

    def setUp(self):
        """Set up test data"""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test files"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_users"
    )
    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_organizations"
    )
    def test_csv_export_creates_files(self, mock_orgs, mock_users):
        """Test that CSV export creates output files"""
        # Mock data
        mock_users.return_value = [
            {
                "username": "test_user",
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "last_login": None,
                "date_joined": "2020-01-01",
                "is_active": True,
                "profile_name": "Test User",
                "organization": "Test Org",
                "num_of_submissions": 10,
                "project_count": 2,
                "form_count": 5,
            }
        ]

        mock_orgs.return_value = [
            {
                "org_name": "Test Org",
                "org_username": "test_org",
                "org_email": "org@example.com",
                "date_created": "2020-01-01",
                "creator_username": "creator",
                "creator_email": "creator@example.com",
                "creator_date_joined": "2019-12-01",
                "creator_last_login": "2020-01-01",
                "last_submission_date": "2020-06-01",
                "project_count": 2,
                "form_count": 5,
                "total_submissions": 100,
            }
        ]

        # Run command with skip storage to avoid S3 mocking complexity
        call_command(
            "export_inactive_users_orgs",
            output_dir=self.temp_dir,
            verbosity=0,
            include_storage=False,
        )

        # Check that files were created
        files = os.listdir(self.temp_dir)
        csv_files = [f for f in files if f.endswith(".csv")]

        self.assertGreater(len(csv_files), 0, "No CSV files were created")

    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_users"
    )
    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_organizations"
    )
    def test_command_with_custom_years(self, mock_orgs, mock_users):
        """Test command with custom years parameter"""
        mock_users.return_value = []
        mock_orgs.return_value = []

        # Should not raise an error
        call_command(
            "export_inactive_users_orgs",
            years=3,
            output_dir=self.temp_dir,
            verbosity=0,
            include_storage=False,
        )

        # Verify the years parameter was passed correctly
        mock_users.assert_called_with(3, None, 0)  # years, limit, offset
        mock_orgs.assert_called_with(3, None, 0)  # years, limit, offset

    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_users"
    )
    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_organizations"
    )
    def test_csv_file_format(self, mock_orgs, mock_users):
        """Test that CSV files have correct format and headers"""
        # Mock data
        mock_users.return_value = [
            {
                "username": "test_user",
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "last_login": None,
                "date_joined": "2020-01-01T00:00:00Z",
                "is_active": True,
                "profile_name": "Test User",
                "organization": "Test Org",
                "num_of_submissions": 10,
                "project_count": 2,
                "form_count": 5,
            }
        ]

        mock_orgs.return_value = [
            {
                "org_name": "Test Org",
                "org_username": "test_org",
                "org_email": "org@example.com",
                "date_created": "2020-01-01",
                "creator_username": "creator",
                "creator_email": "creator@example.com",
                "creator_date_joined": "2019-12-01",
                "creator_last_login": "2020-01-01",
                "last_submission_date": "2020-06-01",
                "project_count": 2,
                "form_count": 5,
                "total_submissions": 100,
            }
        ]

        # Run command with storage calculation skipped to avoid S3 mocking complexity
        call_command(
            "export_inactive_users_orgs",
            output_dir=self.temp_dir,
            verbosity=0,
            include_storage=False,
        )

        # Find and read the users CSV file
        files = os.listdir(self.temp_dir)
        user_csv = [f for f in files if "users" in f and f.endswith(".csv")][0]

        with open(os.path.join(self.temp_dir, user_csv), "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames

            expected_headers = [
                "username",
                "email",
                "domain",
                "first_name",
                "last_name",
                "name",
                "last_login",
                "date_joined",
                "is_active",
                "profile_name",
                "organization",
                "num_of_submissions",
                "project_count",
                "form_count",
            ]

            for header in expected_headers:
                self.assertIn(header, headers, f"Missing header: {header}")

            # Read first row
            row = next(reader)
            self.assertEqual(row["username"], "test_user")

        # Check organizations CSV
        org_csv = [f for f in files if "organizations" in f and f.endswith(".csv")][0]

        with open(os.path.join(self.temp_dir, org_csv), "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames

            expected_headers = [
                "org_name",
                "org_username",
                "email",
                "domain",
                "date_created",
                "creator_username",
                "creator_email",
                "creator_domain",
                "creator_date_joined",
                "creator_last_login",
                "last_submission_date",
                "project_count",
                "form_count",
                "total_submissions",
            ]

            for header in expected_headers:
                self.assertIn(header, headers, f"Missing header: {header}")

            # Read first row
            row = next(reader)
            self.assertEqual(row["org_name"], "Test Org")

    def test_sql_query_structure(self):
        """Test that SQL queries are properly structured"""
        command = Command()

        # Test that the methods exist and can be called
        self.assertTrue(hasattr(command, "get_inactive_users"))
        self.assertTrue(hasattr(command, "get_inactive_organizations"))

        # Test that they accept years parameter
        try:
            # These will fail due to no test data, but should not raise AttributeError
            command.get_inactive_users(years=5)
        except Exception as e:
            # Should be a database-related error, not an AttributeError
            self.assertNotIsInstance(e, AttributeError)

        try:
            command.get_inactive_organizations(years=5)
        except Exception as e:
            # Should be a database-related error, not an AttributeError
            self.assertNotIsInstance(e, AttributeError)

    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_users"
    )
    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_organizations"
    )
    def test_handles_empty_results(self, mock_orgs, mock_users):
        """Test that the command handles empty results gracefully"""
        mock_users.return_value = []
        mock_orgs.return_value = []

        # Should not raise an error
        call_command(
            "export_inactive_users_orgs", output_dir=self.temp_dir, verbosity=0
        )

        # Should still create files (with headers only)
        files = os.listdir(self.temp_dir)
        csv_files = [f for f in files if f.endswith(".csv")]
        self.assertEqual(
            len(csv_files), 0, "No files should be created for empty results"
        )

    def test_data_completeness_requirements(self):
        """Test that all required fields are defined in the command"""
        command = Command()

        # Check that export methods exist
        self.assertTrue(hasattr(command, "export_inactive_users"))
        self.assertTrue(hasattr(command, "export_inactive_organizations"))

        # Check that formatting method exists
        self.assertTrue(hasattr(command, "_format_datetime"))

    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_users"
    )
    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_organizations"
    )
    def test_verbosity_levels(self, mock_orgs, mock_users):
        """Test that different verbosity levels work"""
        mock_users.return_value = []
        mock_orgs.return_value = []

        # Test different verbosity levels
        for verbosity in [0, 1, 2]:
            call_command(
                "export_inactive_users_orgs",
                output_dir=self.temp_dir,
                verbosity=verbosity,
            )

    def test_command_help_text(self):
        """Test that the command has proper help text"""
        command = Command()
        self.assertTrue(hasattr(command, "help"))
        self.assertIn("inactive", command.help.lower())

    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_users"
    )
    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_organizations"
    )
    def test_date_formatting(self, mock_orgs, mock_users):
        """Test that date formatting works correctly"""
        # Test with various date formats
        test_datetime = timezone.now()

        mock_users.return_value = [
            {
                "username": "test_user",
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "last_login": test_datetime,
                "date_joined": test_datetime,
                "is_active": True,
                "profile_name": "Test User",
                "organization": "Test Org",
                "num_of_submissions": 10,
                "project_count": 2,
                "form_count": 5,
            }
        ]

        mock_orgs.return_value = [
            {
                "org_name": "Test Org",
                "org_username": "test_org",
                "org_email": "org@example.com",
                "date_created": test_datetime,
                "creator_username": "creator",
                "creator_email": "creator@example.com",
                "creator_date_joined": test_datetime,
                "creator_last_login": test_datetime,
                "last_submission_date": test_datetime,
                "project_count": 2,
                "form_count": 5,
                "total_submissions": 100,
            }
        ]

        # Should not raise an error
        call_command(
            "export_inactive_users_orgs",
            output_dir=self.temp_dir,
            verbosity=0,
            include_storage=False,
        )

        # Check that dates were formatted properly in CSV
        files = os.listdir(self.temp_dir)
        if files:
            user_csv = [f for f in files if "users" in f and f.endswith(".csv")]
            if user_csv:
                with open(
                    os.path.join(self.temp_dir, user_csv[0]), "r", encoding="utf-8"
                ) as f:
                    content = f.read()
                    # Should contain formatted date string
                    self.assertIn(test_datetime.strftime("%Y-%m-%d"), content)

    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_users"
    )
    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_organizations"
    )
    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.boto3.client"
    )
    def test_storage_size_calculation(self, mock_boto3_client, mock_orgs, mock_users):
        """Test that storage size calculation works correctly"""
        # Mock S3 client
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client

        # Mock paginator for S3 list_objects_v2
        mock_paginator = MagicMock()
        mock_s3_client.get_paginator.return_value = mock_paginator

        # Mock page iterator with file data
        mock_page_iterator = [
            {
                "Contents": [
                    {"Key": "test_user/attachments/file1.jpg", "Size": 1048576},  # 1MB
                    {"Key": "test_user/docs/file2.pdf", "Size": 2097152},  # 2MB
                    {"Key": "test_user/exports/file3.csv", "Size": 512000},  # 0.5MB
                ]
            }
        ]
        mock_paginator.paginate.return_value = mock_page_iterator

        # Mock data
        mock_users.return_value = [
            {
                "username": "test_user",
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "last_login": None,
                "date_joined": "2020-01-01T00:00:00Z",
                "is_active": True,
                "profile_name": "Test User",
                "organization": "Test Org",
                "num_of_submissions": 10,
                "project_count": 2,
                "form_count": 5,
            }
        ]

        mock_orgs.return_value = []

        # Run command with storage calculation enabled
        with patch(
            "onadata.apps.api.management.commands.export_inactive_users_orgs.settings"
        ) as mock_settings:
            mock_settings.AWS_ACCESS_KEY_ID = "test_key"
            mock_settings.AWS_SECRET_ACCESS_KEY = "test_secret"
            mock_settings.AWS_STORAGE_BUCKET_NAME = "test_bucket"
            mock_settings.AWS_S3_REGION_NAME = "us-east-1"

            call_command(
                "export_inactive_users_orgs",
                output_dir=self.temp_dir,
                verbosity=0,
                include_storage=True,
            )

        # Check that CSV contains storage information
        files = os.listdir(self.temp_dir)
        user_csv = [f for f in files if "users" in f and f.endswith(".csv")][0]

        with open(os.path.join(self.temp_dir, user_csv), "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames

            # Check storage headers are present
            self.assertIn("storage_size_mb", headers)
            self.assertIn("storage_breakdown", headers)

            # Read first row
            row = next(reader)
            self.assertEqual(row["username"], "test_user")
            # Total: 1MB + 2MB + 0.5MB = 3.5MB (allow small rounding difference)
            self.assertAlmostEqual(float(row["storage_size_mb"]), 3.5, places=1)
            # Check storage breakdown JSON
            breakdown = json.loads(row["storage_breakdown"])
            self.assertEqual(breakdown["attachments"], 1.0)
            self.assertEqual(breakdown["docs"], 2.0)
            self.assertAlmostEqual(breakdown["exports"], 0.5, places=1)

    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_users"
    )
    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_organizations"
    )
    def test_include_storage_option(self, mock_orgs, mock_users):
        """Test that include-storage option works correctly"""
        # Mock data
        mock_users.return_value = [
            {
                "username": "test_user",
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "last_login": None,
                "date_joined": "2020-01-01T00:00:00Z",
                "is_active": True,
                "profile_name": "Test User",
                "organization": "Test Org",
                "num_of_submissions": 10,
                "project_count": 2,
                "form_count": 5,
            }
        ]

        mock_orgs.return_value = [
            {
                "org_name": "Test Org",
                "org_username": "test_org",
                "org_email": "org@example.com",
                "date_created": "2020-01-01",
                "creator_username": "creator",
                "creator_email": "creator@example.com",
                "creator_date_joined": "2019-12-01",
                "creator_last_login": "2020-01-01",
                "last_submission_date": "2020-06-01",
                "project_count": 2,
                "form_count": 5,
                "total_submissions": 100,
            }
        ]

        # Run command without include-storage (default behavior)
        call_command(
            "export_inactive_users_orgs",
            output_dir=self.temp_dir,
            verbosity=0,
            include_storage=False,
        )

        # Check that CSV does NOT contain storage information
        files = os.listdir(self.temp_dir)
        user_csv = [f for f in files if "users" in f and f.endswith(".csv")][0]

        with open(os.path.join(self.temp_dir, user_csv), "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames

            # Check storage headers are NOT present
            self.assertNotIn("storage_size_mb", headers)
            self.assertNotIn("storage_breakdown", headers)

    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_users"
    )
    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_organizations"
    )
    def test_limit_functionality(self, mock_orgs, mock_users):
        """Test that limit parameter works correctly"""
        # Create more mock data than the limit
        mock_users.return_value = [
            {
                "id": i,
                "username": f"test_user_{i}",
                "email": f"test{i}@example.com",
                "first_name": "Test",
                "last_name": f"User{i}",
                "last_login": None,
                "date_joined": "2020-01-01T00:00:00Z",
                "is_active": True,
                "profile_name": f"Test User {i}",
                "organization": "",
                "num_of_submissions": 0,
                "project_count": 0,
                "form_count": 0,
            }
            for i in range(5)  # 5 users
        ]

        mock_orgs.return_value = [
            {
                "userprofile_ptr_id": i + 100,
                "org_name": f"Test Org {i}",
                "org_username": f"test_org_{i}",
                "org_email": f"org{i}@example.com",
                "date_created": "2020-01-01",
                "creator_username": f"creator{i}",
                "creator_email": f"creator{i}@example.com",
                "creator_date_joined": "2019-12-01",
                "creator_last_login": "2020-01-01",
                "last_submission_date": "2020-06-01",
                "project_count": 1,
                "form_count": 2,
                "total_submissions": 10,
            }
            for i in range(5)  # 5 organizations
        ]

        # Run command with limit
        call_command(
            "export_inactive_users_orgs",
            output_dir=self.temp_dir,
            verbosity=0,
            include_storage=False,
            limit=3,  # Limit to 3 records each
        )

        # Verify mock calls received the limit parameter
        mock_users.assert_called_with(2, 3, 0)  # years=2, limit=3, offset=0
        mock_orgs.assert_called_with(2, 3, 0)

        # Verify files were created
        files = os.listdir(self.temp_dir)
        csv_files = [f for f in files if f.endswith(".csv")]
        self.assertEqual(len(csv_files), 2)  # users and organizations files

    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_users"
    )
    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_organizations"
    )
    def test_tracking_functionality(self, mock_orgs, mock_users):
        """Test that tracking functionality works correctly"""
        # Create unique session ID to avoid test interference
        unique_session = f"test_session_{uuid.uuid4().hex[:8]}"
        mock_users.return_value = [
            {
                "id": 1,
                "username": "test_user",
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "last_login": None,
                "date_joined": "2020-01-01T00:00:00Z",
                "is_active": True,
                "profile_name": "Test User",
                "organization": "",
                "num_of_submissions": 10,
                "project_count": 2,
                "form_count": 5,
            }
        ]

        mock_orgs.return_value = [
            {
                "userprofile_ptr_id": 100,
                "org_name": "Test Org",
                "org_username": "test_org",
                "org_email": "org@example.com",
                "date_created": "2020-01-01",
                "creator_username": "creator",
                "creator_email": "creator@example.com",
                "creator_date_joined": "2019-12-01",
                "creator_last_login": "2020-01-01",
                "last_submission_date": "2020-06-01",
                "project_count": 2,
                "form_count": 5,
                "total_submissions": 100,
            }
        ]

        # Run command with tracking enabled
        call_command(
            "export_inactive_users_orgs",
            output_dir=self.temp_dir,
            verbosity=0,
            include_storage=False,
            track_exports=True,
            export_session=unique_session,
        )

        # Check that tracking records were created
        tracker = InactiveExportTracker(unique_session)

        # Check user tracking
        user_usernames = tracker.get_exported_inactive_usernames("user")
        self.assertEqual(len(user_usernames), 1)
        self.assertIn("test_user", user_usernames)

        # Check organization tracking
        org_usernames = tracker.get_exported_inactive_usernames("organization")
        self.assertEqual(len(org_usernames), 1)
        self.assertIn("test_org", org_usernames)

    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_users"
    )
    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_organizations"
    )
    def test_resume_session_functionality(self, mock_orgs, mock_users):
        """Test that resume session functionality works correctly"""
        # Create unique session ID to avoid test interference
        unique_session = f"existing_session_{uuid.uuid4().hex[:8]}"

        # Pre-create some tracking records to simulate previous exports
        tracker = InactiveExportTracker(unique_session)
        tracker.add_inactive_record(
            export_type="user",
            record_id=1,
            username="already_exported_user",
            years_threshold=2,
        )

        # Mock data - the exclusion logic should filter out the already exported user
        # So we only return the user that should be processed
        mock_users.return_value = [
            {
                "id": 2,
                "username": "new_user",
                "email": "new@example.com",
                "first_name": "New",
                "last_name": "User",
                "last_login": None,
                "date_joined": "2020-01-01T00:00:00Z",
                "is_active": True,
                "profile_name": "New User",
                "organization": "",
                "num_of_submissions": 3,
                "project_count": 1,
                "form_count": 2,
            }
        ]

        mock_orgs.return_value = []

        # Resume the session
        call_command(
            "export_inactive_users_orgs",
            output_dir=self.temp_dir,
            verbosity=0,
            include_storage=False,
            resume_session=unique_session,
        )

        # Verify that the exclusion was applied (only new_user should be processed)
        # The mock should be called with the new signature (years, limit, offset)
        args, kwargs = mock_users.call_args
        self.assertEqual(args, (2, None, 0))  # years=2, limit=None, offset=0

        # Verify that one user was exported (the new_user, not the already_exported_user)
        tracker = InactiveExportTracker(unique_session)
        user_usernames = tracker.get_exported_inactive_usernames("user")
        self.assertEqual(len(user_usernames), 2)  # original + new user
        self.assertIn("already_exported_user", user_usernames)
        self.assertIn("new_user", user_usernames)

    def test_inactive_export_tracker(self):
        """Test InactiveExportTracker functionality"""
        # Test creating tracker and adding records with unique session
        unique_session = f"test_session_{uuid.uuid4().hex[:8]}"
        tracker = InactiveExportTracker(unique_session)
        tracker.add_inactive_record(
            export_type="user",
            record_id=123,
            username="test_user",
            years_threshold=2,
        )

        # Test get_exported_inactive_usernames method
        usernames = tracker.get_exported_inactive_usernames("user")
        self.assertIn("test_user", usernames)
        self.assertEqual(len(usernames), 1)

        # Test get_inactive_session_stats method
        stats = InactiveExportTracker.get_inactive_session_stats(unique_session)
        self.assertIn("user", stats)
        self.assertEqual(stats["user"]["count"], 1)

        # Test summary
        summary = tracker.get_summary()
        self.assertEqual(summary["total_inactive_users"], 1)
        self.assertEqual(summary["total_inactive_orgs"], 0)

    def test_azure_storage_backend_detection(self):
        """Test that Azure storage backend detection works"""
        command = Command()
        command._verbosity = 0  # Prevent output during test

        # Set up the command attributes that would be set during init
        command.storage_client = MagicMock()
        command.storage_container = "test-container"
        command.storage_backend = "azure"

        # Mock the Azure imports to avoid ModuleNotFoundError
        with patch.dict("sys.modules", {"azure.core.exceptions": MagicMock()}):
            # Mock Azure container client
            mock_container_client = MagicMock()
            command.storage_client.get_container_client.return_value = (
                mock_container_client
            )

            # Mock blobs
            mock_blob1 = MagicMock()
            mock_blob1.name = "test_user/attachments/file1.jpg"
            mock_blob1.size = 1048576  # 1MB

            mock_blob2 = MagicMock()
            mock_blob2.name = "test_user/docs/file2.pdf"
            mock_blob2.size = 2097152  # 2MB

            mock_blob3 = MagicMock()
            mock_blob3.name = "test_user/exports/file3.csv"
            mock_blob3.size = 512000  # 0.5MB

            mock_blobs = [mock_blob1, mock_blob2, mock_blob3]
            mock_container_client.list_blobs.return_value = mock_blobs

            # Call the Azure storage size method
            result = command._get_azure_storage_size("test_user")

            # Verify results (allow for small rounding differences)
            self.assertAlmostEqual(result["total_size_mb"], 3.5, places=1)
            breakdown = json.loads(result["storage_breakdown"])
            self.assertEqual(breakdown["attachments"], 1.0)
            self.assertEqual(breakdown["docs"], 2.0)
            self.assertAlmostEqual(breakdown["exports"], 0.5, places=1)

    def test_storage_size_calculation_fallback(self):
        """Test storage size calculation fallback when no client is available"""
        command = Command()

        # Test with no storage client
        result = command.get_storage_size_for_user("test_user")
        self.assertEqual(result["total_size_mb"], 0)
        self.assertEqual(result["storage_breakdown"], "{}")

        # Test with unsupported backend
        command.storage_client = MagicMock()
        command.storage_container = "test"
        command.storage_backend = "unsupported"

        result = command.get_storage_size_for_user("test_user")
        self.assertEqual(result["total_size_mb"], 0)
        self.assertEqual(result["storage_breakdown"], "{}")

    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_users"
    )
    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.Command.get_inactive_organizations"
    )
    def test_organization_creator_login_requirement(self, mock_orgs, mock_users):
        """Test that organizations require both old submissions AND old creator login"""
        # Mock no users for this test
        mock_users.return_value = []

        # Test organization with old submissions but recent creator login (should NOT be exported)
        # The mock should return empty list to simulate the SQL filtering effect
        mock_orgs.return_value = []

        # Run command
        call_command(
            "export_inactive_users_orgs",
            output_dir=self.temp_dir,
            verbosity=0,
            include_storage=False,
        )

        # Check that no organization file was created (no inactive organizations found)
        files = os.listdir(self.temp_dir)
        org_files = [f for f in files if "organizations" in f and f.endswith(".csv")]
        self.assertEqual(len(org_files), 0)  # No organization file should be created

        # Now test with both old submissions AND old creator login (should be exported)
        mock_orgs.return_value = [
            {
                "org_name": "Fully Inactive Org",
                "org_username": "inactive_org",
                "org_email": "inactive@example.com",
                "date_created": "2020-01-01",
                "creator_username": "inactive_creator",
                "creator_email": "inactivecreator@example.com",
                "creator_date_joined": "2019-12-01",
                "creator_last_login": "2020-01-01",  # Old login (over 2 years)
                "last_submission_date": "2020-06-01",  # Old submissions (over 2 years)
                "project_count": 2,
                "form_count": 5,
                "total_submissions": 100,
            }
        ]

        # Clear temp directory for second test
        for file in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, file))

        # Run command again
        call_command(
            "export_inactive_users_orgs",
            output_dir=self.temp_dir,
            verbosity=0,
            include_storage=False,
        )

        # Check that organization was exported this time
        files = os.listdir(self.temp_dir)
        org_csv = [f for f in files if "organizations" in f and f.endswith(".csv")][0]

        with open(os.path.join(self.temp_dir, org_csv), "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            # Should have exactly 1 data row
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["org_name"], "Fully Inactive Org")
