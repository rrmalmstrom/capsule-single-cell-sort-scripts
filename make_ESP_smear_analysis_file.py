#!/usr/bin/env python3
"""
ESP Smear Analysis File Generator

Adapted from SPS_make_illumina_index_and_FA_files_NEW.py for ESP workflow.
This script identifies grid tables, extracts information, and merges with the ESP database
to create smear analysis files for upload.

Key differences from SPS:
- Uses 'master_plate_data' table instead of CSV files
- Merges on ['Library Plate Label', 'Well'] ↔ ['Plate_Barcode', 'Well']
- Functional programming approach (not object-oriented)

Recent Updates:
- Added Library Plate Container Barcode extraction from grid tables
- Enhanced individual_plates table with library_plate_container_barcode column
- Establishes one-to-one mapping: individual_plates.barcode ↔ grid_table.Library Plate Container Barcode
"""

import os
import sys
import sqlite3
import pandas as pd
import argparse
from pathlib import Path
from datetime import datetime
import logging


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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global flag for quiet mode
QUIET_MODE = False

def log_info(message):
    """Log info message only if not in quiet mode."""
    if not QUIET_MODE:
        logger.info(message)

def log_essential(message):
    """Log essential messages even in quiet mode."""
    if QUIET_MODE:
        # In quiet mode, print without timestamp/level formatting
        print(message)
    else:
        logger.info(message)


def read_project_database(base_dir):
    """Read the ESP project database from project_summary.db into pandas DataFrames."""
    db_path = Path(base_dir) / "project_summary.db"
    
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Read master_plate_data table
        master_plate_df = pd.read_sql_query("SELECT * FROM master_plate_data", conn)
        log_info(f"Successfully read master_plate_data with {len(master_plate_df)} records")
        log_info(f"Master plate data columns: {list(master_plate_df.columns)}")
        
        # Read individual_plates table
        individual_plates_df = pd.read_sql_query("SELECT * FROM individual_plates", conn)
        log_info(f"Successfully read individual_plates with {len(individual_plates_df)} records")
        log_info(f"Individual plates columns: {list(individual_plates_df.columns)}")
        
        conn.close()
        
        return master_plate_df, individual_plates_df
        
    except Exception as e:
        logger.error(f"Error reading database: {e}")
        raise


def identify_expected_grid_samples(master_plate_df, individual_plates_df):
    """
    Identify which samples should be present in grid tables based on pooling selection.
    
    Logic:
    1. Find plates selected for pooling from individual_plates table
    2. Find samples selected for pooling from master_plate_data table
    3. Return samples that meet both criteria
    """
    log_info("Identifying samples expected in grid tables...")
    
    # Check for required columns
    if 'selected_for_pooling' not in individual_plates_df.columns:
        logger.error("Missing 'selected_for_pooling' column in individual_plates table")
        logger.error("SCRIPT TERMINATED: Cannot determine which plates are selected for pooling")
        sys.exit()
    
    if 'selected_for_pooling' not in master_plate_df.columns:
        logger.error("Missing 'selected_for_pooling' column in master_plate_data table")
        logger.error("SCRIPT TERMINATED: Cannot determine which samples are selected for pooling")
        sys.exit()
    
    # Get plates selected for pooling
    selected_plates = individual_plates_df[
        individual_plates_df['selected_for_pooling'] == True
    ]['barcode'].tolist()
    
    log_info(f"Found {len(selected_plates)} plates selected for pooling: {selected_plates}")
    
    # Get samples selected for pooling from selected plates
    expected_samples = master_plate_df[
        (master_plate_df['selected_for_pooling'] == True) &
        (master_plate_df['Plate_Barcode'].isin(selected_plates))
    ].copy()
    
    log_info(f"Found {len(expected_samples)} samples expected in grid tables")
    log_info(f"Expected samples from plates: {expected_samples['Plate_Barcode'].unique().tolist()}")
    
    if len(expected_samples) == 0:
        logger.error("No samples found that are selected for pooling from plates selected for pooling")
        logger.error("SCRIPT TERMINATED: No expected grid table samples identified")
        sys.exit()
    
    return expected_samples, selected_plates


def validate_grid_table_columns(csv_file):
    """Check if CSV file has required grid table columns without full validation."""
    is_valid, error_msg = validate_grid_table_columns_detailed(csv_file)
    
    if not is_valid:
        logger.error(f"Invalid grid table file {csv_file}: {error_msg}")
        logger.error("SCRIPT TERMINATED: Required columns are missing from grid table file")
        sys.exit()
    
    return True


