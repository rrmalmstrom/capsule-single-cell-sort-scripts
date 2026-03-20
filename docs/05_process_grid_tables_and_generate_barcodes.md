# Script 5: process_grid_tables_and_generate_barcodes.py

## Overview
This is the **fifth script** in the refactored laboratory workflow. It replaces the combined functionality previously split between `make_ESP_smear_analysis_file.py` and `relabel_lib_plates_for_pooling.py` by handling grid table processing and barcode scanning material generation as a single step. ESP smear file generation has been moved to Script 6 (`verify_scanning_and_generate_ESP_files.py`), which runs after manual barcode scanning verification.

> **Note**: The older scripts `make_ESP_smear_analysis_file.py` and `relabel_lib_plates_for_pooling.py` are no longer used in the active workflow. They are retained for reference only.

## Workflow Position

```
[Script 4: create_capsule_spits.py]
        ↓
[Script 5: process_grid_tables_and_generate_barcodes.py]  ← THIS SCRIPT
        ↓
Manual Step: User completes barcode scanning in Excel template
        ↓
[Script 6: verify_scanning_and_generate_ESP_files.py]
```

## Primary Functions

### Grid Table Processing
- **Multi-file support**: Discovers and processes all valid grid table CSV files in `4_plate_selection_and_pooling/`
- **Data validation**: Ensures grid tables contain exactly the expected samples from pooling selection
- **Duplicate detection**: Prevents processing of samples appearing in multiple grid files
- **Completeness verification**: Validates perfect match between expected and actual samples

### Database Updates
- **Container barcode mapping**: Extracts `Library Plate Container Barcode` from grid tables and stores in `individual_plates.library_plate_container_barcode`
- **Master data enhancement**: Merges grid table columns (`Illumina Library`, `Nucleic Acid ID`, `Library Plate Container Barcode`) into `master_plate_data`
- **Archiving**: Timestamps and archives the database, old CSV files, and processed grid files

### Barcode Scanning Material Generation
- **Excel template**: Copies blank template and populates Column C (Expected Barcode) only — 2 rows per plate
- **BarTender file**: Generates container label file for physical label printing
- **Output directory**: `4_plate_selection_and_pooling/B_new_plate_barcode_labels/`

## Input Requirements

### Database Dependencies
- **Complete database structure** from Script 4:
  - `sample_metadata`: Project information (proposal value)
  - `individual_plates`: Plates with `selected_for_pooling = 1`
  - `master_plate_data`: Wells with `selected_for_pooling = 1`

### Grid Table Files
- **Location**: `4_plate_selection_and_pooling/` directory (top-level only)
- **Format**: CSV files with required columns
- **Auto-discovery**: Script finds all valid grid table files automatically

### Required Grid Table Columns
```csv
Well,Library Plate Label,Illumina Library,Library Plate Container Barcode,Nucleic Acid ID
```

### Template File
- **Location**: Same directory as the script
- **Filename**: `BLANK_TEMPLATE_Pooling_Plate_Barcode_Scan_tool.xlsx`
- **Required**: Script will exit if template is not found

## Output Files

### Excel Barcode Scanning Template
- **Location**: `4_plate_selection_and_pooling/B_new_plate_barcode_labels/`
- **Filename pattern**: `{proposal}_pool_label_scan_verificiation_tool.xlsx`
- **Content**: Column C (Expected Barcode) populated with plate barcodes and container barcodes
- **Template structure**: 2 rows per plate — "plate name" row and "LIMS ID" row

### BarTender Container Label File
- **Location**: `4_plate_selection_and_pooling/B_new_plate_barcode_labels/`
- **Filename pattern**: `BARTENDER_{proposal}_container_labels.txt`
- **Content**: Container barcodes formatted for BarTender label printing system

## Excel Template Population Logic

The Excel template has a fixed structure with 2 rows per plate starting at row 2:

| Row | Column A | Column B | Column C (populated by script) | Column D | Column E |
|-----|----------|----------|-------------------------------|----------|----------|
| 1 | sample | type | Expected Barcode | Checker | Scanned barcode |
| 2 | 1 | plate name | XUPVQ-1 | =IF(...) | (user scans) |
| 3 | | LIMS ID | 27-810254 | | (user scans) |
| 4 | 2 | plate name | XUPVQ-3 | =IF(...) | (user scans) |
| 5 | | LIMS ID | 27-000002 | | (user scans) |

**Row calculation**:
```python
plate_name_row = 2 + (i * 2)   # Row for plate barcode (e.g., XUPVQ-1)
lims_id_row    = 3 + (i * 2)   # Row for container barcode (e.g., 27-810254)
```

**Critical**: Only Column C is modified. Columns A, B, D, and E are never touched.

## Key Features

### Grid Table Validation Pipeline
```python
# 1. Find all CSV files in 4_plate_selection_and_pooling/
# 2. Validate each for required columns
# 3. Read and combine all valid grid tables
# 4. Check for duplicate samples across files
# 5. Verify exact match with expected samples from database
```

