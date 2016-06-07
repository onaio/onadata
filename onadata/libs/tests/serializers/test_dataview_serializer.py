from rest_framework.test import APIRequestFactory

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.libs.serializers.dataview_serializer import DataViewSerializer
from onadata.apps.logger.models import DataView


class TestDataViewSerializer(TestAbstractViewSet):

    def setUp(self):
        self.factory = APIRequestFactory()
        pass

    def test_value_of_has_hxl_support_field(self):
        # age is the only field with hxl support in this context so any
        # dataview without the age column should have 'has_hxl_support'
        # set to False
        self._login_user_and_profile()
        self._publish_form_with_hxl_support()

        name_and_columns = {
            'name_only': '["name"]',
            'age_only': '["age"]',
            'age_and_name': '["age", "name"]'
        }
        for name, columns in name_and_columns.items():
            data = {
                'name': name,
                'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
                'project': 'http://testserver/api/v1/projects/%s'
                           % self.project.pk,
                'columns': columns,
                'query': '[]'
            }

            self._create_dataview(data=data)

        request = self.factory.get('/', **self.extra)
        request.user = self.user

        def get_has_hxl_support_value(data_view_name):
            data_view = DataView.objects.get(name=data_view_name)
            data = DataViewSerializer(
                data_view, context={'request': request}
            ).data

            return data.get('has_hxl_support')

        self.assertFalse(get_has_hxl_support_value('name_only'))
        self.assertTrue(get_has_hxl_support_value('age_only'))
        self.assertTrue(get_has_hxl_support_value('age_and_name'))
