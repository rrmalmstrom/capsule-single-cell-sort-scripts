#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Laboratory Fragment Analyzer (FA) Quality Analysis Script

This script processes Fragment Analyzer output files to analyze DNA library quality
with automated index set failure detection and comprehensive database integration
following laboratory automation standards.

USAGE: python capsule_fa_analysis.py

CRITICAL REQUIREMENTS:
- MUST use sip-lims conda environment
- Follows existing SPS script patterns
- Implements comprehensive error handling with systematic validation
- Supports automated quality assessment with 50% failure thresholds

Features:
- Automated FA output file discovery and processing from subdirectories
- Index set failure rate analysis (PE17, PE18, PE19, PE20) using only 'sample' type wells
- 50% failure threshold logic for both index sets and whole plate rework decisions
- Failed index set extrapolation to entire library plates
- Comprehensive database integration with timestamped archiving
- Master plate data updates with FA results and quality assessments
- FA result directory archiving with organized folder management
- Detailed quality reporting with pass/fail analysis

Input File Organization (3_FA_analysis/ folder):
- thresholds.txt: DNA concentration and size thresholds per destination plate
- Subdirectories with FA instrument output: {date}/{plate_name}/
- *Smear Analysis Result.csv: FA instrument output files (automatically discovered)

Output File Organization (3_FA_analysis/ folder):
- reduced_fa_analysis_summary_{timestamp}.txt: Comprehensive quality analysis results
- {plate_name}.csv: Processed FA data files (copied from subdirectories)
- archived_files/capsule_fa_analysis_results/: Organized archive of processed FA files

Database Schema Integration:
- Reads from existing three-table architecture (sample_metadata, individual_plates, master_plate_data)
- Archives existing database and CSV files with timestamps
- Updates master_plate_data with FA results: dilution_factor, ng/uL, nmol/L, Avg. Size, Passed_library, Failed_index_sets, Redo_whole_plate
- Database file: project_summary.db (working directory)

Index Set Failure Analysis:
- Calculates failure rates per index set (PE17, PE18, PE19, PE20) using only FA-analyzed 'sample' wells
- Applies 50% failure threshold to identify failed index sets
- Extrapolates failed index set results to all wells on the same library plate
- Failed_index_sets column contains Python lists of failed index sets (e.g., ['PE17', 'PE19'])
- Whole plate rework determined by overall 50% failure rate across all sample wells

Quality Threshold System:
- Per-plate DNA concentration thresholds (nmol/L) and size thresholds (bp)
- Automatic dilution factor application for original library concentration calculation
- Pass/fail determination based on both concentration and size criteria
- Systematic quality reporting with detailed failure rate statistics

