#!/usr/bin/env python3

"""
Laboratory Library Creation Files Generation Script

This script processes sorted microwell plates to generate comprehensive library creation
files including index assignments, FA transfer protocols, and master data tracking
following laboratory automation standards.

USAGE: python generate_lib_creation_files.py

CRITICAL REQUIREMENTS:
- MUST use sip-lims conda environment
- Follows existing SPS script patterns
- Implements comprehensive error handling with "FATAL ERROR" messaging
- Supports both first-run and subsequent-run workflows

Features:
- Automatic detection of run type (first vs subsequent)
- Database-driven plate validation and metadata management
- Custom and standard plate layout processing
- 384-well to 96-well index mapping (PE17, PE18, PE19, PE20)
- Upper left registration detection with specialized index assignment
- FA (Fragment Analyzer) well selection and transfer file generation
- Illumina index transfer file creation
- Master library dataframe with comprehensive well tracking
- Timestamped file archiving and organized folder management
- Duplicate plate prevention for data integrity

Input File Organization (2_library_creation/ folder):
- library_sort_plates.txt: List of plates to process
- {plate_name}.csv: Individual plate layout files (custom plates required, standard plates optional)
- standard_sort_layout.csv: Template for standard plates without individual layouts

Output File Organization (2_library_creation/ folder):
- Illumina_index_transfer_files/: Index primer transfer protocols
- FA_transfer_files/: Fragment Analyzer transfer protocols
- FA_upload_files/: Fragment Analyzer upload manifests
- previously_processed_files/: Organized archive of processed input files

Database Schema (Three-Table Architecture):
- sample_metadata table: Project and sample information
- individual_plates table: Individual plate data with barcodes
- master_plate_data table: Comprehensive well-level data with index and FA assignments
- Database file: project_summary.db (working directory)

Index Assignment System:
- Full plates: 384-well plates mapped to four 96-well index sets (PE17, PE18, PE19, PE20)
- Upper left registration: Random cyclic assignment of single index set per plate
- Odd/even row and column pattern mapping for systematic coverage
- Index names with zero-padded format (e.g., PE17_A01, PE18_B12)
- Unused and ladder wells excluded from index assignments

FA Well Selection Logic:
- Column-wise selection prioritizing sample and control wells
- 96-well FA plate format with systematic well assignment
- Ladder wells automatically assigned to H12 position
- Smart column filtering to exclude unused-only columns

File Management:
- Input files moved to previously_processed_files/ with timestamps
- Plate layout files preserved without timestamp modification
- Database and master files archived before updates
- Comprehensive error logging and validation

Safety Features:
- Laboratory-grade error messaging with "FATAL ERROR" prefix
- Comprehensive plate validation against database records
- Duplicate plate detection and prevention
- Automatic file archiving before modifications
- Consistent error handling with sys.exit() (no exit codes)
"""

import pandas as pd
import sys
import shutil
import random
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine

# BarTender file header — matches the format used by initiate_project_folder_and_make_sort_plate_labels.py
BARTENDER_HEADER = '%BTW% /AF="\\\\BARTENDER\\shared\\templates\\ECHO_BCode8.btw" /D="%Trigger File Name%" /PRN="bcode8" /R=3 /P /DD\r\n\r\n%END%\r\n\r\n\r\n'

# === WORKFLOW SNAPSHOT ITEMS ===
# Files and folders this script modifies, deletes, or replaces.
# The workflow manager reads this list before running the script to create
# a pre-run backup. Keep this list accurate — an incomplete list means
# incomplete rollback capability.
SNAPSHOT_ITEMS = [
    "project_summary.db",
    "master_plate_data.csv",
    "individual_plates.csv",
    "2_library_creation/",
    "3_FA_analysis/thresholds.txt",
]
# === END WORKFLOW SNAPSHOT ITEMS ===


def create_success_marker():
    """Create success marker file for workflow manager integration."""
    script_name = Path(__file__).stem
    status_dir = Path(".workflow_status")
    status_dir.mkdir(exist_ok=True)
    success_file = status_dir / f"{script_name}.success"

    try:
        with open(success_file, "w") as f:
            f.write(f"SUCCESS: {script_name} completed at {datetime.now()}\n")
        print(f"✅ Success marker created: {success_file}")
    except Exception as e:
        print(f"FATAL ERROR: Could not create success marker: {e}")
        print("Laboratory automation requires workflow integration for safety.")
        sys.exit()


def read_database_tables():
    """
    Read the project_summary.db database and create DataFrames from the two tables.
    
    Returns:
        tuple: (sample_metadata_df, individual_plates_df) - Two DataFrames from the database tables
        
    Raises:
        SystemExit: If database file not found or tables not found
    """
    db_path = Path("project_summary.db")
    
    # Check if database file exists
    if not db_path.exists():
        print(f"FATAL ERROR: Database file 'project_summary.db' not found in working directory")
        print("Script requires existing database file to proceed.")
        sys.exit()
    
    try:
        # Create SQLAlchemy engine
        engine = create_engine(f'sqlite:///{db_path}')
        
        # Read sample_metadata table
        try:
            sample_metadata_df = pd.read_sql('SELECT * FROM sample_metadata', engine)
            # Database read successful - no output needed
        except Exception as e:
            print(f"FATAL ERROR: Could not read 'sample_metadata' table: {e}")
            print("Database must contain 'sample_metadata' table.")
            engine.dispose()
            sys.exit()
        
        # Read individual_plates table
        try:
            individual_plates_df = pd.read_sql('SELECT * FROM individual_plates', engine)
            # Database read successful - no output needed
        except Exception as e:
            print(f"FATAL ERROR: Could not read 'individual_plates' table: {e}")
            print("Database must contain 'individual_plates' table.")
            engine.dispose()
            sys.exit()
        
        # Properly dispose of engine
        engine.dispose()
        
        return sample_metadata_df, individual_plates_df
        
    except Exception as e:
        print(f"FATAL ERROR: Could not connect to database {db_path}: {e}")
        print("Database file may be corrupted or inaccessible.")
        sys.exit()


def read_library_sort_plates():
    """
    Read the library_sort_plates.txt file and return a list of plate names.
    
    Returns:
        list: List of plate names from the file
        
    Raises:
        SystemExit: If file not found or incorrectly formatted
    """
    file_path = Path("2_library_creation/library_sort_plates.txt")
    
    # Check if file exists
    if not file_path.exists():
        print(f"FATAL ERROR: File 'library_sort_plates.txt' not found in 2_library_creation folder")
        print("Script requires library_sort_plates.txt file in 2_library_creation/ to proceed.")
        sys.exit()
    
    try:
        # Read file and process lines
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        plate_list = []
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Basic validation - check if line looks like a plate name
            # Expected format: PROJECT_SAMPLE.NUMBER or CUSTOM_NAME.NUMBER
            if '.' not in line:
                print(f"FATAL ERROR: Invalid plate name format on line {line_num}: '{line}'")
                print("Expected format: 'PROJECT_SAMPLE.NUMBER' (e.g., 'BP9735_SitukAM.1')")
                sys.exit()
            
            # Additional validation - check for reasonable length
            if len(line) > 50:
                print(f"FATAL ERROR: Plate name too long on line {line_num}: '{line}'")
                print("Plate names should be less than 50 characters.")
                sys.exit()
            
            plate_list.append(line)
        
        # Check if we found any plates
        if not plate_list:
            print(f"FATAL ERROR: No valid plate names found in 'library_sort_plates.txt'")
            print("File must contain at least one plate name.")
            sys.exit()
        
        # Read successful - no output needed
        return plate_list
        
    except Exception as e:
        print(f"FATAL ERROR: Could not read file 'library_sort_plates.txt': {e}")
        print("File may be corrupted or inaccessible.")
        sys.exit()


def validate_plates_in_database(plate_list, individual_plates_df):
    """
    Validate that all plates in the list exist in the database.
    
    Args:
        plate_list (list): List of plate names from library_sort_plates.txt
        individual_plates_df (pd.DataFrame): DataFrame from individual_plates table
        
    Raises:
        SystemExit: If any plates are missing from the database
    """
    # Get list of plate names from database
    db_plate_names = set(individual_plates_df['plate_name'].tolist())
    
    # Check if all plates in list exist in database
    missing_plates = []
    for plate_name in plate_list:
        if plate_name not in db_plate_names:
            missing_plates.append(plate_name)
    
    if missing_plates:
        print(f"FATAL ERROR: The following plates from library_sort_plates.txt are not found in the database:")
        for plate in missing_plates:
            print(f"  - {plate}")
        print("All plates in the list must exist in the individual_plates table.")
        sys.exit()
    
    # Plate validation successful - no output needed


def separate_custom_and_standard_plates(plate_list, individual_plates_df):
    """
    Separate plates into custom and standard based on is_custom column.
    
    Args:
        plate_list (list): List of plate names from library_sort_plates.txt
        individual_plates_df (pd.DataFrame): DataFrame from individual_plates table
        
    Returns:
        tuple: (custom_plates, standard_plates)
               custom_plates: list of custom plate names
               standard_plates: list of standard plate names
    """
    custom_plates = []
    standard_plates = []
    
    for plate_name in plate_list:
        plate_row = individual_plates_df[individual_plates_df['plate_name'] == plate_name]
        if not plate_row.empty:
            is_custom = bool(plate_row['is_custom'].iloc[0])
            if is_custom:
                custom_plates.append(plate_name)
            else:
                standard_plates.append(plate_name)
    
    # Plate separation successful - no output needed
    return custom_plates, standard_plates


