#!/usr/bin/env python3

"""
Laboratory SPITS File Generation Script

This script processes plate selection input to generate SPITS (Sample Processing and Information Tracking System) 
files for selected plates and wells following laboratory automation standards.

USAGE: python create_spits.py

CRITICAL REQUIREMENTS:
- MUST use sip-lims conda environment
- Follows existing SPS script patterns
- Implements comprehensive error handling with "FATAL ERROR" messaging
- Supports both upper left registration and full plate layouts

Features:
- Plate selection CSV processing from 4_plate_selection_and_pooling/ folder
- Database-driven plate validation and well selection
- Upper left registration vs full plate detection and handling
- Index set filtering for full plates
- SPITS CSV generation with dynamic field population
- Database updates with selected_for_pooling tracking
- Timestamped file archiving and organized folder management
- Comprehensive validation and error handling

Input File Organization (4_plate_selection_and_pooling/ folder):
- plate_selection.csv: Two-column file with Plate_ID and optional Index_sets

Output File Organization (4_plate_selection_and_pooling/ folder):
- {proposal}_capsule_sort_SPITS.csv: SPITS file with selected well data

Database Schema Updates:
- individual_plates table: Add selected_for_pooling column (boolean)
- master_plate_data table: Add selected_for_pooling column (0/1)
- Database file: project_summary.db (working directory)

Well Selection Logic:
- Upper left registration plates: Select sample/neg_cntrl wells that passed FA analysis (Passed_library = 1)
- Full plates: Select all sample/neg_cntrl wells from specified index sets regardless of FA results
- Empty index sets column means select from all index sets on the plate

SPITS File Format:
- Headers and values defined by SPITS_header_key.csv mapping
- Dynamic field population from master_plate_data and sample_metadata tables
- Fixed values for standard laboratory parameters
- Template string processing for sample names

Safety Features:
- Laboratory-grade error messaging with "FATAL ERROR" prefix
- Comprehensive plate and index set validation
- Database integrity checks and archiving
- Fail-fast error handling with sys.exit()
"""

import pandas as pd
import sys
import shutil
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine


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
    Read the project_summary.db database and create DataFrames from all tables.
    
    Returns:
        tuple: (sample_metadata_df, individual_plates_df, master_plate_data_df)
        
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
        
        # Read master_plate_data table
        try:
            master_plate_data_df = pd.read_sql('SELECT * FROM master_plate_data', engine)
            # Database read successful - no output needed
        except Exception as e:
            print(f"FATAL ERROR: Could not read 'master_plate_data' table: {e}")
            print("Database must contain 'master_plate_data' table.")
            engine.dispose()
            sys.exit()
        
        # Properly dispose of engine
        engine.dispose()
        
        return sample_metadata_df, individual_plates_df, master_plate_data_df
        
    except Exception as e:
        print(f"FATAL ERROR: Could not connect to database {db_path}: {e}")
        print("Database file may be corrupted or inaccessible.")
        sys.exit()


def validate_database_schema(sample_metadata_df, individual_plates_df, master_plate_data_df):
    """
    Validate that database tables have all required columns for SPITS processing.
    
    Args:
        sample_metadata_df (pd.DataFrame): Sample metadata table
        individual_plates_df (pd.DataFrame): Individual plates table
        master_plate_data_df (pd.DataFrame): Master plate data table
        
    Raises:
        SystemExit: If required columns are missing
    """
    # Required columns for each table
    required_columns = {
        'sample_metadata': ['Proposal', 'Project', 'Sample'],
        'individual_plates': ['plate_name', 'upper_left_registration'],
        'master_plate_data': ['Plate_ID', 'Well', 'Type', 'Index_Set', 'Passed_library']
    }
    
    tables = {
        'sample_metadata': sample_metadata_df,
        'individual_plates': individual_plates_df,
        'master_plate_data': master_plate_data_df
    }
    
    # Check each table for required columns
    for table_name, df in tables.items():
        missing_columns = []
        for col in required_columns[table_name]:
            if col not in df.columns:
                missing_columns.append(col)
        
        if missing_columns:
            print(f"FATAL ERROR: Database table '{table_name}' missing required columns: {missing_columns}")
            print(f"Required columns for {table_name}: {required_columns[table_name]}")
            print(f"Found columns in {table_name}: {list(df.columns)}")
            print("Database schema must match expected format for SPITS processing.")
            sys.exit()


