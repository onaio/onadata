# Rust XML Submission Parser Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace Python's minidom-based XML submission parser with a single-pass Rust native extension that eliminates 6+ redundant parses per submission.

**Architecture:** A PyO3 Rust crate (`onadata_xml`) exposes a `parse_submission()` function. A Python wrapper class (`RustXFormInstanceParser`) provides an identical interface to the existing `XFormInstanceParser`. Feature-flagged via `USE_RUST_XML_PARSER` setting.

**Tech Stack:** Rust, PyO3, maturin, quick-xml, sha2

---

### Task 1: Scaffold the Rust Crate

**Files:**
- Create: `rust/onadata_xml/Cargo.toml`
- Create: `rust/onadata_xml/pyproject.toml`
- Create: `rust/onadata_xml/src/lib.rs`

**Step 1: Create directory structure**

Run: `mkdir -p rust/onadata_xml/src`

**Step 2: Create Cargo.toml**

Create `rust/onadata_xml/Cargo.toml`:

```toml
[package]
name = "onadata_xml"
version = "0.1.0"
edition = "2021"

[lib]
name = "onadata_xml"
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.23", features = ["extension-module"] }
quick-xml = "0.37"
sha2 = "0.10"
```

**Step 3: Create pyproject.toml**

Create `rust/onadata_xml/pyproject.toml`:

```toml
[build-system]
requires = ["maturin>=1.0,<2.0"]
build-backend = "maturin"

[project]
name = "onadata-xml"
requires-python = ">=3.9"

[tool.maturin]
features = ["pyo3/extension-module"]
```

**Step 4: Create minimal lib.rs**

Create `rust/onadata_xml/src/lib.rs`:

```rust
use pyo3::prelude::*;

#[pyfunction]
fn parse_submission(xml_str: &str) -> PyResult<String> {
    Ok(format!("received {} bytes", xml_str.len()))
}

#[pymodule]
fn onadata_xml(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_submission, m)?)?;
    Ok(())
}
```

**Step 5: Build and verify**

Run: `cd rust/onadata_xml && maturin develop`
Expected: Builds successfully, installs into virtualenv

Run: `python -c "from onadata_xml import parse_submission; print(parse_submission('<test/>'))"`
Expected: `received 7 bytes`

**Step 6: Commit**

```bash
git add rust/
git commit -m "feat: scaffold onadata_xml Rust crate with PyO3 + maturin"
```

---

### Task 2: Implement the Core XML-to-Dict Parser in Rust

**Files:**
- Create: `rust/onadata_xml/src/parser.rs`
- Modify: `rust/onadata_xml/src/lib.rs`

**Step 1: Write Rust unit tests for XML-to-dict conversion**

Add to `rust/onadata_xml/src/parser.rs` the parser module with tests. The parser
must handle these cases (matching Python's `_xml_node_to_dict` behavior):

- Leaf text nodes → `{"nodeName": "textValue"}`
- Empty nodes → skipped (None)
- CDATA sections → `{"parentNodeName": "cdataValue"}`
- Repeat groups (xpaths in `repeat_xpaths`) → values collected into lists
- Encrypted forms with `<media>` nodes → treated as repeats
- Nested repeats → lists of dicts inside lists
- Duplicate node names not in repeats → aggregated into lists

Test cases from existing fixtures:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_simple_flat_form() {
        let xml = r#"<tutorial id="tutorial"><name>Larry</name><age>23</age></tutorial>"#;
        let result = xml_to_dict(xml, &[], false);
        // result["tutorial"]["name"] == "Larry"
        // result["tutorial"]["age"] == "23"
    }

    #[test]
    fn test_repeat_nodes() {
        // From repeated_nodes.xml fixture
        let xml = r#"<RW id="R" version="1"><S2A><S2_1>1</S2_1></S2A><S2A><S2_2>2</S2_2></S2A></RW>"#;
        let result = xml_to_dict(xml, &["S2A"], false);
        // result["RW"]["S2A"] is a list of 2 dicts
    }

    #[test]
    fn test_encrypted_media_nodes() {
        let xml = r#"<data id="enc" encrypted="yes"><media><file>a.enc</file></media><media><file>b.enc</file></media></data>"#;
        let result = xml_to_dict(xml, &[], true);
        // result["data"]["media"] is a list of 2 dicts
    }

    #[test]
    fn test_empty_nodes_skipped() {
        let xml = r#"<form id="f"><note/><val>x</val></form>"#;
        let result = xml_to_dict(xml, &[], false);
        // result["form"] has only "val", no "note"
    }
}
```

**Step 2: Run Rust tests to verify they fail**

Run: `cd rust/onadata_xml && cargo test`
Expected: Compilation errors (functions don't exist yet)

**Step 3: Implement `xml_to_dict` using quick-xml**

In `rust/onadata_xml/src/parser.rs`, implement a stack-based SAX parser using
`quick-xml::Reader`. The algorithm:

1. Create a stack of `(node_name, HashMap)` entries
2. On `Event::Start(tag)` → push new frame onto stack, compute xpath from stack
3. On `Event::Text(text)` → set text value on current frame
4. On `Event::CData(text)` → set CDATA value on parent frame
5. On `Event::End(tag)` → pop frame, merge into parent:
   - If xpath is in `repeat_xpaths` or (encrypted && name == "media") → append to list
   - Else if key already exists → convert to list and append
   - Else → insert as dict value
6. On `Event::Empty(tag)` → skip (empty node, matches Python's `return None`)

The function returns a `PyObject` (Python dict) via PyO3.

Key types:

```rust
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyString};
use quick_xml::events::Event;
use quick_xml::Reader;
use std::collections::HashSet;

