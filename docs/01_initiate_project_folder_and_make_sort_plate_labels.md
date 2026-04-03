# Script 1: initiate_project_folder_and_make_sort_plate_labels.py

## Overview
This is the **first script** in the laboratory workflow that initializes a new project and generates barcode labels for microwell plates. It serves as the foundation for the entire capsule sorting pipeline by creating the project structure, generating unique barcodes, and setting up the database architecture.

## Primary Functions

### Project Initialization
- **Creates standardized folder structure**: Automatically generates the complete workflow directory tree including:
  - `1_make_barcode_labels/` - For barcode generation files
  - `2_library_creation/` - For library preparation files  
  - `3_FA_analysis/` - For Fragment Analyzer results
  - `4_plate_selection_and_pooling/` - For final selection and pooling
  - `archived_files/` - For timestamped file archiving

### Barcode Generation System
- **Simplified incremental barcodes**: Uses a 5-character alphanumeric base (e.g., `ABC12`) with sequential numbering (`ABC12-1`, `ABC12-2`, etc.)
- **Collision-free design**: No duplicate checking needed due to sequential numbering
- **Variant support**: Creates Echo (`eABC12-1`) and Hamilton (`hABC12-1`) variants for different instruments
- **Custom base barcode support**: Accepts user-provided base barcodes via command line

### Database Architecture
- **Two-table SQLite database** (`project_summary.db`):
  - `sample_metadata`: Project and sample information from input CSV
  - `individual_plates`: Individual plate records with unique barcodes
- **Comprehensive data validation**: Ensures required columns and data types
- **Timestamped archiving**: Preserves previous database versions

## Input Requirements

### Sample Metadata CSV
Expected file: `sample_metadata.csv` (note the intentional typo in filename)

**Required columns:**
- `Proposal`: Project proposal identifier (used as the primary project key throughout the workflow). Must be alphanumeric only (no symbols or spaces), max 8 characters.
- `Group_or_abrvSample`: Abbreviated sample name used for plate naming (e.g., `SitukAM`). Stored in `individual_plates.sample` and used to construct plate names (e.g., `599999_SitukAM.1`). Must be alphanumeric only (no symbols or spaces), max 8 characters.
- `Sample_full`: Full sample identifier including any numeric suffix (e.g., `SitukAM.123`). Used in downstream SPITS file generation as part of the sample name.
- `Number_of_sorted_plates`: Integer count of plates per sample
- `is_custom`: Boolean flag indicating whether this sample uses a custom plate layout (`True`/`False` or `1`/`0`)

**`is_custom` column rules:**
- **Required** — every row must have an explicit value; empty cells cause a FATAL ERROR
- Accepted values (case-insensitive): `True`, `False`, `1`, `0`, `yes`, `no`
- When `True`, all plates generated for that sample are marked as custom in the database
- Custom plates require a corresponding layout CSV file in `2_library_creation/` for downstream processing (see Script 2)
- Standard plates (`is_custom=False`) use `standard_sort_layout.csv` as their layout template

**Optional columns:**
- `Collection Year`, `Collection Month`, `Collection Day`
- `Sample Isolated From`, `Latitude`, `Longitude`
- `Depth (m)`, `Elevation (m)`, `Country`

> **Note**: The `Project` column has been removed. `Proposal` now serves as the sole project identifier and is used to construct plate names (e.g., `BP9735_SitukAM.1`). The old `Sample` column has been split into `Group_or_abrvSample` (short alphanumeric name, max 8 chars, used for plate naming) and `Sample_full` (full identifier used in SPITS submission).

### Optional Input Files
- **`additional_standard_plates.txt`**: Additional plates for existing samples (format: `PROPOSAL_SAMPLE:COUNT`)

> **Note**: `custom_plate_names.txt` file-based input is **disabled**. Custom plate designation is now controlled entirely by the `is_custom` column in `sample_metadata.csv`. The underlying code is preserved in the script and can be re-enabled if needed.

## Output Files

### BarTender Label Files
- **Location**: `1_make_barcode_labels/bartender_barcode_labels/`
- **Format**: BarTender-compatible with header and reverse-ordered entries
- **Content**: Interleaved Echo/Hamilton pairs with separators
- **Filename**: `BARTENDER_sort_plate_labels_{timestamp}.txt`

### Database Files
- **`project_summary.db`**: Main SQLite database with two tables
- **Archived versions**: Timestamped copies in `archived_files/`

### CSV Files
- **`sample_metadata.csv`**: Updated sample metadata
- **`individual_plates.csv`**: Complete plate inventory with barcodes

## Key Features

### Run Type Detection
- **First run**: Creates new database and folder structure
- **Subsequent runs**: Adds plates to existing project, continues barcode numbering

### Safety Features
- **Laboratory-grade error handling**: "FATAL ERROR" messaging with `sys.exit()`
- **Comprehensive validation**: File format, column presence, data types
- **Automatic archiving**: Prevents data loss during updates
- **Barcode uniqueness**: Built-in collision avoidance

### File Organization
- **Timestamped processing**: All input files moved to organized folders with timestamps
- **Template preservation**: Standard layout template remains unchanged
- **Automatic cleanup**: Processed files archived to prevent reprocessing

## Technical Implementation

### Barcode Algorithm
```python
# Base barcode: 5 characters, first must be letter
base_barcode = "ABC12"  # Example
# Sequential numbering from existing max + 1
next_number = max_existing_number + 1
full_barcode = f"{base_barcode}-{next_number}"
```

### Database Schema
```sql
-- sample_metadata table
CREATE TABLE sample_metadata (
    Proposal TEXT,
    Group_or_abrvSample TEXT,   -- abbreviated name used for plate naming (max 8 alphanumeric chars)
    Sample_full TEXT,           -- full sample identifier (e.g., 'SitukAM.123')
    Collection_Year INTEGER,
    -- ... other metadata columns
);

-- individual_plates table
-- Note: the 'project' column stores the Proposal value (used as the project key)
-- Note: the 'sample' column stores the Group_or_abrvSample value
CREATE TABLE individual_plates (
    plate_name TEXT,
    project TEXT,      -- stores the Proposal value
    sample TEXT,       -- stores the Group_or_abrvSample value
    plate_number INTEGER,
    is_custom BOOLEAN,
    barcode TEXT,
    created_timestamp TEXT
);
```

## Error Handling
- **Missing CSV files**: Clear error messages with expected file locations
- **Invalid data formats**: Specific validation errors with correction guidance
- **Duplicate processing**: Prevents reprocessing of existing plates
- **File system errors**: Graceful handling of permission and disk space issues

## Integration Points
- **Output to Script 2**: Database and CSV files feed into [`generate_lib_creation_files.py`](02_generate_lib_creation_files.md)
- **Folder structure**: Creates complete directory tree used by all subsequent scripts
- **Barcode system**: Establishes unique identifiers used throughout workflow

## Usage Examples

### Basic Usage
```bash
python initiate_project_folder_and_make_sort_plate_labels.py
```

### With Custom Base Barcode
```bash
python initiate_project_folder_and_make_sort_plate_labels.py REX12
```

### Interactive Prompts
- "Add additional standard plates? (y/n)": Processes `additional_standard_plates.txt` if available

> **Note**: The "Add custom plates? (y/n)" prompt has been removed. Custom plates are now designated via the `is_custom` column in `sample_metadata.csv`.

This script establishes the foundation for the entire laboratory workflow, ensuring proper project initialization, unique plate identification, and organized file management that supports all downstream processing steps.