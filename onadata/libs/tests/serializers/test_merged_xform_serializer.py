"""
Test MergedXFormSerializer
"""
from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.libs.serializers.merged_xform_serializer import \
    MergedXFormSerializer
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


class TestMergedXFormSerializer(TestAbstractViewSet):
    """
    Test MergedXFormSerializer
    """
    def test_create_merged_xform(self):
        """Test creating a merged dataset with the MergedXFormSerializer"""
        serializer = MergedXFormSerializer(data={})
        self.assertFalse(serializer.is_valid(raise_exception=False))

        # project is required
        self.assertTrue(serializer.errors['project'],
                        [u'This field is required.'])

        # name is required
        self.assertTrue(serializer.errors['name'],
                        [u'This field is required.'])

        # At least 2 *different* xforms
        # 0 xforms
        self.assertTrue(serializer.errors['xforms'],
                        [u'This field is required.'])

        self.project = get_user_default_project(self.user)
        xform1 = self._publish_md(MD, self.user, id_string='a')
        data = {
            'xforms': [],
            'name': 'Merged Dataset',
            'project':
            "http://testserver.com/api/v1/projects/%s" % self.project.pk,
        }
        serializer = MergedXFormSerializer(data=data)
        self.assertFalse(serializer.is_valid(raise_exception=False))
        self.assertNotIn('name', serializer.errors)
        self.assertNotIn('project', serializer.errors)
        self.assertTrue(serializer.errors['xforms'],
                        [u'This field is required.'])

        # 1 xform
        data['xforms'] = ["http://testserver.com/api/v1/forms/%s" % xform1.pk]
        serializer = MergedXFormSerializer(data=data)
        self.assertFalse(serializer.is_valid(raise_exception=False))
        self.assertTrue(
            serializer.errors['xforms'],
            [u'This field should have at least two unique xforms.'])

        # same xform twice
        xform2 = self._publish_md(MD, self.user, id_string='b')
        data['xforms'] = [
            "http://testserver.com/api/v1/forms/%s" % xform1.pk,
            "http://testserver.com/api/v1/forms/%s" % xform1.pk
        ]
        serializer = MergedXFormSerializer(data=data)
        self.assertFalse(serializer.is_valid(raise_exception=False))
        self.assertTrue(serializer.errors['xforms'],
                        [u'This field should have unique xforms'])

        # two different xforms
        data['xforms'] = [
            "http://testserver.com/api/v1/forms/%s" % xform1.pk,
            "http://testserver.com/api/v1/forms/%s" % xform2.pk
        ]
        serializer = MergedXFormSerializer(data=data)
        self.assertTrue(serializer.is_valid(raise_exception=False))
        self.assertNotIn('xforms', serializer.errors)
