# Rust Port Analysis: onadata Performance Hotspots

**Date**: 2026-02-16
**Branch**: `rusty`
**Status**: Analysis / Proposal

## Executive Summary

onadata is a Django-based ODK (Open Data Kit) data collection platform. After thorough
analysis, we identified **5 high-impact areas** where porting CPU/memory-intensive Python
code to Rust (via PyO3 native extensions) would yield significant performance gains.

The biggest wins come from **export generation**, **XML parsing/submission processing**,
and **data transformation pipelines** -- all of which involve tight loops over large
datasets with recursive data structures, string manipulation, and format conversion.

---

## Architecture Overview

```
                    ┌─────────────────────────────────────────────┐
                    │              Django REST API                 │
                    └──────────┬──────────────┬───────────────────┘
                               │              │
                    ┌──────────▼──┐    ┌──────▼──────────────┐
                    │  Submission  │    │   Export / Query     │
                    │  Pipeline    │    │   Pipeline           │
                    └──────┬──────┘    └──────┬───────────────┘
                           │                  │
                    ┌──────▼──────┐    ┌──────▼───────────────┐
                    │ XML Parse → │    │ DB Query → Transform  │
                    │ JSON → Save │    │ → Format → File I/O   │
                    └─────────────┘    └──────────────────────┘
                           │                  │
                    ┌──────▼──────────────────▼───────────────┐
                    │         Celery Async Task Queue          │
                    └──────────────────────────────────────────┘
```

---

## 1. EXPORT GENERATION (Priority: CRITICAL)

**Files**: `export_builder.py`, `csv_builder.py`, `export_tools.py`
**Impact**: Largest single performance bottleneck

### What it does

Converts form submissions (100k+ rows) into XLSX, CSV, SAV (SPSS), KML, GeoJSON formats.
Each export runs as a Celery task and involves:

1. Querying all submissions from PostgreSQL
2. Flattening nested repeat groups into tabular format
3. Processing select-multiple fields (splitting into binary columns)
4. Type conversion, GPS parsing, label lookups
5. Writing to output format (openpyxl for XLSX, csv module for CSV, etc.)

### Why it's slow in Python

| Bottleneck | Location | Complexity | Description |
|---|---|---|---|
| `dict_to_joined_export()` | export_builder.py:112-180 | O(r * f * d) per row | Recursive dict creation for every submission. Creates intermediate dicts at each nesting level. |
| `split_select_multiples()` | export_builder.py:746-796 | O(s * c) per row | Dict comprehension per select-multiple field. 50 fields * 100 choices = 5000 dict updates/row. |
| `pre_process_row()` | export_builder.py:835-909 | O(v) per row | Regex compiled per string value per row. Dynamic value replacement with `re.findall()` on every cell. |
| CSV column discovery | csv_builder.py:803-818 | O(2N) | Iterates ALL data twice: once to discover repeat columns, once to write. |
| Nested repeat writes | export_builder.py:1137-1143 | O(r * n * d) | For nested repeats: 100k submissions * 100 repeats * 50 sub-repeats = 500M write operations. |

### Rust opportunity

A Rust export engine exposed via PyO3 could:

