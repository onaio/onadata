/// Core XML-to-dict parser.
///
/// Replicates Python's `clean_and_parse_xml`, `_xml_node_to_dict`,
/// `xpath_from_xml_node`, `_get_all_attributes`, UUID/deprecatedID extraction,
/// and submissionDate extraction.
use std::collections::HashSet;

use quick_xml::events::{BytesCData, BytesStart, BytesText, Event};
use quick_xml::Reader;

// ---------------------------------------------------------------------------
// Value enum -- our Rust-side representation of the nested Python dict
// ---------------------------------------------------------------------------

/// A value in the parsed XML dict tree.
/// Mirrors what the Python code produces:
/// - `Str` for leaf text nodes
/// - `Dict` for element nodes with children (preserves insertion order)
/// - `List` for repeated elements / encrypted media
#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Str(String),
    Dict(Vec<(String, Value)>),
    List(Vec<Value>),
}

impl Value {
    /// Lookup a key in a Dict value.  Returns None for non-Dict variants.
    #[allow(dead_code)]
    pub fn get(&self, key: &str) -> Option<&Value> {
        match self {
            Value::Dict(pairs) => pairs.iter().find(|(k, _)| k == key).map(|(_, v)| v),
            _ => None,
        }
    }
}

// ---------------------------------------------------------------------------
// Attribute triple
// ---------------------------------------------------------------------------

/// (attr_key, attr_value, element_name)
#[derive(Debug, Clone)]
pub struct XmlAttribute {
    pub key: String,
    pub value: String,
    pub node_name: String,
}

// ---------------------------------------------------------------------------
// ParseResult -- everything extracted from a single parse pass
// ---------------------------------------------------------------------------

#[derive(Debug)]
pub struct ParseResult {
    /// The nested dict, e.g. {"tutorial": {"name": "Larry", ...}}
    pub dict: Option<Value>,
    /// Root element name (e.g. "tutorial")
    pub root_node_name: String,
    /// All XML attributes (respecting entity-skip and first-wins rules)
    pub attributes: Vec<(String, String)>,
    /// UUID extracted from meta/instanceID (uuid: prefix stripped)
    pub uuid: Option<String>,
    /// Deprecated UUID from meta/deprecatedID (uuid: prefix stripped)
    pub deprecated_uuid: Option<String>,
    /// submissionDate attribute from root element
    pub submission_date: Option<String>,
}

// ---------------------------------------------------------------------------
// Internal DOM tree built from quick-xml events
// ---------------------------------------------------------------------------

/// Minimal DOM node built during SAX-style parsing.
#[derive(Debug, Clone)]
enum DomNode {
    Element {
        /// Local name (namespace prefix stripped for matching, but kept for
        /// nodeName output to match Python minidom behaviour).
        name: String,
        attrs: Vec<(String, String)>,
        children: Vec<DomNode>,
    },
    Text(String),
    CData(String),
}

/// Build a minimal DOM tree from cleaned XML bytes.
fn build_dom(xml_bytes: &[u8]) -> Result<DomNode, String> {
    let mut reader = Reader::from_reader(xml_bytes);
    reader.config_mut().trim_text_start = false;
    reader.config_mut().trim_text_end = false;

    let mut stack: Vec<DomNode> = Vec::new();
    // Sentinel root
    stack.push(DomNode::Element {
        name: "#document".to_string(),
        attrs: vec![],
        children: vec![],
    });

    let mut buf = Vec::new();
    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(ref e)) => {
                let name = elem_name(e);
                let attrs = elem_attrs(e);
                stack.push(DomNode::Element {
                    name,
                    attrs,
                    children: vec![],
                });
            }
            Ok(Event::Empty(ref e)) => {
                // Self-closing element like <note/>
                let name = elem_name(e);
                let attrs = elem_attrs(e);
                let node = DomNode::Element {
                    name,
                    attrs,
                    children: vec![],
                };
                // Push onto current top
                if let Some(DomNode::Element { children, .. }) = stack.last_mut() {
                    children.push(node);
                }
            }
            Ok(Event::End(ref _e)) => {
                let node = stack.pop().ok_or("Unexpected end tag")?;
                if let Some(DomNode::Element { children, .. }) = stack.last_mut() {
                    children.push(node);
                } else {
                    return Err("No parent for end tag".to_string());
                }
            }
            Ok(Event::Text(ref e)) => {
                let text = decode_text(e);
                if let Some(DomNode::Element { children, .. }) = stack.last_mut() {
                    children.push(DomNode::Text(text));
                }
            }
            Ok(Event::CData(ref e)) => {
                let text = decode_cdata(e);
                if let Some(DomNode::Element { children, .. }) = stack.last_mut() {
                    children.push(DomNode::CData(text));
                }
            }
            Ok(Event::Decl(_)) | Ok(Event::PI(_)) | Ok(Event::Comment(_)) => {}
            Ok(Event::DocType(_)) => {}
            Ok(Event::Eof) => break,
            Err(e) => return Err(format!("XML parse error: {e}")),
        }
        buf.clear();
    }

    // stack should have only the sentinel #document
    if stack.len() != 1 {
        return Err("Malformed XML: unclosed elements".to_string());
    }
    Ok(stack.pop().unwrap())
}