pub fn xml_to_dict(
    py: Python<'_>,
    xml_str: &str,
    repeat_xpaths: &HashSet<String>,
    encrypted: bool,
) -> PyResult<PyObject> { ... }
```

**Step 4: Run Rust tests to verify they pass**

Run: `cd rust/onadata_xml && cargo test`
Expected: All tests pass

**Step 5: Commit**

```bash
git add rust/onadata_xml/src/parser.rs rust/onadata_xml/src/lib.rs
git commit -m "feat: implement xml_to_dict parser using quick-xml"
```

---

### Task 3: Implement Dict Flattening

**Files:**
- Create: `rust/onadata_xml/src/flatten.rs`
- Modify: `rust/onadata_xml/src/lib.rs`

**Step 1: Write Rust unit tests for flattening**

Must match Python's `_flatten_dict_nest_repeats` behavior:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_flatten_simple() {
        // {"form": {"info": {"name": "Adam", "age": "80"}}}
        // → {"info/name": "Adam", "info/age": "80"}
    }

    #[test]
    fn test_flatten_repeats() {
        // {"form": {"kids": [{"name": "Abel"}, {"name": "Cain"}]}}
        // → {"kids": [{"kids/name": "Abel"}, {"kids/name": "Cain"}]}
    }

    #[test]
    fn test_flatten_nested_repeats() {
        // Nested repeats produce nested lists of flattened dicts
    }
}
```

**Step 2: Run tests to verify they fail**

Run: `cd rust/onadata_xml && cargo test`
Expected: FAIL

**Step 3: Implement `flatten_dict` using iterative stack-based approach**

In `rust/onadata_xml/src/flatten.rs`:

```rust
pub fn flatten_dict_nest_repeats(
    py: Python<'_>,
    data_dict: &Bound<'_, PyDict>,
) -> PyResult<PyObject> { ... }
```

Uses a `Vec` as an explicit stack instead of recursion. Walks the nested dict,
building xpath keys by joining path components with "/". Lists produce sub-dicts
with flattened keys (matching Python behavior where repeats become
`[{"kids/kids_details/kids_name": "Abel"}]`).

**Step 4: Run tests to verify they pass**

Run: `cd rust/onadata_xml && cargo test`
Expected: PASS

**Step 5: Commit**

```bash
git add rust/onadata_xml/src/flatten.rs rust/onadata_xml/src/lib.rs
git commit -m "feat: implement iterative dict flattening for repeat groups"
```

---

### Task 4: Implement Numeric Conversion and Geom Extraction

**Files:**
- Create: `rust/onadata_xml/src/numeric.rs`
- Create: `rust/onadata_xml/src/geom.rs`
- Modify: `rust/onadata_xml/src/lib.rs`

**Step 1: Write Rust tests for numeric conversion**

Must match Python's `numeric_checker` (instance.py:152-166):
- `"42"` → `42` (int)
- `"3.14"` → `3.14` (float)
- `"NaN"` → `0` (matches Python: `0 if math.isnan(value) else value`)
- `"hello"` → `"hello"` (unchanged)
- `""` → `""` (unchanged)
- `"-7"` → `-7` (negative int)

