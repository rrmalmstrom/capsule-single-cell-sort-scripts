#!/usr/bin/env python3

"""
Laboratory Barcode Label Generation Script

This script generates BarTender-compatible barcode labels for microwell plates
following laboratory safety standards with automated file detection and
simplified barcode generation system.

USAGE: python generate_barcode_labels.py

CRITICAL REQUIREMENTS:
- MUST use sip-lims conda environment
- Follows existing SPS script patterns
- Implements comprehensive error handling with "FATAL ERROR" messaging
- Creates success markers for workflow manager integration

Features:
- Automatic detection of sample metadata CSV files (sample_metadata.csv)
- is_custom column in sample metadata CSV controls which samples use custom plate layouts
- File-based input for additional standard plates (list_additional_sort_plates.txt)
- NOTE: custom_plate_names.txt file-based input is DISABLED; use is_custom column in CSV instead
- Simplified incremental barcode generation (e.g., ABC12-1, ABC12-2, ABC12-3)
- Two-table database architecture for better data organization
- Consolidated folder management with automatic creation of workflow structure
- Timestamped file movement to prevent overwrites on subsequent runs
- Smart file location detection (working directory for first runs, organized folders for subsequent runs)
- CSV file archiving and regeneration
- BarTender sort plate label file generation with reverse order (no blank separator lines)
- BarTender tube label file generation (BARTENDER_tube_labels_*.txt) for unique samples per run
- Adding new samples on subsequent runs via new_samples.csv (see below)

Adding New Samples on Subsequent Runs (new_samples.csv):
- Place a file named exactly "new_samples.csv" in the project working directory
- The file must use the same format as the original sample_metadata.csv (same required columns,
  including the is_custom column)
- The script detects the file automatically on re-run; no interactive prompt is needed
- Safety guard: the script will refuse to add new samples if downstream workflow steps
  (select_plates, process_grid_barcodes, or verify_scanning_esp) have already been completed
  in workflow_state.json — new samples must be added before those steps are run
- Overlap check: any (Proposal, Group_or_abrvSample) pair already present in the database
  will cause a FATAL ERROR; all new samples must be genuinely new
- After successful processing, new_samples.csv is archived to
  1_make_barcode_labels/previously_process_label_input_files/Additional_samples/
  with a timestamp suffix (e.g., new_samples_20240422_153012.csv)
- The full individual_plates table is replaced (not appended) so that all plates —
  old and new — are written together, preventing data truncation on future runs

Database Schema (Two-Table Architecture):
- sample_metadata table: Project and sample information
- individual_plates table: Individual plate data with barcodes
- Database file: project_summary.db

File Organization:
- Main workflow folders: 1_make_barcode_labels/, 2_library_creation/, 3_FA_analysis/
- BarTender files → 1_make_barcode_labels/bartender_barcode_labels/
- Processed input files → 1_make_barcode_labels/previously_process_label_input_files/custom_plates/ and /standard_plates/
- Additional samples archive → 1_make_barcode_labels/previously_process_label_input_files/Additional_samples/
- Archived files → archived_files/ (with timestamp suffixes)
- Updated CSV files: sample_metadata.csv and individual_plates.csv

Barcode System:
- Single base barcode per project (5-character alphanumeric)
- Incremental numbering: BASE-1, BASE-2, BASE-3, etc.
- Echo variants: eBASE-1, eBASE-2 (lowercase 'e' prefix)
- Hamilton variants: hBASE-1, hBASE-2 (lowercase 'h' prefix)
- No collision avoidance needed - simple sequential numbering

Safety Features:
- Comprehensive barcode uniqueness validation
- Laboratory-grade error messaging with "FATAL ERROR" prefix
- Automatic file archiving before updates
- Success marker creation for workflow integration
- Consistent error handling with sys.exit() (no exit codes)
- Downstream workflow step guard prevents adding new samples after plates have been selected
"""

import argparse
import json
import pandas as pd
import random
import sys
import shutil
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, text

# Constants following implementation guide
CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
LETTERS_ONLY = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
BARTENDER_HEADER = '%BTW% /AF="\\\\BARTENDER\\shared\\templates\\ECHO_BCode8.btw" /D="%Trigger File Name%" /PRN="bcode8" /R=3 /P /DD\r\n\r\n%END%\r\n\r\n\r\n'
BARTENDER_TUBE_HEADER = '%BTW% /AF="\\\\BARTENDER\\shared\\templates\\JGI_Label_BCode5.btw" /D="%Trigger File Name%" /PRN="bcode5" /R=3 /P /DD\r\n\r\n%END%\r\n\r\n\r\n'

# Database and file names
DATABASE_NAME = "project_summary.db"
BARTENDER_FILE = "BARTENDER_sort_plate_labels.txt"

# === WORKFLOW SNAPSHOT ITEMS ===
# Files and folders this script modifies, deletes, or replaces.
# The workflow manager reads this list before running the script to create
# a pre-run backup. Keep this list accurate — an incomplete list means
# incomplete rollback capability.
SNAPSHOT_ITEMS = [
    "project_summary.db",
    "sample_metadata.csv",
    "individual_plates.csv",
    "1_make_barcode_labels/",
]
# === END WORKFLOW SNAPSHOT ITEMS ===


def validate_custom_base_barcode(base_barcode):
    """
    Validate that a custom base barcode follows the expected format.
    
    Args:
        base_barcode (str): The custom base barcode to validate
        
    Returns:
        bool: True if valid, False otherwise
        
    Validation rules:
    - Must be exactly 5 characters long
    - First character must be a letter (A-Z)
    - All characters must be uppercase letters or digits
    - All characters must be from the allowed CHARSET
    """
    if not base_barcode:
        return False
    
    # Check length
    if len(base_barcode) != 5:
        return False
    
    # Check first character is a letter
    if not base_barcode[0].isalpha():
        return False
    
    # Check all characters are uppercase and from allowed charset
    if base_barcode != base_barcode.upper():
        return False
    
    # Check all characters are in the allowed charset
    for char in base_barcode:
        if char not in CHARSET:
            return False
    
    return True


def read_sample_csv(csv_path):
    """
    Read sample metadata CSV and return DataFrame with validation.
    
    Args:
        csv_path (Path): Path to the CSV file
        
    Returns:
        pd.DataFrame: Validated sample metadata
        
    Raises:
        SystemExit: If required columns are missing or file cannot be read
        FileNotFoundError: If CSV file does not exist
    """
    try:
        # Read CSV with proper encoding handling (including BOM)
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        
        # Validate required columns
        required_cols = ['Proposal', 'Group_or_abrvSample', 'Sample_full', 'Number_of_sorted_plates', 'is_custom']
        missing = [col for col in required_cols if col not in df.columns]
        
        if missing:
            print(f"FATAL ERROR: Missing required columns in CSV file: {missing}")
            print(f"Required columns: {required_cols}")
            print(f"Found columns: {list(df.columns)}")
            print("Laboratory automation requires exact column names for safety.")
            print("NOTE: 'is_custom' is now a required column. Set to True/False or 1/0 for each sample.")
            print("NOTE: 'Sample' column has been replaced by 'Group_or_abrvSample' (short/abbreviated name) and 'Sample_full' (full sample name).")
            sys.exit()
        
        # Validate data types
        try:
            df['Number_of_sorted_plates'] = df['Number_of_sorted_plates'].astype(int)
        except ValueError as e:
            print(f"FATAL ERROR: Invalid data in 'Number_of_sorted_plates' column: {e}")
            print("All values must be integers for laboratory automation safety.")
            sys.exit()
        
        # Validate and normalize is_custom column
        valid_true_values  = {'true',  '1', 'yes'}
        valid_false_values = {'false', '0', 'no'}
        valid_values = valid_true_values | valid_false_values
        
        normalized_is_custom = []
        for idx, val in enumerate(df['is_custom']):
            # Check for empty / NaN
            if pd.isna(val) or str(val).strip() == '':
                print(f"FATAL ERROR: Empty value in 'is_custom' column at row {idx + 2} (CSV row {idx + 2})")
                print("Every sample must have an explicit is_custom value: True, False, 1, or 0.")
                print("Laboratory automation requires complete metadata for safety.")
                sys.exit()
            
            str_val = str(val).strip().lower()
            if str_val not in valid_values:
                print(f"FATAL ERROR: Invalid value '{val}' in 'is_custom' column at row {idx + 2}")
                print("Accepted values: True, False, 1, 0, yes, no (case-insensitive)")
                print("Laboratory automation requires valid boolean values for safety.")
                sys.exit()
            
            normalized_is_custom.append(str_val in valid_true_values)
        
        df['is_custom'] = normalized_is_custom

        # Validate Proposal and Group_or_abrvSample: non-empty, alphanumeric only, max 8 characters
        for idx, row in df.iterrows():
            csv_row = idx + 2  # 1-based header + 1-based data row

            proposal_val = str(row['Proposal']).strip() if not pd.isna(row['Proposal']) else ''
            if not proposal_val:
                print(f"FATAL ERROR: Empty value in 'Proposal' column at row {csv_row}")
                print("Proposal must be a non-empty alphanumeric string (letters and digits only, no symbols, max 8 characters).")
                sys.exit()
            if len(proposal_val) > 8:
                print(f"FATAL ERROR: Value '{proposal_val}' in 'Proposal' column at row {csv_row} exceeds 8 characters (length: {len(proposal_val)})")
                print("Proposal must be 8 characters or fewer.")
                sys.exit()
            if not proposal_val.isalnum():
                print(f"FATAL ERROR: Invalid value '{proposal_val}' in 'Proposal' column at row {csv_row}")
                print("Proposal must contain only alphanumeric characters (letters and digits, no symbols or spaces).")
                sys.exit()

            sample_val = str(row['Group_or_abrvSample']).strip() if not pd.isna(row['Group_or_abrvSample']) else ''
            if not sample_val:
                print(f"FATAL ERROR: Empty value in 'Group_or_abrvSample' column at row {csv_row}")
                print("Group_or_abrvSample must be a non-empty alphanumeric string (letters and digits only, no symbols, max 8 characters).")
                sys.exit()
            if len(sample_val) > 8:
                print(f"FATAL ERROR: Value '{sample_val}' in 'Group_or_abrvSample' column at row {csv_row} exceeds 8 characters (length: {len(sample_val)})")
                print("Group_or_abrvSample must be 8 characters or fewer.")
                sys.exit()
            if not sample_val.isalnum():
                print(f"FATAL ERROR: Invalid value '{sample_val}' in 'Group_or_abrvSample' column at row {csv_row}")
                print("Group_or_abrvSample must contain only alphanumeric characters (letters and digits, no symbols or spaces).")
                sys.exit()

        print(f"✅ Read {len(df)} samples from CSV file")
        return df
        
    except FileNotFoundError:
        print(f"FATAL ERROR: CSV file not found: {csv_path}")
        print("Laboratory automation requires valid input files for safety.")
        raise
    except Exception as e:
        print(f"FATAL ERROR: Could not read CSV file {csv_path}: {e}")
        print("Laboratory automation requires valid CSV format for safety.")
        sys.exit()


