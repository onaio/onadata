/// Dict flattening module.
///
/// Replicates Python's `_flatten_dict_nest_repeats` which:
/// - For regular values: yields (path, value) where path is list of keys
/// - For dicts: recurses deeper
/// - For lists (repeat groups): creates a list of flattened sub-dicts,
///   each with full xpath keys joined by "/", stripped of root node prefix
/// - Final flat_dict is built by: {"/".join(path[1:]): value}
use crate::parser::Value;

/// A flattened entry: (path_segments, value).
/// The value can be a simple Value::Str or a Value::List of flattened dicts.
type FlatEntry = (Vec<String>, Value);

/// Flatten a nested dict with repeat nesting.
///
/// Replicates `_flatten_dict_nest_repeats(data_dict, prefix)`.
///
/// `data_dict` must be a Value::Dict (list of (key, value) pairs).
/// `prefix` is the current path prefix.
fn flatten_dict_nest_repeats_inner(data_dict: &[(String, Value)], prefix: &[String]) -> Vec<FlatEntry> {
    let mut entries = Vec::new();

    for (key, value) in data_dict {
        let mut new_prefix = prefix.to_vec();
        new_prefix.push(key.clone());

        match value {
            Value::Dict(inner_pairs) => {
                // Recurse into dict
                let sub = flatten_dict_nest_repeats_inner(inner_pairs, &new_prefix);
                entries.extend(sub);
            }
            Value::List(items) => {
                // Create a list of flattened sub-dicts
                let mut repeats: Vec<Value> = Vec::new();

                for item in items {
                    let item_prefix = new_prefix.clone();

                    match item {
                        Value::Dict(item_pairs) => {
                            // Flatten each dict item into a flat dict
                            let sub_entries =
                                flatten_dict_nest_repeats_inner(item_pairs, &item_prefix);
                            let mut repeat_dict: Vec<(String, Value)> = Vec::new();

                            for (path, r_value) in sub_entries {
                                // Join path[1:] with "/"
                                let flat_key = path[1..].join("/");
                                repeat_dict.push((flat_key, r_value));
                            }
                            repeats.push(Value::Dict(repeat_dict));
                        }
                        _ => {
                            // Non-dict item in list (e.g. a string)
                            let flat_key = item_prefix[1..].join("/");
                            let mut repeat_dict: Vec<(String, Value)> = Vec::new();
                            repeat_dict.push((flat_key, item.clone()));
                            repeats.push(Value::Dict(repeat_dict));
                        }
                    }
                }

                entries.push((new_prefix, Value::List(repeats)));
            }
            Value::Str(_) => {
                entries.push((new_prefix, value.clone()));
            }
        }
    }

    entries
}