def validate_custom_plate_layouts(custom_plates):
    """
    Validate and load layout CSV files for custom plates.
    
    Args:
        custom_plates (list): List of custom plate names
        
    Returns:
        dict: Mapping of custom plate names to their layout DataFrames
        
    Raises:
        SystemExit: If layout files are missing or invalid
    """
    # Expected column headers for custom plate layout CSV files
    expected_layout_headers = [
        'Plate_ID', 'Well_Row', 'Well_Col', 'Well', 'Sample', 'Type',
        'number_of_cells/capsules', 'Group_1', 'Group_2', 'Group_3'
    ]
    
    custom_layout_data = {}
    
    for custom_plate in custom_plates:
        csv_filename = f"{custom_plate}.csv"
        csv_path = Path(f"2_library_creation/{csv_filename}")
        
        # Check if layout CSV file exists
        if not csv_path.exists():
            print(f"FATAL ERROR: Layout file '{csv_filename}' not found for custom plate '{custom_plate}'")
            print("Custom plates require corresponding CSV layout files in the 2_library_creation/ folder.")
            sys.exit()
        
        try:
            # Read and validate the layout CSV file
            layout_df = pd.read_csv(csv_path, encoding='utf-8-sig')
            
            # Check for required column headers
            missing_headers = []
            for header in expected_layout_headers:
                if header not in layout_df.columns:
                    missing_headers.append(header)
            
            if missing_headers:
                print(f"FATAL ERROR: Layout file '{csv_filename}' missing required column headers:")
                for header in missing_headers:
                    print(f"  - {header}")
                print(f"Required headers: {expected_layout_headers}")
                sys.exit()
            
            # Validate that Plate_ID column contains the expected plate name
            plate_ids = layout_df['Plate_ID'].unique()
            if len(plate_ids) != 1 or plate_ids[0] != custom_plate:
                print(f"FATAL ERROR: Layout file '{csv_filename}' has incorrect Plate_ID values")
                print(f"Expected Plate_ID: '{custom_plate}'")
                print(f"Found Plate_ID values: {list(plate_ids)}")
                sys.exit()
            
            custom_layout_data[custom_plate] = layout_df
            # Validation successful - no detailed output needed
            
        except Exception as e:
            print(f"FATAL ERROR: Could not read or validate layout file '{csv_filename}': {e}")
            print("Layout files must be valid CSV format with correct headers.")
            sys.exit()
    
    return custom_layout_data


def find_individual_standard_plate_files(standard_plates):
    """
    Look for individual CSV layout files for standard plates.
    
    Args:
        standard_plates (list): List of standard plate names
        
    Returns:
        tuple: (plates_with_files, plates_needing_template, individual_layouts)
               plates_with_files: list of plates that have individual CSV files
               plates_needing_template: list of plates that need template
               individual_layouts: dict of plate_name -> DataFrame for found files
    """
    # Expected column headers for layout CSV files
    expected_layout_headers = [
        'Plate_ID', 'Well_Row', 'Well_Col', 'Well', 'Sample', 'Type',
        'number_of_cells/capsules', 'Group_1', 'Group_2', 'Group_3'
    ]
    
    individual_layouts = {}
    plates_with_files = []
    plates_needing_template = []
    
    for standard_plate in standard_plates:
        csv_filename = f"{standard_plate}.csv"
        csv_path = Path(f"2_library_creation/{csv_filename}")
        
        if csv_path.exists():
            try:
                # Read and validate the layout CSV file (same as custom plates)
                layout_df = pd.read_csv(csv_path, encoding='utf-8-sig')
                
                # Check for required column headers
                missing_headers = []
                for header in expected_layout_headers:
                    if header not in layout_df.columns:
                        missing_headers.append(header)
                
                if missing_headers:
                    print(f"FATAL ERROR: Layout file '{csv_filename}' missing required column headers:")
                    for header in missing_headers:
                        print(f"  - {header}")
                    print(f"Required headers: {expected_layout_headers}")
                    sys.exit()
                
                # Validate that Plate_ID column contains the expected plate name
                plate_ids = layout_df['Plate_ID'].unique()
                if len(plate_ids) != 1 or plate_ids[0] != standard_plate:
                    print(f"FATAL ERROR: Layout file '{csv_filename}' has incorrect Plate_ID values")
                    print(f"Expected Plate_ID: '{standard_plate}'")
                    print(f"Found Plate_ID values: {list(plate_ids)}")
                    sys.exit()
                
                individual_layouts[standard_plate] = layout_df
                plates_with_files.append(standard_plate)
                # Found individual file - no detailed output needed
                
            except Exception as e:
                print(f"FATAL ERROR: Could not read or validate layout file '{csv_filename}': {e}")
                print("Layout files must be valid CSV format with correct headers.")
                sys.exit()
        else:
            plates_needing_template.append(standard_plate)
    
    return plates_with_files, plates_needing_template, individual_layouts


def load_standard_template():
    """
    Load and validate the standard plate layout template.
    First looks in 2_library_creation/, then in the script directory.
    
    Returns:
        pd.DataFrame: Standard template DataFrame
        
    Raises:
        SystemExit: If template file is missing or invalid
    """
    # Expected column headers for layout CSV files
    expected_layout_headers = [
        'Plate_ID', 'Well_Row', 'Well_Col', 'Well', 'Sample', 'Type',
        'number_of_cells/capsules', 'Group_1', 'Group_2', 'Group_3'
    ]
    
    # First try the current location (2_library_creation/)
    template_path = Path("2_library_creation/standard_sort_layout.csv")
    
    if not template_path.exists():
        # If not found, try the script directory
        script_dir = Path(__file__).parent
        template_path = script_dir / "standard_sort_layout.csv"
        
        if not template_path.exists():
            print(f"FATAL ERROR: Standard template file 'standard_sort_layout.csv' not found")
            print("Searched in:")
            print("  - 2_library_creation/standard_sort_layout.csv")
            print(f"  - {template_path}")
            print("Template file is required when individual plate layout files are not available.")
            sys.exit()
        else:
            # Template found in script directory - no output needed
            pass
    else:
        # Template found in 2_library_creation - no output needed
        pass
    
    try:
        template_df = pd.read_csv(template_path, encoding='utf-8-sig')
        
        # Validate template headers
        missing_headers = []
        for header in expected_layout_headers:
            if header not in template_df.columns:
                missing_headers.append(header)
        
        if missing_headers:
            print(f"FATAL ERROR: Template file 'standard_sort_layout.csv' missing required column headers:")
            for header in missing_headers:
                print(f"  - {header}")
            print(f"Required headers: {expected_layout_headers}")
            sys.exit()
        
        # Template loaded successfully - no output needed
        return template_df
        
    except Exception as e:
        print(f"FATAL ERROR: Could not read standard template file 'standard_sort_layout.csv': {e}")
        print("Template file must be valid CSV format with correct headers.")
        sys.exit()


def apply_template_to_plates(plates_needing_template, template_df, individual_plates_df):
    """
    Apply standard template to plates that need it.
    
    Args:
        plates_needing_template (list): List of plates that need template
        template_df (pd.DataFrame): Standard template DataFrame
        individual_plates_df (pd.DataFrame): Database plate information
        
    Returns:
        dict: Mapping of plate names to their layout DataFrames
    """
    template_layouts = {}
    
    for standard_plate in plates_needing_template:
        # Get sample name for this plate from database
        plate_row = individual_plates_df[individual_plates_df['plate_name'] == standard_plate]
        if plate_row.empty:
            print(f"FATAL ERROR: Could not find plate '{standard_plate}' in database")
            sys.exit()
        
        proposal = plate_row['project'].iloc[0]
        sample = plate_row['sample'].iloc[0]
        
        # Create a copy of the template for this plate
        plate_layout = template_df.copy()
        
        # Fill in the Plate_ID column with actual plate name
        plate_layout['Plate_ID'] = standard_plate
        
        # Fill in the Sample column with actual sample name for sample wells
        # (Keep other well types like pos_cntrl, neg_cntrl, unused, ladder as they are)
        # Convert Sample column to object dtype to avoid FutureWarning when assigning strings
        plate_layout['Sample'] = plate_layout['Sample'].astype('object')
        sample_mask = plate_layout['Type'] == 'sample'
        plate_layout.loc[sample_mask, 'Sample'] = sample
        
        template_layouts[standard_plate] = plate_layout
        # Template applied successfully - no output needed
    
    return template_layouts


def process_standard_plate_layouts(standard_plates, individual_plates_df, sample_metadata_df):
    """
    Process standard plates by looking for individual CSV files or using standard template.
    
    Args:
        standard_plates (list): List of standard plate names
        individual_plates_df (pd.DataFrame): DataFrame from individual_plates table
        sample_metadata_df (pd.DataFrame): DataFrame from sample_metadata table
        
    Returns:
        dict: Mapping of standard plate names to their layout DataFrames
    """
    # First approach: Look for individual CSV files
    plates_with_files, plates_needing_template, individual_layouts = find_individual_standard_plate_files(standard_plates)
    
    # Second approach: Use standard template for remaining plates
    template_layouts = {}
    if plates_needing_template:
        # Standard plate processing - no detailed output needed
        template_df = load_standard_template()
        template_layouts = apply_template_to_plates(plates_needing_template, template_df, individual_plates_df)
    
    # Combine both approaches
    all_standard_layouts = {**individual_layouts, **template_layouts}
    return all_standard_layouts


def create_index_mapping_dictionaries():
    """
    Create mapping dictionaries for 384-well to 96-well index plate assignments.
    
    Returns:
        dict: Mapping of 384-well position to (index_set, index_well) tuple
    """
    mapping = {}
    
    # Generate all 96-well positions (A1-H12)
    index_wells_96 = []
    for row in 'ABCDEFGH':
        for col in range(1, 13):
            index_wells_96.append(f"{row}{col}")
    
    # PE17: Odd rows (A,C,E,G,I,K,M,O) + Odd columns (1,3,5,7,9,11,13,15,17,19,21,23)
    pe17_wells = []
    for row_idx, row in enumerate(['A','C','E','G','I','K','M','O']):  # 8 odd rows
        for col_idx, col in enumerate([1,3,5,7,9,11,13,15,17,19,21,23]):  # 12 odd columns
            pe17_wells.append(f"{row}{col}")
    
    # PE18: Even rows (B,D,F,H,J,L,N,P) + Odd columns (1,3,5,7,9,11,13,15,17,19,21,23)
    pe18_wells = []
    for row_idx, row in enumerate(['B','D','F','H','J','L','N','P']):  # 8 even rows
        for col_idx, col in enumerate([1,3,5,7,9,11,13,15,17,19,21,23]):  # 12 odd columns
            pe18_wells.append(f"{row}{col}")
    
    # PE19: Odd rows (A,C,E,G,I,K,M,O) + Even columns (2,4,6,8,10,12,14,16,18,20,22,24)
    pe19_wells = []
    for row_idx, row in enumerate(['A','C','E','G','I','K','M','O']):  # 8 odd rows
        for col_idx, col in enumerate([2,4,6,8,10,12,14,16,18,20,22,24]):  # 12 even columns
            pe19_wells.append(f"{row}{col}")
    
    # PE20: Even rows (B,D,F,H,J,L,N,P) + Even columns (2,4,6,8,10,12,14,16,18,20,22,24)
    pe20_wells = []
    for row_idx, row in enumerate(['B','D','F','H','J','L','N','P']):  # 8 even rows
        for col_idx, col in enumerate([2,4,6,8,10,12,14,16,18,20,22,24]):  # 12 even columns
            pe20_wells.append(f"{row}{col}")
    
    # Map 384-well positions to (index_set, index_well) tuples
    for i, well_384 in enumerate(pe17_wells):
        mapping[well_384] = ('PE17', index_wells_96[i])
    
    for i, well_384 in enumerate(pe18_wells):
        mapping[well_384] = ('PE18', index_wells_96[i])
    
    for i, well_384 in enumerate(pe19_wells):
        mapping[well_384] = ('PE19', index_wells_96[i])
    
    for i, well_384 in enumerate(pe20_wells):
        mapping[well_384] = ('PE20', index_wells_96[i])
    
    # Index mapping created - no detailed output needed
    return mapping


