# Laboratory Library Creation Files Generation Script Summary

## Overview
The `generate_lib_creation_files.py` script processes sorted microwell plates to generate comprehensive library creation files including index assignments, FA transfer protocols, and master data tracking following laboratory automation standards.

## Script Execution
```bash
python generate_lib_creation_files.py
```

**Requirements:**
- Must use `sip-lims` conda environment
- Run from the working directory containing input files
- Requires existing `project_summary.db` database from barcode label generation

## Input Files Required

### 1. Library Sort Plates List (Required)
**Filename:** `library_sort_plates.txt`
**Location:** `2_library_creation/` folder
**Format:** Plain text, one plate name per line

**Example:**
**The file contains a list of sorted plates ready for lib creation**
```
BP9735_SitukAM.1
BP9735_SitukAM.2
Rex_badass_custom.1
MA_test_44.1
```

### 2. Custom Plate Layout Files (Required for Custom Plates)
**Filename:** `{plate_name}.csv` (e.g., `Rex_badass_custom.1.csv`)
**Location:** `2_library_creation/` folder
**Format:** CSV with UTF-8 encoding

**Required Columns:**
- `Plate_ID` - Must match the plate name exactly
- `Well_Row` - Well row letter (A-P for 384-well)
- `Well_Col` - Well column number (1-24 for 384-well)
- `Well` - Combined well position (e.g., A1, B12)
- `Sample` - Sample identifier or empty for non-sample wells
- `Type` - Well type: `sample`, `pos_cntrl`, `neg_cntrl`, `unused`, `ladder`
- `number_of_cells/capsules` - Cell/capsule count
- `Group_1`, `Group_2`, `Group_3` - Grouping categories

### 3. Standard Sort Layout Template (Required)
**Filename:** `standard_sort_layout.csv`
**Format:** CSV template for standard plates (same columns as custom plates)
**Usage:** Applied to standard plates that don't have individual layout files

### 4. Individual Standard Plate Files (Optional)
**Filename:** `{plate_name}.csv` for standard plates
**Location:** `2_library_creation/` folder
**Format:** Same as custom plate layout files
**Usage:** Overrides standard template for specific standard plates

## Database Dependencies

### Required Database Tables
The script requires an existing `project_summary.db` database with:

**1. sample_metadata table:**
- Project and sample information
- Created by barcode label generation script

**2. individual_plates table:**
- Plate names, barcodes, project/sample associations
- `is_custom` flag (0 for standard, 1 for custom)
- Created by barcode label generation script

## Output Structure

The script creates organized output folders:

```
2_library_creation/
├── Illumina_index_transfer_files/
│   └── Illumina_index_{plate_name}.csv
├── FA_transfer_files/
│   └── FA_plate_transfer_{plate_name}.csv
├── FA_input_files/
│   └── FA_input_{plate_name}_{barcode}.csv
├── previously_processed_files/
│   ├── list_of_sorted_plates/
│   │   └── library_sort_plates_{timestamp}.txt
│   └── plate_layout_files/
│       └── {plate_name}.csv
└── standard_sort_layout.csv
```

## Generated Files

### 1. Illumina Index Transfer Files
**Location:** `2_library_creation/Illumina_index_transfer_files/`
**Format:** CSV files for Hamilton liquid handler
**Content:**
- `Illumina_index_set` - PE17, PE18, PE19, PE20
- `Illumina_source_well` - 96-well index plate position
- `Lib_plate_name` - Original plate name
- `Lib_plate_ID` - Hamilton barcode (h{barcode})
- `Lib_plate_well` - 384-well source position
- `Primer_volume_(uL)` - Fixed at 2µL

### 2. FA Transfer Files
**Location:** `2_library_creation/FA_transfer_files/`
**Format:** CSV files for Fragment Analyzer sample preparation
**Content:**
- `Library_Plate_Barcode` - Hamilton format (h{barcode})
- `Dilution_Plate_Barcode` - Dilution format ({barcode}D)
- `FA_Plate_Barcode` - FA format ({barcode}F)
- `Library_Well` - Source well position
- `FA_Well` - Destination 96-well position
- Volume and buffer specifications

### 3. FA Input Files
**Location:** `2_library_creation/FA_input_files/`
**Format:** CSV files without headers for FA instrument
**Content:**
- Sequential number (1-96)
- FA well position
- Sample identifier or control name
- Special wells: `library_control_A1`, `library_control_H1`, `library_control_A12`, `ladder`

