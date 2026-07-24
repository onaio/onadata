# -*- coding: utf-8 -*-
"""
Tests for strict upload validation helpers.
"""

import io
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

import openpyxl
from PIL import Image

from onadata.libs.utils.upload_validation import (
    DATA_IMPORT_UPLOAD_CONTEXT,
    FORM_MEDIA_ALLOWED_EXTENSIONS,
    FORM_MEDIA_UPLOAD_CONTEXT,
    SUPPORTING_DOC_ALLOWED_EXTENSIONS,
    SUPPORTING_DOC_UPLOAD_CONTEXT,
    XLSFORM_ALLOWED_EXTENSIONS,
    XLSFORM_UPLOAD_CONTEXT,
    UploadValidationError,
    generic_upload_validation_error_message,
    validate_uploaded_file,
)


class _CountingUpload:
    """A seekable upload-like object that counts bytes read.

    ``size`` may be set larger than the backing data so a bounded validator can
    be checked against a "large" file without materialising one.
    """

    def __init__(self, name, data, content_type, size=None):
        self.name = name
        self.content_type = content_type
        self._stream = io.BytesIO(data)
        self.size = len(data) if size is None else size
        self.bytes_read = 0

    def read(self, amount=-1):
        chunk = self._stream.read(amount)
        self.bytes_read += len(chunk)
        return chunk

    def seek(self, offset, whence=0):
        return self._stream.seek(offset, whence)

    def tell(self):
        return self._stream.tell()


# A minimal valid MP4 ftyp box (box size 0x18 = 24 bytes, major brand "isom").
VALID_MP4_FTYP = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2"

# An illustrative "large" per-(context, extension) cap for exercising the
# bounded-validation path. Any value above the 1 MB default works; this is a
# test value, not a recommended deployment setting.
LARGE_TEST_CAP = 32 * 1024 * 1024