def find_csv_files(base_dir):
    """Find all CSV files in the 4_plate_selection_and_pooling subdirectory."""
    csv_files = []
    try:
        # Look in the 4_plate_selection_and_pooling subdirectory
        grid_table_dir = Path(base_dir) / "4_plate_selection_and_pooling"
        if not grid_table_dir.exists():
            logger.error(f"Grid table directory not found: {grid_table_dir}")
            logger.error("SCRIPT TERMINATED: Required grid table directory does not exist")
            sys.exit()
        
        for file_path in grid_table_dir.glob("*.csv"):
            csv_files.append(str(file_path))
        log_info(f"Found {len(csv_files)} CSV files in {grid_table_dir}")
        return csv_files
    except Exception as e:
        logger.error(f"Error finding CSV files: {e}")
        return []


def find_all_grid_tables(base_dir):
    """
    Find and validate ALL grid table files in directory.
    Adapted from SPS script to work with ESP grid table format.
    
    This function scans the 4_plate_selection_and_pooling directory for CSV files and validates
    each one to determine if it contains the required grid table columns. It
    supports multi-file processing by finding ALL valid grid table files rather
    than just one.
    
    Args:
        base_dir (str): Base directory to scan for CSV files
        
    Returns:
        list: List of valid grid table file paths as strings
        
    Raises:
        SystemExit: If no valid grid tables found with detailed error message
        
    Validation Process:
        1. Scans 4_plate_selection_and_pooling directory for all CSV files
        2. Checks each CSV for required column headers
        3. Reports invalid files with specific error messages
        4. Returns all valid files for multi-grid processing
        
    Required Columns:
        - Well: Well position (e.g., A1, B2, C3)
        - Library Plate Label: Destination plate name
        - Illumina Library: Library identifier
        - Library Plate Container Barcode: Destination plate barcode
        - Nucleic Acid ID: Sample identifier
    """
    log_info("Scanning for grid table CSV files...")
    
    # Find all CSV files in the grid table directory
    csv_files = find_csv_files(base_dir)
    
    if not csv_files:
        logger.error("No CSV files found in 4_plate_selection_and_pooling directory")
        logger.error("SCRIPT TERMINATED: Grid table directory contains no CSV files")
        sys.exit()
    
    # Validate each CSV file
    valid_files = []
    invalid_files = []
    
    for csv_file in csv_files:
        is_valid, error_msg = validate_grid_table_columns_detailed(csv_file)
        if is_valid:
            valid_files.append(csv_file)
            log_info(f"Valid grid table found: {Path(csv_file).name}")
        else:
            invalid_files.append((csv_file, error_msg))
            log_info(f"Skipping non-grid table file: {Path(csv_file).name} - {error_msg}")
    
    # Handle results
    if len(valid_files) == 0:
        logger.error(f"No valid grid table found in 4_plate_selection_and_pooling directory")
        logger.error(f"Found {len(csv_files)} CSV file(s), but none contain the required columns:")
        for csv_file, error_msg in invalid_files:
            logger.error(f"- {Path(csv_file).name}: {error_msg}")
        logger.error("A grid table CSV file must contain these required columns:")
        logger.error("- Well")
        logger.error("- Library Plate Label")
        logger.error("- Illumina Library")
        logger.error("- Library Plate Container Barcode")
        logger.error("- Nucleic Acid ID")
        logger.error("SCRIPT TERMINATED: No valid grid table files found")
        sys.exit()
    
    # Return all valid files
    log_info(f"Found {len(valid_files)} valid grid table file(s)")
    return valid_files


def validate_grid_table_columns_detailed(csv_file):
    """Check if CSV file has required grid table columns with detailed error reporting."""
    required_cols = ['Well', 'Library Plate Label', 'Illumina Library', 'Library Plate Container Barcode', 'Nucleic Acid ID']
    
    try:
        # Read only the header row to check columns
        df_header = pd.read_csv(csv_file, nrows=0)
        missing_cols = [col for col in required_cols if col not in df_header.columns]
        
        if not missing_cols:
            return True, None
        else:
            return False, f"Missing columns: {missing_cols}"
            
    except Exception as e:
        return False, f"Error reading file: {e}"


