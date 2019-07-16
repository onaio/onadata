# -*- coding: utf-8 -*-
"""
Test onadata.libs.utils.cache_tools module.
"""
from unittest import TestCase

from onadata.libs.utils.cache_tools import safe_key


class TestCacheTools(TestCase):
    """Test onadata.libs.utils.cache_tools module class"""

    def test_safe_key(self):
        """Test safe_key() functions returns a valid key"""
        self.assertEqual(safe_key("hello_world"), "hello_world")
        self.assertEqual(safe_key("hello world"), "hello-world")
        self.assertEqual(safe_key("hello@world"), "hello@world")
