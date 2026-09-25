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
# Format suffixes must stay out of the username so DRF's format-suffix
# routes (``users/<username>.json``) split them off. Applied to every
# alternative that can end in letters, including email usernames.
_NOT_FORMAT_SUFFIX = (
    r"(?<!\.json)(?<!\.xml)(?<!\.csv)(?<!\.jsonp)" + r"(?<!\.yaml)(?<!\.html)(?<!\.api)"
)
USERNAME_LOOKUP_REGEX = (
    r"(?:[\w.-]+"
    + _NOT_FORMAT_SUFFIX
    + r")"
    + r"|\+?[\d.\-]+"
    + r"|(?:[\w.%+-]+@[\w.-]+\.[a-zA-Z]{2,}"
    + _NOT_FORMAT_SUFFIX
    + r")"
)

# Username validation regex for form/serializer validation
# Blocks: usernames ending in .json, .csv, .xls, .xlsx, .kml
# Note: Uses ^ and $ anchors since we use fullmatch()
# Note: \w in Python 3 matches Unicode word characters (letters, digits, underscore)
USERNAME_VALIDATION_REGEX = (
    r"^(?!.*\.(?:json|csv|xls|xlsx|kml)$)"
    r"(?:[\w.-]+|\+?[\d.\-]+|[\w.%+-]+@[\w.-]+\.[a-zA-Z]{2,})$"
)
