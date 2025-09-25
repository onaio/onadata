# -*- coding: utf-8 -*-
"""
Inactive Export Tracker for exported inactive users and organizations.
"""

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path


class InactiveExportTracker:
    """Tracker specifically for inactive users and organizations exports"""

    def __init__(self, session_id=None):
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.tracking_file = self._get_or_create_tracking_file()
        self.data = self._load_data()

    def get_tracking_file_path(self, session_id):
        """Get the tracking file path for inactive exports session"""
        temp_dir = tempfile.gettempdir()
        return os.path.join(temp_dir, f"inactive_export_tracking_{session_id}.json")

    def _get_or_create_tracking_file(self):
        """Get existing or create new tracking file for inactive exports"""
        file_path = self.get_tracking_file_path(self.session_id)
        if not os.path.exists(file_path):
            # Create new file with initial structure for inactive exports
            initial_data = {
                "session_id": self.session_id,
                "export_type": "inactive_users_orgs",
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "inactive_records": {"user": [], "organization": []},
                "summary": {
                    "total_inactive_users": 0,
                    "total_inactive_orgs": 0,
                    "export_completed": False,
                },
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, indent=2)
        return file_path

    def _load_data(self):
        """Load data from tracking file"""
        try:
            with open(self.tracking_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Return default structure if file doesn't exist or is corrupted
            return {
                "session_id": self.session_id,
                "export_type": "inactive_users_orgs",
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "inactive_records": {"user": [], "organization": []},
                "summary": {
                    "total_inactive_users": 0,
                    "total_inactive_orgs": 0,
                    "export_completed": False,
                },
            }

    def _save_data(self):
        """Save data to tracking file"""
        self.data["last_updated"] = datetime.now().isoformat()
        with open(self.tracking_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def add_inactive_record(self, export_type, record_id, username, years_threshold):
        """Add an inactive user/org export record"""
        record = {
            "record_id": record_id,
            "username": username,
            "exported_at": datetime.now().isoformat(),
            "years_threshold": years_threshold,
        }

        # Add to appropriate list
        self.data["inactive_records"][export_type].append(record)

        # Update summary
        if export_type == "user":
            self.data["summary"]["total_inactive_users"] += 1
        elif export_type == "organization":
            self.data["summary"]["total_inactive_orgs"] += 1

        self._save_data()

    def get_exported_inactive_usernames(self, export_type):
        """Get list of already exported inactive usernames"""
        records = self.data.get("inactive_records", {}).get(export_type, [])
        return [record["username"] for record in records]

    @staticmethod
    def get_inactive_session_stats(session_id):
        """Get statistics for an inactive export session"""
        tracker = InactiveExportTracker(session_id)
        file_path = tracker.get_tracking_file_path(session_id)

        if not os.path.exists(file_path):
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            stats = {}
            for export_type, records in data.get("inactive_records", {}).items():
                if records:  # Only include if there are records
                    latest_export = max(records, key=lambda x: x.get("exported_at", ""))
                    stats[export_type] = {
                        "count": len(records),
                        "latest": latest_export.get("exported_at"),
                    }

            return stats
        except (json.JSONDecodeError, KeyError):
            return None

    @staticmethod
    def cleanup_old_inactive_sessions(days_old=30):
        """Clean up old inactive export tracking files"""
        temp_dir = tempfile.gettempdir()
        cutoff_date = datetime.now() - timedelta(days=days_old)
        deleted_count = 0

        # Find all inactive export tracking files
        for file_path in Path(temp_dir).glob("inactive_export_tracking_*.json"):
            try:
                # Get file modification time
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_mtime < cutoff_date:
                    file_path.unlink()  # Delete the file
                    deleted_count += 1
            except (OSError, ValueError):
                # Skip files that can't be processed
                continue

        return deleted_count

    def mark_export_completed(self):
        """Mark the export session as completed"""
        self.data["summary"]["export_completed"] = True
        self._save_data()

    def get_summary(self):
        """Get export summary statistics"""
        return self.data.get("summary", {})