fn elem_name(e: &BytesStart) -> String {
    String::from_utf8_lossy(e.name().as_ref()).to_string()
}

fn elem_attrs(e: &BytesStart) -> Vec<(String, String)> {
    e.attributes()
        .filter_map(|a| a.ok())
        .map(|a| {
            let key = String::from_utf8_lossy(a.key.as_ref()).to_string();
            let val = String::from_utf8_lossy(&a.value).to_string();
            (key, val)
        })
        .collect()
}

fn decode_text(e: &BytesText) -> String {
    // Unescape XML entities
    match e.unescape() {
        Ok(s) => s.to_string(),
        Err(_) => String::from_utf8_lossy(e.as_ref()).to_string(),
    }
}

fn decode_cdata(e: &BytesCData) -> String {
    String::from_utf8_lossy(e.as_ref()).to_string()
}

// ---------------------------------------------------------------------------
// Clean XML (matching Python's clean_and_parse_xml)
// ---------------------------------------------------------------------------

/// Strips whitespace, removes whitespace between XML tags.
/// Matches: `re.sub(r">\s+<", "><", smart_str(xml_string.strip()))`
pub fn clean_xml(xml_str: &str) -> String {
    let trimmed = xml_str.trim();
    // Remove whitespace between tags
    let mut result = String::with_capacity(trimmed.len());
    let mut chars = trimmed.chars().peekable();
    while let Some(c) = chars.next() {
        if c == '>' {
            result.push(c);
            // Consume any whitespace that is immediately followed by '<'
            let mut ws_buf = String::new();
            while let Some(&next) = chars.peek() {
                if next.is_whitespace() {
                    ws_buf.push(next);
                    chars.next();
                } else {
                    break;
                }
            }
            // If next char is '<', drop the whitespace; otherwise keep it
            if let Some(&'<') = chars.peek() {
                // drop ws_buf
            } else {
                result.push_str(&ws_buf);
            }
        } else {
            result.push(c);
        }
    }
    result
}

// ---------------------------------------------------------------------------
// xpath computation (matching Python's xpath_from_xml_node)
// ---------------------------------------------------------------------------

/// Compute the xpath for a node given the path of ancestor names.
/// Python's `xpath_from_xml_node` walks parent chain, collects names,
/// then returns "/".join(names[1:]) -- skipping the document node AND
/// the root element node (since _gather_parent_node_list skips when
/// parentNode.parentNode is None, i.e. the document's child = root element).
///
/// Actually, re-reading the Python code more carefully:
/// ```python
/// def _gather_parent_node_list(node):
///     node_names = []
///     if node.parentNode and node.parentNode.parentNode:
///         node_names.extend(_gather_parent_node_list(node.parentNode))
///     node_names.extend([node.nodeName])
///     return node_names
/// ```
///
/// For a node at path document -> root -> child -> grandchild:
/// - grandchild: parent=child, parent.parent=root (exists) -> recurse to child
///   - child: parent=root, parent.parent=document (exists) -> recurse to root
///     - root: parent=document, parent.parent=None -> STOP, return ["root"]
///   - child returns ["root", "child"]
/// - grandchild returns ["root", "child", "grandchild"]
/// Then xpath_from_xml_node returns "/".join(names[1:]) = "child/grandchild"
///
/// So the xpath skips the root element name and gives the path from root's children down.
///
/// We pass `ancestor_names` which is the list of element names from root down (not including
/// the document node). For a child at depth 2 under root:
/// ancestor_names = ["root", "child"] and current node name is the node itself.
/// The xpath = "/".join(ancestor_names[1:] + [node_name])... wait, let me re-check.
///
/// Actually, ancestor_names in our traversal doesn't include the current node.
/// So for grandchild: ancestor_names = ["root", "child"], node_name = "grandchild"
/// full path = ["root", "child", "grandchild"], xpath = "child/grandchild"
///
/// This matches: skip first element (root), join the rest.
pub fn compute_xpath(ancestor_names: &[String], node_name: &str) -> String {
    // ancestor_names[0] is the root element name.
    // We want: ancestor_names[1..] joined with "/" then "/" then node_name
    let mut parts: Vec<&str> = ancestor_names.iter().skip(1).map(|s| s.as_str()).collect();
    parts.push(node_name);
    parts.join("/")
}