class UploadValidationTestCase(SimpleTestCase):
    """Strict upload validation tests."""

    def _upload(self, name, data, content_type):
        return SimpleUploadedFile(name, data, content_type=content_type)

    def _image_bytes(self, image_format):
        image = Image.new("RGB", (1, 1), color=(255, 0, 0))
        stream = io.BytesIO()
        image.save(stream, image_format)
        return stream.getvalue()

    def _xlsx_bytes(self):
        stream = io.BytesIO()
        workbook = openpyxl.Workbook()
        workbook.active["A1"] = "name"
        workbook.save(stream)
        workbook.close()
        return stream.getvalue()

    def test_valid_uploads_are_accepted(self):
        """Valid files from the strict allowlist pass validation."""
        # (name, bytes, content_type, allowed_extensions, context)
        samples = [
            (
                "image.png",
                self._image_bytes("PNG"),
                "image/png",
                FORM_MEDIA_ALLOWED_EXTENSIONS,
                FORM_MEDIA_UPLOAD_CONTEXT,
            ),
            (
                "image.jpg",
                self._image_bytes("JPEG"),
                "image/jpeg",
                FORM_MEDIA_ALLOWED_EXTENSIONS,
                FORM_MEDIA_UPLOAD_CONTEXT,
            ),
            (
                "video.mp4",
                b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2",
                "video/mp4",
                FORM_MEDIA_ALLOWED_EXTENSIONS,
                FORM_MEDIA_UPLOAD_CONTEXT,
            ),
            (
                "data.csv",
                b"name\nAlice\n",
                "text/csv",
                FORM_MEDIA_ALLOWED_EXTENSIONS,
                FORM_MEDIA_UPLOAD_CONTEXT,
            ),
            (
                "form.xml",
                b"<data><name>Alice</name></data>",
                "text/xml",
                FORM_MEDIA_ALLOWED_EXTENSIONS,
                FORM_MEDIA_UPLOAD_CONTEXT,
            ),
            (
                "legacy.xls",
                b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1payload",
                "application/vnd.ms-excel",
                XLSFORM_ALLOWED_EXTENSIONS,
                XLSFORM_UPLOAD_CONTEXT,
            ),
            (
                "workbook.xlsx",
                self._xlsx_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                XLSFORM_ALLOWED_EXTENSIONS,
                XLSFORM_UPLOAD_CONTEXT,
            ),
        ]

        for name, data, content_type, allowed_extensions, context in samples:
            with self.subTest(name=name):
                uploaded_file = self._upload(name, data, content_type)
                result = validate_uploaded_file(
                    uploaded_file, allowed_extensions, context
                )
                self.assertEqual(uploaded_file.tell(), 0)
                self.assertNotEqual(result.storage_basename, result.original_name)
                self.assertTrue(
                    result.storage_basename.endswith(f".{result.extension}")
                )

    def test_generic_validation_error_message_sanitizes_filename(self):
        """Generic API errors identify only the sanitized client filename."""
        uploaded_file = _CountingUpload(
            r"C:\fakepath\evil.svg", b"<svg/>", "image/svg+xml"
        )

        self.assertEqual(
            generic_upload_validation_error_message(uploaded_file),
            "The uploaded file 'evil.svg' could not be validated.",
        )

    def test_generic_validation_error_message_handles_missing_filename(self):
        """Generic API errors retain the old text when no filename remains."""
        uploaded_file = _CountingUpload("\x00\x1f", b"payload", "application/pdf")

        self.assertEqual(
            generic_upload_validation_error_message(uploaded_file),
            "The uploaded file could not be validated.",
        )

    def test_generic_validation_error_message_appends_reason(self):
        """A provided reason is appended after the generic text."""
        uploaded_file = _CountingUpload("data.csv", b"x", "text/csv")

        self.assertEqual(
            generic_upload_validation_error_message(
                uploaded_file, UploadValidationError("CSV files must be UTF-8 encoded.")
            ),
            "The uploaded file 'data.csv' could not be validated. "
            "CSV files must be UTF-8 encoded.",
        )

    def test_generic_validation_error_message_sanitizes_reason(self):
        """A multi-line/oversized reason is collapsed and length-capped."""
        uploaded_file = _CountingUpload("data.csv", b"x", "text/csv")
        noisy_reason = "line one\n\tline two   line three" + ("!" * 500)

        message = generic_upload_validation_error_message(uploaded_file, noisy_reason)
        surfaced = message.split("could not be validated. ", 1)[1]

        self.assertNotIn("\n", surfaced)
        self.assertNotIn("\t", surfaced)
        self.assertLessEqual(len(surfaced), 200)
        self.assertTrue(surfaced.startswith("line one line two line three"))

    def test_double_extension_is_rejected(self):
        """Filenames such as putty.exe.png are rejected before persistence."""
        uploaded_file = self._upload("putty.exe.png", b"MZpayload", "image/png")

        with self.assertRaisesRegex(UploadValidationError, r"'\.exe' suffix"):
            validate_uploaded_file(
                uploaded_file, FORM_MEDIA_ALLOWED_EXTENSIONS, FORM_MEDIA_UPLOAD_CONTEXT
            )

    def test_benign_multi_dot_filename_is_accepted(self):
        """Filenames with multiple dots but a safe penultimate suffix pass."""
        uploaded_file = self._upload("report.v2.csv", b"name\nAlice\n", "text/csv")

        result = validate_uploaded_file(
            uploaded_file, FORM_MEDIA_ALLOWED_EXTENSIONS, FORM_MEDIA_UPLOAD_CONTEXT
        )

        self.assertEqual(result.extension, "csv")
        self.assertEqual(result.original_name, "report.v2.csv")

    def test_content_type_mismatch_is_rejected(self):
        """Mismatched MIME metadata does not pass validation."""
        uploaded_file = self._upload("data.csv", b"name\nAlice\n", "image/png")

        with self.assertRaisesRegex(UploadValidationError, "Unsupported content type"):
            validate_uploaded_file(
                uploaded_file, FORM_MEDIA_ALLOWED_EXTENSIONS, FORM_MEDIA_UPLOAD_CONTEXT
            )

    def test_octet_stream_content_type_is_accepted(self):
        """``application/octet-stream`` is accepted as an unknown-type fallback.

        Windows browsers, ODK Collect, curl without ``-H``, and various mobile
        clients commonly submit uploads with this MIME. Magic-byte validation
        still verifies the content matches the extension.
        """
        uploaded_file = self._upload(
            "data.csv", b"name\nAlice\n", "application/octet-stream"
        )

        result = validate_uploaded_file(
            uploaded_file, FORM_MEDIA_ALLOWED_EXTENSIONS, FORM_MEDIA_UPLOAD_CONTEXT
        )

        self.assertEqual(result.extension, "csv")
        self.assertEqual(result.content_type, "text/csv")

    def test_missing_content_type_is_accepted(self):
        """An upload without a declared content type is accepted."""
        uploaded_file = self._upload("data.csv", b"name\nAlice\n", None)

        result = validate_uploaded_file(
            uploaded_file, FORM_MEDIA_ALLOWED_EXTENSIONS, FORM_MEDIA_UPLOAD_CONTEXT
        )

        self.assertEqual(result.extension, "csv")
        self.assertEqual(result.content_type, "text/csv")

    def test_octet_stream_still_validates_content(self):
        """``application/octet-stream`` does not bypass magic-byte validation."""
        uploaded_file = self._upload(
            "image.png", b"MZpayload", "application/octet-stream"
        )

        with self.assertRaisesRegex(UploadValidationError, "PNG signature mismatch"):
            validate_uploaded_file(
                uploaded_file,
                FORM_MEDIA_ALLOWED_EXTENSIONS,
                FORM_MEDIA_UPLOAD_CONTEXT,
            )

    def test_signature_mismatch_is_rejected(self):
        """Executable bytes renamed as PNG are rejected."""
        uploaded_file = self._upload("putty.png", b"MZpayload", "image/png")

        with self.assertRaisesRegex(UploadValidationError, "PNG signature mismatch"):
            validate_uploaded_file(
                uploaded_file, FORM_MEDIA_ALLOWED_EXTENSIONS, FORM_MEDIA_UPLOAD_CONTEXT
            )

    def test_content_mismatch_is_rejected(self):
        """Valid PNG bytes uploaded as CSV are rejected by content validation."""
        uploaded_file = self._upload("data.csv", self._image_bytes("PNG"), "text/csv")

        with self.assertRaisesRegex(UploadValidationError, "NUL bytes"):
            validate_uploaded_file(
                uploaded_file, FORM_MEDIA_ALLOWED_EXTENSIONS, FORM_MEDIA_UPLOAD_CONTEXT
            )

    @override_settings(STRICT_UPLOAD_MAX_BYTES={"*": 4})
    def test_oversized_upload_is_rejected(self):
        """Oversized uploads are rejected before parser validation."""
        uploaded_file = self._upload("data.csv", b"name\nAlice\n", "text/csv")

        with self.assertRaisesRegex(UploadValidationError, "maximum upload size"):
            validate_uploaded_file(uploaded_file, ("csv",), DATA_IMPORT_UPLOAD_CONTEXT)

    @override_settings(STRICT_UPLOAD_MAX_BYTES={"data_import": {"*": 4}})
    def test_per_context_size_override_is_applied(self):
        """A whole-context ("*") cap narrows the upload size limit."""
        uploaded_file = self._upload("data.csv", b"name\nAlice\n", "text/csv")

        with self.assertRaisesRegex(UploadValidationError, "maximum upload size"):
            validate_uploaded_file(uploaded_file, ("csv",), DATA_IMPORT_UPLOAD_CONTEXT)

    @override_settings(
        STRICT_UPLOAD_MAX_BYTES={"*": 4, "data_import": {"*": 8, "csv": 64}},
    )
    def test_per_context_extension_override_takes_precedence(self):
        """An exact extension cap wins over the "*" and global caps."""
        # 30 bytes: above the global (4) and whole-context "*" (8) caps but below
        # the (data_import, csv) cap (64), so it must be accepted.
        uploaded_file = self._upload("data.csv", b"name\n" + b"a\n" * 12, "text/csv")
        result = validate_uploaded_file(
            uploaded_file, ("csv",), DATA_IMPORT_UPLOAD_CONTEXT
        )
        self.assertEqual(result.extension, "csv")
        self.assertEqual(uploaded_file.tell(), 0)

    @override_settings(STRICT_FORM_MEDIA_UPLOAD_TYPES=["image/png"])
    def test_operator_form_media_allowlist_narrows_extensions(self):
        """Operator-configured MIME allowlist filters form media extensions."""
        uploaded_file = self._upload("data.csv", b"name\nAlice\n", "text/csv")

        with self.assertRaisesRegex(
            UploadValidationError, "Unsupported file extension"
        ):
            validate_uploaded_file(
                uploaded_file,
                FORM_MEDIA_ALLOWED_EXTENSIONS,
                FORM_MEDIA_UPLOAD_CONTEXT,
            )

    @override_settings(STRICT_FORM_MEDIA_UPLOAD_TYPES=["image/png"])
    def test_operator_form_media_allowlist_permits_listed_type(self):
        """Operator-configured MIME allowlist permits its listed types."""
        uploaded_file = self._upload("image.png", self._image_bytes("PNG"), "image/png")

        result = validate_uploaded_file(
            uploaded_file,
            FORM_MEDIA_ALLOWED_EXTENSIONS,
            FORM_MEDIA_UPLOAD_CONTEXT,
        )
        self.assertEqual(result.extension, "png")

    @override_settings(
        STRICT_UPLOAD_MAX_BYTES={
            "*": 1 * 1024 * 1024,
            "form_media": {"mp4": LARGE_TEST_CAP, "csv": LARGE_TEST_CAP},
            "data_import": {"csv": LARGE_TEST_CAP},
        },
    )
    def test_large_mp4_accepted_and_read_is_bounded(self):
        """A large MP4 passes form_media validation reading only its header."""
        uploaded = _CountingUpload(
            "video.mp4", VALID_MP4_FTYP, "video/mp4", size=LARGE_TEST_CAP
        )
        result = validate_uploaded_file(
            uploaded, FORM_MEDIA_ALLOWED_EXTENSIONS, FORM_MEDIA_UPLOAD_CONTEXT
        )
        self.assertEqual(result.extension, "mp4")
        # Only the ftyp box is read, never the (claimed) large body.
        self.assertLessEqual(uploaded.bytes_read, 1024)
        self.assertEqual(uploaded.tell(), 0)

    @override_settings(
        STRICT_UPLOAD_MAX_BYTES={
            "*": 1 * 1024 * 1024,
            "form_media": {"mp4": LARGE_TEST_CAP, "csv": LARGE_TEST_CAP},
            "data_import": {"csv": LARGE_TEST_CAP},
        },
    )
    def test_large_csv_accepted_under_form_media_and_data_import(self):
        """A CSV well above the 1 MB default is accepted where the cap allows."""
        # ~2 MB CSV, larger than both the default cap and the head sample.
        data = b"name\n" + (b"value\n" * 350_000)
        self.assertGreater(len(data), 2 * 1024 * 1024)
        for context in (FORM_MEDIA_UPLOAD_CONTEXT, DATA_IMPORT_UPLOAD_CONTEXT):
            with self.subTest(context=context):
                uploaded = self._upload("data.csv", data, "text/csv")
                result = validate_uploaded_file(uploaded, ("csv",), context)
                self.assertEqual(result.extension, "csv")
                self.assertEqual(uploaded.tell(), 0)

    @override_settings(
        STRICT_UPLOAD_MAX_BYTES={
            "*": 1 * 1024 * 1024,
            "form_media": {"mp4": LARGE_TEST_CAP, "csv": LARGE_TEST_CAP},
        },
    )
    def test_large_cap_does_not_leak_to_full_read_formats(self):
        """Only mp4/csv get the large cap; png/xml/geojson stay at 1 MB."""
        oversized = b"\x00" * (1 * 1024 * 1024 + 16)
        cases = [
            ("map.png", b"\x89PNG\r\n\x1a\n" + oversized, "image/png"),
            ("form.xml", b"<data/>" + oversized, "application/xml"),
            ("area.geojson", b'{"type":"Point"}' + oversized, "application/geo+json"),
        ]
        for name, data, content_type in cases:
            with self.subTest(name=name):
                uploaded = self._upload(name, data, content_type)
                with self.assertRaisesRegex(
                    UploadValidationError, "maximum upload size"
                ):
                    validate_uploaded_file(
                        uploaded,
                        FORM_MEDIA_ALLOWED_EXTENSIONS,
                        FORM_MEDIA_UPLOAD_CONTEXT,
                    )

    def test_csv_streaming_scans_whole_file_for_invalid_utf8(self):
        """Invalid UTF-8 past the first chunk is caught, not just the head."""
        # Valid first chunk, invalid UTF-8 continuation byte in a later chunk.
        data = b"name\n" + (b"value\n" * 20_000) + b"\xff\xfe\n"
        self.assertGreater(len(data), 64 * 1024)
        uploaded = self._upload("data.csv", data, "text/csv")
        with self.assertRaisesRegex(UploadValidationError, "UTF-8"):
            validate_uploaded_file(uploaded, ("csv",), DATA_IMPORT_UPLOAD_CONTEXT)

    def test_csv_streaming_scans_whole_file_for_nul_bytes(self):
        """A NUL byte past the first chunk is caught by the streaming scan."""
        data = b"name\n" + (b"value\n" * 20_000) + b"bad\x00row\n"
        self.assertGreater(len(data), 64 * 1024)
        uploaded = self._upload("data.csv", data, "text/csv")
        with self.assertRaisesRegex(UploadValidationError, "NUL bytes"):
            validate_uploaded_file(uploaded, ("csv",), DATA_IMPORT_UPLOAD_CONTEXT)