def make_plate_names(sample_df):
    """
    Generate standard plate names from sample data.
    
    Args:
        sample_df (pd.DataFrame): Sample metadata DataFrame
        
    Returns:
        pd.DataFrame: DataFrame with plate names and metadata
    """
    plates = []
    
    for _, row in sample_df.iterrows():
        proposal = row['Proposal']
        sample = row['Group_or_abrvSample']
        num_plates = int(row['Number_of_sorted_plates'])
        is_custom = bool(row['is_custom'])
        
        # Generate plate names for each sample
        for i in range(1, num_plates + 1):
            plates.append({
                'plate_name': f"{proposal}_{sample}.{i}",
                'project': proposal,
                'sample': sample,
                'plate_number': i,
                'is_custom': is_custom
            })
    
    result_df = pd.DataFrame(plates)
    print(f"✅ Generated {len(result_df)} standard plates")
    return result_df


def generate_simple_barcodes(plates_df, existing_individual_plates_df=None, custom_base_barcode=None):
    """
    Generate simplified incremental barcodes for all plates.
    
    Args:
        plates_df (pd.DataFrame): DataFrame of plates needing barcodes
        existing_individual_plates_df (pd.DataFrame, optional): Existing individual plates to continue numbering
        custom_base_barcode (str, optional): Custom base barcode to use instead of generating random one
        
    Returns:
        pd.DataFrame: DataFrame with generated barcodes
        
    Raises:
        SystemExit: If barcode generation fails
    """
    try:
        # Determine base barcode and starting number
        start_number = 1
        base_barcode = None
        
        if existing_individual_plates_df is not None and len(existing_individual_plates_df) > 0:
            # Extract existing base barcode from first existing barcode
            first_barcode = existing_individual_plates_df['barcode'].iloc[0]
            if '-' in str(first_barcode):
                base_barcode = str(first_barcode).split('-')[0]
                # Reuse existing base barcode
            
            # Find the highest existing barcode number to continue from
            existing_numbers = []
            for barcode in existing_individual_plates_df['barcode']:
                if '-' in str(barcode):
                    try:
                        number = int(str(barcode).split('-')[-1])
                        existing_numbers.append(number)
                    except ValueError:
                        continue
            
            if existing_numbers:
                start_number = max(existing_numbers) + 1
                # Continue numbering from existing plates
        
        # Generate new base barcode only if no existing plates
        if base_barcode is None:
            if custom_base_barcode:
                # Use provided custom base barcode
                if not validate_custom_base_barcode(custom_base_barcode):
                    print(f"FATAL ERROR: Invalid custom base barcode '{custom_base_barcode}'")
                    print("Custom base barcode must be exactly 5 characters:")
                    print("- First character must be a letter (A-Z)")
                    print("- All characters must be uppercase letters or digits")
                    print("- Example: REX12, ABCD1, TEST9")
                    print("Laboratory automation requires valid barcode format for safety.")
                    sys.exit()
                base_barcode = custom_base_barcode.upper()
                print(f"Using custom base barcode: '{base_barcode}'")
            else:
                # Generate random base barcode
                # First character must be a letter, remaining 4 can be letters or numbers
                first_char = random.choice(LETTERS_ONLY)
                remaining_chars = ''.join(random.choices(CHARSET, k=4))
                base_barcode = first_char + remaining_chars
                print(f"Generated base barcode: '{base_barcode}'")
        
        # Assign incremental barcodes to all plates
        for i, idx in enumerate(plates_df.index):
            barcode_number = start_number + i
            full_barcode = f"{base_barcode}-{barcode_number}"
            
            plates_df.at[idx, 'barcode'] = full_barcode
            plates_df.at[idx, 'created_timestamp'] = datetime.now().isoformat()
        
        print(f"✅ Generated {len(plates_df)} barcodes: {base_barcode}-{start_number} to {base_barcode}-{start_number + len(plates_df) - 1}")
        
        return plates_df
        
    except Exception as e:
        print(f"FATAL ERROR: Could not generate barcodes: {e}")
        print("Laboratory automation requires reliable barcode generation for safety.")
        sys.exit()


def generate_barcodes(plates_df, existing_df=None, custom_base_barcode=None):
    """
    Wrapper function for backward compatibility.
    Calls the new simplified barcode generation system.
    """
    return generate_simple_barcodes(plates_df, existing_df, custom_base_barcode)


def validate_barcode_uniqueness(df):
    """
    Validate that all barcodes in DataFrame are unique.
    
    Args:
        df (pd.DataFrame): DataFrame with barcode column
        
    Returns:
        bool: True if all barcodes are unique, False otherwise
    """
    if 'barcode' not in df.columns:
        print("WARNING: No 'barcode' column found for validation")
        return True
    
    barcodes = df['barcode'].tolist()
    unique_barcodes = set(barcodes)
    
    is_unique = len(barcodes) == len(unique_barcodes)
    
    if not is_unique:
        duplicates = [barcode for barcode in unique_barcodes if barcodes.count(barcode) > 1]
        print(f"Duplicate barcodes found: {duplicates}")
    
    return is_unique


def save_to_two_table_database(sample_metadata_df, individual_plates_df, db_path):
    """
    Save DataFrames to two-table SQLite database using SQLAlchemy.
    
    Args:
        sample_metadata_df (pd.DataFrame): Sample metadata DataFrame
        individual_plates_df (pd.DataFrame): Individual plates DataFrame
        db_path (Path): Path to database file
        
    Raises:
        SystemExit: If database operation fails
    """
    try:
        engine = create_engine(f'sqlite:///{db_path}')
        
        # Save both tables with replace to handle updates
        sample_metadata_df.to_sql('sample_metadata', engine, if_exists='replace', index=False)
        individual_plates_df.to_sql('individual_plates', engine, if_exists='replace', index=False)
        
        # Properly dispose of engine
        engine.dispose()
        
        print(f"✅ Saved to database: {len(sample_metadata_df)} samples, {len(individual_plates_df)} plates")
        
    except Exception as e:
        print(f"FATAL ERROR: Could not save to database {db_path}: {e}")
        print("Laboratory automation requires reliable data storage for safety.")
        sys.exit()


