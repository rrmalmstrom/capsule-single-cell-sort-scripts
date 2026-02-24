# Detailed Implementation Plan for generate_barcode_labels.py Modifications

## Executive Summary

This plan outlines the comprehensive modification of [`generate_barcode_labels.py`](../generate_barcode_labels.py) based on detailed requirements analysis. The modifications will transform the script from an interactive, single-table system to an automated, two-table architecture with simplified barcode generation and enhanced file-based input handling.

## Current Architecture Analysis

### Existing Script Structure
- **Entry Point**: [`main()`](../generate_barcode_labels.py:394) - Controls workflow logic
- **Database Operations**: Single table `plate_barcodes` with file replacement strategy
- **Barcode System**: Complex 3-variant system (base, echo, hamilton) with collision avoidance
- **User Interaction**: Interactive prompts for CSV file and custom plates
- **File Management**: Archive-and-replace strategy for database and BarTender files

### Key Functions Requiring Modification
1. [`get_csv_file()`](../generate_barcode_labels.py:310) - Interactive CSV input
2. [`get_custom_plates()`](../generate_barcode_labels.py:324) - Interactive custom plate input
3. [`generate_barcodes()`](../generate_barcode_labels.py:136) - Complex barcode generation
4. [`save_to_database()`](../generate_barcode_labels.py:214) - Single table storage
5. [`read_from_database()`](../generate_barcode_labels.py:242) - Single table reading
6. [`make_bartender_file()`](../generate_barcode_labels.py:272) - BarTender file generation
7. [`main()`](../generate_barcode_labels.py:394) - Workflow orchestration

## Problem-to-Function Mapping

### Problem 1: Error Handling Inconsistency
**Target Functions**: ALL functions using `sys.exit(1)`
- [`read_sample_csv()`](../generate_barcode_labels.py:81) - Line 81, 89, 101
- [`generate_barcodes()`](../generate_barcode_labels.py:191) - Line 191
- [`save_to_database()`](../generate_barcode_labels.py:239) - Line 239
- [`read_from_database()`](../generate_barcode_labels.py:269) - Line 269
- [`make_bartender_file()`](../generate_barcode_labels.py:307) - Line 307
- [`create_success_marker()`](../generate_barcode_labels.py:367) - Line 367
- [`main()`](../generate_barcode_labels.py:453) - Lines 453, 465

**Required Change**: Replace ALL `sys.exit(1)` with `sys.exit()`

### Problem 2: Interactive CSV File Input
**Target Function**: [`get_csv_file()`](../generate_barcode_labels.py:310)
**Current Behavior**: Interactive prompt loop
**Required Change**: Replace with automatic CSV detection function

**New Function Design**: `detect_csv_file()`
```python
def detect_csv_file():
    """
    Automatically detect and validate CSV file in working directory.
    
    Returns:
        Path: Valid CSV file path
        
    Raises:
        SystemExit: If no valid CSV found
    """
    # Search for .csv files in current directory
    # Validate each CSV for required headers
    # Return first valid CSV or fatal error
```

### Problem 3: Interactive Custom Plates Input
**Target Function**: [`get_custom_plates()`](../generate_barcode_labels.py:324)
**Current Behavior**: Interactive prompt for plate names
**Required Change**: Replace with file-based input

**New Function Design**: `read_custom_plates_file()`
```python
def read_custom_plates_file():
    """
    Read custom plate names from 'custom_plate_names.txt' file.
    
    Returns:
        list: List of validated custom plate names
        
    Raises:
        SystemExit: If file missing when custom plates expected
    """
    # Check for custom_plate_names.txt
    # Validate plate names (<20 characters)
    # Extract plate numbers if format matches
```

### Problem 4: Complex Barcode Generation System
**Target Function**: [`generate_barcodes()`](../generate_barcode_labels.py:136)
**Current Behavior**: Generates base, echo, hamilton with collision avoidance
**Required Change**: Simplify to single base barcode with incremental numbering

**New Function Design**: `generate_simple_barcodes()`
```python
def generate_simple_barcodes(plates_df, existing_df=None):
    """
    Generate single base barcode with incremental plate numbering.
    
    Args:
        plates_df: New plates needing barcodes
        existing_df: Existing plates to continue numbering
        
    Returns:
        pd.DataFrame: Plates with base barcodes and incremental numbers
    """
    # Generate ONE base barcode per project
    # Assign incremental numbers: T45JK.1, T45JK.2, etc.
    # Continue from existing highest number
    # Remove collision avoidance logic
```

### Problem 5: Single Table Database Architecture
**Target Functions**: 
- [`save_to_database()`](../generate_barcode_labels.py:214)
- [`read_from_database()`](../generate_barcode_labels.py:242)