```rust
#[test]
fn test_numeric_checker() {
    assert_eq!(numeric_check("42"), Value::Int(42));
    assert_eq!(numeric_check("3.14"), Value::Float(3.14));
    assert_eq!(numeric_check("NaN"), Value::Int(0));
    assert_eq!(numeric_check("hello"), Value::Str("hello".into()));
}
```

**Step 2: Write Rust tests for geopoint extraction**

Must match `_set_geom` behavior (instance.py:416-441):
- Input: flat dict + geo_xpaths list
- Searches flat dict values for matching keys
- Splits GPS string `"-1.2627 36.7926 0.0 30.0"` into `(lat, lng)` tuple
- Returns `Vec<(f64, f64)>`

```rust
#[test]
fn test_extract_geopoints() {
    // flat_dict with "gps" = "-1.2627 36.7926 0.0 30.0"
    // geo_xpaths = ["gps"]
    // → [(−1.2627, 36.7926)]
}
```

**Step 3: Run tests to verify they fail**

Run: `cd rust/onadata_xml && cargo test`
Expected: FAIL

**Step 4: Implement numeric conversion**

In `rust/onadata_xml/src/numeric.rs`:

```rust
use pyo3::prelude::*;

/// Applies numeric conversion inline during dict construction.
/// Called on leaf text values when the xpath is in numeric_fields.
pub fn numeric_check(py: Python<'_>, value: &str) -> PyObject {
    if let Ok(i) = value.parse::<i64>() {
        return i.into_pyobject(py).unwrap().into_any().unbind();
    }
    if let Ok(f) = value.parse::<f64>() {
        if f.is_nan() {
            return 0i64.into_pyobject(py).unwrap().into_any().unbind();
        }
        return f.into_pyobject(py).unwrap().into_any().unbind();
    }
    PyString::new(py, value).into_any().unbind()
}
```

**Step 5: Implement geopoint extraction**

In `rust/onadata_xml/src/geom.rs`:

```rust
use pyo3::prelude::*;
use std::collections::HashSet;

/// Extracts (lat, lng) tuples from the flat dict for matching geo_xpaths.
/// Searches recursively through nested dicts/lists (matching get_values_matching_key).
pub fn extract_geopoints(
    py: Python<'_>,
    flat_dict: &Bound<'_, PyDict>,
    geo_xpaths: &HashSet<String>,
) -> PyResult<Vec<(f64, f64)>> { ... }
```

**Step 6: Run tests to verify they pass**

Run: `cd rust/onadata_xml && cargo test`
Expected: PASS

**Step 7: Commit**

```bash
git add rust/onadata_xml/src/numeric.rs rust/onadata_xml/src/geom.rs rust/onadata_xml/src/lib.rs
git commit -m "feat: add numeric conversion and geopoint extraction"
```

---

### Task 5: Wire Up the Full `parse_submission` Function

**Files:**
- Modify: `rust/onadata_xml/src/lib.rs`

**Step 1: Write Rust integration test for full parse_submission**

```rust
#[test]
fn test_parse_submission_full() {
    let xml = r#"<?xml version='1.0' ?><tutorial id="tutorial">
        <name>Larry</name><age>23</age>
        <gps>-1.2836198 36.8795437 0.0 1044.0</gps>
        <meta><instanceID>uuid:729f173c688e482486a48661700455ff</instanceID></meta>
    </tutorial>"#;

    Python::with_gil(|py| {
        let result = parse_submission(
            py, xml,
            vec![],        // repeat_xpaths
            false,         // encrypted
            HashSet::new(), // numeric_fields
            vec!["gps".into()], // geo_xpaths
        ).unwrap();

        // Verify all fields of SubmissionResult
        // result.root_node_name == "tutorial"
        // result.uuid == Some("729f173c688e482486a48661700455ff")
        // result.geom_points == [(-1.2836198, 36.8795437)]
        // result.checksum == sha256 of xml
        // result.attributes["id"] == "tutorial"
        // result.dict["tutorial"]["name"] == "Larry"
        // result.flat_dict["name"] == "Larry"
        // result.flat_dict["age"] == "23" (not in numeric_fields)
    });
}
```

**Step 2: Run test to verify it fails**

Run: `cd rust/onadata_xml && cargo test`
Expected: FAIL

**Step 3: Implement `parse_submission` and `SubmissionResult`**

