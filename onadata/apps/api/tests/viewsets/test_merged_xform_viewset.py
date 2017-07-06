# coding=utf-8
from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.merged_xform_viewset import MergedXFormViewSet

MD = """
| survey |
|        | type              | name  | label |
|        | select one fruits | fruit | Fruit |

| choices |
|         | list name | name   | label  |
|         | fruits    | orange | Orange |
|         | fruits    | mango  | Mango  |
"""


class TestMergedXFormViewSet(TestAbstractViewSet):
    def setUp(self):
        super(self.__class__, self).setUp()

    def test_create_merged_dataset(self):
        view = MergedXFormViewSet.as_view({'post': 'create', })
        xform1 = self._publish_md(MD, self.user, id_string='a')
        xform2 = self._publish_md(MD, self.user, id_string='b')

        data = {
            'xforms': [
                "http://testserver.com/api/v1/forms/%s" % xform1.pk,
                "http://testserver.com/api/v1/forms/%s" % xform2.pk,
            ],
            'name': 'Merged Dataset',
            'project':
                "http://testserver.com/api/v1/projects/%s" % self.project.pk,
        }
        request = self.factory.post('/', data=data)
        response = view(request)
        self.assertEqual(response.status_code, 201)
        self.assertIn('id', response.data)
        self.assertIn('title', response.data)
        self.assertIn('xforms', response.data)