// ---------------------------------------------------------------------------
// _xml_node_to_dict equivalent
// ---------------------------------------------------------------------------

/// Convert a DomNode (element) into our Value tree.
/// `repeats` is the set of xpaths that should be treated as list-type.
/// `encrypted` when true forces "media" child elements to be list-type.
/// `ancestor_names` tracks the path for xpath computation.
fn node_to_dict(
    node: &DomNode,
    repeats: &HashSet<String>,
    encrypted: bool,
    ancestor_names: &[String],
) -> Option<Value> {
    match node {
        DomNode::Text(_) | DomNode::CData(_) => {
            // Leaf nodes handled by parent
            None
        }
        DomNode::Element {
            name,
            children,
            ..
        } => {
            // If node has 0 children -> None
            if children.is_empty() {
                return None;
            }

            // If node has 1 child that is Text -> {nodeName: textValue}
            if children.len() == 1 {
                match &children[0] {
                    DomNode::Text(text) => {
                        return Some(Value::Dict(vec![(name.clone(), Value::Str(text.clone()))]));
                    }
                    DomNode::CData(text) => {
                        // CDATA section -> {parentNodeName: cdataValue}
                        return Some(Value::Dict(vec![(name.clone(), Value::Str(text.clone()))]));
                    }
                    _ => {}
                }
            }

            // Check for CDATA among children (Python checks this in the loop)
            for child in children {
                if let DomNode::CData(text) = child {
                    return Some(Value::Dict(vec![(name.clone(), Value::Str(text.clone()))]));
                }
            }

            // This is an internal node - iterate children
            let mut value: Vec<(String, Value)> = Vec::new();
            let mut current_path = ancestor_names.to_vec();
            current_path.push(name.clone());

            for child in children {
                match child {
                    DomNode::Text(_) => {
                        // Text nodes among element siblings are ignored
                        // (Python: the loop only processes element children
                        //  via _xml_node_to_dict which returns None for text)
                        continue;
                    }
                    DomNode::CData(text) => {
                        // CDATA found during iteration (Python line 200-201)
                        return Some(Value::Dict(vec![(name.clone(), Value::Str(text.clone()))]));
                    }
                    DomNode::Element {
                        name: child_name, ..
                    } => {
                        let child_dict =
                            node_to_dict(child, repeats, encrypted, &current_path);

                        if child_dict.is_none() {
                            continue;
                        }

                        let child_dict = child_dict.unwrap();

                        // Extract the child's value from the wrapper dict
                        let child_value = match &child_dict {
                            Value::Dict(pairs) => {
                                if pairs.len() == 1 && pairs[0].0 == *child_name {
                                    pairs[0].1.clone()
                                } else {
                                    // This shouldn't happen per Python assertion
                                    child_dict.clone()
                                }
                            }
                            _ => child_dict.clone(),
                        };

                        let child_xpath = compute_xpath(&current_path, child_name);

                        let is_list_type = repeats.contains(&child_xpath)
                            || (encrypted && child_name == "media");

                        // Find if child_name already exists in value
                        let existing_idx =
                            value.iter().position(|(k, _)| k == child_name);

                        if is_list_type {
                            // List type: always append to list
                            if let Some(idx) = existing_idx {
                                match &mut value[idx].1 {
                                    Value::List(list) => {
                                        list.push(child_value);
                                    }
                                    _ => {
                                        // Shouldn't happen since we always init as list
                                    }
                                }
                            } else {
                                value.push((
                                    child_name.clone(),
                                    Value::List(vec![child_value]),
                                ));
                            }
                        } else {
                            // Dict type
                            if let Some(idx) = existing_idx {
                                // Node is repeated, aggregate
                                let existing = &mut value[idx].1;
                                match existing {
                                    Value::List(list) => {
                                        // Already a list, just append
                                        list.push(child_value);
                                    }
                                    _ => {
                                        // Convert to list
                                        let prev = existing.clone();
                                        *existing = Value::List(vec![prev, child_value]);
                                    }
                                }
                            } else {
                                value.push((child_name.clone(), child_value));
                            }
                        }
                    }
                }
            }

            if value.is_empty() {
                return None;
            }

            Some(Value::Dict(vec![(name.clone(), Value::Dict(value))]))
        }
    }
}

