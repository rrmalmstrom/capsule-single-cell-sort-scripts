# Laboratory Barcode Label Generation Script Summary

## Overview
The `generate_barcode_labels.py` script generates BarTender-compatible barcode labels for microwell plates containing sorted capsules

## Script Execution
```bash
python generate_barcode_labels.py [CUSTOM_BASE_BARCODE]
```

**Requirements:**
- Must use `sip-lims` conda environment
- Run from the working directory containing input files

**Optional Arguments:**
- `CUSTOM_BASE_BARCODE`: 5-character custom base barcode (e.g., REX12). Must start with a letter and contain only uppercase letters and digits.

## Input Files Required

### 1. Sample Metadata CSV (Required)
**Filename:** `sample_metadata.csv`
**Location:** Working directory (first run only)
**Format:** CSV with UTF-8 encoding

**Required Columns:**
- `Proposal` - Project proposal identifier
- `Project` - Project name/code
- `Sample` - Sample identifier
- `Number_of_sorted_plates` - Integer count of plates per sample

**Optional Columns:**
- `Collection Year`, `Collection Month`, `Collection Day`
- `Sample Isolated From`, `Latitude`, `Longitude`
- `Depth (m)`, `Elevation (m)`, `Country`

**Example:**
```csv
Proposal,Project,Sample,Number_of_sorted_plates,Collection Year
BP9735,BP9735,SitukAM,2,2023
BP9735,BP9735,WCBP1PR,3,2023
```

### 2. Custom Plate Names (Optional)
**Filename:** `custom_plate_names.txt`
**Location:** 
- **First run:** Working directory
- **Subsequent runs:** `1_make_barcode_labels/` folder

**Format:** Plain text, one plate name per line
**Constraints:** Each name must be < 20 characters

**Example:**
```
Rex_badass_custom.1
MA_test_44.1
```

### 3. Additional Standard Plates (Optional)
**Filename:** `additional_standard_plates.txt`
**Location:** 
- **Subsequent runs:** `1_make_barcode_labels/` folder

**Format:** Plain text, format `PROJECT_SAMPLE:COUNT` (note, the count is the number of addtional plates to add to that particular sample, not the next plate number in the series)

**Example:**
**adds two more plates to BP9735_SitukAM and one more to BP9735_WCBP1PR**
```
BP9735_SitukAM:2
BP9735_WCBP1PR:1
```



## Interactive Prompts

### First Run
1. **"Add custom plates? (y/n):"** - Add custom plates from `custom_plate_names.txt`

### Subsequent Runs
1. **"Add additional standard plates to existing samples? (y/n):"** - Add more plates to existing samples
2. **"Add custom plates? (y/n):"** - Add custom plates

## Output Structure

The script creates an organized folder structure:

```
working_directory/
├── 1_make_barcode_labels/
│   ├── bartender_barcode_labels/
│   │   └── BARTENDER_sort_plate_labels_[timestamp].txt
│   └── previously_process_label_input_files/
│       ├── custom_plates/
│       │   └── custom_plate_names_[timestamp].txt
│       └── standard_plates/
│           └── additional_standard_plates_[timestamp].txt
├── 2_library_creation/
├── 3_FA_analysis/
├── archived_files/
│   ├── project_summary_[timestamp].db
│   ├── sample_metadata_[timestamp].csv
│   └── plate_names_[timestamp].csv
├── sample_metadata.csv (updated)
├── plate_names.csv (updated)
└── project_summary.db (current database)
```

## Generated Files

### 1. BarTender Label File
**Location:** `1_make_barcode_labels/bartender_barcode_labels/`
**Format:** Text file with BarTender header and barcode data
**Content:** 
- Echo labels: `e[BARCODE],"[PLATE_NAME]"`
- Hamilton labels: `h[BARCODE],"h[BARCODE]"`
- Reverse order (highest to lowest barcode numbers)
- Interleaved echo/hamilton pairs with separators

### 2. Database File
**Filename:** `project_summary.db`
**Format:** SQLite database with two tables:
- `sample_metadata` - Project and sample information
- `individual_plates` - Individual plate data with barcodes

### 3. Updated CSV Files
- `sample_metadata.csv` - Current sample metadata
- `plate_names.csv` - All plates with barcodes and metadata

## Barcode System

**Format:** 5-character alphanumeric base + incremental number
- **Base:** First character = letter, remaining 4 = letters/numbers
- **Numbering:** BASE-1, BASE-2, BASE-3, etc.
- **Echo variant:** eBASE-1, eBASE-2 (lowercase 'e' prefix)
- **Hamilton variant:** hBASE-1, hBASE-2 (lowercase 'h' prefix)

**Example:** `YL28G-1`, `YL28G-2`, `YL28G-3`

## File Management Features

### Timestamped File Movement
- All processed input files are moved with unique timestamps
- Format: `filename_YYYY_MM_DD-TimeHH-MM-SS.ext`
- Prevents overwrites on subsequent runs
- Maintains complete history of processed files

### Smart File Location Detection
- **First runs:** Script looks for input files in working directory
- **Subsequent runs:** Script looks for input files in `1_make_barcode_labels/` folder
- Automatic detection based on existing database

### Archive System
- Previous versions of database and CSV files are archived with timestamps
- Archived files stored in `archived_files/` folder
- Ensures data preservation and rollback capability

## Workflow Process

### First Run

1. Detects no existing database → First run mode
2. Reads `sample_metadata.csv` from working directory
3. Generates standard plates from sample metadata
4. Optionally adds custom plates from `custom_plate_names.txt`
5. Generates base barcode and sequential numbering
6. Creates BarTender file, database, and organized folder structure
7. Moves input files to organized folders with timestamps

### Subsequent Runs
1. Detects existing database → Subsequent run mode
2. Optionally adds additional standard plates from `1_make_barcode_labels/additional_standard_plates.txt`
3. Optionally adds custom plates from `1_make_barcode_labels/custom_plate_names.txt`
4. Continues barcode numbering from existing sequence
5. Updates database and creates new BarTender file
6. Moves new input files to organized folders with timestamps

## Error Handling

- **FATAL ERROR** prefix for all critical errors
- Comprehensive validation of input file formats
- Barcode uniqueness validation
- Laboratory-grade safety messaging
- Graceful exit with `sys.exit()` on errors

## Safety Features

- Automatic file archiving before updates
- Input file validation (column names, data types, constraints)
- Organized file management prevents data loss
- Timestamped file movement prevents overwrites