def read_plate_selection_csv():
    """
    Read the plate selection CSV file from 4_plate_selection_and_pooling/ folder.
    
    Returns:
        pd.DataFrame: DataFrame with Plate_ID and Index_sets columns
        
    Raises:
        SystemExit: If file not found or incorrectly formatted
    """
    file_path = Path("4_plate_selection_and_pooling/plate_selection.csv")
    
    # Check if file exists
    if not file_path.exists():
        print(f"FATAL ERROR: File 'plate_selection.csv' not found in 4_plate_selection_and_pooling folder")
        print("Script requires plate_selection.csv file in 4_plate_selection_and_pooling/ to proceed.")
        sys.exit()
    
    try:
        # Read CSV file
        plate_selection_df = pd.read_csv(file_path, encoding='utf-8-sig')
        
        # Validate required columns exist
        required_columns = ['Plate_ID', 'Index_sets']
        missing_columns = []
        for col in required_columns:
            if col not in plate_selection_df.columns:
                missing_columns.append(col)
        
        if missing_columns:
            print(f"FATAL ERROR: Plate selection CSV missing required columns: {missing_columns}")
            print(f"Required columns: {required_columns}")
            print(f"Found columns: {list(plate_selection_df.columns)}")
            sys.exit()
        
        # Check if we have any plates to process
        if len(plate_selection_df) == 0:
            print(f"FATAL ERROR: No plates found in plate_selection.csv")
            print("File must contain at least one plate to process.")
            sys.exit()
        
        # Validate Plate_ID format
        for idx, plate_id in enumerate(plate_selection_df['Plate_ID'], 1):
            if pd.isna(plate_id) or str(plate_id).strip() == '':
                print(f"FATAL ERROR: Empty Plate_ID on row {idx}")
                print("All rows must have valid Plate_ID values.")
                sys.exit()
            
            # Basic format validation
            plate_id_str = str(plate_id).strip()
            if '.' not in plate_id_str:
                print(f"FATAL ERROR: Invalid Plate_ID format on row {idx}: '{plate_id_str}'")
                print("Expected format: 'PROJECT_SAMPLE.NUMBER' (e.g., 'BP9735_SitukAM.1')")
                sys.exit()
        
        # Clean up Index_sets column - replace NaN with empty string
        plate_selection_df['Index_sets'] = plate_selection_df['Index_sets'].fillna('')
        
        print(f"✅ Read {len(plate_selection_df)} plates from plate_selection.csv")
        return plate_selection_df
        
    except Exception as e:
        print(f"FATAL ERROR: Could not read file 'plate_selection.csv': {e}")
        print("File may be corrupted or inaccessible.")
        sys.exit()


def validate_plates_exist_in_database(plate_selection_df, individual_plates_df):
    """
    Validate that all plates in selection exist in the database.
    
    Args:
        plate_selection_df (pd.DataFrame): Plate selection data
        individual_plates_df (pd.DataFrame): Individual plates table
        
    Raises:
        SystemExit: If any plates are missing
    """
    db_plate_names = set(individual_plates_df['plate_name'].tolist())
    
    missing_plates = []
    for plate_id in plate_selection_df['Plate_ID']:
        if plate_id not in db_plate_names:
            missing_plates.append(plate_id)
    
    if missing_plates:
        print(f"FATAL ERROR: The following plates from plate_selection.csv are not found in the database:")
        for plate in missing_plates:
            print(f"  - {plate}")
        print("All plates in the selection must exist in the individual_plates table.")
        sys.exit()


def validate_plates_have_fa_results(plate_selection_df, master_plate_data_df):
    """
    Validate that all plates have completed FA analysis.
    
    Args:
        plate_selection_df (pd.DataFrame): Plate selection data
        master_plate_data_df (pd.DataFrame): Master plate data table
        
    Raises:
        SystemExit: If any plates lack FA results
    """
    master_plate_names = set(master_plate_data_df['Plate_ID'].tolist())
    
    plates_without_fa = []
    for plate_id in plate_selection_df['Plate_ID']:
        if plate_id not in master_plate_names:
            plates_without_fa.append(plate_id)
    
    if plates_without_fa:
        print(f"FATAL ERROR: The following plates have not completed FA analysis:")
        for plate in plates_without_fa:
            print(f"  - {plate}")
        print("All plates must have completed FA analysis before SPITS file generation.")
        sys.exit()


