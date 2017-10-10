from onadata.apps.logger.models import Project
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import DataEntryRole
from onadata.libs.utils.project_utils import set_project_perms_to_xform


class TestProjectUtils(TestBase):
    def setUp(self):
        super(TestProjectUtils, self).setUp()

        self._create_user('bob', 'bob', create_profile=True)
        self._publish_transportation_form()

    def test_set_project_perms_to_xform(self):
        # Alice has data entry role to default project
        alice = self._create_user('alice', 'alice', create_profile=True)
        DataEntryRole.add(alice, self.project)
        set_project_perms_to_xform(self.xform, self.project)
        self.assertTrue(DataEntryRole.user_has_role(alice, self.xform))
        self.assertTrue(self.project.pk, self.xform.project_id)

        # Create other project and transfer xform to new project
        project_b = Project(
            name='Project B', created_by=self.user, organization=self.user)
        project_b.save()
        self.xform.project = project_b
        self.xform.save()
        self.xform.refresh_from_db()
        self.assertTrue(self.project.pk, self.xform.project_id)

        # set permissions for new project
        set_project_perms_to_xform(self.xform, project_b)

        # Alice should have no data entry role to transfered form
        self.assertFalse(DataEntryRole.user_has_role(alice, self.xform))
