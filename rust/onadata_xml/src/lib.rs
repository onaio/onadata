use std::collections::HashSet;

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyNone, PyString};
use sha2::{Digest, Sha256};

mod flatten;
mod geom;
mod numeric;
mod parser;

use flatten::flatten_dict;
use geom::extract_geopoints;
use numeric::{numeric_checker, NumericValue};
use parser::{parse_xml, Value};

// ---------------------------------------------------------------------------
// SubmissionResult PyO3 class
// ---------------------------------------------------------------------------

#[pyclass]
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

// ---------------------------------------------------------------------------
// Value -> Python object conversion
// ---------------------------------------------------------------------------

/// Convert a parser::Value to a Python object.
///
/// - Value::Str -> Python str (or int/float if in numeric_fields)
/// - Value::Dict -> Python dict
/// - Value::List -> Python list
fn value_to_py(py: Python<'_>, value: &Value, numeric_fields: &HashSet<String>, current_key: &str) -> PyResult<PyObject> {
    match value {
        Value::Str(s) => {
            if numeric_fields.contains(current_key) {
                match numeric_checker(s) {
                    NumericValue::Int(i) => Ok(i.into_pyobject(py)?.into_any().unbind()),
                    NumericValue::Float(f) => Ok(f.into_pyobject(py)?.into_any().unbind()),
                    NumericValue::Str(s) => Ok(PyString::new(py, &s).into_any().unbind()),
                }
            } else {
                Ok(PyString::new(py, s).into_any().unbind())
            }
        }
        Value::Dict(pairs) => {
            let dict = PyDict::new(py);
            for (key, val) in pairs {
                let py_val = value_to_py(py, val, numeric_fields, key)?;
                dict.set_item(key, py_val)?;
            }
            Ok(dict.into_any().unbind())
        }
        Value::List(items) => {
            let list = PyList::empty(py);
            for item in items {
                let py_item = value_to_py(py, item, numeric_fields, current_key)?;
                list.append(py_item)?;
            }
            Ok(list.into_any().unbind())
        }
    }
}

/// Convert a flat dict (Vec of (String, Value)) to a Python dict.
///
/// The numeric_fields set contains abbreviated xpaths that should be converted
/// to numeric values. This matches Python's `numeric_converter` which walks the
/// flat dict recursively.
fn flat_dict_to_py(
    py: Python<'_>,
    flat: &[(String, Value)],
    numeric_fields: &HashSet<String>,
) -> PyResult<PyObject> {
    let dict = PyDict::new(py);
    for (key, value) in flat {
        let py_val = value_to_py(py, value, numeric_fields, key)?;
        dict.set_item(key, py_val)?;
    }
    Ok(dict.into_any().unbind())
}

// ---------------------------------------------------------------------------
// SHA256 checksum
// ---------------------------------------------------------------------------

fn sha256_hex(data: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data.as_bytes());
    format!("{:x}", hasher.finalize())
}

// ---------------------------------------------------------------------------
// parse_submission pyfunction
// ---------------------------------------------------------------------------

/// Parse an XML submission and return a SubmissionResult.
///
/// Arguments:
/// - xml_str: The raw XML string
/// - repeat_xpaths: List of xpaths that should be treated as repeating groups
/// - encrypted: Whether the form is encrypted (forces "media" to be list-type)
/// - numeric_fields: Set of abbreviated xpaths for numeric conversion
/// - geo_xpaths: List of field names for geopoint extraction
#[pyfunction]
#[pyo3(signature = (xml_str, repeat_xpaths, encrypted, numeric_fields, geo_xpaths))]
fn parse_submission(
    py: Python<'_>,
    xml_str: &str,
    repeat_xpaths: Vec<String>,
    encrypted: bool,
    numeric_fields: HashSet<String>,
    geo_xpaths: Vec<String>,
) -> PyResult<SubmissionResult> {
    // Parse XML
    let parse_result = parse_xml(xml_str, &repeat_xpaths, encrypted)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))?;

    // Build Python dict from parsed Value tree
    let py_dict = match &parse_result.dict {
        Some(dict) => value_to_py(py, dict, &numeric_fields, "")?,
        None => PyNone::get(py).to_owned().into_any().unbind(),
    };

    // Build flat dict
    let flat = match &parse_result.dict {
        Some(dict) => flatten_dict(dict),
        None => Vec::new(),
    };
    let py_flat_dict = flat_dict_to_py(py, &flat, &numeric_fields)?;

    // Build attributes dict
    let attrs_dict = PyDict::new(py);
    for (key, value) in &parse_result.attributes {
        attrs_dict.set_item(key, value)?;
    }

    // Extract geopoints from the nested dict
    let geom_points = match &parse_result.dict {
        Some(dict) => extract_geopoints(dict, &geo_xpaths),
        None => Vec::new(),
    };

    // SHA256 of original XML string
    let checksum = sha256_hex(xml_str);

    Ok(SubmissionResult {
        dict: py_dict,
        flat_dict: py_flat_dict,
        attributes: attrs_dict.into_any().unbind(),
        root_node_name: parse_result.root_node_name,
        uuid: parse_result.uuid,
        deprecated_uuid: parse_result.deprecated_uuid,
        submission_date: parse_result.submission_date,
        geom_points,
        checksum,
    })
}

#[pymodule]
fn onadata_xml(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<SubmissionResult>()?;
    m.add_function(wrap_pyfunction!(parse_submission, m)?)?;
    Ok(())
}
