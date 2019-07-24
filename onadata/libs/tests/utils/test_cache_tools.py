# -*- coding: utf-8 -*-
"""
Test onadata.libs.utils.cache_tools module.
"""
from unittest import TestCase

from onadata.libs.utils.cache_tools import safe_key


class TestCacheTools(TestCase):
    """Test onadata.libs.utils.cache_tools module class"""

    def test_safe_key(self):
        """Test safe_key() function returns a hashed key"""
        self.assertEqual(
            safe_key("hello world"),
            "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9")
