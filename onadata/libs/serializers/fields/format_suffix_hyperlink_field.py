# -*- coding: utf-8 -*-
"""
FormatSuffixHyperlinkedRelatedField serializer field.

This field extends DRF's HyperlinkedRelatedField to properly handle format suffixes
like .json, .csv, etc. in hyperlink URLs before performing lookups.
"""

import re

from rest_framework import serializers


class FormatSuffixHyperlinkedRelatedField(serializers.HyperlinkedRelatedField):
    """
    A HyperlinkedRelatedField that strips format suffixes before lookup.

    This is necessary for usernames or lookup fields that can contain dots,
    which would otherwise be confused with format suffixes like .json, .csv, etc.

    Example:
        Without this field:
            URL: https://api.ona.io/api/v1/users/user@example.com.json
            Extracted username: "user@example.com.json" (incorrect)

        With this field:
            URL: https://api.ona.io/api/v1/users/user@example.com.json
            Extracted username: "user@example.com" (correct)
    """

    # Common format suffixes used in DRF APIs
    FORMAT_SUFFIXES = ["json", "api", "csv", "jsonp", "xml", "yaml", "html"]

    def to_internal_value(self, data):
        """
        Convert a hyperlink to the internal value (object instance).

        Before calling the parent's to_internal_value, we strip any format
        suffixes from the URL path to ensure proper lookup field extraction.
        """
        if data and isinstance(data, str):
            # Strip format suffix from the URL path before lookup
            # Pattern: matches .{format} at the end of the path (before query/fragment)
            # Case-insensitive to handle .json, .JSON, .Json, etc.
            pattern = r"\.(" + "|".join(self.FORMAT_SUFFIXES) + r")(?=[/?#]|$)"
            data = re.sub(pattern, "", data, flags=re.IGNORECASE)

        return super().to_internal_value(data)