**Current Behavior**: Single `plate_barcodes` table
**Required Change**: Two-table architecture

**New Database Schema**:
```sql
-- Table 1: Sample metadata with plate lists
CREATE TABLE sample_metadata (
    id INTEGER PRIMARY KEY,
    proposal TEXT,
    project TEXT,
    sample TEXT,
    collection_year INTEGER,
    collection_month INTEGER,
    collection_day INTEGER,
    sample_isolated_from TEXT,
    latitude REAL,
    longitude REAL,
    depth_m REAL,
    elevation_m REAL,
    country TEXT,
    number_of_sorted_plates INTEGER,
    plate_names_list TEXT,  -- JSON array of plate names
    is_custom BOOLEAN,
    created_timestamp TEXT
);

-- Table 2: Individual plate details
CREATE TABLE individual_plates (
    id INTEGER PRIMARY KEY,
    plate_name TEXT UNIQUE,
    base_barcode TEXT,
    plate_number INTEGER,
    project TEXT,
    sample TEXT,
    is_custom BOOLEAN,
    created_timestamp TEXT
);
```

### Problem 6: Outdated Documentation
**Target**: ALL function docstrings and comments
**Required Change**: Update to reflect new requirements

### Problem 7: No Support for Additional Standard Plates
**New Function Required**: `read_additional_plates_file()`
```python
def read_additional_plates_file():
    """
    Read additional standard plates from 'additional_sort_plates.txt'.
    
    Returns:
        dict: Mapping of sample_id to additional plate count
    """
    # Parse format: "BP9735_SitukAM:2"
    # Look up existing plates in database
    # Calculate next plate numbers
```

## New Two-Table Database Architecture

### Table 1: sample_metadata
**Purpose**: Store original CSV data plus generated plate name lists
**Key Features**:
- One row per sample from CSV
- `plate_names_list` stores JSON array of all plate names for that sample
- Custom plates get special "CUSTOM" entry
- Maintains full audit trail

### Table 2: individual_plates
**Purpose**: Store individual plate details with barcodes
**Key Features**:
- One row per physical plate
- Links to sample_metadata via project/sample
- Contains barcode and plate-specific metadata
- Enables efficient plate lookups

### Migration Strategy
1. **Backward Compatibility**: Read existing single-table databases
2. **Data Migration**: Convert existing data to two-table format
3. **Archiving**: Maintain existing archiving strategy for both tables

## Simplified Barcode Generation System

### Current System Issues
- Complex 3-variant generation (base, echo, hamilton)
- Collision avoidance with 1000 retry attempts
- All variants stored in database
- Echo/Hamilton created at generation time

### New Simplified System
1. **Single Base Barcode**: Generate ONE 5-character code per project
2. **Incremental Numbering**: T45JK.1, T45JK.2, T45JK.3, etc.
3. **Continuation Logic**: On subsequent runs, continue from highest number
4. **Print-Time Variants**: Echo/Hamilton created only during BarTender file generation
5. **No Collision Avoidance**: Simple incremental system eliminates need

### Implementation Details
```python
def generate_project_barcode():
    """Generate single 5-character base barcode for project."""
    return ''.join(random.choices(CHARSET, k=5))

def assign_plate_numbers(plates_df, base_barcode, start_number=1):
    """Assign incremental numbers to plates."""
    for i, idx in enumerate(plates_df.index):
        plates_df.at[idx, 'base_barcode'] = base_barcode
        plates_df.at[idx, 'plate_number'] = start_number + i
        plates_df.at[idx, 'full_barcode'] = f"{base_barcode}.{start_number + i}"
```

## Automatic File Detection Algorithms

### CSV File Detection
```python
def detect_csv_file():
    """
    Search working directory for valid CSV files.
    
    Algorithm:
    1. Find all *.csv files in current directory
    2. For each CSV file:
       a. Try to read with pandas
       b. Check for required headers
       c. Validate data types
    3. Return first valid CSV
    4. Fatal error if none found
    """
    required_headers = ['Proposal', 'Project', 'Sample', 'Number_of_sorted_plates']
    csv_files = list(Path('.').glob('*.csv'))
    
    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file, encoding='utf-8-sig')
            if all(col in df.columns for col in required_headers):
                return csv_file
        except Exception:
            continue
    
    # Fatal error if no valid CSV found
    print("FATAL ERROR: No valid CSV file found in working directory")
    sys.exit()
```