def read_multiple_grid_tables(grid_table_files):
    """
    Read and combine multiple grid table files.
    Adapted from SPS version for ESP workflow.
    """
    if not grid_table_files:
        raise ValueError("No grid table files provided")
    
    grid_dataframes = {}
    combined_grid_df = pd.DataFrame()
    
    for filename in grid_table_files:
        grid_path = Path(filename)
        log_info(f"Processing grid table: {grid_path.name}")
        
        try:
            # Read the grid table
            grid_df = pd.read_csv(filename)
            
            # Store individual dataframe
            grid_dataframes[grid_path.name] = grid_df
            
            # Add source file column for tracking
            grid_df['Source_File'] = grid_path.name
            
            # Combine with master dataframe
            if combined_grid_df.empty:
                combined_grid_df = grid_df.copy()
            else:
                combined_grid_df = pd.concat([combined_grid_df, grid_df], ignore_index=True)
            
            log_info(f"Successfully processed {grid_path.name}: {len(grid_df)} rows")
            
        except Exception as e:
            logger.error(f"Error processing {filename}: {e}")
            continue
    
    if combined_grid_df.empty:
        raise ValueError("No valid grid table data could be read")
    
    log_info(f"Combined grid table: {len(combined_grid_df)} total rows from {len(grid_dataframes)} files")
    
    return grid_dataframes, combined_grid_df


def detect_duplicate_samples(grid_dataframes):
    """
    Detect duplicate samples across grid tables.
    Adapted from SPS version for ESP workflow.
    """
    log_info("Checking for duplicate samples across grid tables...")
    
    all_samples = []
    sample_sources = {}
    
    # Collect all samples with their source files
    for filename, df in grid_dataframes.items():
        for _, row in df.iterrows():
            sample_id = row.get('Nucleic Acid ID', '')
            if pd.notna(sample_id) and sample_id != '':
                sample_key = f"{sample_id}_{row.get('Well', '')}_{row.get('Library Plate Label', '')}"
                all_samples.append(sample_key)
                
                if sample_key in sample_sources:
                    sample_sources[sample_key].append(filename)
                else:
                    sample_sources[sample_key] = [filename]
    
    # Find duplicates
    duplicates = {sample: sources for sample, sources in sample_sources.items() 
                 if len(sources) > 1}
    
    if duplicates:
        logger.error(f"Found {len(duplicates)} duplicate samples:")
        for sample, sources in duplicates.items():
            logger.error(f"  {sample} appears in: {', '.join(sources)}")
        logger.error("SCRIPT TERMINATED: Duplicate samples detected - data integrity compromised")
        sys.exit()
    else:
        log_info("No duplicate samples found")
        return {}


def validate_grid_table_completeness(expected_samples, combined_grid_df):
    """
    Validate that grid table contains exactly the expected samples (no more, no less).
    """
    log_info("Validating grid table completeness against expected samples...")
    
    # Create sets for comparison using (Plate_Barcode, Well) tuples
    expected_set = set(zip(expected_samples['Plate_Barcode'], expected_samples['Well']))
    grid_set = set(zip(combined_grid_df['Library Plate Label'], combined_grid_df['Well']))
    
    # Find missing samples (expected but not in grid)
    missing_from_grid = expected_set - grid_set
    
    # Find unexpected samples (in grid but not expected)
    unexpected_in_grid = grid_set - expected_set
    
    log_info(f"Validation results:")
    log_info(f"  Expected samples: {len(expected_set)}")
    log_info(f"  Grid table samples: {len(grid_set)}")
    log_info(f"  Missing from grid: {len(missing_from_grid)}")
    log_info(f"  Unexpected in grid: {len(unexpected_in_grid)}")
    
    # Report missing samples
    if missing_from_grid:
        logger.error(f"Found {len(missing_from_grid)} expected samples missing from grid tables:")
        for plate_barcode, well in missing_from_grid:
            logger.error(f"  {plate_barcode} - {well}")
        logger.error("SCRIPT TERMINATED: Expected samples missing from grid tables")
        sys.exit()
    
    # Report unexpected samples
    if unexpected_in_grid:
        logger.error(f"Found {len(unexpected_in_grid)} unexpected samples in grid tables:")
        for plate_barcode, well in unexpected_in_grid:
            logger.error(f"  {plate_barcode} - {well}")
        logger.error("SCRIPT TERMINATED: Grid tables contain samples not selected for pooling")
        sys.exit()
    
    log_info("Grid table validation passed - perfect match with expected samples")
    return True


