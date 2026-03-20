# Script 6: verify_scanning_and_generate_ESP_files.py

## Overview
This is the **sixth and final script** in the refactored laboratory workflow. It replaces the ESP file generation portion of the older `make_ESP_smear_analysis_file.py` script. It first verifies that barcode scanning was completed correctly (using the Excel template populated by Script 5), then generates ESP smear analysis files for upload to the external system.

> **Note**: The older scripts `make_ESP_smear_analysis_file.py` and `relabel_lib_plates_for_pooling.py` are no longer used in the active workflow. They are retained for reference only.

## Workflow Position

```
[Script 5: process_grid_tables_and_generate_barcodes.py]
        ↓
Manual Step: User completes barcode scanning in Excel template
        ↓
[Script 6: verify_scanning_and_generate_ESP_files.py]  ← THIS SCRIPT
```

## Primary Functions

### Barcode Scanning Verification (CRITICAL)
- **Locates** the completed Excel scanning file in `B_new_plate_barcode_labels/`
- **Validates** the Checker column (Column D) for any `FALSE` values
- **Fail-fast**: Any `FALSE` value causes immediate `sys.exit()` — no ESP files are generated
- **Acceptable values**: `True` (boolean, scan matched) or `"empty"` (string, unused slot)

### ESP Smear File Generation
- **Standardized format**: Creates 13-column ESP-compatible smear analysis files
- **Per-plate output**: Generates separate files for each Library Plate Container Barcode
- **Fixed parameters**: Applies laboratory-standard values for ESP submission
- **Output directory**: `4_plate_selection_and_pooling/C_smear_file_for_ESP_upload/`

### Database Updates (Script 6 responsibility)
- **ESP status columns**: Adds `esp_generation_status`, `esp_generated_timestamp`, `esp_batch_id` to `individual_plates`
- **Status values**: Selected plates set to `'generated'`; non-selected plates default to `'pending'`
- **CSV refresh**: Archives old `individual_plates.csv` and regenerates with ESP columns included

## Input Requirements

### Database Dependencies
- **Complete database** from Script 5:
  - `sample_metadata`: Project information (proposal value for file lookup)
  - `individual_plates`: Must have `library_plate_container_barcode` column (set by Script 5)
  - `master_plate_data`: Must have `Library Plate Container Barcode` column (set by Script 5)

### Excel Barcode Scanning File
- **Location**: `4_plate_selection_and_pooling/B_new_plate_barcode_labels/`
- **Filename**: `{proposal}_pool_label_scan_verificiation_tool.xlsx`
- **Required state**: User must have completed scanning (Column E filled in)
- **Validation**: All Checker values (Column D) must be `True` or `"empty"` — no `FALSE`

## Output Files

### ESP Smear Analysis Files
- **Location**: `4_plate_selection_and_pooling/C_smear_file_for_ESP_upload/`
- **Filename pattern**: `ESP_smear_file_for_upload_{container_barcode}.csv`
- **Format**: 13-column CSV with ESP-required headers
- **Content**: One file per unique Library Plate Container Barcode

### ESP File Format
```csv
Well,Sample ID,Range,ng/uL,%Total,nmole/L,Avg. Size,%CV,Volume uL,QC Result,Failure Mode,Index Name,PCR Cycles
```

### ESP Column Mapping
```python
ESP_COLUMN_MAPPING = {
    'Well': 'Well',                           # From master_plate_data
    'Sample ID': 'Illumina Library',          # From grid table (via Script 5 merge)
    'Range': '400 bp to 800 bp',             # Fixed value
    'ng/uL': 'ng/uL',                        # From FA results
    '%Total': 15,                            # Fixed value
    'nmole/L': 'nmole/L',                    # From FA results
    'Avg. Size': 'Avg. Size',               # From FA results
    '%CV': 20,                              # Fixed value
    'Volume uL': 20,                        # Fixed value
    'QC Result': 'Pass',                    # Always Pass
    'Failure Mode': '',                     # Always empty
    'Index Name': 'Index_Name',             # From database
    'PCR Cycles': 12                        # Fixed value
}
```

### Refreshed CSV File
- **Location**: Project root directory
- **Filename**: `individual_plates.csv`
- **Content**: All `individual_plates` table columns including new ESP status columns
- **Old version**: Archived to `archived_files/individual_plates_{timestamp}.csv`

## Barcode Scanning Validation Logic

The Excel template Checker column (Column D) contains formulas that evaluate to:
- `True` — scanned barcode matches expected barcode (both plate name and LIMS ID)
- `"empty"` — no expected barcode and no scanned barcode (unused slot)
- `False` — **MISMATCH**: scanned barcode does not match expected barcode

**Validation checks rows 2, 4, 6, ... 40** (the "plate name" rows where Checker formulas live).

```python
# Script reads Excel with data_only=True to get formula-evaluated values
workbook = openpyxl.load_workbook(excel_path, data_only=True)

# Any False value → immediate sys.exit()
for row in range(2, 42, 2):  # plate name rows only
    if worksheet.cell(row=row, column=4).value is False:
        sys.exit()  # FATAL — do not generate ESP files
```

**Why this matters**: A `False` value means a physical barcode was scanned incorrectly. Generating ESP files with wrong container barcodes would cause laboratory errors. The script must refuse to proceed.