def _pdf_bytes(body=b"PDF body bytes\n", include_eof=True):
    payload = b"%PDF-1.4\n" + body
    if include_eof:
        payload += b"%%EOF\n"
    return payload


def _ooxml_bytes(parts):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, body in parts:
            archive.writestr(name, body)
    return stream.getvalue()


def _odf_bytes(mimetype, extra_parts=()):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("mimetype", mimetype)
        for name, body in extra_parts:
            archive.writestr(name, body)
    return stream.getvalue()


class SupportingDocUploadValidationTestCase(SimpleTestCase):
    """Strict validation for supporting-doc uploads."""

    def _upload(self, name, data, content_type):
        return SimpleUploadedFile(name, data, content_type=content_type)

    def test_pdf_header_and_eof_required(self):
        """A PDF body without %%EOF is rejected."""
        uploaded_file = self._upload(
            "report.pdf", _pdf_bytes(include_eof=False), "application/pdf"
        )

        with self.assertRaisesRegex(UploadValidationError, "PDF EOF"):
            validate_uploaded_file(
                uploaded_file,
                SUPPORTING_DOC_ALLOWED_EXTENSIONS,
                SUPPORTING_DOC_UPLOAD_CONTEXT,
            )

    def test_pdf_with_javascript_action_rejected(self):
        """A PDF containing a /JavaScript action is rejected."""
        uploaded_file = self._upload(
            "report.pdf",
            _pdf_bytes(body=b"1 0 obj <</S /JavaScript /JS (alert(1))>> endobj\n"),
            "application/pdf",
        )

        with self.assertRaisesRegex(UploadValidationError, "JavaScript"):
            validate_uploaded_file(
                uploaded_file,
                SUPPORTING_DOC_ALLOWED_EXTENSIONS,
                SUPPORTING_DOC_UPLOAD_CONTEXT,
            )

    def test_docx_structure_validated(self):
        """A .docx archive lacking word/document.xml is rejected."""
        data = _ooxml_bytes([("[Content_Types].xml", b"<types/>")])
        uploaded_file = self._upload(
            "report.docx",
            data,
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document",
        )

        with self.assertRaisesRegex(UploadValidationError, "DOCX required entries"):
            validate_uploaded_file(
                uploaded_file,
                SUPPORTING_DOC_ALLOWED_EXTENSIONS,
                SUPPORTING_DOC_UPLOAD_CONTEXT,
            )

    def test_pptx_structure_validated(self):
        """A .pptx archive lacking ppt/presentation.xml is rejected."""
        data = _ooxml_bytes([("[Content_Types].xml", b"<types/>")])
        uploaded_file = self._upload(
            "deck.pptx",
            data,
            "application/vnd.openxmlformats-officedocument."
            "presentationml.presentation",
        )

        with self.assertRaisesRegex(UploadValidationError, "PPTX required entries"):
            validate_uploaded_file(
                uploaded_file,
                SUPPORTING_DOC_ALLOWED_EXTENSIONS,
                SUPPORTING_DOC_UPLOAD_CONTEXT,
            )

    def test_odt_mimetype_member_required(self):
        """ODT archives without a matching 'mimetype' entry are rejected."""
        data = _odf_bytes("application/vnd.oasis.opendocument.spreadsheet")
        uploaded_file = self._upload(
            "report.odt", data, "application/vnd.oasis.opendocument.text"
        )

        with self.assertRaisesRegex(UploadValidationError, "'mimetype' entry"):
            validate_uploaded_file(
                uploaded_file,
                SUPPORTING_DOC_ALLOWED_EXTENSIONS,
                SUPPORTING_DOC_UPLOAD_CONTEXT,
            )

    def test_geojson_type_required(self):
        """GeoJSON without a recognised 'type' field is rejected."""
        uploaded_file = self._upload(
            "shapes.geojson",
            b'{"properties": {}}',
            "application/geo+json",
        )

        with self.assertRaisesRegex(UploadValidationError, "valid 'type'"):
            validate_uploaded_file(
                uploaded_file,
                SUPPORTING_DOC_ALLOWED_EXTENSIONS,
                SUPPORTING_DOC_UPLOAD_CONTEXT,
            )

    def test_pdf_accepted(self):
        """A minimal valid PDF passes."""
        uploaded_file = self._upload("report.pdf", _pdf_bytes(), "application/pdf")

        result = validate_uploaded_file(
            uploaded_file,
            SUPPORTING_DOC_ALLOWED_EXTENSIONS,
            SUPPORTING_DOC_UPLOAD_CONTEXT,
        )
        self.assertEqual(result.extension, "pdf")
        self.assertNotEqual(result.storage_basename, "report.pdf")

    def test_odt_accepted(self):
        """A minimal valid ODT passes."""
        data = _odf_bytes("application/vnd.oasis.opendocument.text")
        uploaded_file = self._upload(
            "report.odt", data, "application/vnd.oasis.opendocument.text"
        )

        result = validate_uploaded_file(
            uploaded_file,
            SUPPORTING_DOC_ALLOWED_EXTENSIONS,
            SUPPORTING_DOC_UPLOAD_CONTEXT,
        )
        self.assertEqual(result.extension, "odt")

    @override_settings(
        STRICT_SUPPORTING_DOC_UPLOAD_TYPES=["application/pdf"],
    )
    def test_supporting_doc_operator_allowlist_narrows_extensions(self):
        """Narrowing the supporting-doc allowlist disables other extensions."""
        data = _odf_bytes("application/vnd.oasis.opendocument.text")
        uploaded_file = self._upload(
            "report.odt", data, "application/vnd.oasis.opendocument.text"
        )

        with self.assertRaisesRegex(
            UploadValidationError, "Unsupported file extension"
        ):
            validate_uploaded_file(
                uploaded_file,
                SUPPORTING_DOC_ALLOWED_EXTENSIONS,
                SUPPORTING_DOC_UPLOAD_CONTEXT,
            )
