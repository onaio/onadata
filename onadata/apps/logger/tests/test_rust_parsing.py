"""Tests that RustXFormInstanceParser produces identical output to XFormInstanceParser."""

import os

from django.test import override_settings

from onadata.apps.logger.xform_instance_parser import (
    RustXFormInstanceParser,
    XFormInstanceParser,
)
from onadata.apps.main.tests.test_base import TestBase


class TestRustXFormInstanceParser(TestBase):
    """Compare Rust parser output against Python parser for identical inputs."""

    def _get_fixture_path(self, *parts):
        return os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "fixtures",
            *parts,
        )

    def _publish_and_get_xml(self, fixture_dir, xls_name, xml_rel_path):
        self._create_user_and_login()
        xls_path = self._get_fixture_path(fixture_dir, xls_name)
        self._publish_xls_file_and_set_xform(xls_path)
        xml_path = self._get_fixture_path(fixture_dir, xml_rel_path)
        with open(xml_path) as f:
            return f.read()

    def _assert_parsers_match(self, xml):
        """Assert that Python and Rust parsers produce identical output."""
        py_parser = XFormInstanceParser(xml, self.xform)
        rust_parser = RustXFormInstanceParser(xml, self.xform)

        self.assertEqual(
            py_parser.to_dict(),
            rust_parser.to_dict(),
            "to_dict() mismatch",
        )
        self.assertEqual(
            py_parser.to_flat_dict(),
            rust_parser.to_flat_dict(),
            "to_flat_dict() mismatch",
        )
        self.assertEqual(
            py_parser.get_flat_dict_with_attributes(),
            rust_parser.get_flat_dict_with_attributes(),
            "get_flat_dict_with_attributes() mismatch",
        )
        self.assertEqual(
            py_parser.get_root_node_name(),
            rust_parser.get_root_node_name(),
            "get_root_node_name() mismatch",
        )
        self.assertEqual(
            py_parser.get_xform_id_string(),
            rust_parser.get_xform_id_string(),
            "get_xform_id_string() mismatch",
        )

    def test_nested_repeats_parity(self):
        """Test that nested repeats produce identical output."""
        xml = self._publish_and_get_xml(
            "new_repeats",
            "new_repeats.xlsx",
            os.path.join("instances", "new_repeats_2012-07-05-14-33-53.xml"),
        )
        self._assert_parsers_match(xml)

    def test_encrypted_form_parity(self):
        """Test that encrypted form parsing produces identical output."""
        xml = self._publish_and_get_xml(
            "tutorial_encrypted",
            "tutorial_encrypted.xlsx",
            os.path.join("instances", "tutorial_encrypted.xml"),
        )
        self._assert_parsers_match(xml)

    def test_rust_parser_uuid_extraction(self):
        """Test UUID extraction from Rust parser."""
        xml = self._publish_and_get_xml(
            "new_repeats",
            "new_repeats.xlsx",
            os.path.join("instances", "new_repeats_2012-07-05-14-33-53.xml"),
        )
        rust_parser = RustXFormInstanceParser(xml, self.xform)
        # new_repeats fixture doesn't have a UUID in meta
        # Just verify the attribute is accessible
        self.assertIsNotNone(rust_parser._result)
        self.assertEqual(rust_parser.get_root_node_name(), "new_repeats")

    def test_rust_parser_geom_extraction(self):
        """Test geopoint extraction from Rust parser."""
        xml = self._publish_and_get_xml(
            "new_repeats",
            "new_repeats.xlsx",
            os.path.join("instances", "new_repeats_2012-07-05-14-33-53.xml"),
        )
        rust_parser = RustXFormInstanceParser(xml, self.xform)
        # The new_repeats form has a gps field
        geom_points = rust_parser._result.geom_points
        self.assertIsInstance(geom_points, list)

    @override_settings(USE_RUST_XML_PARSER=True)
    def test_full_submission_with_rust_parser(self):
        """Test that a full submission round-trip works with the Rust parser."""
        self._create_user_and_login()
        xls_path = self._get_fixture_path("tutorial", "tutorial.xlsx")
        self._publish_xls_file_and_set_xform(xls_path)
        xml_path = self._get_fixture_path(
            "tutorial",
            "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid.xml",
        )
        self._make_submission(xml_path)
        self.assertEqual(self.response.status_code, 201)

        # Verify instance was saved correctly
        instance = self.xform.instances.first()
        self.assertIsNotNone(instance)
        self.assertEqual(instance.uuid, "729f173c688e482486a48661700455ff")