// ---------------------------------------------------------------------------
// Attribute collection (matching Python's _get_all_attributes + _set_attributes)
// ---------------------------------------------------------------------------

/// Recursively collect all attributes from an element tree.
fn collect_attributes(node: &DomNode, out: &mut Vec<XmlAttribute>) {
    if let DomNode::Element {
        name,
        attrs,
        children,
    } = node
    {
        for (key, val) in attrs {
            out.push(XmlAttribute {
                key: key.clone(),
                value: val.clone(),
                node_name: name.clone(),
            });
        }
        for child in children {
            collect_attributes(child, out);
        }
    }
}

/// Apply Python's _set_attributes logic: skip entity nodes, first-wins for duplicates.
fn build_attributes(raw: &[XmlAttribute]) -> Vec<(String, String)> {
    let mut result: Vec<(String, String)> = Vec::new();
    let mut seen: HashSet<String> = HashSet::new();
    for attr in raw {
        if attr.node_name == "entity" {
            continue;
        }
        if seen.contains(&attr.key) {
            // Duplicate - skip (first wins)
            continue;
        }
        seen.insert(attr.key.clone());
        result.push((attr.key.clone(), attr.value.clone()));
    }
    result
}

// ---------------------------------------------------------------------------
// UUID extraction
// ---------------------------------------------------------------------------

/// Extract UUID from meta/instanceID or orx:meta/orx:instanceID.
/// Also checks root element's instanceID attribute.
fn extract_uuid(root: &DomNode, attributes: &[(String, String)]) -> Option<String> {
    // First try meta/instanceID in the XML tree
    if let Some(uuid) = extract_meta_value(root, "instanceID") {
        return strip_uuid_prefix(&uuid);
    }

    // Then check root element's instanceID attribute
    for (key, value) in attributes {
        if key == "instanceID" {
            return strip_uuid_prefix(value);
        }
    }

    None
}

/// Extract deprecated UUID from meta/deprecatedID or orx:meta/orx:deprecatedID.
fn extract_deprecated_uuid(root: &DomNode) -> Option<String> {
    if let Some(uuid) = extract_meta_value(root, "deprecatedID") {
        return strip_uuid_prefix(&uuid);
    }
    None
}

