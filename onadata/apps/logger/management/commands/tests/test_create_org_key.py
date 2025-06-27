"""Tests for management command create_org_key"""

from io import StringIO
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command

from onadata.apps.api.models import OrganizationProfile
from onadata.apps.logger.models import KMSKey
from onadata.apps.main.tests.test_base import TestBase

User = get_user_model()


class CreateOrgKeyTestCase(TestBase):
    """Tests for management command create_org_key"""

    def setUp(self):
        super().setUp()
        self.out = StringIO()

        # Create test organizations
        self.org1 = self._create_organization(
            username="testorg1", name="Test Org 1", created_by=self.user
        )
        self.org2 = self._create_organization(
            username="testorg2", name="Test Org 2", created_by=self.user
        )
        self.org3 = self._create_organization(
            username="testorg3", name="Test Org 3", created_by=self.user
        )

    @patch("onadata.apps.logger.management.commands.create_org_key.create_key")
    def test_create_key_for_specific_usernames(self, mock_create_key):
        """Create keys for specific organization usernames"""
        mock_key = Mock()
        mock_key.key_id = "test-key-123"
        mock_create_key.return_value = mock_key

        call_command(
            "create_org_key", "--usernames", "testorg1", "testorg2", stdout=self.out
        )

        output = self.out.getvalue()
        self.assertIn("Processing 2 organizations: testorg1, testorg2", output)
        self.assertIn("Created key test-key-123 for organization: testorg1", output)
        self.assertIn("Created key test-key-123 for organization: testorg2", output)
        self.assertIn("Created: 2", output)
        self.assertIn("Skipped: 0", output)
        self.assertIn("Errors: 0", output)

        # Verify create_key was called for both organizations
        self.assertEqual(mock_create_key.call_count, 2)
        mock_create_key.assert_any_call(self.org1, created_by=None)
        mock_create_key.assert_any_call(self.org2, created_by=None)

    @patch("onadata.apps.logger.management.commands.create_org_key.create_key")
    def test_create_key_for_all_organizations(self, mock_create_key):
        """Create keys for all organizations"""
        mock_key = Mock()
        mock_key.key_id = "test-key-123"
        mock_create_key.return_value = mock_key

        call_command("create_org_key", "--all", stdout=self.out)

        output = self.out.getvalue()
        self.assertIn("Processing all 3 organizations", output)
        self.assertIn("Created: 3", output)
        self.assertIn("Skipped: 0", output)
        self.assertIn("Errors: 0", output)

        # Verify create_key was called for all organizations
        self.assertEqual(mock_create_key.call_count, 3)

    @patch("onadata.apps.logger.management.commands.create_org_key.create_key")
    def test_skip_organizations_with_active_keys(self, mock_create_key):
        """Skip organizations that already have active keys"""
        # Create an active key for org1
        content_type = ContentType.objects.get_for_model(OrganizationProfile)
        KMSKey.objects.create(
            key_id="existing-key",
            description="Existing Key",
            public_key="fake-pub-key",
            content_type=content_type,
            object_id=self.org1.pk,
            is_active=True,
            provider=KMSKey.KMSProvider.AWS,
        )

        mock_key = Mock()
        mock_key.key_id = "test-key-123"
        mock_create_key.return_value = mock_key

        call_command(
            "create_org_key", "--usernames", "testorg1", "testorg2", stdout=self.out
        )

        output = self.out.getvalue()
        self.assertIn("Skipping testorg1 - already has active key", output)
        self.assertIn("Created key test-key-123 for organization: testorg2", output)
        self.assertIn("Created: 1", output)
        self.assertIn("Skipped: 1", output)
        self.assertIn("Errors: 0", output)

        # Verify create_key was only called for org2
        mock_create_key.assert_called_once_with(self.org2, created_by=None)

    @patch("onadata.apps.logger.management.commands.create_org_key.create_key")
    def test_dry_run_mode(self, mock_create_key):
        """Dry run mode shows what would be done without creating keys"""
        call_command(
            "create_org_key",
            "--usernames",
            "testorg1",
            "testorg2",
            "--dry-run",
            stdout=self.out,
        )

        output = self.out.getvalue()
        self.assertIn("DRY RUN MODE - No keys will be created", output)
        self.assertIn("Would create key for organization: testorg1", output)
        self.assertIn("Would create key for organization: testorg2", output)
        self.assertIn("Created: 2", output)
        self.assertIn("Skipped: 0", output)
        self.assertIn("Errors: 0", output)

        # Verify create_key was not called
        mock_create_key.assert_not_called()

    @patch("onadata.apps.logger.management.commands.create_org_key.create_key")
    def test_error_handling(self, mock_create_key):
        """Handle errors when creating keys"""
        mock_create_key.side_effect = Exception("KMS error")

        call_command(
            "create_org_key", "--usernames", "testorg1", "testorg2", stdout=self.out
        )

        output = self.out.getvalue()
        self.assertIn("Error creating key for testorg1: KMS error", output)
        self.assertIn("Error creating key for testorg2: KMS error", output)
        self.assertIn("Created: 0", output)
        self.assertIn("Skipped: 0", output)
        self.assertIn("Errors: 2", output)

    def test_no_arguments_error(self):
        """Error when no arguments are provided"""
        call_command("create_org_key", stdout=self.out)

        output = self.out.getvalue()
        self.assertIn("Please specify either --usernames or --all", output)

    def test_both_arguments_error(self):
        """Error when both --usernames and --all are provided"""
        call_command(
            "create_org_key", "--usernames", "testorg1", "--all", stdout=self.out
        )

        output = self.out.getvalue()
        self.assertIn("Please specify either --usernames or --all, not both", output)

    def test_nonexistent_username(self):
        """Handle nonexistent usernames gracefully"""
        call_command("create_org_key", "--usernames", "nonexistent", stdout=self.out)

        output = self.out.getvalue()
        self.assertIn("Processing 0 organizations: nonexistent", output)
        self.assertIn("Created: 0", output)
        self.assertIn("Skipped: 0", output)
        self.assertIn("Errors: 0", output)

    @patch("onadata.apps.logger.management.commands.create_org_key.create_key")
    def test_exclude_deleted_users(self, mock_create_key):
        """Exclude organizations with deleted users"""
        # Create a deleted user
        deleted_user = User.objects.create(
            username="deletedorg-deleted-at-1234567890", is_active=False
        )
        OrganizationProfile.objects.create(
            user=deleted_user,
            name="Deleted Org",
            creator=self.user,
        )
        mock_key = Mock()
        mock_key.key_id = "test-key-123"
        mock_create_key.return_value = mock_key

        call_command("create_org_key", "--all", stdout=self.out)

        output = self.out.getvalue()
        self.assertIn(
            "Processing all 3 organizations", output
        )  # Only the 3 original orgs
        self.assertIn("Created: 3", output)
        self.assertIn("Skipped: 0", output)
        self.assertIn("Errors: 0", output)

        # Verify create_key was only called for active organizations
        self.assertEqual(mock_create_key.call_count, 3)