def create_upper_left_index_mapping(assigned_index_set):
    """
    Create mapping dictionary for upper left registration plates.
    Maps all 96 active wells (odd rows × odd columns) to a single index set.
    
    Args:
        assigned_index_set (str): The index set to assign (PE17, PE18, PE19, or PE20)
        
    Returns:
        dict: Mapping of 384-well position to (index_set, index_well) tuple
    """
    mapping = {}
    
    # Generate all 96-well positions (A1-H12) - same as current logic
    index_wells_96 = []
    for row in 'ABCDEFGH':
        for col in range(1, 13):
            index_wells_96.append(f"{row}{col}")
    
    # Upper left registration uses only odd rows and odd columns
    # This matches the PE17 pattern from the original logic
    upper_left_wells = []
    for row_idx, row in enumerate(['A','C','E','G','I','K','M','O']):  # 8 odd rows
        for col_idx, col in enumerate([1,3,5,7,9,11,13,15,17,19,21,23]):  # 12 odd columns
            upper_left_wells.append(f"{row}{col}")
    
    # Map all 96 upper left wells to the assigned index set
    for i, well_384 in enumerate(upper_left_wells):
        mapping[well_384] = (assigned_index_set, index_wells_96[i])
    
    return mapping


def assign_upper_left_index_sets(upper_left_plates):
    """
    Assign index sets to upper left registration plates using random cyclic assignment.
    
    Args:
        upper_left_plates (list): List of upper left plate names
        
    Returns:
        dict: Mapping of plate_name -> assigned_index_set
    """
    if not upper_left_plates:
        return {}
    
    # Available index sets
    index_sets = ['PE17', 'PE18', 'PE19', 'PE20']
    
    # Randomly select starting index set
    start_index = random.randint(0, len(index_sets) - 1)
    # Upper left registration assignments - no detailed output needed
    
    # Assign index sets cyclically
    plate_assignments = {}
    for i, plate_name in enumerate(upper_left_plates):
        # Calculate cyclic index
        current_index = (start_index + i) % len(index_sets)
        assigned_set = index_sets[current_index]
        plate_assignments[plate_name] = assigned_set
        # Index assignment successful - no output needed
    
    return plate_assignments


def add_index_columns_to_plates(all_plate_layouts):
    """
    Add index assignment columns to all plate layout DataFrames.
    Uses different strategies for upper left registration vs full plates.
    
    Args:
        all_plate_layouts (dict): Dictionary of plate_name -> DataFrame
        
    Returns:
        tuple: (updated_layouts_dict, layout_detection_results_dict)
               updated_layouts_dict: Updated dictionary with index columns added to each DataFrame
               layout_detection_results_dict: Dictionary of plate_name -> is_upper_left_bool
    """
    updated_layouts = {}
    layout_detection_results = {}
    
    # Step 1: Detect plate types and separate them
    upper_left_plates = []
    full_plates = []
    
    for plate_name, plate_df in all_plate_layouts.items():
        is_upper_left = detect_upper_left_registration(plate_df)
        layout_detection_results[plate_name] = is_upper_left
        if is_upper_left:
            upper_left_plates.append(plate_name)
        else:
            full_plates.append(plate_name)
    
    # Plate type detection successful - no output needed
    
    # Step 2: Assign index sets to upper left plates
    upper_left_assignments = assign_upper_left_index_sets(upper_left_plates)
    
    # Step 3: Create mapping for full plates (original logic)
    full_plate_mapping = create_index_mapping_dictionaries() if full_plates else {}
    
    # Step 4: Process each plate with appropriate mapping
    for plate_name, plate_df in all_plate_layouts.items():
        # Create a copy to avoid modifying original
        updated_df = plate_df.copy()
        
        # Initialize new columns
        updated_df['Index_Set'] = ''
        updated_df['Index_Well'] = ''
        updated_df['Index_Name'] = ''
        
        # Determine which mapping to use
        if plate_name in upper_left_assignments:
            # Upper left registration plate
            assigned_index_set = upper_left_assignments[plate_name]
            index_mapping = create_upper_left_index_mapping(assigned_index_set)
        else:
            # Full plate
            index_mapping = full_plate_mapping
        
        # Apply mapping to each well
        for idx, row in updated_df.iterrows():
            well_position = row['Well']
            
            # Look up the index assignment
            if well_position in index_mapping:
                index_set, index_well = index_mapping[well_position]
                
                # Create index name with leading zero for columns < 10
                row_letter = index_well[0]
                col_number = int(index_well[1:])
                if col_number < 10:
                    index_name = f"{index_set}_{row_letter}0{col_number}"
                else:
                    index_name = f"{index_set}_{row_letter}{col_number}"
                
                # Update the DataFrame
                updated_df.at[idx, 'Index_Set'] = index_set
                updated_df.at[idx, 'Index_Well'] = index_well
                updated_df.at[idx, 'Index_Name'] = index_name
        
        updated_layouts[plate_name] = updated_df
        
        # Count assigned indexes for this plate
        assigned_count = len(updated_df[updated_df['Index_Set'] != ''])
        # Index assignments added - no detailed output needed
    
    return updated_layouts, layout_detection_results


# def export_plates_to_csv(all_plate_layouts_with_indexes):
#     """
#     Export each plate DataFrame to a separate CSV file for inspection.
#
#     Args:
#         all_plate_layouts_with_indexes (dict): Dictionary of plate_name -> DataFrame with index columns
#     """
#     for plate_name, plate_df in all_plate_layouts_with_indexes.items():
#         # Use plate name as filename (replace any problematic characters)
#         safe_filename = plate_name.replace('/', '_').replace('\\', '_')
#         csv_filename = f"{safe_filename}.csv"
#
#         # Export to CSV
#         plate_df.to_csv(csv_filename, index=False)
#         print(f"✅ Exported plate '{plate_name}' to '{csv_filename}' ({len(plate_df)} wells)")
#
#     print(f"✅ Exported {len(all_plate_layouts_with_indexes)} plate CSV files")


def create_illumina_index_files(all_plate_layouts_with_indexes, individual_plates_df):
    """
    Create Illumina index transfer files for each plate in a dedicated subfolder.
    
    Args:
        all_plate_layouts_with_indexes (dict): Dictionary of plate_name -> DataFrame with index columns
        individual_plates_df (pd.DataFrame): Database plate information for barcode lookup
    """
    # Create output directory if it doesn't exist
    output_dir = Path("2_library_creation/Illumina_index_transfer_files")
    output_dir.mkdir(exist_ok=True)
    # Output directory created - no output needed
    for plate_name, plate_df in all_plate_layouts_with_indexes.items():
        # Get barcode for this plate from database
        plate_row = individual_plates_df[individual_plates_df['plate_name'] == plate_name]
        if plate_row.empty:
            print(f"FATAL ERROR: Could not find barcode for plate '{plate_name}' in database")
            print("All plates must have valid barcodes in the individual_plates table.")
            sys.exit()
        
        lib_plate_id = plate_row['barcode'].iloc[0]
        
        # Check which index sets have any non-unused/non-ladder wells
        included_index_sets = []
        for index_set in ['PE17', 'PE18', 'PE19', 'PE20']:
            # Get all wells for this index set (should be 96 wells each after our fix)
            index_wells = plate_df[plate_df['Index_Set'] == index_set]
            
            # Check if any wells are NOT unused or ladder
            non_excluded_wells = index_wells[~index_wells['Type'].isin(['unused', 'ladder'])]
            
            if len(non_excluded_wells) > 0:
                included_index_sets.append(index_set)
                # Index set included - no detailed output needed
            else:
                # Index set excluded - no detailed output needed
                pass
        
        if not included_index_sets:
            print(f"FATAL ERROR: No index sets to include for plate '{plate_name}' - all wells are unused/ladder")
            print("Plates must contain at least some sample or control wells for index assignment.")
            sys.exit()
        
        # Create output data for included index sets
        output_rows = []
        for index_set in included_index_sets:
            # Get ALL wells for this index set (including unused/ladder)
            index_wells = plate_df[plate_df['Index_Set'] == index_set].copy()
            
            for _, row in index_wells.iterrows():
                output_rows.append({
                    'Illumina_index_set': row['Index_Set'],
                    'Illumina_source_well': row['Index_Well'],
                    'Lib_plate_name': row['Plate_ID'],
                    'Lib_plate_ID': lib_plate_id,
                    'Lib_plate_well': row['Well'],
                    'Primer_volume_(uL)': 2
                })
        
        # Create output DataFrame and save to CSV
        if output_rows:
            output_df = pd.DataFrame(output_rows)
            
            # Extract column and row from Lib_plate_well for sorting
            output_df['sort_col'] = output_df['Lib_plate_well'].str.extract(r'([A-P])(\d+)')[1].astype(int)
            output_df['sort_row'] = output_df['Lib_plate_well'].str.extract(r'([A-P])(\d+)')[0]
            
            # Sort by index set first, then by sort plate column, then by sort plate row
            output_df = output_df.sort_values(['Illumina_index_set', 'sort_col', 'sort_row'])
            
            # Remove the temporary sorting columns
            output_df = output_df.drop(['sort_col', 'sort_row'], axis=1)
            
            # Create filename in subfolder
            safe_filename = plate_name.replace('/', '_').replace('\\', '_')
            csv_filename = output_dir / f"Illumina_index_{safe_filename}.csv"
            
            # Export to CSV
            output_df.to_csv(csv_filename, index=False)
            # Illumina index file created - no detailed output needed
        
    # Illumina index file generation completed - no output needed


def detect_upper_left_registration(plate_df):
    """
    Detect if a plate uses upper left registration pattern:
    - All even rows (B,D,F,H,J,L,N,P) contain only 'unused' wells
    - All even columns (2,4,6,8,10,12,14,16,18,20,22,24) contain only 'unused' wells
    - This creates a 96-well pattern using only odd rows and odd columns
    
    Args:
        plate_df (pd.DataFrame): Plate layout DataFrame
        
    Returns:
        bool: True if upper left registration pattern detected, False otherwise
    """
    # Check even rows (B,D,F,H,J,L,N,P)
    even_rows = ['B', 'D', 'F', 'H', 'J', 'L', 'N', 'P']
    for row in even_rows:
        row_wells = plate_df[plate_df['Well_Row'] == row]
        if not row_wells.empty:
            # Check if all wells in this even row are 'unused'
            non_unused_wells = row_wells[row_wells['Type'] != 'unused']
            if not non_unused_wells.empty:
                # Found non-unused wells in even row - not upper left registration
                return False
    
    # Check even columns (2,4,6,8,10,12,14,16,18,20,22,24)
    even_cols = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24]
    for col in even_cols:
        col_wells = plate_df[plate_df['Well_Col'] == col]
        if not col_wells.empty:
            # Check if all wells in this even column are 'unused'
            non_unused_wells = col_wells[col_wells['Type'] != 'unused']
            if not non_unused_wells.empty:
                # Found non-unused wells in even column - not upper left registration
                return False
    
    # All even rows and even columns contain only 'unused' wells
    # Upper left registration pattern detected - no output needed
    return True


