# -*- coding: utf-8 -*-
"""
Strict upload validation helpers.
"""

import codecs
import csv
import io
import json
import os
import re
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import PurePath, PurePosixPath

from django.conf import settings
from django.utils.translation import gettext as _

import openpyxl
from defusedxml import ElementTree
from PIL import Image, UnidentifiedImageError

FORM_MEDIA_UPLOAD_CONTEXT = "form_media"
XLSFORM_UPLOAD_CONTEXT = "xlsform"
DATA_IMPORT_UPLOAD_CONTEXT = "data_import"
SUPPORTING_DOC_UPLOAD_CONTEXT = "supporting_doc"

FORM_MEDIA_ALLOWED_EXTENSIONS = (
    "csv",
    "geojson",
    "jpeg",
    "jpg",
    "mp4",
    "png",
    "xml",
)
XLSFORM_ALLOWED_EXTENSIONS = ("csv", "json", "xls", "xlsx", "xml")
SUPPORTING_DOC_ALLOWED_EXTENSIONS = (
    "csv",
    "docx",
    "geojson",
    "jpeg",
    "jpg",
    "json",
    "ods",
    "odp",
    "odt",
    "pdf",
    "png",
    "pptx",
    "xlsx",
)

FORM_MEDIA_DEFAULT_CONTENT_TYPES = (
    "image/jpeg",
    "image/png",
    "text/csv",
    "text/xml",
    "application/xml",
    "application/geo+json",
    "application/json",
    "video/mp4",
)

SUPPORTING_DOC_DEFAULT_CONTENT_TYPES = (
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.presentation",
    "application/geo+json",
    "application/json",
    "text/csv",
    # Images remain permitted for supporting documents (diagrams, scans,
    # screenshots) per existing product behaviour. SVG, DOC/PPT/XLS (OLE),
    # ZIP and audio types from the legacy allowlist remain removed.
    "image/jpeg",
    "image/png",
)

ODF_MIMETYPE_BY_EXTENSION = {
    "odt": "application/vnd.oasis.opendocument.text",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
    "odp": "application/vnd.oasis.opendocument.presentation",
}

OLE_COMPOUND_FILE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8"
ZIP_LOCAL_FILE_SIGNATURE = b"PK\x03\x04"

MP4_COMPATIBLE_BRANDS = {
    b"avc1",
    b"dash",
    b"isom",
    b"iso2",
    b"iso5",
    b"iso6",
    b"m4v ",
    b"M4V ",
    b"mp41",
    b"mp42",
}

UNKNOWN_CONTENT_TYPES = frozenset({"", "application/octet-stream"})

ALLOWED_UPLOAD_TYPES = {
    "csv": ("text/csv",),
    "docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    "geojson": ("application/geo+json", "application/json"),
    "json": ("application/json", "text/json"),
    "jpeg": ("image/jpeg",),
    "jpg": ("image/jpeg",),
    "mp4": ("video/mp4",),
    "odp": ("application/vnd.oasis.opendocument.presentation",),
    "ods": ("application/vnd.oasis.opendocument.spreadsheet",),
    "odt": ("application/vnd.oasis.opendocument.text",),
    "pdf": ("application/pdf",),
    "png": ("image/png",),
    "pptx": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ),
    "xml": ("application/xml", "text/xml"),
    "xls": ("application/vnd.ms-excel",),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",),
}


class UploadValidationError(ValueError):
    """Raised when an uploaded file violates strict upload policy."""


@dataclass(frozen=True)
class ValidatedUpload:
    """Validated upload metadata."""

    extension: str
    content_type: str
    original_name: str
    storage_basename: str


def normalize_content_type(content_type):
    """Return a normalized MIME type without parameters."""
    if not content_type:
        return ""
    return content_type.split(";")[0].strip().lower()


def sanitized_original_filename(name):
    """Return a display-safe basename from a submitted filename."""
    name = str(name or "").replace("\\", "/")
    basename = PurePosixPath(PurePath(name).name).name
    basename = re.sub(r"[\x00-\x1f\x7f]", "", basename).strip()
    return basename


