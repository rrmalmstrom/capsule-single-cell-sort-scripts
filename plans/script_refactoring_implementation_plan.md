# Script Refactoring Implementation Plan

## Overview
Refactor two existing laboratory workflow scripts to change execution order and add barcode scanning verification.

## Current State
- **Script 1**: `make_ESP_smear_analysis_file.py` - Processes grid tables, creates ESP files
- **Script 2**: `relabel_lib_plates_for_pooling.py` - Creates barcode templates and labels

## Target State
- **New Script 1**: Grid processing + barcode generation (runs first)
- **New Script 2**: Barcode verification + ESP file generation (runs second)

---

## New Script 1: Grid Processing + Barcode Generation

### Script Name
`process_grid_tables_and_generate_barcodes.py`

### Purpose
Process grid tables, extract barcode mappings, and generate barcode scanning materials.

### Key Functions to Migrate

#### From `make_ESP_smear_analysis_file.py`:
- `read_project_database()` - Read database tables
- `identify_expected_grid_samples()` - Find samples selected for pooling
- `find_all_grid_tables()` - Locate and validate grid CSV files
- `validate_grid_table_columns_detailed()` - Validate grid table structure
- `read_multiple_grid_tables()` - Read and combine grid tables
- `detect_duplicate_samples()` - Check for duplicate samples
- `validate_grid_table_completeness()` - Ensure all expected samples present
- `extract_library_plate_container_barcode_mapping()` - Extract barcode mapping
- `update_individual_plates_with_esp_status()` - Update database with barcodes
- `archive_grid_table_files()` - Move processed grid files
- `validate_and_merge_data()` - Merge grid data with master_plate_data
- `update_master_plate_data_table()` - Update database with merged data
- `archive_csv_files()` - Archive existing CSV files
- `generate_fresh_csv_files()` - Generate updated CSV files

#### From `relabel_lib_plates_for_pooling.py`:
- `get_pooling_plates_data()` - Get plates selected for pooling
- `get_proposal_value()` - Get proposal from sample_metadata
- `create_bartender_file()` - Generate BarTender label files
- `copy_template_file()` - Copy Excel template
- `populate_excel_template()` - **UPDATED** - Populate Excel Expected Barcode column only

### Updated Excel Template Population Logic

The Excel template structure has changed:
- **Column A**: Sample number (1, 1, 2, 2, 3, 3, ...)
- **Column B**: Type ("plate name" or "LIMS ID") - visual reference, **not modified**
- **Column C**: Expected Barcode - **ONLY column populated by script**
- **Column D**: Checker - contains formulas, **not modified**
- **Column E**: Scanned barcode - left empty for user input

**Population Rules**:
- Each plate uses **2 consecutive rows**
- Row with type "plate name": Expected Barcode = plate barcode (e.g., "XUPVQ-1")
- Row with type "LIMS ID": Expected Barcode = library_plate_container_barcode (e.g., "27-810254")

**Updated populate_excel_template() function**:
```python
def populate_excel_template(excel_path: str, plate_data: List[Tuple[str, str]]) -> None:
    """Populate only the Expected Barcode column (Column C) with database values."""
    MAX_PLATES = 20  # Template handles 20 plates (40 rows total)
    
    if len(plate_data) > MAX_PLATES:
        raise ValueError(f"Too many plates ({len(plate_data)}) for template capacity ({MAX_PLATES})")
    
    try:
        workbook = openpyxl.load_workbook(excel_path)
        worksheet = workbook['Sheet1']
        
        # Populate Expected Barcode column (column C) starting from row 3
        for i, (plate_barcode, container_barcode) in enumerate(plate_data):
            # Each plate uses 2 rows
            plate_name_row = 3 + (i * 2)      # Row for "plate name" type
            lims_id_row = 3 + (i * 2) + 1     # Row for "LIMS ID" type
            
            # Column C (Expected Barcode):
            worksheet.cell(row=plate_name_row, column=3, value=plate_barcode)      # plate name row
            worksheet.cell(row=lims_id_row, column=3, value=container_barcode)     # LIMS ID row
        
        workbook.save(excel_path)
        workbook.close()
        
    except Exception as e:
        raise Exception(f"Failed to populate Excel template: {e}")
```

