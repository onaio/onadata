# -*- coding: utf-8 -*-
"""Tests for onadata.libs.utils.xform_utils."""

from django.test import SimpleTestCase

from onadata.libs.utils.xform_utils import role_under_meta_perms

META_PERMS = "owner|manager|readonly-no-download"


class TestRoleUnderMetaPerms(SimpleTestCase):
    """Each lesser role takes the role in its slot of the meta permissions."""

    def test_an_editor_role_takes_the_first_slot(self):
        """Every editor role maps to the first slot."""
        for role_name in ("editor", "editor-minor", "editor-no-download"):
            self.assertEqual(role_under_meta_perms(META_PERMS, role_name), "owner")

    def test_a_data_entry_role_takes_the_second_slot(self):
        """Every data-entry role maps to the second slot."""
        for role_name in ("dataentry", "dataentry-minor", "dataentry-only"):
            self.assertEqual(role_under_meta_perms(META_PERMS, role_name), "manager")

    def test_a_read_only_role_takes_the_third_slot(self):
        """Both read-only roles map to the third slot."""
        for role_name in ("readonly", "readonly-no-download"):
            self.assertEqual(
                role_under_meta_perms(META_PERMS, role_name), "readonly-no-download"
            )

    def test_an_admin_role_is_left_alone(self):
        """Meta permissions never replace an owner or manager."""
        for role_name in ("owner", "manager"):
            self.assertEqual(role_under_meta_perms(META_PERMS, role_name), role_name)

    def test_a_missing_slot_leaves_the_role_alone(self):
        """A value with too few slots replaces only the roles it covers."""
        self.assertEqual(role_under_meta_perms("owner", "editor"), "owner")
        self.assertEqual(role_under_meta_perms("owner", "dataentry"), "dataentry")