def validate_and_merge_data(master_plate_df, expected_samples, grid_df):
    """
    Validate and merge grid table data with master plate dataframe.
    Only expected samples should have grid data, but all master data is preserved.
    
    ESP merging strategy:
    - Grid table: ['Library Plate Label', 'Well']
    - Master plate data: ['Plate_Barcode', 'Well']
    """
    log_info("Validating and merging grid table with master plate data...")
    
    # Check required columns exist
    grid_merge_cols = ['Library Plate Label', 'Well']
    db_merge_cols = ['Plate_Barcode', 'Well']
    
    missing_grid_cols = [col for col in grid_merge_cols if col not in grid_df.columns]
    missing_db_cols = [col for col in db_merge_cols if col not in master_plate_df.columns]
    
    if missing_grid_cols:
        logger.error(f"Missing grid table columns: {missing_grid_cols}")
        logger.error("SCRIPT TERMINATED: Required columns missing from grid table")
        sys.exit()
    if missing_db_cols:
        logger.error(f"Missing master plate data columns: {missing_db_cols}")
        logger.error("SCRIPT TERMINATED: Required columns missing from database")
        sys.exit()
    
    # Prepare dataframes for merging
    # Grid table columns we want to add to the master dataframe
    grid_data_cols = ['Illumina Library', 'Nucleic Acid ID', 'Library Plate Container Barcode']
    grid_merge_df = grid_df[grid_merge_cols + grid_data_cols].copy()
    
    # Rename grid table merge column to match database column
    grid_merge_df = grid_merge_df.rename(columns={
        'Library Plate Label': 'Plate_Barcode'
    })
    
    # Perform the merge: master dataframe (left) with grid data (right)
    # This preserves ALL master data, only adds grid data where available
    merged_df = pd.merge(
        master_plate_df,    # Left: ALL master plate data
        grid_merge_df,      # Right: grid table data
        on=['Plate_Barcode', 'Well'],
        how='left',         # Keep all master data, add grid data where matches exist
        suffixes=(None, '_y')  # Master gets no suffix, grid gets '_y'
    )
    
    # Remove duplicate columns from grid table (they have '_y' suffix)
    columns_to_remove = ['Well_y']  # Remove the duplicate Well column from grid table
    
    for col in columns_to_remove:
        if col in merged_df.columns:
            logger.info(f"Removing duplicate column: {col}")
            merged_df = merged_df.drop(columns=[col])
    
    # Validate that expected samples got grid data
    expected_sample_keys = set(zip(expected_samples['Plate_Barcode'], expected_samples['Well']))
    
    # Check which expected samples are missing grid data
    missing_grid_data = []
    for _, row in expected_samples.iterrows():
        merged_row = merged_df[
            (merged_df['Plate_Barcode'] == row['Plate_Barcode']) &
            (merged_df['Well'] == row['Well'])
        ]
        if merged_row.empty or pd.isna(merged_row.iloc[0]['Nucleic Acid ID']):
            missing_grid_data.append((row['Plate_Barcode'], row['Well']))
    
    log_info(f"Merge results:")
    log_info(f"  Master plate data rows: {len(master_plate_df)}")
    log_info(f"  Expected samples: {len(expected_samples)}")
    log_info(f"  Grid table rows: {len(grid_df)}")
    log_info(f"  Final merged rows: {len(merged_df)}")
    log_info(f"  Expected samples missing grid data: {len(missing_grid_data)}")
    
    if missing_grid_data:
        logger.error("Some expected samples are missing grid table data:")
        for plate_barcode, well in missing_grid_data:
            logger.error(f"  {plate_barcode} - {well}")
        logger.error("SCRIPT TERMINATED: Incomplete merge - not all expected samples have grid data")
        sys.exit()
    
    log_info("Perfect merge achieved - all expected samples have grid table data")
    log_info(f"Master dataframe updated with grid data for {len(expected_samples)} samples")
    return merged_df


