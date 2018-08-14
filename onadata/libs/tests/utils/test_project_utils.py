# -*- coding=utf-8 -*-
"""
Test onadata.libs.utils.project_utils
"""
from django.test.utils import override_settings

from kombu.exceptions import OperationalError
from mock import patch

from onadata.apps.logger.models import Project
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import DataEntryRole
from onadata.libs.utils.project_utils import (set_project_perms_to_xform,
                                              set_project_perms_to_xform_async)


class TestProjectUtils(TestBase):
    """
    Test project_utils module.
    """

    def setUp(self):
        super(TestProjectUtils, self).setUp()

        self._create_user('bob', 'bob', create_profile=True)

    def test_set_project_perms_to_xform(self):
        """
        Test set_project_perms_to_xform(xform, project)
        """
        self._publish_transportation_form()
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

    # pylint: disable=invalid-name
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch('onadata.libs.utils.project_utils.set_project_perms_to_xform')
    def test_set_project_perms_to_xform_async(self, mock):
        """
        Test that the set_project_perms_to_xform_async task actually calls
        the set_project_perms_to_xform function
        """
        self._publish_transportation_form()
        set_project_perms_to_xform_async.delay(self.xform.pk, self.project.pk)
        self.assertTrue(mock.called)
        args, _kwargs = mock.call_args_list[0]
        self.assertEqual(args[0], self.xform)
        self.assertEqual(args[1], self.project)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch(
        'onadata.libs.utils.project_utils.set_project_perms_to_xform_async.delay'  # noqa
    )
    @patch('onadata.libs.utils.project_utils.set_project_perms_to_xform')
    def test_rabbitmq_connection_error(self, mock_set_perms_async,
                                       mock_set_perms):
        """
        Test rabbitmq connection error.
        """
        mock_set_perms_async.side_effect = OperationalError("connection error")
        self._publish_transportation_form()
        self.assertFalse(mock_set_perms_async.called)
        self.assertTrue(mock_set_perms.called)