def validate_index_sets_for_plates(plate_selection_df, master_plate_data_df):
    """
    Validate that specified index sets are valid and exist on each plate.
    
    Args:
        plate_selection_df (pd.DataFrame): Plate selection data
        master_plate_data_df (pd.DataFrame): Master plate data table
        
    Raises:
        SystemExit: If any index sets are invalid or missing
    """
    valid_index_sets = {'PE17', 'PE18', 'PE19', 'PE20'}
    
    for idx, row in plate_selection_df.iterrows():
        plate_id = row['Plate_ID']
        index_sets_str = str(row['Index_sets']).strip()
        
        # Skip validation if index sets column is empty (means use all)
        if index_sets_str == '' or index_sets_str == 'nan':
            continue
        
        # Parse index sets
        try:
            specified_index_sets = [s.strip() for s in index_sets_str.split(',')]
        except Exception as e:
            print(f"FATAL ERROR: Could not parse index sets for plate '{plate_id}': {index_sets_str}")
            print("Index sets should be comma-separated (e.g., 'PE17,PE19') or empty.")
            sys.exit()
        
        # Check if specified index sets are valid
        invalid_index_sets = []
        for index_set in specified_index_sets:
            if index_set not in valid_index_sets:
                invalid_index_sets.append(index_set)
        
        if invalid_index_sets:
            print(f"FATAL ERROR: Invalid index sets for plate '{plate_id}': {invalid_index_sets}")
            print(f"Valid index sets are: {sorted(valid_index_sets)}")
            sys.exit()
        
        # Check if specified index sets exist on this plate
        plate_data = master_plate_data_df[master_plate_data_df['Plate_ID'] == plate_id]
        available_index_sets = set(plate_data['Index_Set'].dropna().tolist())
        
        missing_index_sets = []
        for index_set in specified_index_sets:
            if index_set not in available_index_sets:
                missing_index_sets.append(index_set)
        
        if missing_index_sets:
            print(f"FATAL ERROR: Plate '{plate_id}' does not have the following specified index sets: {missing_index_sets}")
            print(f"Available index sets on this plate: {sorted(available_index_sets)}")
            sys.exit()


def validate_plates_and_index_sets(plate_selection_df, individual_plates_df, master_plate_data_df):
    """
    Validate that all plates exist in database, have FA results, and index sets are valid.
    
    Args:
        plate_selection_df (pd.DataFrame): Plate selection data
        individual_plates_df (pd.DataFrame): Individual plates table
        master_plate_data_df (pd.DataFrame): Master plate data table
        
    Raises:
        SystemExit: If validation fails
    """
    validate_plates_exist_in_database(plate_selection_df, individual_plates_df)
    validate_plates_have_fa_results(plate_selection_df, master_plate_data_df)
    validate_index_sets_for_plates(plate_selection_df, master_plate_data_df)
    
    print(f"✅ Validated {len(plate_selection_df)} plates and their index set specifications")


def select_wells_from_upper_left_plate(plate_wells):
    """
    Select wells from upper left registration plate (sample/neg_cntrl that passed FA).
    
    Args:
        plate_wells (pd.DataFrame): All wells for the plate
        
    Returns:
        pd.DataFrame: Selected wells
    """
    selected_wells = plate_wells[
        (plate_wells['Type'].isin(['sample', 'neg_cntrl'])) &
        (plate_wells['Passed_library'] == 1)
    ].copy()
    
    # Add plate type information for SPITS generation
    selected_wells['is_upper_left_plate'] = True
    
    return selected_wells


def select_wells_from_full_plate(plate_wells, index_sets_str):
    """
    Select wells from full plate based on specified index sets.
    
    Args:
        plate_wells (pd.DataFrame): All wells for the plate
        index_sets_str (str): Comma-separated index sets or empty string
        
    Returns:
        pd.DataFrame: Selected wells
    """
    # Parse index sets to use
    if index_sets_str == '' or index_sets_str == 'nan':
        # Use all index sets
        target_index_sets = plate_wells['Index_Set'].dropna().unique().tolist()
    else:
        # Use specified index sets
        target_index_sets = [s.strip() for s in index_sets_str.split(',')]
    
    selected_wells = plate_wells[
        (plate_wells['Type'].isin(['sample', 'neg_cntrl'])) &
        (plate_wells['Index_Set'].isin(target_index_sets))
    ].copy()
    
    # Add plate type information for SPITS generation
    selected_wells['is_upper_left_plate'] = False
    
    return selected_wells, target_index_sets