Note: create_success_marker function commented out per user request
"""


import sys
from pathlib import Path
import shutil
from sqlalchemy import create_engine
import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle
import os


# def create_success_marker():
#     """Create success marker file for workflow manager integration."""
#     script_name = Path(__file__).stem
#     status_dir = Path(".workflow_status")
#     status_dir.mkdir(exist_ok=True)
#     success_file = status_dir / f"{script_name}.success"
    
#     try:
#         with open(success_file, "w") as f:
#             f.write(f"SUCCESS: {script_name} completed at {datetime.now()}\n")
#         print(f"✅ Success marker created: {success_file}")
#     except Exception as e:
#         print(f"❌ ERROR: Could not create success marker: {e}")
#         print("Script failed - workflow manager integration requires success marker")
#         sys.exit()


# Define paths using pathlib strategy
PROJECT_DIR = Path.cwd()

FA_DIR = PROJECT_DIR / "3_FA_analysis"

ARCHIV_DIR = PROJECT_DIR / "archived_files"

ARCHIV_DIR.mkdir(parents=True, exist_ok=True)


##########################
##########################
def compareFolderFileNames(folder_path, file, folder_name):
    """
    Validate that FA plate names in folder match sample names in CSV file.
    
    Args:
        folder_path: Path to the folder containing the FA file
        file: Name of the FA CSV file
        folder_name: Name of the FA plate folder
        
    Raises:
        SystemExit: If plate names don't match
    """
    # Read FA smear analysis output CSV file
    fa_df = pd.read_csv(folder_path / file, usecols=['Sample ID'])
    
    # Extract unique sample names
    sample_list = fa_df['Sample ID'].unique().tolist()
    
    # Parse plate names from sample IDs and add 'F' suffix to match folder naming
    plate_list = [s.split('_')[0] + 'F' for s in sample_list]
    
    # Validate folder name matches parsed plate names
    if folder_name not in set(plate_list):
        print(f'\n\nMismatch between FA plate ID and sample names for plate {folder_name}. Aborting script\n')
        sys.exit()
##########################
##########################

##########################
##########################
def getFAfiles(fa_dir, processed_plates=None):
    """
    Scan directories for FA output files and copy them to the working directory.
    Only processes plates that haven't been processed before.
    
    Args:
        fa_dir: Path to the FA analysis directory
        processed_plates: Set of plate barcodes that have already been processed
        
    Returns:
        Tuple of (List of FA file names that were processed, List of FA result directories for archiving)
        
    Raises:
        SystemExit: If no FA files are found
    """
    if processed_plates is None:
        processed_plates = set()
    
    fa_files = []
    fa_result_dirs_to_archive = []  # Track directories for archiving
    skipped_files = []  # Track skipped files for reporting
    
    for direct in fa_dir.iterdir():
        if direct.is_dir():
            nxt_dir = direct
            
            # scan current directory and find subdirectories
            for fa in nxt_dir.iterdir():
                if fa.is_dir():
                    
                    # find full path to subdirectories
                    folder_path = fa
                    
                    # extract name of FA plate by parsing the subdirectory name
                    folder_name = fa.name
                    folder_name = folder_name.split(' ')[0]
                    
                    # Extract plate barcode (remove 'F' suffix if present)
                    plate_barcode = folder_name.replace('F', '')
                    
                    # Skip if this plate has already been processed
                    if plate_barcode in processed_plates:
                        skipped_files.append(folder_name)
                        continue
                    
                    # search for smear analysis files in each subdirectory
                    for file_path in fa.iterdir():
                        if file_path.name.endswith('Smear Analysis Result.csv'):
                            # confirm folder name matches plate name parsed from
                            # smear analysis .csv sample names.  Error out if mismatch
                            compareFolderFileNames(folder_path, file_path.name, folder_name)
                            
                            # copy and rename smear analysis to main directory if good match
                            shutil.copy(file_path, fa_dir / f'{folder_name}.csv')
                            
                            # add folder name (aka FA plate name) to list
                            fa_files.append(f'{folder_name}.csv')
                            
                            # Track this directory for archiving
                            fa_result_dirs_to_archive.append(fa)
    

    # Report on skipped files
    if skipped_files:
        print(f"\n⏭️  Skipped {len(skipped_files)} already processed plates: {sorted(skipped_files)}")

    # quit script if directory doesn't contain NEW FA .csv files
    if len(fa_files) == 0:
        if skipped_files:
            print(f"\n✅ No new FA files to process. All {len(skipped_files)} available plates have already been processed.")
        else:
            print("\n\nDid not find any FA output files. Aborting program\n\n")
        sys.exit()
    
    # return both lists
    return fa_files, fa_result_dirs_to_archive
##########################
##########################

##########################
##########################
def processFAfiles(my_fa_files):
    """
    Process FA CSV files into DataFrames with cleaned and standardized data.
    
    Args:
        my_fa_files: List of FA file names to process
        
    Returns:
        Tuple of (dictionary mapping filenames to DataFrames, list of destination plates)
        
    Raises:
        SystemExit: If processing fails or file counts don't match
    """
    # create dict where  keys are FA file names and value are df's from those files
    fa_dict = {}

    fa_dest_plates = []

    # loop through all FA files and create df's stored in dict
    for f in my_fa_files:
        fa_dict[f] = pd.read_csv(FA_DIR / f, usecols=[
            'Well', 'Sample ID', 'ng/uL', 'nmole/L', 'Avg. Size'])

        fa_dict[f] = fa_dict[f].rename(
            columns={"Sample ID": "FA_Sample_ID", "Well": "FA_Well_Instrument"})

        fa_dict[f]['FA_Well_Instrument'] = fa_dict[f]['FA_Well_Instrument'].str.replace(
            ':', '')

        # remove rows with "empty" or "ladder" in sample ID. search is case insensitive
        fa_dict[f] = fa_dict[f][fa_dict[f]["FA_Sample_ID"].str.contains(
            'empty', case=False) == False]

        fa_dict[f] = fa_dict[f][fa_dict[f]["FA_Sample_ID"].str.contains(
            'ladder', case=False) == False]

        fa_dict[f] = fa_dict[f][fa_dict[f]["FA_Sample_ID"].str.contains(
            'LibStd', case=False) == False]

        # NEW: Also remove library control samples BEFORE parsing
        fa_dict[f] = fa_dict[f][fa_dict[f]["FA_Sample_ID"].str.contains(
            'library_control', case=False) == False]

        # NEW: Parse FA Sample ID using complex logic for format "HOM7Q-1_BP9735_SitukAM.1_C1"
        # Only parse rows that remain after filtering
        if len(fa_dict[f]) > 0:
            # Split on first underscore to get plate barcode
            fa_dict[f][['FA_Plate_Barcode', 'remaining']] = fa_dict[f]['FA_Sample_ID'].str.split('_', n=1, expand=True)
            
            # Split remaining on last underscore to get plate ID and original well
            fa_dict[f][['FA_Plate_ID', 'FA_Original_Well']] = fa_dict[f]['remaining'].str.rsplit('_', n=1, expand=True)
            
            # Clean up temporary column
            fa_dict[f].drop(['remaining'], axis=1, inplace=True)
        else:
            # If no rows remain after filtering, add empty columns
            fa_dict[f]['FA_Plate_Barcode'] = ''
            fa_dict[f]['FA_Plate_ID'] = ''
            fa_dict[f]['FA_Original_Well'] = ''

        fa_dict[f]['ng/uL'] = fa_dict[f]['ng/uL'].fillna(0)

        fa_dict[f]['nmole/L'] = fa_dict[f]['nmole/L'].fillna(0)

        fa_dict[f]['Avg. Size'] = fa_dict[f]['Avg. Size'].fillna(0)

        fa_dict[f]['FA_Plate_ID'] = fa_dict[f]['FA_Plate_ID'].astype(str)

        fa_dict[f]['ng/uL'] = fa_dict[f]['ng/uL'].astype(float)

        fa_dict[f]['nmole/L'] = fa_dict[f]['nmole/L'].astype(float)

        fa_dict[f]['Avg. Size'] = fa_dict[f]['Avg. Size'].astype(float)

        # add destination plates in fa file to list fa_dest_plates
        fa_dest_plates = fa_dest_plates + \
            fa_dict[f]['FA_Plate_Barcode'].unique().tolist()
    
        # get rid of unnecessary columns
        fa_dict[f].drop(['FA_Sample_ID'], inplace=True, axis=1)

    # quit script if were not able to process FA input files
    if len(fa_dict.keys()) == 0:
        print("\n\nDid not successfully extract FA files\n\n")
        sys.exit()

    # Remove duplicate destination plates for comparison
    unique_dest_plates = list(set(fa_dest_plates))
    
    if len(fa_dict.keys()) != len(unique_dest_plates):
        print(f"\n\nMismatch in number of FA files ({len(fa_dict.keys())}) and unique destination plates ({len(unique_dest_plates)})\n\n")
        print(f"FA files: {list(fa_dict.keys())}")
        print(f"Destination plates: {unique_dest_plates}")
        sys.exit()

    # print out list of successfully processed FA files
    print("\n\n\nList of processed FA output files:\n\n\n")

    for k in fa_dict.keys():
        print(f'{k}\n')

    # add some blank lines after displaying list of processed FA files
    print('\n\n\n')

    return fa_dict, fa_dest_plates
##########################
##########################



##########################
##########################
def readSQLdb():
    """
    Read master plate data from SQLite database.
    
    Returns:
        DataFrame containing master plate data
    """
    # path to sqlite db project_summary.db
    sql_db_path = PROJECT_DIR / 'project_summary.db'

    # create sqlalchemy engine
    engine = create_engine(f'sqlite:///{sql_db_path}') 

    # define sql query
    query = "SELECT * FROM master_plate_data"
    
    # import sql db into pandas df
    sql_df = pd.read_sql(query, engine)
    
    
    engine.dispose()

    return sql_df

def readIndividualPlatesTable():
    """
    Read individual plates table from SQLite database.
    
    Returns:
        DataFrame containing individual plates data
    """
    # path to sqlite db project_summary.db
    sql_db_path = PROJECT_DIR / 'project_summary.db'

    # create sqlalchemy engine
    engine = create_engine(f'sqlite:///{sql_db_path}')

    # define sql query
    query = "SELECT * FROM individual_plates"
    
    # import sql db into pandas df
    individual_plates_df = pd.read_sql(query, engine)
    
    engine.dispose()

    return individual_plates_df

def ensure_fa_tracking_columns():
    """
    Add FA tracking columns to individual_plates table if they don't exist.
    """
    sql_db_path = PROJECT_DIR / 'project_summary.db'
    engine = create_engine(f'sqlite:///{sql_db_path}')
    
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text("PRAGMA table_info(individual_plates)"))
            existing_columns = [row[1] for row in result]
            
            # Add missing columns
            if 'fa_processing_status' not in existing_columns:
                conn.execute(text("ALTER TABLE individual_plates ADD COLUMN fa_processing_status TEXT DEFAULT 'pending'"))
                conn.commit()
                print("✅ Added fa_processing_status column to individual_plates")
                
            if 'fa_processed_timestamp' not in existing_columns:
                conn.execute(text("ALTER TABLE individual_plates ADD COLUMN fa_processed_timestamp TEXT"))
                conn.commit()
                print("✅ Added fa_processed_timestamp column to individual_plates")
                
            if 'fa_batch_id' not in existing_columns:
                conn.execute(text("ALTER TABLE individual_plates ADD COLUMN fa_batch_id TEXT"))
                conn.commit()
                print("✅ Added fa_batch_id column to individual_plates")
        
    except Exception as e:
        print(f"❌ Error adding FA tracking columns: {e}")
        raise
    finally:
        engine.dispose()

def get_processed_plates():
    """
    Identify plates that have already been processed through FA analysis.
    Uses individual_plates table as single source of truth.
    
    Returns:
        set: Set of plate barcodes that have been processed
    """
    try:
        individual_plates_df = readIndividualPlatesTable()
        
        # Check if fa_processing_status column exists
        if 'fa_processing_status' in individual_plates_df.columns:
            # Use explicit tracking column
            processed_plates = set(
                individual_plates_df[
                    individual_plates_df['fa_processing_status'] == 'processed'
                ]['barcode'].tolist()
            )
        else:
            # Fallback: no plates processed yet (first run scenario)
            processed_plates = set()
        
        return processed_plates
        
    except Exception as e:
        print(f"⚠️  Warning: Could not read individual_plates table: {e}")
        print("Assuming first run - no plates processed yet")
        return set()

def analyze_fa_processing_status():
    """
    Analyze FA processing status for all plates.
    
    Returns:
        dict: Processing status information
    """
    master_df = readSQLdb()
    
    # Get all plates with FA wells assigned (scheduled for FA)
    scheduled_mask = master_df['FA_Well'].notna()
    scheduled_plates = set(master_df[scheduled_mask]['Plate_Barcode'].unique())
    
    # Get processed plates from individual_plates table
    processed_plates = get_processed_plates()
    
    # Calculate pending plates
    pending_plates = scheduled_plates - processed_plates
    
    # Get available FA files
    try:
        available_fa_files, _ = getFAfiles(FA_DIR)
        available_plates = set()
        for fa_file in available_fa_files:
            # Extract plate barcode from filename (remove .csv and F suffix)
            plate_barcode = fa_file.replace('.csv', '').replace('F', '')
            available_plates.add(plate_barcode)
    except SystemExit:
        # getFAfiles exits if no files found, catch this
        available_fa_files = []
        available_plates = set()
    
    # Plates ready to process (pending + has FA file available)
    ready_to_process = pending_plates & available_plates
    
    # Plates missing FA files
    missing_fa_files = pending_plates - available_plates
    
    return {
        'scheduled_plates': scheduled_plates,
        'processed_plates': processed_plates,
        'pending_plates': pending_plates,
        'available_plates': available_plates,
        'ready_to_process': ready_to_process,
        'missing_fa_files': missing_fa_files,
        'available_fa_files': available_fa_files
    }

def print_fa_status_report(status):
    """
    Print user-friendly FA processing status report.
    """
    print("\n" + "="*70)
    print("📊 FA PROCESSING STATUS REPORT")
    print("="*70)
    print(f"📋 Total plates scheduled for FA: {len(status['scheduled_plates'])}")
    print(f"✅ Already processed: {len(status['processed_plates'])}")
    print(f"⏳ Pending processing: {len(status['pending_plates'])}")
    print(f"🆕 Ready to process now: {len(status['ready_to_process'])}")
    print(f"❌ Missing FA files: {len(status['missing_fa_files'])}")
    print(f"📁 Available FA files: {len(status['available_fa_files'])}")
    
    if status['ready_to_process']:
        print(f"\n🔬 Will process these plates: {sorted(list(status['ready_to_process']))}")
    
    if status['missing_fa_files']:
        print(f"\n⚠️  Waiting for FA files for: {sorted(list(status['missing_fa_files']))}")
    
    if status['processed_plates']:
        print(f"\n✅ Previously processed: {sorted(list(status['processed_plates']))}")
    
    print("="*70 + "\n")

def update_individual_plates_with_fa_status_sql(processed_plate_barcodes, batch_id):
    """
    Update individual_plates table using SQL UPDATE statements (more efficient than table replacement).
    Following the barcode script's incremental update pattern.
    
    Args:
        processed_plate_barcodes: List of plate barcodes that were successfully processed
        batch_id: Batch ID for this processing run
    """
    if not processed_plate_barcodes:
        return
    
    sql_db_path = PROJECT_DIR / 'project_summary.db'
    engine = create_engine(f'sqlite:///{sql_db_path}')
    
    try:
        timestamp = datetime.now().isoformat()
        
        with engine.connect() as conn:
            from sqlalchemy import text
            
            # Use SQL UPDATE for efficient in-place updates
            for barcode in processed_plate_barcodes:
                update_query = text("""
                    UPDATE individual_plates
                    SET fa_processing_status = :status,
                        fa_processed_timestamp = :timestamp,
                        fa_batch_id = :batch_id
                    WHERE barcode = :barcode
                """)
                
                conn.execute(update_query, {
                    'status': 'processed',
                    'timestamp': timestamp,
                    'batch_id': batch_id,
                    'barcode': barcode
                })
            
            # Commit all updates
            conn.commit()
        
        print(f"✅ Updated individual_plates table: marked {len(processed_plate_barcodes)} plates as processed")
        
    except Exception as e:
        print(f"❌ Error updating individual_plates table: {e}")
        raise
    finally:
        engine.dispose()

def update_individual_plates_with_fa_status(processed_plate_barcodes, batch_id):
    """
    Update individual_plates table to mark plates as processed.
    Uses SQL UPDATE approach for better performance.
    
    Args:
        processed_plate_barcodes: List of plate barcodes that were successfully processed
        batch_id: Batch ID for this processing run
    """
    return update_individual_plates_with_fa_status_sql(processed_plate_barcodes, batch_id)
##########################
##########################



##########################
##########################
def addFAresults(my_prjct_dir, my_fa_df):
    """
    Merge FA results with master plate data using compound key.
    
    Args:
        my_prjct_dir: Project directory path (currently unused)
        my_fa_df: DataFrame containing FA analysis results
        
    Returns:
        Merged DataFrame with FA and project data
        
    Raises:
        SystemExit: If merge operation fails or changes row count
    """
    # create df from sqlite db
    full_master_df = readSQLdb()
    
    # CRITICAL FIX: Extract unique plate barcodes from the FA data (these are the NEW plates)
    new_plate_barcodes = my_fa_df['FA_Plate_Barcode'].unique()
    print(f"🔍 NEW plates being processed: {list(new_plate_barcodes)}")
    
    # Filter master_plate_data to ONLY include the NEW plates being processed
    my_lib_df = full_master_df[full_master_df['Plate_Barcode'].isin(new_plate_barcodes)].copy()
    print(f"📊 Filtered master_plate_data to {my_lib_df.shape[0]} rows for NEW plates only")
    
    # convert columns to string for consistent merging
    my_lib_df['Plate_ID'] = my_lib_df['Plate_ID'].astype(str)
    my_lib_df['Well'] = my_lib_df['Well'].astype(str)

    # NEW: First, identify which samples SHOULD have FA results based on master_plate_data
    # Only exclude samples that are truly not processed:
    # - Type = 'unused' (not processed)
    # - Type = 'ladder' (filtered out during FA processing)
    # Note: neg_cntrl and pos_cntrl samples ARE processed and should have FA results
    excluded_types = ['unused', 'ladder']
    expected_fa_samples_df = my_lib_df[
        (my_lib_df['FA_Well'].notna()) &
        (~my_lib_df['Type'].isin(excluded_types))
    ].copy()
    
    expected_fa_count = expected_fa_samples_df.shape[0]
    
    # NEW: Merge using compound key (Plate_ID + Well) - INNER JOIN to only include FA-analyzed samples
    my_lib_df = my_lib_df.merge(
        my_fa_df,
        how='inner',
        left_on=['Plate_ID', 'Well'],
        right_on=['FA_Plate_ID', 'FA_Original_Well']
    )
    
    # Verify that plate barcodes match (data validation)
    barcode_mismatch = my_lib_df[
        (my_lib_df['Plate_Barcode'] != my_lib_df['FA_Plate_Barcode']) &
        my_lib_df['FA_Plate_Barcode'].notna()
    ]
    
    if len(barcode_mismatch) > 0:
        print(f"\n❌ ERROR: Plate barcode mismatch detected!")
        print("Expected plate barcodes don't match FA sample IDs:")
        print(barcode_mismatch[['Plate_ID', 'Well', 'Plate_Barcode', 'FA_Plate_Barcode']].head())
        sys.exit()
    
    # NEW: Critical verification - ensure we have FA results for ALL expected samples
    expected_fa_count = expected_fa_samples_df.shape[0]
    if my_lib_df.shape[0] != expected_fa_count:
        print(f"\n❌ ERROR: Missing FA results for some expected samples!")
        print(f"Expected samples with FA_Well data: {expected_fa_count}")
        print(f"Actual merged samples: {my_lib_df.shape[0]}")
        
        # Identify which samples are missing FA results
        merged_samples = set(zip(my_lib_df['Plate_ID'], my_lib_df['Well']))
        expected_samples = set(zip(expected_fa_samples_df['Plate_ID'], expected_fa_samples_df['Well']))
        missing_samples = expected_samples - merged_samples
        
        if missing_samples:
            print(f"\nMissing FA results for {len(missing_samples)} samples:")
            for plate_id, well in list(missing_samples)[:10]:  # Show first 10
                print(f"  - {plate_id}, Well {well}")
            if len(missing_samples) > 10:
                print(f"  ... and {len(missing_samples) - 10} more")
        
        sys.exit()
    
    print(f"✅ All expected samples have FA results - no missing data detected")

    # get rid of unnecessary columns from FA parsing
    my_lib_df.drop(['FA_Plate_ID', 'FA_Original_Well', 'FA_Plate_Barcode'], inplace=True, axis=1)

    return my_lib_df
##########################
##########################


##########################
##########################
def findPassFailLibs(my_lib_df, my_dest_plates):
    """
    Apply quality thresholds and identify pass/fail libraries using new index set failure logic.
    
    Args:
        my_lib_df: DataFrame with merged library and FA data
        my_dest_plates: List of destination plate names
        
    Returns:
        DataFrame with pass/fail analysis and rework recommendations
        
    Raises:
        SystemExit: If thresholds file is missing values
    """
    # import df with dna conc and size thresholds for each FA plate
    thresh_df = pd.read_csv(FA_DIR / "thresholds.txt", sep="\t", header=0)
    
    # make sure threshold file has values for all threshold parameters
    if thresh_df.isnull().values.any():
        print('\nThe thresholds.txt file is missing needed values. Aborting\n\n')
        sys.exit()

    # FIXED: Smart merge strategy to handle incremental processing
    # Check which columns already exist to avoid conflicts
    existing_columns = set(my_lib_df.columns)
    threshold_columns = set(thresh_df.columns)
    
    # Identify which plates need threshold data (those without existing threshold columns)
    plates_needing_thresholds = []
    if 'DNA_conc_threshold_(nmol/L)' not in existing_columns:
        # No plates have threshold data yet - this is a fresh run
        plates_needing_thresholds = my_lib_df['Plate_Barcode'].unique().tolist()
    else:
        # Some plates may already have threshold data - check which ones are missing
        plates_with_thresholds = my_lib_df[my_lib_df['DNA_conc_threshold_(nmol/L)'].notna()]['Plate_Barcode'].unique()
        all_plates = my_lib_df['Plate_Barcode'].unique()
        plates_needing_thresholds = [p for p in all_plates if p not in plates_with_thresholds]
    
    if plates_needing_thresholds:
        # Filter threshold data to only plates that need it
        thresh_df_filtered = thresh_df[thresh_df['Destination_plate'].isin(plates_needing_thresholds)].copy()
        
        # Determine merge strategy based on existing columns
        if 'DNA_conc_threshold_(nmol/L)' in existing_columns:
            # Incremental merge - only update rows for new plates
            # Create a mask for rows that need threshold updates
            update_mask = my_lib_df['Plate_Barcode'].isin(plates_needing_thresholds)
            
            # Merge only the rows that need updates
            rows_to_update = my_lib_df[update_mask].copy()
            rows_to_keep = my_lib_df[~update_mask].copy()
            
            # Merge threshold data with rows that need updates
            updated_rows = rows_to_update.merge(thresh_df_filtered, how='left',
                                              left_on='Plate_Barcode', right_on='Destination_plate')
            
            # Combine updated rows with unchanged rows
            my_lib_df = pd.concat([rows_to_keep, updated_rows], ignore_index=True)
            
        else:
            # Fresh merge - no existing threshold columns
            my_lib_df = my_lib_df.merge(thresh_df_filtered, how='left',
                                      left_on='Plate_Barcode', right_on='Destination_plate')
    
    # Check for missing threshold data
    if 'DNA_conc_threshold_(nmol/L)' in my_lib_df.columns:
        missing_thresholds = my_lib_df[my_lib_df['DNA_conc_threshold_(nmol/L)'].isna()]
        if len(missing_thresholds) > 0:
            print(f"\n❌ ERROR: Missing threshold data for plates:")
            print(missing_thresholds['Plate_Barcode'].unique())
            sys.exit()
    else:
        print(f"\n❌ ERROR: No threshold data found in merged DataFrame")
        sys.exit()
    
    # Handle column name conflicts from merge - clean up suffixed columns
    # Handle dilution_factor columns
    if 'dilution_factor_y' in my_lib_df.columns:
        # Use threshold dilution factor (from _y suffix)
        my_lib_df['dilution_factor'] = my_lib_df['dilution_factor_y']
        my_lib_df.drop(['dilution_factor_x', 'dilution_factor_y'], axis=1, inplace=True)
    elif 'dilution_factor_x' in my_lib_df.columns:
        # Use existing dilution factor (from _x suffix)
        my_lib_df['dilution_factor'] = my_lib_df['dilution_factor_x']
        my_lib_df.drop(['dilution_factor_x'], axis=1, inplace=True)
    
    # Handle ng/uL columns
    if 'ng/uL_y' in my_lib_df.columns and 'ng/uL_x' in my_lib_df.columns:
        # Use FA data (from _y suffix), fallback to existing (from _x suffix)
        my_lib_df['ng/uL'] = my_lib_df['ng/uL_y'].fillna(my_lib_df['ng/uL_x'])
        my_lib_df.drop(['ng/uL_x', 'ng/uL_y'], axis=1, inplace=True)
    elif 'ng/uL_y' in my_lib_df.columns:
        my_lib_df['ng/uL'] = my_lib_df['ng/uL_y']
        my_lib_df.drop(['ng/uL_y'], axis=1, inplace=True)
    elif 'ng/uL_x' in my_lib_df.columns:
        my_lib_df['ng/uL'] = my_lib_df['ng/uL_x']
        my_lib_df.drop(['ng/uL_x'], axis=1, inplace=True)
    
    # Handle nmole/L columns
    if 'nmole/L_y' in my_lib_df.columns and 'nmole/L_x' in my_lib_df.columns:
        # Use FA data (from _y suffix), fallback to existing (from _x suffix)
        my_lib_df['nmole/L'] = my_lib_df['nmole/L_y'].fillna(my_lib_df['nmole/L_x'])
        my_lib_df.drop(['nmole/L_x', 'nmole/L_y'], axis=1, inplace=True)
    elif 'nmole/L_y' in my_lib_df.columns:
        my_lib_df['nmole/L'] = my_lib_df['nmole/L_y']
        my_lib_df.drop(['nmole/L_y'], axis=1, inplace=True)
    elif 'nmole/L_x' in my_lib_df.columns:
        my_lib_df['nmole/L'] = my_lib_df['nmole/L_x']
        my_lib_df.drop(['nmole/L_x'], axis=1, inplace=True)
    
    # Handle Avg. Size columns
    if 'Avg. Size_y' in my_lib_df.columns and 'Avg. Size_x' in my_lib_df.columns:
        # Use FA data (from _y suffix), fallback to existing (from _x suffix)
        my_lib_df['Avg. Size'] = my_lib_df['Avg. Size_y'].fillna(my_lib_df['Avg. Size_x'])
        my_lib_df.drop(['Avg. Size_x', 'Avg. Size_y'], axis=1, inplace=True)
    elif 'Avg. Size_y' in my_lib_df.columns:
        my_lib_df['Avg. Size'] = my_lib_df['Avg. Size_y']
        my_lib_df.drop(['Avg. Size_y'], axis=1, inplace=True)
    elif 'Avg. Size_x' in my_lib_df.columns:
        my_lib_df['Avg. Size'] = my_lib_df['Avg. Size_x']
        my_lib_df.drop(['Avg. Size_x'], axis=1, inplace=True)

    # assign pass or fail to each lib based on dna conc and size thresholds
    my_lib_df['Passed_library'] = np.where(((my_lib_df['nmole/L'] > my_lib_df['DNA_conc_threshold_(nmol/L)']) & (
        my_lib_df['Avg. Size'] > my_lib_df['Size_theshold_(bp)'])), 1, 0)

    # update lib conc info based on the dilution factor.  This is conc in original library plate
    my_lib_df['ng/uL'] = my_lib_df['ng/uL'] * my_lib_df['dilution_factor']

    my_lib_df = my_lib_df.round({'ng/uL': 3})

    my_lib_df['nmole/L'] = my_lib_df['nmole/L'] * my_lib_df['dilution_factor']

    my_lib_df = my_lib_df.round({'nmole/L': 3})

    # remove columns no longer needed
    my_lib_df.drop(['Destination_plate', 'DNA_conc_threshold_(nmol/L)',
                   'Size_theshold_(bp)'], inplace=True, axis=1)

    # NEW: Calculate index set failure rates and identify failed index sets
    print("📊 Calculating index set failure rates...")
    
    # Initialize new columns
    my_lib_df['Failed_index_sets'] = [[] for _ in range(len(my_lib_df))]
    my_lib_df['Redo_whole_plate'] = False
    
    # Group by Plate_Barcode to analyze each FA plate separately
    for plate_barcode in my_lib_df['Plate_Barcode'].unique():
        plate_mask = my_lib_df['Plate_Barcode'] == plate_barcode
        plate_data = my_lib_df[plate_mask].copy()
        
        # Only analyze 'sample' type wells that were FA-analyzed
        fa_samples = plate_data[plate_data['Type'] == 'sample'].copy()
        
        if len(fa_samples) == 0:
            continue
            
        print(f"📋 Analyzing plate {plate_barcode}: {len(fa_samples)} sample wells")
        
        # Calculate failure rates for each index set
        failed_index_sets = []
        index_set_stats = {}
        
        for index_set in ['PE17', 'PE18', 'PE19', 'PE20']:
            index_samples = fa_samples[fa_samples['Index_Set'] == index_set]
            
            if len(index_samples) == 0:
                continue
                
            failed_count = len(index_samples[index_samples['Passed_library'] == 0])
            total_count = len(index_samples)
            failure_rate = failed_count / total_count if total_count > 0 else 0
            
            index_set_stats[index_set] = {
                'failed': failed_count,
                'total': total_count,
                'rate': failure_rate
            }
            
            print(f"  {index_set}: {failed_count}/{total_count} failed ({failure_rate:.1%})")
            
            # Mark index set as failed if >50% failure rate
            if failure_rate > 0.5:
                failed_index_sets.append(index_set)
        
        # Calculate overall failure rate for this plate
        total_failed = len(fa_samples[fa_samples['Passed_library'] == 0])
        total_samples = len(fa_samples)
        overall_failure_rate = total_failed / total_samples if total_samples > 0 else 0
        
        print(f"  Overall: {total_failed}/{total_samples} failed ({overall_failure_rate:.1%})")
        
        # Determine if whole plate needs rework (>50% overall failure)
        plate_needs_rework = overall_failure_rate > 0.5
        
        # Apply results to ALL wells on this library plate (not just FA-analyzed ones)
        # This extrapolates FA results to the entire library plate
        # Convert list to string for storage in DataFrame
        failed_index_sets_str = str(failed_index_sets)
        my_lib_df.loc[plate_mask, 'Failed_index_sets'] = failed_index_sets_str
        my_lib_df.loc[plate_mask, 'Redo_whole_plate'] = plate_needs_rework

    return my_lib_df
##########################
##########################

def archive_thresholds_file():
    """
    Archive the thresholds.txt file after processing by moving it to
    previously_processed_threshold_files folder with timestamp suffix.
    """
    thresholds_file = FA_DIR / "thresholds.txt"
    
    if not thresholds_file.exists():
        return
    
    # Create archive directory
    archive_dir = FA_DIR / "previously_processed_threshold_files"
    archive_dir.mkdir(exist_ok=True)
    
    # Create timestamped filename
    timestamp = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
    archived_filename = f"thresholds_{timestamp}.txt"
    archived_path = archive_dir / archived_filename
    
    # Move the file
    shutil.move(str(thresholds_file), str(archived_path))

def generate_fa_summary_statistics(fa_summary_df):
    """
    Generate CSV summary statistics for library pass/fail results by plate and index set.
    
    Args:
        fa_summary_df: DataFrame containing FA analysis results with all wells
        
    Returns:
        DataFrame with summary statistics
    """
    summary_rows = []
    
    # Group by Plate_Barcode to analyze each FA plate separately
    for plate_barcode in fa_summary_df['Plate_Barcode'].unique():
        plate_data = fa_summary_df[fa_summary_df['Plate_Barcode'] == plate_barcode].copy()
        
        # Only analyze 'sample' type wells that were FA-analyzed
        fa_samples = plate_data[plate_data['Type'] == 'sample'].copy()
        
        if len(fa_samples) == 0:
            continue
        
        # Calculate plate-level summary (all samples)
        total_samples = len(fa_samples)
        passed_samples = len(fa_samples[fa_samples['Passed_library'] == 1])
        pass_percentage = round((passed_samples / total_samples) * 100) if total_samples > 0 else 0
        
        summary_rows.append({
            'Plate_Barcode': plate_barcode,
            'Index_Set': 'All',
            'Passed_Count': passed_samples,
            'Total_Count': total_samples,
            'Pass_Percentage': pass_percentage
        })
        
        # Calculate index set summaries
        for index_set in ['PE17', 'PE18', 'PE19', 'PE20']:
            index_samples = fa_samples[fa_samples['Index_Set'] == index_set]
            
            if len(index_samples) == 0:
                continue
                
            total_count = len(index_samples)
            passed_count = len(index_samples[index_samples['Passed_library'] == 1])
            pass_percentage = round((passed_count / total_count) * 100) if total_count > 0 else 0
            
            summary_rows.append({
                'Plate_Barcode': plate_barcode,
                'Index_Set': index_set,
                'Passed_Count': passed_count,
                'Total_Count': total_count,
                'Pass_Percentage': pass_percentage
            })
    
    # Create DataFrame from summary rows
    summary_df = pd.DataFrame(summary_rows)
    
    # Sort by Plate_Barcode and Index_Set (with 'All' first for each plate)
    summary_df['sort_order'] = summary_df['Index_Set'].map({
        'All': 0, 'PE17': 1, 'PE18': 2, 'PE19': 3, 'PE20': 4
    })
    summary_df = summary_df.sort_values(['Plate_Barcode', 'sort_order']).drop('sort_order', axis=1)
    
    print(f"✅ Generated summary statistics for {len(summary_df)} entries")
    return summary_df

def archive_database_file():
    """
    Archive existing database file with timestamp suffix by copying (not moving).
    Follows the barcode script's copy-for-archive pattern for safer database handling.
    """
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
        print(f"📁 Archived database: {archive_path}")


def archive_master_csv_file():
    """
    Archive existing master DataFrame CSV file with timestamp suffix by moving it.
    """
    csv_path = Path("library_dataframe.csv")
    
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
        print(f"📁 Archived CSV: {archive_path}")

def archive_plate_names_csv_file():
    """
    Archive existing plate_names.csv file with timestamp suffix.
    """
    csv_path = Path("plate_names.csv")
    
    if csv_path.exists():
        timestamp = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
        archive_dir = Path("archived_files")
        archive_dir.mkdir(exist_ok=True)
        
        # Create archive name with timestamp suffix
        stem = csv_path.stem  # "plate_names"
        suffix = csv_path.suffix  # ".csv"
        archive_name = f"{stem}_{timestamp}{suffix}"
        archive_path = archive_dir / archive_name
        
        shutil.move(str(csv_path), str(archive_path))
        print(f"📁 Archived CSV: {archive_path}")


def generate_plate_names_csv_from_database():
    """
    Generate fresh plate_names.csv from updated individual_plates table.
    """
    try:
        # Read individual_plates table from database
        sql_db_path = Path("project_summary.db")
        engine = create_engine(f'sqlite:///{sql_db_path}')
        individual_plates_df = pd.read_sql('SELECT * FROM individual_plates', engine)
        engine.dispose()
        
        # Select only the columns that should be in plate_names.csv
        # (excluding FA tracking columns)
        plate_names_columns = ['plate_name', 'project', 'sample', 'plate_number', 'is_custom', 'barcode', 'created_timestamp']
        plate_names_df = individual_plates_df[plate_names_columns].copy()
        
        # Generate fresh plate_names.csv
        output_filename = "plate_names.csv"
        plate_names_df.to_csv(output_filename, index=False)
        
        print(f"✅ Generated fresh {output_filename} with {len(plate_names_df)} rows")
        
        return plate_names_df
        
    except Exception as e:
        print(f"❌ ERROR: Could not generate plate_names.csv: {e}")
        raise


def generate_fresh_library_dataframe_csv(updated_master_df):
    """
    Generate fresh library_dataframe.csv from updated master_plate_data.
    
    Args:
        updated_master_df: Updated master plate data DataFrame
    """
    try:
        output_filename = "library_dataframe.csv"
        updated_master_df.to_csv(output_filename, index=False)
        print(f"✅ Generated fresh library_dataframe.csv with {len(updated_master_df)} rows")
        
    except Exception as e:
        print(f"❌ Error generating library_dataframe.csv: {e}")
        raise


def update_database_with_fa_results_hybrid(fa_summary_df, sample_metadata_df, individual_plates_df, master_plate_data_df):
    """
    Hybrid database update approach:
    - sample_metadata: No changes (never updated)
    - individual_plates: Updated via SQL UPDATE (handled separately)
    - master_plate_data: Complete table replacement (complex FA result merging)
    
    Args:
        fa_summary_df: DataFrame containing FA analysis results with all wells
        sample_metadata_df: Existing sample metadata (unchanged)
        individual_plates_df: Existing individual plates (will be updated separately)
        master_plate_data_df: Existing master plate data to be updated with FA results
    """
    try:
        # Prepare FA results for merging - only keep FA-specific columns
        fa_columns_to_merge = ['Plate_ID', 'Well', 'dilution_factor', 'ng/uL', 'nmole/L', 'Avg. Size', 'Passed_library', 'Failed_index_sets', 'Redo_whole_plate']
        fa_merge_df = fa_summary_df[fa_columns_to_merge].copy()
        
        # Merge FA results with existing master_plate_data
        # Use left join to preserve all existing data, only updating wells that have FA results
        updated_master_df = master_plate_data_df.merge(
            fa_merge_df,
            on=['Plate_ID', 'Well'],
            how='left',
            suffixes=('', '_fa')
        )
        
        # Update columns with FA results where available
        fa_result_columns = ['dilution_factor', 'ng/uL', 'nmole/L', 'Avg. Size', 'Passed_library', 'Failed_index_sets', 'Redo_whole_plate']
        
        for col in fa_result_columns:
            fa_col = f"{col}_fa"
            if fa_col in updated_master_df.columns:
                # Update existing column with FA results where available
                mask = updated_master_df[fa_col].notna()
                if col not in updated_master_df.columns:
                    # Create new column if it doesn't exist
                    updated_master_df[col] = pd.NA
                
                # Special handling for Redo_whole_plate to ensure consistent data type
                if col == 'Redo_whole_plate':
                    # First, standardize ALL existing values to string format
                    existing_values = updated_master_df[col].copy()
                    # Convert all existing values to consistent string format
                    standardized_existing = existing_values.map({
                        True: 'True', False: 'False',
                        1: 'True', 0: 'False', 1.0: 'True', 0.0: 'False',
                        '1': 'True', '0': 'False', 'True': 'True', 'False': 'False'
                    })
                    # Fill any unmapped values with 'False'
                    standardized_existing = standardized_existing.fillna('False')
                    updated_master_df[col] = standardized_existing
                    
                    # Now add the new FA values
                    fa_values = updated_master_df.loc[mask, fa_col]
                    # Convert new boolean values to string representation
                    string_values = fa_values.map({True: 'True', False: 'False', 1: 'True', 0: 'False'})
                    updated_master_df.loc[mask, col] = string_values
                else:
                    updated_master_df.loc[mask, col] = updated_master_df.loc[mask, fa_col]
                
                # Drop the temporary FA column
                updated_master_df.drop(fa_col, axis=1, inplace=True)
            elif col not in updated_master_df.columns:
                # Add new column with default values if it doesn't exist
                if col == 'Failed_index_sets':
                    updated_master_df[col] = [[] for _ in range(len(updated_master_df))]
                elif col == 'Redo_whole_plate':
                    updated_master_df[col] = 'False'  # Use string 'False' instead of boolean
                else:
                    updated_master_df[col] = pd.NA
        
        # Hybrid approach: Only update tables that actually change
        db_path = Path("project_summary.db")
        engine = create_engine(f'sqlite:///{db_path}')
        
        # sample_metadata: Never changes, skip update
        # individual_plates: Updated separately via SQL UPDATE
        # master_plate_data: Replace with updated data (complex merging)
        updated_master_df.to_sql('master_plate_data', engine, if_exists='replace', index=False)
        
        # Properly dispose of engine
        engine.dispose()
        
        print(f"✅ Updated master_plate_data table with FA results for {len(fa_summary_df['Plate_Barcode'].unique())} plates")
        
        return updated_master_df
        
    except Exception as e:
        print(f"❌ FATAL ERROR: Could not update database with FA results: {e}")
        sys.exit(1)

def update_database_with_fa_results(fa_summary_df, sample_metadata_df, individual_plates_df, master_plate_data_df):
    """
    Update database with FA results using hybrid approach.
    """
    return update_database_with_fa_results_hybrid(fa_summary_df, sample_metadata_df, individual_plates_df, master_plate_data_df)


def create_plate_visualization(fa_summary_df, output_dir):
    """
    Create visual representation of plate pass/fail results as PDF.
    
    Args:
        fa_summary_df: DataFrame containing FA analysis results with all wells
        output_dir: Directory to save the PDF output
        
    Returns:
        Path to the generated PDF file
    """
    print("🎨 Creating plate visualizations...")
    
    # Create output directory if it doesn't exist
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get unique plates
    plates = fa_summary_df['Plate_Barcode'].unique()
    
    # Create individual PDFs for each plate
    individual_pdfs = []
    
    for plate_barcode in plates:
        plate_data = fa_summary_df[fa_summary_df['Plate_Barcode'] == plate_barcode].copy()
        
        # Create individual PDF for this plate
        pdf_path = output_dir / f"plate_visualization_{plate_barcode}.pdf"
        individual_pdfs.append(pdf_path)
        
        with PdfPages(pdf_path) as pdf:
            fig, ax = plt.subplots(figsize=(16, 12))
            
            # Set up the plate layout (384-well: 24 columns x 16 rows)
            rows = 16  # A-P
            cols = 24  # 1-24
            well_size = 0.8
            spacing = 1.0
            
            # Row labels A-P
            row_labels = [chr(ord('A') + i) for i in range(rows)]
            
            # Create wells
            for row in range(rows):
                for col in range(cols):
                    # Calculate position
                    x = col * spacing
                    y = (rows - 1 - row) * spacing  # Flip Y to have A at top
                    
                    # Find well data
                    well_id = f"{row_labels[row]}{col + 1}"
                    well_data = plate_data[plate_data['Well'] == well_id]
                    
                    # Determine colors and patterns
                    if len(well_data) == 0:
                        # No data for this well
                        edge_color = 'lightgray'
                        fill_color = 'lightgray'
                        pattern = None
                        well_type = 'no_data'
                    else:
                        well_info = well_data.iloc[0]
                        well_type = well_info.get('Type', 'unknown')
                        
                        # Edge color based on type
                        if well_type == 'sample':
                            edge_color = 'green'
                        elif well_type == 'neg_cntrl':
                            edge_color = 'red'
                        elif well_type == 'pos_cntrl':
                            edge_color = 'blue'
                        elif well_type == 'unused':
                            edge_color = 'gray'
                        else:
                            edge_color = 'black'
                        
                        # Fill color and pattern based on pass/fail
                        if well_type == 'unused' or pd.isna(well_info.get('Passed_library')):
                            fill_color = 'lightgray'
                            pattern = None
                        elif well_info.get('Passed_library') == 1:
                            fill_color = 'lightgreen'
                            pattern = '///'  # Diagonal lines for pass
                        else:
                            fill_color = 'lightcoral'
                            pattern = 'xx'  # X pattern for fail
                    
                    # Create circle for well
                    circle = plt.Circle((x, y), well_size/2,
                                      facecolor=fill_color,
                                      edgecolor=edge_color,
                                      linewidth=2,
                                      hatch=pattern)
                    ax.add_patch(circle)
            
            # Add row labels (A-P)
            for i, label in enumerate(row_labels):
                ax.text(-1.5, (rows - 1 - i) * spacing, label,
                       fontsize=12, ha='center', va='center', fontweight='bold')
            
            # Add column labels (1-24)
            for i in range(cols):
                ax.text(i * spacing, rows * spacing + 0.5, str(i + 1),
                       fontsize=10, ha='center', va='center', fontweight='bold')
            
            # Set axis properties
            ax.set_xlim(-2, cols * spacing)
            ax.set_ylim(-1, rows * spacing + 1)
            ax.set_aspect('equal')
            ax.axis('off')
            
            # Add title
            ax.set_title(f'Plate {plate_barcode} - FA Pass/Fail Results',
                        fontsize=16, fontweight='bold', pad=20)
            
            # Create legend - Section 1: Well Types (Border Colors)
            type_legend_elements = [
                plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='white',
                          markersize=15, markeredgecolor='green', markeredgewidth=3,
                          label='Sample', linestyle='None'),
                plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='white',
                          markersize=15, markeredgecolor='red', markeredgewidth=3,
                          label='Negative Control', linestyle='None'),
                plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='white',
                          markersize=15, markeredgecolor='blue', markeredgewidth=3,
                          label='Positive Control', linestyle='None'),
                plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='white',
                          markersize=15, markeredgecolor='gray', markeredgewidth=3,
                          label='Unused', linestyle='None')
            ]
            
            # Create legend - Section 2: Pass/Fail Results (Fill Colors & Patterns)
            result_legend_elements = [
                plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='lightgreen',
                          markersize=15, markeredgecolor='none', markeredgewidth=0,
                          label='Pass (/// pattern)', linestyle='None'),
                plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='lightcoral',
                          markersize=15, markeredgecolor='none', markeredgewidth=0,
                          label='Fail (XX pattern)', linestyle='None'),
                plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='lightgray',
                          markersize=15, markeredgecolor='none', markeredgewidth=0,
                          label='No Data/Unused', linestyle='None')
            ]
            
            # Add first legend for well types
            type_legend = ax.legend(handles=type_legend_elements, loc='center left',
                                   bbox_to_anchor=(1, 0.75), title='Well Types (Border Color)',
                                   title_fontsize=12, fontsize=10, handletextpad=1.0,
                                   borderpad=1.2, labelspacing=0.8)
            
            # Add second legend for pass/fail results
            result_legend = ax.legend(handles=result_legend_elements, loc='center left',
                                     bbox_to_anchor=(1, 0.25), title='Pass/Fail Results (Fill Color)',
                                     title_fontsize=12, fontsize=10, handletextpad=1.0,
                                     borderpad=1.2, labelspacing=0.8)
            
            # Add the first legend back (matplotlib removes it when adding the second)
            ax.add_artist(type_legend)
            
            plt.tight_layout()
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
        
        pass  # Removed verbose output
    
    # Merge all individual PDFs into one with timestamp
    timestamp = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
    merged_pdf_path = output_dir / f"FA_plate_visualizations_combined_{timestamp}.pdf"
    
    try:
        from PyPDF2 import PdfMerger
        
        merger = PdfMerger()
        for pdf_path in individual_pdfs:
            if pdf_path.exists():
                merger.append(str(pdf_path))
        
        with open(merged_pdf_path, 'wb') as output_file:
            merger.write(output_file)
        merger.close()
        
        # Clean up individual PDFs
        for pdf_path in individual_pdfs:
            if pdf_path.exists():
                pdf_path.unlink()
        
        pass  # Removed verbose output
        
    except ImportError:
        print("⚠️  PyPDF2 not available - keeping individual PDF files")
        merged_pdf_path = None
    
    return merged_pdf_path if merged_pdf_path and merged_pdf_path.exists() else individual_pdfs[0] if individual_pdfs else None


def cleanup_temporary_csv_files(fa_files):
    """Remove temporary CSV files that were copied to FA_DIR for processing"""
    for csv_file in fa_files:
        temp_file_path = FA_DIR / csv_file
        if temp_file_path.exists():
            try:
                temp_file_path.unlink()
            except Exception as e:
                print(f"Warning: Could not remove temporary file {csv_file}: {e}")

def archive_fa_results(fa_result_dirs, archive_subdir_name, batch_id=None):
    """Archive FA result directories to permanent storage by copying them with batch-specific timestamping"""
    if not fa_result_dirs:
        return
    
    # Create batch-specific archive directory with timestamp
    if batch_id is None:
        batch_id = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
    
    archive_base = PROJECT_DIR / "archived_files"
    archive_dir = archive_base / archive_subdir_name / f"batch_{batch_id}"
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📁 Archiving {len(fa_result_dirs)} FA result directories to batch_{batch_id}")
    
    for result_dir in fa_result_dirs:
        if result_dir.exists():
            dest_path = archive_dir / result_dir.name
            
            # Copy directory to archive (no overwrite risk since each batch gets its own folder)
            shutil.copytree(str(result_dir), str(dest_path))
            print(f"   ✅ Archived: {result_dir.name}")

def main():
    """
    Main function to orchestrate the incremental FA analysis workflow.
    """
    print("Starting Capsule FA Analysis...")
    
    # Step 1: Read database tables FIRST (before archiving) - following generate_lib_creation_files.py pattern
    sql_db_path = Path("project_summary.db")
    if not sql_db_path.exists():
        print("❌ ERROR: project_summary.db not found")
        sys.exit()
    
    try:
        # Create sqlalchemy engine and read all tables
        engine = create_engine(f'sqlite:///{sql_db_path}')
        sample_metadata_df = pd.read_sql('SELECT * FROM sample_metadata', engine)
        individual_plates_df = pd.read_sql('SELECT * FROM individual_plates', engine)
        master_plate_data_df = pd.read_sql('SELECT * FROM master_plate_data', engine)
        engine.dispose()
        
    except Exception as e:
        print(f"❌ ERROR: Could not read database: {e}")
        sys.exit()
    
    # Step 2: Ensure FA tracking columns exist in individual_plates table
    ensure_fa_tracking_columns()
    
    # Step 3: Analyze FA processing status
    status = analyze_fa_processing_status()
    print_fa_status_report(status)
    
    # Step 4: Get FA files for ONLY unprocessed plates
    processed_plates = get_processed_plates()
    fa_files, fa_result_dirs_to_archive = getFAfiles(FA_DIR, processed_plates)

    # get dictionary where keys are FA file names and values are df's created from FA files
    # and get a list of destination/lib plate IDs processed
    fa_lib_dict, fa_dest_plates = processFAfiles(fa_files)

    # create new dataframe combining all entries in dictionary fa_lib_dict
    fa_df = pd.concat(fa_lib_dict.values(), ignore_index=True)

    # add FA results to df from master_plate_data (use the pre-read data)
    lib_df = addFAresults(PROJECT_DIR, fa_df)

    # identify libs that passed/failed based on new index set failure logic
    fa_summary_df = findPassFailLibs(lib_df, fa_dest_plates)

    # Archive the thresholds file after processing
    archive_thresholds_file()

    # Generate FA summary statistics CSV (only for newly processed plates)
    summary_stats_df = generate_fa_summary_statistics(fa_summary_df)
    
    # Save summary statistics to CSV file with timestamp
    timestamp = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
    summary_output_file = FA_DIR / f'fa_summary_statistics_{timestamp}.csv'
    summary_stats_df.to_csv(summary_output_file, index=False)
    
    # Step 5: Archive existing database (copy-for-archive strategy)
    archive_database_file()
    
    # Step 6: Update database using hybrid approach
    # 6a: Update master_plate_data table (complex FA result merging)
    updated_master_df = update_database_with_fa_results(fa_summary_df, sample_metadata_df, individual_plates_df, master_plate_data_df)
    
    # 6b: Update individual_plates table using SQL UPDATE (simple status changes)
    processed_plate_barcodes = [plate.replace('F', '') for plate in fa_dest_plates]
    batch_id = timestamp  # Use same timestamp for batch ID
    update_individual_plates_with_fa_status(processed_plate_barcodes, batch_id)
    
    # Step 7: Archive and regenerate CSV files
    archive_master_csv_file()
    archive_plate_names_csv_file()
    generate_fresh_library_dataframe_csv(updated_master_df)
    generate_plate_names_csv_from_database()
    
    # Step 8: Archive FA results with batch-specific timestamping
    if fa_result_dirs_to_archive:
        archive_fa_results(fa_result_dirs_to_archive, "capsule_fa_analysis_results", batch_id)
    
    # Step 9: Generate plate visualizations (only for newly processed plates)
    try:
        visualization_pdf = create_plate_visualization(fa_summary_df, FA_DIR)
    except Exception as e:
        print(f"❌ ERROR: Could not create plate visualizations: {e}")
        print("Continuing without visualizations...")
    
    # Step 10: Clean up temporary CSV files
    cleanup_temporary_csv_files(fa_files)
    
    print(f"\n🎉 FA Analysis completed successfully!")
    print(f"📊 Processed {len(fa_dest_plates)} plates in batch {batch_id}")
    print(f"✅ {len(status['processed_plates']) + len(fa_dest_plates)} total plates now have FA results")
    
    # # Create success marker for workflow manager integration
    # create_success_marker()


if __name__ == "__main__":
    main()