def create_smear_analysis_file(merged_df, base_dir):
    """
    Create the ESP smear analysis file for upload in the proper ESP format.
    
    This function transforms the merged dataframe into the ESP smear file format
    with the required 13 columns and proper data mapping.
    """
    log_info("Creating ESP smear analysis file...")
    
    if merged_df.empty:
        logger.error("No merged data available for smear analysis file")
        logger.error("SCRIPT TERMINATED: Cannot create output file without merged data")
        sys.exit()
    
    # Filter to only samples that have grid table data (expected samples)
    # These are the samples that should appear in the smear file
    grid_samples = merged_df[merged_df['Nucleic Acid ID'].notna()].copy()
    
    if grid_samples.empty:
        logger.error("No samples with grid table data found for smear analysis file")
        logger.error("SCRIPT TERMINATED: Cannot create smear file without grid table samples")
        sys.exit()
    
    log_info(f"Creating smear file for {len(grid_samples)} samples with grid table data")
    
    # Create smear_df with the required ESP format columns
    # Map from merged dataframe columns to ESP format columns
    smear_df = pd.DataFrame()
    
    # Required column mappings based on user specifications:
    # ESP Format -> Source Column
    smear_df['Well'] = grid_samples['Well']
    smear_df['Sample ID'] = grid_samples['Illumina Library']
    smear_df['Range'] = '400 bp to 800 bp'  # Fixed value
    smear_df['ng/uL'] = grid_samples['ng/uL']
    smear_df['%Total'] = 15  # Fixed value
    smear_df['nmole/L'] = grid_samples['nmole/L']
    smear_df['Avg. Size'] = grid_samples['Avg. Size']
    smear_df['%CV'] = 20  # Fixed value
    smear_df['Volume uL'] = 20  # Fixed value
    smear_df['QC Result'] = 'Pass'  # Always Pass per user specification
    smear_df['Failure Mode'] = ''  # Always empty per user specification
    smear_df['Index Name'] = grid_samples['Index_Name']
    smear_df['PCR Cycles'] = 12  # Fixed value
    
    # Validate that we have all required columns
    expected_columns = ['Well', 'Sample ID', 'Range', 'ng/uL', '%Total', 'nmole/L',
                       'Avg. Size', '%CV', 'Volume uL', 'QC Result', 'Failure Mode',
                       'Index Name', 'PCR Cycles']
    
    missing_columns = [col for col in expected_columns if col not in smear_df.columns]
    if missing_columns:
        logger.error(f"Missing required ESP format columns: {missing_columns}")
        logger.error("SCRIPT TERMINATED: Cannot create complete ESP smear file")
        sys.exit()
    
    # Ensure column order matches ESP format
    smear_df = smear_df[expected_columns]
    
    # Get unique Library Plate Container Barcodes for file naming
    # Use Library Plate Container Barcode from grid table for file naming
    unique_plates = grid_samples['Library Plate Container Barcode'].unique()
    
    log_info(f"Found {len(unique_plates)} unique Library Plate Container Barcodes: {list(unique_plates)}")
    
    # Create the ESP smear file output directory
    esp_smear_dir = Path(base_dir) / "4_plate_selection_and_pooling" / "B_smear_file_for_ESP_upload"
    esp_smear_dir.mkdir(parents=True, exist_ok=True)
    log_info(f"Created ESP smear file directory: {esp_smear_dir}")
    
    # Create separate files for each unique Library Plate Container Barcode
    output_files = []
    for plate_barcode in unique_plates:
        # Filter data for current plate barcode
        plate_samples = grid_samples[grid_samples['Library Plate Container Barcode'] == plate_barcode]
        plate_smear_df = smear_df[grid_samples['Library Plate Container Barcode'] == plate_barcode].copy()
        
        # Create filename with Library Plate Container Barcode
        output_filename = f'ESP_smear_file_for_upload_{plate_barcode}.csv'
        output_path = esp_smear_dir / output_filename
        
        # Export plate-specific data to CSV file
        plate_smear_df.to_csv(output_path, index=False)
        output_files.append(output_path)
        
        log_info(f"✓ Created ESP smear file: {output_path} ({len(plate_smear_df)} rows)")
        log_info(f"  Library Plate Container Barcode: {plate_barcode}")
        log_info(f"  Samples: {len(plate_smear_df)}")
    
    log_info(f"ESP smear analysis file generation completed successfully!")
    log_info(f"Created {len(output_files)} ESP smear files")
    
    return output_files


def archive_grid_table_files(base_dir, grid_table_files):
    """
    Create 'previously_processed_grid_files' folder and move all grid table files there.
    
    Args:
        base_dir (Path): Base directory containing the 4_plate_selection_and_pooling folder
        grid_table_files (list): List of grid table file paths to move
    """
    log_info("Archiving processed grid table files...")
    
    # Create the archive directory
    archive_dir = Path(base_dir) / "4_plate_selection_and_pooling" / "previously_processed_grid_files"
    archive_dir.mkdir(parents=True, exist_ok=True)
    log_info(f"Created archive directory: {archive_dir}")
    
    # Move each grid table file to the archive directory
    moved_files = []
    for grid_file_path in grid_table_files:
        grid_file = Path(grid_file_path)
        if grid_file.exists():
            # Create destination path in archive directory
            dest_path = archive_dir / grid_file.name
            
            # Move the file
            grid_file.rename(dest_path)
            moved_files.append(dest_path)
            log_info(f"✓ Moved grid table file: {grid_file.name} → {dest_path}")
        else:
            logger.warning(f"Grid table file not found for archiving: {grid_file_path}")
    
    log_info(f"Successfully archived {len(moved_files)} grid table files to: {archive_dir}")
    return moved_files


