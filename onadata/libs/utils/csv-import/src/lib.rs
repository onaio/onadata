use std::collections::HashMap;

use pyo3::{exceptions::PyValueError, prelude::*, types::PyDict};

#[derive(Debug, Clone)]
struct InvalidCSVFile {
    msg: String,
}

impl InvalidCSVFile {
    fn new(msg: &str) -> Self {
        InvalidCSVFile {
            msg: msg.to_string(),
        }
    }
}

impl std::fmt::Display for InvalidCSVFile {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        write!(f, "CSV File failed validation: {}", self.msg)
    }
}

impl std::convert::From<InvalidCSVFile> for PyErr {
    fn from(err: InvalidCSVFile) -> Self {
        PyValueError::new_err(err.to_string())
    }
}

#[pyfunction]
pub fn validate_csv_file(
    csv_path: String,
    columns_with_type: HashMap<String, String>,
) -> PyResult<Vec<String>> {
    let mut reader = csv::Reader::from_path(csv_path)
        .map_err(|_| InvalidCSVFile::new("Failed to open CSV File"))?;

    let headers: Vec<String> = reader
        .headers()
        .map_err(|_| InvalidCSVFile::new("Failed to read headers"))?
        .iter()
        .map(|header| header.to_string())
        .collect();

    let missing_headers: Vec<String> = columns_with_type
        .iter()
        .filter_map(|(key, value)| {
            if !headers.contains(key) && value != "select all that apply" {
                Some(key.to_owned())
            } else {
                None
            }
        })
        .collect();

    if missing_headers.len() > 0 {
        return Err(PyValueError::new_err(format!(
            "Imported CSV is missing the following fields: {}",
            missing_headers.join(", ")
        )));
    }

    let additional_columns: Vec<String> = headers.iter().filter_map(|header| {
        if !columns_with_type.contains_key(header) && !header.contains("[") {
            Some(header.to_owned())
        } else {
            None
        }
    }).collect();

    Ok(additional_columns)
}

#[pymodule]
fn import_helper(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(validate_csv_file, m)?)?;
    Ok(())
}