def select_wells_for_single_plate(plate_id, index_sets_str, individual_plates_df, master_plate_data_df):
    """
    Select wells for a single plate based on its type and criteria.
    
    Args:
        plate_id (str): Plate identifier
        index_sets_str (str): Index sets specification
        individual_plates_df (pd.DataFrame): Individual plates table
        master_plate_data_df (pd.DataFrame): Master plate data table
        
    Returns:
        pd.DataFrame: Selected wells for this plate
    """
    # Get plate information
    plate_info = individual_plates_df[individual_plates_df['plate_name'] == plate_id]
    if plate_info.empty:
        print(f"FATAL ERROR: Could not find plate info for '{plate_id}'")
        sys.exit()
    
    # Check if plate uses upper left registration
    is_upper_left = False
    if 'upper_left_registration' in plate_info.columns:
        is_upper_left = bool(plate_info['upper_left_registration'].iloc[0])
    
    # Get all wells for this plate
    plate_wells = master_plate_data_df[master_plate_data_df['Plate_ID'] == plate_id].copy()
    
    if is_upper_left:
        # Upper left registration: select sample/neg_cntrl wells that passed FA analysis
        selected_wells = select_wells_from_upper_left_plate(plate_wells)
        print(f"✅ Upper left plate '{plate_id}': Selected {len(selected_wells)} wells that passed FA analysis")
    else:
        # Full plate: select sample/neg_cntrl wells from specified index sets
        selected_wells, target_index_sets = select_wells_from_full_plate(plate_wells, index_sets_str)
        print(f"✅ Full plate '{plate_id}': Selected {len(selected_wells)} wells from index sets {target_index_sets}")
    
    if len(selected_wells) == 0:
        print(f"FATAL ERROR: No wells selected for plate '{plate_id}'")
        print("Each plate must have at least some wells that meet the selection criteria.")
        sys.exit()
    
    return selected_wells


def select_wells_for_spits(plate_selection_df, individual_plates_df, master_plate_data_df):
    """
    Select wells based on plate type and selection criteria.
    
    Args:
        plate_selection_df (pd.DataFrame): Plate selection data
        individual_plates_df (pd.DataFrame): Individual plates table
        master_plate_data_df (pd.DataFrame): Master plate data table
        
    Returns:
        pd.DataFrame: Selected wells for SPITS processing
    """
    selected_wells_list = []
    
    for idx, row in plate_selection_df.iterrows():
        plate_id = row['Plate_ID']
        index_sets_str = str(row['Index_sets']).strip()
        
        selected_wells = select_wells_for_single_plate(
            plate_id, index_sets_str, individual_plates_df, master_plate_data_df
        )
        selected_wells_list.append(selected_wells)
    
    # Combine all selected wells
    if selected_wells_list:
        all_selected_wells = pd.concat(selected_wells_list, ignore_index=True)
    else:
        print(f"FATAL ERROR: No wells selected from any plates")
        sys.exit()
    
    print(f"✅ Total wells selected for SPITS processing: {len(all_selected_wells)}")
    return all_selected_wells


def get_proposal_name(sample_metadata_df):
    """
    Extract proposal name from sample_metadata table.
    
    Args:
        sample_metadata_df (pd.DataFrame): Sample metadata table
        
    Returns:
        str: Proposal name for SPITS file naming
        
    Raises:
        SystemExit: If proposal cannot be determined
    """
    # Check if proposal column exists and has values
    if 'Proposal' not in sample_metadata_df.columns:
        print("FATAL ERROR: 'Proposal' column not found in sample_metadata table")
        print("Sample metadata must contain proposal information for SPITS file naming.")
        sys.exit()
    
    # Get unique proposal values
    proposals = sample_metadata_df['Proposal'].dropna().unique()
    
    if len(proposals) == 0:
        print("FATAL ERROR: No proposal values found in sample_metadata table")
        sys.exit()
    elif len(proposals) > 1:
        print(f"FATAL ERROR: Multiple proposals found in sample_metadata: {proposals}")
        print("SPITS file generation requires a single proposal per run.")
        sys.exit()
    
    return str(proposals[0])


def create_spits_sample_name(row):
    """
    Create SPITS sample name using a prefix determined by sample type.
    
    - neg_cntrl samples use prefix: "NoTemplateControl"
    - All other samples use prefix: "Uncultured microbe JGI"
    
    Template: "{prefix} {groups}_{plate_id}_{well}"
    Only includes groups that have actual values (not empty, None, or 'None').
    
    Args:
        row (pd.Series): Row from selected wells DataFrame
        
    Returns:
        str: Formatted sample name
    """
    # Get group values and filter out empty/None values
    groups = []
    for group_col in ['Group_1', 'Group_2', 'Group_3']:
        group_val = row.get(group_col, '')
        # Include group if it has a value and is not 'None' or empty
        if group_val and str(group_val).strip() not in ['', 'None', 'nan']:
            groups.append(str(group_val).strip())
    
    plate_id = row.get('Plate_ID', '')
    well = row.get('Well', '')
    
    # Select prefix based on sample type
    prefix = "NoTemplateControl" if row.get('Type', '') == 'neg_cntrl' else "Uncultured microbe JGI"
    
    # Build sample name with only non-empty groups
    if groups:
        groups_str = '_'.join(groups)
        return f"{prefix} {groups_str}_{plate_id}_{well}"
    else:
        # No groups have values
        return f"{prefix} {plate_id}_{well}"


