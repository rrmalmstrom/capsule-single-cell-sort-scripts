# Script 3: capsule_fa_analysis.py

## Overview
This is the **third script** in the laboratory workflow that processes Fragment Analyzer (FA) output files to analyze DNA library quality with automated index set failure detection and comprehensive database integration. It implements sophisticated quality assessment algorithms with 50% failure thresholds for both individual index sets and whole plate rework decisions.

## Primary Functions

### FA Data Processing
- **Automated file discovery**: Scans subdirectories for FA instrument output files
- **Incremental processing**: Only processes new plates, skips previously analyzed ones
- **Data validation**: Ensures FA results match expected samples from database
- **Quality assessment**: Applies concentration and size thresholds per plate

### Index Set Failure Analysis
- **Per-index failure rates**: Calculates failure percentages for PE17, PE18, PE19, PE20
- **50% threshold logic**: Identifies failed index sets requiring rework
- **Extrapolation strategy**: Applies index set failures to entire library plates
- **Whole plate assessment**: Determines if complete plate rework is needed

### Database Integration
- **Status tracking**: Marks plates as processed to prevent reanalysis
- **Result storage**: Updates master_plate_data with FA results and quality decisions
- **Batch management**: Organizes processing runs with timestamps

## Input Requirements

### Database Dependencies
- **`project_summary.db`**: Must contain complete three-table structure from Script 2
  - `sample_metadata`: Project information
  - `individual_plates`: Plate inventory (updated with FA tracking columns)
  - `master_plate_data`: Well-level data with index assignments

### FA Analysis Files
- **Location**: `3_FA_analysis/` subdirectories
- **Structure**: `{date}/{plate_name}/` containing FA instrument output
- **File pattern**: `*Smear Analysis Result.csv`
- **Auto-discovery**: Script automatically finds and validates FA files

### Thresholds Configuration
- **File**: `3_FA_analysis/thresholds.txt`
- **Format**: Tab-separated with columns:
  - `Destination_plate`: Plate barcode
  - `DNA_conc_threshold_(nmol/L)`: Concentration threshold (user-defined)
  - `Size_theshold_(bp)`: Size threshold (fixed at 530)
  - `dilution_factor`: Dilution factor (fixed at 20)

### Expected FA File Columns
```
Well, Sample ID, ng/uL, nmole/L, Avg. Size
```

## Output Files

### FA Summary Statistics
- **Location**: `3_FA_analysis/`
- **Filename**: `fa_summary_statistics_{timestamp}.csv`
- **Content**: Pass/fail statistics by plate and index set
- **Columns**:
  - `Plate_Barcode`: Plate identifier
  - `Index_Set`: PE17/PE18/PE19/PE20 or 'All'
  - `Passed_Count`: Number of wells passing QC
  - `Total_Count`: Total wells analyzed
  - `Pass_Percentage`: Percentage passing (rounded)

### Plate Visualizations
- **Location**: `3_FA_analysis/`
- **Filename**: `FA_plate_visualizations_combined_{timestamp}.pdf`
- **Content**: Visual 384-well plate maps showing pass/fail results
- **Features**:
  - Color-coded well types (sample, control, unused)
  - Pass/fail patterns with hatching
  - Comprehensive legends
  - Individual plates merged into single PDF

### Updated Database Tables
- **`master_plate_data`**: Enhanced with FA results and quality decisions
- **`individual_plates`**: Updated with FA processing status and timestamps

## Key Features

### Incremental Processing System
```python
def get_processed_plates():
    # Uses individual_plates.fa_processing_status column
    # Returns set of already-processed plate barcodes
    # Enables safe re-running without duplicate processing
```

### FA Sample ID Parsing
- **Format**: `{barcode}_{plate_name}_{well}` (e.g., `HOM7Q-1_BP9735_SitukAM.1_C1`)
- **Validation**: Ensures FA samples match expected database entries
- **Filtering**: Removes empty, ladder, LibStd, and library_control samples

### Quality Assessment Algorithm
```python
def findPassFailLibs(lib_df, dest_plates):
    # Apply per-plate thresholds
    passed = (nmol_L > threshold) & (avg_size > size_threshold)
    
    # Calculate index set failure rates (sample wells only)
    for index_set in ['PE17', 'PE18', 'PE19', 'PE20']:
        failure_rate = failed_count / total_count
        if failure_rate > 0.5:
            failed_index_sets.append(index_set)
    
    # Determine whole plate rework (>50% overall failure)
    overall_failure_rate = total_failed / total_samples
    redo_whole_plate = overall_failure_rate > 0.5
```

