# -*- coding: utf-8 -*-
"""Tests for which projects and forms a team owns or manages, and so which
organisations govern joining it."""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from guardian.shortcuts import get_perms

from onadata.apps.api.models import Team
from onadata.apps.api.tests.viewsets.test_merged_xform_viewset import MD
from onadata.apps.api.tests.viewsets.test_stepup_sharing_gates import (
    EDITOR_BECOMES_MANAGER,
    EDITOR_STAYS_BELOW_ADMIN,
)
from onadata.apps.logger.models import Project, XForm
from onadata.apps.main.models import MetaData
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import EditorRole, ManagerRole, OwnerRole, get_role
from onadata.libs.stepup.owners import team_holding_owners
from onadata.libs.stepup.sharing import team_admin_objects, team_reaches_admin_role
from onadata.libs.utils.common_tags import XFORM_META_PERMS

NOTHING = (set(), set())


class TestTeamAdminHoldings(TestBase):
    """``self.xform`` belongs to ``self.user`` and sits in ``self.project``,
    which ``denoinc`` owns. The team starts with no role on either."""

    def setUp(self):
        super().setUp()
        self.organization = self._create_organization("denoinc", "Dennis", self.user)
        # Creating a team grants its organisation's created_by permissions on it.
        self.organization.created_by = self.user
        self.organization.save(update_fields=["created_by"])
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
        projects, xforms = team_admin_objects([self.team])
        return (
            set(projects.values_list("pk", flat=True)),
            set(xforms.values_list("pk", flat=True)),
        )

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

    def test_a_deleted_form_meta_perms_raise_to_manager_is_not_counted(self):
        self._set_meta_perms(EDITOR_BECOMES_MANAGER)
        EditorRole.add(self.team, self.xform)
        self.assertEqual(self._holdings(), (set(), {self.xform.pk}))

        self._soft_delete(XForm, self.xform)

        self.assertEqual(self._team_role_on(self.xform), EditorRole.name)
        self.assertEqual(self._holdings(), NOTHING)
        self.assertEqual(list(team_holding_owners([self.team])), [])

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

    def test_a_team_managing_a_project_reaches_admin_in_one_query(self):
        ManagerRole.add(self.team, self.project)
        self.assertEqual(self._team_role_on(self.project), ManagerRole.name)

        with self.assertNumQueries(1):
            self.assertTrue(team_reaches_admin_role(self.team))

    def _raise_to_manager(self, xform):
        MetaData.xform_meta_permission(xform, data_value=EDITOR_BECOMES_MANAGER)
        EditorRole.add(self.team, xform)
        self.assertEqual(self._team_role_on(xform), EditorRole.name)

    def _query_counts(self):
        calls = {
            "holdings": self._holdings,
            "owners": lambda: list(team_holding_owners([self.team])),
            "reaches": lambda: team_reaches_admin_role(self.team),
        }
        counts = {}
        for name, call in calls.items():
            with CaptureQueriesContext(connection) as captured:
                call()
            counts[name] = len(captured)
        return counts

    def test_the_query_count_does_not_grow_with_the_forms_held(self):
        """Every form is raised to manager by its meta permissions, so
        ``team_reaches_admin_role`` reads every query it can make."""
        self._raise_to_manager(self.xform)
        # Also warms the content type cache the counts would otherwise include.
        self.assertEqual(self._holdings(), (set(), {self.xform.pk}))
        one_form = self._query_counts()

        xforms = [self.xform]
        for id_string in ("a", "b", "c"):
            published = self._publish_markdown(
                MD, self.user, project=self.project, id_string=id_string
            )
            xform = XForm.objects.get(pk=published.pk)
            self._raise_to_manager(xform)
            xforms.append(xform)

        self.assertEqual(self._holdings(), (set(), {xform.pk for xform in xforms}))
        self.assertEqual(self._query_counts(), one_form)
