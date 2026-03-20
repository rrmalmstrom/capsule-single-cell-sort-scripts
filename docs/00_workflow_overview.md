# Laboratory Capsule Sorting Workflow - Complete Overview

## Executive Summary

This laboratory workflow consists of **six Python scripts** that execute in sequence to process microwell plates from initial project setup through final pooling preparation. The workflow transforms sample metadata into a complete laboratory processing pipeline with quality control, selection logic, external system integration, barcode scanning verification, and ESP file generation.

> **Workflow Update (March 2026)**: Scripts 5 and 6 have been refactored. The older scripts `make_ESP_smear_analysis_file.py` and `relabel_lib_plates_for_pooling.py` are **no longer used** and have been replaced by `process_grid_tables_and_generate_barcodes.py` and `verify_scanning_and_generate_ESP_files.py`. The key change is that barcode scanning verification now occurs **before** ESP file generation, adding a mandatory quality gate.

## Workflow Architecture

### Database-Driven Design
- **Central database**: `project_summary.db` (SQLite) serves as the single source of truth
- **Three-table architecture**: 
  - `sample_metadata`: Project and collection information
  - `individual_plates`: Plate inventory with barcodes and status tracking
  - `master_plate_data`: Comprehensive well-level data with index assignments and quality results
- **Incremental updates**: Each script enhances the database with additional information
- **Audit trail**: Timestamped archiving preserves processing history

### File Organization Strategy
- **Structured directories**: Automatic creation of organized folder hierarchy
- **Timestamped archiving**: All processed files preserved with timestamps
- **Input/output separation**: Clear distinction between input files and generated outputs
- **External integration**: Dedicated folders for each processing stage

## Script Execution Sequence

### 1. Project Initialization
**Script**: [`initiate_project_folder_and_make_sort_plate_labels.py`](01_initiate_project_folder_and_make_sort_plate_labels.md)

**Purpose**: Foundation setup and barcode generation
- Creates complete directory structure for workflow
- Generates unique sequential barcodes for all plates
- Establishes database architecture with sample metadata
- Produces BarTender label files for physical plate labeling

**Key Outputs**:
- `project_summary.db` with `sample_metadata` and `individual_plates` tables
- Organized folder structure (`1_make_barcode_labels/`, `2_library_creation/`, etc.)
- BarTender label files for Echo and Hamilton instruments

### 2. Library Preparation
**Script**: [`generate_lib_creation_files.py`](02_generate_lib_creation_files.md)

**Purpose**: Index assignment and FA protocol generation
- Maps 384-well plates to 96-well index sets (PE17, PE18, PE19, PE20)
- Detects plate layout types (upper left registration vs full plate)
- Generates Fragment Analyzer transfer protocols
- Creates comprehensive master plate data table

**Key Outputs**:
- `master_plate_data` table with index assignments and FA well mappings
- Illumina index transfer files for library preparation
- FA transfer and upload files for quality control
- Thresholds file for FA analysis

### 3. Quality Analysis
**Script**: [`capsule_fa_analysis.py`](03_capsule_fa_analysis.md)

**Purpose**: Fragment Analyzer data processing and quality assessment
- Processes FA instrument output files with automated discovery
- Calculates index set failure rates using 50% threshold logic
- Determines whole plate rework requirements
- Generates quality visualizations and statistics

**Key Outputs**:
- Updated `master_plate_data` with FA results and quality decisions
- FA summary statistics and plate visualization PDFs
- Processing status tracking in `individual_plates` table

### 4. Plate Selection
**Script**: [`create_capsule_spits.py`](04_create_capsule_spits.md)

**Purpose**: Well selection and SPITS file generation
- Processes user-defined plate selection criteria
- Applies layout-specific well selection logic
- Generates JGI-compatible SPITS submission files
- Updates database with selection status

**Key Outputs**:
- SPITS CSV file with selected wells and complete metadata
- Selection status flags in database tables
- Archived plate selection input file

### 5. Grid Processing + Barcode Generation *(Refactored)*
**Script**: [`process_grid_tables_and_generate_barcodes.py`](05_process_grid_tables_and_generate_barcodes.md)

**Purpose**: Grid table processing, container barcode mapping, and barcode scanning material generation
- Validates grid table completeness against selected samples
- Extracts Library Plate Container Barcode mapping from grid tables
- Updates database with container barcodes (`library_plate_container_barcode`)
- Merges grid table data into `master_plate_data`
- Generates Excel barcode scanning template (Column C populated with expected barcodes)
- Generates BarTender file for container label printing

