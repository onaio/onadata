# n -*- coding: utf-8 -*-
"""
Test MergedXFormSerializer
"""
import copy

from flaky import flaky
from rest_framework import serializers

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.libs.serializers.merged_xform_serializer import (
    MergedXFormSerializer,
    get_merged_xform_survey,
)
from onadata.libs.utils.user_auth import get_user_default_project

MD = """
| survey |
|        | type              | name  | label |
|        | select one fruits | fruit | Fruit |

| choices |
|         | list name | name   | label  |
|         | fruits    | orange | Orange |
|         | fruits    | mango  | Mango  |
"""

A_MD = """
| survey |
|        | type              | name   | label |
|        | text              | name   | Name  |
|        | select one gender | gender | Sex   |
|        | integer           | age    | Age   |

| choices |
|         | list name | name   | label  |
|         | gender    | female | Female |
|         | gender    | male   | Male   |
"""

B_MD = """
| survey |
|        | type              | name   | label |
|        | text              | name   | Name  |
|        | select one gender | gender | Sex   |

| choices |
|         | list name | name   | label  |
|         | gender    | female | Female |
|         | gender    | male   | Male   |
"""

GROUP_A_MD = """
| survey |
|        | type              | name   | label  |
|        | text              | name   | Name   |
|        | begin group       | info   | Info   |
|        | select one gender | gender | Sex    |
|        | end group         |        |        |
|        | begin group       | other  | Other  |
|        | begin group       | person | Person |
|        | select one gender | gender | Sex    |
|        | end group         |        |        |
|        | end group         |        |        |

| choices |
|         | list name | name   | label  |
|         | gender    | female | Female |
|         | gender    | male   | Male   |
"""

GROUP_B_MD = """
| survey |
|        | type              | name   | label | Relevant   |
|        | text              | name   | Name  |            |
|        | begin group       | info   | Info  |            |
|        | integer           | age    | Age   |            |
|        | select one gender | gender | Sex   | ${age} > 5 |
|        | end group         |        |       |            |
|        | begin group       | other  | Other |            |
|        | begin group       | person | Person |           |
|        | integer           | bage    | Age   |            |
|        | select one gender | gender | Sex   |            |
|        | end group         |        |       |            |
|        | end group         |        |       |            |

| choices |
|         | list name | name   | label  |
|         | gender    | female | Female |
|         | gender    | male   | Male   |
"""

GROUP_C_MD = """
| survey |
|        | type              | name   | label | Relevant   |
|        | text              | name   | Name  |            |
|        | begin group       | info   | Info  |            |
|        | integer           | age    | Age   |            |
|        | select one gender | gender | Sex   | ${age} > 5 |
|        | end group         |        |       |            |
|        | begin group       | other  | Other |            |
|        | begin group       | person | Person |           |
|        | integer           | cage    | Age   |            |
|        | select one gender | gender | Sex   | ${cage} > 5 |
|        | end group         |        |       |            |
|        | end group         |        |       |            |

| choices |
|         | list name | name   | label  |
|         | gender    | female | Female |
|         | gender    | male   | Male   |
"""