def archive_database_file(base_dir):
    """
    Archive existing database file with timestamp suffix by copying (not moving).
    Follows the capsule_fa_analysis.py copy-for-archive pattern for safer database handling.
    """
    db_path = Path(base_dir) / "project_summary.db"
    
    # Archive existing database file if it exists
    if db_path.exists():
        timestamp = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
        archive_dir = Path(base_dir) / "archived_files"
        archive_dir.mkdir(exist_ok=True)
        
        # Create archive name with timestamp suffix
        stem = db_path.stem  # "project_summary"
        suffix = db_path.suffix  # ".db"
        archive_name = f"{stem}_{timestamp}{suffix}"
        archive_path = archive_dir / archive_name
        
        # Copy instead of move to preserve original for in-place updates
        import shutil
        shutil.copy2(str(db_path), str(archive_path))
        log_info(f"📁 Archived database: {archive_path}")
        return archive_path
    return None


def extract_library_plate_container_barcode_mapping(combined_grid_df):
    """
    Extract mapping from Library Plate Label to Library Plate Container Barcode from grid tables.
    
    Args:
        combined_grid_df: Combined dataframe from all grid tables
        
    Returns:
        dict: Mapping of Library Plate Label (e.g., 'XUPVQ-1') to Library Plate Container Barcode (e.g., '27-810254')
    """
    log_info("Extracting Library Plate Container Barcode mapping from grid tables...")
    
    # Get unique mappings from grid table
    mapping_df = combined_grid_df[['Library Plate Label', 'Library Plate Container Barcode']].drop_duplicates()
    
    # Convert to dictionary
    barcode_mapping = dict(zip(mapping_df['Library Plate Label'], mapping_df['Library Plate Container Barcode']))
    
    log_info(f"Found Library Plate Container Barcode mappings for {len(barcode_mapping)} plates:")
    for plate_label, container_barcode in barcode_mapping.items():
        log_info(f"  {plate_label} → {container_barcode}")
    
    return barcode_mapping


def update_individual_plates_with_esp_status(base_dir, processed_plate_barcodes, batch_id, barcode_mapping=None):
    """
    Update individual_plates table to mark plates that generated ESP files and add Library Plate Container Barcode.
    Uses SQL UPDATE approach for better performance, following capsule_fa_analysis.py pattern.
    
    Args:
        base_dir: Base directory containing the database
        processed_plate_barcodes: List of plate barcodes that generated ESP files
        batch_id: Batch ID for this processing run
        barcode_mapping: Dict mapping plate barcode (e.g., 'XUPVQ-1') to Library Plate Container Barcode (e.g., '27-810254')
    """
    if not processed_plate_barcodes:
        return
    
    sql_db_path = Path(base_dir) / 'project_summary.db'
    
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(f'sqlite:///{sql_db_path}')
        timestamp = datetime.now().isoformat()
        
        with engine.connect() as conn:
            # First, ensure the ESP tracking columns exist
            result = conn.execute(text("PRAGMA table_info(individual_plates)"))
            existing_columns = [row[1] for row in result]
            
            # Add missing columns if they don't exist
            if 'esp_generation_status' not in existing_columns:
                conn.execute(text("ALTER TABLE individual_plates ADD COLUMN esp_generation_status TEXT DEFAULT 'pending'"))
                conn.commit()
                log_info("✅ Added esp_generation_status column to individual_plates")
                
            if 'esp_generated_timestamp' not in existing_columns:
                conn.execute(text("ALTER TABLE individual_plates ADD COLUMN esp_generated_timestamp TEXT"))
                conn.commit()
                log_info("✅ Added esp_generated_timestamp column to individual_plates")
                
            if 'esp_batch_id' not in existing_columns:
                conn.execute(text("ALTER TABLE individual_plates ADD COLUMN esp_batch_id TEXT"))
                conn.commit()
                log_info("✅ Added esp_batch_id column to individual_plates")
                
            if 'library_plate_container_barcode' not in existing_columns:
                conn.execute(text("ALTER TABLE individual_plates ADD COLUMN library_plate_container_barcode TEXT"))
                conn.commit()
                log_info("✅ Added library_plate_container_barcode column to individual_plates")
            
            # Use SQL UPDATE for efficient in-place updates
            for barcode in processed_plate_barcodes:
                # Get the Library Plate Container Barcode for this plate
                container_barcode = barcode_mapping.get(barcode) if barcode_mapping else None
                
                update_query = text("""
                    UPDATE individual_plates
                    SET esp_generation_status = :status,
                        esp_generated_timestamp = :timestamp,
                        esp_batch_id = :batch_id,
                        library_plate_container_barcode = :container_barcode
                    WHERE barcode = :barcode
                """)
                
                conn.execute(update_query, {
                    'status': 'generated',
                    'timestamp': timestamp,
                    'batch_id': batch_id,
                    'barcode': barcode,
                    'container_barcode': container_barcode
                })
                
                if container_barcode:
                    log_info(f"✅ Updated plate {barcode} with Library Plate Container Barcode: {container_barcode}")
                else:
                    logger.warning(f"⚠️ No Library Plate Container Barcode found for plate {barcode}")
            
            # Commit all updates
            conn.commit()
        
        log_info(f"✅ Updated individual_plates table: marked {len(processed_plate_barcodes)} plates as ESP generated")
        
    except Exception as e:
        logger.error(f"❌ Error updating individual_plates table: {e}")
        raise
    finally:
        engine.dispose()


