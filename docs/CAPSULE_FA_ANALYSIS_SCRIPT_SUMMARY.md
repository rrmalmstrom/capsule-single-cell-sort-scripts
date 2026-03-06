# Laboratory Fragment Analyzer (FA) Quality Analysis Script Summary

## Overview
The `capsule_fa_analysis.py` script processes Fragment Analyzer output files to analyze DNA library quality with automated index set failure detection and comprehensive database integration following laboratory automation standards.

## Script Execution
```bash
python capsule_fa_analysis.py
```

**Requirements:**
- Must use `sip-lims` conda environment
- Run from the working directory containing input files
- Requires existing `project_summary.db` database with completed library creation
- Requires FA instrument output files in organized subdirectories

## Input Files Required

### 1. Quality Thresholds File (Required)
**Filename:** `thresholds.txt`
**Location:** `3_FA_analysis/` folder
**Format:** Plain text file with DNA concentration and size thresholds per destination plate

**Example:**
```
Plate_ID,Concentration_Threshold_nmol/L,Size_Threshold_bp
BP9735_SitukAM.1,0.5,200
BP9735_SitukAM.2,0.5,200
Rex_badass_custom.1,0.3,150
```

### 2. FA Instrument Output Files (Required)
**Location:** `3_FA_analysis/{date}/{plate_barcode}/`
**Format:** Subdirectories containing FA instrument CSV files
**Filename Pattern:** `*Smear Analysis Result.csv`

**Directory Structure Example:**
```
3_FA_analysis/
├── thresholds.txt
├── 2023 07 21/
│   ├── XUPVQ-1F 17-38-59/
│   │   └── BP9735_SitukAM.1_XUPVQ-1 Smear Analysis Result.csv
│   └── XUPVQ-3F 16-09-05/
│       └── BP4444_RexRM.1_XUPVQ-3 Smear Analysis Result.csv
└── 2024 07 22/
    └── XUPVQ-6F 16-09-05/
        └── BP9735_FULL.1_XUPVQ-6 Smear Analysis Result.csv
```

### 3. Database Dependencies
**Filename:** `project_summary.db`
**Location:** Working directory
**Required Tables:**
- `sample_metadata` - Project and sample information
- `individual_plates` - Plate data with FA tracking columns
- `master_plate_data` - Well-level data with index assignments

## Output Structure

The script creates organized output and archives:

```
3_FA_analysis/
├── fa_summary_statistics_{timestamp}.csv
├── FA_plate_visualizations_combined_{timestamp}.pdf
├── previously_processed_threshold_files/
│   └── thresholds_{timestamp}.txt
├── {plate_name}.csv (copied from subdirectories)
└── archived_files/
    └── capsule_fa_analysis_results/
        └── batch_{timestamp}/
            └── {date}/
                └── {plate_barcode}/
                    └── *Smear Analysis Result.csv
```

## Generated Files

### 1. FA Summary Statistics
**Location:** `3_FA_analysis/`
**Filename:** `fa_summary_statistics_{timestamp}.csv`
**Content:**
- Comprehensive quality analysis results per plate
- Index set failure rates and statistics
- Pass/fail determinations based on thresholds
- Whole plate rework recommendations

### 2. FA Plate Visualizations
**Location:** `3_FA_analysis/`
**Filename:** `FA_plate_visualizations_combined_{timestamp}.pdf`
**Content:**
- Visual heatmaps of plate quality results
- Well-by-well pass/fail status
- Index set failure pattern visualization
- Quality metrics distribution plots

### 3. Processed FA Data Files
**Location:** `3_FA_analysis/`
**Filename:** `{plate_name}.csv` (e.g., `XUPVQ-1F.csv`)
**Content:**
- Cleaned and standardized FA instrument data
- Parsed sample identifiers and well positions
- Concentration, size, and quality measurements

## Index Set Failure Analysis

### Failure Rate Calculation
- **Sample Wells Only:** Uses only 'sample' type wells for failure rate calculation
- **50% Threshold:** Index sets with ≥50% failure rate are marked as failed
- **Extrapolation:** Failed index set results applied to all wells on the same library plate
- **Whole Plate Assessment:** Overall 50% failure rate determines plate rework necessity