In `rust/onadata_xml/src/lib.rs`:

```rust
use pyo3::prelude::*;
use pyo3::types::PyDict;
use sha2::{Sha256, Digest};
use std::collections::HashSet;

mod parser;
mod flatten;
mod numeric;
mod geom;

#[pyclass]
#[derive(Clone)]
pub struct SubmissionResult {
    #[pyo3(get)]
    pub dict: PyObject,
    #[pyo3(get)]
    pub flat_dict: PyObject,
    #[pyo3(get)]
    pub attributes: PyObject,
    #[pyo3(get)]
    pub root_node_name: String,
    #[pyo3(get)]
    pub uuid: Option<String>,
    #[pyo3(get)]
    pub deprecated_uuid: Option<String>,
    #[pyo3(get)]
    pub submission_date: Option<String>,
    #[pyo3(get)]
    pub geom_points: Vec<(f64, f64)>,
    #[pyo3(get)]
    pub checksum: String,
}

#[pyfunction]
fn parse_submission(
    py: Python<'_>,
    xml_str: &str,
    repeat_xpaths: Vec<String>,
    encrypted: bool,
    numeric_fields: HashSet<String>,
    geo_xpaths: Vec<String>,
) -> PyResult<SubmissionResult> {
    // 1. Clean XML (strip whitespace between tags)
    let clean_xml = clean_xml(xml_str);

    // 2. Parse XML to dict + extract attributes, uuid, etc.
    let parsed = parser::parse_full(py, &clean_xml, &repeat_xpaths.into_iter().collect(),
                                     encrypted, &numeric_fields)?;

    // 3. Flatten dict
    let flat_dict = flatten::flatten_dict_nest_repeats(py, &parsed.dict)?;

    // 4. Extract geopoints from the parsed dict
    let geo_set: HashSet<String> = geo_xpaths.into_iter().collect();
    let geom_points = geom::extract_geopoints(py, &parsed.dict, &geo_set)?;

    // 5. Compute SHA256
    let mut hasher = Sha256::new();
    hasher.update(xml_str.as_bytes());
    let checksum = format!("{:x}", hasher.finalize());

    Ok(SubmissionResult {
        dict: parsed.dict,
        flat_dict,
        attributes: parsed.attributes,
        root_node_name: parsed.root_node_name,
        uuid: parsed.uuid,
        deprecated_uuid: parsed.deprecated_uuid,
        submission_date: parsed.submission_date,
        geom_points,
        checksum,
    })
}

fn clean_xml(xml_str: &str) -> String {
    // Equivalent to: re.sub(r">\s+<", "><", xml_string.strip())
    let trimmed = xml_str.trim();
    let mut result = String::with_capacity(trimmed.len());
    let mut after_close = false;
    let mut whitespace_buf = String::new();
    for ch in trimmed.chars() {
        if after_close {
            if ch.is_whitespace() {
                whitespace_buf.push(ch);
                continue;
            } else if ch == '<' {
                // drop whitespace between > and <
                after_close = false;
                result.push('<');
                whitespace_buf.clear();
                continue;
            } else {
                // not followed by <, flush whitespace
                result.push_str(&whitespace_buf);
                whitespace_buf.clear();
                after_close = false;
            }
        }
        if ch == '>' {
            after_close = true;
            whitespace_buf.clear();
        }
        result.push(ch);
    }
    result.push_str(&whitespace_buf);
    result
}

#[pymodule]
fn onadata_xml(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_submission, m)?)?;
    m.add_class::<SubmissionResult>()?;
    Ok(())
}
```

**Step 4: Run tests to verify they pass**

Run: `cd rust/onadata_xml && cargo test`
Expected: PASS

**Step 5: Build and smoke test from Python**

Run: `cd rust/onadata_xml && maturin develop`

Run:
```python
python -c "
from onadata_xml import parse_submission
r = parse_submission(
    '<tutorial id=\"tutorial\"><name>Larry</name><age>23</age><meta><instanceID>uuid:abc123</instanceID></meta></tutorial>',
    [], False, set(), []
)
print('root:', r.root_node_name)
print('uuid:', r.uuid)
print('dict:', r.dict)
print('flat:', r.flat_dict)
print('attrs:', r.attributes)
print('sha:', r.checksum[:16])
"
```

Expected: Prints correct parsed values.

**Step 6: Commit**

