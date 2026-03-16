# Script 5: make_ESP_smear_analysis_file.py

## Overview
This is the **fifth script** in the laboratory workflow that generates ESP (External Sample Processing) smear analysis files for upload to external systems. It processes grid table files containing pooling information and merges them with database records to create standardized smear analysis files for each destination plate.

## Primary Functions

### Grid Table Processing
- **Multi-file support**: Discovers and processes all valid grid table CSV files
- **Data validation**: Ensures grid tables contain expected samples from pooling selection
- **Duplicate detection**: Prevents processing of samples appearing in multiple grid files
- **Completeness verification**: Validates perfect match between expected and actual samples

### ESP File Generation
- **Standardized format**: Creates 13-column ESP-compatible smear analysis files
- **Per-plate output**: Generates separate files for each Library Plate Container Barcode
- **Fixed parameters**: Applies laboratory-standard values for ESP submission
- **Quality mapping**: Translates FA results into ESP format requirements

### Database Integration
- **Library container mapping**: Establishes plate barcode to container barcode relationships
- **Status tracking**: Updates individual_plates table with ESP generation status
- **Master data enhancement**: Adds grid table information to master_plate_data
- **Batch management**: Organizes processing runs with timestamps

## Input Requirements

### Database Dependencies
- **Complete database structure** from Script 4:
  - `sample_metadata`: Project information
  - `individual_plates`: Plates with `selected_for_pooling = 1`
  - `master_plate_data`: Wells with `selected_for_pooling = 1`

### Grid Table Files
- **Location**: `4_plate_selection_and_pooling/` directory
- **Format**: CSV files with required columns
- **Auto-discovery**: Script finds all valid grid table files automatically

### Required Grid Table Columns
```csv
Well,Library Plate Label,Illumina Library,Library Plate Container Barcode,Nucleic Acid ID
```

### Expected Sample Identification
- **Selection criteria**: Samples where both plate and well are marked `selected_for_pooling = True`
- **Validation logic**: Grid tables must contain exactly these samples (no more, no less)

## Output Files

### ESP Smear Analysis Files
- **Location**: `4_plate_selection_and_pooling/B_smear_file_for_ESP_upload/`
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
    'Well': 'Well',                           # From grid table
    'Sample ID': 'Illumina Library',          # From grid table  
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

## Key Features

### Grid Table Validation Pipeline
```python
def validate_grid_table_completeness(expected_samples, combined_grid_df):
    # Create comparison sets using (Plate_Barcode, Well) tuples
    expected_set = set(zip(expected_samples['Plate_Barcode'], expected_samples['Well']))
    grid_set = set(zip(combined_grid_df['Library Plate Label'], combined_grid_df['Well']))
    
    # Ensure perfect match - no missing, no extra samples
    missing_from_grid = expected_set - grid_set
    unexpected_in_grid = grid_set - expected_set
    
    # Exit if any discrepancies found
```

### Library Container Barcode Mapping
- **Extraction**: Derives mapping from grid table data
- **Format**: `Library Plate Label` (e.g., 'XUPVQ-1') → `Library Plate Container Barcode` (e.g., '27-810254')
- **Database update**: Stores mapping in `individual_plates.library_plate_container_barcode`
- **File naming**: Uses container barcode for ESP file names

### Merge Strategy
```python
def validate_and_merge_data(master_plate_df, expected_samples, grid_df):
    # ESP merging strategy:
    # Grid table: ['Library Plate Label', 'Well'] 
    # Master data: ['Plate_Barcode', 'Well']
    
    merged_df = pd.merge(
        master_plate_df,    # All master plate data (left)
        grid_merge_df,      # Grid table data (right)  
        on=['Plate_Barcode', 'Well'],
        how='left'          # Preserve all master data
    )
```

## Technical Implementation

### Database Schema Updates
```sql
-- Add ESP tracking columns to individual_plates
ALTER TABLE individual_plates ADD COLUMN esp_generation_status TEXT DEFAULT 'pending';
ALTER TABLE individual_plates ADD COLUMN esp_generated_timestamp TEXT;
ALTER TABLE individual_plates ADD COLUMN esp_batch_id TEXT;
ALTER TABLE individual_plates ADD COLUMN library_plate_container_barcode TEXT;

-- Grid table columns added to master_plate_data
ALTER TABLE master_plate_data ADD COLUMN "Illumina Library" TEXT;
ALTER TABLE master_plate_data ADD COLUMN "Nucleic Acid ID" TEXT;
ALTER TABLE master_plate_data ADD COLUMN "Library Plate Container Barcode" TEXT;
```

### File Organization
- **Grid table archiving**: Processed files moved to `previously_processed_grid_files/`
- **Database archiving**: Timestamped database copies in `archived_files/`
- **CSV regeneration**: Fresh CSV files created from updated database

### Error Handling
- **Missing grid tables**: Clear guidance on required file location and format
- **Sample mismatches**: Detailed reporting of missing or unexpected samples
- **Incomplete merges**: Validation that all expected samples have grid data
- **File format errors**: Specific column validation with correction guidance

## Integration Points
- **Input from Script 4**: Reads selection status from [`create_capsule_spits.py`](04_create_capsule_spits.md)
- **Output to Script 6**: Container barcode mapping feeds into [`relabel_lib_plates_for_pooling.py`](06_relabel_lib_plates_for_pooling.md)
- **External dependency**: Requires grid table files from external pooling system

## Usage Examples

### Basic Usage
```bash
python make_ESP_smear_analysis_file.py
```

### Quiet Mode
```bash
python make_ESP_smear_analysis_file.py --quiet
```

### Grid Table File Example
```csv
Well,Library Plate Label,Illumina Library,Library Plate Container Barcode,Nucleic Acid ID
A1,XUPVQ-1,XUPVQ-1_A1_lib,27-810254,sample_001
A2,XUPVQ-1,XUPVQ-1_A2_lib,27-810254,sample_002
B1,XUPVQ-3,XUPVQ-3_B1_lib,27-999999,sample_003
```

### Processing Output
```
Starting ESP smear analysis file generation...
Reading ESP project database...
Identifying expected grid table samples...
Found 2 plates selected for pooling: ['XUPVQ-1', 'XUPVQ-3']
Found 48 samples expected in grid tables
Finding grid table files...
Found 2 valid grid table file(s)
Generated 2 ESP smear files successfully!
Database and CSV file updates completed successfully!
```

## Quality Control Features
- **Perfect validation**: Ensures exact match between expected and grid table samples
- **Duplicate prevention**: Blocks processing if samples appear in multiple grid files
- **Data integrity**: Validates all expected samples receive grid table data
- **Batch tracking**: Maintains processing history with timestamps

## Performance Features
- **Multi-file processing**: Handles multiple grid tables in single run
- **Incremental updates**: Only processes new data, preserves existing records
- **Memory efficiency**: Processes data in chunks to handle large datasets
- **Parallel file generation**: Creates multiple ESP files simultaneously

## External System Integration
- **ESP compatibility**: Generates files in exact format required by ESP system
- **Container barcode tracking**: Establishes traceability between internal and external identifiers
- **Quality standardization**: Applies consistent QC parameters across all samples
- **Batch submission**: Organizes files for efficient upload to external systems

This script serves as the critical interface between the internal laboratory workflow and external processing systems, ensuring data integrity and format compliance for downstream analysis.