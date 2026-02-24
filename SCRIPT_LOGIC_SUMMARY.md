# Laboratory Barcode Label Generation Script - Logic Summary

## Overview

The `generate_barcode_labels.py` script is a laboratory automation tool that generates BarTender-compatible barcode labels for microwell plates. It follows a streamlined workflow with automatic file detection, simplified barcode generation, and organized file management.

## Script Logic Flow

### 1. Startup and Database Detection

The script begins by checking if a database file (`project_summary.db`) exists to determine if this is a first run or subsequent run.

**First Run (No Database):**
- Automatically detects and validates `sample_metadtata.csv` in the working directory
- Validates that the CSV contains all 13 expected columns
- Processes sample metadata to generate plate names based on `Number_of_sorted_plates` column

**Subsequent Run (Database Exists):**
- Reads existing sample metadata and plate data from the two-table database
- Displays current database contents (number of samples and plates)

### 2. Input File Processing

#### Sample Metadata CSV Format
The script expects a CSV file named `sample_metadtata.csv` with these 13 columns:
- `Proposal`, `Project`, `Sample`, `Collection Year`, `Collection Month`
- `Collection Day`, `Sample Isolated From`, `Latitude`, `Longitude`
- `Depth (m)`, `Elevation (m)`, `Country`, `Number_of_sorted_plates`

Only 4 columns are required for processing: `Proposal`, `Project`, `Sample`, `Number_of_sorted_plates`

#### Optional Input Files

**Custom Plates File (`custom_plate_names.txt`):**
- Simple text file with one plate name per line
- Plate names must be under 20 characters
- Example format:
  ```
  CustomPlate_A
  CustomPlate_B
  SpecialSample_1
  ```

**Additional Standard Plates File (`additional_standard_plates.txt`):**
- Format: `SampleID:NumberOfAdditionalPlates`
- Used only on subsequent runs to add more plates for existing samples
- Example format:
  ```
  BP9735_SitukAM:2
  BP9735_WCBP1AM:1
  ```

### 3. Plate Name Generation

For each sample, the script generates plate names following the pattern:
- `{Project}_{Sample}.{PlateNumber}`
- Example: `BP9735_SitukAM.1`, `BP9735_SitukAM.2`, `BP9735_SitukAM.3`

The number of plates per sample is determined by the `Number_of_sorted_plates` column.

### 4. Simplified Barcode Generation

**New Barcode System:**
- Generates one 5-character alphanumeric base barcode per project (e.g., `ABC12`)
- Uses incremental numbering: `ABC12.1`, `ABC12.2`, `ABC12.3`, etc.
- No collision avoidance needed - simple sequential numbering
- Continues numbering from existing plates on subsequent runs

**Echo/Hamilton Variants:**
- Created only at print time in BarTender file
- Echo: lowercase 'e' prefix (e.g., `eABC12.1`)
- Hamilton: lowercase 'h' prefix (e.g., `hABC12.1`)

### 5. Database Architecture

**Two-Table Structure:**
- **sample_metadata table:** Stores project and sample information
- **individual_plates table:** Stores individual plate data with barcodes
- **Database file:** `project_summary.db`

This replaces the old single-table architecture for better data organization and query performance.

### 6. BarTender File Generation

**File Format:**
- Reverse order: Highest plate number first (e.g., plate 15, then 14, then 13...)
- Interleaved format: Echo plate, then Hamilton plate for same number
- Blank separator lines between each plate set (comma-only lines)

**Label Format:**
- Echo labels: `eABC12.15,"BP9735_SitukAM.5"`
- Hamilton labels: `hABC12.15,"hABC12.15"`

### 7. File Management and Organization

**Automatic Folder Creation:**
- `bartender_barcode_labels/` - Contains all BarTender files
- `previously_processed_plate_files/custom_plates/` - Processed custom plate files
- `previously_processed_plate_files/standard_plates/` - Processed additional plate files
- `archived_files/` - Archived database and CSV files with timestamps

**File Archiving:**
- Database files archived with timestamp suffix before updates
- CSV files archived before creating new versions
- Input text files moved to organized folders after processing

### 8. CSV File Management

**Archive and Regenerate Process:**
1. Archive existing `sample_metadata.csv` and `plate_names.csv` (if they exist)
2. Create new `sample_metadata.csv` from current sample metadata DataFrame
3. Create new `plate_names.csv` from current individual plates DataFrame

**File Naming Convention:**
- Archived files: `filename_YYYY_MM_DD-TimeHH-MM-SS.extension`
- Example: `sample_metadata_2026_02_24-Time14-30-25.csv`

### 9. User Interaction

**Interactive Prompts (Preserved):**
- "Would you like to add custom plates?" (Y/N)
- "Would you like to add additional standard plates?" (Y/N, subsequent runs only)

**Automatic Detection:**
- Sample metadata CSV detection and validation
- Input file detection and processing
- No manual file path entry required

### 10. Error Handling and Safety

**Laboratory Safety Standards:**
- All errors prefixed with "FATAL ERROR:"
- Descriptive error messages explaining the issue
- Consistent use of `sys.exit()` for termination
- Barcode uniqueness validation at multiple stages

**Validation Points:**
- CSV file format and column validation
- Barcode uniqueness within new plates
- Barcode uniqueness across entire final dataset
- File existence and accessibility checks

### 11. Success Workflow

**Completion Steps:**
1. Generate and validate barcodes
2. Archive existing database
3. Save to two-table database
4. Generate BarTender file
5. Organize files into folders
6. Archive and regenerate CSV files
7. Create success marker for workflow integration
8. Display completion summary

**Output Summary:**
- Total samples and plates in database
- Number of new plates added
- File locations and organization status
- Barcode validation confirmation

## Key Improvements

1. **Simplified Barcode System:** Eliminated complex collision avoidance for simple incremental numbering
2. **Automatic File Detection:** No manual file path entry required
3. **Two-Table Database:** Better data organization and query performance
4. **Organized File Management:** Automatic folder creation and file organization
5. **CSV Regeneration:** Always provides current data in CSV format
6. **Enhanced Error Handling:** Consistent laboratory safety standards
7. **Streamlined Workflow:** Reduced user interaction while maintaining necessary prompts

This design ensures reliable, safe operation in laboratory environments while providing the flexibility needed for various plate processing scenarios.