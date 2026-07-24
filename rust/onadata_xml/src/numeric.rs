/// Numeric conversion utilities matching Python's `numeric_checker`.
///
/// Tries int, then float (NaN -> 0), otherwise returns original string.

/// Result of numeric checking - either a parsed number or the original string.
#[derive(Debug, Clone, PartialEq)]
pub enum NumericValue {
    Int(i64),
    Float(f64),
    Str(String),
}

/// Replicates Python's `numeric_checker(string_value)`:
/// - Try int(string_value) -> return int
/// - Try float(string_value) -> if NaN return 0, else return float
/// - Otherwise return string unchanged
pub fn numeric_checker(string_value: &str) -> NumericValue {
    // Try parsing as integer first
    if let Ok(i) = string_value.parse::<i64>() {
        return NumericValue::Int(i);
    }

    // Try parsing as float
    if let Ok(f) = string_value.parse::<f64>() {
        if f.is_nan() {
            return NumericValue::Int(0);
        }
        return NumericValue::Float(f);
    }

    NumericValue::Str(string_value.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_integer() {
        assert_eq!(numeric_checker("23"), NumericValue::Int(23));
    }

    #[test]
    fn test_negative_integer() {
        assert_eq!(numeric_checker("-5"), NumericValue::Int(-5));
    }

    #[test]
    fn test_zero() {
        assert_eq!(numeric_checker("0"), NumericValue::Int(0));
    }

    #[test]
    fn test_float() {
        assert_eq!(numeric_checker("1.25"), NumericValue::Float(1.25));
    }

    #[test]
    fn test_negative_float() {
        assert_eq!(numeric_checker("-1.2836198"), NumericValue::Float(-1.2836198));
    }

    #[test]
    fn test_nan() {
        assert_eq!(numeric_checker("NaN"), NumericValue::Int(0));
    }

    #[test]
    fn test_nan_lowercase() {
        // Python's float("nan") works, Rust's parse also handles various NaN forms
        assert_eq!(numeric_checker("nan"), NumericValue::Int(0));
    }

    #[test]
    fn test_string() {
        assert_eq!(
            numeric_checker("hello"),
            NumericValue::Str("hello".to_string())
        );
    }

    #[test]
    fn test_empty_string() {
        assert_eq!(numeric_checker(""), NumericValue::Str("".to_string()));
    }

    #[test]
    fn test_gps_string() {
        assert_eq!(
            numeric_checker("-1.2836198 36.8795437 0.0 1044.0"),
            NumericValue::Str("-1.2836198 36.8795437 0.0 1044.0".to_string())
        );
    }

    #[test]
    fn test_uuid_string() {
        assert_eq!(
            numeric_checker("uuid:729f173c688e482486a48661700455ff"),
            NumericValue::Str("uuid:729f173c688e482486a48661700455ff".to_string())
        );
    }
}
