#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Capsule FA Analysis Script

This script processes Fragment Analyzer (FA) output files to analyze DNA library quality.
It reads FA smear analysis results, merges them with master plate data, applies
quality thresholds, and generates summary reports for library pass/fail analysis.

The script expects to be run from the project root directory and will:
1. Find and process FA output CSV files in 3_FA_analysis/
2. Merge with master_plate_data from project_summary.db
3. Apply quality thresholds from thresholds.txt
4. Generate reduced summary output file

"""


import sys
from pathlib import Path
import shutil
from sqlalchemy import create_engine
import pandas as pd
import numpy as np
from datetime import datetime


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
        print(f"❌ ERROR: Could not create success marker: {e}")
        print("Script failed - workflow manager integration requires success marker")
        sys.exit()


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
def getFAfiles(fa_dir):
    """
    Scan directories for FA output files and copy them to the working directory.
    
    Args:
        fa_dir: Path to the FA analysis directory
        
    Returns:
        Tuple of (List of FA file names that were processed, List of FA result directories for archiving)
        
    Raises:
        SystemExit: If no FA files are found
    """
    fa_files = []
    fa_result_dirs_to_archive = []  # NEW: Track directories for archiving
    
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
                            
                            # NEW: Track this directory for archiving
                            fa_result_dirs_to_archive.append(fa)
    

    # quit script if directory doesn't contain FA .csv files
    if len(fa_files) == 0:
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
    my_lib_df = readSQLdb()
    
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
    
    print(f"📊 Expected FA samples (excluding unused & controls): {expected_fa_count}")
    print(f"📊 Actual FA samples (from smear analysis files): {my_fa_df.shape[0]}")

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
    
    print(f"✅ Successfully merged {my_lib_df.shape[0]} FA-analyzed samples with master plate data")
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
    Apply quality thresholds and identify pass/fail libraries.
    
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

    # NEW: Merge thresholds using Plate_Barcode (destination plate barcode)
    my_lib_df = my_lib_df.merge(thresh_df, how='left', left_on=[
        'Plate_Barcode'], right_on=['Destination_plate'], suffixes=('', '_y'))
    
    # Check for missing threshold data
    missing_thresholds = my_lib_df[my_lib_df['dilution_factor'].isna()]
    if len(missing_thresholds) > 0:
        print(f"\n❌ ERROR: Missing threshold data for plates:")
        print(missing_thresholds['Plate_Barcode'].unique())
        sys.exit()

    # get max number of failed libs per plate before triggering whole plate rework
    min_failed_libs = float(
        input("""How many failed libs per plate to trigger whole plate rework?\n
              Default threshold is 20: """) or 20)

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

    # create empty list for whole plates that need rework
    whole_plate_redo = []
    
    # NEW: Use Plate_Barcode for identifying plates that need rework
    for val, cnt in my_lib_df[(my_lib_df['Passed_library'] == 0)]['Plate_Barcode'].value_counts().items():
    
        if cnt >= min_failed_libs:
            whole_plate_redo.append(val)
        

    # sort the list of whole plates that neede to be reworked
    whole_plate_redo = sorted(whole_plate_redo)

    my_lib_df['Redo_whole_plate'] = ""

    # NEW: Use Plate_Barcode for identifying libs that are part of a whole plate rework
    my_lib_df.loc[my_lib_df['Plate_Barcode'].isin(
        whole_plate_redo), 'Redo_whole_plate'] = True

    return my_lib_df
##########################
##########################

def archive_fa_results(fa_result_dirs, archive_subdir_name):
    """Archive FA result directories to permanent storage by copying them"""
    if not fa_result_dirs:
        return
    
    # Create archive directory
    archive_base = PROJECT_DIR / "archived_files"
    archive_dir = archive_base / archive_subdir_name
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    for result_dir in fa_result_dirs:
        if result_dir.exists():
            dest_path = archive_dir / result_dir.name
            
            # Handle existing archives (prevent nesting)
            if dest_path.exists():
                shutil.rmtree(dest_path)
                # print(f"Removing existing archive: {result_dir.name}")
            
            # Copy directory to archive (preserves original)
            shutil.copytree(str(result_dir), str(dest_path))
            print(f"Archived (copied): {result_dir.name}")

def main():
    """
    Main function to orchestrate the FA analysis workflow.
    """
    print("Starting Capsule FA Analysis...")
    
    # MODIFIED: Update function call to receive both returns
    fa_files, fa_result_dirs_to_archive = getFAfiles(FA_DIR)

    # get dictionary where keys are FA file names and values are df's created from FA files
    # and get a list of destination/lib plate IDs processed
    fa_lib_dict, fa_dest_plates = processFAfiles(fa_files)

    # create new dataframe combining all entries in dictionary fa_lib_dict
    fa_df = pd.concat(fa_lib_dict.values(), ignore_index=True)

    # add FA results to df from master_plate_data
    lib_df = addFAresults(PROJECT_DIR, fa_df)

    # identify libs that passed/failed based on user provided thresholds
    fa_summary_df = findPassFailLibs(lib_df, fa_dest_plates)

    # NEW: Create output with correct column names as specified in requirements
    # Expected columns: Plate_ID, Well, Plate_Barcode, FA_Well, dilution_factor, ng/uL, nmole/L, Avg. Size, Passed_library, Redo_whole_plate
    reduced_fa_df = fa_summary_df[['Plate_ID', 'Well', 'Plate_Barcode', 'FA_Well', 'dilution_factor', 'ng/uL', 'nmole/L', 'Avg. Size', 'Passed_library', 'Redo_whole_plate']].copy()

    reduced_fa_df.sort_values(
        by=['Plate_Barcode', 'Plate_ID', 'Well'], inplace=True)

    # create updated library info file
    output_file = FA_DIR / 'reduced_fa_analysis_summary.txt'
    reduced_fa_df.to_csv(output_file, sep='\t', index=False)
    
    print(f"\nAnalysis complete. Output saved to: {output_file}")
    print(f"Processed {len(reduced_fa_df)} samples from {len(fa_dest_plates)} FA plates")
    
    # NEW: Archive FA results before creating success marker
    if fa_result_dirs_to_archive:
        archive_fa_results(fa_result_dirs_to_archive, "capsule_fa_analysis_results")
    
    # Create success marker for workflow manager integration
    create_success_marker()


if __name__ == "__main__":
    main()