def save_to_database_smart(sample_metadata_df, new_plates_df, db_path, is_first_run, existing_sample_df=None):
    """
    Smart database save that only updates tables that actually need updating.
    Preserves all unknown tables by only touching specific tables.
    
    Args:
        sample_metadata_df (pd.DataFrame): Sample metadata DataFrame
        new_plates_df (pd.DataFrame): NEW plates DataFrame (not all plates)
        db_path (Path): Path to database file
        is_first_run (bool): True for first runs, False for subsequent runs
        existing_sample_df (pd.DataFrame, optional): Existing sample metadata for comparison
        
    Raises:
        SystemExit: If database operation fails
    """
    try:
        engine = create_engine(f'sqlite:///{db_path}')
        
        if is_first_run:
            # First run: create both tables fresh
            sample_metadata_df.to_sql('sample_metadata', engine, if_exists='replace', index=False)
            new_plates_df.to_sql('individual_plates', engine, if_exists='replace', index=False)
            print(f"✅ Created database: {len(sample_metadata_df)} samples, {len(new_plates_df)} plates")
        else:
            # Subsequent run: only update what actually changes
            sample_updated = False
            
            # Check if sample metadata actually changed
            if existing_sample_df is not None and sample_metadata_df.equals(existing_sample_df):
                # Sample metadata unchanged - skip update
                pass
            else:
                # Sample metadata changed - update it
                sample_metadata_df.to_sql('sample_metadata', engine, if_exists='replace', index=False)
                sample_updated = True
            
            # Always append new plates (this is the main purpose of subsequent runs)
            if not new_plates_df.empty:
                new_plates_df.to_sql('individual_plates', engine, if_exists='append', index=False)
            
            # Summary
            print(f"\n✅ Database updated successfully")
        
        # Properly dispose of engine
        engine.dispose()
        
    except Exception as e:
        print(f"FATAL ERROR: Could not save to database {db_path}: {e}")
        print("Laboratory automation requires reliable data storage for safety.")
        sys.exit()


def save_to_database(sample_metadata_df, individual_plates_df, db_path):
    """
    Save DataFrames to two-table SQLite database using SQLAlchemy.
    
    Args:
        sample_metadata_df (pd.DataFrame): Sample metadata DataFrame
        individual_plates_df (pd.DataFrame): Individual plates DataFrame
        db_path (Path): Path to database file
        
    Raises:
        SystemExit: If database operation fails
    """
    return save_to_two_table_database(sample_metadata_df, individual_plates_df, db_path)


def read_from_two_table_database(db_path):
    """
    Read DataFrames from two-table SQLite database using SQLAlchemy.
    
    Args:
        db_path (Path): Path to database file
        
    Returns:
        tuple: (sample_metadata_df, individual_plates_df) or (None, None) if file doesn't exist
        
    Raises:
        SystemExit: If database read fails unexpectedly
    """
    if not Path(db_path).exists():
        return None, None
    
    try:
        engine = create_engine(f'sqlite:///{db_path}')
        
        # Check if tables exist
        with engine.connect() as conn:
            # Check for new two-table format
            try:
                sample_metadata_df = pd.read_sql('SELECT * FROM sample_metadata', conn)
                individual_plates_df = pd.read_sql('SELECT * FROM individual_plates', conn)
                engine.dispose()
                
                # Database read successfully
                return sample_metadata_df, individual_plates_df
                
            except Exception:
                # Tables don't exist - might be old single-table format
                engine.dispose()
                return None, None
        
    except Exception as e:
        print(f"FATAL ERROR: Could not read from database {db_path}: {e}")
        print("Laboratory automation requires reliable data access for safety.")
        sys.exit()


def read_from_database(db_path):
    """
    Read DataFrames from two-table SQLite database using SQLAlchemy.
    
    Args:
        db_path (Path): Path to database file
        
    Returns:
        tuple: (sample_metadata_df, individual_plates_df) or (None, None) if file doesn't exist
        
    Raises:
        SystemExit: If database read fails unexpectedly
    """
    return read_from_two_table_database(db_path)


def make_bartender_file(df, output_path):
    """
    Generate BarTender sort plate label file with simplified barcode system.
    Format: Reverse order (highest to lowest), one line per plate with barcode and plate name.
    No blank separator lines between plates.
    
    Args:
        df (pd.DataFrame): DataFrame with barcode data (must have 'barcode' and 'plate_name' columns)
        output_path (Path): Path for output file
        
    Raises:
        SystemExit: If file creation fails
    """
    try:
        with open(output_path, 'w', newline='') as f:
            # Write header
            f.write(BARTENDER_HEADER)
            
            # Sort by barcode number in reverse order (highest first)
            # Extract number from barcode (e.g., "W91ZL-15" -> 15)
            df_sorted = df.copy()
            df_sorted['barcode_num'] = df_sorted['barcode'].str.split('-').str[1].astype(int)
            df_sorted = df_sorted.sort_values('barcode_num', ascending=False)
            
            # Group plates by sample (project + sample combination) to insert blank
            # separator lines between each sample's set of plates
            df_sorted['sample_group'] = df_sorted['project'].astype(str) + '_' + df_sorted['sample'].astype(str)
            sample_groups = df_sorted['sample_group'].unique()
            
            first_group = True
            for group in sample_groups:
                group_rows = df_sorted[df_sorted['sample_group'] == group]
                
                # Add blank separator line between sample groups (not before the first group)
                if not first_group:
                    f.write(',\r\n')
                first_group = False
                
                # Write all plates for this sample group
                for _, row in group_rows.iterrows():
                    barcode = row['barcode']
                    plate_name = row['plate_name']
                    f.write(f'{barcode},"{plate_name}"\r\n')
            
            # Add 3 trailing blank labels for BarTender compatibility
            for _ in range(3):
                f.write(',\r\n')
            f.write('\r\n')
        
        # BarTender file created silently
        
    except Exception as e:
        print(f"FATAL ERROR: Could not create BarTender file {output_path}: {e}")
        print("Laboratory automation requires valid label files for safety.")
        sys.exit()


def make_bartender_tube_labels_file(df, output_path):
    """
    Generate BarTender tube label file for unique samples in the new plates.
    Format: For each unique Proposal+Group_or_abrvSample combination (in descending order),
    write 3 lines representing SPC_PTA (70%EtOH), SPC (60%Glycerol), and Cells (10%Glycerol) tubes.
    No blank separator lines between label groups.
    Uses JGI_Label_BCode5.btw template and bcode5 printer.
    
    Args:
        df (pd.DataFrame): DataFrame with plate data (must have 'project', 'sample' columns)
        output_path (Path): Path for output file
        
    Raises:
        SystemExit: If file creation fails
    """
    try:
        with open(output_path, 'w', newline='') as f:
            # Write tube label header
            f.write(BARTENDER_TUBE_HEADER)
            
            # Get unique Proposal+Group_or_abrvSample combinations from new plates,
            # ordered to match the sort plate label file (descending by max barcode number).
            # Extract the max barcode number per sample group to determine sort order.
            df_with_num = df.copy()
            df_with_num['barcode_num'] = df_with_num['barcode'].str.split('-').str[1].astype(int)
            sample_max_barcode = df_with_num.groupby(['project', 'sample'])['barcode_num'].max().reset_index()
            sample_max_barcode = sample_max_barcode.sort_values('barcode_num', ascending=False)
            unique_samples = sample_max_barcode[['project', 'sample']]
            
            # Write 3 label lines per unique sample with blank separator lines between groups.
            # The blank separator line has 6 commas to match the 7-field tube label format.
            first_group = True
            for _, row in unique_samples.iterrows():
                proposal = row['project']
                sample = row['sample']
                combined = f"{proposal}_{sample}"
                
                # Add blank separator line between sample groups (not before the first group)
                if not first_group:
                    f.write(',,,,,,\r\n')
                first_group = False
                
                # Three tube labels per sample: SPC_PTA, SPC, Cells (descending _3, _2, _1)
                f.write(f'{combined},{proposal},{sample},SPC_PTA,70%EtOH,,{sample}_3\r\n')
                f.write(f'{combined},{proposal},{sample},SPC,60%Glycerol,,{sample}_2\r\n')
                f.write(f'{combined},{proposal},{sample},Cells,10%Glycerol,,{sample}_1\r\n')
            
            # Add 3 trailing blank labels for BarTender compatibility
            for _ in range(3):
                f.write(',,,,,,\r\n')
            f.write('\r\n')
        
        # BarTender tube label file created silently
        
    except Exception as e:
        print(f"FATAL ERROR: Could not create BarTender tube label file {output_path}: {e}")
        print("Laboratory automation requires valid label files for safety.")
        sys.exit()