class TestMergedXFormSerializer(TestAbstractViewSet):
    """
    Test MergedXFormSerializer
    """

    def setUp(self):
        self.project = None

        super(TestMergedXFormSerializer, self).setUp()

    def test_create_merged_xform(self):
        """Test creating a merged dataset with the MergedXFormSerializer"""
        serializer = MergedXFormSerializer(data={})
        self.assertFalse(serializer.is_valid(raise_exception=False))

        # project is required
        self.assertEqual(serializer.errors["project"], ["This field is required."])

        # name is required
        self.assertEqual(serializer.errors["name"], ["This field is required."])

        # At least 2 *different* xforms
        # 0 xforms
        self.assertEqual(serializer.errors["xforms"], ["This field is required."])

        self.project = get_user_default_project(self.user)
        xform1 = self._publish_markdown(MD, self.user, id_string="a")
        data = {
            "xforms": [],
            "name": "Merged Dataset",
            "project": "http://testserver.com/api/v1/projects/%s" % self.project.pk,
        }
        serializer = MergedXFormSerializer(data=data)
        self.assertFalse(serializer.is_valid(raise_exception=False))
        self.assertNotIn("name", serializer.errors)
        self.assertNotIn("project", serializer.errors)
        self.assertEqual(serializer.errors["xforms"], ["This list may not be empty."])

        # 1 xform
        data["xforms"] = ["http://testserver.com/api/v1/forms/%s" % xform1.pk]
        serializer = MergedXFormSerializer(data=data)
        self.assertFalse(serializer.is_valid(raise_exception=False))
        self.assertIn(
            "This field should have at least two unique xforms.",
            serializer.errors["xforms"],
        )

        # same xform twice
        data["xforms"] = [
            "http://testserver.com/api/v1/forms/%s" % xform1.pk,
            "http://testserver.com/api/v1/forms/%s" % xform1.pk,
        ]
        serializer = MergedXFormSerializer(data=data)
        self.assertFalse(serializer.is_valid(raise_exception=False))
        self.assertIn(
            "This field should have unique xforms", serializer.errors["xforms"]
        )

        # xform with no matching fields
        xform3 = self._publish_markdown(A_MD, self.user, id_string="c")
        data["xforms"] = [
            "http://testserver.com/api/v1/forms/%s" % xform1.pk,
            "http://testserver.com/api/v1/forms/%s" % xform3.pk,
        ]
        serializer = MergedXFormSerializer(data=data)
        self.assertFalse(serializer.is_valid(raise_exception=False))
        self.assertEqual(serializer.errors["xforms"], ["No matching fields in xforms."])

        # two different xforms
        xform2 = self._publish_markdown(MD, self.user, id_string="b")
        data["xforms"] = [
            "http://testserver.com/api/v1/forms/%s" % xform1.pk,
            "http://testserver.com/api/v1/forms/%s" % xform2.pk,
        ]
        serializer = MergedXFormSerializer(data=data)
        self.assertTrue(serializer.is_valid(raise_exception=False))
        self.assertNotIn("xforms", serializer.errors)

    @flaky(max_runs=5)
    def test_get_merged_xform_survey(self):
        """
        Test get_merged_xform_survey()
        """
        with self.assertRaises(serializers.ValidationError):
            get_merged_xform_survey([])

        self.project = get_user_default_project(self.user)
        xform1 = self._publish_markdown(A_MD, self.user, id_string="a")
        xform2 = self._publish_markdown(B_MD, self.user, id_string="b")
        xform3 = self._publish_markdown(MD, self.user, id_string="c")
        expected = {
            "name": "data",
            "title": "data",
            "sms_keyword": "a",
            "default_language": "default",
            "id_string": "a",
            "type": "survey",
            "choices": {
                "gender": [
                    {"name": "female", "label": "Female"},
                    {"name": "male", "label": "Male"},
                ]
            },
            "children": [
                {"name": "name", "label": "Name", "type": "text"},
                {
                    "name": "gender",
                    "label": "Sex",
                    "type": "select one",
                    "itemset": "gender",
                    "list_name": "gender",
                    "children": [
                        {"name": "female", "label": "Female"},
                        {"name": "male", "label": "Male"},
                    ],
                },
                {
                    "name": "meta",
                    "type": "group",
                    "control": {"bodyless": True},
                    "children": [
                        {
                            "name": "instanceID",
                            "type": "calculate",
                            "bind": {"readonly": "true()", "jr:preload": "uid"},
                        }
                    ],
                },
            ],
        }  # yapf: disable

        with self.assertRaises(serializers.ValidationError):
            get_merged_xform_survey([xform1])

        survey = get_merged_xform_survey([xform1, xform2])
        survey_dict = survey.to_json_dict()
        self.assertDictEqual(survey_dict, expected)

        # no matching fields
        with self.assertRaises(serializers.ValidationError):
            survey = get_merged_xform_survey([xform1, xform3])

    def test_group_merged_xform_survey(self):
        """
        Test get_merged_xform_survey() with groups in xforms.
        """
        self.project = get_user_default_project(self.user)
        xform1 = self._publish_markdown(GROUP_A_MD, self.user, id_string="a")
        xform2 = self._publish_markdown(GROUP_B_MD, self.user, id_string="b")
        survey = get_merged_xform_survey([xform1, xform2])
        expected = {
            "name": "data",
            "type": "survey",
            "title": "data",
            "id_string": "a",
            "sms_keyword": "a",
            "default_language": "default",
            "choices": {
                "gender": [
                    {"name": "female", "label": "Female"},
                    {"name": "male", "label": "Male"},
                ]
            },
            "children": [
                {"name": "name", "label": "Name", "type": "text"},
                {
                    "name": "info",
                    "label": "Info",
                    "type": "group",
                    "children": [
                        {
                            "name": "gender",
                            "label": "Sex",
                            "type": "select one",
                            "itemset": "gender",
                            "list_name": "gender",
                            "children": [
                                {"name": "female", "label": "Female"},
                                {"name": "male", "label": "Male"},
                            ],
                        }
                    ],
                },
                {
                    "name": "other",
                    "label": "Other",
                    "type": "group",
                    "children": [
                        {
                            "name": "person",
                            "label": "Person",
                            "type": "group",
                            "children": [
                                {
                                    "name": "gender",
                                    "label": "Sex",
                                    "type": "select one",
                                    "itemset": "gender",
                                    "list_name": "gender",
                                    "children": [
                                        {"name": "female", "label": "Female"},
                                        {"name": "male", "label": "Male"},
                                    ],
                                }
                            ],
                        }
                    ],
                },
                {
                    "name": "meta",
                    "type": "group",
                    "control": {"bodyless": True},
                    "children": [
                        {
                            "name": "instanceID",
                            "type": "calculate",
                            "bind": {"readonly": "true()", "jr:preload": "uid"},
                        }
                    ],
                },
            ],
        }  # yapf: disable
        self.assertEqual(survey.to_json_dict(), expected)

    def test_repeat_merged_xform_survey(self):
        """
        Test get_merged_xform_survey() with repeats in xforms.
        """
        self.project = get_user_default_project(self.user)
        xform1 = self._publish_markdown(
            GROUP_A_MD.replace("group", "repeat"), self.user, id_string="a"
        )
        xform2 = self._publish_markdown(
            GROUP_B_MD.replace("group", "repeat"), self.user, id_string="b"
        )
        survey = get_merged_xform_survey([xform1, xform2])
        expected = {
            "name": "data",
            "type": "survey",
            "title": "data",
            "id_string": "a",
            "sms_keyword": "a",
            "default_language": "default",
            "choices": {
                "gender": [
                    {"name": "female", "label": "Female"},
                    {"name": "male", "label": "Male"},
                ]
            },
            "children": [
                {"name": "name", "label": "Name", "type": "text"},
                {
                    "name": "info",
                    "label": "Info",
                    "type": "repeat",
                    "children": [
                        {
                            "name": "gender",
                            "label": "Sex",
                            "type": "select one",
                            "itemset": "gender",
                            "list_name": "gender",
                            "children": [
                                {"name": "female", "label": "Female"},
                                {"name": "male", "label": "Male"},
                            ],
                        }
                    ],
                },
                {
                    "name": "other",
                    "label": "Other",
                    "type": "repeat",
                    "children": [
                        {
                            "name": "person",
                            "label": "Person",
                            "type": "repeat",
                            "children": [
                                {
                                    "name": "gender",
                                    "label": "Sex",
                                    "type": "select one",
                                    "itemset": "gender",
                                    "list_name": "gender",
                                    "children": [
                                        {"name": "female", "label": "Female"},
                                        {"name": "male", "label": "Male"},
                                    ],
                                }
                            ],
                        }
                    ],
                },
                {
                    "name": "meta",
                    "type": "group",
                    "control": {"bodyless": True},
                    "children": [
                        {
                            "name": "instanceID",
                            "type": "calculate",
                            "bind": {"readonly": "true()", "jr:preload": "uid"},
                        }
                    ],
                },
            ],
        }  # yapf: disable
        self.assertEqual(survey.to_json_dict(), expected)

    def test_matching_fields_by_type(self):
        """
        Test get_merged_xform_survey(): should only match when question type
        matches.
        """
        self.project = get_user_default_project(self.user)
        xform1 = self._publish_markdown(
            GROUP_A_MD.replace("group", "repeat"), self.user, id_string="a"
        )
        xform2 = self._publish_markdown(GROUP_B_MD, self.user, id_string="b")
        survey = get_merged_xform_survey([xform1, xform2])
        expected = {
            "default_language": "default",
            "id_string": "a",
            "choices": {
                "gender": [
                    {"label": "Female", "name": "female"},
                    {"label": "Male", "name": "male"},
                ]
            },
            "children": [
                {"name": "name", "label": "Name", "type": "text"},
                {
                    "control": {"bodyless": True},
                    "children": [
                        {
                            "name": "instanceID",
                            "bind": {"readonly": "true()", "jr:preload": "uid"},
                            "type": "calculate",
                        }
                    ],
                    "name": "meta",
                    "type": "group",
                },
            ],
            "type": "survey",
            "name": "data",
            "sms_keyword": "a",
            "title": "data",
        }  # yapf: disable

        self.assertEqual(survey.to_json_dict(), expected)

    def test_merged_dataset_dict_contains_no_bind_attributes(self):
        """
        Test get_merged_xform_survey(): should not contain bind elements.
        """
        self.project = get_user_default_project(self.user)
        xform1 = self._publish_markdown(GROUP_A_MD, self.user, id_string="a")
        xform2 = self._publish_markdown(GROUP_B_MD, self.user, id_string="b")
        xform3 = self._publish_markdown(GROUP_C_MD, self.user, id_string="c")
        survey = get_merged_xform_survey([xform1, xform2, xform3])

        result = survey.to_json_dict()
        count = len([child for child in result["children"] if "bind" in child])

        # check that no elements within the newly created
        # merged_dataset_dict contains bind attributes
        self.assertEqual(count, 0)