## Technical Implementation

### Database Schema Updates (Script 6 only)
```sql
-- Add ESP tracking columns to individual_plates
ALTER TABLE individual_plates ADD COLUMN esp_generation_status TEXT DEFAULT 'pending';
ALTER TABLE individual_plates ADD COLUMN esp_generated_timestamp TEXT;
ALTER TABLE individual_plates ADD COLUMN esp_batch_id TEXT;

-- Update selected plates after successful ESP file generation
UPDATE individual_plates
SET esp_generation_status = 'generated',
    esp_generated_timestamp = '2026-03-20T10:14:22.231563',
    esp_batch_id = '2026_03_20-Time10-14-22'
WHERE barcode IN ('XUPVQ-1', 'XUPVQ-3', 'XUPVQ-6');
```

> **Note**: `library_plate_container_barcode` is NOT modified by Script 6. It was set by Script 5 and is read-only here.

### File Organization
- **ESP output**: New files created in `C_smear_file_for_ESP_upload/`
- **CSV archiving**: Old `individual_plates.csv` moved to `archived_files/` with timestamp
- **CSV regeneration**: Fresh `individual_plates.csv` created from updated database
- **No grid file changes**: Grid files were already archived by Script 5

### Error Handling
- **Missing Excel file**: Exits with clear message about expected location and filename
- **FALSE in Checker column**: Exits with row numbers of failed checks
- **Missing Script 5 columns**: Exits if `library_plate_container_barcode` not in database
- **Empty data**: Exits if no samples with grid data found for ESP generation
- **Database errors**: Exits with error details

## Integration Points
- **Input from Script 5**: Reads merged `master_plate_data` and `library_plate_container_barcode` from [`process_grid_tables_and_generate_barcodes.py`](05_process_grid_tables_and_generate_barcodes.md)
- **Manual dependency**: Requires user to complete barcode scanning in Excel before running
- **External output**: ESP smear files uploaded to external ESP system

## Usage

### Basic Usage
```bash
cd /path/to/project_directory
python /path/to/verify_scanning_and_generate_ESP_files.py
```

### Expected Output (Success)
```
============================================================
Starting barcode verification and ESP file generation...
============================================================

[Step 1] Getting proposal value from database...
  ✓ Proposal: 599999

[Step 2] Finding barcode scanning file...
  ✓ Found: 599999_pool_label_scan_verificiation_tool.xlsx

[Step 3] Validating barcode scanning completion...
  ✓ Barcode scanning validation passed (no FALSE values in Checker column)

[Step 4] Reading project database...
  ✓ master_plate_data: 2304 rows
  ✓ individual_plates: 6 rows

[Step 5] Generating ESP smear analysis files...
  ✓ Created ESP smear file: ESP_smear_file_for_upload_27-810254.csv (71 samples)
  ✓ Created ESP smear file: ESP_smear_file_for_upload_27-000002.csv (64 samples)
  ✓ Created ESP smear file: ESP_smear_file_for_upload_27-999999.csv (376 samples)

[Step 6] Updating database with ESP generation status...
  ✓ ESP status updated for 3 plate(s)

[Step 7] Refreshing individual_plates.csv...
  ✓ Archived: individual_plates_2026_03_20-Time10-14-22.csv
  ✓ Fresh individual_plates.csv generated (includes ESP status columns)

============================================================
🎉 Barcode verification and ESP file generation completed successfully!
📊 Generated 3 ESP smear file(s)
📁 Output directory: 4_plate_selection_and_pooling/C_smear_file_for_ESP_upload/
============================================================
```

### Expected Output (Failure — FALSE in Checker)
```
[Step 3] Validating barcode scanning completion...
FATAL ERROR: Barcode scanning validation failed!
Found FALSE values in Checker column (Column D) at rows: [4, 8]
This means scanned barcodes do not match expected barcodes.
Please review and correct the barcode scanning before proceeding.
SCRIPT TERMINATED: Barcode scanning validation failed
```

## Quality Control Features
- **Zero-tolerance validation**: Any barcode mismatch prevents ESP file generation
- **Detailed error reporting**: Reports exact row numbers of failed checks
- **Data integrity**: Verifies Script 5 has run before proceeding
- **Fail-fast design**: Immediate `sys.exit()` on any error — no partial state corruption
- **Workflow manager integration**: Creates `.workflow_status/verify_scanning_and_generate_ESP_files.success` marker on completion

## Comparison with Older Scripts

| Feature | Old Workflow | New Workflow |
|---------|-------------|-------------|
| Barcode scanning verification | None | ✅ Mandatory — script exits on mismatch |
| ESP file generation | `make_ESP_smear_analysis_file.py` | `verify_scanning_and_generate_ESP_files.py` |
| Barcode label generation | `relabel_lib_plates_for_pooling.py` (ran after ESP) | `process_grid_tables_and_generate_barcodes.py` (runs before scanning) |
| ESP output directory | `B_smear_file_for_ESP_upload/` | `C_smear_file_for_ESP_upload/` |
| ESP status DB columns | Added by old Script 5 | Added by new Script 6 |
| Container barcode DB column | Added by old Script 5 | Added by new Script 5 |
