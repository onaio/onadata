from django.test import TransactionTestCase

from onadata.libs.serializers.project_serializer import\
    ProjectSerializer


class TestProjectSerializer(TransactionTestCase):

    def setUp(self):
        self.serializer = ProjectSerializer()

    def test_get_project_permissions_none(self):
        perms = self.serializer.get_project_permissions(None)
        self.assertEqual(perms, [])