### Index Set Processing
- **PE17, PE18, PE19, PE20:** Four standard index sets analyzed independently
- **Failed_index_sets Column:** Contains Python lists of failed index sets (e.g., ['PE17', 'PE19'])
- **Library Plate Mapping:** Results extrapolated from FA plates to original library plates

## Quality Threshold System

### Per-Plate Thresholds
- **DNA Concentration:** nmol/L thresholds per destination plate
- **Fragment Size:** Base pair (bp) thresholds per destination plate
- **Dilution Factor:** Automatic application for original library concentration calculation

### Pass/Fail Determination
- **Dual Criteria:** Both concentration AND size must meet thresholds
- **Passed_library Column:** Binary (0/1) pass/fail status per well
- **Quality Reporting:** Detailed failure rate statistics and recommendations

## Database Integration

### FA Tracking Columns (Individual Plates)
- `fa_processing_status` - Processing status ('pending', 'processed')
- `fa_processed_timestamp` - Timestamp of FA processing completion
- `fa_batch_id` - Batch identifier for processing group

### Master Plate Data Updates
- `dilution_factor` - Applied dilution factor for concentration calculation
- `ng/uL` - DNA concentration from FA instrument
- `nmol/L` - Calculated molar concentration
- `Avg. Size` - Average fragment size from FA analysis
- `Passed_library` - Binary pass/fail status (0/1)
- `Failed_index_sets` - Python list of failed index sets
- `Redo_whole_plate` - Boolean whole plate rework recommendation

## FA File Processing Workflow

### 1. File Discovery and Validation
- Scans `3_FA_analysis/` subdirectories for FA output files
- Validates folder names match sample names in CSV files
- Skips already processed plates based on database tracking
- Copies and renames files to working directory

### 2. Data Processing and Cleaning
- Reads FA instrument CSV files with standardized column mapping
- Removes empty, ladder, and library control wells
- Parses complex sample ID format: `{barcode}_{plate_id}_{well}`
- Handles missing values and data type conversions

### 3. Quality Analysis
- Applies per-plate concentration and size thresholds
- Calculates index set failure rates using sample wells only
- Determines whole plate rework recommendations
- Generates comprehensive quality statistics

### 4. Database Updates
- Archives existing database with timestamp
- Updates master_plate_data with FA results and quality assessments
- Updates individual_plates with processing status tracking
- Maintains complete audit trail of processing

### 5. File Management and Archiving
- Archives processed FA result directories with batch timestamps
- Moves threshold files to organized archive structure
- Creates timestamped summary files and visualizations
- Maintains organized folder structure for workflow management

## Duplicate Processing Prevention

### Processing Status Tracking
- Uses `fa_processing_status` column in individual_plates table
- Skips plates marked as 'processed' in subsequent runs
- Reports skipped plates for user awareness
- Supports incremental processing of new FA results

### Batch Processing
- Groups processed plates into timestamped batches
- Maintains separate archive directories per batch
- Enables rollback and reprocessing capabilities
- Supports workflow management and quality control

## Error Handling and Validation

### Input Validation
- **File Existence:** Validates all required input files and directories
- **Data Format:** Comprehensive validation of FA instrument CSV format
- **Threshold Format:** Validates threshold file format and plate matching
- **Database Schema:** Ensures required tables and columns exist

### Processing Validation
- **Plate Name Matching:** Validates folder names match sample IDs in FA files
- **Data Integrity:** Checks for missing or invalid FA measurements
- **Threshold Application:** Ensures all plates have defined quality thresholds
- **Index Set Validation:** Confirms index set assignments exist for analysis

### Safety Features
- **Database Archiving:** Automatic backup before any updates
- **Fail-Fast Processing:** Stops on first critical error to prevent data corruption
- **Comprehensive Logging:** Detailed error messages with laboratory-grade safety messaging
- **Graceful Exit:** Uses `sys.exit()` for clean termination on errors

## Integration Points

### Upstream Dependencies
- Requires completed barcode label generation (individual_plates table)
- Requires completed library creation (master_plate_data with index assignments)
- Requires FA instrument analysis completion (FA output files in subdirectories)

### Downstream Usage
- FA results enable plate selection for SPITS file generation
- Quality assessments support laboratory decision-making
- Database updates provide audit trail for regulatory compliance
- Visualization outputs support quality control and reporting workflows