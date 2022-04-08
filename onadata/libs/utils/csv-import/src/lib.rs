use pyo3::prelude::*;
use std::collections::{HashMap, HashSet};
use std::fmt;
use std::fs;
use std::ops::ControlFlow;

use csv;

const IGNORED_COLUMNS: Vec<&str> = vec![];

#[derive(Debug, Clone)]
struct InvalidCSVFile {
    msg: String,
}

impl fmt::Display for InvalidCSVFile {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "CSV File failed validation: {}", self.msg)
    }
}

fn validate_csv_file(
    csv_path: &String,
    columns_with_type: &HashMap<String, String>,
) -> Result<Vec<String>, InvalidCSVFile> {
    let mut reader: csv::Reader<fs::File> =
        csv::Reader::from_path(csv_path).map_err(|_| InvalidCSVFile {
            msg: String::from("Failed to read CSV File"),
        })?;
    let mut missing_headers: Vec<String> = Vec::new();

    let headers = reader.headers().map_err(|_| InvalidCSVFile {
        msg: String::from("Failed to read CSV Headers"),
    })?;

    let headers: Vec<String> = headers.iter().map(|record| record.to_string()).collect();

    columns_with_type.iter().for_each(|(key, value)| {
        if !headers.contains(key) && value != "select all that apply" {
            missing_headers.push(key.to_string());
        }
    });

    if missing_headers.len() > 0 {
        return Err(InvalidCSVFile {
            msg: format!("Missing headers: {:?}", missing_headers.to_vec()),
        });
    }

    let mut additional_columns = Vec::new();

    headers.iter().for_each(|header| {
        if !columns_with_type.contains_key(header) && !header.to_string().contains("[") {
            additional_columns.push(header.to_string())
        }
    });

    Ok(additional_columns)
}

fn import_csv(
    csv_path: String,
    columns_with_type: HashMap<String, String>,
) -> Result<(), InvalidCSVFile> {
    let additional_columns = validate_csv_file(&csv_path, &columns_with_type)?;

    todo!()
}

#[cfg(test)]
mod tests {
    #[test]
    fn it_works() {
        let result = 2 + 2;
        assert_eq!(result, 4);
    }
}
