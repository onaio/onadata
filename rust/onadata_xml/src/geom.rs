/// Geopoint extraction module.
///
/// Replicates Python's `_set_geom` which:
/// 1. For each xpath in geo_xpaths, searches the NESTED dict recursively
///    for matching keys (using `get_values_matching_key` from dict_tools.py)
/// 2. Splits GPS string by whitespace, takes first 2 as (lat, lng) floats
///
/// The search function `get_values_matching_key` does a recursive traversal
/// of the entire dict structure, including into lists.
use crate::parser::Value;

/// Recursively search a Value tree for all values with a matching key.
///
/// Replicates Python's `get_values_matching_key(doc, key)` from dict_tools.py.
///
/// The Python code:
/// - If key in doc: yield doc[key]
/// - For each (k, v) in doc.items():
///   - If v is dict: recurse
///   - If v is list: for each item, if dict/list: recurse; elif item == key: yield item
fn get_values_matching_key<'a>(value: &'a Value, key: &str) -> Vec<&'a Value> {
    let mut results = Vec::new();

    match value {
        Value::Dict(pairs) => {
            // First check if this dict directly contains the key
            if let Some(v) = pairs.iter().find(|(k, _)| k == key) {
                results.push(&v.1);
            }

            // Then recurse into all values
            for (_k, v) in pairs {
                match v {
                    Value::Dict(_) => {
                        results.extend(get_values_matching_key(v, key));
                    }
                    Value::List(items) => {
                        for item in items {
                            match item {
                                Value::Dict(_) | Value::List(_) => {
                                    results.extend(get_values_matching_key(item, key));
                                }
                                Value::Str(s) if s == key => {
                                    results.push(item);
                                }
                                _ => {}
                            }
                        }
                    }
                    _ => {}
                }
            }
        }
        Value::List(items) => {
            for item in items {
                match item {
                    Value::Dict(_) | Value::List(_) => {
                        results.extend(get_values_matching_key(item, key));
                    }
                    Value::Str(s) if s == key => {
                        results.push(item);
                    }
                    _ => {}
                }
            }
        }
        _ => {}
    }

    results
}

/// Extract geopoints from the nested dict.
///
/// For each geo_xpath, search the nested dict recursively for matching keys.
/// For each matching value (GPS string), split by whitespace and take first 2 as (lat, lng).
///
/// Returns a list of (lat, lng) tuples. On any parse error for a geopoint,
/// returns early with the points collected so far (matching Python's `return` on ValueError).
pub fn extract_geopoints(dict: &Value, geo_xpaths: &[String]) -> Vec<(f64, f64)> {
    let mut points = Vec::new();

    for xpath in geo_xpaths {
        // Search the nested dict recursively for matching keys.
        // geo_xpaths contains abbreviated xpaths used as search keys.
        let values = get_values_matching_key(dict, xpath);
        for gps_val in values {
            if let Value::Str(gps_str) = gps_val {
                let parts: Vec<&str> = gps_str.split_whitespace().collect();
                if parts.len() >= 2 {
                    match (parts[0].parse::<f64>(), parts[1].parse::<f64>()) {
                        (Ok(lat), Ok(lng)) => {
                            points.push((lat, lng));
                        }
                        _ => {
                            // Python returns on ValueError, stopping all processing
                            return points;
                        }
                    }
                }
            }
        }
    }

    points
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parser::parse_xml;

    #[test]
    fn test_extract_gps_simple() {
        let xml = r#"<?xml version='1.0' ?><tutorial id="tutorial">
  <name>Larry</name>
  <gps>-1.2836198 36.8795437 0.0 1044.0</gps>
  <meta><instanceID>uuid:abc</instanceID></meta>
</tutorial>"#;

        let result = parse_xml(xml, &[], false).unwrap();
        let dict = result.dict.unwrap();
        let points = extract_geopoints(&dict, &["gps".to_string()]);

        assert_eq!(points.len(), 1);
        assert!((points[0].0 - (-1.2836198)).abs() < 1e-10);
        assert!((points[0].1 - 36.8795437).abs() < 1e-10);
    }

    #[test]
    fn test_extract_gps_nested() {
        let xml = r#"<new_repeats id="new_repeats">
  <info><age>80</age></info>
  <gps>-1.2627557 36.7926442 0.0 30.0</gps>
</new_repeats>"#;

        let result = parse_xml(xml, &[], false).unwrap();
        let dict = result.dict.unwrap();
        let points = extract_geopoints(&dict, &["gps".to_string()]);

        assert_eq!(points.len(), 1);
        assert!((points[0].0 - (-1.2627557)).abs() < 1e-10);
        assert!((points[0].1 - 36.7926442).abs() < 1e-10);
    }

    #[test]
    fn test_no_gps() {
        let xml = "<root><name>test</name></root>";
        let result = parse_xml(xml, &[], false).unwrap();
        let dict = result.dict.unwrap();
        let points = extract_geopoints(&dict, &["gps".to_string()]);
        assert!(points.is_empty());
    }

    #[test]
    fn test_empty_geo_xpaths() {
        let xml = "<root><gps>-1.0 36.0 0.0 0.0</gps></root>";
        let result = parse_xml(xml, &[], false).unwrap();
        let dict = result.dict.unwrap();
        let points = extract_geopoints(&dict, &[]);
        assert!(points.is_empty());
    }

    #[test]
    fn test_get_values_matching_key_nested() {
        // Simulate a nested dict structure
        let dict = Value::Dict(vec![
            (
                "root".to_string(),
                Value::Dict(vec![
                    (
                        "group".to_string(),
                        Value::Dict(vec![("gps".to_string(), Value::Str("-1.0 36.0".to_string()))]),
                    ),
                ]),
            ),
        ]);

        let values = get_values_matching_key(&dict, "gps");
        assert_eq!(values.len(), 1);
        assert_eq!(*values[0], Value::Str("-1.0 36.0".to_string()));
    }

    #[test]
    fn test_get_values_matching_key_in_list() {
        // Value with a list of dicts (repeat group)
        let dict = Value::Dict(vec![
            (
                "locations".to_string(),
                Value::List(vec![
                    Value::Dict(vec![("gps".to_string(), Value::Str("-1.0 36.0".to_string()))]),
                    Value::Dict(vec![("gps".to_string(), Value::Str("-2.0 37.0".to_string()))]),
                ]),
            ),
        ]);

        let values = get_values_matching_key(&dict, "gps");
        assert_eq!(values.len(), 2);
    }
}