### 4. Master Library DataFrame
**Filename:** `library_dataframe.csv`
**Location:** Working directory
**Content:** Comprehensive well-level data with index and FA assignments

### 5. Updated Database
**Filename:** `project_summary.db`
**New Table:** `master_plate_data` - Complete well-level tracking data

## Index Assignment System

### 384-Well to 96-Well Mapping
The script maps 384-well plates to four 96-well index sets:

- **PE17:** Odd rows (A,C,E,G,I,K,M,O) + Odd columns (1,3,5,7,9,11,13,15,17,19,21,23)
- **PE18:** Even rows (B,D,F,H,J,L,N,P) + Odd columns (1,3,5,7,9,11,13,15,17,19,21,23)
- **PE19:** Odd rows (A,C,E,G,I,K,M,O) + Even columns (2,4,6,8,10,12,14,16,18,20,22,24)
- **PE20:** Even rows (B,D,F,H,J,L,N,P) + Even columns (2,4,6,8,10,12,14,16,18,20,22,24)

### Index Naming Convention
- Format: `{SET}_{ROW}{COL}` with zero-padded columns
- Examples: `PE17_A01`, `PE18_B12`, `PE19_C10`
- Unused and ladder wells excluded from index assignments

## FA Well Selection Logic

### Selection Strategy
- **Column-wise selection** prioritizing sample and control wells
- **96-well FA plate format** with systematic well assignment
- **Ladder wells** automatically assigned to H12 position
- **Smart column filtering** excludes unused-only columns

### Selection Algorithm
1. Identify valid columns (containing samples/controls)
2. Select first 48 wells + last 48 wells from valid columns
3. Add excluded ladder wells to H12
4. Fill remaining positions with "empty" for 96-well format

## Run Type Detection

### First Run
- **Detection:** No `master_plate_data` table in database
- **Behavior:** Creates new master DataFrame and database table
- **Output:** `🔬 FIRST RUN DETECTED`

### Subsequent Run
- **Detection:** Existing `master_plate_data` table found
- **Behavior:** Appends new data to existing master DataFrame
- **Validation:** Prevents reprocessing of existing plates
- **Output:** `🔄 SUBSEQUENT RUN DETECTED`

## Plate Processing Workflow

### 1. Plate Validation
- Validates all plates exist in database
- Checks for duplicate processing (subsequent runs)
- Separates custom and standard plates

### 2. Layout Processing
- **Custom plates:** Requires individual CSV files
- **Standard plates:** Uses individual files or standard template
- Validates all required columns and data integrity

### 3. Index Assignment
- Maps all wells to appropriate index sets
- Generates index names with proper formatting
- Excludes unused/ladder wells from indexing

### 4. FA Well Selection
- Selects 96 wells per plate for Fragment Analyzer
- Assigns FA well positions systematically
- Handles ladder wells and controls appropriately

### 5. File Generation
- Creates Illumina index transfer files
- Generates FA transfer and input files
- Updates master database with new table

### 6. File Management
- Archives existing database and CSV files
- Moves processed input files with timestamps
- Maintains organized folder structure

## Error Handling

- **FATAL ERROR** prefix for all critical errors
- Comprehensive input file validation
- Database integrity checks
- Duplicate plate prevention
- Laboratory-grade safety messaging
- Graceful exit with `sys.exit()` on errors

## Safety Features

- **Automatic file archiving** before updates
- **Input file validation** (headers, data types, plate IDs)
- **Duplicate prevention** for data integrity
- **Organized file management** prevents data loss
- **Timestamped file movement** prevents overwrites
- **Database backup** before modifications

## File Management Features

### Timestamped File Movement
- All processed input files moved with unique timestamps
- Format: `filename_YYYY_MM_DD-TimeHH-MM-SS.ext`
- Prevents overwrites on subsequent runs
- Maintains complete processing history

### Archive System
- Previous database versions archived with timestamps
- Master CSV files archived before updates
- Stored in `archived_files/` folder
- Ensures data preservation and rollback capability

### Organized Structure
- Input files moved to `previously_processed_files/`
- Separate folders for plate layouts and sort lists
- Output files organized by function (Illumina, FA, etc.)
- Clear separation of processed and active files