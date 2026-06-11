# -*- coding: utf-8 -*-
"""
API constants module.
"""

# Username lookup regex pattern for URL routing in viewsets
# Allows: alphanumeric (including Unicode), dots, hyphens, underscores,
# emails, and phone numbers
# Excludes format suffixes (.json, .xml, etc.)
# DRF's format_suffix_patterns will handle them
# Note: No ^ or $ anchors as Django URL routing provides boundaries
# Note: \w in Python 3 matches Unicode word characters (letters, digits, underscore)
USERNAME_LOOKUP_REGEX = (
    r"(?:[\w.-]+"
    r"(?<!\.json)(?<!\.xml)(?<!\.csv)(?<!\.jsonp)"
    r"(?<!\.yaml)(?<!\.html)(?<!\.api))|"
    r"\+?[\d.\-]+|"
    r"[\w.%+-]+@[\w.-]+\.[a-zA-Z]{2,}"
)

# Username validation regex for form/serializer validation
# Blocks: usernames ending in .json, .csv, .xls, .xlsx, .kml
# Note: Uses ^ and $ anchors since we use fullmatch()
# Note: \w in Python 3 matches Unicode word characters (letters, digits, underscore)
USERNAME_VALIDATION_REGEX = (
    r"^(?!.*\.(?:json|csv|xls|xlsx|kml)$)"
    r"(?:[\w.-]+|\+?[\d.\-]+|[\w.%+-]+@[\w.-]+\.[a-zA-Z]{2,})$"
)