def detect_sample_metadata_csv():
    """
    Detect and validate sample metadata CSV file in working directory.
    
    Returns:
        Path: Valid sample metadata CSV file path
        
    Raises:
        SystemExit: If no valid sample metadata CSV found
    """
    # Complete list of expected headers from sample_metadata.csv format
    expected_headers = [
        'Proposal', 'Group_or_abrvSample', 'Sample_full', 'Collection Year', 'Collection Month',
        'Collection Day', 'Sample Isolated From', 'Latitude', 'Longitude',
        'Depth (m)', 'Elevation (m)', 'Country', 'Number_of_sorted_plates'
    ]
    
    # Required subset for processing
    required_headers = ['Proposal', 'Group_or_abrvSample', 'Number_of_sorted_plates']
    
    # Look for sample_metadata.csv specifically first
    sample_metadata_file = Path('sample_metadata.csv')
    if sample_metadata_file.exists():
        try:
            df = pd.read_csv(sample_metadata_file, encoding='utf-8-sig')
            
            # Check for all expected headers
            missing_expected = [col for col in expected_headers if col not in df.columns]
            if missing_expected:
                print(f"⚠️  Sample metadata CSV missing some expected columns: {missing_expected}")
            
            # Check for required headers
            missing_required = [col for col in required_headers if col not in df.columns]
            if missing_required:
                print(f"FATAL ERROR: Sample metadata CSV missing required columns: {missing_required}")
                print(f"Required columns: {required_headers}")
                print("Laboratory automation requires exact column names for safety.")
                sys.exit()
            
            print(f"✅ Found valid sample metadata CSV: {sample_metadata_file}")
            return sample_metadata_file
            
        except Exception as e:
            print(f"FATAL ERROR: Could not read sample metadata CSV {sample_metadata_file}: {e}")
            print("Laboratory automation requires valid CSV format for safety.")
            sys.exit()
    
    # If sample_metadata.csv doesn't exist, search for other CSV files
    csv_files = [f for f in Path('.').glob('*.csv') if f.name != 'sample_metadata.csv']
    
    if not csv_files:
        print("FATAL ERROR: No sample metadata CSV file found in working directory")
        print("Expected: 'sample_metadata.csv' or other CSV with required headers")
        print(f"Required columns: {required_headers}")
        print("Laboratory automation requires valid input files for safety.")
        sys.exit()
    
    # Check all CSV files for validity first
    valid_csv_files = []
    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file, encoding='utf-8-sig')
            
            # Check for required headers
            missing_required = [col for col in required_headers if col not in df.columns]
            if not missing_required:
                valid_csv_files.append(csv_file)
                
        except Exception as e:
            print(f"⚠️  Skipping invalid CSV file {csv_file}: {e}")
            continue
    
    # Check if we found multiple valid CSV files
    if len(valid_csv_files) > 1:
        print("FATAL ERROR: Multiple valid sample metadata CSV files found in working directory")
        print("Found valid CSV files:")
        for csv_file in valid_csv_files:
            print(f"  - {csv_file}")
        print("Laboratory automation requires exactly one sample metadata CSV file for safety.")
        print("Please ensure only one valid CSV file exists in the working directory.")
        sys.exit()
    
    # Check if we found exactly one valid CSV file
    if len(valid_csv_files) == 1:
        print(f"✅ Found valid sample metadata CSV: {valid_csv_files[0]}")
        return valid_csv_files[0]
    
    # No valid CSV found
    print("FATAL ERROR: No valid sample metadata CSV file found in working directory")
    print(f"Required columns: {required_headers}")
    print("Laboratory automation requires valid input files for safety.")
    sys.exit()


def get_csv_file():
    """
    Get CSV file path using automatic detection.
    """
    return detect_sample_metadata_csv()


# ---------------------------------------------------------------------------
# New-samples-on-subsequent-run helpers
# ---------------------------------------------------------------------------

def detect_new_samples_csv():
    """
    Detect a 'new_samples.csv' file in the working directory.

    The file is optional — its absence simply means no new samples are being
    added this run.  Its presence is treated as the user's intent to add new
    samples without any interactive prompt.

    Returns:
        Path or None: Path to new_samples.csv if found, None if not present.

    Raises:
        SystemExit: If multiple files matching 'new_samples*.csv' are found,
                    which would be ambiguous and unsafe.
    """
    # Look for the canonical filename first
    canonical = Path('new_samples.csv')

    # Also search for any variant names to catch accidental duplicates
    candidates = list(Path('.').glob('new_samples*.csv'))
    # Filter to actual files (not directories)
    candidates = [f for f in candidates if f.is_file()]

    if len(candidates) > 1:
        print("FATAL ERROR: Multiple 'new_samples*.csv' files found in the working directory.")
        print("Found files:")
        for f in candidates:
            print(f"  - {f}")
        print("Laboratory automation requires exactly one new samples file for safety.")
        print("Please ensure only 'new_samples.csv' exists in the working directory.")
        sys.exit()

    if canonical.exists():
        print(f"✅ Found new samples CSV: {canonical}")
        return canonical

    return None


def check_downstream_steps_not_run():
    """
    Verify that no downstream workflow steps have been completed before
    allowing new samples to be added.

    Reads 'workflow_state.json' from the project root (same directory as
    project_summary.db).  If any step at or after Script 4 (select_plates)
    has status 'completed', the script exits with a FATAL ERROR instructing
    the user to roll back via the workflow manager first.

    Scripts 2 (prep_library) and 3 (analyze_quality) are re-runnable by
    design (allow_rerun: true in CapsuleSorting_workflow.yml), so new samples
    can safely be added even after those steps have completed.

    If workflow_state.json does not exist (e.g. the workflow manager has not
    been used), a warning is printed but the script is NOT blocked — the user
    is assumed to know what they are doing.

    Raises:
        SystemExit: If any downstream step (Script 4+) is already completed.
    """
    state_file = Path('workflow_state.json')

    if not state_file.exists():
        print("⚠️  WARNING: workflow_state.json not found in project root.")
        print("   Cannot verify downstream step status. Proceeding with caution.")
        print("   If downstream steps (select_plates, etc.) have already run,")
        print("   adding new samples now may produce inconsistent results.")
        return

    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
    except Exception as e:
        print(f"⚠️  WARNING: Could not read workflow_state.json: {e}")
        print("   Cannot verify downstream step status. Proceeding with caution.")
        return

    # Steps that must NOT be completed before new samples can be added.
    # Scripts 1-3 are re-runnable (allow_rerun: true); Scripts 4-6 are not.
    downstream_steps = [
        'select_plates',          # Script 4 — create_capsule_spits.py
        'process_grid_barcodes',  # Script 5 — process_grid_tables_and_generate_barcodes.py
        'verify_scanning_esp',    # Script 6 — verify_scanning_and_generate_ESP_files.py
    ]

    completed_downstream = [
        step for step in downstream_steps
        if state.get(step) == 'completed'
    ]

    if completed_downstream:
        print("FATAL ERROR: Cannot add new samples — downstream workflow steps have already been completed.")
        print("Completed downstream steps:")
        for step in completed_downstream:
            print(f"  - {step}")
        print("")
        print("Adding new samples after Scripts 4-6 have run would produce")
        print("inconsistent results (missing SPITS data, missing ESP files, etc.).")
        print("")
        print("To add new samples, you must first roll back the workflow to the")
        print("'init_project' step using the workflow manager, then re-run")
        print("the affected downstream steps for all samples (old and new).")
        print("Laboratory automation requires consistent data for safety.")
        sys.exit()


def validate_new_samples_against_existing(new_samples_csv_path, existing_sample_df):
    """
    Validate new sample rows against the existing database samples.

    Applies the same full validation used on first-run CSVs (via
    read_sample_csv()), then performs a cross-check to ensure none of
    the new (Proposal, Group_or_abrvSample) pairs already exist in the
    database.

    Args:
        new_samples_csv_path (Path): Path to new_samples.csv.
        existing_sample_df (pd.DataFrame): Existing sample_metadata from the database.

    Returns:
        pd.DataFrame: Validated new sample DataFrame (with is_custom normalized,
                      Number_of_sorted_plates cast to int).

    Raises:
        SystemExit: On any validation failure or overlap with existing samples.
    """
    # --- Full validation via read_sample_csv (same rules as first run) ---
    # This validates: required columns, is_custom values, Proposal/Group length,
    # alphanumeric constraints, and Number_of_sorted_plates as int.
    new_df = read_sample_csv(new_samples_csv_path)

    # --- Cross-check: no (Proposal, Group_or_abrvSample) overlap with existing DB ---
    existing_pairs = set(
        zip(
            existing_sample_df['Proposal'].astype(str),
            existing_sample_df['Group_or_abrvSample'].astype(str),
        )
    )

    overlapping = []
    for _, row in new_df.iterrows():
        pair = (str(row['Proposal']), str(row['Group_or_abrvSample']))
        if pair in existing_pairs:
            overlapping.append(f"{row['Proposal']}_{row['Group_or_abrvSample']}")

    if overlapping:
        print("FATAL ERROR: The following samples in 'new_samples.csv' already exist in the database:")
        for s_name in overlapping:
            print(f"  - {s_name}")
        print("")
        print("'new_samples.csv' must contain ONLY new samples not previously registered.")
        print("Do NOT include existing samples in this file — they are already in the database.")
        print("Laboratory automation requires unique sample identifiers for safety.")
        sys.exit()

    print(f"✅ Validated {len(new_df)} new sample row(s) — no overlap with existing {len(existing_sample_df)} sample(s)")
    return new_df