def generic_upload_validation_error_message(uploaded_file, reason=None):
    """Return an API validation error that identifies the upload.

    When ``reason`` is provided (typically the :class:`UploadValidationError`
    raised by the validators), it is appended so API clients learn *why* the
    upload failed instead of only seeing the generic text. The validators
    raise static, non-sensitive descriptions of the rule that was violated
    (e.g. "CSV files must be UTF-8 encoded."), so surfacing them is safe.
    """
    filename = sanitized_original_filename(getattr(uploaded_file, "name", ""))

    if filename:
        message = _("The uploaded file '%(filename)s' could not be validated.") % {
            "filename": filename
        }
    else:
        message = _("The uploaded file could not be validated.")

    reason_text = str(reason).strip() if reason is not None else ""
    if reason_text:
        return f"{message} {reason_text}"

    return message


DANGEROUS_PENULTIMATE_EXTENSIONS = frozenset(
    {
        ".asp",
        ".aspx",
        ".bat",
        ".cgi",
        ".cmd",
        ".com",
        ".dll",
        ".exe",
        ".htm",
        ".html",
        ".jar",
        ".js",
        ".jse",
        ".jsp",
        ".msi",
        ".phar",
        ".php",
        ".phtml",
        ".pif",
        ".pl",
        ".ps1",
        ".py",
        ".rb",
        ".scr",
        ".sh",
        ".svg",
        ".vbe",
        ".vbs",
        ".ws",
        ".wsf",
        ".wsh",
    }
)


def reject_double_extension(name):
    """Reject filenames missing a suffix or with a dangerous penultimate suffix.

    The double-extension attack pattern (``putty.exe.png``) is blocked by
    rejecting any filename whose penultimate suffix is in
    :data:`DANGEROUS_PENULTIMATE_EXTENSIONS` (script/executable types that
    misconfigured servers may execute). Legitimate multi-dot filenames like
    ``report.v2.pdf`` or ``transportation.bad_id.xlsx`` are accepted; only
    the final suffix is used for extension/MIME matching downstream.
    """
    basename = sanitized_original_filename(name)
    suffixes = PurePath(basename).suffixes

    if not suffixes:
        raise UploadValidationError(
            _("Unsupported filename '%(basename)s'. A file extension is required.")
            % {"basename": basename}
        )

    if len(suffixes) > 1 and suffixes[-2].lower() in DANGEROUS_PENULTIMATE_EXTENSIONS:
        raise UploadValidationError(
            _(
                "Unsupported filename '%(basename)s'. "
                "The '%(suffix)s' suffix is not allowed."
            )
            % {"basename": basename, "suffix": suffixes[-2]}
        )

    return basename


DEFAULT_UPLOAD_MAX_BYTES = 1 * 1024 * 1024


def get_upload_max_bytes(context=None, extension=None):
    """Return the configured upload size limit for a context/extension.

    ``STRICT_UPLOAD_MAX_BYTES`` is a nested map where ``"*"`` is the global
    default cap and each context maps to ``{extension-or-"*": byte_cap}``.
    Resolution is most specific first:

    1. ``STRICT_UPLOAD_MAX_BYTES[context][extension]``
    2. ``STRICT_UPLOAD_MAX_BYTES[context]["*"]`` (whole-context cap)
    3. ``STRICT_UPLOAD_MAX_BYTES["*"]`` (global default)
    """
    config = getattr(settings, "STRICT_UPLOAD_MAX_BYTES", None)

    # Tolerate a bare int (legacy/simple config): treat it as the global cap.
    if isinstance(config, int):
        return config
    if not isinstance(config, dict):
        return DEFAULT_UPLOAD_MAX_BYTES

    context_caps = config.get(context)
    if isinstance(context_caps, dict):
        if extension is not None and extension in context_caps:
            return context_caps[extension]
        if "*" in context_caps:
            return context_caps["*"]

    return config.get("*", DEFAULT_UPLOAD_MAX_BYTES)


