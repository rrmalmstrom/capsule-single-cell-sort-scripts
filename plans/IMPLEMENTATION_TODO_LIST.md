# Implementation Todo List for Code Mode

## Overview
This todo list provides the specific, actionable steps for implementing the modifications to [`generate_barcode_labels.py`](../generate_barcode_labels.py) based on the [Detailed Implementation Plan](DETAILED_IMPLEMENTATION_PLAN.md).

## Phase 1: Foundation Changes (Low Risk)

### Error Handling Standardization
- [ ] Replace `sys.exit(1)` with `sys.exit()` in [`read_sample_csv()`](../generate_barcode_labels.py:81) (lines 81, 89, 101)
- [ ] Replace `sys.exit(1)` with `sys.exit()` in [`generate_barcodes()`](../generate_barcode_labels.py:191) (line 191)
- [ ] Replace `sys.exit(1)` with `sys.exit()` in [`save_to_database()`](../generate_barcode_labels.py:239) (line 239)
- [ ] Replace `sys.exit(1)` with `sys.exit()` in [`read_from_database()`](../generate_barcode_labels.py:269) (line 269)
- [ ] Replace `sys.exit(1)` with `sys.exit()` in [`make_bartender_file()`](../generate_barcode_labels.py:307) (line 307)
- [ ] Replace `sys.exit(1)` with `sys.exit()` in [`create_success_marker()`](../generate_barcode_labels.py:367) (line 367)
- [ ] Replace `sys.exit(1)` with `sys.exit()` in [`main()`](../generate_barcode_labels.py:453) (lines 453, 465)
- [ ] Test all error handling paths work correctly

### Documentation Updates
- [ ] Update script header docstring to reflect new workflow
- [ ] Update [`read_sample_csv()`](../generate_barcode_labels.py:54) docstring
- [ ] Update [`generate_barcodes()`](../generate_barcode_labels.py:136) docstring
- [ ] Update database function docstrings
- [ ] Update [`main()`](../generate_barcode_labels.py:394) docstring

## Phase 2: File Detection System (Medium Risk)

### CSV Detection Implementation
- [ ] Create `detect_csv_file()` function to replace [`get_csv_file()`](../generate_barcode_labels.py:310)
- [ ] Implement automatic CSV search in working directory
- [ ] Add CSV header validation for required columns: `['Proposal', 'Project', 'Sample', 'Number_of_sorted_plates']`
- [ ] Update [`main()`](../generate_barcode_labels.py:411) to use `detect_csv_file()` instead of `get_csv_file()`
- [ ] Write tests for CSV detection scenarios
- [ ] Test CSV detection with sample files

### Custom Plates File Implementation
- [ ] Create `read_custom_plates_file()` function to replace [`get_custom_plates()`](../generate_barcode_labels.py:324)
- [ ] Implement reading from `custom_plate_names.txt` file
- [ ] Add validation for plate names (<20 characters)
- [ ] Add plate number extraction for names ending with dot-number
- [ ] Update [`main()`](../generate_barcode_labels.py:416) to use file-based custom plates
- [ ] Write tests for custom plates file processing
- [ ] Test with sample custom plates file

### Additional Plates File Implementation
- [ ] Create `read_additional_plates_file()` function
- [ ] Implement parsing of format: "BP9735_SitukAM:2"
- [ ] Add logic to look up existing plates in database
- [ ] Add logic to calculate next plate numbers
- [ ] Integrate into workflow logic
- [ ] Write tests for additional plates processing
- [ ] Test with sample additional plates file

## Phase 3: Database Architecture (High Risk)

### Two-Table Schema Design
- [ ] Design `sample_metadata` table schema
- [ ] Design `individual_plates` table schema
- [ ] Create database migration functions
- [ ] Write tests for schema creation

### Database Function Modifications
- [ ] Modify [`save_to_database()`](../generate_barcode_labels.py:214) for two-table architecture
- [ ] Modify [`read_from_database()`](../generate_barcode_labels.py:242) for two-table architecture
- [ ] Add migration logic for existing single-table databases
- [ ] Add functions to save/read sample metadata
- [ ] Add functions to save/read individual plates
- [ ] Write comprehensive database tests
- [ ] Test migration with existing database files

## Phase 4: Barcode System Simplification (Medium Risk)