def read_custom_plates_file(is_first_run=True):
    """
    Read custom plate names from 'custom_plate_names.txt' file.
    
    NOTE: This function is DISABLED. Custom plate designation is now controlled
    by the 'is_custom' column in the sample metadata CSV file (sample_metadata.csv).
    Set is_custom=True for any sample whose plates require a custom layout file.
    
    This function is preserved here for reference and potential future re-enablement.
    To re-enable file-based custom plate input, restore the body below and update
    get_custom_plates() and the process_first_run() / process_subsequent_run() callers.
    
    Args:
        is_first_run (bool): True for first runs (look in working directory),
                            False for subsequent runs (look in 1_make_barcode_labels folder)
    
    Returns:
        list: Always returns empty list (feature disabled)
    """
    # --- CUSTOM PLATE FILE INPUT DISABLED ---
    # Custom plates are now designated via the 'is_custom' column in sample_metadata.csv.
    # The original file-reading implementation is preserved below for reference.
    #
    # if is_first_run:
    #     search_dir = Path('.')
    #     custom_file = Path('custom_plate_names.txt')
    #     location_desc = "working directory"
    # else:
    #     search_dir = Path('1_make_barcode_labels')
    #     custom_file = Path('1_make_barcode_labels/custom_plate_names.txt')
    #     location_desc = "1_make_barcode_labels folder"
    #
    # custom_files = list(search_dir.glob('*custom*plate*names*.txt'))
    # custom_files.extend(search_dir.glob('custom_plate_names.txt'))
    # custom_files.extend(search_dir.glob('*custom*plates*.txt'))
    # custom_files = list(set([f for f in custom_files if f.is_file()]))
    #
    # if len(custom_files) > 1:
    #     print(f"FATAL ERROR: Multiple custom plate files found in {location_desc}")
    #     ...
    #     sys.exit()
    #
    # if not custom_file.exists():
    #     print(f"FATAL ERROR: Custom plates requested but 'custom_plate_names.txt' not found")
    #     ...
    #     sys.exit()
    #
    # try:
    #     with open(custom_file, 'r', encoding='utf-8') as f:
    #         lines = f.readlines()
    #     plates = []
    #     for line_num, line in enumerate(lines, 1):
    #         name = line.strip()
    #         if not name:
    #             continue
    #         if len(name) >= 20:
    #             print(f"FATAL ERROR: Custom plate name too long on line {line_num}: {name}")
    #             sys.exit()
    #         plates.append(name)
    #     if plates:
    #         print(f"✅ Read {len(plates)} custom plate names from {custom_file}")
    #     return plates
    # except Exception as e:
    #     print(f"FATAL ERROR: Could not read custom plates file {custom_file}: {e}")
    #     sys.exit()

    return []