### Output Directory
`4_plate_selection_and_pooling/B_new_plate_barcode_labels/`

### Output Files
- Excel barcode scanning template: `{proposal}_pool_label_scan_verificiation_tool.xlsx`
- BarTender label file: `BARTENDER_{proposal}_container_labels.txt`

### Key Changes
1. **Remove**: ESP smear file generation logic
2. **Add**: Excel template population with barcode data
3. **Add**: BarTender file generation
4. **Modify**: Output directory path to `B_new_plate_barcode_labels/`
5. **Keep**: All grid validation and database update logic

### Database Modifications (Script 1)
- Update `individual_plates` table with `library_plate_container_barcode`
- Update `master_plate_data` table with merged grid information
- Archive and regenerate CSV files
- Add ESP status columns if they don't exist

---

## New Script 2: Barcode Verification + ESP Generation

### Script Name
`verify_scanning_and_generate_ESP_files.py`

### Purpose
Verify completed barcode scanning and generate ESP smear files.

### Key Functions to Migrate

#### From `make_ESP_smear_analysis_file.py`:
- `create_smear_analysis_file()` - Generate ESP smear files
- `read_project_database()` - Read database tables (READ-ONLY)
- `create_success_marker()` - Create workflow success marker

### Database Access
**READ-ONLY**: Script 2 only reads from the database to generate ESP files. All database modifications happen in Script 1.

### New Functions Needed

#### `find_barcode_scanning_file()`
```python
def find_barcode_scanning_file(base_dir, proposal):
    """
    Find the completed Excel barcode scanning file.
    
    Args:
        base_dir: Project base directory
        proposal: Proposal value for filename matching
        
    Returns:
        Path to Excel file
        
    Raises:
        FileNotFoundError: If Excel file not found
    """
    search_dir = Path(base_dir) / "4_plate_selection_and_pooling" / "B_new_plate_barcode_labels"
    expected_filename = f"{proposal}_pool_label_scan_verificiation_tool.xlsx"
    excel_path = search_dir / expected_filename
    
    if not excel_path.exists():
        raise FileNotFoundError(f"Barcode scanning file not found: {excel_path}")
    
    return excel_path
```

#### `validate_barcode_scanning_completion()`
```python
def validate_barcode_scanning_completion(excel_path):
    """
    Validate that barcode scanning was completed successfully.
    
    Args:
        excel_path: Path to Excel barcode scanning file
        
    Raises:
        SystemExit: If any FALSE values found in Checker column
    """
    try:
        workbook = openpyxl.load_workbook(excel_path, data_only=True)  # data_only=True reads values, not formulas
        worksheet = workbook['Sheet1']
        
        # Check Checker column (column D) for FALSE values
        checker_column = 4  # Column D
        false_found = False
        false_rows = []
        
        # Check rows 3-42 (where data should be)
        for row in range(3, 43):
            cell_value = worksheet.cell(row=row, column=checker_column).value
            
            if cell_value == False or cell_value == "FALSE":
                false_found = True
                false_rows.append(row)
        
        workbook.close()
        
        if false_found:
            print("FATAL ERROR: Barcode scanning validation failed!")
            print(f"Found FALSE values in Checker column at rows: {false_rows}")
            print("Please review and correct the barcode scanning before proceeding.")
            print("SCRIPT TERMINATED: Barcode scanning validation failed")
            sys.exit()
            
        print("✓ Barcode scanning validation passed")
        
    except Exception as e:
        print(f"ERROR reading barcode scanning file: {e}")
        print("SCRIPT TERMINATED: Could not validate barcode scanning")
        sys.exit()
```

