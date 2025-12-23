# -*- coding: utf-8 -*-
"""
API constants module.
"""

# Username lookup regex pattern for URL routing in viewsets
# Allows: alphanumeric, dots, hyphens, underscores, emails, and phone numbers
# Note: No ^ or $ anchors as Django URL routing provides boundaries
# Note: No negative lookahead needed - DRF's format suffix will handle
USERNAME_LOOKUP_REGEX = (
    r"[a-zA-Z0-9._-]+|\+?[\d.\-]+|[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
)

# Username validation regex for form/serializer validation
# Blocks: usernames ending in .json, .csv, .xls, .xlsx, .kml
# Note: Uses ^ and $ anchors since we use fullmatch()
USERNAME_VALIDATION_REGEX = (
    r"^(?!.*\.(?:json|csv|xls|xlsx|kml)$)"
    r"(?:[a-zA-Z0-9._-]+|\+?[\d.\-]+|[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})$"
)