def select_wells_for_fa_transfer_upper_left(plate_df):
    """
    Select wells for FA transfer using upper left registration pattern:
    - Direct 1:1 mapping from source to FA plate
    - Only select wells from odd rows and odd columns that are not 'unused' or 'ladder'
    - Maintain original well positions (A1 -> A1, C5 -> C5, etc.)
    
    Args:
        plate_df (pd.DataFrame): Plate layout DataFrame
        
    Returns:
        pd.DataFrame: Selected wells for FA transfer with direct mapping
    """
    # Get wells from odd rows and odd columns only
    odd_rows = ['A', 'C', 'E', 'G', 'I', 'K', 'M', 'O']
    odd_cols = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23]
    
    # Filter to odd rows and odd columns
    valid_wells = plate_df[
        (plate_df['Well_Row'].isin(odd_rows)) &
        (plate_df['Well_Col'].isin(odd_cols))
    ].copy()
    
    # Exclude 'unused' and 'ladder' wells
    selected_wells = valid_wells[~valid_wells['Type'].isin(['unused', 'ladder'])].copy()
    
    if selected_wells.empty:
        print(f"FATAL ERROR: No valid wells found for FA transfer in upper left registration")
        print("Upper left registration plates must contain at least some sample or control wells.")
        sys.exit()
    
    # Sort by row then column for consistent ordering
    selected_wells = selected_wells.sort_values(['Well_Row', 'Well_Col'])
    
    # Upper left registration wells selected - no output needed
    return selected_wells


def select_wells_for_fa_transfer_full_plate(plate_df):
    """
    Select wells from a 384-well plate for FA transfer using full plate logic:
    - Exclude columns containing only 'unused' or 'ladder' wells
    - Number remaining wells column-wise until reaching the last pos_cntrl well
    - If ≤92 wells total: select all
    - If >92 wells total: select first 48 + last 44 wells
    - Last selected well must be pos_cntrl type
    
    Args:
        plate_df (pd.DataFrame): Plate layout DataFrame
        
    Returns:
        pd.DataFrame: Selected wells for FA transfer
    """
    # Step 1: Identify valid columns (exclude columns with only unused/ladder wells)
    valid_columns = []
    
    for col in range(1, 25):  # Columns 1-24
        col_wells = plate_df[plate_df['Well_Col'] == col]
        # Check if column has any wells that are NOT unused or ladder
        non_excluded_wells = col_wells[~col_wells['Type'].isin(['unused', 'ladder'])]
        
        if len(non_excluded_wells) > 0:
            # Column has samples/controls - include it
            valid_columns.append(col)
    
    if not valid_columns:
        print(f"FATAL ERROR: No valid columns found for FA transfer")
        print("Full plates must contain at least some columns with sample or control wells.")
        sys.exit()
    
    # Step 2: Get wells from valid columns only and sort column-wise
    valid_wells = plate_df[plate_df['Well_Col'].isin(valid_columns)].copy()
    valid_wells = valid_wells.sort_values(['Well_Col', 'Well_Row'])
    valid_wells['sequential_number'] = range(1, len(valid_wells) + 1)
    
    # Step 3: Find the last pos_cntrl well
    pos_cntrl_wells = valid_wells[valid_wells['Type'] == 'pos_cntrl']
    if pos_cntrl_wells.empty:
        print(f"FATAL ERROR: No pos_cntrl wells found for FA transfer")
        print("Full plates must contain at least one positive control well for proper FA transfer.")
        sys.exit()
    
    # Get the sequential number of the last pos_cntrl well
    last_pos_cntrl_number = pos_cntrl_wells['sequential_number'].max()
    
    # Step 4: Get all wells up to and including the last pos_cntrl well
    wells_up_to_last_pos_cntrl = valid_wells[valid_wells['sequential_number'] <= last_pos_cntrl_number].copy()
    
    # Step 5: Apply selection logic
    total_wells = len(wells_up_to_last_pos_cntrl)
    
    if total_wells <= 92:
        # Select all wells
        selected_wells = wells_up_to_last_pos_cntrl
        # Full plate wells selected - no output needed
    else:
        # Select first 48 + last 44 wells
        first_48 = wells_up_to_last_pos_cntrl.head(48)
        last_44 = wells_up_to_last_pos_cntrl.tail(44)
        selected_wells = pd.concat([first_48, last_44])
        # Full plate wells selected - no output needed
    
    # Step 6: Verify the last selected well is pos_cntrl
    if not selected_wells.empty:
        last_selected_well = selected_wells.iloc[-1]
        if last_selected_well['Type'] != 'pos_cntrl':
            print(f"FATAL ERROR: Last selected well is not pos_cntrl type: {last_selected_well['Type']}")
            print("FA transfer selection logic requires the last selected well to be a positive control.")
            sys.exit()
    
    return selected_wells.drop('sequential_number', axis=1, errors='ignore')


def select_wells_for_fa_transfer(plate_df):
    """
    Select wells from a 384-well plate for FA transfer using automatic pattern detection:
    - Detects upper left registration vs full plate usage
    - Uses appropriate selection logic for each pattern
    
    Args:
        plate_df (pd.DataFrame): Plate layout DataFrame
        
    Returns:
        pd.DataFrame: Selected wells for FA transfer
    """
    # Detect which pattern we're dealing with
    is_upper_left = detect_upper_left_registration(plate_df)
    
    if is_upper_left:
        return select_wells_for_fa_transfer_upper_left(plate_df)
    else:
        return select_wells_for_fa_transfer_full_plate(plate_df)


def assign_fa_wells_upper_left(selected_wells_df):
    """
    Assign FA well positions for upper left registration pattern:
    - Maps from 384-well odd positions to 96-well standard layout
    - A1→A1, C1→B1, E1→C1, G1→D1, I1→E1, K1→F1, M1→G1, O1→H1
    - A3→A2, C3→B2, E3→C2, G3→D2, I3→E2, K3→F2, M3→G2, O3→H2
    - And so on...
    
    Args:
        selected_wells_df (pd.DataFrame): Selected wells DataFrame
        
    Returns:
        pd.DataFrame: DataFrame with FA_Well column added (compressed mapping)
    """
    result_df = selected_wells_df.copy()
    
    # Sort by column first, then row to ensure proper sequential mapping
    result_df = result_df.sort_values(['Well_Col', 'Well_Row'])
    
    # Create mapping from 384-well odd positions to 96-well positions
    # 384-well odd rows: A,C,E,G,I,K,M,O (8 rows)
    # 384-well odd cols: 1,3,5,7,9,11,13,15,17,19,21,23 (12 columns)
    # 96-well layout: A-H (8 rows) × 1-12 (12 columns)
    
    source_row_mapping = {'A': 0, 'C': 1, 'E': 2, 'G': 3, 'I': 4, 'K': 5, 'M': 6, 'O': 7}
    source_col_mapping = {1: 0, 3: 1, 5: 2, 7: 3, 9: 4, 11: 5, 13: 6, 15: 7, 17: 8, 19: 9, 21: 10, 23: 11}
    
    dest_rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    
    # Initialize FA_Well column
    result_df['FA_Well'] = ''
    
    # Assign FA wells based on compressed mapping
    for idx, row in result_df.iterrows():
        source_row = row['Well_Row']
        source_col = row['Well_Col']
        
        # Map source position to destination position
        if source_row in source_row_mapping and source_col in source_col_mapping:
            dest_row_idx = source_row_mapping[source_row]
            dest_col_idx = source_col_mapping[source_col]
            
            dest_row = dest_rows[dest_row_idx]
            dest_col = dest_col_idx + 1  # Convert 0-based to 1-based
            
            fa_well = f"{dest_row}{dest_col}"
            result_df.at[idx, 'FA_Well'] = fa_well
        else:
            print(f"FATAL ERROR: Unexpected well position {row['Well']} in upper left registration")
            print("Upper left registration plates should only contain wells in odd rows and odd columns.")
            sys.exit()
    
    # Upper left registration FA mapping completed - no output needed
    return result_df


def assign_fa_wells_full_plate(selected_wells_df):
    """
    Assign FA well positions to selected wells using 92-position layout:
    - Columns 1-11: All rows (A-H) = 88 positions
    - Column 12: Only rows A-D = 4 positions
    - Total: 92 positions for real samples
    
    Args:
        selected_wells_df (pd.DataFrame): Selected wells DataFrame
        
    Returns:
        pd.DataFrame: DataFrame with FA_Well column added
    """
    # Create a copy for sorting
    sorted_df = selected_wells_df.copy()
    
    # Create sorting helper columns
    # Map row letters to numbers for odd/even sorting
    row_mapping = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7, 'H': 8,
                   'I': 9, 'J': 10, 'K': 11, 'L': 12, 'M': 13, 'N': 14, 'O': 15, 'P': 16}
    
    sorted_df['row_number'] = sorted_df['Well_Row'].map(row_mapping)
    sorted_df['is_odd_row'] = sorted_df['row_number'] % 2 == 1  # True for odd rows (A,C,E,G,I,K,M,O), False for even rows (B,D,F,H,J,L,N,P)
    
    # Sort by: plate name, then column, then odd rows first (True before False), then row number
    sorted_df = sorted_df.sort_values(['Plate_ID', 'Well_Col', 'is_odd_row', 'row_number'], ascending=[True, True, False, True])
    
    # Remove helper columns
    sorted_df = sorted_df.drop(['row_number', 'is_odd_row'], axis=1)
    
    # Generate 92 FA well positions using new layout
    fa_wells = []
    rows = 'ABCDEFGH'
    
    # Columns 1-11: All rows (A1-H1, A2-H2, ..., A11-H11)
    for col in range(1, 12):  # Columns 1-11
        for row in rows:  # Rows A-H
            fa_wells.append(f"{row}{col}")
    
    # Column 12: Only rows A-D (A12, B12, C12, D12)
    for row in 'ABCD':  # Only rows A-D
        fa_wells.append(f"{row}12")
    
    # Initialize FA_Well column
    sorted_df['FA_Well'] = ''
    
    # Assign FA wells to all selected wells sequentially
    fa_index = 0
    
    for idx in sorted_df.index:
        if fa_index < len(fa_wells):
            sorted_df.at[idx, 'FA_Well'] = fa_wells[fa_index]
            fa_index += 1
        else:
            # Should not happen if selection logic is correct (max 92 wells)
            print(f"FATAL ERROR: More wells selected than FA positions available")
            print("FA well assignment logic error - too many wells selected for 92-position layout.")
            sys.exit()
    
    # Full plate FA assignment completed - no output needed
    return sorted_df