def get_form_media_allowed_content_types():
    """Return the operator-configurable form media MIME allowlist."""
    configured = getattr(settings, "STRICT_FORM_MEDIA_UPLOAD_TYPES", None)
    if configured is None:
        return {normalize_content_type(ct) for ct in FORM_MEDIA_DEFAULT_CONTENT_TYPES}
    return {normalize_content_type(ct) for ct in configured if ct}


def get_supporting_doc_allowed_content_types():
    """Return the operator-configurable supporting doc MIME allowlist."""
    configured = getattr(settings, "STRICT_SUPPORTING_DOC_UPLOAD_TYPES", None)
    if configured is None:
        return {
            normalize_content_type(ct) for ct in SUPPORTING_DOC_DEFAULT_CONTENT_TYPES
        }
    return {normalize_content_type(ct) for ct in configured if ct}


OPERATOR_ALLOWLIST_BY_CONTEXT = {
    FORM_MEDIA_UPLOAD_CONTEXT: get_form_media_allowed_content_types,
    SUPPORTING_DOC_UPLOAD_CONTEXT: get_supporting_doc_allowed_content_types,
}


def _seek_zero(uploaded_file):
    """Best-effort rewind of an upload to position 0."""
    try:
        uploaded_file.seek(0)
    except (AttributeError, OSError):
        pass


def _enforce_size_limit(uploaded_file, max_bytes):
    """Reject an upload whose reported size exceeds ``max_bytes``."""
    size = getattr(uploaded_file, "size", None)
    if size is not None and size > max_bytes:
        raise UploadValidationError(
            _("File exceeds the maximum upload size of %(max_bytes)d bytes.")
            % {"max_bytes": max_bytes}
        )


def _read_upload_bytes(uploaded_file, context, extension=None):
    max_bytes = get_upload_max_bytes(context, extension)
    _enforce_size_limit(uploaded_file, max_bytes)

    position = None
    try:
        position = uploaded_file.tell()
    except (AttributeError, OSError):
        pass

    _seek_zero(uploaded_file)

    data = uploaded_file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise UploadValidationError(
            _("File exceeds the maximum upload size of %(max_bytes)d bytes.")
            % {"max_bytes": max_bytes}
        )

    if isinstance(data, str):
        data = data.encode("utf-8")

    try:
        uploaded_file.seek(0 if position is None else position)
    except (AttributeError, OSError):
        pass

    return data


UPLOAD_CHUNK_SIZE = 64 * 1024
CSV_HEAD_SAMPLE_CHARS = 1 * 1024 * 1024
CSV_STRUCTURE_SAMPLE_ROWS = 10


def _assert_csv_has_rows(sample_text):
    """Confirm a CSV head sample parses and holds at least one row."""
    try:
        reader = csv.reader(io.StringIO(sample_text))
        row_count = 0
        for index, _row in enumerate(reader):
            row_count = index + 1
            if index >= CSV_STRUCTURE_SAMPLE_ROWS:
                break
    except csv.Error as error:
        raise UploadValidationError(
            _("CSV file content could not be parsed.")
        ) from error

    if row_count == 0:
        raise UploadValidationError(_("CSV files must contain at least one row."))