### Additional Files Detection
```python
def detect_additional_files():
    """
    Check for additional input files in working directory.
    
    Returns:
        dict: Available files and their status
    """
    files = {
        'custom_plates': Path('custom_plate_names.txt').exists(),
        'additional_plates': Path('additional_sort_plates.txt').exists()
    }
    return files
```

## Workflow Logic Changes

### Current Workflow
1. Check database existence → First run vs Subsequent run
2. First run: CSV + optional custom plates
3. Subsequent run: Only custom plates

### New Workflow
1. **Always check for files first**: CSV, custom plates, additional plates
2. **First run**: Process CSV + optional custom plates
3. **Subsequent runs**: 
   - Additional standard plates from file
   - Custom plates from file
   - Both types can be processed simultaneously

### New Main Function Logic
```python
def main():
    """New main function workflow."""
    # 1. Detect available input files
    available_files = detect_available_files()
    
    # 2. Determine run type and required processing
    existing_df = read_from_database(DATABASE_NAME)
    
    # 3. Process based on available files
    if existing_df is None:
        # First run - require CSV
        if not available_files['csv']:
            fatal_error("No CSV file found for first run")
        process_first_run(available_files)
    else:
        # Subsequent run - process additional files
        process_subsequent_run(available_files, existing_df)
```

## Test-Driven Development Specifications

### Test Categories
1. **Unit Tests**: Individual function testing
2. **Integration Tests**: Workflow testing
3. **File System Tests**: File detection and processing
4. **Database Tests**: Two-table operations
5. **Barcode Tests**: Simplified generation system

### Key Test Cases

#### CSV Detection Tests
```python
def test_detect_csv_file_valid():
    """Test detection of valid CSV file."""
    
def test_detect_csv_file_multiple_valid():
    """Test selection when multiple valid CSVs exist."""
    
def test_detect_csv_file_none_valid():
    """Test fatal error when no valid CSV found."""
```

#### Barcode Generation Tests
```python
def test_generate_simple_barcodes_first_run():
    """Test barcode generation for first run."""
    
def test_generate_simple_barcodes_continuation():
    """Test continuation of numbering in subsequent runs."""
    
def test_barcode_incremental_numbering():
    """Test proper incremental numbering."""
```

#### Database Tests
```python
def test_two_table_save():
    """Test saving to both sample_metadata and individual_plates tables."""
    
def test_two_table_read():
    """Test reading from two-table architecture."""
    
def test_database_migration():
    """Test migration from single-table to two-table format."""
```

#### File Processing Tests
```python
def test_read_custom_plates_file():
    """Test reading custom plates from file."""
    
def test_read_additional_plates_file():
    """Test reading additional plates specification."""
    
def test_file_validation():
    """Test validation of input file formats."""
```

## Implementation Sequence

### Phase 1: Foundation Changes (Low Risk)
1. **Error Handling Standardization**
   - Replace all `sys.exit(1)` with `sys.exit()`
   - Update error messages for consistency
   - Test: Verify all error paths work correctly

2. **Documentation Updates**
   - Update all function docstrings
   - Update header comments
   - Update inline comments
   - Test: Documentation review

### Phase 2: File Detection System (Medium Risk)
1. **Implement CSV Detection**
   - Create `detect_csv_file()` function
   - Replace `get_csv_file()` calls
   - Test: CSV detection with various scenarios

2. **Implement Custom Plates File Reading**
   - Create `read_custom_plates_file()` function
   - Replace `get_custom_plates()` calls
   - Test: File-based custom plate processing

3. **Implement Additional Plates File Reading**
   - Create `read_additional_plates_file()` function
   - Add to workflow logic
   - Test: Additional plates processing

### Phase 3: Database Architecture (High Risk)
1. **Design Two-Table Schema**
   - Create new table definitions
   - Design migration functions
   - Test: Schema creation and validation

2. **Implement Database Functions**
   - Modify `save_to_database()` for two tables
   - Modify `read_from_database()` for two tables
   - Add migration logic
   - Test: Two-table operations

3. **Data Migration**
   - Convert existing single-table data
   - Maintain backward compatibility
   - Test: Migration with real data

### Phase 4: Barcode System Simplification (Medium Risk)
1. **Implement Simplified Generation**
   - Create `generate_simple_barcodes()` function
   - Remove collision avoidance logic
   - Implement incremental numbering
   - Test: Barcode generation and numbering

2. **Update BarTender File Generation**
   - Modify `make_bartender_file()` to create echo/hamilton at print time
   - Update file format for new barcode system
   - Test: BarTender file compatibility

### Phase 5: Workflow Integration (High Risk)
1. **Update Main Function**
   - Implement new workflow logic
   - Integrate all new functions
   - Handle first run vs subsequent run scenarios
   - Test: Complete workflow scenarios