def assign_fa_wells(selected_wells_df):
    """
    Assign FA well positions using automatic pattern detection:
    - For upper left registration: direct 1:1 mapping
    - For full plate: complex 92-position layout mapping
    
    Args:
        selected_wells_df (pd.DataFrame): Selected wells DataFrame
        
    Returns:
        pd.DataFrame: DataFrame with FA_Well column added
    """
    if selected_wells_df.empty:
        return selected_wells_df
    
    # Detect pattern by checking if we have upper left registration
    # Upper left registration uses only odd rows and odd columns
    odd_rows = ['A', 'C', 'E', 'G', 'I', 'K', 'M', 'O']
    odd_cols = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23]
    
    # Check if all selected wells are from odd rows and odd columns
    all_odd_rows = selected_wells_df['Well_Row'].isin(odd_rows).all()
    all_odd_cols = selected_wells_df['Well_Col'].isin(odd_cols).all()
    
    if all_odd_rows and all_odd_cols:
        # Upper left registration pattern
        return assign_fa_wells_upper_left(selected_wells_df)
    else:
        # Full plate pattern
        return assign_fa_wells_full_plate(selected_wells_df)


def create_fa_transfer_files(fa_well_assignments, individual_plates_df):
    """
    Create FA transfer files for each plate using pre-computed FA well assignments.
    
    Args:
        fa_well_assignments (dict): Dictionary of plate_name -> DataFrame with FA well assignments
        individual_plates_df (pd.DataFrame): Database plate information for barcode lookup
    """
    # Create output directory if it doesn't exist
    output_dir = Path("2_library_creation/FA_transfer_files")
    output_dir.mkdir(exist_ok=True)
    # Directory created - no output needed
    
    for plate_name, fa_wells_df in fa_well_assignments.items():
        # Processing FA transfer - no detailed output needed
        
        # Skip plates with no FA well assignments
        if fa_wells_df.empty:
            print(f"FATAL ERROR: No wells selected for FA transfer for plate '{plate_name}'")
            print("All plates must have at least some wells selected for FA transfer.")
            sys.exit()
        
        # Get barcode for this plate from database
        plate_row = individual_plates_df[individual_plates_df['plate_name'] == plate_name]
        if plate_row.empty:
            print(f"FATAL ERROR: Could not find barcode for plate '{plate_name}' in database")
            print("All plates must have valid barcodes in the individual_plates table.")
            sys.exit()
        
        barcode = plate_row['barcode'].iloc[0]
        
        # Step 3: Create output DataFrame with required columns
        output_rows = []
        for _, row in fa_wells_df.iterrows():
            output_rows.append({
                'Library_Plate_Barcode': barcode,
                'Dilution_Plate_Barcode': f"{barcode}D",
                'FA_Plate_Barcode': f"{barcode}F",
                'Library_Well': row['Well'],
                'FA_Well': row['FA_Well'],
                'Nextera_Vol_Add': 30,
                'Dilution_Vol': 2.4,
                'FA_Vol_Add': 2.4,
                'Dilution_Plate_Preload': 10,
                'Total_buffer_aspiration': 40
            })
        
        # Step 4: Create output DataFrame and save to CSV
        if output_rows:
            output_df = pd.DataFrame(output_rows)
            
            # Create filename
            safe_filename = plate_name.replace('/', '_').replace('\\', '_')
            csv_filename = output_dir / f"FA_plate_transfer_{safe_filename}.csv"
            
            # Export to CSV
            output_df.to_csv(csv_filename, index=False)
            # FA transfer file created - no detailed output needed
    
    # FA transfer file generation completed - no output needed


def create_fa_upload_files(fa_well_assignments, individual_plates_df):
    """
    Create FA upload files for each plate with 3 columns: number (1-96), FA_well, sample_name.
    New logic:
    - Wells with source samples: {barcode}_{plate_name}_{well}
    - Wells without source samples: "empty"
    - E12: "LibStd_E12", F12: "LibStd_F12", G12: "LibStd_G12", H12: "ladder_H12"
    
    Args:
        fa_well_assignments (dict): Dictionary of plate_name -> DataFrame with FA well assignments
        individual_plates_df (pd.DataFrame): Database plate information for barcode lookup
    """
    # Create output directory if it doesn't exist
    output_dir = Path("2_library_creation/FA_upload_files")
    output_dir.mkdir(exist_ok=True)
    # Output directory created - no output needed
    
    for plate_name, fa_wells_df in fa_well_assignments.items():
        # Processing FA upload - no detailed output needed
        
        # Get barcode for this plate from database
        plate_row = individual_plates_df[individual_plates_df['plate_name'] == plate_name]
        if plate_row.empty:
            print(f"FATAL ERROR: Could not find barcode for plate '{plate_name}' in database")
            print("All plates must have valid barcodes in the individual_plates table.")
            sys.exit()
        
        barcode = plate_row['barcode'].iloc[0]
        
        # Generate all 96 FA well positions column-wise
        all_fa_wells = []
        rows = 'ABCDEFGH'
        for col in range(1, 13):  # Columns 1-12 in 96-well plate
            for row in rows:  # Rows A-H
                all_fa_wells.append(f"{row}{col}")
        
        # Create mapping of FA wells to source wells (if any)
        fa_well_to_source = {}
        if not fa_wells_df.empty:
            # Sort by FA well position for consistent ordering
            fa_wells_df['fa_row'] = fa_wells_df['FA_Well'].str[0]
            fa_wells_df['fa_col'] = fa_wells_df['FA_Well'].str[1:].astype(int)
            fa_wells_sorted = fa_wells_df.sort_values(['fa_col', 'fa_row'])
            
            for _, row in fa_wells_sorted.iterrows():
                fa_well = row['FA_Well']
                source_well = row['Well']
                fa_well_to_source[fa_well] = f"{barcode}_{plate_name}_{source_well}"
        
        # Create output rows for all 96 FA wells
        output_rows = []
        
        for i, fa_well in enumerate(all_fa_wells, 1):
            # Determine the sample name for this FA well
            if fa_well == 'E12':
                sample_name = "LibStd_E12"
            elif fa_well == 'F12':
                sample_name = "LibStd_F12"
            elif fa_well == 'G12':
                sample_name = "LibStd_G12"
            elif fa_well == 'H12':
                sample_name = "ladder_H12"
            elif fa_well in fa_well_to_source:
                # Has a source well
                sample_name = fa_well_to_source[fa_well]
            else:
                # No source well - empty
                sample_name = "empty"
            
            output_rows.append([i, fa_well, sample_name])
        
        # Create output file (no headers)
        if output_rows:
            # Create filename: FA_upload_{plate_name}_{barcode}.csv
            safe_plate_name = plate_name.replace('/', '_').replace('\\', '_')
            safe_barcode = barcode.replace('/', '_').replace('\\', '_')
            csv_filename = output_dir / f"FA_upload_{safe_plate_name}_{safe_barcode}.csv"
            
            # Write to CSV without headers
            with open(csv_filename, 'w', newline='') as f:
                import csv
                writer = csv.writer(f)
                writer.writerows(output_rows)
            
            # FA upload file created - no detailed output needed
    
    # FA upload file generation completed - no output needed


def generate_thresholds_file(plate_list, individual_plates_df):
    """
    Generate thresholds.txt file for FA analysis plates in the 3_FA_analysis/ folder.
    
    Creates a tab-separated file with plate barcodes and fixed threshold values:
    - Destination_plate: Plate barcodes (without F suffix)
    - DNA_conc_threshold_(nmol/L): Empty (for manual entry)
    - Size_theshold_(bp): Fixed value 530
    - dilution_factor: Fixed value 20
    
    Args:
        plate_list (list): List of plate names being processed
        individual_plates_df (pd.DataFrame): Database plate information for barcode lookup
    """
    # Create output directory if it doesn't exist
    output_dir = Path("3_FA_analysis")
    output_dir.mkdir(exist_ok=True)
    
    # Collect plate barcodes for all processed plates
    plate_barcodes = []
    
    for plate_name in plate_list:
        # Get barcode for this plate from database
        plate_row = individual_plates_df[individual_plates_df['plate_name'] == plate_name]
        if plate_row.empty:
            print(f"FATAL ERROR: Could not find barcode for plate '{plate_name}' in database")
            print("All plates must have valid barcodes in the individual_plates table.")
            sys.exit()
        
        barcode = plate_row['barcode'].iloc[0]
        plate_barcodes.append(barcode)
    
    # Sort plate barcodes for consistent output
    plate_barcodes.sort()
    
    # Create thresholds.txt file
    thresholds_file = output_dir / "thresholds.txt"
    
    try:
        with open(thresholds_file, 'w', newline='', encoding='utf-8') as f:
            # Write header row
            f.write("Destination_plate\tDNA_conc_threshold_(nmol/L)\tSize_theshold_(bp)\tdilution_factor\n")
            
            # Write data rows
            for barcode in plate_barcodes:
                # DNA concentration threshold is left empty, size threshold is 530, dilution factor is 20
                f.write(f"{barcode}\t\t530\t20\n")
        
        # Thresholds file generated successfully - no output needed
        
    except Exception as e:
        print(f"FATAL ERROR: Could not create thresholds.txt file: {e}")
        print("Failed to write thresholds file to 3_FA_analysis/ folder.")
        sys.exit()


