# -*- coding: utf-8 -*-
"""
API constants module.
"""

# Username lookup regex pattern for URL routing in viewsets
# Allows: alphanumeric, dots, hyphens, underscores, emails, and phone numbers
# Blocks: usernames ending in .json, .csv, .xls, .xlsx, .kml (case-insensitive)
# Note: No ^ or $ anchors as Django URL routing provides boundaries
USERNAME_LOOKUP_REGEX = (
    r"(?!.*\.(?i:json|csv|xls|xlsx|kml)$)"
    r"(?:[a-zA-Z0-9._-]+|\+?[\d.\-]+|[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"
)