```bash
git add rust/onadata_xml/src/
git commit -m "feat: wire up full parse_submission with SubmissionResult"
```

---

### Task 6: Add the Python Wrapper Class

**Files:**
- Modify: `onadata/apps/logger/xform_instance_parser.py`

**Step 1: Write Python test for RustXFormInstanceParser**

Create test in `onadata/apps/logger/tests/test_rust_parsing.py`:

```python
"""Tests that RustXFormInstanceParser produces identical output to XFormInstanceParser."""
import os

from django.test import TestCase, override_settings

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.xform_instance_parser import (
    RustXFormInstanceParser,
    XFormInstanceParser,
)
from onadata.libs.utils.common_tags import XFORM_ID_STRING, VERSION


class TestRustXFormInstanceParser(TestBase):
    """Compare Rust parser output against Python parser for identical inputs."""

    def _publish_and_get_xml(self, fixture_dir, xls_name, xml_name):
        self._create_user_and_login()
        xls_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f"../fixtures/{fixture_dir}/{xls_name}",
        )
        self._publish_xls_file_and_set_xform(xls_path)
        xml_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f"../fixtures/{fixture_dir}/instances/{xml_name}",
        )
        with open(xml_path) as f:
            return f.read()

    @override_settings(USE_RUST_XML_PARSER=True)
    def test_nested_repeats_match(self):
        xml = self._publish_and_get_xml(
            "new_repeats", "new_repeats.xlsx",
            "new_repeats_2012-07-05-14-33-53.xml",
        )
        py_parser = XFormInstanceParser(xml, self.xform)
        rust_parser = RustXFormInstanceParser(xml, self.xform)

        self.assertEqual(py_parser.to_dict(), rust_parser.to_dict())
        self.assertEqual(py_parser.to_flat_dict(), rust_parser.to_flat_dict())
        self.assertEqual(
            py_parser.get_flat_dict_with_attributes(),
            rust_parser.get_flat_dict_with_attributes(),
        )
        self.assertEqual(py_parser.get_root_node_name(), rust_parser.get_root_node_name())
        self.assertEqual(py_parser.get_xform_id_string(), rust_parser.get_xform_id_string())

    @override_settings(USE_RUST_XML_PARSER=True)
    def test_encrypted_form_match(self):
        xml = self._publish_and_get_xml(
            "tutorial_encrypted", "tutorial_encrypted.xlsx",
            "tutorial_encrypted.xml",
        )
        py_parser = XFormInstanceParser(xml, self.xform)
        rust_parser = RustXFormInstanceParser(xml, self.xform)

        self.assertEqual(py_parser.to_dict(), rust_parser.to_dict())
        self.assertEqual(py_parser.to_flat_dict(), rust_parser.to_flat_dict())
```

**Step 2: Run test to verify it fails**

