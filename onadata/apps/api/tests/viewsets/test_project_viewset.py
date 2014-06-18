from onadata.apps.api.tests.viewsets.test_abstract_viewset import\
    TestAbstractViewSet
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet


class TestProjectViewset(TestAbstractViewSet):
    def setUp(self):
        super(self.__class__, self).setUp()
        self.view = ProjectViewSet.as_view({
            'get': 'list',
            'post': 'create'
        })

    def test_projects_list(self):
        self._project_create()
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [self.project_data])

    def test_projects_get(self):
        self._project_create()
        view = ProjectViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data,
                         {'detail': 'Expected URL keyword argument `owner`.'})
        request = self.factory.get('/', **self.extra)
        response = view(request, owner='bob', pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.project_data)

    def test_projects_create(self):
        self._project_create()

    def test_publish_xls_form_to_project(self):
        self._publish_xls_form_to_project()

    def test_view_xls_form(self):
        self._publish_xls_form_to_project()
        view = ProjectViewSet.as_view({
            'get': 'forms'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request, owner='bob', pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [self.form_data])
        response = view(request, owner='bob',
                        pk=self.project.pk, formid=self.xform.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.form_data)

    def test_assign_form_to_project(self):
        view = ProjectViewSet.as_view({
            'post': 'forms'
        })
        self._publish_xls_form_to_project()
        formid = self.xform.pk
        old_project = self.project
        project_name = u'another project'
        self._project_create({'name': project_name})
        self.assertTrue(self.project.name == project_name)

        project_id = self.project.pk
        post_data = {'formid': formid}
        request = self.factory.post('/', data=post_data, **self.extra)
        response = view(request, owner=self.user.username, pk=project_id)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(self.project.projectxform_set.filter(xform=self.xform))
        self.assertFalse(old_project.projectxform_set.filter(xform=self.xform))