### Database Update Strategy
- **Hybrid approach**: Different update methods for different tables
  - `sample_metadata`: Never updated (static)
  - `individual_plates`: SQL UPDATE for status tracking
  - `master_plate_data`: Complete table replacement with merged results

## Technical Implementation

### FA Result Columns Added to Database
```sql
-- New columns in master_plate_data
ALTER TABLE master_plate_data ADD COLUMN dilution_factor REAL;
ALTER TABLE master_plate_data ADD COLUMN "ng/uL" REAL;
ALTER TABLE master_plate_data ADD COLUMN "nmole/L" REAL;
ALTER TABLE master_plate_data ADD COLUMN "Avg. Size" REAL;
ALTER TABLE master_plate_data ADD COLUMN Passed_library INTEGER;
ALTER TABLE master_plate_data ADD COLUMN Failed_index_sets TEXT;
ALTER TABLE master_plate_data ADD COLUMN Redo_whole_plate TEXT;

-- FA tracking columns in individual_plates
ALTER TABLE individual_plates ADD COLUMN fa_processing_status TEXT DEFAULT 'pending';
ALTER TABLE individual_plates ADD COLUMN fa_processed_timestamp TEXT;
ALTER TABLE individual_plates ADD COLUMN fa_batch_id TEXT;
```

### File Organization
- **FA result archiving**: Processed subdirectories moved to `archived_files/capsule_fa_analysis_results/batch_{timestamp}/`
- **Threshold archiving**: `thresholds.txt` moved to `previously_processed_threshold_files/`
- **Database archiving**: Timestamped copies preserve processing history

### Visualization System
- **384-well layout**: 16 rows (A-P) × 24 columns (1-24)
- **Color coding**:
  - Border colors: Well types (green=sample, red=neg_control, blue=pos_control, gray=unused)
  - Fill colors: Results (light green=pass, light coral=fail, light gray=no data)
  - Patterns: Diagonal lines for pass, X pattern for fail

## Error Handling
- **Missing FA files**: Clear guidance on expected file locations and formats
- **Sample mismatches**: Detailed reporting of missing or unexpected samples
- **Threshold validation**: Ensures all required threshold values are present
- **Database integrity**: Validates merge operations and prevents data corruption

## Integration Points
- **Input from Script 2**: Reads master database and expected samples from [`generate_lib_creation_files.py`](02_generate_lib_creation_files.md)
- **Output to Script 4**: Quality decisions feed into [`create_capsule_spits.py`](04_create_capsule_spits.md)
- **Threshold dependency**: Requires thresholds file generated by Script 2

## Usage Examples

### Basic Usage
```bash
python capsule_fa_analysis.py
```

### FA Status Report
The script provides comprehensive status reporting:
```
📊 FA PROCESSING STATUS REPORT
======================================================================
📋 Total plates scheduled for FA: 4
✅ Already processed: 2
⏳ Pending processing: 2
🆕 Ready to process now: 1
❌ Missing FA files: 1
📁 Available FA files: 1
```

### Quality Analysis Output
```
📋 Analyzing plate XUPVQ-1: 48 sample wells
  PE17: 2/12 failed (17%)
  PE18: 8/12 failed (67%)  ← Failed index set
  PE19: 1/12 failed (8%)
  PE20: 3/12 failed (25%)
  Overall: 14/48 failed (29%)
```

## Performance Features
- **Batch processing**: Handles multiple plates in single run
- **Memory efficiency**: Processes plates individually to manage large datasets
- **Skip logic**: Avoids reprocessing completed plates
- **Parallel file operations**: Creates multiple output files simultaneously

## Quality Control Features
- **Perfect merge validation**: Ensures all expected samples have FA results
- **Barcode verification**: Validates FA sample IDs match database expectations
- **Threshold completeness**: Requires all threshold parameters before processing
- **Result consistency**: Applies quality decisions uniformly across plate wells

This script transforms raw FA instrument data into actionable quality assessments, providing the foundation for informed plate selection decisions in Script 4.