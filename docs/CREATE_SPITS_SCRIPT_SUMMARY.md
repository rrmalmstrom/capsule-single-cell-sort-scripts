# Laboratory SPITS File Generation Script Summary

## Overview
The `create_spits.py` script processes plate selection input to generate SPITS (Sample Processing and Information Tracking System) files for selected plates and wells following laboratory automation standards.

## Script Execution
```bash
python create_spits.py
```

**Requirements:**
- Must use `sip-lims` conda environment
- Run from the working directory containing input files
- Requires existing `project_summary.db` database with completed FA analysis
- Requires plate selection CSV file in `4_plate_selection_and_pooling/` folder

## Input Files Required

### 1. Plate Selection CSV (Required)
**Filename:** `plate_selection.csv`
**Location:** `4_plate_selection_and_pooling/` folder
**Format:** CSV with UTF-8 encoding

**Required Columns:**
- `Plate_ID` - Plate identifier (e.g., BP9735_SitukAM.1)
- `Index_sets` - Comma-separated index sets or empty for all sets

**Example:**
```csv
Plate_ID,Index_sets
BP9735_SitukAM.1,PE17,PE19
BP9735_SitukAM.2,
Rex_badass_custom.1,PE18
```

### 2. Database Dependencies
**Filename:** `project_summary.db`
**Location:** Working directory
**Required Tables:**
- `sample_metadata` - Project and sample information with Proposal column
- `individual_plates` - Plate data with upper_left_registration column
- `master_plate_data` - Well-level data with FA results and index assignments

## Output Structure

The script creates organized output in the existing folder structure:

```
4_plate_selection_and_pooling/
├── {proposal}_capsule_sort_SPITS.csv
└── plate_selection.csv (input file)
```

## Generated Files

### 1. SPITS CSV File
**Location:** `4_plate_selection_and_pooling/`
**Filename:** `{proposal}_capsule_sort_SPITS.csv` (e.g., `BP9735_capsule_sort_SPITS.csv`)
**Format:** CSV file with SPITS-compatible headers and data

**Content:**
- Selected well data from chosen plates
- Dynamic field population from database tables
- Template string processing for sample names
- Fixed values for standard laboratory parameters

## Well Selection Logic

### Upper Left Registration Plates
- **Selection Criteria:** Sample and negative control wells that passed FA analysis
- **Filter:** `Type` in ['sample', 'neg_cntrl'] AND `Passed_library` = 1
- **Index Sets:** Not applicable (uses single index set per plate)

### Full Plates
- **Selection Criteria:** Sample and negative control wells from specified index sets
- **Filter:** `Type` in ['sample', 'neg_cntrl'] AND `Index_Set` in specified sets
- **Index Sets:** Uses specified sets or all available sets if column is empty
- **FA Results:** Includes all wells regardless of FA pass/fail status

## Database Updates

### Individual Plates Table
- Adds `selected_for_pooling` column (boolean) to track plate selection status
- Updates plates that were included in SPITS file generation

### Master Plate Data Table
- Adds `selected_for_pooling` column (0/1) to track well-level selection
- Updates wells that were included in SPITS file output

## Validation Features

### Input Validation
- **Plate Existence:** All plates in selection must exist in individual_plates table
- **FA Completion:** All plates must have completed FA analysis (exist in master_plate_data)
- **Index Set Validation:** Specified index sets must be valid (PE17, PE18, PE19, PE20)
- **Index Set Availability:** Specified index sets must exist on each plate

### Data Integrity
- **Non-empty Selection:** Each plate must have at least some wells meeting criteria
- **Proposal Consistency:** All samples must belong to the same proposal
- **Database Schema:** Required columns must exist in all database tables

## SPITS File Format

### Header Mapping
- Uses SPITS_header_key.csv mapping for field definitions
- Dynamic field population from master_plate_data and sample_metadata tables
- Template string processing for complex sample name generation

### Data Fields
- **Well Information:** Plate ID, well position, sample identifiers
- **Quality Data:** FA results, concentration, size measurements
- **Index Information:** Index set assignments and primer details
- **Laboratory Parameters:** Fixed values for standard processing parameters

## Workflow Process

### 1. Database Validation
- Reads all required database tables
- Validates schema and required columns
- Checks for FA analysis completion

### 2. Plate Selection Processing
- Reads and validates plate selection CSV
- Confirms all plates exist in database
- Validates index set specifications

### 3. Well Selection
- Applies appropriate selection logic based on plate type
- Filters wells based on type and quality criteria
- Handles index set filtering for full plates

### 4. SPITS Generation
- Extracts proposal name for file naming
- Processes selected wells through SPITS template
- Generates final SPITS CSV file

### 5. Database Updates
- Archives existing database with timestamp
- Updates selection tracking columns
- Maintains data integrity and audit trail

## Error Handling

- **FATAL ERROR** prefix for all critical errors
- Comprehensive input file validation
- Database integrity checks
- Plate and index set validation
- Laboratory-grade safety messaging
- Graceful exit with `sys.exit()` on errors

## Safety Features

- **Database Archiving:** Automatic backup before updates
- **Input Validation:** Comprehensive checks for all input data
- **Selection Verification:** Ensures meaningful well selection results
- **Audit Trail:** Tracks which plates and wells were selected for pooling
- **Error Prevention:** Fail-fast validation prevents partial processing

## Integration Points

### Upstream Dependencies
- Requires completed barcode label generation (individual_plates table)
- Requires completed library creation (master_plate_data table)
- Requires completed FA analysis (FA results in master_plate_data)

### Downstream Usage
- SPITS file used for laboratory sample processing and tracking
- Database updates support workflow management and audit requirements
- Selection tracking enables reprocessing and quality control workflows