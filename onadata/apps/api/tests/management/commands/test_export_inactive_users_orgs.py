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
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test.utils import override_settings
from django.utils import timezone

from onadata.apps.api.management.commands.export_inactive_users_orgs import (
    Command,
    calculate_azure_storage_size,
)
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.inactive_export_tracker import InactiveExportTracker

User = get_user_model()


class TestExportInactiveUsersOrgs(TestBase):
    """Test export_inactive_users_orgs management command"""

    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.temp_dir = tempfile.mkdtemp()

        # Create timestamps for inactive users/orgs (2+ years old)
        two_years_ago = timezone.now() - timedelta(days=750)  # A bit over 2 years
        one_year_ago = timezone.now() - timedelta(days=365)  # Active threshold

        # Create inactive user with old last_login
        inactive_user = self._create_user(
            "inactive_user", "password", create_profile=True
        )
        inactive_user.last_login = two_years_ago
        inactive_user.date_joined = two_years_ago
        inactive_user.first_name = "Inactive"
        inactive_user.last_name = "User"
        inactive_user.email = "inactive@example.com"
        inactive_user.save()

        # Create inactive organization with old submission date and creator login
        inactive_org_creator = self._create_user(
            "inactive_org_creator", "password", create_profile=True
        )
        inactive_org_creator.date_joined = two_years_ago
        inactive_org_creator.last_login = two_years_ago
        inactive_org_creator.save()

        _inactive_org = self._create_organization(
            "inactive_org", "Inactive Organization", inactive_org_creator
        )

        # Create organization with old submissions but recent creator login
        # (should NOT be exported)
        recent_creator = self._create_user(
            "recent_creator", "password", create_profile=True
        )
        recent_creator.date_joined = two_years_ago
        recent_creator.last_login = one_year_ago  # Recent login
        recent_creator.save()

        _org_recent_creator = self._create_organization(
            "org_recent_creator", "Org with Recent Creator", recent_creator
        )

        # Create organization with recent submissions but old creator login
        # (should NOT be exported)
        # Note: We can't easily create submissions in setUp,
        #       so this tests the creator login requirement
        old_creator_no_submissions = self._create_user(
            "old_creator_no_subs", "password", create_profile=True
        )

        old_creator_no_submissions.date_joined = two_years_ago
        old_creator_no_submissions.last_login = two_years_ago  # Old login
        old_creator_no_submissions.save()

        _org_old_creator_no_subs = self._create_organization(
            "org_old_creator_no_subs",
            "Org Old Creator No Submissions",
            old_creator_no_submissions,
        )

        # Create active user (for contrast)
        active_user = self._create_user("active_user", "password", create_profile=True)
        active_user.last_login = one_year_ago  # Recent enough to be active
        active_user.date_joined = one_year_ago
        active_user.first_name = "Active"
        active_user.last_name = "User"
        active_user.email = "active@example.com"
        active_user.save()

        # Create user inactive for 2.5 years (for testing custom years parameter)
        two_and_half_years_ago = timezone.now() - timedelta(days=912)  # ~2.5 years
        user_2_5_years = self._create_user(
            "user_2_5_years", "password", create_profile=True
        )
        user_2_5_years.last_login = two_and_half_years_ago
        user_2_5_years.date_joined = two_and_half_years_ago
        user_2_5_years.first_name = "TwoHalf"
        user_2_5_years.last_name = "Years"
        user_2_5_years.email = "twohalf@example.com"
        user_2_5_years.save()

        # Create user inactive for 3.5 years (for testing custom years parameter)
        three_and_half_years_ago = timezone.now() - timedelta(days=1277)  # ~3.5 years
        user_3_5_years = self._create_user(
            "user_3_5_years", "password", create_profile=True
        )
        user_3_5_years.last_login = three_and_half_years_ago
        user_3_5_years.date_joined = three_and_half_years_ago
        user_3_5_years.first_name = "ThreeHalf"
        user_3_5_years.last_name = "Years"
        user_3_5_years.email = "threehalf@example.com"
        user_3_5_years.save()

    def tearDown(self):
        """Clean up test files"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_csv_export_creates_files(self):
        """Test that CSV export creates output files"""
        # Run command - will use real tespappappapt data created in setUp
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

        # Verify CSV files contain expected data
        user_csv = [f for f in csv_files if "users" in f.lower()]
        with open(os.path.join(self.temp_dir, user_csv[0]), "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            usernames = [row.get("username", "") for row in rows]
            # Should contain inactive_user but not active_user
            self.assertIn("inactive_user", usernames)
            self.assertNotIn("active_user", usernames)

    def test_command_with_custom_years(self):
        """Test command with custom years parameter"""
        # Run command with years=3 parameter
        call_command(
            "export_inactive_users_orgs",
            years=3,
            output_dir=self.temp_dir,
            verbosity=0,
            include_storage=False,
        )

        # Check if user CSV files were created
        files = os.listdir(self.temp_dir)
        user_csv = [f for f in files if "users" in f and f.endswith(".csv")]

        # Should have at least one CSV file
        self.assertGreater(len(user_csv), 0, "Should create user CSV file")

        # Parse the CSV to verify which users were exported with 3-year threshold
        with open(os.path.join(self.temp_dir, user_csv[0]), "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            exported_users = list(reader)
            exported_usernames = [row["username"] for row in exported_users]

            # With years=3, only users inactive for 3+ years should be exported
            # NOTE: Our test setup has inactive_user at 750 days (~2.05 years)
            # So with years=3, it should NOT be exported
            self.assertNotIn(
                "inactive_user",
                exported_usernames,
                "User with ~2 years inactivity should NOT be exported with years=3",
            )

            self.assertNotIn(
                "user_2_5_years",
                exported_usernames,
                "User with 2.5 years inactivity should NOT be exported with years=3",
            )

            self.assertIn(
                "user_3_5_years",
                exported_usernames,
                "User with 3.5 years inactivity SHOULD be exported with years=3",
            )

            self.assertNotIn(
                "active_user", exported_usernames, "Active user should NOT be exported"
            )

    def test_csv_file_format(self):
        """Test that CSV files have correct format and headers"""
        # Run command - will use real test data created in setUp
        call_command(
            "export_inactive_users_orgs",
            output_dir=self.temp_dir,
            verbosity=0,
            include_storage=False,
        )

        # Find and check CSV files exist
        files = os.listdir(self.temp_dir)
        csv_files = [f for f in files if f.endswith(".csv")]

        # Check user CSV headers if exists
        user_csv = [f for f in csv_files if "users" in f.lower()]
        if user_csv:
            with open(
                os.path.join(self.temp_dir, user_csv[0]), "r", encoding="utf-8"
            ) as f:
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

        # Check organization CSV headers if exists
        org_csv = [f for f in csv_files if "organizations" in f.lower()]
        if org_csv:
            with open(
                os.path.join(self.temp_dir, org_csv[0]), "r", encoding="utf-8"
            ) as f:
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

    def test_date_formatting(self):
        """Test that date formatting works correctly"""
        # Run command with real test data - will use dates from setUp
        call_command(
            "export_inactive_users_orgs",
            output_dir=self.temp_dir,
            verbosity=0,
            include_storage=False,
        )

        # Check that dates were formatted properly in CSV
        files = os.listdir(self.temp_dir)
        csv_files = [f for f in files if f.endswith(".csv")]

        if csv_files:
            user_csv = [f for f in csv_files if "users" in f]
            if user_csv:
                with open(
                    os.path.join(self.temp_dir, user_csv[0]), "r", encoding="utf-8"
                ) as f:
                    content = f.read()
                    # Check that dates are properly formatted (YYYY-MM-DD format)
                    date_pattern = r"\d{4}-\d{2}-\d{2}"
                    self.assertRegex(
                        content, date_pattern, "Should contain properly formatted dates"
                    )

    @patch(
        "onadata.apps.api.management.commands.export_inactive_users_orgs.boto3.client"
    )
    @override_settings(
        AWS_ACCESS_KEY_ID="fake-id",
        AWS_SECRET_ACCESS_KEY="fake-secret",  # nosec
        AWS_STORAGE_BUCKET_NAME="test_bucket",
        AWS_S3_REGION_NAME="us-east-1",
        STORAGES={
            "default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"}
        }
    )
    def test_storage_size_calculation(self, mock_boto3_client):
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

        # Run command with storage calculation enabled
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
            self.assertEqual(row["username"], "inactive_user")
            # Total: 1MB + 2MB + 0.5MB = 3.5MB (allow small rounding difference)
            self.assertAlmostEqual(float(row["storage_size_mb"]), 3.5, places=1)
            # Check storage breakdown JSON
            breakdown = json.loads(row["storage_breakdown"])
            self.assertEqual(breakdown["attachments"], 1.0)
            self.assertEqual(breakdown["docs"], 2.0)
            self.assertAlmostEqual(breakdown["exports"], 0.5, places=1)

    def test_include_storage_option(self):
        """Test that include-storage option works correctly"""

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

    def test_limit_functionality(self):
        """Test that limit parameter works correctly"""
        # First create additional test users to have more than the limit
        two_years_ago = timezone.now() - timedelta(days=750)
        for i in range(5):
            extra_user = self._create_user(
                f"extra_inactive_{i}", "password", create_profile=True
            )
            extra_user.last_login = two_years_ago
            extra_user.date_joined = two_years_ago
            extra_user.save()

        # Run command with limit
        call_command(
            "export_inactive_users_orgs",
            output_dir=self.temp_dir,
            verbosity=0,
            include_storage=False,
            limit=3,  # Limit to 3 records each
        )

        # Check that files respect the limit
        files = os.listdir(self.temp_dir)
        user_csv = [f for f in files if "users" in f and f.endswith(".csv")]

        if user_csv:
            with open(
                os.path.join(self.temp_dir, user_csv[0]), "r", encoding="utf-8"
            ) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                # Should have exactly 3 records due to limit
                self.assertEqual(
                    len(rows), 3, "Limit should restrict number of records to exactly 3"
                )

    def test_tracking_functionality(self):
        """Test that tracking functionality works correctly"""
        # Create unique session ID to avoid test interference
        unique_session = f"test_session_{uuid.uuid4().hex[:8]}"

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

        # Check user tracking - should have exported users from real test data
        user_usernames = tracker.get_exported_inactive_usernames("user")
        self.assertGreater(len(user_usernames), 0)
        self.assertIn("inactive_user", user_usernames)

        # Check organization tracking - should have at least one organization
        org_usernames = tracker.get_exported_inactive_usernames("organization")
        self.assertGreater(len(org_usernames), 0)

    def test_resume_session_functionality(self):
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

        # Resume the session - will use real test data from setUp
        call_command(
            "export_inactive_users_orgs",
            output_dir=self.temp_dir,
            verbosity=0,
            include_storage=False,
            resume_session=unique_session,
        )

        # Verify that tracking was maintained
        tracker = InactiveExportTracker(unique_session)
        user_usernames = tracker.get_exported_inactive_usernames("user")
        # Should still have at least the original tracked user
        self.assertIn("already_exported_user", user_usernames)

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
        # Mock Azure storage client
        mock_storage_client = MagicMock()
        mock_container_client = MagicMock()
        mock_storage_client.get_container_client.return_value = mock_container_client

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

        # Test the standalone function directly
        result = calculate_azure_storage_size(
            mock_storage_client, "test-container", "test_user"
        )

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

    def test_organization_creator_login_requirement(self):
        """Test that organizations require both old submissions AND old creator login"""
        call_command(
            "export_inactive_users_orgs",
            output_dir=self.temp_dir,
            verbosity=0,
            include_storage=False,
        )

        # Check if organization files were created
        files = os.listdir(self.temp_dir)
        org_files = [f for f in files if "organizations" in f and f.endswith(".csv")]

        # Parse the CSV to verify which organizations were exported
        with open(
            os.path.join(self.temp_dir, org_files[0]), "r", encoding="utf-8"
        ) as f:
            reader = csv.DictReader(f)
            exported_orgs = list(reader)
            exported_usernames = [row["org_username"] for row in exported_orgs]

            # Verify that organizations with old creator login are exported
            expected_exported = ["inactive_org", "org_old_creator_no_subs"]
            for expected_org in expected_exported:
                self.assertIn(
                    expected_org,
                    exported_usernames,
                )

            # Verify that organization with recent creator login is NOT exported
            self.assertNotIn(
                "org_recent_creator",
                exported_usernames,
                "Organization with recent creator login should NOT be exported",
            )

            # Verify we have at least the expected number of organizations
            self.assertGreaterEqual(
                len(exported_orgs),
                2,
                "Should export at least 2 organizations with old creator logins",
            )