def create_internal_collaborator_name(row):
    """
    Create internal collaborator sample name using template: "{plate_id}_{well}"
    
    Args:
        row (pd.Series): Row from selected wells DataFrame
        
    Returns:
        str: Formatted internal collaborator name
    """
    plate_id = row.get('Plate_ID', '')
    well = row.get('Well', '')
    
    return f"{plate_id}_{well}"


def merge_sample_metadata_for_spits(selected_wells_df, sample_metadata_df):
    """
    Merge selected wells with sample metadata for SPITS field population.

    Each well's Plate_ID encodes the project and sample in the format
    '{Project}_{Sample}.{number}' (e.g., 'BP9735_SitukAM.1').  This
    function parses those components and performs a proper per-row join
    against the sample_metadata table so that every well receives the
    metadata that belongs to its own project/sample combination.

    Args:
        selected_wells_df (pd.DataFrame): Selected wells data
        sample_metadata_df (pd.DataFrame): Sample metadata table

    Returns:
        pd.DataFrame: Merged data for SPITS generation
    """
    # Derive join keys from Plate_ID: 'BP9735_SitukAM.1' -> Project='BP9735', Sample='SitukAM'
    def _parse_plate_id(plate_id):
        """Return (project, sample) parsed from a Plate_ID string."""
        plate_id_str = str(plate_id)
        # Strip the trailing '.N' plate number
        base = plate_id_str.rsplit('.', 1)[0]  # e.g. 'BP9735_SitukAM'
        if '_' in base:
            project, sample = base.split('_', 1)
        else:
            # Fallback: no underscore separator found
            project, sample = base, base
        return project, sample

    # Add temporary join-key columns to the wells DataFrame
    parsed = selected_wells_df['Plate_ID'].apply(_parse_plate_id)
    selected_wells_df = selected_wells_df.copy()
    selected_wells_df['_join_Project'] = [p for p, s in parsed]
    selected_wells_df['_join_Sample'] = [s for p, s in parsed]

    # Prepare metadata for merging: rename join columns to match temp keys
    metadata_for_merge = sample_metadata_df.copy()
    metadata_for_merge = metadata_for_merge.rename(
        columns={'Project': '_join_Project', 'Sample': '_join_Sample'}
    )

    # Identify metadata columns that are not already present in wells DataFrame
    # (excluding the join keys themselves which we added temporarily)
    existing_cols = set(selected_wells_df.columns) - {'_join_Project', '_join_Sample'}
    metadata_cols_to_add = [
        c for c in metadata_for_merge.columns
        if c not in existing_cols and c not in ('_join_Project', '_join_Sample')
    ]
    # Always keep the join keys in the metadata slice
    merge_cols = ['_join_Project', '_join_Sample'] + metadata_cols_to_add

    merged_df = selected_wells_df.merge(
        metadata_for_merge[merge_cols],
        on=['_join_Project', '_join_Sample'],
        how='left'
    )

    # Warn if any wells could not be matched to a sample_metadata record.
    # Those wells will have blank metadata fields in the SPITS output.
    if metadata_cols_to_add:
        unmatched_mask = merged_df[metadata_cols_to_add[0]].isna()
        if unmatched_mask.any():
            unmatched_plates = (
                merged_df.loc[unmatched_mask, 'Plate_ID'].unique().tolist()
            )
            print(f"⚠️  Warning: No sample_metadata entry found for plates: {unmatched_plates}")
            print("   Metadata fields will be left blank for those wells in the SPITS output.")
            print("   To populate them, add the corresponding Project/Sample row to sample_metadata.")

    # Drop temporary join-key columns
    merged_df = merged_df.drop(columns=['_join_Project', '_join_Sample'])

    return merged_df


