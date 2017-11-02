# -*- coding=utf-8 -*-
"""
Test floip module."
"""
from unittest import TestCase

from onadata.libs.floip import floip_to_markdown


class TestFloip(TestCase):
    """
    Test floip module functions.
    """

    def test_floip_to_markdown(self):
        """
        Test converting a floip questioon to xlsform markdown.
        """
        floip_question = {
            "type": "multiple_choice",
            "label": "Are you male or female?",
            "type_options": {
                "choices": ["male", "female", "not identified"]
            }
        }
        name = "ae54d3"
        question = floip_to_markdown(name, floip_question)
        self.assertEqual(question,
                         'ae54d3 | select_one | Are you male or female?')
