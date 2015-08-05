from django.test import TransactionTestCase

from onadata.libs.serializers.organization_serializer import\
    OrganizationSerializer


class TestOrganizationSerializer(TransactionTestCase):

    def setUp(self):
        self.serializer = OrganizationSerializer()

    def test_get_users_none(self):
        perms = self.serializer.get_users(None)
        self.assertEqual(perms, [])