def update_master_plate_data_table(base_dir, merged_df):
    """
    Replace master_plate_data table with the merged dataframe.
    Follows the capsule_fa_analysis.py pattern for complete table replacement.
    
    Args:
        base_dir: Base directory containing the database
        merged_df: Updated master plate data DataFrame with grid table information
    """
    sql_db_path = Path(base_dir) / 'project_summary.db'
    
    try:
        from sqlalchemy import create_engine
        engine = create_engine(f'sqlite:///{sql_db_path}')
        
        # Replace master_plate_data table with updated data
        merged_df.to_sql('master_plate_data', engine, if_exists='replace', index=False)
        
        log_info(f"✅ Updated master_plate_data table with grid table information")
        log_info(f"   Total rows in updated table: {len(merged_df)}")
        
    except Exception as e:
        logger.error(f"❌ Error updating master_plate_data table: {e}")
        raise
    finally:
        engine.dispose()


def archive_csv_files(base_dir):
    """
    Archive existing CSV files with timestamp suffix by moving them.
    Follows the capsule_fa_analysis.py pattern.
    
    Args:
        base_dir: Base directory containing the CSV files
        
    Returns:
        dict: Paths to archived files
    """
    timestamp = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
    archive_dir = Path(base_dir) / "archived_files"
    archive_dir.mkdir(exist_ok=True)
    
    archived_files = {}
    
    # Archive master_plate_data.csv
    master_csv_path = Path(base_dir) / "master_plate_data.csv"
    if master_csv_path.exists():
        archive_name = f"master_plate_data_{timestamp}.csv"
        archive_path = archive_dir / archive_name
        import shutil
        shutil.move(str(master_csv_path), str(archive_path))
        archived_files['master_plate_data'] = archive_path
        log_info(f"📁 Archived CSV: {archive_path}")
    
    # Archive individual_plates.csv
    plates_csv_path = Path(base_dir) / "individual_plates.csv"
    if plates_csv_path.exists():
        archive_name = f"individual_plates_{timestamp}.csv"
        archive_path = archive_dir / archive_name
        import shutil
        shutil.move(str(plates_csv_path), str(archive_path))
        archived_files['individual_plates'] = archive_path
        log_info(f"📁 Archived CSV: {archive_path}")
    
    return archived_files


def generate_fresh_csv_files(base_dir, updated_master_df):
    """
    Generate fresh CSV files from updated database tables.
    Follows the capsule_fa_analysis.py pattern.
    
    Args:
        base_dir: Base directory to save CSV files
        updated_master_df: Updated master plate data DataFrame
    """
    try:
        # Generate fresh master_plate_data.csv
        master_csv_path = Path(base_dir) / "master_plate_data.csv"
        updated_master_df.to_csv(master_csv_path, index=False)
        log_info(f"✅ Generated fresh master_plate_data.csv with {len(updated_master_df)} rows")
        
        # Generate fresh individual_plates.csv from database
        sql_db_path = Path(base_dir) / 'project_summary.db'
        from sqlalchemy import create_engine
        engine = create_engine(f'sqlite:///{sql_db_path}')
        individual_plates_df = pd.read_sql('SELECT * FROM individual_plates', engine)
        engine.dispose()
        
        # Include ALL columns from the SQL table in the CSV file
        plates_csv_path = Path(base_dir) / "individual_plates.csv"
        individual_plates_df.to_csv(plates_csv_path, index=False)
        log_info(f"✅ Generated fresh individual_plates.csv with {len(individual_plates_df)} rows and {len(individual_plates_df.columns)} columns")
        
    except Exception as e:
        logger.error(f"❌ Error generating fresh CSV files: {e}")
        raise