def create_master_dataframe(all_plate_layouts_with_indexes, fa_well_assignments, individual_plates_df):
    """
    Concatenate all plate DataFrames and merge with pre-computed FA well information.
    
    Args:
        all_plate_layouts_with_indexes (dict): Dictionary of plate DataFrames with index assignments
        fa_well_assignments (dict): Dictionary of plate_name -> DataFrame with FA well assignments
        individual_plates_df (pd.DataFrame): Individual plates metadata
        
    Returns:
        pd.DataFrame: Master DataFrame with all wells and FA well assignments where applicable
    """
    # Creating master DataFrame - no output needed
    
    # Step 1: Concatenate all plate DataFrames
    all_plate_dfs = []
    
    for plate_name, plate_df in all_plate_layouts_with_indexes.items():
        # Add plate name column to identify source plate
        plate_df_copy = plate_df.copy()
        plate_df_copy['Plate_Name'] = plate_name
        all_plate_dfs.append(plate_df_copy)
    
    # Concatenate all plates vertically
    master_df = pd.concat(all_plate_dfs, ignore_index=True)
    # Master DataFrame created - no detailed output needed
    
    # Step 2: Use pre-computed FA well assignments
    fa_assignments = []
    
    for plate_name, fa_wells_df in fa_well_assignments.items():
        if len(fa_wells_df) > 0:
            # Keep only the columns needed for merging
            fa_merge_df = fa_wells_df[['Plate_ID', 'Well_Row', 'Well_Col', 'Well', 'FA_Well']].copy()
            fa_merge_df['Plate_Name'] = plate_name
            fa_assignments.append(fa_merge_df)
    
    # Step 3: Merge FA well assignments with master DataFrame
    if fa_assignments:
        fa_master_df = pd.concat(fa_assignments, ignore_index=True)
        # FA assignments created - no detailed output needed
        
        # Merge on plate name and well identifiers
        merge_columns = ['Plate_Name', 'Well_Row', 'Well_Col', 'Well']
        
        # Check for merge conflicts before merging
        master_merge_keys = master_df[merge_columns].drop_duplicates()
        fa_merge_keys = fa_master_df[merge_columns].drop_duplicates()
        
        # Verify that all FA wells exist in master DataFrame
        fa_not_in_master = fa_merge_keys.merge(master_merge_keys, on=merge_columns, how='left', indicator=True)
        fa_not_in_master = fa_not_in_master[fa_not_in_master['_merge'] == 'left_only']
        
        if len(fa_not_in_master) > 0:
            print(f"❌ FATAL ERROR: {len(fa_not_in_master)} FA wells not found in master DataFrame")
            print("Conflicting wells:")
            print(fa_not_in_master[merge_columns])
            sys.exit(1)
        
        # Perform the merge
        final_df = master_df.merge(fa_master_df[merge_columns + ['FA_Well']],
                                  on=merge_columns,
                                  how='left')
        
        # Verify merge was successful
        if len(final_df) != len(master_df):
            print(f"❌ FATAL ERROR: Merge changed row count from {len(master_df)} to {len(final_df)}")
            sys.exit(1)
        
        # Check for any unexpected duplicates
        duplicate_check = final_df.groupby(merge_columns).size()
        duplicates = duplicate_check[duplicate_check > 1]
        if len(duplicates) > 0:
            print(f"❌ FATAL ERROR: {len(duplicates)} duplicate wells found after merge")
            print("Duplicate wells:")
            print(duplicates)
            sys.exit(1)
        
        # FA well assignments merged successfully - no detailed output needed
        
        # Prepare DataFrame for sorting and cleaning
        df_to_process = final_df.copy()
        
    else:
        # No FA assignments found - no detailed output needed
        master_df['FA_Well'] = pd.NA
        
        # Prepare DataFrame for sorting and cleaning
        df_to_process = master_df.copy()
    
    # Step 4: Add plate barcodes and sort before cleaning
    # Adding barcodes and sorting - no output needed
    
    # Add plate barcodes for all wells
    for plate_name in df_to_process['Plate_Name'].unique():
        # Get barcode for this plate from database
        plate_row = individual_plates_df[individual_plates_df['plate_name'] == plate_name]
        if plate_row.empty:
            print(f"FATAL ERROR: Could not find barcode for plate '{plate_name}' in database")
            print("All plates must have valid barcodes in the individual_plates table.")
            sys.exit()
        else:
            barcode = plate_row['barcode'].iloc[0]
        
        # Add barcode to all wells from this plate
        plate_mask = df_to_process['Plate_Name'] == plate_name
        df_to_process.loc[plate_mask, 'Plate_Barcode'] = barcode
    
    # Plate barcodes added - no detailed output needed
    
    # Sort by barcode (numerically by number after hyphen), then well column, then well row
    # Extract numeric part from barcode for proper numerical sorting
    df_to_process['barcode_base'] = df_to_process['Plate_Barcode'].str.split('-').str[0]
    df_to_process['barcode_number'] = df_to_process['Plate_Barcode'].str.split('-').str[1].astype(int)
    
    # Sort by base barcode, then numeric part, then well column, then well row
    df_to_process = df_to_process.sort_values(['barcode_base', 'barcode_number', 'Well_Col', 'Well_Row'])
    
    # Remove temporary sorting columns
    df_to_process = df_to_process.drop(['barcode_base', 'barcode_number'], axis=1)
    
    # DataFrame sorted - no detailed output needed
    
    # Step 5: Clean up the master DataFrame
    # Cleaning DataFrame - no output needed
    cleaned_df = df_to_process.copy()
    
    # Remove specified columns
    columns_to_remove = ['Well_Row', 'Well_Col', 'Plate_Name']
    for col in columns_to_remove:
        if col in cleaned_df.columns:
            cleaned_df = cleaned_df.drop(col, axis=1)
            # Column removed - no detailed output needed
    
    # Clear index values for unused/ladder wells
    index_columns = ['Index_Set', 'Index_Well', 'Index_Name']
    unused_ladder_mask = cleaned_df['Type'].isin(['unused', 'ladder'])
    
    for col in index_columns:
        if col in cleaned_df.columns:
            cleaned_df.loc[unused_ladder_mask, col] = pd.NA
    
    unused_count = unused_ladder_mask.sum()
    # Index values cleared - no detailed output needed
    
    # Reorder columns to put Plate_Barcode after index info and before FA_Well
    if 'Plate_Barcode' in cleaned_df.columns and 'FA_Well' in cleaned_df.columns:
        # Get current column order
        cols = list(cleaned_df.columns)
        
        # Remove Plate_Barcode and FA_Well from their current positions
        cols.remove('Plate_Barcode')
        if 'FA_Well' in cols:
            cols.remove('FA_Well')
        
        # Find position after Index_Name (or last index column)
        insert_pos = len(cols)  # Default to end if no index columns found
        for i, col in enumerate(cols):
            if col == 'Index_Name':
                insert_pos = i + 1
                break
            elif col in ['Index_Set', 'Index_Well'] and insert_pos == len(cols):
                insert_pos = i + 1
        
        # Insert Plate_Barcode after index columns
        cols.insert(insert_pos, 'Plate_Barcode')
        
        # Add FA_Well at the end
        if 'FA_Well' in cleaned_df.columns:
            cols.append('FA_Well')
        
        # Reorder the DataFrame
        cleaned_df = cleaned_df[cols]
        # Columns reordered - no detailed output needed
    
    # Save cleaned master DataFrame to CSV for inspection
    output_filename = "master_plate_data.csv"
    cleaned_df.to_csv(output_filename, index=False)
    # Master DataFrame saved - no detailed output needed
    
    return cleaned_df


def archive_database_file():
    """
    Archive existing database file with timestamp suffix by copying (not moving).
    This preserves the original database for in-place updates.
    Follows the same archiving pattern as generate_barcode_labels.py.
    """
    # Archiving database - no output needed
    
    db_path = Path("project_summary.db")
    
    # Archive existing database file if it exists
    if db_path.exists():
        timestamp = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
        archive_dir = Path("archived_files")
        archive_dir.mkdir(exist_ok=True)
        
        # Create archive name with timestamp suffix
        stem = db_path.stem  # "project_summary"
        suffix = db_path.suffix  # ".db"
        archive_name = f"{stem}_{timestamp}{suffix}"
        archive_path = archive_dir / archive_name
        
        # Copy instead of move to preserve original for in-place updates
        shutil.copy2(str(db_path), str(archive_path))
        # Database archived - no detailed output needed
        
        # Also archive master CSV file if it exists
        archive_master_csv_file()
    else:
        # No database to archive - no output needed
        pass


def update_database_smart(master_df, sample_metadata_df, individual_plates_df, is_first_run, layout_detection_results=None):
    """
    Smart database update that only modifies what actually changes.
    Preserves all unknown tables by only touching specific tables.
    
    Args:
        master_df (pd.DataFrame): Master DataFrame to add/update as table
        sample_metadata_df (pd.DataFrame): Sample metadata (for first run only)
        individual_plates_df (pd.DataFrame): Individual plates (for first run only)
        is_first_run (bool): True for first runs, False for subsequent runs
        layout_detection_results (dict): Dictionary of plate_name -> is_upper_left_bool (optional)
    """
    # Creating/updating database - no output needed
    
    db_path = Path("project_summary.db")
    
    try:
        engine = create_engine(f'sqlite:///{db_path}')
        
        if is_first_run:
            # First run: create all tables fresh
            # Add upper_left_registration column to individual_plates_df if layout results provided
            if layout_detection_results:
                individual_plates_with_layout = add_layout_info_to_individual_plates(
                    individual_plates_df, layout_detection_results
                )
            else:
                individual_plates_with_layout = individual_plates_df
            
            sample_metadata_df.to_sql('sample_metadata', engine, if_exists='replace', index=False)
            individual_plates_with_layout.to_sql('individual_plates', engine, if_exists='replace', index=False)
            master_df.to_sql('master_plate_data', engine, if_exists='replace', index=False)
            # Database created successfully - no detailed output needed
        else:
            # Subsequent run: only update master_plate_data table
            # sample_metadata and individual_plates remain unchanged, but update layout info if provided
            if layout_detection_results:
                update_individual_plates_with_layout_info(engine, layout_detection_results)
            
            master_df.to_sql('master_plate_data', engine, if_exists='replace', index=False)
            # Database updated successfully - no detailed output needed
        
        # Properly dispose of engine
        engine.dispose()
        
    except Exception as e:
        print(f"❌ FATAL ERROR: Could not update database: {e}")
        sys.exit(1)


def add_layout_info_to_individual_plates(individual_plates_df, layout_detection_results):
    """
    Add upper_left_registration column to individual_plates DataFrame for first run.
    Only sets values for plates being processed - others remain NULL.
    
    Args:
        individual_plates_df (pd.DataFrame): Original individual plates DataFrame
        layout_detection_results (dict): Dictionary of plate_name -> is_upper_left_bool
        
    Returns:
        pd.DataFrame: Updated DataFrame with upper_left_registration column
    """
    # Create a copy to avoid modifying original
    updated_df = individual_plates_df.copy()
    
    # Add the new column with default value NULL (pd.NA)
    # This ensures plates not being processed have NULL values
    updated_df['upper_left_registration'] = pd.NA
    
    # Update values ONLY for plates being processed in this run
    for plate_name, is_upper_left in layout_detection_results.items():
        mask = updated_df['plate_name'] == plate_name
        updated_df.loc[mask, 'upper_left_registration'] = is_upper_left
    
    return updated_df