2. **Integration Testing**
   - Test complete first run workflow
   - Test complete subsequent run workflow
   - Test error scenarios
   - Test with real laboratory data

## MCP Documentation Requirements

### Context7 Library Research Needed
1. **SQLAlchemy Best Practices**
   - Two-table relationship design
   - Migration strategies
   - Transaction handling

2. **Pandas DataFrame Operations**
   - Efficient CSV processing
   - Data validation techniques
   - Memory optimization

3. **File System Operations**
   - Robust file detection
   - Cross-platform compatibility
   - Error handling patterns

### Documentation Queries
```python
# Example MCP queries needed:
# 1. "SQLAlchemy two-table relationship design patterns"
# 2. "Pandas CSV validation and error handling best practices"
# 3. "Python file detection algorithms for laboratory automation"
# 4. "Database migration strategies for SQLite with SQLAlchemy"
```

## Conda Environment Requirements

### Environment Setup
```bash
# Always activate sip-lims environment before any Python operations
conda activate sip-lims

# Verify required packages
python -c "import pandas, sqlalchemy, pathlib; print('Environment ready')"
```

### Testing Protocol
```bash
# All testing must be done in sip-lims environment
conda activate sip-lims
cd /Users/RRMalmstrom/Desktop/Programming/capsule_sort_scripts
python -m pytest tests/ -v
```

## Integration Points for Coding and Debugging Agents

### Handoff to Code Mode
**Trigger Conditions**:
- User approves this implementation plan
- All clarifying questions answered
- Test specifications confirmed

**Handoff Package**:
1. **This implementation plan document**
2. **Function-by-function modification specifications**
3. **Test case specifications**
4. **Database schema definitions**
5. **File format specifications**

### Code Mode Responsibilities
1. **Implement functions in sequence** (Phases 1-5)
2. **Write tests first** (TDD approach)
3. **Use MCP Context7** for documentation research
4. **Test in sip-lims environment** for all operations
5. **Maintain laboratory safety standards**

### Debug Mode Integration Points
**Trigger Conditions**:
- Test failures during implementation
- Unexpected behavior in file detection
- Database migration issues
- Barcode generation problems

**Debug Mode Responsibilities**:
1. **Systematic debugging** of failed tests
2. **Root cause analysis** of workflow issues
3. **Performance optimization** if needed
4. **Data integrity validation**

### Communication Protocol
1. **Progress Updates**: After each phase completion
2. **Issue Escalation**: For architectural decisions
3. **Test Results**: Comprehensive test reports
4. **Final Validation**: Complete workflow testing

## Risk Assessment and Mitigation

### High-Risk Areas
1. **Database Migration**: Potential data loss
   - **Mitigation**: Comprehensive backup and rollback procedures
   
2. **Workflow Logic Changes**: Breaking existing functionality
   - **Mitigation**: Extensive integration testing
   
3. **File Detection**: False positives/negatives
   - **Mitigation**: Robust validation and error handling

### Medium-Risk Areas
1. **Barcode System Changes**: Compatibility issues
   - **Mitigation**: Maintain BarTender file format compatibility
   
2. **File Processing**: Format variations
   - **Mitigation**: Flexible parsing with validation

### Low-Risk Areas
1. **Error Handling**: Standardization changes
   - **Mitigation**: Simple find-and-replace with testing
   
2. **Documentation**: Updates
   - **Mitigation**: Review and validation

## Success Criteria

### Functional Requirements
- [ ] Automatic CSV detection works reliably
- [ ] File-based custom plates processing
- [ ] Additional standard plates support
- [ ] Simplified barcode generation
- [ ] Two-table database architecture
- [ ] Backward compatibility maintained

### Quality Requirements
- [ ] All tests pass in sip-lims environment
- [ ] Laboratory safety standards maintained
- [ ] Error handling consistency achieved
- [ ] Documentation updated and accurate

### Performance Requirements
- [ ] Processing time comparable to current system
- [ ] Memory usage within acceptable limits
- [ ] Database operations efficient

## Conclusion

This implementation plan provides a comprehensive roadmap for transforming the [`generate_barcode_labels.py`](../generate_barcode_labels.py) script according to the detailed requirements. The phased approach minimizes risk while ensuring all critical functionality is preserved and enhanced.

The plan emphasizes:
- **Laboratory Safety**: Maintaining FATAL ERROR standards
- **Test-Driven Development**: Comprehensive test coverage
- **Backward Compatibility**: Smooth transition from existing system
- **Modular Implementation**: Phased approach for risk management

Ready for handoff to Code mode for implementation.