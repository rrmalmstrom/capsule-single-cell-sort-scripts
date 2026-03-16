# Laboratory Capsule Sorting Workflow - Complete Overview

## Executive Summary

This laboratory workflow consists of **six Python scripts** that execute in sequence to process microwell plates from initial project setup through final pooling preparation. The workflow transforms sample metadata into a complete laboratory processing pipeline with quality control, selection logic, external system integration, and physical tracking materials.

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
- **External integration**: Dedicated folders for external system file exchange

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

### 5. External System Integration
**Script**: [`make_ESP_smear_analysis_file.py`](05_make_ESP_smear_analysis_file.md)

**Purpose**: ESP file generation and grid table processing
- Validates grid table completeness against selected samples
- Creates ESP-compatible smear analysis files
- Establishes library container barcode mapping
- Updates database with external system identifiers

**Key Outputs**:
- ESP smear analysis files for external upload
- Library container barcode mapping in database
- Archived grid table files

### 6. Physical Labeling
**Script**: [`relabel_lib_plates_for_pooling.py`](06_relabel_lib_plates_for_pooling.md)

**Purpose**: Physical labeling materials for pooling completion
- Creates populated barcode scan verification templates
- Generates BarTender files for container label printing
- Provides materials for manual pooling operations

**Key Outputs**:
- Excel barcode verification template
- BarTender container label files
- Physical workflow support materials

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
[Script 5] → ESP Files + Container Mapping
        ↓
[Script 6] → Physical Labeling Materials
```

### Database Evolution

| Script | Tables Modified | Key Additions |
|--------|----------------|---------------|
| 1 | `sample_metadata`, `individual_plates` | Basic project structure, plate barcodes |
| 2 | `master_plate_data` | Index assignments, FA well mappings |
| 3 | `master_plate_data`, `individual_plates` | FA results, quality decisions, processing status |
| 4 | `master_plate_data`, `individual_plates` | Selection flags, pooling status |
| 5 | `master_plate_data`, `individual_plates` | Grid table data, container barcodes |
| 6 | None | Read-only access for label generation |

## Key Technical Features

### Barcode System
- **Sequential generation**: Collision-free 5-character base + incremental numbering
- **Instrument variants**: Echo (`e{barcode}`) and Hamilton (`h{barcode}`) prefixes
- **External mapping**: Internal barcodes linked to library container barcodes

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
- **BarTender**: Label printing system integration
- **Fragment Analyzer**: Quality control instrument data processing
- **ESP**: External sample processing system file exchange
- **JGI SPITS**: Sample submission system compatibility

### Laboratory Instruments
- **Echo**: Acoustic liquid handling (barcode prefix `e`)
- **Hamilton**: Robotic liquid handling (barcode prefix `h`)
- **Fragment Analyzer**: DNA quality assessment instrument

### Manual Processes
- **Plate selection**: User-driven decision based on FA results
- **Grid table creation**: External pooling system output
- **Physical labeling**: Barcode verification and container labeling

## Error Handling Strategy

### Laboratory-Grade Safety
- **"FATAL ERROR" messaging**: Clear error identification for laboratory safety
- **Fail-fast design**: Immediate termination on critical errors
- **Comprehensive validation**: Input validation at every processing stage
- **Data integrity checks**: Prevents processing with incomplete or corrupted data

### Recovery Mechanisms
- **Incremental processing**: Scripts can be re-run safely
- **Skip logic**: Avoids reprocessing completed items
- **Archive preservation**: Previous processing states always available
- **Status tracking**: Database maintains processing state for recovery

## Performance Characteristics

### Scalability
- **Plate capacity**: Handles projects with hundreds of plates
- **Memory efficiency**: Processes data in chunks to manage large datasets
- **Parallel processing**: Multiple output files generated simultaneously
- **Incremental updates**: Only processes new data, preserves existing records

### Reliability
- **Database transactions**: Atomic updates prevent partial state corruption
- **File locking**: Prevents concurrent access issues
- **Validation pipelines**: Multi-stage validation ensures data quality
- **Rollback capability**: Archive system enables recovery from errors

## Quality Assurance Features

### Data Validation
- **Schema enforcement**: Required columns and data types validated
- **Completeness checks**: Ensures all expected data is present
- **Consistency validation**: Cross-references between tables verified
- **Format compliance**: External system file formats strictly enforced

### Audit Trail
- **Processing timestamps**: Every operation timestamped
- **Batch identification**: Processing runs uniquely identified
- **Status tracking**: Processing state maintained in database
- **Archive preservation**: Complete processing history maintained

## Usage Patterns

### Typical Project Workflow
1. **Project setup**: Run Script 1 with sample metadata CSV
2. **Library preparation**: Run Script 2 with plate list and layouts
3. **Quality analysis**: Run Script 3 after FA instrument processing
4. **Selection decision**: Create plate selection CSV based on FA results
5. **SPITS generation**: Run Script 4 to create submission files
6. **External processing**: Obtain grid tables from external system
7. **ESP file creation**: Run Script 5 to generate ESP files
8. **Physical preparation**: Run Script 6 to create labeling materials

### Re-run Scenarios
- **Additional plates**: Scripts 1-2 can add plates to existing projects
- **New FA results**: Script 3 processes only new FA files
- **Selection changes**: Scripts 4-6 can be re-run with different selections

### Error Recovery
- **Database corruption**: Restore from timestamped archive
- **Partial processing**: Resume from last successful step
- **File corruption**: Regenerate from database state

This comprehensive workflow provides a robust, scalable, and maintainable solution for laboratory capsule sorting operations, with built-in quality control, error handling, and integration capabilities for complex laboratory environments.