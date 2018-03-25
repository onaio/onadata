# -*- coding: utf-8 -*-
"""
Test MergedXFormSerializer
"""
from rest_framework import serializers

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.libs.serializers.merged_xform_serializer import (
    MergedXFormSerializer, get_merged_xform_survey)
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
|        | type              | name   | label |
|        | text              | name   | Name  |
|        | begin group       | info   | Info  |
|        | integer           | age    | Age   |
|        | select one gender | gender | Sex   |
|        | end group         |        |       |
|        | begin group       | other  | Other |
|        | begin group       | person | Person |
|        | integer           | age    | Age   |
|        | select one gender | gender | Sex   |
|        | end group         |        |       |
|        | end group         |        |       |

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
        self.assertEqual(serializer.errors['project'],
                         [u'This field is required.'])

        # name is required
        self.assertEqual(serializer.errors['name'],
                         [u'This field is required.'])

        # At least 2 *different* xforms
        # 0 xforms
        self.assertEqual(serializer.errors['xforms'],
                         [u'This field is required.'])

        self.project = get_user_default_project(self.user)
        xform1 = self._publish_markdown(MD, self.user, id_string='a')
        data = {
            'xforms': [],
            'name':
            'Merged Dataset',
            'project':
            "http://testserver.com/api/v1/projects/%s" % self.project.pk,
        }
        serializer = MergedXFormSerializer(data=data)
        self.assertFalse(serializer.is_valid(raise_exception=False))
        self.assertNotIn('name', serializer.errors)
        self.assertNotIn('project', serializer.errors)
        self.assertEqual(serializer.errors['xforms'],
                         [u'This list may not be empty.'])

        # 1 xform
        data['xforms'] = ["http://testserver.com/api/v1/forms/%s" % xform1.pk]
        serializer = MergedXFormSerializer(data=data)
        self.assertFalse(serializer.is_valid(raise_exception=False))
        self.assertIn(
            u'This field should have at least two unique xforms.',
            serializer.errors['xforms']
        )

        # same xform twice
        data['xforms'] = [
            "http://testserver.com/api/v1/forms/%s" % xform1.pk,
            "http://testserver.com/api/v1/forms/%s" % xform1.pk
        ]
        serializer = MergedXFormSerializer(data=data)
        self.assertFalse(serializer.is_valid(raise_exception=False))
        self.assertIn(
            u'This field should have unique xforms',
            serializer.errors['xforms']
        )

        # xform with no matching fields
        xform3 = self._publish_markdown(A_MD, self.user, id_string='c')
        data['xforms'] = [
            "http://testserver.com/api/v1/forms/%s" % xform1.pk,
            "http://testserver.com/api/v1/forms/%s" % xform3.pk
        ]
        serializer = MergedXFormSerializer(data=data)
        self.assertFalse(serializer.is_valid(raise_exception=False))
        self.assertEqual(serializer.errors['xforms'],
                         [u'No matching fields in xforms.'])

        # two different xforms
        xform2 = self._publish_markdown(MD, self.user, id_string='b')
        data['xforms'] = [
            "http://testserver.com/api/v1/forms/%s" % xform1.pk,
            "http://testserver.com/api/v1/forms/%s" % xform2.pk
        ]
        serializer = MergedXFormSerializer(data=data)
        self.assertTrue(serializer.is_valid(raise_exception=False))
        self.assertNotIn('xforms', serializer.errors)

    def test_get_merged_xform_survey(self):
        """
        Test get_merged_xform_survey()
        """
        with self.assertRaises(serializers.ValidationError):
            get_merged_xform_survey([])

        self.project = get_user_default_project(self.user)
        xform1 = self._publish_markdown(A_MD, self.user, id_string='a')
        xform2 = self._publish_markdown(B_MD, self.user, id_string='b')
        xform3 = self._publish_markdown(MD, self.user, id_string='c')
        expected = {
            u'name': u'data',
            u'title': u'pyxform_autotesttitle',
            u'sms_keyword': u'a',
            u'default_language': u'default',
            u'id_string': u'a',
            u'type': u'survey',
            u'children': [{
                u'name': u'name',
                u'label': u'Name',
                u'type': u'text'
            }, {
                u'children': [{
                    u'name': u'female',
                    u'label': u'Female'
                }, {
                    u'name': u'male',
                    u'label': u'Male'
                }],
                u'name': u'gender',
                u'label': u'Sex',
                u'type': u'select one'
            }, {
                u'control': {
                    u'bodyless': True
                },
                u'children': [{
                    u'name': u'instanceID',
                    u'bind': {
                        u'readonly': u'true()',
                        u'calculate': u"concat('uuid:', uuid())"
                    },
                    u'type': u'calculate'
                }],
                u'name': u'meta',
                u'type': u'group'
            }]
        }  # yapf: disable

        with self.assertRaises(serializers.ValidationError):
            get_merged_xform_survey([xform1])

        survey = get_merged_xform_survey([xform1, xform2])
        self.assertEqual(survey.to_json_dict(), expected)

        # no matching fields
        with self.assertRaises(serializers.ValidationError):
            survey = get_merged_xform_survey([xform1, xform3])

    def test_group_merged_xform_survey(self):
        """
        Test get_merged_xform_survey() with groups in xforms.
        """
        self.project = get_user_default_project(self.user)
        xform1 = self._publish_markdown(GROUP_A_MD, self.user, id_string='a')
        xform2 = self._publish_markdown(GROUP_B_MD, self.user, id_string='b')
        survey = get_merged_xform_survey([xform1, xform2])
        expected = {
            u'default_language': u'default',
            u'id_string': u'a',
            u'children': [{
                u'name': u'name',
                u'label': u'Name',
                u'type': u'text'
            }, {
                u'children': [{
                    u'children': [{
                        u'name': u'female',
                        u'label': u'Female'
                    }, {
                        u'name': u'male',
                        u'label': u'Male'
                    }],
                    u'name': u'gender',
                    u'label': u'Sex',
                    u'type': u'select one'
                }],
                u'name': u'info',
                u'label': u'Info',
                u'type': u'group'
            }, {
                u'children': [{
                    u'children': [{
                        u'children': [{
                            u'name': u'female',
                            u'label': u'Female'
                        }, {
                            u'name': u'male',
                            u'label': u'Male'
                        }],
                        u'name': u'gender',
                        u'label': u'Sex',
                        u'type': u'select one'
                    }],
                    u'name': u'person',
                    u'label': u'Person',
                    u'type': u'group'
                }],
                u'name': u'other',
                u'label': u'Other',
                u'type': u'group',
            }, {
                u'control': {
                    u'bodyless': True
                },
                u'children': [{
                    u'name': u'instanceID',
                    u'bind': {
                        u'readonly': u'true()',
                        u'calculate': u"concat('uuid:', uuid())"
                    },
                    u'type': u'calculate'
                }],
                u'name': u'meta',
                u'type': u'group'
            }],
            u'type': u'survey',
            u'name': u'data',
            u'sms_keyword': u'a',
            u'title': u'pyxform_autotesttitle'
        }  # yapf: disable

        self.assertEqual(survey.to_json_dict(), expected)

    def test_repeat_merged_xform_survey(self):
        """
        Test get_merged_xform_survey() with repeats in xforms.
        """
        self.project = get_user_default_project(self.user)
        xform1 = self._publish_markdown(GROUP_A_MD.replace('group', 'repeat'),
                                        self.user, id_string='a')
        xform2 = self._publish_markdown(GROUP_B_MD.replace('group', 'repeat'),
                                        self.user, id_string='b')
        survey = get_merged_xform_survey([xform1, xform2])
        expected = {
            u'default_language': u'default',
            u'id_string': u'a',
            u'children': [{
                u'name': u'name',
                u'label': u'Name',
                u'type': u'text'
            }, {
                u'children': [{
                    u'children': [{
                        u'name': u'female',
                        u'label': u'Female'
                    }, {
                        u'name': u'male',
                        u'label': u'Male'
                    }],
                    u'name': u'gender',
                    u'label': u'Sex',
                    u'type': u'select one'
                }],
                u'name': u'info',
                u'label': u'Info',
                u'type': u'repeat'
            }, {
                u'children': [{
                    u'children': [{
                        u'children': [{
                            u'name': u'female',
                            u'label': u'Female'
                        }, {
                            u'name': u'male',
                            u'label': u'Male'
                        }],
                        u'name': u'gender',
                        u'label': u'Sex',
                        u'type': u'select one'
                    }],
                    u'name': u'person',
                    u'label': u'Person',
                    u'type': u'repeat'
                }],
                u'name': u'other',
                u'label': u'Other',
                u'type': u'repeat',
            }, {
                u'control': {
                    u'bodyless': True
                },
                u'children': [{
                    u'name': u'instanceID',
                    u'bind': {
                        u'readonly': u'true()',
                        u'calculate': u"concat('uuid:', uuid())"
                    },
                    u'type': u'calculate'
                }],
                u'name': u'meta',
                u'type': u'group'
            }],
            u'type': u'survey',
            u'name': u'data',
            u'sms_keyword': u'a',
            u'title': u'pyxform_autotesttitle'
        }  # yapf: disable

        self.assertEqual(survey.to_json_dict(), expected)

    def test_matching_fields_by_type(self):
        """
        Test get_merged_xform_survey(): should only match when question type
        matches.
        """
        self.project = get_user_default_project(self.user)
        xform1 = self._publish_markdown(GROUP_A_MD.replace('group', 'repeat'),
                                        self.user, id_string='a')
        xform2 = self._publish_markdown(GROUP_B_MD, self.user, id_string='b')
        survey = get_merged_xform_survey([xform1, xform2])
        expected = {
            u'default_language': u'default',
            u'id_string': u'a',
            u'children': [{
                u'name': u'name',
                u'label': u'Name',
                u'type': u'text'
            }, {
                u'control': {
                    u'bodyless': True
                },
                u'children': [{
                    u'name': u'instanceID',
                    u'bind': {
                        u'readonly': u'true()',
                        u'calculate': u"concat('uuid:', uuid())"
                    },
                    u'type': u'calculate'
                }],
                u'name': u'meta',
                u'type': u'group'
            }],
            u'type': u'survey',
            u'name': u'data',
            u'sms_keyword': u'a',
            u'title': u'pyxform_autotesttitle'
        }  # yapf: disable

        self.assertEqual(survey.to_json_dict(), expected)
