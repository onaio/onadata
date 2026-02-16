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