def create_spits_dataframe(merged_wells_df):
    """
    Create SPITS DataFrame with hardcoded header mapping and field population.
    
    Args:
        merged_wells_df (pd.DataFrame): Wells data merged with sample metadata
        
    Returns:
        pd.DataFrame: SPITS DataFrame ready for CSV export
    """
    spits_rows = []
    
    for idx, row in merged_wells_df.iterrows():
        is_neg_cntrl = row.get('Type', '') == 'neg_cntrl'
        now = datetime.now()
        
        spits_row = {
            # Dynamic fields
            'Sample Name*': create_spits_sample_name(row),
            'Internal Collaborator Sample Name': create_internal_collaborator_name(row),
            
            # Fixed values
            'Concentration* (ng/ul)': 10,
            'Volume* (ul)': 25,
            'Sample Container*': 384,
            'Sample Format*': 'MDA reaction buffer',
            'Was Sample DNAse treated?*': 'N',
            'Biosafety Material Category*': 'Metagenome (Environmental)',
            'Sample Isolation Method*': 'flow sorting',
            
            # From master_plate_data
            'Tube or Plate Label*': row.get('Plate_Barcode', ''),
            'Plate location (well #)* required if samples provided in a plate.': row.get('Well', ''),
            
            # Collection date: neg_cntrl uses current date; samples use sample_metadata values
            'Collection Year*': now.year if is_neg_cntrl else row.get('Collection Year', ''),
            'Collection Month*': now.strftime('%B') if is_neg_cntrl else row.get('Collection Month', ''),
            'Collection Day*': now.day if is_neg_cntrl else row.get('Collection Day', ''),
            
            # Sample origin: neg_cntrl uses fixed lab values; samples use sample_metadata values
            'Sample Isolated From*': 'WGA reagents' if is_neg_cntrl else row.get('Sample Isolated From', ''),
            'Collection Site or Growth Conditions* (required for RNA samples)': 'WGA reagents' if is_neg_cntrl else '',
            'Latitude*': 37.87606 if is_neg_cntrl else row.get('Latitude', ''),
            'Longitude*': -122.25166 if is_neg_cntrl else row.get('Longitude', ''),
            'Depth* (in meters) or minimum depth if a range': 0 if is_neg_cntrl else row.get('Depth (m)', ''),
            'Elevation* (in meters) or minimum elevation if a range': 75 if is_neg_cntrl else row.get('Elevation (m)', ''),
            'Country*': 'USA' if is_neg_cntrl else row.get('Country', ''),
            
            # Empty fields
            'Known / Suspected Organisms': '',
            'Maximum depth (in meters) if a range': '',
            'Maximum elevation (in meters) if a range': '',
            'Sample Contact Name': '',
            'Seq Project PI Name (No edit)': '',
            'Proposal ID (No edit)': '',
            'Control Type': 'negative' if is_neg_cntrl else '',
            'Control Organism Name': '',
            'Control Organism Tax ID': ''
        }
        
        spits_rows.append(spits_row)
    
    # Create DataFrame
    spits_df = pd.DataFrame(spits_rows)
    
    # Define correct column order based on SPITS_header_key.csv
    correct_column_order = [
        'Sample Name*',
        'Concentration* (ng/ul)',
        'Volume* (ul)',
        'Tube or Plate Label*',
        'Sample Container*',
        'Plate location (well #)* required if samples provided in a plate.',
        'Sample Format*',
        'Was Sample DNAse treated?*',
        'Known / Suspected Organisms',
        'Biosafety Material Category*',
        'Sample Isolation Method*',
        'Collection Year*',
        'Collection Month*',
        'Collection Day*',
        'Sample Isolated From*',
        'Collection Site or Growth Conditions* (required for RNA samples)',
        'Latitude*',
        'Longitude*',
        'Depth* (in meters) or minimum depth if a range',
        'Maximum depth (in meters) if a range',
        'Elevation* (in meters) or minimum elevation if a range',
        'Maximum elevation (in meters) if a range',
        'Country*',
        'Sample Contact Name',
        'Seq Project PI Name (No edit)',
        'Proposal ID (No edit)',
        'Control Type',
        'Control Organism Name',
        'Control Organism Tax ID',
        'Internal Collaborator Sample Name'
    ]
    
    # Reorder columns to match SPITS header key specification
    spits_df = spits_df[correct_column_order]
    
    return spits_df


def generate_spits_csv(selected_wells_df, sample_metadata_df, output_dir):
    """
    Generate SPITS CSV file using header mapping and selected wells.
    
    Args:
        selected_wells_df (pd.DataFrame): Selected wells data
        sample_metadata_df (pd.DataFrame): Sample metadata for field population
        output_dir (Path): Output directory path
        
    Returns:
        Path: Path to generated SPITS CSV file
    """
    # Get proposal name for file naming
    proposal = get_proposal_name(sample_metadata_df)
    
    # Merge wells with sample metadata
    merged_wells_df = merge_sample_metadata_for_spits(selected_wells_df.copy(), sample_metadata_df)
    
    # Create SPITS DataFrame
    spits_df = create_spits_dataframe(merged_wells_df)
    
    # Generate output file path
    spits_filename = f"{proposal}_capsule_sort_SPITS.csv"
    spits_file_path = output_dir / spits_filename
    
    # Export to CSV
    spits_df.to_csv(spits_file_path, index=False)
    
    print(f"✅ Generated SPITS file: {spits_filename}")
    print(f"📊 SPITS file contains {len(spits_df)} well records")
    
    return spits_file_path