def update_individual_plates_with_layout_info(engine, layout_detection_results):
    """
    Update individual_plates table with layout information for subsequent runs.
    Adds column if it doesn't exist, then updates records ONLY for plates being processed.
    
    Args:
        engine: SQLAlchemy engine for database connection
        layout_detection_results (dict): Dictionary of plate_name -> is_upper_left_bool
    """
    from sqlalchemy import text
    
    try:
        # Check if upper_left_registration column exists, add if not
        with engine.connect() as conn:
            # Try to add column (will fail silently if column already exists)
            # Default NULL ensures unprocessed plates remain NULL
            try:
                conn.execute(text("ALTER TABLE individual_plates ADD COLUMN upper_left_registration BOOLEAN DEFAULT NULL"))
                conn.commit()
                # Column added successfully - no output needed
            except Exception:
                # Column already exists - this is expected for subsequent runs after first implementation
                pass
            
            # Update records ONLY for the plates being processed in this run
            for plate_name, is_upper_left in layout_detection_results.items():
                conn.execute(
                    text("UPDATE individual_plates SET upper_left_registration = :is_upper_left WHERE plate_name = :plate_name"),
                    {"is_upper_left": is_upper_left, "plate_name": plate_name}
                )
            conn.commit()
            
    except Exception as e:
        print(f"❌ FATAL ERROR: Could not update individual_plates with layout info: {e}")
        raise


def archive_and_regenerate_plate_names_csv():
    """
    Archive existing individual_plates.csv file and regenerate it from the updated database.
    Uses ALL available columns from the SQL table.
    Follows the same archiving pattern as other files in the system.
    """
    # Step 1: Archive existing individual_plates.csv if it exists
    csv_path = Path("individual_plates.csv")
    
    if csv_path.exists():
        timestamp = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
        archive_dir = Path("archived_files")
        archive_dir.mkdir(exist_ok=True)
        
        # Create archive name with timestamp suffix
        stem = csv_path.stem  # "plate_names"
        suffix = csv_path.suffix  # ".csv"
        archive_name = f"{stem}_{timestamp}{suffix}"
        archive_path = archive_dir / archive_name
        
        # Move existing file to archive
        shutil.move(str(csv_path), str(archive_path))
        # Plate names CSV archived - no detailed output needed
    
    # Step 2: Generate fresh individual_plates.csv from updated database
    db_path = Path("project_summary.db")

    if not db_path.exists():
        print("FATAL ERROR: No database file found, cannot regenerate individual_plates.csv")
        sys.exit()
    
    try:
        engine = create_engine(f'sqlite:///{db_path}')
        
        # Read the updated individual_plates table with ALL columns
        # This ensures that any new columns added over time are included
        individual_plates_df = pd.read_sql('SELECT * FROM individual_plates', engine)
        engine.dispose()
        
        # Generate fresh individual_plates.csv with ALL available columns
        individual_plates_df.to_csv('individual_plates.csv', index=False)
        # Individual plates CSV regenerated successfully - no output needed

    except Exception as e:
        print(f"FATAL ERROR: Could not regenerate individual_plates.csv: {e}")
        sys.exit()


def update_database_with_master_table(master_df, sample_metadata_df, individual_plates_df):
    """
    Legacy function - kept for backward compatibility.
    Calls the new smart update function with first_run=True.
    """
    update_database_smart(master_df, sample_metadata_df, individual_plates_df, is_first_run=True)


def detect_run_type():
    """
    Detect if this is a first run or subsequent run by checking for master_plate_data table.
    
    Returns:
        tuple: (is_first_run, existing_master_df)
               is_first_run: True if first run, False if subsequent run
               existing_master_df: DataFrame of existing master data (None if first run)
    """
    db_path = Path("project_summary.db")
    
    # Check if database file exists
    if not db_path.exists():
        print("🔬 FIRST RUN DETECTED: No database file found")
        return True, None
    
    try:
        engine = create_engine(f'sqlite:///{db_path}')
        
        # Check if master_plate_data table exists
        try:
            existing_master_df = pd.read_sql('SELECT * FROM master_plate_data', engine)
            engine.dispose()
            print(f"🔄 SUBSEQUENT RUN DETECTED")
            return False, existing_master_df
        except Exception:
            # Table doesn't exist - first run
            engine.dispose()
            print("🔬 FIRST RUN DETECTED: Database exists but no master_plate_data table found")
            return True, None
            
    except Exception as e:
        print(f"FATAL ERROR: Could not access database {db_path}: {e}")
        sys.exit()


def validate_no_duplicate_plates(plate_list, existing_master_df):
    """
    Validate that none of the plates in the current list were previously processed.
    
    Args:
        plate_list (list): List of plate names from library_sort_plates.txt
        existing_master_df (pd.DataFrame): Existing master plate data
        
    Raises:
        SystemExit: If any plates were previously processed
    """
    if existing_master_df is None or existing_master_df.empty:
        return  # No existing data to check against
    
    # Get list of previously processed plates
    if 'Plate_ID' in existing_master_df.columns:
        previously_processed = set(existing_master_df['Plate_ID'].unique())
    else:
        print("FATAL ERROR: No Plate_ID column found in existing master data")
        print("Existing master_plate_data table must contain 'Plate_ID' column for duplicate validation.")
        sys.exit()
    
    # Check for duplicates
    duplicate_plates = []
    for plate_name in plate_list:
        if plate_name in previously_processed:
            duplicate_plates.append(plate_name)
    
    if duplicate_plates:
        print("FATAL ERROR: The following plates have already been processed and cannot be reprocessed:")
        for plate in duplicate_plates:
            print(f"  - {plate}")
        print("Reprocessing existing plates is not allowed for data integrity.")
        print("Remove these plates from library_sort_plates.txt or use different plate names.")
        sys.exit()
    
    # Duplicate validation successful - no detailed output needed


def archive_master_csv_file():
    """
    Archive existing master DataFrame CSV file with timestamp suffix.
    """
    csv_path = Path("master_plate_data.csv")
    
    if csv_path.exists():
        timestamp = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
        archive_dir = Path("archived_files")
        archive_dir.mkdir(exist_ok=True)
        
        # Create archive name with timestamp suffix
        stem = csv_path.stem  # "library_dataframe"
        suffix = csv_path.suffix  # ".csv"
        archive_name = f"{stem}_{timestamp}{suffix}"
        archive_path = archive_dir / archive_name
        
        shutil.move(str(csv_path), str(archive_path))
        # Master CSV archived - no detailed output needed
    else:
        # No master CSV to archive - no output needed
        pass


def create_processed_files_directories():
    """
    Create directory structure for organizing processed input files.
    """
    # Creating directory structure - no output needed
    
    # Create main directory
    processed_dir = Path("2_library_creation/previously_processed_files")
    processed_dir.mkdir(exist_ok=True)
    
    # Create subdirectories
    layout_files_dir = processed_dir / "plate_layout_files"
    layout_files_dir.mkdir(exist_ok=True)
    
    sorted_plates_dir = processed_dir / "list_of_sorted_plates"
    sorted_plates_dir.mkdir(exist_ok=True)
    
    # Directory structure created - no detailed output needed
    
    # Create main directory
    processed_dir = Path("2_library_creation/previously_processed_files")
    processed_dir.mkdir(exist_ok=True)
    
    # Create subdirectories
    layout_files_dir = processed_dir / "plate_layout_files"
    layout_files_dir.mkdir(exist_ok=True)
    
    sorted_plates_dir = processed_dir / "list_of_sorted_plates"
    sorted_plates_dir.mkdir(exist_ok=True)
    
    # Directory structure created - no detailed output needed


def move_processed_input_files(processed_plates):
    """
    Move processed input files to organized directory structure with timestamp suffixes.
    
    Args:
        processed_plates (list): List of plate names that were processed
    """
    # Moving processed files - no output needed
    
    timestamp = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
    
    # Move library_sort_plates.txt
    library_file = Path("2_library_creation/library_sort_plates.txt")
    if library_file.exists():
        dest_dir = Path("2_library_creation/previously_processed_files/list_of_sorted_plates")
        dest_file = dest_dir / f"library_sort_plates_{timestamp}.txt"
        shutil.move(str(library_file), str(dest_file))
        # Library sort plates file moved - no detailed output needed
    
    # Move layout CSV files for processed plates
    layout_files_moved = 0
    for plate_name in processed_plates:
        csv_file = Path(f"2_library_creation/{plate_name}.csv")
        if csv_file.exists():
            # Skip the standard template file
            if csv_file.name == "standard_sort_layout.csv":
                continue
                
            dest_dir = Path("2_library_creation/previously_processed_files/plate_layout_files")
            dest_file = dest_dir / csv_file.name
            shutil.move(str(csv_file), str(dest_file))
            # File moved - no detailed output needed
            layout_files_moved += 1
    
    # Input files moved - no detailed output needed


def perform_fa_well_selection(all_plate_layouts_with_indexes, individual_plates_df):
    """
    Perform FA well selection once for all plates to avoid redundant processing.
    
    Args:
        all_plate_layouts_with_indexes (dict): Dictionary of plate_name -> DataFrame with index columns
        individual_plates_df (pd.DataFrame): Database plate information for barcode lookup
        
    Returns:
        dict: Dictionary of plate_name -> DataFrame with FA well assignments
    """
    # Performing FA well selection - no output needed
    
    fa_well_assignments = {}
    
    for plate_name, plate_df in all_plate_layouts_with_indexes.items():
        # Processing FA selection - no detailed output needed
        
        # Step 1: Select wells for FA transfer
        selected_wells = select_wells_for_fa_transfer(plate_df)
        if selected_wells.empty:
            # No wells selected - no detailed output needed
            fa_well_assignments[plate_name] = pd.DataFrame()  # Empty DataFrame
            continue
        
        # Step 2: Assign FA well positions
        fa_wells_df = assign_fa_wells(selected_wells)
        
        # Store the result
        fa_well_assignments[plate_name] = fa_wells_df
        # Wells selected for FA processing - no detailed output needed
    
    total_selected = sum(len(df) for df in fa_well_assignments.values())
    # FA well selection completed - no detailed output needed
    
    return fa_well_assignments