/// Extract a value from meta/<tag_name> or orx:meta/orx:<tag_name>.
fn extract_meta_value(root: &DomNode, tag_name: &str) -> Option<String> {
    if let DomNode::Element { children, .. } = root {
        for child in children {
            if let DomNode::Element {
                name, children: meta_children, ..
            } = child
            {
                let name_lower = name.to_lowercase();
                if name_lower == "meta" || name_lower == "orx:meta" {
                    for meta_child in meta_children {
                        if let DomNode::Element {
                            name: child_name,
                            children: value_children,
                            ..
                        } = meta_child
                        {
                            let child_name_lower = child_name.to_lowercase();
                            if child_name_lower == tag_name.to_lowercase()
                                || child_name_lower
                                    == format!("orx:{}", tag_name.to_lowercase())
                            {
                                // Get text content
                                if let Some(text) = get_text_content(value_children) {
                                    return Some(text.trim().to_string());
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    None
}

/// Get the text content of a node's children.
fn get_text_content(children: &[DomNode]) -> Option<String> {
    for child in children {
        match child {
            DomNode::Text(text) => return Some(text.clone()),
            DomNode::CData(text) => return Some(text.clone()),
            _ => {}
        }
    }
    None
}

/// Strip "uuid:" prefix from a UUID string.
fn strip_uuid_prefix(s: &str) -> Option<String> {
    if let Some(rest) = s.strip_prefix("uuid:") {
        if rest.is_empty() {
            None
        } else {
            Some(rest.to_string())
        }
    } else if !s.is_empty() {
        // Return as-is if no uuid: prefix but non-empty
        Some(s.to_string())
    } else {
        None
    }
}

/// Extract submissionDate from root element's attributes.
fn extract_submission_date(attributes: &[(String, String)]) -> Option<String> {
    for (key, value) in attributes {
        if key == "submissionDate" {
            if !value.is_empty() {
                return Some(value.clone());
            }
        }
    }
    None
}

// ---------------------------------------------------------------------------
// Public parse entry point
// ---------------------------------------------------------------------------

/// Parse an XML submission string.
///
/// This is the main entry point that performs:
/// 1. Clean XML (strip whitespace between tags)
/// 2. Build DOM tree
/// 3. Convert root element to nested dict (skipping #document wrapper)
/// 4. Collect attributes (entity-skip, first-wins)
/// 5. Extract UUID, deprecated UUID, submission date
pub fn parse_xml(
    xml_str: &str,
    repeat_xpaths: &[String],
    encrypted: bool,
) -> Result<ParseResult, String> {
    let cleaned = clean_xml(xml_str);
    let dom = build_dom(cleaned.as_bytes())?;

    // Get the root element (first element child of #document)
    let root_element = match &dom {
        DomNode::Element { children, .. } => children
            .iter()
            .find(|c| matches!(c, DomNode::Element { .. }))
            .ok_or("No root element found")?,
        _ => return Err("Expected document node".to_string()),
    };

    let root_name = match root_element {
        DomNode::Element { name, .. } => name.clone(),
        _ => unreachable!(),
    };

    // Build repeat xpath set
    let repeats: HashSet<String> = repeat_xpaths.iter().cloned().collect();

    // Convert root element to dict
    // ancestor_names is empty because we start at root (no ancestors above it)
    let dict = node_to_dict(root_element, &repeats, encrypted, &[]);

    // Collect attributes from root element (not #document)
    let mut raw_attrs = Vec::new();
    collect_attributes(root_element, &mut raw_attrs);
    let attributes = build_attributes(&raw_attrs);

    // Extract UUID and deprecated UUID
    let uuid = extract_uuid(root_element, &attributes);
    let deprecated_uuid = extract_deprecated_uuid(root_element);

    // Extract submission date from root attributes
    let submission_date = extract_submission_date(&attributes);

    Ok(ParseResult {
        dict,
        root_node_name: root_name,
        attributes,
        uuid,
        deprecated_uuid,
        submission_date,
    })
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_clean_xml() {
        let input = "  <?xml version='1.0' ?><root>  \n  <child>text</child>  \n  </root>  ";
        let cleaned = clean_xml(input);
        assert_eq!(
            cleaned,
            "<?xml version='1.0' ?><root><child>text</child></root>"
        );
    }

    #[test]
    fn test_clean_xml_preserves_inner_text() {
        let input = "<root><name>Larry\n        Again\n  </name></root>";
        let cleaned = clean_xml(input);
        // Text inside a single element should be preserved
        assert_eq!(cleaned, "<root><name>Larry\n        Again\n  </name></root>");
    }

    #[test]
    fn test_simple_form() {
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

        assert_eq!(result.root_node_name, "tutorial");
        assert_eq!(
            result.uuid,
            Some("729f173c688e482486a48661700455ff".to_string())
        );
        assert_eq!(result.deprecated_uuid, None);
        assert_eq!(result.submission_date, None);

        // Check attributes
        assert_eq!(result.attributes, vec![("id".to_string(), "tutorial".to_string())]);

        // Check dict structure
        let dict = result.dict.unwrap();
        match &dict {
            Value::Dict(pairs) => {
                assert_eq!(pairs.len(), 1);
                assert_eq!(pairs[0].0, "tutorial");
                match &pairs[0].1 {
                    Value::Dict(inner) => {
                        // Check name preserves whitespace
                        let name_val = inner.iter().find(|(k, _)| k == "name").unwrap();
                        match &name_val.1 {
                            Value::Str(s) => {
                                assert_eq!(s, "Larry\n        Again\n  ");
                            }
                            _ => panic!("Expected Str for name"),
                        }

                        // Check age
                        let age_val = inner.iter().find(|(k, _)| k == "age").unwrap();
                        assert_eq!(age_val.1, Value::Str("23".to_string()));

                        // Check meta/instanceID
                        let meta_val = inner.iter().find(|(k, _)| k == "meta").unwrap();
                        match &meta_val.1 {
                            Value::Dict(meta_inner) => {
                                assert_eq!(meta_inner.len(), 1);
                                assert_eq!(meta_inner[0].0, "instanceID");
                                assert_eq!(
                                    meta_inner[0].1,
                                    Value::Str(
                                        "uuid:729f173c688e482486a48661700455ff".to_string()
                                    )
                                );
                            }
                            _ => panic!("Expected Dict for meta"),
                        }
                    }
                    _ => panic!("Expected Dict for tutorial"),
                }
            }
            _ => panic!("Expected Dict"),
        }
    }

    #[test]
    fn test_nested_repeats() {
        let xml = r#"<new_repeats id="new_repeats">
  <info><age>80</age><name>Adam</name></info>
  <kids><kids_details><kids_age>50</kids_age><kids_name>Abel</kids_name></kids_details><has_kids>1</has_kids></kids>
  <web_browsers>chrome ie</web_browsers>
  <gps>-1.2627557 36.7926442 0.0 30.0</gps>
</new_repeats>"#;

        let repeats = vec!["kids/kids_details".to_string()];
        let result = parse_xml(xml, &repeats, false).unwrap();

        let dict = result.dict.unwrap();
        // dict = {"new_repeats": {"info": ..., "kids": ..., ...}}
        match &dict {
            Value::Dict(pairs) => {
                assert_eq!(pairs[0].0, "new_repeats");
                let inner = match &pairs[0].1 {
                    Value::Dict(d) => d,
                    _ => panic!("Expected Dict"),
                };

                // Check kids/kids_details is a list
                let kids = inner.iter().find(|(k, _)| k == "kids").unwrap();
                match &kids.1 {
                    Value::Dict(kids_inner) => {
                        let kids_details =
                            kids_inner.iter().find(|(k, _)| k == "kids_details").unwrap();
                        match &kids_details.1 {
                            Value::List(list) => {
                                assert_eq!(list.len(), 1);
                                // The single item should be a dict with kids_age and kids_name
                                match &list[0] {
                                    Value::Dict(d) => {
                                        assert!(d.iter().any(|(k, _)| k == "kids_age"));
                                        assert!(d.iter().any(|(k, _)| k == "kids_name"));
                                    }
                                    _ => panic!("Expected Dict in list"),
                                }
                            }
                            _ => panic!("Expected List for kids_details"),
                        }
                    }
                    _ => panic!("Expected Dict for kids"),
                }
            }
            _ => panic!("Expected Dict"),
        }
    }

    #[test]
    fn test_encrypted_media() {
        let xml = r#"<data id="tutorial_encrypted" version="201701031234" encrypted="yes" xmlns="http://www.opendatakit.org/xforms/encrypted"><base64EncryptedKey>ZJTc</base64EncryptedKey><orx:meta xmlns:orx="http://openrosa.org/xforms"><orx:instanceID>uuid:f8971231-f3b8-4b2b-8c35-d95fa207d937</orx:instanceID></orx:meta>
<media><file>1483528430996.jpg.enc</file></media>
<media><file>1483528445767.jpg.enc</file></media>
<encryptedXmlFile>submission.xml.enc</encryptedXmlFile><base64EncryptedElementSignature>UUR8</base64EncryptedElementSignature></data>"#;

        let result = parse_xml(xml, &[], true).unwrap();

        assert_eq!(
            result.uuid,
            Some("f8971231-f3b8-4b2b-8c35-d95fa207d937".to_string())
        );

        let dict = result.dict.unwrap();
        match &dict {
            Value::Dict(pairs) => {
                assert_eq!(pairs[0].0, "data");
                let inner = match &pairs[0].1 {
                    Value::Dict(d) => d,
                    _ => panic!("Expected Dict"),
                };

                // media should be a list with 2 items
                let media = inner.iter().find(|(k, _)| k == "media").unwrap();
                match &media.1 {
                    Value::List(list) => {
                        assert_eq!(list.len(), 2);
                        // First item
                        match &list[0] {
                            Value::Dict(d) => {
                                assert_eq!(d[0].0, "file");
                                assert_eq!(
                                    d[0].1,
                                    Value::Str("1483528430996.jpg.enc".to_string())
                                );
                            }
                            _ => panic!("Expected Dict in media list"),
                        }
                        // Second item
                        match &list[1] {
                            Value::Dict(d) => {
                                assert_eq!(d[0].0, "file");
                                assert_eq!(
                                    d[0].1,
                                    Value::Str("1483528445767.jpg.enc".to_string())
                                );
                            }
                            _ => panic!("Expected Dict in media list"),
                        }
                    }
                    _ => panic!("Expected List for media"),
                }
            }
            _ => panic!("Expected Dict"),
        }
    }

    #[test]
    fn test_repeated_nodes_auto_list() {
        // S2A appears 3 times without being in repeat_xpaths.
        // Python auto-converts to list on second occurrence.
        let xml = r#"<RW_OUNIS_2016 id="ROUNIS2" version="201608211141">
<S2A><S2A_note/><S2_1_3_2_2>1</S2_1_3_2_2><S2_1_3_2_3>1.25</S2_1_3_2_3></S2A>
<S2A><S2A_note/><S2_1_3_3_2>1</S2_1_3_3_2><S2_1_3_3_3>1.25</S2_1_3_3_3></S2A>
<S2A><S2A_note/><S2_1_3_5_2>1</S2_1_3_5_2><S2_1_3_5_3><S3B><S3_1_3_4>2</S3_1_3_4><S3_1_3_4>test</S3_1_3_4></S3B><S3B><S3_1_3_5>8</S3_1_3_5><S3_1_3_6>test2</S3_1_3_6></S3B><S3B><S3_1_3_7>5</S3_1_3_7><S3_1_3_8>test</S3_1_3_8></S3B></S2_1_3_5_3></S2A>
</RW_OUNIS_2016>"#;

        let result = parse_xml(xml, &[], false).unwrap();
        let dict = result.dict.unwrap();

        match &dict {
            Value::Dict(pairs) => {
                assert_eq!(pairs[0].0, "RW_OUNIS_2016");
                let inner = match &pairs[0].1 {
                    Value::Dict(d) => d,
                    _ => panic!("Expected Dict"),
                };

                // S2A should be a list of 3 dicts
                let s2a = inner.iter().find(|(k, _)| k == "S2A").unwrap();
                match &s2a.1 {
                    Value::List(list) => {
                        assert_eq!(list.len(), 3);

                        // First S2A: {S2_1_3_2_2: "1", S2_1_3_2_3: "1.25"}
                        // (S2A_note is empty/self-closing, so skipped)
                        match &list[0] {
                            Value::Dict(d) => {
                                assert!(d.iter().any(|(k, v)| k == "S2_1_3_2_2"
                                    && *v == Value::Str("1".to_string())));
                                assert!(d.iter().any(|(k, v)| k == "S2_1_3_2_3"
                                    && *v == Value::Str("1.25".to_string())));
                            }
                            _ => panic!("Expected Dict in S2A list"),
                        }

                        // Third S2A has nested S2_1_3_5_3 with S3B repeats
                        match &list[2] {
                            Value::Dict(d) => {
                                let s2_1_3_5_3 =
                                    d.iter().find(|(k, _)| k == "S2_1_3_5_3").unwrap();
                                match &s2_1_3_5_3.1 {
                                    Value::Dict(inner_d) => {
                                        let s3b =
                                            inner_d.iter().find(|(k, _)| k == "S3B").unwrap();
                                        match &s3b.1 {
                                            Value::List(s3b_list) => {
                                                assert_eq!(s3b_list.len(), 3);
                                                // First S3B has S3_1_3_4 appearing twice -> list ["2", "test"]
                                                match &s3b_list[0] {
                                                    Value::Dict(d) => {
                                                        let field = d
                                                            .iter()
                                                            .find(|(k, _)| k == "S3_1_3_4")
                                                            .unwrap();
                                                        match &field.1 {
                                                            Value::List(vals) => {
                                                                assert_eq!(vals.len(), 2);
                                                                assert_eq!(
                                                                    vals[0],
                                                                    Value::Str("2".to_string())
                                                                );
                                                                assert_eq!(
                                                                    vals[1],
                                                                    Value::Str(
                                                                        "test".to_string()
                                                                    )
                                                                );
                                                            }
                                                            _ => panic!(
                                                                "Expected List for S3_1_3_4"
                                                            ),
                                                        }
                                                    }
                                                    _ => panic!("Expected Dict in S3B list"),
                                                }
                                            }
                                            _ => panic!("Expected List for S3B"),
                                        }
                                    }
                                    _ => panic!("Expected Dict for S2_1_3_5_3"),
                                }
                            }
                            _ => panic!("Expected Dict in S2A list"),
                        }
                    }
                    _ => panic!("Expected List for S2A, got {:?}", s2a.1),
                }
            }
            _ => panic!("Expected Dict"),
        }
    }

    #[test]
    fn test_self_closing_tag_skipped() {
        let xml = "<root><note/><name>test</name></root>";
        let result = parse_xml(xml, &[], false).unwrap();
        let dict = result.dict.unwrap();
        match &dict {
            Value::Dict(pairs) => {
                let inner = match &pairs[0].1 {
                    Value::Dict(d) => d,
                    _ => panic!("Expected Dict"),
                };
                // note should be skipped
                assert!(!inner.iter().any(|(k, _)| k == "note"));
                // name should be present
                assert!(inner.iter().any(|(k, _)| k == "name"));
            }
            _ => panic!("Expected Dict"),
        }
    }

    #[test]
    fn test_entity_attributes_skipped() {
        let xml = r#"<data id="form1"><entity id="ent1" dataset="people"><label>test</label></entity><name>test</name></data>"#;
        let result = parse_xml(xml, &[], false).unwrap();
        // "id" from data should be present, but "id" and "dataset" from entity should be skipped
        assert_eq!(
            result.attributes,
            vec![("id".to_string(), "form1".to_string())]
        );
    }

    #[test]
    fn test_submission_date_extraction() {
        let xml = r#"<data id="form1" submissionDate="2023-01-15T10:30:00.000Z"><name>test</name></data>"#;
        let result = parse_xml(xml, &[], false).unwrap();
        assert_eq!(
            result.submission_date,
            Some("2023-01-15T10:30:00.000Z".to_string())
        );
    }

    #[test]
    fn test_deprecated_uuid() {
        let xml = r#"<data id="form1"><meta><instanceID>uuid:new-uuid</instanceID><deprecatedID>uuid:old-uuid</deprecatedID></meta><name>test</name></data>"#;
        let result = parse_xml(xml, &[], false).unwrap();
        assert_eq!(result.uuid, Some("new-uuid".to_string()));
        assert_eq!(result.deprecated_uuid, Some("old-uuid".to_string()));
    }

    #[test]
    fn test_orx_namespace_uuid() {
        let xml = r#"<data id="test" xmlns:orx="http://openrosa.org/xforms"><orx:meta><orx:instanceID>uuid:f8971231-f3b8-4b2b-8c35-d95fa207d937</orx:instanceID></orx:meta><name>test</name></data>"#;
        let result = parse_xml(xml, &[], false).unwrap();
        assert_eq!(
            result.uuid,
            Some("f8971231-f3b8-4b2b-8c35-d95fa207d937".to_string())
        );
    }

    #[test]
    fn test_empty_root() {
        let xml = "<root/>";
        let result = parse_xml(xml, &[], false).unwrap();
        assert!(result.dict.is_none());
        assert_eq!(result.root_node_name, "root");
    }

    #[test]
    fn test_xpath_computation() {
        // For a child "age" under root "tutorial", xpath should be "age"
        assert_eq!(compute_xpath(&["tutorial".to_string()], "age"), "age");

        // For grandchild "instanceID" under root "tutorial" > "meta"
        assert_eq!(
            compute_xpath(
                &["tutorial".to_string(), "meta".to_string()],
                "instanceID"
            ),
            "meta/instanceID"
        );

        // For deeply nested
        assert_eq!(
            compute_xpath(
                &["root".to_string(), "a".to_string(), "b".to_string()],
                "c"
            ),
            "a/b/c"
        );
    }

    #[test]
    fn test_xmlns_attributes_included() {
        // xmlns attributes should be included (they are regular attributes to quick-xml)
        let xml = r#"<data id="test" xmlns="http://example.com"><name>v</name></data>"#;
        let result = parse_xml(xml, &[], false).unwrap();
        // Should have both 'id' and 'xmlns'
        assert!(result.attributes.iter().any(|(k, _)| k == "id"));
        assert!(result.attributes.iter().any(|(k, _)| k == "xmlns"));
    }
}