def add_selection_columns_to_database():
    """
    Add selected_for_pooling columns to database tables if they don't exist.
    """
    db_path = Path("project_summary.db")
    engine = create_engine(f'sqlite:///{db_path}')
    
    with engine.connect() as conn:
        from sqlalchemy import text
        
        # Add selected_for_pooling column to individual_plates table
        try:
            conn.execute(text("ALTER TABLE individual_plates ADD COLUMN selected_for_pooling BOOLEAN DEFAULT 0"))
            conn.commit()
            print("✅ Added selected_for_pooling column to individual_plates table")
        except Exception:
            # Column already exists
            pass
        
        # Add selected_for_pooling column to master_plate_data table
        try:
            conn.execute(text("ALTER TABLE master_plate_data ADD COLUMN selected_for_pooling INTEGER DEFAULT 0"))
            conn.commit()
            print("✅ Added selected_for_pooling column to master_plate_data table")
        except Exception:
            # Column already exists
            pass
    
    engine.dispose()


def update_individual_plates_selection_status(plate_selection_df):
    """
    Update individual_plates table to mark selected plates.
    
    Args:
        plate_selection_df (pd.DataFrame): Plate selection data
    """
    db_path = Path("project_summary.db")
    engine = create_engine(f'sqlite:///{db_path}')
    
    selected_plate_ids = plate_selection_df['Plate_ID'].tolist()
    
    with engine.connect() as conn:
        from sqlalchemy import text
        for plate_id in selected_plate_ids:
            conn.execute(
                text("UPDATE individual_plates SET selected_for_pooling = 1 WHERE plate_name = :plate_id"),
                {"plate_id": plate_id}
            )
        conn.commit()
    
    print(f"✅ Updated individual_plates table: marked {len(selected_plate_ids)} plates as selected")
    engine.dispose()


def update_master_plate_data_selection_status(selected_wells_df):
    """
    Update master_plate_data table to mark selected wells.
    
    Args:
        selected_wells_df (pd.DataFrame): Selected wells data
    """
    db_path = Path("project_summary.db")
    engine = create_engine(f'sqlite:///{db_path}')
    
    # Get unique combinations of Plate_ID and Well from selected wells
    selected_wells_keys = selected_wells_df[['Plate_ID', 'Well']].drop_duplicates()
    
    with engine.connect() as conn:
        from sqlalchemy import text
        for _, row in selected_wells_keys.iterrows():
            conn.execute(
                text("UPDATE master_plate_data SET selected_for_pooling = 1 WHERE Plate_ID = :plate_id AND Well = :well"),
                {"plate_id": row['Plate_ID'], "well": row['Well']}
            )
        conn.commit()
    
    print(f"✅ Updated master_plate_data table: marked {len(selected_wells_keys)} wells as selected")
    engine.dispose()


def update_database_with_selection_status(selected_wells_df, plate_selection_df):
    """
    Update database tables to mark selected plates and wells.
    
    Args:
        selected_wells_df (pd.DataFrame): Selected wells data
        plate_selection_df (pd.DataFrame): Plate selection data
    """
    try:
        add_selection_columns_to_database()
        update_individual_plates_selection_status(plate_selection_df)
        update_master_plate_data_selection_status(selected_wells_df)
        
    except Exception as e:
        print(f"FATAL ERROR: Could not update database with selection status: {e}")
        sys.exit()


def archive_database_and_csv_files():
    """
    Archive existing database and CSV files with timestamp suffix.
    """
    timestamp = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
    archive_dir = Path("archived_files")
    archive_dir.mkdir(exist_ok=True)
    
    # Archive database file
    db_path = Path("project_summary.db")
    if db_path.exists():
        archive_db_path = archive_dir / f"project_summary_{timestamp}.db"
        shutil.copy2(str(db_path), str(archive_db_path))
        print(f"✅ Archived database: {archive_db_path}")
    
    # Archive master_plate_data.csv
    library_csv_path = Path("master_plate_data.csv")
    if library_csv_path.exists():
        archive_csv_path = archive_dir / f"library_dataframe_{timestamp}.csv"
        shutil.move(str(library_csv_path), str(archive_csv_path))
        print(f"✅ Archived library CSV: {archive_csv_path}")
    
    # Archive individual_plates.csv
    plate_names_csv_path = Path("individual_plates.csv")
    if plate_names_csv_path.exists():
        archive_plate_csv_path = archive_dir / f"plate_names_{timestamp}.csv"
        shutil.move(str(plate_names_csv_path), str(archive_plate_csv_path))
        print(f"✅ Archived plate names CSV: {archive_plate_csv_path}")