Run: `python manage.py test onadata.apps.logger.tests.test_rust_parsing -v2 --settings=onadata.settings.github_actions_test`
Expected: FAIL (RustXFormInstanceParser doesn't exist yet)

**Step 3: Add RustXFormInstanceParser to xform_instance_parser.py**

Add at the end of `onadata/apps/logger/xform_instance_parser.py`:

```python
class RustXFormInstanceParser:
    """Drop-in replacement for XFormInstanceParser using Rust native parser."""

    def __init__(self, xml_str, data_dictionary):
        self.data_dicionary = data_dictionary
        repeat_xpaths = [
            get_abbreviated_xpath(e.get_xpath())
            for e in data_dictionary.get_survey_elements_of_type("repeat")
        ]

        from onadata.libs.data.query import get_numeric_fields

        numeric_fields = set(get_numeric_fields(data_dictionary))
        geo_xpaths = (
            data_dictionary.geopoint_xpaths()
            if hasattr(data_dictionary, "geopoint_xpaths")
            else []
        )

        from onadata_xml import parse_submission

        self._result = parse_submission(
            smart_str(xml_str.strip()) if isinstance(xml_str, str) else xml_str,
            repeat_xpaths,
            data_dictionary.encrypted,
            numeric_fields,
            geo_xpaths,
        )

    def get_root_node(self):
        return None

    def get_root_node_name(self):
        return self._result.root_node_name

    def to_dict(self):
        return self._result.dict

    def to_flat_dict(self):
        return self._result.flat_dict

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

**Step 4: Run test to verify it passes**

Run: `python manage.py test onadata.apps.logger.tests.test_rust_parsing -v2 --settings=onadata.settings.github_actions_test`
Expected: PASS

**Step 5: Commit**

```bash
git add onadata/apps/logger/xform_instance_parser.py onadata/apps/logger/tests/test_rust_parsing.py
git commit -m "feat: add RustXFormInstanceParser wrapper class with parity tests"
```

---

### Task 7: Integrate Feature Flag and Wire Into Instance Model

**Files:**
- Modify: `onadata/settings/common.py`
- Modify: `onadata/apps/logger/models/instance.py`

**Step 1: Add feature flag settings**

Add to end of `onadata/settings/common.py`:

```python
# Rust XML parser feature flags
USE_RUST_XML_PARSER = False
RUST_XML_PARSER_SHADOW_MODE = False
```

**Step 2: Modify Instance._set_parser()**

In `onadata/apps/logger/models/instance.py`, line 516-520, change:

```python
def _set_parser(self):
    if not hasattr(self, "_parser"):
        self._parser = XFormInstanceParser(self.xml, self.xform)
```

To:

```python
def _set_parser(self):
    if not hasattr(self, "_parser"):
        if getattr(settings, "USE_RUST_XML_PARSER", False):
            from onadata.apps.logger.xform_instance_parser import (
                RustXFormInstanceParser,
            )
            self._parser = RustXFormInstanceParser(self.xml, self.xform)
        else:
            self._parser = XFormInstanceParser(self.xml, self.xform)
```

**Step 3: Modify Instance._set_geom() to use cached geom_points**

In `onadata/apps/logger/models/instance.py`, line 416-441, change `_set_geom`
to check for Rust parser result first:

```python
def _set_geom(self):
    xform = self.xform
    self._set_parser()

    if (
        getattr(settings, "USE_RUST_XML_PARSER", False)
        and hasattr(self._parser, "_result")
    ):
        points = [
            Point(lng, lat) for lat, lng in self._parser._result.geom_points
        ]
    else:
        geo_xpaths = xform.geopoint_xpaths()
        doc = self.get_dict()
        points = []
        if geo_xpaths:
            for xpath in geo_xpaths:
                for gps in get_values_matching_key(doc, xpath):
                    try:
                        geometry = [float(s) for s in gps.split()]
                        lat, lng = geometry[0:2]
                        points.append(Point(lng, lat))
                    except ValueError:
                        return

    if not xform.instances_with_geopoints and points:
        xform.instances_with_geopoints = True
        xform.save()

    if points:
        self.geom = GeometryCollection(points)
    else:
        self.geom = None
```

**Step 4: Modify Instance._set_uuid() to use cached uuid**

In `onadata/apps/logger/models/instance.py`, line 528-536, change:

```python
def _set_uuid(self):
    if self.xml and not self.uuid:
        if (
            getattr(settings, "USE_RUST_XML_PARSER", False)
            and hasattr(self, "_parser")
            and hasattr(self._parser, "_result")
        ):
            uuid = self._parser._result.uuid
        else:
            uuid = get_uuid_from_xml(self.xml)
        if uuid is not None:
            self.uuid = uuid
    set_uuid(self)
```

**Step 5: Run existing tests to verify no regression**

Run: `python manage.py test onadata.apps.logger.tests.test_parsing -v2 --settings=onadata.settings.github_actions_test`
Expected: PASS (feature flag is off, so existing Python path is used)

**Step 6: Run with feature flag on**

Run: `USE_RUST_XML_PARSER=True python manage.py test onadata.apps.logger.tests.test_parsing -v2 --settings=onadata.settings.github_actions_test`
Expected: PASS

**Step 7: Commit**

```bash
git add onadata/settings/common.py onadata/apps/logger/models/instance.py
git commit -m "feat: integrate Rust XML parser with feature flag in Instance model"
```

---

### Task 8: Add Shadow Mode for Safe Rollout

**Files:**
- Modify: `onadata/apps/logger/models/instance.py`

**Step 1: Implement shadow mode comparison**

Add a helper function to `onadata/apps/logger/models/instance.py`:

```python
def _compare_parser_outputs(py_parser, rust_parser, instance_pk):
    """Log differences between Python and Rust parser outputs."""
    logger = logging.getLogger("onadata.rust_parser_shadow")
    try:
        if py_parser.to_dict() != rust_parser.to_dict():
            logger.warning("dict mismatch for instance pk=%s", instance_pk)
        if py_parser.to_flat_dict() != rust_parser.to_flat_dict():
            logger.warning("flat_dict mismatch for instance pk=%s", instance_pk)
        if py_parser.get_root_node_name() != rust_parser.get_root_node_name():
            logger.warning("root_node_name mismatch for instance pk=%s", instance_pk)
    except Exception:
        logger.exception("Shadow mode comparison failed for instance pk=%s", instance_pk)
```

**Step 2: Wire shadow mode into _set_parser()**

Update `_set_parser`:

```python
def _set_parser(self):
    if not hasattr(self, "_parser"):
        if getattr(settings, "USE_RUST_XML_PARSER", False):
            from onadata.apps.logger.xform_instance_parser import (
                RustXFormInstanceParser,
            )
            self._parser = RustXFormInstanceParser(self.xml, self.xform)
        else:
            self._parser = XFormInstanceParser(self.xml, self.xform)

            if getattr(settings, "RUST_XML_PARSER_SHADOW_MODE", False):
                try:
                    from onadata.apps.logger.xform_instance_parser import (
                        RustXFormInstanceParser,
                    )
                    rust_parser = RustXFormInstanceParser(self.xml, self.xform)
                    _compare_parser_outputs(self._parser, rust_parser, self.pk)
                except Exception:
                    logger = logging.getLogger("onadata.rust_parser_shadow")
                    logger.exception("Shadow mode Rust parser failed for pk=%s", self.pk)
```

**Step 3: Run tests**

Run: `python manage.py test onadata.apps.logger.tests.test_parsing -v2 --settings=onadata.settings.github_actions_test`
Expected: PASS

**Step 4: Commit**

```bash
git add onadata/apps/logger/models/instance.py
git commit -m "feat: add shadow mode for Rust XML parser comparison logging"
```

---

### Task 9: Final Integration Test and Push

**Files:**
- Modify: `onadata/apps/logger/tests/test_rust_parsing.py`

**Step 1: Add end-to-end submission test with Rust parser**

Add to `test_rust_parsing.py`:

```python
@override_settings(USE_RUST_XML_PARSER=True)
def test_full_submission_with_rust_parser(self):
    """Test that a full submission round-trip works with the Rust parser."""
    self._create_user_and_login()
    xls_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "../fixtures/tutorial/tutorial.xlsx",
    )
    self._publish_xls_file_and_set_xform(xls_path)
    xml_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "../fixtures/tutorial/instances/tutorial_2012-06-27_11-27-53_w_uuid.xml",
    )
    self._make_submission(xml_path)
    self.assertEqual(self.response.status_code, 201)

    # Verify instance was saved correctly
    instance = self.xform.instances.first()
    self.assertIsNotNone(instance)
    self.assertEqual(instance.uuid, "729f173c688e482486a48661700455ff")

    # Verify get_dict works
    data = instance.get_dict()
    self.assertEqual(data.get("name"), "Larry\n        Again")
    self.assertEqual(data.get("age"), "23")