#### `get_proposal_from_database()`
```python
def get_proposal_from_database(base_dir):
    """
    Get proposal value from sample_metadata table.
    
    Args:
        base_dir: Project base directory
        
    Returns:
        Proposal value as string
    """
    # Similar to existing get_proposal_value() function
    # Read from project_summary.db sample_metadata table
```

### Input Requirements
- Completed Excel file from `4_plate_selection_and_pooling/B_new_plate_barcode_labels/`
- Updated database with Library Plate Container Barcodes from Script 1

### Output Directory
`4_plate_selection_and_pooling/C_smear_file_for_ESP_upload/`

### Output Files
- ESP smear files: `ESP_smear_file_for_upload_{container_barcode}.csv`

### Key Changes
1. **Add**: Excel file location and reading logic
2. **Add**: Barcode scanning validation (Checker column)
3. **Add**: Proposal value retrieval from database
4. **Modify**: Output directory path to `C_smear_file_for_ESP_upload/`
5. **Keep**: ESP smear file generation logic
6. **Remove**: All database modification logic (read-only access)

### Database Modifications (Script 2)
**NONE** - Script 2 is read-only. No database updates are performed since no new information is introduced.

---

## Database Schema Requirements

### Individual Plates Table
Ensure these columns exist (Script 1 will add them if missing):
- `library_plate_container_barcode` (TEXT)
- `esp_generation_status` (TEXT, default 'pending')
- `esp_generated_timestamp` (TEXT)
- `esp_batch_id` (TEXT)

### Master Plate Data Table
Will be updated with merged grid table information by Script 1.

---

## Error Handling Requirements

### Script 1 Error Conditions
- No grid table files found
- Invalid grid table format
- Missing expected samples in grid tables
- Duplicate samples across grid tables
- Database connection failures
- Template file not found

### Script 2 Error Conditions
- Excel barcode scanning file not found
- FALSE values in Checker column (FATAL - sys.exit())
- Invalid Excel file format
- Database connection failures (read-only)
- Missing barcode data in database

---

## File Archiving Strategy

### Script 1
- Archive processed grid files to `previously_processed_grid_files/`
- Archive database and CSV files with timestamps

### Script 2
- **No archiving needed** - Script 2 is purely verification and output generation
- Excel file remains in place for potential re-verification

---

## Testing Requirements

### Script 1 Testing
- Test with valid grid tables
- Test with missing grid tables
- Test with invalid grid table formats
- Test Excel template population
- Test BarTender file generation
- Test database updates

### Script 2 Testing
- Test with completed Excel file (all TRUE/empty in Checker)
- Test with FALSE values in Checker column (should terminate)
- Test with missing Excel file
- Test ESP file generation after validation
- Test read-only database access

---

## Migration Strategy

### Phase 1: Create New Script 1
1. Copy relevant functions from both existing scripts
2. Remove ESP generation logic
3. Add Excel template population
4. Update output directory paths
5. Test thoroughly

### Phase 2: Create New Script 2
1. Copy ESP generation logic from existing Script 1
2. Add Excel file reading and validation
3. Add Checker column validation
4. Remove all database modification logic
5. Update output directory paths
6. Test thoroughly

### Phase 3: Integration Testing
1. Run Script 1 → manually complete Excel scanning → run Script 2
2. Test error conditions (FALSE in Checker column)
3. Verify complete workflow functionality
4. Verify no database modifications in Script 2

### Phase 4: Deployment
1. Backup existing scripts
2. Deploy new scripts
3. Update documentation
4. Train users on new workflow

---

## Summary of Key Changes

### Script 1 Changes
- **Add**: Excel template and BarTender file generation
- **Keep**: All grid processing and database updates
- **Remove**: ESP file generation
- **Change**: Output directory to `B_new_plate_barcode_labels/`

### Script 2 Changes
- **Add**: Excel file validation (Checker column)
- **Keep**: ESP file generation
- **Remove**: All database modifications (read-only)
- **Change**: Output directory to `C_smear_file_for_ESP_upload/`
- **Change**: Input source (reads from completed Excel file)