**Key Outputs**:
- Updated `individual_plates` with `library_plate_container_barcode`
- Updated `master_plate_data` with grid table columns
- Excel scanning template: `B_new_plate_barcode_labels/{proposal}_pool_label_scan_verificiation_tool.xlsx`
- BarTender file: `B_new_plate_barcode_labels/BARTENDER_{proposal}_container_labels.txt`
- Archived grid files in `previously_processed_grid_files/`

**→ Manual Step**: User opens Excel template, scans physical barcodes into Column E, verifies all Checker values show TRUE

### 6. Barcode Verification + ESP File Generation *(Refactored)*
**Script**: [`verify_scanning_and_generate_ESP_files.py`](06_verify_scanning_and_generate_ESP_files.md)

**Purpose**: Mandatory barcode scanning verification followed by ESP smear file generation
- Locates completed Excel scanning file from Script 5 output
- **Validates Checker column**: Any FALSE value causes immediate `sys.exit()` — no ESP files generated
- Generates ESP-compatible smear analysis files for external upload
- Updates `individual_plates` with ESP generation status columns
- Refreshes `individual_plates.csv` with all new columns

**Key Outputs**:
- ESP smear files: `C_smear_file_for_ESP_upload/ESP_smear_file_for_upload_{container_barcode}.csv`
- Updated `individual_plates` with `esp_generation_status`, `esp_generated_timestamp`, `esp_batch_id`
- Refreshed `individual_plates.csv`

## Data Flow Architecture

### Input → Processing → Output Chain

```
Sample Metadata CSV
        ↓
[Script 1] → Database + Barcodes + Folder Structure
        ↓
Library Sort Plates List + Plate Layouts
        ↓  
[Script 2] → Index Assignments + FA Protocols + Master Data
        ↓
FA Instrument Output + Thresholds
        ↓
[Script 3] → Quality Results + Failure Analysis + Visualizations
        ↓
Plate Selection CSV (User Input)
        ↓
[Script 4] → SPITS Files + Selection Status
        ↓
Grid Table Files (External Input)
        ↓
[Script 5] → Container Barcode Mapping + Excel Scanning Template + BarTender File
        ↓
Manual Step: User scans physical barcodes into Excel template
        ↓
[Script 6] → Barcode Verification → ESP Smear Files + ESP Status Updates
```

### Database Evolution

| Script | Tables Modified | Key Additions |
|--------|----------------|---------------|
| 1 | `sample_metadata`, `individual_plates` | Basic project structure, plate barcodes |
| 2 | `master_plate_data` | Index assignments, FA well mappings |
| 3 | `master_plate_data`, `individual_plates` | FA results, quality decisions, processing status |
| 4 | `master_plate_data`, `individual_plates` | Selection flags, pooling status |
| 5 | `master_plate_data`, `individual_plates` | Grid table data, `library_plate_container_barcode` |
| 6 | `individual_plates` | `esp_generation_status`, `esp_generated_timestamp`, `esp_batch_id` |

### Directory Structure After Complete Workflow

```
project_directory/
├── project_summary.db
├── individual_plates.csv          (refreshed by Scripts 5 and 6)
├── master_plate_data.csv          (refreshed by Script 5)
├── sample_metadata.csv
├── 1_make_barcode_labels/
│   └── bartender_barcode_labels/
├── 2_library_creation/
│   ├── FA_transfer_files/
│   ├── FA_upload_files/
│   └── Illumina_index_transfer_files/
├── 3_FA_analysis/
├── 4_plate_selection_and_pooling/
│   ├── {proposal}_capsule_sort_SPITS.csv
│   ├── plate_selection.csv
│   ├── B_new_plate_barcode_labels/          ← Script 5 output
│   │   ├── {proposal}_pool_label_scan_verificiation_tool.xlsx
│   │   └── BARTENDER_{proposal}_container_labels.txt
│   ├── C_smear_file_for_ESP_upload/         ← Script 6 output
│   │   └── ESP_smear_file_for_upload_{barcode}.csv
│   └── previously_processed_grid_files/
└── archived_files/
```

## Key Technical Features

### Barcode System
- **Sequential generation**: Collision-free 5-character base + incremental numbering
- **Instrument variants**: Echo (`e{barcode}`) and Hamilton (`h{barcode}`) prefixes
- **External mapping**: Internal barcodes linked to library container barcodes via grid tables