def main():
    """Main execution function for ESP smear analysis file generation."""
    parser = argparse.ArgumentParser(
        description="Generate ESP smear analysis files from grid tables and database"
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Reduce output to essential messages only (5-6 lines total)'
    )
    
    args = parser.parse_args()
    
    # Set global quiet mode
    global QUIET_MODE
    QUIET_MODE = args.quiet
    
    try:
        log_info("Starting ESP smear analysis file generation...")
        
        # Use current working directory as the base directory
        base_dir = Path.cwd()
        log_info(f"Base directory (current working directory): {base_dir}")
        
        # ESP smear files will always be created in base_dir/4_plate_selection_and_pooling/B_smear_file_for_ESP_upload/
        log_info(f"ESP smear files will be created in: {base_dir}/4_plate_selection_and_pooling/B_smear_file_for_ESP_upload/")
        
        if not base_dir.exists():
            raise FileNotFoundError(f"Base directory not found: {base_dir}")
        
        # Read ESP database
        log_info("Reading ESP project database...")
        master_plate_df, individual_plates_df = read_project_database(base_dir)
        
        # Identify which samples should be in grid tables
        log_info("Identifying expected grid table samples...")
        expected_samples, selected_plates = identify_expected_grid_samples(master_plate_df, individual_plates_df)
        
        # Find and read grid tables
        log_info("Finding grid table files...")
        grid_table_files = find_all_grid_tables(base_dir)
        
        if not grid_table_files:
            logger.error("No valid grid table files found!")
            sys.exit()
        
        # Read and combine grid tables
        grid_dataframes, combined_grid_df = read_multiple_grid_tables(grid_table_files)
        
        # Check for duplicates (will exit if any found)
        detect_duplicate_samples(grid_dataframes)
        
        # Validate grid table completeness
        validate_grid_table_completeness(expected_samples, combined_grid_df)
        
        # Merge data with perfect validation
        merged_df = validate_and_merge_data(master_plate_df, expected_samples, combined_grid_df)
        
        # Create smear analysis file
        output_files = create_smear_analysis_file(merged_df, base_dir)
        
        if output_files:
            log_essential(f"Generated {len(output_files)} ESP smear files successfully!")
            log_info(f"ESP smear files created:")
            for file_path in output_files:
                log_info(f"  - {file_path}")
            
            # Archive the processed grid table files
            archive_grid_table_files(base_dir, grid_table_files)
            
            # Database and CSV file updates following capsule_fa_analysis.py pattern
            log_info("Updating database and CSV files...")
            
            # Step 1: Archive existing database file
            archive_database_file(base_dir)
            
            # Step 2: Get unique plate barcodes that generated ESP files and extract barcode mapping
            # Filter to only samples that have grid table data
            grid_samples = merged_df[merged_df['Nucleic Acid ID'].notna()].copy()
            # Use the original Plate_Barcode (XUPVQ-X) not the Library Plate Container Barcode (27-XXXXX)
            # because individual_plates table uses XUPVQ-X format barcodes
            processed_plate_barcodes = list(grid_samples['Plate_Barcode'].unique())
            batch_id = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
            
            # Extract Library Plate Container Barcode mapping from grid tables
            barcode_mapping = extract_library_plate_container_barcode_mapping(combined_grid_df)
            
            # Step 3: Update individual_plates table with ESP generation status and Library Plate Container Barcode
            update_individual_plates_with_esp_status(base_dir, processed_plate_barcodes, batch_id, barcode_mapping)
            
            # Step 4: Update master_plate_data table with merged dataframe
            update_master_plate_data_table(base_dir, merged_df)
            
            # Step 5: Archive existing CSV files and generate fresh ones
            archive_csv_files(base_dir)
            generate_fresh_csv_files(base_dir, merged_df)
            
            log_essential("Database and CSV file updates completed successfully!")

            # Create success marker for workflow manager
            create_success_marker()

        else:
            logger.error("Failed to create smear analysis file")
            sys.exit()

    except Exception as e:
        logger.error(f"ESP smear analysis generation failed: {e}")
        sys.exit()


if __name__ == "__main__":
    main()
