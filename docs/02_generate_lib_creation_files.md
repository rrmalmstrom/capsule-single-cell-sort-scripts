# Script 2: generate_lib_creation_files.py

## Overview
This is the **second script** in the laboratory workflow that processes sorted microwell plates to generate comprehensive library creation files. It handles index assignments, Fragment Analyzer (FA) transfer protocols, and master data tracking following laboratory automation standards.

## Primary Functions

### Library Processing Pipeline
- **Plate validation**: Ensures all plates exist in database and have proper metadata
- **Layout detection**: Automatically identifies upper left registration vs full plate layouts
- **Index assignment**: Maps 384-well plates to 96-well index sets (PE17, PE18, PE19, PE20)
- **FA well selection**: Chooses optimal wells for Fragment Analyzer quality control
- **File generation**: Creates transfer protocols and upload manifests

### Index Assignment System
- **Full plates**: 384-well plates mapped to four 96-well index sets using odd/even row/column patterns
- **Upper left registration**: Random cyclic assignment of single index set per plate
- **Collision avoidance**: Systematic coverage ensures no index conflicts
- **Zero-padded format**: Index names like `PE17_A01`, `PE18_B12` for consistency

## Input Requirements

### Database Dependencies
- **`project_summary.db`**: Must contain all three tables from Script 1
  - `sample_metadata`: Project information
  - `individual_plates`: Plate inventory with barcodes
  - `master_plate_data`: Will be created/updated by this script

### Input Files (2_library_creation/ folder)
- **`library_sort_plates.txt`**: List of plates to process (one per line)
- **Individual plate layouts** (optional): `{plate_name}.csv` files for custom plates
- **`standard_sort_layout.csv`**: Template for standard plates without individual layouts

### Required CSV Columns for Plate Layouts
```
Plate_ID, Well_Row, Well_Col, Well, Sample, Type,
number_of_cells/capsules, Group_1, Group_2, Group_3
```

## Output Files

### Illumina Index Transfer Files
- **Location**: `2_library_creation/Illumina_index_transfer_files/`
- **Purpose**: Index primer transfer protocols for library preparation
- **Format**: CSV with columns:
  - `Illumina_index_set`: PE17/PE18/PE19/PE20
  - `Illumina_source_well`: 96-well position (A1-H12)
  - `Lib_plate_name`: Destination plate name
  - `Lib_plate_ID`: Hamilton-compatible barcode (`h{barcode}`)
  - `Lib_plate_well`: 384-well position
  - `Primer_volume_(uL)`: Fixed at 2µL

### FA Transfer Files
- **Location**: `2_library_creation/FA_transfer_files/`
- **Purpose**: Fragment Analyzer sample transfer protocols
- **Format**: CSV with transfer volumes and plate mappings
- **Columns**:
  - `Library_Plate_Barcode`: Source plate (`h{barcode}`)
  - `Dilution_Plate_Barcode`: Intermediate plate (`{barcode}D`)
  - `FA_Plate_Barcode`: FA destination (`{barcode}F`)
  - `Library_Well`: Source well position
  - `FA_Well`: Destination well position
  - Volume and buffer specifications

### FA Upload Files
- **Location**: `2_library_creation/FA_upload_files/`
- **Purpose**: Fragment Analyzer instrument upload manifests
- **Format**: CSV without headers, 96 wells per file
- **Content**: Well number, FA well position, sample identifier
- **Special wells**: E12/F12/G12 (LibStd), H12 (ladder)

### Master Database Table
- **`master_plate_data`**: Comprehensive well-level tracking
- **Columns include**:
  - Plate and well identifiers
  - Sample metadata and groupings
  - Index assignments (Set, Well, Name)
  - FA well assignments
  - Plate barcodes and timestamps

## Key Features

### Run Type Detection
- **First run**: Creates new master_plate_data table
- **Subsequent runs**: Appends new plates to existing data, prevents duplicates

### Layout Detection Algorithm
```python
def detect_upper_left_registration(plate_df):
    # Upper left if:
    # - All even rows (B,D,F,H,J,L,N,P) contain only 'unused' wells
    # - All even columns (2,4,6,8,10,12,14,16,18,20,22,24) contain only 'unused' wells
    # This creates 96-well pattern using odd rows/columns only
```

### Index Assignment Patterns
- **PE17**: Odd rows + Odd columns (A1, A3, C1, C3, ...)
- **PE18**: Even rows + Odd columns (B1, B3, D1, D3, ...)
- **PE19**: Odd rows + Even columns (A2, A4, C2, C4, ...)
- **PE20**: Even rows + Even columns (B2, B4, D2, D4, ...)

### FA Well Selection Logic

#### Upper Left Registration
- **Direct 1:1 mapping**: Source well position preserved in FA plate
- **Compressed layout**: 96 active wells mapped to standard 96-well FA plate
- **Pattern**: A1→A1, C1→B1, E1→C1, etc.

#### Full Plate
- **Column-wise selection**: Prioritizes sample and control wells
- **92-position layout**: Columns 1-11 (all rows) + Column 12 (rows A-D)
- **Smart filtering**: Excludes unused-only columns
- **Selection rules**:
  - If ≤92 wells: select all
  - If >92 wells: select first 48 + last 44
  - Last well must be positive control

## Technical Implementation

### Database Architecture
```sql
-- Enhanced individual_plates table
ALTER TABLE individual_plates ADD COLUMN upper_left_registration BOOLEAN;

-- New master_plate_data table
CREATE TABLE master_plate_data (
    Plate_ID TEXT,
    Well TEXT,
    Sample TEXT,
    Type TEXT,
    Index_Set TEXT,
    Index_Well TEXT,
    Index_Name TEXT,
    Plate_Barcode TEXT,
    FA_Well TEXT,
    -- ... additional columns
);
```

### File Organization Strategy
- **Input archiving**: Processed files moved to `previously_processed_files/` with timestamps
- **Template preservation**: `standard_sort_layout.csv` remains in place
- **Batch tracking**: Timestamped subdirectories for organized processing

## Error Handling
- **Plate validation**: Ensures all plates exist in database before processing
- **Duplicate prevention**: Blocks reprocessing of existing plates
- **Layout validation**: Verifies CSV format and required columns
- **Index uniqueness**: Validates no index assignment conflicts

## Integration Points
- **Input from Script 1**: Reads database and plate inventory from [`initiate_project_folder_and_make_sort_plate_labels.py`](01_initiate_project_folder_and_make_sort_plate_labels.md)
- **Output to Script 3**: Master database feeds into [`capsule_fa_analysis.py`](03_capsule_fa_analysis.md)
- **Thresholds file**: Generates `3_FA_analysis/thresholds.txt` for FA analysis

## Usage Examples

### Basic Usage
```bash
python generate_lib_creation_files.py
```

### Input File Format (library_sort_plates.txt)
```
BP9735_SitukAM.1
BP9735_SitukAM.2
BP4444_RexRM.1
Custom_Plate_Name.1
```

### Standard Template Application
- Plates without individual CSV files automatically use `standard_sort_layout.csv`
- Template fields populated with actual plate and sample names
- Maintains consistent well layout across standard plates

## Performance Features
- **Smart database updates**: Only modifies tables that actually change
- **Incremental processing**: Supports adding plates to existing projects
- **Memory efficient**: Processes plates individually to handle large datasets
- **Parallel file generation**: Creates multiple output files simultaneously

This script transforms the basic plate inventory from Script 1 into a comprehensive library preparation dataset, establishing the index assignments and FA protocols needed for quality control in Script 3.