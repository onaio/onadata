# -*- coding: utf-8 -*-
"""
Management command to export inactive users and organizations
"""

import csv
import json
import os
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.files.storage import storages
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone
from django.utils.translation import gettext as _

from onadata.libs.utils.inactive_export_tracker import InactiveExportTracker


class Command(BaseCommand):
    """Export inactive users and organizations (2+ years of inactivity)"""

    help = _("Export inactive users and organizations to CSV files")

    def add_arguments(self, parser):
        parser.add_argument(
            "--years",
            type=int,
            default=2,
            help=_("Years of inactivity threshold (default: 2)"),
        )
        parser.add_argument(
            "--output-dir",
            type=str,
            default=".",
            help=_("Directory for output CSV files (default: current directory)"),
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help=_("Batch size for streaming results (default: 1000)"),
        )
        parser.add_argument(
            "--include-storage",
            action="store_true",
            help=_("Include storage size calculation (slower but more detailed)"),
        )
        parser.add_argument(
            "--limit",
            type=int,
            help=_("Maximum number of users/organizations to export per run"),
        )
        parser.add_argument(
            "--offset",
            type=int,
            default=0,
            help=_("Starting position for export (default: 0)"),
        )
        parser.add_argument(
            "--track-exports",
            action="store_true",
            help=_("Enable tracking of exported records for incremental exports"),
        )
        parser.add_argument(
            "--export-session",
            type=str,
            help=_("Session identifier for tracking (defaults to timestamp)"),
        )
        parser.add_argument(
            "--resume-session", type=str, help=_("Resume a previous export session")
        )

    def handle(self, *args, **options):
        years = options["years"]
        output_dir = options["output_dir"]
        batch_size = options["batch_size"]
        include_storage = options["include_storage"]
        limit = options.get("limit")
        offset = options.get("offset", 0)
        track_exports = options.get("track_exports", False)
        export_session = options.get("export_session")
        resume_session = options.get("resume_session")

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Handle session management
        if resume_session:
            self.session_id = resume_session
            track_exports = True  # Always track when resuming
            if self.verbosity >= 1:
                self.stdout.write(
                    _("Resuming export session: {}").format(self.session_id)
                )

            # Get session stats
            stats = InactiveExportTracker.get_inactive_session_stats(self.session_id)
            if stats:
                for export_type, stat in stats.items():
                    self.stdout.write(
                        _("  - {}: {} records already exported").format(
                            export_type, stat["count"]
                        )
                    )
        elif track_exports:
            if export_session:
                self.session_id = export_session
            else:
                self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            if self.verbosity >= 1:
                self.stdout.write(
                    _("Starting tracked export session: {}").format(self.session_id)
                )
        else:
            self.session_id = None

        # Store tracking options for use in export methods
        self.track_exports = track_exports
        self.years_threshold = years

        # Initialize tracker if tracking is enabled
        self.tracker = (
            InactiveExportTracker(self.session_id) if self.track_exports else None
        )

        if self.verbosity >= 1:
            message = _(
                "Exporting inactive users and organizations (inactive for {}+ years)..."
            ).format(years)
            if limit:
                message += _(" (limit: {} records per type)").format(limit)
            if offset:
                message += _(" (starting at offset: {})").format(offset)
            self.stdout.write(message)

        # Initialize storage client if storage calculation is enabled
        if include_storage:
            self._init_storage_client()

        # Export inactive organizations
        org_count = self.export_inactive_organizations(
            years, output_dir, batch_size, include_storage, limit, offset
        )

        # Export inactive users
        user_count = self.export_inactive_users(
            years, output_dir, batch_size, include_storage, limit, offset
        )

        if self.verbosity >= 1:
            success_msg = _("Export completed to {}:\n").format(output_dir)
            success_msg += _("  - {} inactive organizations\n").format(org_count)
            success_msg += _("  - {} inactive users").format(user_count)

            if self.session_id and self.track_exports:
                success_msg += _("\n  - Session ID: {}").format(self.session_id)
                if limit:
                    success_msg += _(
                        "\n  - Use --resume-session {} to continue"
                    ).format(self.session_id)

            self.stdout.write(self.style.SUCCESS(success_msg))

    def get_inactive_organizations(self, years=2, limit=None, offset=0):
        """Get inactive organizations using SQL query for performance"""

        # Build exclusion list if tracking is enabled
        excluded_usernames = []
        if self.track_exports and self.tracker:
            excluded_usernames = self.tracker.get_exported_inactive_usernames(
                "organization"
            )

        query = """
        WITH org_activity AS (
            SELECT
                o.userprofile_ptr_id,
                up.name as org_name,
                org_user.username as org_username,
                o.email as org_email,
                org_user.date_joined as date_created,
                creator.username as creator_username,
                creator.email as creator_email,
                creator.date_joined as creator_date_joined,
                creator.last_login as creator_last_login,
                MAX(xf.last_submission_time) as last_submission_date,
                COUNT(DISTINCT p.id) as project_count,
                COUNT(DISTINCT xf.id) as form_count,
                COALESCE(SUM(xf.num_of_submissions), 0) as total_submissions
            FROM api_organizationprofile o
            INNER JOIN main_userprofile up ON o.userprofile_ptr_id = up.id
            INNER JOIN auth_user org_user ON up.user_id = org_user.id
            INNER JOIN auth_user creator ON o.creator_id = creator.id
            LEFT JOIN logger_project p ON p.organization_id = org_user.id
                AND p.deleted_at IS NULL
            LEFT JOIN logger_xform xf ON xf.project_id = p.id
                AND xf.deleted_at IS NULL
            WHERE org_user.is_active = true
            GROUP BY o.userprofile_ptr_id, up.name, org_user.username, o.email,
                     org_user.date_joined, creator.username, creator.email,
                     creator.date_joined, creator.last_login
        )
        SELECT * FROM org_activity
        WHERE (last_submission_date < %s
           OR last_submission_date IS NULL)
          AND (creator_last_login < %s
           OR creator_last_login IS NULL)"""

        # Add exclusion clause if needed
        if excluded_usernames:
            query += """
           AND org_username NOT IN %s"""

        query += """
        ORDER BY last_submission_date DESC NULLS LAST"""

        # Add LIMIT and OFFSET if specified
        if limit:
            query += f"""
        LIMIT {limit}"""
        if offset:
            query += f"""
        OFFSET {offset}"""

        threshold_date = timezone.now() - timedelta(days=years * 365)

        with connection.cursor() as cursor:
            params = [threshold_date, threshold_date]
            if excluded_usernames:
                params.append(tuple(excluded_usernames))
            cursor.execute(query, params)
            columns = [col[0] for col in cursor.description]
            results = []

            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))

        return results

    def get_inactive_users(self, years=2, limit=None, offset=0):
        """Get inactive users using SQL query for performance"""

        # Build exclusion list if tracking is enabled
        excluded_usernames = []
        if self.track_exports and self.tracker:
            excluded_usernames = self.tracker.get_exported_inactive_usernames("user")

        query = """
        SELECT
            u.id,
            u.username,
            u.email,
            u.first_name,
            u.last_name,
            u.last_login,
            u.date_joined,
            u.is_active,
            up.name as profile_name,
            up.organization,
            COALESCE(up.num_of_submissions, 0) as num_of_submissions
        FROM auth_user u
        LEFT JOIN main_userprofile up ON up.user_id = u.id
        LEFT JOIN api_organizationprofile op ON op.userprofile_ptr_id = up.id
        WHERE op.userprofile_ptr_id IS NULL  -- Exclude organization accounts
          AND u.is_active = true
          AND (u.last_login < %s OR u.last_login IS NULL)"""

        # Add exclusion clause if needed
        if excluded_usernames:
            query += """
          AND u.username NOT IN %s"""

        query += """
        ORDER BY u.last_login DESC NULLS LAST"""

        # Add LIMIT and OFFSET if specified
        if limit:
            query += f"""
        LIMIT {limit}"""
        if offset:
            query += f"""
        OFFSET {offset}"""

        threshold_date = timezone.now() - timedelta(days=years * 365)

        with connection.cursor() as cursor:
            params = [threshold_date]
            if excluded_usernames:
                params.append(tuple(excluded_usernames))
            cursor.execute(query, params)
            columns = [col[0] for col in cursor.description]
            results = []

            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))

        return results

    def export_inactive_organizations(
        self, years, output_dir, batch_size, include_storage=False, limit=None, offset=0
    ):
        """Export inactive organizations to CSV"""

        organizations = self.get_inactive_organizations(years, limit, offset)

        if not organizations:
            if self.verbosity >= 1:
                self.stdout.write(_("No inactive organizations found."))
            return 0

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(output_dir, f"inactive_organizations_{timestamp}.csv")

        # Define CSV headers
        headers = [
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

        if include_storage:
            headers.extend(["storage_size_mb", "storage_breakdown"])

        with open(filename, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()

            for org in organizations:
                # Format dates for CSV
                row = {
                    "org_name": org["org_name"],
                    "org_username": org["org_username"],
                    "email": org["org_email"] or "",
                    "domain": self._extract_domain(org["org_email"]),
                    "date_created": self._format_datetime(org["date_created"]),
                    "creator_username": org["creator_username"],
                    "creator_email": org["creator_email"] or "",
                    "creator_domain": self._extract_domain(org["creator_email"]),
                    "creator_date_joined": self._format_datetime(
                        org["creator_date_joined"]
                    ),
                    "creator_last_login": self._format_datetime(
                        org["creator_last_login"]
                    ),
                    "last_submission_date": self._format_datetime(
                        org["last_submission_date"]
                    ),
                    "project_count": org["project_count"] or 0,
                    "form_count": org["form_count"] or 0,
                    "total_submissions": org["total_submissions"] or 0,
                }

                # Add storage information if included
                if include_storage:
                    storage_info = self.get_storage_size_for_user(org["org_username"])
                    row["storage_size_mb"] = storage_info["total_size_mb"]
                    row["storage_breakdown"] = storage_info["storage_breakdown"]

                writer.writerow(row)

                # Track exported record if tracking is enabled
                if self.track_exports and self.tracker:
                    self.tracker.add_inactive_record(
                        export_type="organization",
                        record_id=org.get("userprofile_ptr_id"),
                        username=org["org_username"],
                        years_threshold=self.years_threshold,
                    )

        if self.verbosity >= 1:
            self.stdout.write(
                _("Exported {} inactive organizations to {}").format(
                    len(organizations), filename
                )
            )

        return len(organizations)

    def export_inactive_users(
        self, years, output_dir, batch_size, include_storage=False, limit=None, offset=0
    ):
        """Export inactive users to CSV"""

        users = self.get_inactive_users(years, limit, offset)

        if not users:
            if self.verbosity >= 1:
                self.stdout.write(_("No inactive users found."))
            return 0

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(output_dir, f"inactive_users_{timestamp}.csv")

        # Define CSV headers
        headers = [
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
        ]

        if include_storage:
            headers.extend(["storage_size_mb", "storage_breakdown"])

        with open(filename, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()

            for user in users:
                # Format data for CSV
                first_name = user["first_name"] or ""
                last_name = user["last_name"] or ""
                name = f"{first_name} {last_name}".strip()

                row = {
                    "username": user["username"],
                    "email": user["email"],
                    "domain": self._extract_domain(user["email"]),
                    "first_name": first_name,
                    "last_name": last_name,
                    "name": name,
                    "last_login": self._format_datetime(user["last_login"]),
                    "date_joined": self._format_datetime(user["date_joined"]),
                    "is_active": user["is_active"],
                    "profile_name": user["profile_name"] or "",
                    "organization": user["organization"] or "",
                    "num_of_submissions": user["num_of_submissions"] or 0,
                }

                # Add storage information if included
                if include_storage:
                    storage_info = self.get_storage_size_for_user(user["username"])
                    row["storage_size_mb"] = storage_info["total_size_mb"]
                    row["storage_breakdown"] = storage_info["storage_breakdown"]

                writer.writerow(row)

                # Track exported record if tracking is enabled
                if self.track_exports and self.tracker:
                    self.tracker.add_inactive_record(
                        export_type="user",
                        record_id=user.get("id"),
                        username=user["username"],
                        years_threshold=self.years_threshold,
                    )

        if self.verbosity >= 1:
            self.stdout.write(
                _("Exported {} inactive users to {}").format(len(users), filename)
            )

        return len(users)

    def _init_storage_client(self):
        """Initialize storage client (S3 or Azure) for storage size calculations"""
        # Detect storage backend type
        default_storage = storages["default"]
        self.storage_backend = None
        self.storage_client = None

        try:
            # Check if S3 storage is configured
            s3_class = storages.create_storage(
                {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"}
            )
            if isinstance(default_storage, type(s3_class)):
                self._init_s3_client()
                return
        except (ModuleNotFoundError, ImportError):
            pass

        try:
            # Check if Azure storage is configured
            azure_class = storages.create_storage(
                {"BACKEND": "storages.backends.azure_storage.AzureStorage"}
            )
            if isinstance(default_storage, type(azure_class)):
                self._init_azure_client()
                return
        except (ModuleNotFoundError, ImportError):
            pass

        if self.verbosity >= 1:
            self.stdout.write(
                self.style.WARNING(
                    _("No supported storage backend found, skipping calculation")
                )
            )

    def _init_s3_client(self):
        """Initialize S3 client for storage size calculations"""
        try:
            self.storage_client = boto3.client(
                "s3",
                aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
                aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
                region_name=getattr(settings, "AWS_S3_REGION_NAME", "us-east-1"),
            )
            self.storage_container = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
            if not self.storage_container:
                if self.verbosity >= 1:
                    self.stdout.write(
                        self.style.WARNING(
                            _("S3 Bucket not configured, skipping calculation")
                        )
                    )
                self.storage_client = None
                return
            self.storage_backend = "s3"
        except (BotoCoreError, ClientError) as e:
            if self.verbosity >= 1:
                self.stdout.write(
                    self.style.WARNING(
                        _("Failed to initialize S3 client: {}").format(e)
                    )
                )
            self.storage_client = None

    def _init_azure_client(self):
        """Initialize Azure client for storage size calculations"""
        try:
            # pylint: disable=import-outside-toplevel
            from azure.storage.blob import BlobServiceClient

            account_name = getattr(settings, "AZURE_ACCOUNT_NAME", None)
            account_key = getattr(settings, "AZURE_ACCOUNT_KEY", None)
            container_name = getattr(settings, "AZURE_CONTAINER", None)

            if not all([account_name, account_key, container_name]):
                if self.verbosity >= 1:
                    self.stdout.write(
                        self.style.WARNING(
                            _("Azure storage not configured, skipping calculation")
                        )
                    )
                self.storage_client = None
                return

            connection_string = (
                "DefaultEndpointsProtocol=https;AccountName={};"
                "AccountKey={};EndpointSuffix=core.windows.net"
            ).format(account_name, account_key)
            self.storage_client = BlobServiceClient.from_connection_string(
                connection_string
            )
            self.storage_container = container_name
            self.storage_backend = "azure"

        except (ImportError, Exception) as e:
            if self.verbosity >= 1:
                self.stdout.write(
                    self.style.WARNING(
                        _("Failed to initialize Azure client: {}").format(e)
                    )
                )
            self.storage_client = None

    def get_storage_size_for_user(self, username):
        """Calculate storage size for a user or organization"""
        if not getattr(self, "storage_client", None) or not getattr(
            self, "storage_container", None
        ):
            return {"total_size_mb": 0, "storage_breakdown": "{}"}

        if getattr(self, "storage_backend", None) == "s3":
            return self._get_s3_storage_size(username)
        elif getattr(self, "storage_backend", None) == "azure":
            return self._get_azure_storage_size(username)
        else:
            return {"total_size_mb": 0, "storage_breakdown": "{}"}

    def _get_s3_storage_size(self, username):
        """Calculate storage size for S3 backend"""
        try:
            # List all objects with the username prefix
            paginator = self.storage_client.get_paginator("list_objects_v2")
            page_iterator = paginator.paginate(
                Bucket=self.storage_container, Prefix=f"{username}/"
            )

            total_size = 0
            folder_sizes = {}

            for page in page_iterator:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        size = obj["Size"]
                        total_size += size

                        # Extract top-level folder
                        key_parts = obj["Key"].split("/")
                        if len(key_parts) > 1:
                            # Skip username, get first folder
                            folder = key_parts[1]
                            folder_sizes[folder] = folder_sizes.get(folder, 0) + size

            # Convert to MB and format
            total_size_mb = round(total_size / (1024 * 1024), 2)
            folder_sizes_mb = {
                folder: round(size / (1024 * 1024), 2)
                for folder, size in folder_sizes.items()
            }

            return {
                "total_size_mb": total_size_mb,
                "storage_breakdown": json.dumps(folder_sizes_mb),
            }

        except (BotoCoreError, ClientError) as e:
            if self.verbosity >= 2:
                self.stdout.write(
                    self.style.WARNING(
                        _("Failed to calculate S3 storage for {}: {}").format(
                            username, e
                        )
                    )
                )
            return {"total_size_mb": 0, "storage_breakdown": "{}"}

    def _get_azure_storage_size(self, username):
        """Calculate storage size for Azure backend"""
        AzureError = Exception  # Default fallback
        try:
            # pylint: disable=import-outside-toplevel
            from azure.core.exceptions import AzureError

            container_client = self.storage_client.get_container_client(
                self.storage_container
            )

            total_size = 0
            folder_sizes = {}

            # List blobs with the username prefix
            blobs = container_client.list_blobs(name_starts_with=f"{username}/")

            for blob in blobs:
                size = blob.size or 0
                total_size += size

                # Extract top-level folder
                name_parts = blob.name.split("/")
                if len(name_parts) > 1:
                    # Skip username, get first folder
                    folder = name_parts[1]
                    folder_sizes[folder] = folder_sizes.get(folder, 0) + size

            # Convert to MB and format
            total_size_mb = round(total_size / (1024 * 1024), 2)
            folder_sizes_mb = {
                folder: round(size / (1024 * 1024), 2)
                for folder, size in folder_sizes.items()
            }

            return {
                "total_size_mb": total_size_mb,
                "storage_breakdown": json.dumps(folder_sizes_mb),
            }

        except (AzureError, Exception) as e:
            if self.verbosity >= 2:
                self.stdout.write(
                    self.style.WARNING(
                        _("Failed to calculate Azure storage for {}: {}").format(
                            username, e
                        )
                    )
                )
            return {"total_size_mb": 0, "storage_breakdown": "{}"}

    def _format_datetime(self, dt):
        """Format datetime for CSV output"""
        if dt is None:
            return ""
        if isinstance(dt, str):
            return dt
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def _extract_domain(self, email):
        """Extract domain from email address"""
        if email and "@" in email:
            return email.split("@")[1]
        return ""

    @property
    def verbosity(self):
        """Get verbosity level from options"""
        return getattr(self, "_verbosity", 1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._verbosity = 1
        # Initialize tracking attributes
        self.track_exports = False
        self.session_id = None
        self.years_threshold = 2