### Barcode Scanning Verification (New in Refactored Workflow)
- **Excel template**: Checker column (Column D) contains formulas comparing expected vs. scanned barcodes
- **Acceptable values**: `True` (match) or `"empty"` (unused slot)
- **Fatal condition**: Any `False` value causes Script 6 to `sys.exit()` immediately
- **Safety guarantee**: ESP files are never generated with mismatched barcodes

### Index Assignment Strategy
- **Full plates**: 384-well → four 96-well index sets using odd/even patterns
- **Upper left registration**: Single index set assigned to 96 active wells
- **Collision avoidance**: Systematic coverage prevents index conflicts

### Quality Control Logic
- **Index set failure**: >50% failure rate triggers index set rework
- **Whole plate failure**: >50% overall failure rate triggers complete plate rework
- **Layout-aware selection**: Different well selection logic for different plate types

### File Management
- **Timestamped archiving**: All processed files preserved with timestamps
- **Organized structure**: Dedicated folders for each processing stage
- **Template preservation**: Standard templates remain unchanged
- **Batch tracking**: Processing runs organized by timestamp

## Integration Points

### External Systems
- **BarTender**: Label printing system integration (Scripts 1 and 5)
- **Fragment Analyzer**: Quality control instrument data processing (Script 3)
- **ESP**: External sample processing system file exchange (Script 6)
- **JGI SPITS**: Sample submission system compatibility (Script 4)

### Laboratory Instruments
- **Echo**: Acoustic liquid handling (barcode prefix `e`)
- **Hamilton**: Robotic liquid handling (barcode prefix `h`)
- **Fragment Analyzer**: DNA quality assessment instrument

### Manual Processes
- **Plate selection**: User-driven decision based on FA results (between Scripts 3 and 4)
- **Grid table creation**: External pooling system output (input to Script 5)
- **Barcode scanning**: Physical barcode verification using Excel template (between Scripts 5 and 6)

## Error Handling Strategy

### Laboratory-Grade Safety
- **"FATAL ERROR" messaging**: Clear error identification for laboratory safety
- **Fail-fast design**: Immediate `sys.exit()` on critical errors — no partial state corruption
- **Comprehensive validation**: Input validation at every processing stage
- **Data integrity checks**: Prevents processing with incomplete or corrupted data
- **Barcode mismatch protection**: Script 6 refuses to generate ESP files if any barcode scan failed

### Recovery Mechanisms
- **Incremental processing**: Scripts can be re-run safely
- **Archive preservation**: Previous processing states always available
- **Status tracking**: Database maintains processing state for recovery
- **Workflow manager integration**: `.workflow_status/` success markers for automation

## Deprecated Scripts

The following scripts are **no longer part of the active workflow** and have been replaced:

| Deprecated Script | Replaced By | Reason |
|------------------|-------------|--------|
| `make_ESP_smear_analysis_file.py` | `process_grid_tables_and_generate_barcodes.py` (grid processing) + `verify_scanning_and_generate_ESP_files.py` (ESP generation) | Split to insert mandatory barcode scanning verification step |
| `relabel_lib_plates_for_pooling.py` | `process_grid_tables_and_generate_barcodes.py` | Barcode label generation now happens before scanning, not after ESP files |

Both deprecated scripts are retained in the repository for reference but should not be run as part of the standard workflow.

## Usage Patterns

### Typical Project Workflow
1. **Project setup**: Run Script 1 with sample metadata CSV
2. **Library preparation**: Run Script 2 with plate list and layouts
3. **Quality analysis**: Run Script 3 after FA instrument processing
4. **Selection decision**: Create plate selection CSV based on FA results
5. **SPITS generation**: Run Script 4 to create submission files
6. **External processing**: Obtain grid tables from external pooling system
7. **Grid processing**: Run Script 5 to process grids and generate barcode scanning materials
8. **Barcode scanning**: Manually scan physical barcodes into Excel template
9. **Verification + ESP**: Run Script 6 to verify scanning and generate ESP files

### Re-run Scenarios
- **Additional plates**: Scripts 1-2 can add plates to existing projects
- **New FA results**: Script 3 processes only new FA files
- **Selection changes**: Scripts 4-6 can be re-run with different selections
- **Barcode scan correction**: Fix Excel template and re-run Script 6 (no database changes needed)

### Error Recovery
- **Database corruption**: Restore from timestamped archive in `archived_files/`
- **Partial processing**: Resume from last successful step
- **Failed barcode scan**: Correct Excel template and re-run Script 6

This comprehensive workflow provides a robust, scalable, and maintainable solution for laboratory capsule sorting operations, with built-in quality control, mandatory barcode verification, error handling, and integration capabilities for complex laboratory environments.