### Simplified Barcode Generation
- [ ] Create `generate_simple_barcodes()` function to replace [`generate_barcodes()`](../generate_barcode_labels.py:136)
- [ ] Implement single base barcode generation per project
- [ ] Implement incremental numbering system (T45JK.1, T45JK.2, etc.)
- [ ] Add continuation logic for subsequent runs
- [ ] Remove collision avoidance logic
- [ ] Remove echo/hamilton barcode storage in database
- [ ] Write tests for simplified barcode generation
- [ ] Test barcode continuation across runs

### BarTender File Updates
- [ ] Modify [`make_bartender_file()`](../generate_barcode_labels.py:272) to create echo/hamilton at print time
- [ ] Update to use lowercase prefixes: "eT45JK.1", "hT45JK.1"
- [ ] Ensure BarTender file format compatibility
- [ ] Write tests for updated BarTender file generation
- [ ] Test BarTender file with new barcode format

## Phase 5: Workflow Integration (High Risk)

### Main Function Redesign
- [ ] Implement new workflow logic in [`main()`](../generate_barcode_labels.py:394)
- [ ] Add file detection at start of workflow
- [ ] Update first run logic to use automatic file detection
- [ ] Update subsequent run logic to handle additional plates and custom plates
- [ ] Remove interactive prompts
- [ ] Integrate all new functions
- [ ] Write integration tests for complete workflows

### Complete Workflow Testing
- [ ] Test complete first run workflow with CSV file
- [ ] Test first run with CSV + custom plates
- [ ] Test subsequent run with additional plates
- [ ] Test subsequent run with custom plates
- [ ] Test subsequent run with both additional and custom plates
- [ ] Test error scenarios (missing files, invalid formats)
- [ ] Test with real laboratory data files

## Testing Requirements

### Test Environment Setup
- [ ] Ensure all tests run in `sip-lims` conda environment
- [ ] Verify test data files are available in `test_input_data_files/`
- [ ] Set up test database isolation

### Test Categories
- [ ] Unit tests for each new function
- [ ] Integration tests for workflow scenarios
- [ ] File system tests for file detection
- [ ] Database tests for two-table operations
- [ ] Error handling tests for all failure modes

## MCP Documentation Research

### Required Context7 Queries
- [ ] Research SQLAlchemy two-table relationship patterns
- [ ] Research pandas CSV validation best practices
- [ ] Research Python file detection algorithms
- [ ] Research database migration strategies for SQLite

### Documentation Updates
- [ ] Update function docstrings with research findings
- [ ] Add code comments explaining design decisions
- [ ] Update error messages for clarity

## Final Validation

### Functionality Verification
- [ ] Verify automatic CSV detection works reliably
- [ ] Verify file-based custom plates processing
- [ ] Verify additional standard plates support
- [ ] Verify simplified barcode generation
- [ ] Verify two-table database architecture
- [ ] Verify backward compatibility with existing databases

### Quality Assurance
- [ ] All tests pass in sip-lims environment
- [ ] Laboratory safety standards maintained
- [ ] Error handling consistency achieved
- [ ] Documentation accurate and complete
- [ ] Performance comparable to current system

## Success Criteria Checklist

- [ ] Script runs without interactive prompts
- [ ] Automatic file detection works for all file types
- [ ] Two-table database architecture implemented
- [ ] Simplified barcode system functional
- [ ] All existing functionality preserved
- [ ] Comprehensive test coverage achieved
- [ ] Laboratory safety standards maintained

## Notes for Code Mode

1. **Always use sip-lims conda environment** for all Python operations
2. **Follow TDD approach** - write tests first, then implement functions
3. **Use MCP Context7** for documentation research when needed
4. **Maintain laboratory safety standards** with "FATAL ERROR" messaging
5. **Test incrementally** after each phase completion
6. **Preserve existing file archiving strategy**
7. **Focus on modest modifications** rather than complete rewrites

## Handoff Information

- **Implementation Plan**: [DETAILED_IMPLEMENTATION_PLAN.md](DETAILED_IMPLEMENTATION_PLAN.md)
- **Current Script**: [`generate_barcode_labels.py`](../generate_barcode_labels.py)
- **Test Files**: [`tests/test_barcode_labels.py`](../tests/test_barcode_labels.py)
- **Sample Data**: `test_input_data_files/` directory
- **Environment**: `sip-lims` conda environment required