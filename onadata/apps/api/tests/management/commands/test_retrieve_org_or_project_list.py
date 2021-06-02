import json
from django.core.management import call_command
from django.utils.six import StringIO

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.libs.serializers.share_project_serializer import \
    ShareProjectSerializer


class TestRetrieveOrgOrProjectListCommand(TestAbstractViewSet):
    def test_retrieve_org_or_project_list(self):
        self._org_create()
        self._project_create()

        user = self._create_user_profile(
            {'username': 'alice'}).user
        share_data = {
            'project': self.project.id,
            'username': user.username,
            'role': 'editor'
        }
        serializer = ShareProjectSerializer(data=share_data)
        self.assertTrue(serializer.is_valid())
        serializer.save()

        out = StringIO()
        call_command(
            'retrieve_org_or_project_list',
            stdout=out
        )

        expected_project_data = {
            self.project.name: {
                user.username: {
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_org': False,
                    'role': 'editor'
                },
                self.user.username: {
                    'first_name': self.user.first_name,
                    'last_name': self.user.last_name,
                    'is_org': False,
                    'role': 'owner'
                }
            }
        }

        expected_org_data = {
            self.organization.name: {
                self.user.username: {
                    'first_name': self.user.first_name,
                    'last_name': self.user.last_name,
                    'role': 'owner'
                },
                self.organization.user.username: {
                    'first_name': self.organization.user.first_name,
                    'last_name': self.organization.user.last_name,
                    'role': 'owner'
                }
            }
        }

        expected_data = {}
        expected_data.update(expected_project_data)
        expected_data.update(expected_org_data)

        self.assertEqual(
            expected_data,
            json.loads(out.getvalue())
        )

        out = StringIO()

        call_command(
            'retrieve_org_or_project_list',
            project_ids=f'{self.project.id}',
            stdout=out
        )
        self.assertEqual(
            expected_project_data,
            json.loads(out.getvalue())
        )

        out = StringIO()

        call_command(
            'retrieve_org_or_project_list',
            organization_ids=f'{self.organization.id}',
            stdout=out
        )
        self.assertEqual(
            expected_org_data,
            json.loads(out.getvalue())
        )