/// Flatten a parsed XML dict into a flat dict.
///
/// Takes the top-level dict (e.g. {"tutorial": {...}}) and returns
/// a flat dict where keys are xpath segments joined by "/", with the
/// root node name stripped.
///
/// This matches the Python code:
/// ```python
/// for path, value in _flatten_dict_nest_repeats(self._dict, []):
///     self._flat_dict["/".join(path[1:])] = value
/// ```
pub fn flatten_dict(dict: &Value) -> Vec<(String, Value)> {
    match dict {
        Value::Dict(pairs) => {
            let entries = flatten_dict_nest_repeats_inner(pairs, &[]);
            let mut flat = Vec::new();
            for (path, value) in entries {
                let key = path[1..].join("/");
                flat.push((key, value));
            }
            flat
        }
        _ => Vec::new(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parser::{parse_xml, Value};

    fn find_flat<'a>(flat: &'a [(String, Value)], key: &str) -> Option<&'a Value> {
        flat.iter().find(|(k, _)| k == key).map(|(_, v)| v)
    }

    #[test]
    fn test_simple_form_flatten() {
        let xml = r#"<?xml version='1.0' ?><tutorial id="tutorial">
  <name>Larry
        Again
  </name>
  <age>23</age>
  <picture>1333604907194.jpg</picture>
  <has_children>0</has_children>
  <gps>-1.2836198 36.8795437 0.0 1044.0</gps>
  <web_browsers>firefox chrome safari</web_browsers>
  <meta>
    <instanceID>uuid:729f173c688e482486a48661700455ff</instanceID>
  </meta>
</tutorial>"#;

        let result = parse_xml(xml, &[], false).unwrap();
        let dict = result.dict.unwrap();
        let flat = flatten_dict(&dict);

        assert_eq!(
            find_flat(&flat, "name"),
            Some(&Value::Str("Larry\n        Again\n  ".to_string()))
        );
        assert_eq!(
            find_flat(&flat, "age"),
            Some(&Value::Str("23".to_string()))
        );
        assert_eq!(
            find_flat(&flat, "picture"),
            Some(&Value::Str("1333604907194.jpg".to_string()))
        );
        assert_eq!(
            find_flat(&flat, "has_children"),
            Some(&Value::Str("0".to_string()))
        );
        assert_eq!(
            find_flat(&flat, "gps"),
            Some(&Value::Str(
                "-1.2836198 36.8795437 0.0 1044.0".to_string()
            ))
        );
        assert_eq!(
            find_flat(&flat, "web_browsers"),
            Some(&Value::Str("firefox chrome safari".to_string()))
        );
        assert_eq!(
            find_flat(&flat, "meta/instanceID"),
            Some(&Value::Str(
                "uuid:729f173c688e482486a48661700455ff".to_string()
            ))
        );
    }

    #[test]
    fn test_nested_repeats_flatten() {
        let xml = r#"<new_repeats id="new_repeats">
  <info><age>80</age><name>Adam</name></info>
  <kids><kids_details><kids_age>50</kids_age><kids_name>Abel</kids_name></kids_details><has_kids>1</has_kids></kids>
  <web_browsers>chrome ie</web_browsers>
  <gps>-1.2627557 36.7926442 0.0 30.0</gps>
</new_repeats>"#;

        let repeats = vec!["kids/kids_details".to_string()];
        let result = parse_xml(xml, &repeats, false).unwrap();
        let dict = result.dict.unwrap();
        let flat = flatten_dict(&dict);

        assert_eq!(
            find_flat(&flat, "gps"),
            Some(&Value::Str(
                "-1.2627557 36.7926442 0.0 30.0".to_string()
            ))
        );
        assert_eq!(
            find_flat(&flat, "kids/has_kids"),
            Some(&Value::Str("1".to_string()))
        );
        assert_eq!(
            find_flat(&flat, "info/age"),
            Some(&Value::Str("80".to_string()))
        );
        assert_eq!(
            find_flat(&flat, "info/name"),
            Some(&Value::Str("Adam".to_string()))
        );
        assert_eq!(
            find_flat(&flat, "web_browsers"),
            Some(&Value::Str("chrome ie".to_string()))
        );

        // kids/kids_details should be a list of flattened dicts
        let kids_details = find_flat(&flat, "kids/kids_details").unwrap();
        match kids_details {
            Value::List(list) => {
                assert_eq!(list.len(), 1);
                match &list[0] {
                    Value::Dict(d) => {
                        // Check for kids/kids_details/kids_age and kids/kids_details/kids_name
                        assert!(d.iter().any(|(k, v)| k == "kids/kids_details/kids_age"
                            && *v == Value::Str("50".to_string())));
                        assert!(d.iter().any(|(k, v)| k == "kids/kids_details/kids_name"
                            && *v == Value::Str("Abel".to_string())));
                    }
                    _ => panic!("Expected Dict in list"),
                }
            }
            _ => panic!("Expected List for kids/kids_details"),
        }
    }

    #[test]
    fn test_encrypted_media_flatten() {
        let xml = r#"<data id="tutorial_encrypted" version="201701031234" encrypted="yes" xmlns="http://www.opendatakit.org/xforms/encrypted"><base64EncryptedKey>ZJTc</base64EncryptedKey><orx:meta xmlns:orx="http://openrosa.org/xforms"><orx:instanceID>uuid:f8971231-f3b8-4b2b-8c35-d95fa207d937</orx:instanceID></orx:meta>
<media><file>1483528430996.jpg.enc</file></media>
<media><file>1483528445767.jpg.enc</file></media>
<encryptedXmlFile>submission.xml.enc</encryptedXmlFile><base64EncryptedElementSignature>UUR8</base64EncryptedElementSignature></data>"#;

        let result = parse_xml(xml, &[], true).unwrap();
        let dict = result.dict.unwrap();
        let flat = flatten_dict(&dict);

        let media = find_flat(&flat, "media").unwrap();
        match media {
            Value::List(list) => {
                assert_eq!(list.len(), 2);
                match &list[0] {
                    Value::Dict(d) => {
                        assert!(d.iter().any(|(k, v)| k == "media/file"
                            && *v == Value::Str("1483528430996.jpg.enc".to_string())));
                    }
                    _ => panic!("Expected Dict"),
                }
                match &list[1] {
                    Value::Dict(d) => {
                        assert!(d.iter().any(|(k, v)| k == "media/file"
                            && *v == Value::Str("1483528445767.jpg.enc".to_string())));
                    }
                    _ => panic!("Expected Dict"),
                }
            }
            _ => panic!("Expected List for media"),
        }
    }

    #[test]
    fn test_auto_repeated_flatten() {
        // S2A repeated 3 times without being in repeat_xpaths
        let xml = r#"<RW_OUNIS_2016 id="ROUNIS2" version="201608211141">
<S2A><S2A_note/><S2_1_3_2_2>1</S2_1_3_2_2><S2_1_3_2_3>1.25</S2_1_3_2_3></S2A>
<S2A><S2A_note/><S2_1_3_3_2>1</S2_1_3_3_2><S2_1_3_3_3>1.25</S2_1_3_3_3></S2A>
<S2A><S2A_note/><S2_1_3_5_2>1</S2_1_3_5_2><S2_1_3_5_3><S3B><S3_1_3_4>2</S3_1_3_4><S3_1_3_4>test</S3_1_3_4></S3B><S3B><S3_1_3_5>8</S3_1_3_5><S3_1_3_6>test2</S3_1_3_6></S3B><S3B><S3_1_3_7>5</S3_1_3_7><S3_1_3_8>test</S3_1_3_8></S3B></S2_1_3_5_3></S2A>
</RW_OUNIS_2016>"#;

        let result = parse_xml(xml, &[], false).unwrap();
        let dict = result.dict.unwrap();
        let flat = flatten_dict(&dict);

        // S2A should be a list in the flat dict
        let s2a = find_flat(&flat, "S2A").unwrap();
        match s2a {
            Value::List(list) => {
                assert_eq!(list.len(), 3);
            }
            _ => panic!("Expected List for S2A, got {:?}", s2a),
        }
    }
}