```

**Step 2: Run full test suite**

Run: `python manage.py test onadata.apps.logger -v2 --settings=onadata.settings.github_actions_test --parallel=4`
Expected: All existing tests PASS

**Step 3: Run with Rust parser enabled**

Run: `USE_RUST_XML_PARSER=True python manage.py test onadata.apps.logger.tests.test_rust_parsing -v2 --settings=onadata.settings.github_actions_test`
Expected: PASS

**Step 4: Commit and push**

```bash
git add onadata/apps/logger/tests/test_rust_parsing.py
git commit -m "test: add end-to-end submission test with Rust XML parser"
git push origin rusty
```

---

## Summary of Tasks

| Task | Description | Key Files |
|------|-------------|-----------|
| 1 | Scaffold Rust crate | `rust/onadata_xml/` |
| 2 | Core XML-to-dict parser | `src/parser.rs` |
| 3 | Dict flattening | `src/flatten.rs` |
| 4 | Numeric conversion + geom extraction | `src/numeric.rs`, `src/geom.rs` |
| 5 | Wire up `parse_submission` + `SubmissionResult` | `src/lib.rs` |
| 6 | Python wrapper class | `xform_instance_parser.py` |
| 7 | Feature flag + Instance model integration | `instance.py`, `common.py` |
| 8 | Shadow mode | `instance.py` |
| 9 | Final integration test + push | `test_rust_parsing.py` |