def regenerate_csv_files():
    """
    Generate fresh CSV files from updated database tables.
    Uses ALL available columns from the SQL tables.
    """
    db_path = Path("project_summary.db")
    
    try:
        engine = create_engine(f'sqlite:///{db_path}')
        
        # Regenerate master_plate_data.csv from master_plate_data table
        master_plate_data_df = pd.read_sql('SELECT * FROM master_plate_data', engine)
        master_plate_data_df.to_csv('master_plate_data.csv', index=False)
        print(f"✅ Regenerated master_plate_data.csv with {len(master_plate_data_df)} records")

        # Regenerate individual_plates.csv from individual_plates table
        # Use ALL columns from the individual_plates table to ensure any new columns added over time are included
        individual_plates_df = pd.read_sql('SELECT * FROM individual_plates', engine)
        individual_plates_df.to_csv('individual_plates.csv', index=False)
        print(f"✅ Regenerated individual_plates.csv with {len(individual_plates_df)} records and {len(individual_plates_df.columns)} columns")
        
        engine.dispose()
        
    except Exception as e:
        print(f"FATAL ERROR: Could not regenerate CSV files: {e}")
        sys.exit()


def create_output_directory():
    """
    Create 4_plate_selection_and_pooling/ directory and A_spits_file subfolder if they don't exist.
    
    Returns:
        Path: Path to A_spits_file output directory
    """
    # Create main directory first
    main_dir = Path("4_plate_selection_and_pooling")
    main_dir.mkdir(exist_ok=True)
    
    # Create A_spits_file subfolder
    output_dir = main_dir / "A_spits_file"
    output_dir.mkdir(exist_ok=True)
    
    return output_dir


def move_plate_selection_csv(output_dir):
    """
    Move plate_selection.csv to the A_spits_file folder after SPITS file generation.
    Adds datetime suffix to the filename.
    
    Args:
        output_dir (Path): Path to A_spits_file directory
    """
    source_path = Path("4_plate_selection_and_pooling/plate_selection.csv")
    
    # Generate timestamp for filename suffix
    timestamp = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
    destination_filename = f"plate_selection_{timestamp}.csv"
    destination_path = output_dir / destination_filename
    
    if source_path.exists():
        shutil.move(str(source_path), str(destination_path))
        print(f"✅ Moved plate_selection.csv to: {destination_path}")
    else:
        print(f"⚠️  Warning: plate_selection.csv not found at {source_path}")


def main():
    """
    Main function - entry point for the script.
    Orchestrates the complete SPITS file generation workflow.
    """
    print("🧬 Starting SPITS file generation...")
    
    # Step 1: Create output directory
    output_dir = create_output_directory()
    
    # Step 2: Read database tables
    sample_metadata_df, individual_plates_df, master_plate_data_df = read_database_tables()
    
    # Step 2.5: Validate database schema
    validate_database_schema(sample_metadata_df, individual_plates_df, master_plate_data_df)

    # Step 3: Read plate selection CSV
    plate_selection_df = read_plate_selection_csv()
    
    # Step 4: Validate plates and index sets
    validate_plates_and_index_sets(plate_selection_df, individual_plates_df, master_plate_data_df)
    
    # Step 5: Select wells for SPITS processing
    selected_wells_df = select_wells_for_spits(plate_selection_df, individual_plates_df, master_plate_data_df)
    
    # Step 6: Generate SPITS CSV file
    spits_file_path = generate_spits_csv(selected_wells_df, sample_metadata_df, output_dir)
    
    # Step 6.5: Move plate_selection.csv to A_spits_file folder
    move_plate_selection_csv(output_dir)
    
    # Step 7: Archive existing files
    archive_database_and_csv_files()
    
    # Step 8: Update database with selection status
    update_database_with_selection_status(selected_wells_df, plate_selection_df)
    
    # Step 9: Regenerate CSV files
    regenerate_csv_files()
    
    print(f"✅ SPITS file generation completed successfully!")
    print(f"📄 Generated: {spits_file_path}")
    print(f"🔬 Processed {len(selected_wells_df)} wells from {len(plate_selection_df)} plates")

    # Create success marker for workflow manager
    create_success_marker()


if __name__ == "__main__":
    main()