### Library Container Barcode Mapping
- **Extraction**: Derives mapping from grid table `Library Plate Label` → `Library Plate Container Barcode`
- **Example**: `{'XUPVQ-1': '27-810254', 'XUPVQ-3': '27-000002', 'XUPVQ-6': '27-999999'}`
- **Database update**: Stored in `individual_plates.library_plate_container_barcode`
- **Fail-fast**: Script exits if any selected plate has no container barcode in the grid table

### Merge Strategy
```python
# Grid table: ['Library Plate Label', 'Well']
# Master data: ['Plate_Barcode', 'Well']
# Left join: preserves all master data, adds grid columns for selected wells
merged_df = pd.merge(master_plate_df, grid_merge_df, on=['Plate_Barcode', 'Well'], how='left')
```

## Technical Implementation

### Database Schema Updates (Script 5 only)
```sql
-- Add container barcode column to individual_plates
ALTER TABLE individual_plates ADD COLUMN library_plate_container_barcode TEXT;

-- Grid table columns added to master_plate_data (via table replacement)
-- Illumina Library, Nucleic Acid ID, Library Plate Container Barcode
```

> **Note**: ESP status columns (`esp_generation_status`, `esp_generated_timestamp`, `esp_batch_id`) are added by Script 6, not Script 5.

### File Organization
- **Grid table archiving**: Processed files moved to `4_plate_selection_and_pooling/previously_processed_grid_files/`
- **Database archiving**: Timestamped database copy in `archived_files/`
- **CSV archiving**: Old `master_plate_data.csv` and `individual_plates.csv` moved to `archived_files/`
- **CSV regeneration**: Fresh CSV files created from updated database

### Error Handling
- **Missing grid tables**: Clear guidance on required file location and format
- **Sample mismatches**: Detailed reporting of missing or unexpected samples
- **Missing container barcodes**: Exits immediately if any selected plate lacks a container barcode
- **Template not found**: Exits with clear message about template file location
- **Too many plates**: Exits if plate count exceeds template capacity (20 plates)

## Integration Points
- **Input from Script 4**: Reads selection status from [`create_capsule_spits.py`](04_create_capsule_spits.md)
- **Output to Script 6**: Container barcode mapping and Excel template feed into [`verify_scanning_and_generate_ESP_files.py`](06_verify_scanning_and_generate_ESP_files.md)
- **External dependency**: Requires grid table files from external pooling system
- **Manual step**: User must complete barcode scanning in Excel before running Script 6

## Usage

### Basic Usage
```bash
cd /path/to/project_directory
python /path/to/process_grid_tables_and_generate_barcodes.py
```

### Expected Output
```
============================================================
Starting grid table processing and barcode generation...
============================================================

[Step 1] Reading project database...
  ✓ master_plate_data: 2304 rows
  ✓ individual_plates: 6 rows

[Step 2] Identifying samples selected for pooling...
  ✓ 3 plate(s) selected for pooling
  ✓ 511 sample(s) expected in grid tables

[Step 3] Finding grid table files...
  ✓ Found 3 valid grid table file(s):
    - grid_XUPVQ-1.csv
    - grid_XUPVQ-3.csv
    - grid_XUPVQ-6.csv

[Step 4] Reading and validating grid tables...
  ✓ Grid tables valid: 511 total rows, no duplicates

[Step 5] Extracting Library Plate Container Barcode mapping...
  ✓ XUPVQ-1 → 27-810254
  ✓ XUPVQ-3 → 27-000002
  ✓ XUPVQ-6 → 27-999999

[Step 6] Merging grid data with master plate data...
  ✓ Merged dataframe: 2304 rows

[Step 7] Archiving database and updating tables...
  ✓ Database archived: project_summary_2026_03_20-Time10-02-50.db
  ✓ individual_plates updated for 3 plate(s)
  ✓ master_plate_data table updated

[Step 8] Archiving grid files and regenerating CSV files...
  ✓ 3 grid file(s) archived
  ✓ Fresh CSV files generated

[Step 9] Generating barcode scanning materials...
  ✓ Proposal: 599999
  ✓ 3 plate(s) ready for barcode generation
  ✓ Excel template created: 599999_pool_label_scan_verificiation_tool.xlsx
  ✓ BarTender file created: BARTENDER_599999_container_labels.txt

============================================================
🎉 Grid processing and barcode generation completed successfully!
📊 Processed 3 plate(s)
📁 Output directory: 4_plate_selection_and_pooling/B_new_plate_barcode_labels/

NEXT STEP: Open the Excel file, complete barcode scanning,
           then run verify_scanning_and_generate_ESP_files.py
============================================================
```

## Quality Control Features
- **Perfect validation**: Ensures exact match between expected and grid table samples
- **Duplicate prevention**: Blocks processing if samples appear in multiple grid files
- **Data integrity**: Validates all expected samples receive grid table data
- **Fail-fast design**: Immediate `sys.exit()` on any error — no partial state corruption
- **Workflow manager integration**: Creates `.workflow_status/process_grid_tables_and_generate_barcodes.success` marker on completion
