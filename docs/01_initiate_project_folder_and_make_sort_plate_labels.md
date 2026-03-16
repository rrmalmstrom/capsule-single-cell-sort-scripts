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
Expected file: `sample_metadtata.csv` (note the intentional typo in filename)

**Required columns:**
- `Proposal`: Project proposal identifier
- `Project`: Project name/identifier  
- `Sample`: Sample identifier
- `Number_of_sorted_plates`: Integer count of plates per sample

**Optional columns:**
- `Collection Year`, `Collection Month`, `Collection Day`
- `Sample Isolated From`, `Latitude`, `Longitude`
- `Depth (m)`, `Elevation (m)`, `Country`

### Optional Input Files
- **`custom_plate_names.txt`**: Custom plate names (one per line, <20 characters)
- **`additional_standard_plates.txt`**: Additional plates for existing samples (format: `PROJECT_SAMPLE:COUNT`)

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
    Project TEXT,
    Sample TEXT,
    Collection_Year INTEGER,
    -- ... other metadata columns
);

-- individual_plates table  
CREATE TABLE individual_plates (
    plate_name TEXT,
    project TEXT,
    sample TEXT,
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
- "Add custom plates? (y/n)": Processes `custom_plate_names.txt` if available
- "Add additional standard plates? (y/n)": Processes `additional_standard_plates.txt` if available

This script establishes the foundation for the entire laboratory workflow, ensuring proper project initialization, unique plate identification, and organized file management that supports all downstream processing steps.