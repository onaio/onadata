# -*- coding: utf-8 -*-
"""Tests for which projects and forms a team owns or manages, and so which
organisations govern joining it."""

from django.utils import timezone

from guardian.shortcuts import get_perms

from onadata.apps.api.models import Team
from onadata.apps.api.tests.viewsets.test_stepup_sharing_gates import (
    EDITOR_BECOMES_MANAGER,
    EDITOR_STAYS_BELOW_ADMIN,
)
from onadata.apps.logger.models import Project, XForm
from onadata.apps.main.models import MetaData
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import EditorRole, ManagerRole, OwnerRole, get_role
from onadata.libs.stepup.owners import team_holding_owners
from onadata.libs.stepup.sharing import team_admin_holdings
from onadata.libs.utils.common_tags import XFORM_META_PERMS

NOTHING = (set(), set())


class TestTeamAdminHoldings(TestBase):
    """``self.xform`` belongs to ``self.user`` and sits in ``self.project``,
    which ``denoinc`` owns. The team starts with no role on either."""

    def setUp(self):
        super().setUp()
        self.organization = self._create_organization("denoinc", "Dennis", self.user)
        self.team = Team.objects.create(
            name="denoinc#dreamteam",
            organization=self.organization.user,
            created_by=self.user,
        )
        self.project = Project.objects.create(
            name="org project",
            organization=self.organization.user,
            created_by=self.user,
        )
        self._publish_transportation_form()
        XForm.objects.filter(pk=self.xform.pk).update(project=self.project)
        self.xform.refresh_from_db()
        self.assertNotEqual(self.xform.user, self.organization.user)
        self.assertEqual(self.xform.project.organization, self.organization.user)
        self.assertIsNone(self._team_role_on(self.project))
        self.assertIsNone(self._team_role_on(self.xform))

    def _team_role_on(self, obj):
        return get_role(get_perms(self.team, obj), obj)

    def _holdings(self):
        return team_admin_holdings([self.team])

    def _set_meta_perms(self, value):
        MetaData.xform_meta_permission(self.xform, data_value=value)
        self.assertEqual(MetaData.xform_meta_permission(self.xform).data_value, value)

    def _soft_delete(self, model, obj):
        model.objects.filter(pk=obj.pk).update(deleted_at=timezone.now())
        obj.refresh_from_db()
        self.assertIsNotNone(obj.deleted_at)

    def test_a_deleted_project_is_not_counted(self):
        ManagerRole.add(self.team, self.project)
        self.assertEqual(self._team_role_on(self.project), ManagerRole.name)
        self.assertEqual(self._holdings(), ({self.project.pk}, set()))

        self._soft_delete(Project, self.project)

        self.assertEqual(self._team_role_on(self.project), ManagerRole.name)
        self.assertEqual(self._holdings(), NOTHING)

    def test_a_deleted_form_is_not_counted(self):
        ManagerRole.add(self.team, self.xform)
        self.assertEqual(self._team_role_on(self.xform), ManagerRole.name)
        self.assertEqual(self._holdings(), (set(), {self.xform.pk}))

        self._soft_delete(XForm, self.xform)

        self.assertEqual(self._team_role_on(self.xform), ManagerRole.name)
        self.assertEqual(self._holdings(), NOTHING)

    def test_an_admin_role_held_directly_on_a_form_is_counted(self):
        for role in (ManagerRole, OwnerRole):
            with self.subTest(role=role.name):
                role.add(self.team, self.xform)
                self.assertEqual(self._team_role_on(self.xform), role.name)
                self.assertIsNone(self._team_role_on(self.project))

                self.assertEqual(self._holdings(), (set(), {self.xform.pk}))
                self.assertEqual(
                    set(team_holding_owners([self.team])),
                    {self.xform.user_id, self.organization.user_id},
                )

    def test_a_lesser_role_meta_perms_raise_to_manager_is_counted(self):
        self._set_meta_perms(EDITOR_BECOMES_MANAGER)
        EditorRole.add(self.team, self.xform)
        self.assertEqual(self._team_role_on(self.xform), EditorRole.name)

        self.assertEqual(self._holdings(), (set(), {self.xform.pk}))
        self.assertEqual(
            set(team_holding_owners([self.team])),
            {self.xform.user_id, self.organization.user_id},
        )

    def test_a_lesser_role_no_meta_perms_raise_is_not_counted(self):
        EditorRole.add(self.team, self.xform)
        self.assertEqual(self._team_role_on(self.xform), EditorRole.name)
        self.assertFalse(
            self.xform.metadata_set.filter(data_type=XFORM_META_PERMS).exists()
        )
        self.assertEqual(self._holdings(), NOTHING)

        self._set_meta_perms(EDITOR_STAYS_BELOW_ADMIN)

        self.assertEqual(self._team_role_on(self.xform), EditorRole.name)
        self.assertEqual(self._holdings(), NOTHING)
        self.assertEqual(list(team_holding_owners([self.team])), [])