def create_dilution_and_fa_bartender_file(plate_list, individual_plates_df):
    """
    Create a single BarTender label file containing dilution plate and FA plate
    labels for all processed plates.

    For each library plate barcode (e.g. "A7A7K-6") two labels are written:
      - Dilution plate: "{barcode}D"  (e.g. "A7A7K-6D")
      - FA plate:       "{barcode}F"  (e.g. "A7A7K-6F")

    The file is written to:
        2_library_creation/BARTENDER_dilution_and_FA_plate_labels.txt

    Format mirrors the BarTender files produced by
    initiate_project_folder_and_make_sort_plate_labels.py:
      - Special header block
      - One label per line: {barcode},"<human-readable name>"
      - Blank separator line (,) between labels
      - Plates are ordered highest barcode number first (reverse order),
        with the dilution label printed before the FA label for each plate.

    Args:
        plate_list (list): List of plate names being processed (in processing order)
        individual_plates_df (pd.DataFrame): Database plate information for barcode lookup
    """
    output_dir = Path("2_library_creation/Bartender_files")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
    output_path = output_dir / f"BARTENDER_dilution_and_FA_plate_labels_{timestamp}.txt"

    # Build list of (barcode_number, barcode, plate_name) tuples so we can sort
    plate_entries = []
    for plate_name in plate_list:
        plate_row = individual_plates_df[individual_plates_df['plate_name'] == plate_name]
        if plate_row.empty:
            print(f"FATAL ERROR: Could not find barcode for plate '{plate_name}' in database")
            print("All plates must have valid barcodes in the individual_plates table.")
            sys.exit()

        barcode = plate_row['barcode'].iloc[0]

        # Extract numeric suffix for sorting (e.g. "A7A7K-6" -> 6)
        try:
            barcode_number = int(str(barcode).split('-')[-1])
        except ValueError:
            barcode_number = 0

        plate_entries.append((barcode_number, barcode, plate_name))

    # Sort highest barcode number first (matches sort-plate BarTender convention)
    plate_entries.sort(key=lambda x: x[0], reverse=True)

    try:
        with open(output_path, 'w', newline='') as f:
            # Write BarTender header
            f.write(BARTENDER_HEADER)

            for barcode_number, barcode, plate_name in plate_entries:
                dilution_barcode = f"{barcode}D"
                fa_barcode = f"{barcode}F"

                # --- Dilution and FA plate labels written back-to-back (no blank between them) ---
                f.write(f'{dilution_barcode},"{plate_name} Dilution"\r\n')
                f.write(f'{fa_barcode},"{plate_name} FA"\r\n')

                # After every pair (including the last), write a blank separator label
                f.write(',\r\n')

            # Three blank labels at the end (the loop already wrote one after the last pair,
            # so write two more to reach a total of three trailing blanks)
            f.write(',\r\n')
            f.write(',\r\n')

        # BarTender dilution/FA label file created - no detailed output needed

    except Exception as e:
        print(f"FATAL ERROR: Could not create BarTender dilution/FA label file: {e}")
        print("Failed to write BarTender label file to 2_library_creation/ folder.")
        sys.exit()


def main():
    """
    Main function - entry point for our script.
    Handles both first run and subsequent run logic.
    """
    # Script starting - no detailed output needed
    
    # Step 1: Detect run type and get existing data
    is_first_run, existing_master_df = detect_run_type()
    
    # Step 2: Read database tables and current plate list
    sample_metadata_df, individual_plates_df = read_database_tables()
    plate_list = read_library_sort_plates()
    
    # Step 3: Validate plates based on run type
    if is_first_run:
        # First run: validate all plates exist in database
        validate_plates_in_database(plate_list, individual_plates_df)
    else:
        # Subsequent run: validate plates exist AND check for duplicates
        validate_plates_in_database(plate_list, individual_plates_df)
        validate_no_duplicate_plates(plate_list, existing_master_df)
    
    # Step 4: Create directory structure for processed files
    create_processed_files_directories()
    
    # Step 5: Process plates (same logic for both first and subsequent runs)
    # Separate custom and standard plates
    custom_plates, standard_plates = separate_custom_and_standard_plates(plate_list, individual_plates_df)
    
    # Validate and load custom plate layout files
    custom_layout_data = validate_custom_plate_layouts(custom_plates)
    
    # Process standard plate layouts
    standard_layout_data = process_standard_plate_layouts(standard_plates, individual_plates_df, sample_metadata_df)
    
    # Combine all plate layout data
    all_plate_layouts = {**custom_layout_data, **standard_layout_data}
    print(f"✅ Processed {len(all_plate_layouts)} plates ({len(custom_layout_data)} custom + {len(standard_layout_data)} standard)")
    
    # Add index assignments to all plates and capture layout detection results
    all_plate_layouts_with_indexes, layout_detection_results = add_index_columns_to_plates(all_plate_layouts)
    
    # Create Illumina index transfer files
    create_illumina_index_files(all_plate_layouts_with_indexes, individual_plates_df)
    
    # Perform FA well selection once for all plates
    fa_well_assignments = perform_fa_well_selection(all_plate_layouts_with_indexes, individual_plates_df)
    
    # Create FA transfer files using pre-computed FA selections
    create_fa_transfer_files(fa_well_assignments, individual_plates_df)

    # Create single BarTender label file for dilution and FA plates
    create_dilution_and_fa_bartender_file(plate_list, individual_plates_df)

    # Create FA upload files using pre-computed FA selections
    create_fa_upload_files(fa_well_assignments, individual_plates_df)
    
    # Generate thresholds.txt file for FA analysis
    generate_thresholds_file(plate_list, individual_plates_df)
    
    # Step 6: Handle master DataFrame based on run type
    if is_first_run:
        # First run: create new master DataFrame
        master_df = create_master_dataframe(all_plate_layouts_with_indexes, fa_well_assignments, individual_plates_df)
    else:
        # Subsequent run: create new data, clean it, then append to existing
        # Processing new plates for subsequent run - no output needed
        
        # Create new master DataFrame (this will be uncleaned with all columns)
        new_master_df_raw = create_master_dataframe(all_plate_layouts_with_indexes, fa_well_assignments, individual_plates_df)
        
        # Clean the new DataFrame using the same logic as the existing one
        # Cleaning new master DataFrame - no output needed
        new_master_df_cleaned = new_master_df_raw.copy()
        
        # Remove the same columns that were removed from existing DataFrame
        columns_to_remove = ['Well_Row', 'Well_Col', 'Plate_Name']
        for col in columns_to_remove:
            if col in new_master_df_cleaned.columns:
                new_master_df_cleaned = new_master_df_cleaned.drop(col, axis=1)
        
        # Clear index values for unused/ladder wells (same as existing)
        index_columns = ['Index_Set', 'Index_Well', 'Index_Name']
        unused_ladder_mask = new_master_df_cleaned['Type'].isin(['unused', 'ladder'])
        
        for col in index_columns:
            if col in new_master_df_cleaned.columns:
                new_master_df_cleaned.loc[unused_ladder_mask, col] = pd.NA
        
        unused_count = unused_ladder_mask.sum()
        
        # Reorder columns to match existing DataFrame structure
        if 'Plate_Barcode' in new_master_df_cleaned.columns and 'FA_Well' in new_master_df_cleaned.columns:
            cols = list(new_master_df_cleaned.columns)
            cols.remove('Plate_Barcode')
            if 'FA_Well' in cols:
                cols.remove('FA_Well')
            
            # Find position after Index_Name
            insert_pos = len(cols)
            for i, col in enumerate(cols):
                if col == 'Index_Name':
                    insert_pos = i + 1
                    break
                elif col in ['Index_Set', 'Index_Well'] and insert_pos == len(cols):
                    insert_pos = i + 1
            
            cols.insert(insert_pos, 'Plate_Barcode')
            if 'FA_Well' in new_master_df_cleaned.columns:
                cols.append('FA_Well')
            
            new_master_df_cleaned = new_master_df_cleaned[cols]
        
        # Validate and fix DataFrame compatibility for concatenation
        # Validating DataFrame compatibility - no output needed
        existing_cols = set(existing_master_df.columns)
        new_cols = set(new_master_df_cleaned.columns)
        
        if existing_cols != new_cols:
            missing_in_existing = new_cols - existing_cols
            missing_in_new = existing_cols - new_cols
            
            # Check for unexpected columns in new DataFrame
            if missing_in_existing:
                print(f"FATAL ERROR: New DataFrame has unexpected columns not found in existing DataFrame")
                print(f"Existing DataFrame columns: {sorted(existing_cols)}")
                print(f"New DataFrame columns: {sorted(new_cols)}")
                print(f"Unexpected columns in new: {sorted(missing_in_existing)}")
                print("This indicates a logic error in the script. New DataFrames should not have columns that existing DataFrames lack.")
                sys.exit()
            
            # Handle missing columns in new DataFrame (expected scenario after FA analysis)
            if missing_in_new:
                # Add missing columns to new DataFrame with appropriate default values
                for col in missing_in_new:
                    if col in ['dilution_factor', 'ng/uL', 'nmole/L', 'Avg. Size']:
                        # Numeric columns - use NaN
                        new_master_df_cleaned[col] = pd.NA
                    elif col in ['Passed_library', 'Redo_whole_plate']:
                        # Boolean columns - use NaN (will be filled later)
                        new_master_df_cleaned[col] = pd.NA
                    elif col == 'Failed_index_sets':
                        # List column - use string representation of empty list for SQLite compatibility
                        new_master_df_cleaned[col] = '[]'
                    else:
                        # Other columns - use NaN
                        new_master_df_cleaned[col] = pd.NA
        
        # Ensure column order matches existing DataFrame
        if list(existing_master_df.columns) != list(new_master_df_cleaned.columns):
            # Reorder new DataFrame columns to match existing DataFrame
            new_master_df_cleaned = new_master_df_cleaned[existing_master_df.columns]
        
        # Safely append new data to existing master DataFrame
        try:
            # Use explicit dtype preservation to avoid FutureWarning about NA handling
            import warnings
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=FutureWarning, message=".*DataFrame concatenation.*")
                master_df = pd.concat([existing_master_df, new_master_df_cleaned], ignore_index=True)
            
            print(f"✅ Appended {len(new_master_df_cleaned)} new wells to existing {len(existing_master_df)} wells")
        except Exception as e:
            print(f"FATAL ERROR: Failed to concatenate DataFrames: {e}")
            print("Cannot safely append new data to existing master DataFrame.")
            sys.exit()
        
        # Note: CSV will be saved after database operations for consistency
    
    # Step 7: Archive existing files and update database
    archive_database_file()
    update_database_smart(master_df, sample_metadata_df, individual_plates_df, is_first_run, layout_detection_results)
    
    # Step 7.5: Archive and regenerate individual_plates.csv with layout information
    archive_and_regenerate_plate_names_csv()

    # Step 8: Save final master DataFrame to CSV (for both first and subsequent runs)
    output_filename = "master_plate_data.csv"
    master_df.to_csv(output_filename, index=False)
    # Final master DataFrame saved - no detailed output needed
    
    # Step 9: Move processed input files to organized directories
    move_processed_input_files(plate_list)

    # Create success marker for workflow manager
    create_success_marker()


if __name__ == "__main__":
    main()