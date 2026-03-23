# Coding Agent Implementation Todo List

## Overview
Refactor two existing laboratory workflow scripts to change execution order and add barcode scanning verification.

## IMPORTANT DEVELOPMENT APPROACH

### Test-Driven Development (TDD) - Lightweight
- Use a **lightweight TDD approach** with both automated tests and manual validation
- Work on **ONE SCRIPT AT A TIME** - complete and validate Script 1 before starting Script 2
- This is an **INTERACTIVE PROCESS** - describe what you're doing at each step and ask questions
- Do NOT create both complete scripts and then test - validate each script individually

### Development Sequence
1. **Script 1 Development**: Create `process_grid_tables_and_generate_barcodes.py`
2. **Script 1 Testing**: Automated tests + manual verification by user
3. **Script 1 Validation**: User confirms Script 1 works correctly
4. **Script 2 Development**: Create `verify_scanning_and_generate_ESP_files.py`
5. **Script 2 Testing**: Automated tests + manual verification by user
6. **Final Integration**: Test complete workflow

### Technical Requirements
- **sqlite3**: This is part of Python standard library, no separate conda installation needed
- **Excel File Handling**: Use MCP Context7 to research best practices for:
  - Modifying .xlsx files with openpyxl
  - Reading Excel files to get VALUES (not formulas) - critical for Checker column validation
- **Interactive Communication**: Explain your approach and ask questions throughout development

## Python Environment Notes
- `sqlite3` is included in Python standard library - no additional conda package needed
- Existing environment `sip-lims` should have required packages
- May need to verify `openpyxl` is available for Excel file handling

## Script 1: Create `process_grid_tables_and_generate_barcodes.py`

### [ ] Set up script structure and imports
- [ ] Copy header and imports from both existing scripts
- [ ] Add required imports: `openpyxl`, `sqlite3`, `pandas`, `pathlib`, etc.
- [ ] Set up argument parsing and main() function structure

### [ ] Migrate grid processing functions from `make_ESP_smear_analysis_file.py`
- [ ] Copy `read_project_database()` function
- [ ] Copy `identify_expected_grid_samples()` function  
- [ ] Copy `find_all_grid_tables()` function
- [ ] Copy `validate_grid_table_columns_detailed()` function
- [ ] Copy `read_multiple_grid_tables()` function
- [ ] Copy `detect_duplicate_samples()` function
- [ ] Copy `validate_grid_table_completeness()` function
- [ ] Copy `extract_library_plate_container_barcode_mapping()` function
- [ ] Copy `archive_grid_table_files()` function

### [ ] Migrate database update functions from `make_ESP_smear_analysis_file.py`
- [ ] Copy `validate_and_merge_data()` function (remove ESP generation logic)
- [ ] Copy `update_individual_plates_with_esp_status()` function
- [ ] Copy `update_master_plate_data_table()` function
- [ ] Copy `archive_csv_files()` function
- [ ] Copy `generate_fresh_csv_files()` function

### [ ] Migrate barcode generation functions from `relabel_lib_plates_for_pooling.py`
- [ ] Copy `get_pooling_plates_data()` function
- [ ] Copy `get_proposal_value()` function
- [ ] Copy `create_bartender_file()` function
- [ ] Copy `copy_template_file()` function
- [ ] **UPDATE** `populate_excel_template()` function with new logic:
  - [ ] Only populate Column C (Expected Barcode)
  - [ ] Use 2 rows per plate (plate name + LIMS ID)
  - [ ] Plate name row gets plate barcode (e.g., XUPVQ-1)
  - [ ] LIMS ID row gets library_plate_container_barcode (e.g., 27-810254)

### [ ] Update directory paths
- [ ] Change output directory to `4_plate_selection_and_pooling/B_new_plate_barcode_labels/`
- [ ] Update all file path references

### [ ] Remove ESP generation logic
- [ ] Remove `create_smear_analysis_file()` function calls
- [ ] Remove ESP file output logic
- [ ] Keep all database updates and grid processing

### [ ] Add success marker and error handling
- [ ] Copy `create_success_marker()` function
- [ ] Add comprehensive error handling for all operations
- [ ] Add validation for template file existence

## Script 2: Create `verify_scanning_and_generate_ESP_files.py`