- **Stream-process rows** without intermediate dict allocation (zero-copy where possible)
- **Pre-compile regex** once, reuse across all rows
- **Flatten nested structures** iteratively with stack-based traversal instead of Python recursion
- **Write output formats** directly using Rust crates (`calamine`/`rust_xlsxwriter` for XLSX, `csv` crate)
- **Parallelize section writes** across threads (Python's GIL prevents this)

**Estimated speedup**: 10-50x for large exports (100k+ rows with repeat groups)

### Proposed Rust module: `onadata_export`

```
onadata_export/
├── src/
│   ├── lib.rs              # PyO3 module entry
│   ├── flatten.rs          # dict_to_joined_export replacement
│   ├── select_multiples.rs # split_select_multiples replacement
│   ├── preprocess.rs       # pre_process_row with compiled regex
│   ├── writers/
│   │   ├── xlsx.rs         # XLSX writer (rust_xlsxwriter)
│   │   ├── csv.rs          # CSV writer
│   │   └── sav.rs          # SAV/SPSS writer
│   └── schema.rs           # Form schema representation
└── Cargo.toml
```

---

## 2. XML PARSING & SUBMISSION PROCESSING (Priority: HIGH)

**Files**: `xform_instance_parser.py`, `instance.py`, `logger_tools.py`
**Impact**: Every single submission goes through this path

### What it does

When a form submission arrives (XML from a mobile device):

1. Read entire XML into memory
2. Parse with minidom (full DOM tree, 2-3x memory of raw XML)
3. Recursively convert DOM to Python dict (`_xml_node_to_dict`)
4. Flatten nested dict into key-value pairs
5. Extract geolocation, media references, UUIDs
6. Convert numeric strings to numbers (recursive traversal)
7. Compute SHA256 hash
8. Save JSON representation

### Why it's slow in Python

| Bottleneck | Location | Issue |
|---|---|---|
| `clean_and_parse_xml()` | xform_instance_parser.py:174-183 | Regex on full XML + minidom DOM tree (2-3x memory) |
| `_xml_node_to_dict()` | xform_instance_parser.py:187-240 | Recursive DOM traversal with `xpath_from_xml_node()` called per node (walks parent chain each time) |
| `_flatten_dict_nest_repeats()` | xform_instance_parser.py:243-273 | Recursive generator with `list(new_prefix)` copy on every iteration |
| `numeric_converter()` | instance.py:398-414 | Recursive dict traversal with try/except int/float per value |
| `get_values_matching_key()` | dict_tools.py:8-33 | Full recursive document search for geolocation/media extraction |
| **XML parsed 6+ times** | Multiple locations | `get_dict()` called separately by `save()`, `_set_geom()`, `get_expected_media()`, `get_full_dict()` |

### Rust opportunity

A Rust XML processor could:

- **Parse XML once** with `quick-xml` (SAX-style, no DOM tree) and extract all needed data in a single pass
- **Build the flat dict, geolocation, media list, UUID, and numeric conversions** all in one traversal
- **Avoid recursive Python calls** -- use iterative stack-based traversal
- **Return a Python dict** via PyO3 with all data ready, eliminating 5 of 6 redundant parses
- **Compute SHA256** natively (10x+ faster than Python's hashlib for in-process hashing)

**Estimated speedup**: 5-20x per submission (more for large submissions with many repeat groups)

### Proposed Rust module: `onadata_xml`

```
onadata_xml/
├── src/
│   ├── lib.rs           # PyO3 module entry
│   ├── parser.rs        # Single-pass XML → structured data
│   ├── flatten.rs       # Iterative flattening (replaces recursive Python)
│   ├── numeric.rs       # Fast numeric conversion
│   ├── geom.rs          # Geolocation extraction
│   └── media.rs         # Media reference extraction
└── Cargo.toml
```

---

## 3. DATA AGGREGATION & CHART BUILDING (Priority: MEDIUM-HIGH)

**Files**: `query.py`, `chart_tools.py`, `parsed_instance.py`
**Impact**: Every chart render and data view query

### What it does

Aggregates submission data for charts/dashboards:

1. Execute raw PostgreSQL queries with JSON operators
2. Fetch results into Python dicts
3. Group, sort, and label-map results in Python
4. Build chart-ready data structures

### Why it's slow in Python

| Bottleneck | Location | Issue |
|---|---|---|
| `_flatten_multiple_dict_into_one()` | chart_tools.py:151-170 | **O(N^2)** nested loop: iterates results * unique values to group data |
| `_use_labels_from_field_name()` | chart_tools.py:173-197 | Double iteration over data (once for labels, once for key rename) |
| `_use_labels_from_group_by_name()` | chart_tools.py:212-219 | Nested loop: items * sub-items for label replacement |
| Post-query sorting | chart_tools.py:329-341 | Python re-sort + timezone regex on every row |
| `_dictfetchall()` | query.py:18-22 | All rows materialized as dicts in memory |
| `get_field_records()` | query.py:244-247 | Python float conversion instead of SQL CAST |
| JSON parsing per row | parsed_instance.py:136-142 | `json.loads()` called per row in result iterator |

### Rust opportunity

- **Replace O(N^2) grouping** with HashMap-based O(N) grouping
- **Batch label lookups** with pre-built HashMap instead of linear scan
- **Parse JSON in bulk** using `serde_json` (much faster than Python's `json` module)
- **Handle timezone conversion** with compiled regex + chrono crate

**Estimated speedup**: 3-10x for aggregation queries on large datasets

### Proposed Rust module: `onadata_agg`

```
onadata_agg/
├── src/
│   ├── lib.rs         # PyO3 module entry
│   ├── grouping.rs    # HashMap-based grouping (replaces O(N²) loop)
│   ├── labels.rs      # Pre-indexed label lookups
│   ├── json_parse.rs  # Bulk JSON parsing
│   └── datetime.rs    # Timezone handling
└── Cargo.toml
```

---

## 4. ENCRYPTION / DECRYPTION (Priority: MEDIUM)

**Files**: `libs/kms/tools.py`, `logger/tasks.py`
**Impact**: Every encrypted submission

### What it does

For encrypted form submissions:

1. Load all encrypted attachments into memory (`BytesIO(file.read())`)
2. Call external KMS for key material (network-bound)
3. Decrypt submission XML and media files
4. Compute SHA256 of decrypted content
5. Save decrypted attachments individually

### Why it's slow in Python

| Bottleneck | Location | Issue |
|---|---|---|
| Attachment loading | tools.py:487-491 | All attachments loaded into memory simultaneously |
| SHA256 hashing | tools.py:560 | Python hashlib for potentially large files |
| Per-attachment DB writes | tools.py:570 | Individual `instance.attachments.create()` per file, no `bulk_create()` |

### Rust opportunity

- **Stream-decrypt** attachments without loading all into memory
- **Native SHA256** via `ring` or `sha2` crate (2-5x faster for large files)
- **Prepare bulk insert data** for batch DB writes
- Note: The KMS network call is the dominant bottleneck here and Rust won't help with that

**Estimated speedup**: 2-5x for the crypto/hashing portions (network I/O dominates overall)

### Proposed Rust module: `onadata_crypto`

```
onadata_crypto/
├── src/
│   ├── lib.rs         # PyO3 module entry
│   ├── decrypt.rs     # Streaming decryption
│   └── hash.rs        # Fast SHA256
└── Cargo.toml
```

---

## 5. BULK CSV IMPORT (Priority: MEDIUM)

**Files**: `csv_import.py`, `entities_utils.py`
**Impact**: Large CSV uploads (100k+ rows)

### What it does

Imports CSV data as form submissions or entity updates:

1. Count total rows (full file scan)
2. Parse each row, validate types
3. Transform flat CSV dict to nested dict
4. Generate XML submission per row
5. Process through full submission pipeline

### Why it's slow in Python

| Bottleneck | Location | Issue |
|---|---|---|
| Upfront row count | csv_import.py:341 | `sum(1 for row in csv_file)` scans entire file before processing |
| Per-row dict transformation | csv_import.py:424-432 | 3 nested function calls: `csv_dict_to_nested_dict()`, `flatten_split_select_multiples()`, `dict_merge()` |
| Per-row XML generation | csv_import.py:462 | `dict2xmlsubmission()` string manipulation per row |
| Per-row entity persistence | entities_utils.py:355 | Individual `serializer.save()`, no `bulk_create()` |

### Rust opportunity

- **Single-pass CSV parsing** with row count + processing combined (using `csv` crate)
- **Batch dict-to-XML conversion** with pre-compiled templates
- **Prepare bulk inserts** instead of per-row saves
- **Validate types** at parse time using Rust's type system

**Estimated speedup**: 3-8x for CSV parsing and transformation (DB writes still dominate)

---

## Prioritized Implementation Roadmap

### Phase 1: Export Engine (Highest ROI)
```
Effort:   ████████░░  (8/10)
Impact:   ██████████  (10/10)
Speedup:  10-50x for large exports
```
- Replace `ExportBuilder` core with Rust
- Stream-process rows, write XLSX/CSV directly
- Eliminate intermediate dict allocations
- Parallelize section writes across threads

### Phase 2: XML Submission Parser (High ROI)
```
Effort:   ██████░░░░  (6/10)
Impact:   ████████░░  (8/10)
Speedup:  5-20x per submission
```
- Single-pass XML parser replacing 6+ redundant parses
- Returns complete Python dict with all extracted data
- Eliminates recursive traversals

### Phase 3: Aggregation Engine (Medium ROI)
```
Effort:   ████░░░░░░  (4/10)
Impact:   ██████░░░░  (6/10)
Speedup:  3-10x for chart queries
```
- HashMap-based grouping replacing O(N^2) loops
- Bulk JSON parsing
- Pre-indexed label lookups

### Phase 4: Crypto Helpers (Lower ROI)
```
Effort:   ███░░░░░░░  (3/10)
Impact:   ████░░░░░░  (4/10)
Speedup:  2-5x for hashing (network I/O dominates)
```
- Streaming decryption
- Native SHA256

### Phase 5: CSV Import Parser (Lower ROI)
```
Effort:   ████░░░░░░  (4/10)
Impact:   ████░░░░░░  (4/10)
Speedup:  3-8x for parsing (DB writes dominate)
```
- Combined count + parse pass
- Batch transformation

---

## Integration Strategy: PyO3 Native Extensions

### Why PyO3

- Mature Rust-Python bridge with zero-copy where possible
- Compiles to native `.so`/`.dylib` that imports like any Python module
- Supports Python dicts, lists, strings natively
- Can release GIL for true parallelism

### Integration pattern

```python
# Before (Python)
from onadata.libs.utils.export_builder import ExportBuilder

builder = ExportBuilder()
builder.set_survey(survey)
builder.to_xlsx_export(path, data, username, xform)

# After (Rust via PyO3, drop-in replacement)
from onadata_export import RustExportBuilder

builder = RustExportBuilder()
builder.set_survey(survey)  # accepts Python survey object
builder.to_xlsx_export(path, data, username, xform)
```

### Build integration

```toml
# pyproject.toml addition
[build-system]
requires = ["maturin>=1.0,<2.0"]

[tool.maturin]
features = ["pyo3/extension-module"]
```

### Rollout strategy

1. Feature-flag each Rust module: `USE_RUST_EXPORTS=true`
2. Run both Python and Rust paths in parallel, compare outputs
3. Benchmark with production-scale data
4. Gradually shift traffic to Rust path
5. Remove Python implementation after validation

---

## Risk Assessment

| Risk | Mitigation |
|---|---|
| Rust introduces subtle behavior differences | Parallel execution + output comparison in staging |
| Build complexity (Rust toolchain in CI/CD) | maturin handles cross-compilation; pre-built wheels |
| Team unfamiliar with Rust | Start with Phase 1 (export) as learning project; well-defined interface |
| PyO3 overhead for small operations | Only port hot paths; keep Django/ORM in Python |
| Maintenance burden of two languages | Clear module boundaries; Rust modules are self-contained |

---

## Estimated Impact Summary

| Component | Current (100k rows) | With Rust | Speedup |
|---|---|---|---|
| XLSX Export | ~45-90 min | ~2-5 min | 10-50x |
| XML Submission Parse | ~15ms/submission | ~1-3ms | 5-20x |
| Chart Aggregation | ~5-15s | ~1-3s | 3-10x |
| Decryption (crypto only) | ~200ms/submission | ~50-100ms | 2-5x |
| CSV Import (parse only) | ~8ms/row | ~1-2ms/row | 3-8x |

**Note**: These are estimates based on typical Python-to-Rust speedups for similar workloads.
Actual numbers depend on data shape, hardware, and I/O patterns. The DB and network I/O
portions remain unchanged regardless of language.

---

## Conclusion

Your intuition is correct -- the form processing and export pipelines are the prime
candidates for Rust porting. The export engine (Phase 1) offers the highest ROI because:

1. It's the most CPU/memory-intensive code path
2. It processes the largest data volumes
3. It has well-defined inputs/outputs (easy to wrap with PyO3)
4. Python's GIL prevents parallelizing section writes
5. The recursive dict manipulation and regex-per-row patterns are exactly where Rust excels

Phase 2 (XML parsing) is the second priority because it affects every single submission
and currently parses the same XML 6+ times due to lack of caching between method calls.

The Django ORM, REST API, authentication, and routing should stay in Python -- Rust
offers no meaningful advantage for I/O-bound web framework code.
