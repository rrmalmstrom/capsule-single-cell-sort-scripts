# Script 6: relabel_lib_plates_for_pooling.py

## Overview
This is the **sixth and final script** in the laboratory workflow that creates populated barcode scan templates and BarTender label files for capsule SPS pooling. It generates the physical labeling materials needed to properly identify and track library plates during the final pooling process.

## Primary Functions

### Barcode Template Generation
- **Excel template population**: Creates populated barcode scan verification tools
- **Database-driven data**: Retrieves plate and container barcode information
- **Proposal-based naming**: Uses project proposal for consistent file naming
- **Template validation**: Ensures capacity limits and data integrity

### BarTender Label Creation
- **Physical label generation**: Creates BarTender-compatible files for label printing
- **Container barcode focus**: Uses Library Plate Container Barcodes for external tracking
- **Sorted output**: Organizes labels in consistent order for efficient printing
- **Laboratory compatibility**: Follows established BarTender template format

### Quality Control Integration
- **Selection filtering**: Only processes plates marked for pooling
- **Complete data validation**: Ensures both plate and container barcodes are available
- **Proposal consistency**: Validates single proposal per project

## Input Requirements

### Database Dependencies
- **`project_summary.db`**: Must contain updated tables from Script 5
  - `sample_metadata`: Project proposal information
  - `individual_plates`: Plates with pooling selection and container barcodes

### Required Database Columns
```sql
-- individual_plates table
barcode,                           -- Internal plate barcode (e.g., XUPVQ-1)
library_plate_container_barcode,   -- External container barcode (e.g., 27-810254)  
selected_for_pooling               -- Boolean selection flag

-- sample_metadata table
Proposal                          -- Project proposal for file naming
```

### Template File
- **Location**: Same directory as script
- **Filename**: `BLANK_TEMPLATE_Pooling_Plate_Barcode_Scan_tool.xlsx`
- **Format**: Excel workbook with predefined structure
- **Capacity**: Supports up to 20 plates (rows 3-42)

## Output Files

### Populated Excel Template
- **Location**: `4_plate_selection_and_pooling/C_pooling_barcode_labels/`
- **Filename**: `{proposal}_pool_label_scan_verificiation_tool.xlsx`
- **Content**: Barcode verification tool with plate data populated
- **Format**: Excel workbook with data in columns M and N

### Excel Template Structure
```
Row 3-22: Data rows (up to 20 plates)
Column M (13): Internal plate barcode (e.g., XUPVQ-1)
Column N (14): Library Plate Container Barcode (e.g., 27-810254)
```

### BarTender Label File
- **Location**: Same directory as Excel file
- **Filename**: `BARTENDER_{proposal}_container_labels.txt`
- **Content**: Container barcode labels for physical printing
- **Format**: BarTender-compatible with header and data sections

### BarTender File Format
```
%BTW% /AF="\\BARTENDER\shared\templates\ECHO_BCode8.btw" /D="%Trigger File Name%" /PRN="bcode8" /R=3 /P /DD

%END%


27-810254,"27-810254"
,
27-999999,"27-999999"
,

```

## Key Features

### Data Retrieval Logic
```python
def get_pooling_plates_data(db_path):
    query = """
    SELECT barcode, library_plate_container_barcode
    FROM individual_plates
    WHERE selected_for_pooling = 1
    ORDER BY barcode
    """
    # Filters out rows where either barcode is None
    # Returns only complete barcode pairs
```

### Proposal Validation
```python
def get_proposal_value(db_path):
    # Ensures exactly one proposal exists in sample_metadata
    # Prevents processing projects with multiple or missing proposals
    # Returns proposal string for file naming
```

### Template Population
```python
def populate_excel_template(excel_path, plate_data):
    # Validates plate count against template capacity (max 20)
    # Populates columns M and N starting from row 3
    # Maintains Excel formatting and structure
```

### BarTender Generation
```python
def create_bartender_file(plate_data, output_dir, proposal):
    # Sorts by container barcode for consistent ordering
    # Uses container barcode as both barcode and label text
    # Includes proper separators and formatting for BarTender
```

## Technical Implementation

### File Management
- **Template copying**: Creates working copy with proposal-based naming
- **Directory creation**: Automatically creates output directory structure
- **Error handling**: Validates file existence and accessibility

### Data Validation Pipeline
1. **Database validation**: Ensures database file exists and is accessible
2. **Template validation**: Confirms template file is available
3. **Proposal validation**: Verifies single proposal in project
4. **Data completeness**: Ensures all selected plates have container barcodes
5. **Capacity validation**: Confirms plate count fits template capacity

### Error Handling
- **Missing database**: Clear error with expected file location
- **Missing template**: Guidance on template file placement
- **Multiple proposals**: Error with list of found proposals
- **No selected plates**: Warning about empty selection
- **Incomplete data**: Filtering of plates missing container barcodes

## Integration Points
- **Input from Script 5**: Reads container barcode mapping from [`make_ESP_smear_analysis_file.py`](05_make_ESP_smear_analysis_file.md)
- **Final workflow output**: Generates physical materials for laboratory use
- **External template dependency**: Requires Excel template file in script directory

## Usage Examples

### Basic Usage
```bash
python relabel_lib_plates_for_pooling.py
```

### Verbose Mode
```bash
python relabel_lib_plates_for_pooling.py --verbose
```

### Expected Output
```
Processing 3 plates for proposal 599999
✓ Created: 599999_pool_label_scan_verificiation_tool.xlsx
✓ Created: BARTENDER_599999_container_labels.txt
```

### Data Flow Example
```python
# Database query results
plate_data = [
    ('XUPVQ-1', '27-810254'),
    ('XUPVQ-3', '27-999999'),
    ('XUPVQ-6', '27-000002')
]

# Excel population (columns M, N)
Row 3: XUPVQ-1, 27-810254
Row 4: XUPVQ-3, 27-999999  
Row 5: XUPVQ-6, 27-000002

# BarTender file (sorted by container barcode)
27-000002,"27-000002"
27-810254,"27-810254"
27-999999,"27-999999"
```

## Quality Control Features
- **Complete data requirement**: Only processes plates with both barcodes
- **Capacity validation**: Prevents template overflow with clear error messages
- **Proposal consistency**: Ensures single project context
- **Sorted output**: Consistent ordering for reproducible label printing

## Laboratory Integration
- **Physical workflow support**: Provides materials for manual barcode verification
- **Label printing**: BarTender files ready for immediate label generation
- **Traceability**: Links internal plate barcodes to external container barcodes
- **Error prevention**: Verification tools help prevent mislabeling during pooling

## File Organization
- **Dedicated subfolder**: Creates organized location for pooling materials
- **Proposal-based naming**: Consistent file naming across project
- **Template preservation**: Original template remains unchanged
- **Ready-to-use output**: Files immediately usable for laboratory operations

## Workflow Completion
This script represents the final step in the laboratory workflow, generating the physical materials needed to complete the capsule sorting and pooling process. It bridges the digital workflow with physical laboratory operations, ensuring proper identification and tracking of selected samples through the final pooling stages.

### Workflow Summary
1. **Script 1**: Project initialization and barcode generation
2. **Script 2**: Library preparation and index assignment  
3. **Script 3**: Fragment Analyzer quality analysis
4. **Script 4**: Plate selection and SPITS file generation
5. **Script 5**: ESP smear file creation for external processing
6. **Script 6**: Physical labeling materials for pooling completion

The workflow transforms initial sample metadata into a complete laboratory processing pipeline with quality control, selection logic, external system integration, and physical tracking materials.