### [ ] Set up script structure and imports
- [ ] Copy header and imports from `make_ESP_smear_analysis_file.py`
- [ ] Add `openpyxl` import for Excel file reading
- [ ] Set up argument parsing and main() function structure

### [ ] Create new Excel validation functions
- [ ] **NEW** `get_proposal_from_database()` function:
  - [ ] Read proposal value from sample_metadata table
  - [ ] Handle database connection and error cases
- [ ] **NEW** `find_barcode_scanning_file()` function:
  - [ ] Search in `4_plate_selection_and_pooling/B_new_plate_barcode_labels/`
  - [ ] Look for `{proposal}_pool_label_scan_verificiation_tool.xlsx`
  - [ ] Raise FileNotFoundError if not found
- [ ] **NEW** `validate_barcode_scanning_completion()` function:
  - [ ] Load Excel file with `data_only=True` to read values not formulas
  - [ ] Check Column D (Checker) for FALSE values in rows 3-42
  - [ ] If any FALSE found, print error details and `sys.exit()`
  - [ ] Print success message if validation passes

### [ ] Migrate ESP generation functions (read-only database access)
- [ ] Copy `read_project_database()` function (read-only)
- [ ] Copy `create_smear_analysis_file()` function
- [ ] Copy `create_success_marker()` function

### [ ] Update directory paths
- [ ] Change output directory to `4_plate_selection_and_pooling/C_smear_file_for_ESP_upload/`
- [ ] Update all file path references

### [ ] Remove all database modification logic
- [ ] **REMOVE** all database UPDATE operations
- [ ] **REMOVE** CSV file generation
- [ ] **REMOVE** database archiving
- [ ] Keep only READ operations for ESP file generation

### [ ] Implement main workflow
- [ ] Get proposal value from database
- [ ] Find Excel barcode scanning file
- [ ] Validate barcode scanning completion (check Checker column)
- [ ] If validation passes, generate ESP files
- [ ] Create success marker

## Testing Requirements

### [ ] Test Script 1
- [ ] Test with valid grid tables and database
- [ ] Test Excel template population with correct data mapping
- [ ] Test BarTender file generation
- [ ] Test database updates (individual_plates and master_plate_data)
- [ ] Test error handling (missing files, invalid data)
- [ ] Verify output directory creation and file placement

### [ ] Test Script 2  
- [ ] Test with completed Excel file (all TRUE/empty in Checker column)
- [ ] **Test FATAL error case**: Excel file with FALSE in Checker column (should sys.exit())
- [ ] Test with missing Excel file
- [ ] Test ESP file generation after successful validation
- [ ] Verify read-only database access (no modifications)
- [ ] Test error handling for database connection issues

### [ ] Integration Testing
- [ ] Run complete workflow: Script 1 → manual Excel completion → Script 2
- [ ] Test with multiple plates
- [ ] Verify data consistency between scripts
- [ ] Test error recovery scenarios

## File Management

### [ ] Backup existing scripts
- [ ] Create backup copies of `make_ESP_smear_analysis_file.py`
- [ ] Create backup copies of `relabel_lib_plates_for_pooling.py`

### [ ] Update documentation
- [ ] Update script docstrings with new functionality
- [ ] Document the new two-step workflow
- [ ] Update any workflow documentation

## Key Implementation Notes

### Excel Template Population (Script 1)
- **CRITICAL**: Only modify Column C (Expected Barcode)
- Each plate uses 2 consecutive rows starting from row 3
- Row calculation: `plate_name_row = 3 + (i * 2)`, `lims_id_row = 3 + (i * 2) + 1`
- Data mapping: plate name row → plate barcode, LIMS ID row → container barcode

### Barcode Validation (Script 2)
- **CRITICAL**: Use `data_only=True` when loading Excel to read values not formulas
- **CRITICAL**: Any FALSE value in Checker column must cause `sys.exit()`
- Check rows 3-42, Column D (Checker column)
- Provide detailed error messages showing which rows have FALSE values

### Database Access
- **Script 1**: Full read/write access, performs all database modifications
- **Script 2**: Read-only access, no database modifications whatsoever

### Directory Structure
- **Script 1 Output**: `4_plate_selection_and_pooling/B_new_plate_barcode_labels/`
- **Script 2 Input**: Excel file from Script 1 output directory
- **Script 2 Output**: `4_plate_selection_and_pooling/C_smear_file_for_ESP_upload/`