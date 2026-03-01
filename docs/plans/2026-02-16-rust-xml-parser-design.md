# Design: Rust XML Submission Parser (`onadata_xml`)

**Date**: 2026-02-16
**Branch**: `rusty`
**Approach**: C -- Rust parser + Python cached wrapper (drop-in replacement)

## Problem

The `XFormInstanceParser` parses submission XML using Python's minidom (full DOM tree,
2-3x memory of raw XML). The same XML is parsed 6+ times per submission because
`get_dict()` is called independently by `save()`, `_set_geom()`, `get_expected_media()`,
and `get_full_dict()`. Each parse involves recursive DOM traversal, xpath computation
per node, recursive dict flattening, and recursive numeric conversion.

## Solution

A Rust native extension (`onadata_xml`) that parses XML in a single pass using
`quick-xml` (SAX-style, no DOM), returning all extracted data at once. A Python wrapper
class (`RustXFormInstanceParser`) provides the same interface as the existing parser,
so callers don't change.

## Rust Module: `onadata_xml`

### Crate Structure

```
rust/onadata_xml/
├── Cargo.toml
├── pyproject.toml
└── src/
    ├── lib.rs          # PyO3 module entry, parse_submission()
    ├── parser.rs       # Single-pass XML -> structured data
    ├── flatten.rs      # Iterative dict flattening (stack-based)
    ├── numeric.rs      # String -> int/float conversion
    └── geom.rs         # Geopoint extraction from parsed data
```

### Core Function

```rust
#[pyfunction]
fn parse_submission(
    xml_str: &str,
    repeat_xpaths: Vec<String>,
    encrypted: bool,
    numeric_fields: HashSet<String>,
    geo_xpaths: Vec<String>,
) -> PyResult<SubmissionResult> { ... }
```

### SubmissionResult Fields

| Field | Type | Replaces |
|---|---|---|
| `dict` | `dict` | `_xml_node_to_dict()` output |
| `flat_dict` | `dict` | `_flatten_dict_nest_repeats()` + `numeric_converter()` |
| `attributes` | `dict[str, str]` | `_get_all_attributes()` + `_set_attributes()` |
| `root_node_name` | `str` | `_root_node.nodeName` |
| `uuid` | `Optional[str]` | `get_uuid_from_xml()` |
| `deprecated_uuid` | `Optional[str]` | `get_deprecated_uuid_from_xml()` |
| `submission_date` | `Optional[str]` | `get_submission_date_from_xml()` |
| `geom_points` | `list[tuple[float, float]]` | `_set_geom()` point extraction |
| `checksum` | `str` | `sha256(xml).hexdigest()` |

### Rust Crates

- `quick-xml` -- SAX-style streaming parser (no DOM, ~10x faster than minidom)
- `sha2` -- native SHA256
- `pyo3` -- Python bindings

### Parser Algorithm

Single pass over XML using `quick-xml::Reader`. Maintains a stack of node names for
xpath computation. As it encounters relevant nodes, it accumulates:

1. The nested dict structure (handling repeats via the `repeat_xpaths` set)
2. Attributes (skipping `entity` node attributes)
3. UUID from `meta/instanceID` or root `instanceID` attribute
4. Deprecated UUID from `meta/deprecatedID`
5. Submission date from root `submissionDate` attribute
6. Text values with numeric conversion applied inline

After the parse pass, a second in-Rust step:

1. Flattens the dict iteratively (stack-based, not recursive)
2. Extracts geopoints from fields matching `geo_xpaths`
3. Computes SHA256 checksum

All returned to Python as a single `SubmissionResult` object.

## Python Wrapper: `RustXFormInstanceParser`

Lives in `onadata/apps/logger/xform_instance_parser.py`, same file as the original.

```python
class RustXFormInstanceParser:
    def __init__(self, xml_str, data_dictionary):
        self.data_dicionary = data_dictionary
        repeat_xpaths = [
            get_abbreviated_xpath(e.get_xpath())
            for e in data_dictionary.get_survey_elements_of_type("repeat")
        ]
        numeric_fields = get_numeric_fields(data_dictionary)
        geo_xpaths = data_dictionary.geopoint_xpaths()

        from onadata_xml import parse_submission
        self._result = parse_submission(
            xml_str, repeat_xpaths, data_dictionary.encrypted,
            numeric_fields, geo_xpaths,
        )

    def to_dict(self):
        return self._result.dict

    def to_flat_dict(self):
        return self._result.flat_dict

    def get_root_node(self):
        return None  # DOM node not available; callers only use root_node_name

    def get_root_node_name(self):
        return self._result.root_node_name

    def get_attributes(self):
        return self._result.attributes

    def get_xform_id_string(self):
        return self._result.attributes["id"]

    def get_version(self):
        return self._result.attributes.get("version")

    def get_flat_dict_with_attributes(self):
        result = self.to_flat_dict().copy()
        result[XFORM_ID_STRING] = self.get_xform_id_string()
        version = self.get_version()
        if version:
            result[VERSION] = version
        return result
```