def _validate_csv_stream(uploaded_file, max_bytes):
    """Validate a CSV upload without holding the whole file in memory.

    NUL bytes and UTF-8 validity are checked across every 64 KB chunk while
    only a ~1 MB head sample is buffered for structural parsing. Cumulative
    bytes are counted so the cap is enforced even when ``.size`` is unavailable.
    """
    decoder = codecs.getincrementaldecoder("utf-8-sig")()
    head = io.StringIO()
    state = {"head_len": 0, "decoded_any": False}

    def accumulate(text):
        if not text:
            return
        state["decoded_any"] = True
        if state["head_len"] < CSV_HEAD_SAMPLE_CHARS:
            head.write(text[: CSV_HEAD_SAMPLE_CHARS - state["head_len"]])
            state["head_len"] += len(text)

    def decode(chunk, final=False):
        try:
            return decoder.decode(chunk, final)
        except UnicodeDecodeError as error:
            raise UploadValidationError(
                _("CSV files must be UTF-8 encoded.")
            ) from error

    total_bytes = 0
    _seek_zero(uploaded_file)
    try:
        while True:
            chunk = uploaded_file.read(UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8")

            if b"\x00" in chunk:
                raise UploadValidationError(_("CSV files must not contain NUL bytes."))

            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                raise UploadValidationError(
                    _("File exceeds the maximum upload size of %(max_bytes)d bytes.")
                    % {"max_bytes": max_bytes}
                )

            accumulate(decode(chunk))

        accumulate(decode(b"", final=True))
    finally:
        _seek_zero(uploaded_file)

    _assert_csv_has_rows(head.getvalue())

    if not state["decoded_any"]:
        raise UploadValidationError(_("CSV files must not be empty."))


def _validate_json(data):
    try:
        json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise UploadValidationError(
            _("JSON file content could not be parsed.")
        ) from error


def _validate_xml(data):
    try:
        ElementTree.fromstring(data)
    except Exception as error:  # defusedxml can raise several XML errors.
        raise UploadValidationError(
            _("XML file content could not be parsed.")
        ) from error


def _validate_png(data):
    if not data.startswith(PNG_SIGNATURE):
        raise UploadValidationError(_("PNG signature mismatch."))
    _validate_image(data, "PNG")


def _validate_jpeg(data):
    if not data.startswith(JPEG_SIGNATURE):
        raise UploadValidationError(_("JPEG signature mismatch."))
    _validate_image(data, "JPEG")


def _validate_image(data, expected_format):
    try:
        image = Image.open(io.BytesIO(data))
        image.verify()
    except (UnidentifiedImageError, OSError) as error:
        raise UploadValidationError(
            _("Image file content could not be verified.")
        ) from error

    if image.format != expected_format:
        raise UploadValidationError(
            _("Expected %(expected_format)s image content.")
            % {"expected_format": expected_format}
        )


def _validate_mp4(data):
    if len(data) < 16 or data[4:8] != b"ftyp":
        raise UploadValidationError(_("MP4 ftyp box not found."))

    box_size = int.from_bytes(data[:4], "big")
    if box_size < 16 or box_size > len(data):
        raise UploadValidationError(_("Invalid MP4 ftyp box."))

    major_brand = data[8:12]
    compatible_brands = {data[index : index + 4] for index in range(16, box_size, 4)}

    if major_brand not in MP4_COMPATIBLE_BRANDS and not (
        compatible_brands & MP4_COMPATIBLE_BRANDS
    ):
        raise UploadValidationError(_("Unsupported MP4 brand."))


# A legitimate ``ftyp`` box is tiny (size + type + brands); cap the read so a
# bogus box-size claim cannot make us read more than a few KB of a large file.
MP4_FTYP_READ_LIMIT = 4096


def _validate_mp4_stream(uploaded_file, max_bytes):  # pylint: disable=unused-argument
    """Validate an MP4 upload by reading only its leading ``ftyp`` box.

    Reads at most :data:`MP4_FTYP_READ_LIMIT` bytes regardless of file size; the
    overall size cap is enforced by the caller via ``.size``. Delegates the
    structural checks to :func:`_validate_mp4`.
    """
    _seek_zero(uploaded_file)
    try:
        header = uploaded_file.read(8)
        if isinstance(header, str):
            header = header.encode("utf-8")
        if len(header) < 8 or header[4:8] != b"ftyp":
            raise UploadValidationError(_("MP4 ftyp box not found."))

        box_size = int.from_bytes(header[:4], "big")
        to_read = min(max(box_size, 16), MP4_FTYP_READ_LIMIT) - len(header)
        rest = uploaded_file.read(to_read) if to_read > 0 else b""
        if isinstance(rest, str):
            rest = rest.encode("utf-8")
        _validate_mp4(header + rest)
    finally:
        _seek_zero(uploaded_file)


def _validate_xls(data):
    if not data.startswith(OLE_COMPOUND_FILE_SIGNATURE):
        raise UploadValidationError(_("XLS OLE compound file signature mismatch."))


def _validate_xlsx(data):
    if not data.startswith(ZIP_LOCAL_FILE_SIGNATURE):
        raise UploadValidationError(_("XLSX ZIP signature mismatch."))

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as xlsx:
            names = set(xlsx.namelist())
            if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
                raise UploadValidationError(_("XLSX workbook entries not found."))

        workbook = openpyxl.load_workbook(
            io.BytesIO(data), read_only=True, data_only=True
        )
        workbook.close()
    except UploadValidationError:
        raise
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        raise UploadValidationError(
            _("XLSX workbook content could not be parsed.")
        ) from error


PDF_HEADER_SIGNATURE = b"%PDF-"
PDF_EOF_MARKER = b"%%EOF"
PDF_JAVASCRIPT_MARKERS = (b"/JavaScript", b"/JS")


def _validate_pdf(data):
    if not data.startswith(PDF_HEADER_SIGNATURE):
        raise UploadValidationError(_("PDF header signature mismatch."))
    if PDF_EOF_MARKER not in data[-1024:]:
        raise UploadValidationError(_("PDF EOF marker not found."))
    for marker in PDF_JAVASCRIPT_MARKERS:
        if marker in data:
            raise UploadValidationError(
                _("PDF contains JavaScript actions which are not allowed.")
            )


def _validate_ooxml(data, label, required_entries):
    if not data.startswith(ZIP_LOCAL_FILE_SIGNATURE):
        raise UploadValidationError(
            _("%(label)s ZIP signature mismatch.") % {"label": label}
        )

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
            missing = [entry for entry in required_entries if entry not in names]
            if missing:
                raise UploadValidationError(
                    _("%(label)s required entries missing: %(missing)s.")
                    % {"label": label, "missing": ", ".join(sorted(missing))}
                )
    except (OSError, zipfile.BadZipFile) as error:
        raise UploadValidationError(
            _("%(label)s archive content could not be parsed.") % {"label": label}
        ) from error


def _validate_docx(data):
    _validate_ooxml(data, "DOCX", ("[Content_Types].xml", "word/document.xml"))


def _validate_pptx(data):
    _validate_ooxml(data, "PPTX", ("[Content_Types].xml", "ppt/presentation.xml"))


def _validate_odf(extension, data):
    expected_mimetype = ODF_MIMETYPE_BY_EXTENSION[extension]
    label = extension.upper()

    if not data.startswith(ZIP_LOCAL_FILE_SIGNATURE):
        raise UploadValidationError(
            _("%(label)s ZIP signature mismatch.") % {"label": label}
        )

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            if "mimetype" not in names:
                raise UploadValidationError(
                    _("%(label)s archive missing required 'mimetype' entry.")
                    % {"label": label}
                )
            mimetype_bytes = archive.read("mimetype")
    except (OSError, zipfile.BadZipFile) as error:
        raise UploadValidationError(
            _("%(label)s archive content could not be parsed.") % {"label": label}
        ) from error

    if mimetype_bytes.strip().decode("ascii", errors="replace") != expected_mimetype:
        raise UploadValidationError(
            _("%(label)s 'mimetype' entry does not match %(expected)s.")
            % {"label": label, "expected": expected_mimetype}
        )


def _validate_odt(data):
    _validate_odf("odt", data)


def _validate_ods(data):
    _validate_odf("ods", data)


def _validate_odp(data):
    _validate_odf("odp", data)


GEOJSON_OBJECT_TYPES = {
    "Feature",
    "FeatureCollection",
    "Point",
    "MultiPoint",
    "LineString",
    "MultiLineString",
    "Polygon",
    "MultiPolygon",
    "GeometryCollection",
}


def _validate_geojson(data):
    try:
        decoded = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise UploadValidationError(
            _("GeoJSON file content could not be parsed.")
        ) from error

    if not isinstance(decoded, dict):
        raise UploadValidationError(_("GeoJSON root must be an object."))

    if decoded.get("type") not in GEOJSON_OBJECT_TYPES:
        raise UploadValidationError(
            _("GeoJSON object must declare a valid 'type' field.")
        )


# Buffered validators read the whole file into memory. Formats that can be
# verified with a bounded read (csv, mp4) live in STREAMING_VALIDATORS instead
# and are dispatched in preference to this map.
CONTENT_VALIDATORS = {
    "docx": _validate_docx,
    "geojson": _validate_geojson,
    "json": _validate_json,
    "jpeg": _validate_jpeg,
    "jpg": _validate_jpeg,
    "odp": _validate_odp,
    "ods": _validate_ods,
    "odt": _validate_odt,
    "pdf": _validate_pdf,
    "png": _validate_png,
    "pptx": _validate_pptx,
    "xml": _validate_xml,
    "xls": _validate_xls,
    "xlsx": _validate_xlsx,
}

# Formats whose authenticity can be confirmed with a bounded read of a
# file-like object, so they may safely carry a large per-context cap. The
# overall size cap is enforced separately via ``.size`` before dispatch.
STREAMING_VALIDATORS = {
    "csv": _validate_csv_stream,
    "mp4": _validate_mp4_stream,
}


def validate_uploaded_file(uploaded_file, allowed_extensions, context):
    """
    Validate filename, MIME type, size, and content for an uploaded file.

    Returns a :class:`ValidatedUpload` and rewinds the file to position 0.
    """
    original_name = reject_double_extension(getattr(uploaded_file, "name", ""))
    extension = os.path.splitext(original_name)[1].lower().strip(".")
    allowed_extensions = {ext.lower().strip(".") for ext in allowed_extensions}

    operator_allowed_content_types = None
    operator_allowlist_loader = OPERATOR_ALLOWLIST_BY_CONTEXT.get(context)
    if operator_allowlist_loader is not None:
        operator_allowed_content_types = operator_allowlist_loader()
        allowed_extensions = {
            ext
            for ext in allowed_extensions
            if any(
                mime in operator_allowed_content_types
                for mime in ALLOWED_UPLOAD_TYPES.get(ext, ())
            )
        }

    if extension not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise UploadValidationError(
            _(
                "Unsupported file extension '.%(extension)s'. "
                "Allowed extensions: %(allowed)s."
            )
            % {"extension": extension, "allowed": allowed}
        )

    content_type = normalize_content_type(getattr(uploaded_file, "content_type", ""))
    valid_content_types = ALLOWED_UPLOAD_TYPES[extension]
    if operator_allowed_content_types is not None:
        valid_content_types = tuple(
            ct for ct in valid_content_types if ct in operator_allowed_content_types
        )

    if not valid_content_types:
        raise UploadValidationError(
            _("No allowed content types configured for '.%(extension)s'.")
            % {"extension": extension}
        )

    # Clients (Windows browsers, ODK Collect, curl without -H, mobile apps)
    # routinely send "application/octet-stream" or omit the content type
    # entirely. Treat those as "unknown" and rely on the magic-byte and
    # structural validators below to verify the file. A *declared* MIME that
    # disagrees with the extension is still rejected.
    if content_type in UNKNOWN_CONTENT_TYPES:
        content_type = valid_content_types[0]
    elif content_type not in valid_content_types:
        expected = ", ".join(valid_content_types)
        raise UploadValidationError(
            _(
                "Unsupported content type '%(content_type)s' "
                "for '.%(extension)s'. "
                "Expected: %(expected)s."
            )
            % {
                "content_type": content_type,
                "extension": extension,
                "expected": expected,
            }
        )

    streaming_validator = STREAMING_VALIDATORS.get(extension)
    if streaming_validator is not None:
        # mp4 reads only its header, so the cap is enforced up front via .size;
        # csv counts bytes as it streams to guard the cap when .size is absent.
        max_bytes = get_upload_max_bytes(context, extension)
        _enforce_size_limit(uploaded_file, max_bytes)
        streaming_validator(uploaded_file, max_bytes)
    else:
        data = _read_upload_bytes(uploaded_file, context, extension)
        CONTENT_VALIDATORS[extension](data)

    _seek_zero(uploaded_file)

    return ValidatedUpload(
        extension=extension,
        content_type=content_type,
        original_name=original_name,
        storage_basename=f"{uuid.uuid4().hex}.{extension}",
    )