def read_additional_standard_plates_file(is_first_run=True):
    """
    Read additional standard plates from 'list_additional_sort_plates.txt'.
    Location depends on whether this is a first run or subsequent run.
    
    Args:
        is_first_run (bool): True for first runs (look in working directory),
                            False for subsequent runs (look in 1_make_barcode_labels folder)
    
    Returns:
        dict: Mapping of sample_id to additional plate count
        
    Raises:
        SystemExit: If file format is invalid or multiple additional plate files found
    """
    # Determine where to look for input files based on run type
    if is_first_run:
        # First run: look in working directory
        search_dir = Path('.')
        additional_file = Path('list_additional_sort_plates.txt')
        location_desc = "working directory"
    else:
        # Subsequent run: look in 1_make_barcode_labels folder
        search_dir = Path('1_make_barcode_labels')
        additional_file = Path('1_make_barcode_labels/list_additional_sort_plates.txt')
        location_desc = "1_make_barcode_labels folder"
    
    # Check for multiple additional plate files in search directory
    additional_files = list(search_dir.glob('list_additional_sort_plates.txt'))
    additional_files.extend(search_dir.glob('*additional*sort*plates*.txt'))
    additional_files.extend(search_dir.glob('*list*additional*plates*.txt'))
    
    # Remove duplicates and filter to actual files
    additional_files = list(set([f for f in additional_files if f.is_file()]))
    
    if len(additional_files) > 1:
        print(f"FATAL ERROR: Multiple additional sort plate files found in {location_desc}")
        print("Found additional plate files:")
        for additional_file_found in additional_files:
            print(f"  - {additional_file_found}")
        print("Laboratory automation requires exactly one additional plate file for safety.")
        print(f"Please ensure only 'list_additional_sort_plates.txt' exists in the {location_desc}.")
        sys.exit()
    
    if not additional_file.exists():
        print(f"FATAL ERROR: Additional sort plates requested but 'list_additional_sort_plates.txt' file not found in {location_desc}")
        print("")
        print("To fix this error:")
        if is_first_run:
            print("1. Create a file named 'list_additional_sort_plates.txt' in the working directory")
        else:
            print("1. Create a file named 'list_additional_sort_plates.txt' in the 1_make_barcode_labels folder")
        print("2. Add one entry per line in format: PROJECT_SAMPLE:COUNT")
        print("3. Example file content:")
        print("   BP9735_SitukAM:2")
        print("   BP9735_WCBP1PR:1")
        print("4. This means add 2 more plates to BP9735_SitukAM and 1 more to BP9735_WCBP1PR")
        print("")
        print("Laboratory automation requires valid input files for safety.")
        sys.exit()
    
    try:
        with open(additional_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        additional_plates = {}
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:  # Skip empty lines
                continue
            
            # Parse format: "BP9735_SitukAM:2"
            if ':' not in line:
                print(f"FATAL ERROR: Invalid format on line {line_num}: {line}")
                print("Expected format: 'PROJECT_SAMPLE:COUNT' (e.g., 'BP9735_SitukAM:2')")
                print("Laboratory automation requires valid file formats for safety.")
                sys.exit()
            
            try:
                sample_id, count_str = line.split(':', 1)
                count = int(count_str)
                
                if count <= 0:
                    print(f"FATAL ERROR: Invalid plate count on line {line_num}: {count}")
                    print("Plate count must be positive integer.")
                    print("Laboratory automation requires valid data for safety.")
                    sys.exit()
                
                additional_plates[sample_id.strip()] = count
                
            except ValueError as e:
                print(f"FATAL ERROR: Invalid format on line {line_num}: {line}")
                print(f"Error: {e}")
                print("Laboratory automation requires valid file formats for safety.")
                sys.exit()
        
        if additional_plates:
            print(f"✅ Read additional sort plates for {len(additional_plates)} samples from {additional_file}")
        
        return additional_plates
        
    except Exception as e:
        print(f"FATAL ERROR: Could not read additional sort plates file {additional_file}: {e}")
        print("Laboratory automation requires valid input files for safety.")
        sys.exit()


def get_additional_standard_plates(is_first_run=True):
    """
    Interactive function to ask user if they want additional sort plates and read from file.
    
    Additional sort plates file format (list_additional_sort_plates.txt):
    - One entry per line
    - Format: PROJECT_SAMPLE:COUNT
    - Example format:
        BP9735_SitukAM:2
        BP9735_WCBP1PR:1
    - This means add 2 more plates to BP9735_SitukAM and 1 more plate to BP9735_WCBP1PR
    
    Args:
        is_first_run (bool): True for first runs, False for subsequent runs
    
    Returns:
        dict: Mapping of sample_id to additional plate count, or empty dict if user declines
    """
    # Ask user interactively
    while True:
        response = input("Add additional sort plates to existing samples? (y/n): ").lower().strip()
        if response in ['y', 'yes']:
            # User wants additional sort plates - look for file
            print("Looking for 'list_additional_sort_plates.txt' file...")
            return read_additional_standard_plates_file(is_first_run)
        elif response in ['n', 'no']:
            # User doesn't want additional sort plates
            return {}
        else:
            print("Please enter 'y' for yes or 'n' for no.")


def get_custom_plates(is_first_run=True):
    """
    Interactive function to ask user if they want custom plates and read from file.
    
    NOTE: This interactive prompt is DISABLED. Custom plate designation is now
    controlled by the 'is_custom' column in the sample metadata CSV file.
    Users set is_custom=True/False for each sample directly in sample_metadata.csv.
    
    This function is preserved for reference and potential future re-enablement.
    To re-enable, restore the while loop below and update the callers in
    process_first_run() and process_subsequent_run().
    
    Args:
        is_first_run (bool): True for first runs, False for subsequent runs
    
    Returns:
        list: Always returns empty list (feature disabled)
    """
    # --- CUSTOM PLATES INTERACTIVE PROMPT DISABLED ---
    # Custom plates are now designated via the 'is_custom' column in sample_metadata.csv.
    # The original interactive implementation is preserved below for reference.
    #
    # while True:
    #     response = input("Add custom plates? (y/n): ").lower().strip()
    #     if response in ['y', 'yes']:
    #         print("Looking for 'custom_plate_names.txt' file...")
    #         return read_custom_plates_file(is_first_run)
    #     elif response in ['n', 'no']:
    #         return []
    #     else:
    #         print("Please enter 'y' for yes or 'n' for no.")
    return []


def create_project_folder_structure():
    """
    Create the standardized project folder structure.
    
    Creates the following folders if they don't exist:
    - 1_make_barcode_labels/
    - 2_library_creation/
    - 3_FA_analysis/
    - 4_plate_selection_and_pooling/
    - archived_files/
    - 1_make_barcode_labels/bartender_barcode_labels/
    - 1_make_barcode_labels/previously_process_label_input_files/
    - 1_make_barcode_labels/previously_process_label_input_files/custom_plates/
    - 1_make_barcode_labels/previously_process_label_input_files/standard_plates/
    
    Returns:
        dict: Dictionary with folder paths for easy access
        
    Raises:
        SystemExit: If folder creation fails
    """
    try:
        # Main workflow folders
        folders = {
            'make_barcode_labels': Path("1_make_barcode_labels"),
            'library_creation': Path("2_library_creation"),
            'fa_analysis': Path("3_FA_analysis"),
            'plate_selection_and_pooling': Path("4_plate_selection_and_pooling"),
            'archived_files': Path("archived_files"),
        }
        
        # Track which folders were actually created
        created_folders = []
        
        # Create main folders
        for folder_name, folder_path in folders.items():
            if not folder_path.exists():
                created_folders.append(str(folder_path))
            folder_path.mkdir(exist_ok=True)
        
        # Create MISC folder if no folder with that name (case-insensitive) already exists
        existing_names_lower = {p.name.lower() for p in Path('.').iterdir() if p.is_dir()}
        if 'misc' not in existing_names_lower:
            misc_dir = Path("MISC")
            misc_dir.mkdir(exist_ok=True)
            created_folders.append(str(misc_dir))
            folders['misc'] = misc_dir
        else:
            # Point to whichever existing folder matches (case-insensitive)
            misc_existing = next(p for p in Path('.').iterdir() if p.is_dir() and p.name.lower() == 'misc')
            folders['misc'] = misc_existing
        
        # Create subfolder structure for barcode labels
        bartender_dir = folders['make_barcode_labels'] / "bartender_barcode_labels"
        if not bartender_dir.exists():
            created_folders.append(str(bartender_dir))
        bartender_dir.mkdir(exist_ok=True)
        
        label_input_dir = folders['make_barcode_labels'] / "previously_process_label_input_files"
        if not label_input_dir.exists():
            created_folders.append(str(label_input_dir))
        label_input_dir.mkdir(exist_ok=True)
        
        custom_plates_dir = label_input_dir / "custom_plates"
        standard_plates_dir = label_input_dir / "standard_plates"
        additional_samples_dir = label_input_dir / "Additional_samples"
        if not custom_plates_dir.exists():
            created_folders.append(str(custom_plates_dir))
        if not standard_plates_dir.exists():
            created_folders.append(str(standard_plates_dir))
        if not additional_samples_dir.exists():
            created_folders.append(str(additional_samples_dir))
        custom_plates_dir.mkdir(exist_ok=True)
        standard_plates_dir.mkdir(exist_ok=True)
        additional_samples_dir.mkdir(exist_ok=True)
        
        # Add subfolder paths to the dictionary
        folders['bartender_labels'] = bartender_dir
        folders['label_input_files'] = label_input_dir
        folders['custom_plates'] = custom_plates_dir
        folders['standard_plates'] = standard_plates_dir
        folders['additional_samples'] = additional_samples_dir
        
        # Only print if folders were actually created
        if created_folders:
            print(f"✅ Created {len(created_folders)} new project folders")
        
        return folders
        
    except Exception as e:
        print(f"FATAL ERROR: Could not create project folder structure: {e}")
        print("Laboratory automation requires proper folder organization for safety.")
        sys.exit()


def create_success_marker():
    """
    Create success marker file for workflow manager integration.
    
    Raises:
        SystemExit: If marker creation fails
    """
    try:
        script_name = Path(__file__).stem
        status_dir = Path(".workflow_status")
        status_dir.mkdir(exist_ok=True)
        success_file = status_dir / f"{script_name}.success"
        
        with open(success_file, "w") as f:
            f.write(f"SUCCESS: {script_name} completed at {datetime.now()}\n")
        
        print(f"✅ Success marker created: {success_file}")
        
    except Exception as e:
        print(f"FATAL ERROR: Could not create success marker: {e}")
        print("Laboratory automation requires workflow integration for safety.")
        sys.exit()


def archive_database_file(db_path, folders):
    """
    Archive database file with timestamp as suffix by copying (not moving).
    This preserves the original database for in-place updates.
    
    Args:
        db_path (Path): Path to database file to archive
        folders (dict): Dictionary with folder paths from create_project_folder_structure()
    """
    if not Path(db_path).exists():
        return
    
    timestamp = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
    archive_dir = folders['archived_files']
    
    # Create archive name with timestamp as suffix
    # sample_metadata.db → sample_metadata_2026_02_24-Time14-30-25.db
    db_path = Path(db_path)
    stem = db_path.stem  # "sample_metadata"
    suffix = db_path.suffix  # ".db"
    archive_name = f"{stem}_{timestamp}{suffix}"
    archive_path = archive_dir / archive_name
    
    # Copy instead of move to preserve original for in-place updates
    shutil.copy2(str(db_path), str(archive_path))
    # Database archived silently


def manage_bartender_file(bartender_file_path, folders):
    """
    Move BarTender file to organized folder structure.
    
    Args:
        bartender_file_path (Path): Path to BarTender file to organize
        folders (dict): Dictionary with folder paths from create_project_folder_structure()
    """
    bartender_file_path = Path(bartender_file_path)
    if not bartender_file_path.exists():
        return
    
    # Use the dedicated bartender labels folder
    bartender_dir = folders['bartender_labels']
    
    # Move file to bartender folder
    destination = bartender_dir / bartender_file_path.name
    shutil.move(str(bartender_file_path), str(destination))
    # BarTender file organized


def manage_input_files(folders, is_first_run=True, custom_plates_processed=False, additional_plates_processed=False, new_samples_processed=False):
    """
    Move processed input files to organized folder structure with timestamps.
    Uses the new consolidated folder structure and adds timestamps to prevent overwrites.
    Only moves files that were actually processed during this run.
    
    Args:
        folders (dict): Dictionary with folder paths from create_project_folder_structure()
        is_first_run (bool): True for first runs (look in working directory),
                            False for subsequent runs (look in 1_make_barcode_labels folder)
        custom_plates_processed (bool): True if custom plates were processed this run
        additional_plates_processed (bool): True if additional standard plates were processed this run
        new_samples_processed (bool): True if new samples (new_samples.csv) were processed this run
    """
    moved_files = []
    timestamp = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
    
    # Determine where to look for input files based on run type
    if is_first_run:
        # First run: look in working directory
        search_dir = Path('.')
    else:
        # Subsequent run: look in 1_make_barcode_labels folder
        search_dir = Path('1_make_barcode_labels')
    
    # --- CUSTOM PLATE FILE ARCHIVING DISABLED ---
    # custom_plate_names.txt is no longer used; is_custom is set via sample_metadata.csv.
    # The original file-moving logic is preserved below for reference.
    #
    # if custom_plates_processed:
    #     custom_files = list(search_dir.glob('custom_plate_names.txt')) + list(search_dir.glob('custom_sort_plate_names.txt'))
    #     for custom_file in custom_files:
    #         if custom_file.exists():
    #             stem = custom_file.stem
    #             suffix = custom_file.suffix
    #             timestamped_name = f"{stem}_{timestamp}{suffix}"
    #             destination = folders['custom_plates'] / timestamped_name
    #             shutil.move(str(custom_file), str(destination))
    #             moved_files.append(str(destination))
    
    # Move additional sort plate files with timestamp (only if they were processed)
    if additional_plates_processed:
        standard_files = list(search_dir.glob('list_additional_sort_plates.txt')) + list(search_dir.glob('additional_sort_plates.txt'))
        for standard_file in standard_files:
            if standard_file.exists():
                # Add timestamp to filename: list_additional_sort_plates.txt -> list_additional_sort_plates_2026_02_26-Time14-30-25.txt
                stem = standard_file.stem
                suffix = standard_file.suffix
                timestamped_name = f"{stem}_{timestamp}{suffix}"
                destination = folders['standard_plates'] / timestamped_name
                shutil.move(str(standard_file), str(destination))
                moved_files.append(str(destination))
                # File moved silently
    
    # Move new_samples.csv with timestamp (only if new samples were processed)
    if new_samples_processed:
        new_samples_file = Path('new_samples.csv')
        if new_samples_file.exists():
            # Archive to dedicated Additional_samples subfolder with timestamp
            # new_samples.csv → new_samples_2026_02_26-Time14-30-25.csv
            timestamped_name = f"new_samples_{timestamp}.csv"
            destination = folders['additional_samples'] / timestamped_name
            shutil.move(str(new_samples_file), str(destination))
            moved_files.append(str(destination))
            # File moved silently

    # Input files organized silently
    
    return moved_files


def archive_csv_file(csv_file_path, folders):
    """
    Archive CSV file with timestamp as suffix.
    
    Args:
        csv_file_path (Path): Path to CSV file to archive
        folders (dict): Dictionary with folder paths from create_project_folder_structure()
    """
    csv_file_path = Path(csv_file_path)
    if not csv_file_path.exists():
        return
    
    timestamp = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
    archive_dir = folders['archived_files']
    
    # Create archive name with timestamp as suffix
    # sample_metadata.csv → sample_metadata_2026_02_24-Time14-30-25.csv
    stem = csv_file_path.stem  # "sample_metadata"
    suffix = csv_file_path.suffix  # ".csv"
    archive_name = f"{stem}_{timestamp}{suffix}"
    archive_path = archive_dir / archive_name
    
    shutil.move(str(csv_file_path), str(archive_path))
    # Archived CSV file


def create_updated_csv_files(sample_metadata_df, individual_plates_df):
    """
    Create updated CSV files from current DataFrames.
    Uses ALL available columns from the DataFrames.
    
    Args:
        sample_metadata_df (pd.DataFrame): Sample metadata DataFrame
        individual_plates_df (pd.DataFrame): Individual plates DataFrame
    """
    # Create new sample_metadata.csv with all columns
    sample_metadata_df.to_csv('sample_metadata.csv', index=False)
    # Create new individual_plates.csv with ALL columns to ensure any new columns added over time are included
    individual_plates_df.to_csv('individual_plates.csv', index=False)
    # CSV files updated with all available columns


def manage_csv_files(sample_metadata_df, individual_plates_df, folders):
    """
    Archive existing CSV files and create new updated versions.
    
    Args:
        sample_metadata_df (pd.DataFrame): Sample metadata DataFrame
        individual_plates_df (pd.DataFrame): Individual plates DataFrame
        folders (dict): Dictionary with folder paths from create_project_folder_structure()
    """
    # Archive existing CSV files if they exist
    if Path('sample_metadata.csv').exists():
        archive_csv_file('sample_metadata.csv', folders)
    
    if Path('individual_plates.csv').exists():
        archive_csv_file('individual_plates.csv', folders)
    
    # Create new updated CSV files
    create_updated_csv_files(sample_metadata_df, individual_plates_df)


def archive_existing_files(file_list, folders):
    """
    Archive existing files with timestamp.
    
    Args:
        file_list (list): List of Path objects to archive
        folders (dict): Dictionary with folder paths from create_project_folder_structure()
    """
    timestamp = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
    archive_dir = folders['archived_files']
    
    archived_count = 0
    for file_path in file_list:
        if file_path.exists():
            archive_name = f"{timestamp}_{file_path.name}"
            archive_path = archive_dir / archive_name
            shutil.move(str(file_path), str(archive_path))
            print(f"📁 Archived: {file_path} → {archive_path}")
            archived_count += 1
    
    if archived_count > 0:
        print(f"✅ Archived {archived_count} existing files")


def print_header():
    """Print the script header."""
    print("=" * 60)
    print("Laboratory Barcode Label Generation")
    # print("Following SPS Laboratory Safety Standards")
    # print("=" * 60)


def process_first_run():
    """
    Handle first run: CSV detection, plate generation, custom plates.
    
    Returns:
        tuple: (sample_df, plates_df, custom_plates_processed, additional_plates_processed) -
               Sample metadata, plates DataFrames, and processing flags
    """
    print("\n🔬 FIRST RUN DETECTED")
    print("Processing sample metadata CSV file...")
    
    # Automatic CSV detection
    csv_file = detect_sample_metadata_csv()
    sample_df = read_sample_csv(csv_file)
    plates_df = make_plate_names(sample_df)
    
    # Track what was processed
    custom_plates_processed = False
    additional_plates_processed = False  # Never processed on first run
    
    # --- CUSTOM PLATES FILE INPUT DISABLED ---
    # Custom plates are now designated via the 'is_custom' column in sample_metadata.csv.
    # make_plate_names() already sets is_custom per plate based on the CSV column.
    # The original file-based custom plate addition is preserved below for reference.
    #
    # custom_plates = get_custom_plates(is_first_run=True)
    # if custom_plates:
    #     custom_df = pd.DataFrame([
    #         {'plate_name': name, 'project': 'CUSTOM', 'sample': 'CUSTOM',
    #          'plate_number': 1, 'is_custom': True}
    #         for name in custom_plates
    #     ])
    #     plates_df = pd.concat([plates_df, custom_df], ignore_index=True)
    #     print(f"✅ Added {len(custom_plates)} custom plates")
    #     custom_plates_processed = True

    return sample_df, plates_df, custom_plates_processed, additional_plates_processed


def process_additional_standard_plates(existing_sample_df, additional_plates, existing_plates_df):
    """
    Process additional standard plates for existing samples.
    
    Args:
        existing_sample_df (pd.DataFrame): Existing sample metadata
        additional_plates (dict): Mapping of sample_id to additional plate count
        existing_plates_df (pd.DataFrame): Existing plates data to determine next plate numbers
        
    Returns:
        pd.DataFrame: DataFrame of additional plates
    """
    print(f"✅ Found {len(additional_plates)} samples needing additional plates")
    additional_plates_list = []
    
    for sample_id, count in additional_plates.items():
        print(f"  - {sample_id}: {count} additional plates")
        
        # Parse PROPOSAL_SAMPLE format (e.g., "BP9735_WCBP1PR" -> proposal="BP9735", sample="WCBP1PR")
        if '_' not in sample_id:
            print(f"⚠️  WARNING: Invalid format for {sample_id}. Expected PROPOSAL_SAMPLE format (e.g., 'BP9735_WCBP1PR')")
            continue
            
        proposal, sample = sample_id.split('_', 1)
        
        # Find the sample with matching proposal and sample combination
        sample_row = existing_sample_df[
            (existing_sample_df['Proposal'] == proposal) &
            (existing_sample_df['Group_or_abrvSample'] == sample)
        ]
        
        if sample_row.empty:
            print(f"⚠️  WARNING: Proposal-Sample combination '{proposal}' + '{sample}' not found in existing metadata")
            continue
        
        # Find existing plates for this proposal-sample combination
        existing_sample_plates = existing_plates_df[
            (existing_plates_df['project'] == proposal) &
            (existing_plates_df['sample'] == sample) &
            (existing_plates_df['is_custom'] == False)
        ]
        
        # Find the highest existing plate number for this sample
        if not existing_sample_plates.empty:
            max_plate_number = existing_sample_plates['plate_number'].max()
        else:
            max_plate_number = 0
        
        # Create additional plates for this sample, continuing from the highest existing number
        for i in range(count):
            next_plate_number = max_plate_number + i + 1
            plate_name = f"{proposal}_{sample}.{next_plate_number}"
            
            additional_plates_list.append({
                'plate_name': plate_name,
                'project': proposal,
                'sample': sample,
                'plate_number': next_plate_number,
                'is_custom': False
            })
    
    return pd.DataFrame(additional_plates_list) if additional_plates_list else pd.DataFrame()


def process_subsequent_run(existing_sample_df, existing_plates_df):
    """
    Handle subsequent run: new samples, additional plates, or custom plates.

    Decision logic (mutually exclusive per run):
      1. If 'new_samples.csv' is present in the working directory → process new
         samples only.  Adding new samples and adding extra plates for existing
         samples in the same run is not supported; run the script twice.
      2. Otherwise → ask about additional standard plates for existing samples
         (existing behaviour).

    Args:
        existing_sample_df (pd.DataFrame): Existing sample metadata
        existing_plates_df (pd.DataFrame): Existing plates data

    Returns:
        tuple: (sample_df, plates_df, custom_plates_processed,
                additional_plates_processed, new_samples_processed) — sample
                metadata, new plates DataFrames, and processing flags.
    """
    print(f"\n🔄 SUBSEQUENT RUN DETECTED\n")

    # Track what was processed
    custom_plates_processed = False
    additional_plates_processed = False
    new_samples_processed = False

    # --- Path 1: New samples via new_samples.csv ---
    new_samples_csv = detect_new_samples_csv()

    if new_samples_csv is not None:
        # Safety guard: refuse to add new samples if downstream steps have run
        check_downstream_steps_not_run()

        # Read and validate the new samples CSV (full validation + overlap check)
        new_df = validate_new_samples_against_existing(new_samples_csv, existing_sample_df)

        # Generate plate names for the new samples only
        new_plates_df = make_plate_names(new_df)

        # Merge new sample rows into the full sample metadata
        merged_sample_df = pd.concat([existing_sample_df, new_df], ignore_index=True)

        new_samples_processed = True
        print(f"✅ New samples added: {len(new_df)} sample row(s), {len(new_plates_df)} new plate(s)")

        return merged_sample_df, new_plates_df, custom_plates_processed, additional_plates_processed, new_samples_processed

    # --- Path 2: Additional plates for existing samples ---
    # Ask for additional standard plates (only on subsequent runs)
    additional_plates = get_additional_standard_plates(is_first_run=False)

    # --- CUSTOM PLATES FILE INPUT DISABLED ---
    # Custom plates are now designated via the 'is_custom' column in sample_metadata.csv.
    # The original interactive custom plate addition is preserved below for reference.
    #
    # custom_plates = get_custom_plates(is_first_run=False)
    #
    # if not additional_plates and not custom_plates:
    #     return existing_sample_df, pd.DataFrame(), custom_plates_processed, additional_plates_processed, new_samples_processed
    #
    # if custom_plates:
    #     custom_df = pd.DataFrame([...])
    #     ...
    #     custom_plates_processed = True

    # Check if user wants to add any plates
    if not additional_plates:
        return existing_sample_df, pd.DataFrame(), custom_plates_processed, additional_plates_processed, new_samples_processed

    # Process additional standard plates
    plates_df = pd.DataFrame()
    sample_df = existing_sample_df  # Use existing sample metadata

    if additional_plates:
        additional_df = process_additional_standard_plates(existing_sample_df, additional_plates, existing_plates_df)
        plates_df = additional_df
        additional_plates_processed = True

    # Plates prepared for processing

    return sample_df, plates_df, custom_plates_processed, additional_plates_processed, new_samples_processed


def process_barcodes(plates_df, existing_plates_df, custom_base_barcode=None):
    """
    Generate and validate barcodes for new plates.
    
    Args:
        plates_df (pd.DataFrame): New plates needing barcodes
        existing_plates_df (pd.DataFrame): Existing plates data
        custom_base_barcode (str, optional): Custom base barcode to use instead of generating random one
        
    Returns:
        tuple: (plates_df, final_plates_df) - Updated plates and combined final data
    """
    # Generate barcodes
    
    # Generate simplified barcodes for new plates
    plates_df = generate_simple_barcodes(plates_df, existing_plates_df, custom_base_barcode)
    
    # Validate barcode uniqueness
    if not validate_barcode_uniqueness(plates_df):
        print("FATAL ERROR: Generated barcodes are not unique!")
        print("Laboratory automation requires unique identifiers for safety.")
        sys.exit()
    
    # Combine with existing data for final validation
    if existing_plates_df is not None:
        final_plates_df = pd.concat([existing_plates_df, plates_df], ignore_index=True)
    else:
        final_plates_df = plates_df
    
    # Final validation
    if not validate_barcode_uniqueness(final_plates_df):
        print("FATAL ERROR: Final barcode set contains duplicates!")
        print("Laboratory automation requires unique identifiers for safety.")
        sys.exit()
    
    return plates_df, final_plates_df


def finalize_files_and_database(sample_df, final_plates_df, new_plates_df, folders, is_first_run=True, custom_plates_processed=False, additional_plates_processed=False, existing_sample_df=None, new_samples_processed=False):
    """
    Handle all file operations: archiving, saving, organizing.
    
    Args:
        sample_df (pd.DataFrame): Sample metadata
        final_plates_df (pd.DataFrame): Final plates data (all plates combined)
        new_plates_df (pd.DataFrame): New plates added this run
        folders (dict): Dictionary with folder paths from create_project_folder_structure()
        is_first_run (bool): True for first runs, False for subsequent runs
        custom_plates_processed (bool): True if custom plates were processed this run
        additional_plates_processed (bool): True if additional standard plates were processed this run
        existing_sample_df (pd.DataFrame, optional): Existing sample metadata for comparison
        new_samples_processed (bool): True if new samples (new_samples.csv) were processed this run.
            When True, the sample_metadata table is always replaced (merged old+new rows).
    """
    # Archive existing database file (copy, not move)
    archive_database_file(DATABASE_NAME, folders)

    # When new samples were added, force a full replace of both tables by
    # treating this as a first-run save (sample_df already contains old+new rows,
    # and final_plates_df already contains old+new plates).
    effective_first_run = is_first_run or new_samples_processed

    # Smart database save - only update what actually changes.
    # When new_samples_processed is True (effective_first_run=True), we must
    # replace the individual_plates table with the FULL set of plates
    # (final_plates_df = old + new), not just the new plates (new_plates_df).
    # Using new_plates_df here would truncate the table to only the newly added
    # plates, causing individual_plates.csv to be wrong on all future runs.
    plates_df_for_db = final_plates_df if new_samples_processed else new_plates_df
    save_to_database_smart(sample_df, plates_df_for_db, DATABASE_NAME, effective_first_run, existing_sample_df)
    
    # Generate BarTender files with timestamp
    timestamp = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
    bartender_filename = f"BARTENDER_sort_plate_labels_{timestamp}.txt"
    bartender_tube_filename = f"BARTENDER_tube_labels_{timestamp}.txt"
    
    # Use only new plates for BarTender file generation
    if not new_plates_df.empty:
        plates_for_bartender = new_plates_df
    else:
        plates_for_bartender = final_plates_df
    
    make_bartender_file(plates_for_bartender, bartender_filename)
    make_bartender_tube_labels_file(plates_for_bartender, bartender_tube_filename)
    
    # File Management - Organize output and input files
    manage_bartender_file(bartender_filename, folders)
    manage_bartender_file(bartender_tube_filename, folders)
    manage_input_files(folders, is_first_run, custom_plates_processed, additional_plates_processed, new_samples_processed)
    
    # CSV Management - Archive and create updated CSV files
    manage_csv_files(sample_df, final_plates_df, folders)


def print_completion_summary(sample_df, final_plates_df, new_plates_df):
    """
    Print final success summary.
    
    Args:
        sample_df (pd.DataFrame): Sample metadata
        final_plates_df (pd.DataFrame): Final plates data
        new_plates_df (pd.DataFrame): New plates added this run
    """
    # Completion summary suppressed for minimal output
    pass


def parse_command_line_arguments():
    """
    Parse command line arguments for the script.
    
    Returns:
        argparse.Namespace: Parsed arguments containing custom_base_barcode
    """
    parser = argparse.ArgumentParser(
        description="Laboratory Barcode Label Generation Script",
        epilog="Example: python generate_barcode_labels.py REX12"
    )
    
    parser.add_argument(
        'custom_base_barcode',
        nargs='?',  # Optional positional argument
        help='Custom 5-character base barcode (e.g., REX12). Must start with a letter and contain only uppercase letters and digits.'
    )
    
    return parser.parse_args()


def main():
    """
    Main script execution following laboratory safety standards.
    Uses two-table database architecture and simplified barcode system.
    """
    # Parse command line arguments
    args = parse_command_line_arguments()
    custom_base_barcode = args.custom_base_barcode
    
    print_header()
    
    # Create project folder structure
    folders = create_project_folder_structure()
    
    # Determine run type and get existing data
    existing_sample_df, existing_plates_df = read_from_two_table_database(DATABASE_NAME)
    
    # Process plates based on run type
    is_first_run = existing_sample_df is None
    new_samples_processed = False  # default; overridden by process_subsequent_run() when new_samples.csv is used
    if is_first_run:
        sample_df, plates_df, custom_plates_processed, additional_plates_processed = process_first_run()
    else:
        sample_df, plates_df, custom_plates_processed, additional_plates_processed, new_samples_processed = process_subsequent_run(existing_sample_df, existing_plates_df)
        if plates_df.empty:
            print("No new plates to add. Exiting.")
            return
    
    # Generate and validate barcodes
    plates_df, final_plates_df = process_barcodes(plates_df, existing_plates_df, custom_base_barcode)
    
    # Handle all file operations
    finalize_files_and_database(sample_df, final_plates_df, plates_df, folders, is_first_run, custom_plates_processed, additional_plates_processed, existing_sample_df, new_samples_processed)
    
    # Print completion summary
    print_completion_summary(sample_df, final_plates_df, plates_df)
    
    # Create success marker for workflow manager
    create_success_marker()
    

if __name__ == "__main__":
    main()