## Integration Points

### `Instance._set_parser()` (instance.py:516)

```python
def _set_parser(self):
    if not hasattr(self, "_parser"):
        if settings.USE_RUST_XML_PARSER:
            self._parser = RustXFormInstanceParser(self.xml, self.xform)
        else:
            self._parser = XFormInstanceParser(self.xml, self.xform)
```

### `Instance._set_geom()` (instance.py:416)

Reads from cached result instead of re-parsing:

```python
def _set_geom(self):
    self._set_parser()
    if settings.USE_RUST_XML_PARSER and hasattr(self._parser, '_result'):
        points = [Point(lng, lat) for lat, lng in self._parser._result.geom_points]
    else:
        # existing code path
        ...
```

### `Instance._set_uuid()` (instance.py:528)

Reads from cached result:

```python
def _set_uuid(self):
    if self.xml and not self.uuid:
        if settings.USE_RUST_XML_PARSER and hasattr(self, '_parser'):
            uuid = self._parser._result.uuid
        else:
            uuid = get_uuid_from_xml(self.xml)
        if uuid is not None:
            self.uuid = uuid
    set_uuid(self)
```

### `create_instance()` in `logger_tools.py`

The `sha256(xml).hexdigest()` call (line 637) can use `self._parser._result.checksum`
when the Rust parser is active, avoiding a redundant hash computation.

## Feature Flag & Rollout

### Settings

```python
# onadata/settings/common.py
USE_RUST_XML_PARSER = False
RUST_XML_PARSER_SHADOW_MODE = False
```

### Shadow Mode

Run both parsers, compare outputs, log differences:

```python
def _set_parser(self):
    if not hasattr(self, "_parser"):
        self._parser = XFormInstanceParser(self.xml, self.xform)
        if settings.RUST_XML_PARSER_SHADOW_MODE:
            rust_parser = RustXFormInstanceParser(self.xml, self.xform)
            _compare_parser_outputs(self._parser, rust_parser, self.pk)
```

### Rollout Sequence

1. Shadow mode in staging -- validate output parity
2. Feature flag on in production
3. Remove Python parser + shadow mode after validation

## Error Handling

| Condition | Exception |
|---|---|
| Empty XML / no children | `InstanceEmptyError` |
| Malformed XML | `InstanceParseError` |
| No survey element | `ValueError` |
| Missing `id` attribute | `KeyError` |

Rust module imports and raises existing Python exception classes via PyO3.

## Testing Strategy

### Layer 1: Rust Unit Tests (`cargo test`)

- Simple flat forms
- Repeat groups (single and nested)
- CDATA sections
- Encrypted submissions with `<media>` nodes
- Entity metadata (entity node attributes skipped)
- Missing/empty nodes
- Geopoint extraction (valid, malformed, multiple)
- Numeric conversion edge cases (int, float, NaN, empty string)
- UUID extraction from `<meta><instanceID>` and from root attribute
- SHA256 checksum correctness

### Layer 2: Python Integration Tests

Run existing `XFormInstanceParser` test fixtures against `RustXFormInstanceParser`,
assert identical outputs for `to_dict()`, `to_flat_dict()`,
`get_flat_dict_with_attributes()`, `get_root_node_name()`, `get_attributes()`.

### Layer 3: Shadow Mode

Comparison logging in staging against real-world submissions.

## Build & CI

### pyproject.toml (rust/onadata_xml/)

```toml
[build-system]
requires = ["maturin>=1.0,<2.0"]
build-backend = "maturin"

[project]
name = "onadata-xml"
requires-python = ">=3.10"

[tool.maturin]
features = ["pyo3/extension-module"]
```

### CI Additions

- Install Rust toolchain (`rustup`) in CI
- `cd rust/onadata_xml && maturin develop` before running Python tests
- `cargo test` as separate CI step for Rust unit tests

### Dev Workflow

- `maturin develop` builds and installs into active virtualenv
- Rust code changes require re-running `maturin develop`
- Python wrapper changes reload normally
