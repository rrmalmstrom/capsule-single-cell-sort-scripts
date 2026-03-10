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
"""

import os
import sys
import sqlite3
import pandas as pd
import argparse
from pathlib import Path
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_success_marker():
    """Create success marker file for workflow manager integration."""
    marker_file = Path("ESP_smear_analysis_SUCCESS.txt")
    try:
        with open(marker_file, 'w') as f:
            f.write(f"ESP smear analysis completed successfully at {datetime.now()}\n")
        logger.info(f"Success marker created: {marker_file}")
    except Exception as e:
        logger.error(f"Failed to create success marker: {e}")


def read_project_database(base_dir):
    """Read the ESP project database from project_summary.db into a pandas DataFrame."""
    db_path = Path(base_dir) / "project_summary.db"
    
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        # Read from master_plate_data table (identified from database inspection)
        db_df = pd.read_sql_query("SELECT * FROM master_plate_data", conn)
        conn.close()
        
        logger.info(f"Successfully read database with {len(db_df)} records")
        logger.info(f"Database columns: {list(db_df.columns)}")
        
        return db_df
        
    except Exception as e:
        logger.error(f"Error reading database: {e}")
        raise


def validate_grid_table_columns(csv_file):
    """Check if CSV file has required grid table columns without full validation."""
    required_columns = [
        'Illumina Library',
        'Nucleic Acid ID', 
        'Library Plate Container Barcode',
        'Well',
        'Library Plate Label'
    ]
    
    try:
        # Read just the header to check columns
        df_header = pd.read_csv(csv_file, nrows=0)
        missing_columns = [col for col in required_columns if col not in df_header.columns]
        
        if missing_columns:
            logger.warning(f"Missing columns in {csv_file}: {missing_columns}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error validating {csv_file}: {e}")
        return False


def find_csv_files(base_dir):
    """Find all CSV files in the 4_plate_selection_and_pooling subdirectory."""
    csv_files = []
    try:
        # Look in the 4_plate_selection_and_pooling subdirectory
        grid_table_dir = Path(base_dir) / "4_plate_selection_and_pooling"
        if not grid_table_dir.exists():
            logger.warning(f"Grid table directory not found: {grid_table_dir}")
            return []
        
        for file_path in grid_table_dir.glob("*.csv"):
            csv_files.append(str(file_path))
        logger.info(f"Found {len(csv_files)} CSV files in {grid_table_dir}")
        return csv_files
    except Exception as e:
        logger.error(f"Error finding CSV files: {e}")
        return []


def find_all_grid_tables(base_dir):
    """
    Find all valid grid table CSV files in the base directory.
    Adapted from SPS version to work with ESP grid table format.
    """
    logger.info("Searching for grid table files...")
    
    csv_files = find_csv_files(base_dir)
    valid_grid_tables = []
    
    for csv_file in csv_files:
        if validate_grid_table_columns(csv_file):
            valid_grid_tables.append(csv_file)
            logger.info(f"Valid grid table found: {Path(csv_file).name}")
        else:
            logger.info(f"Skipping non-grid table file: {Path(csv_file).name}")
    
    if not valid_grid_tables:
        logger.warning("No valid grid table files found!")
    else:
        logger.info(f"Found {len(valid_grid_tables)} valid grid table(s)")
    
    return valid_grid_tables


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
        logger.info(f"Processing grid table: {grid_path.name}")
        
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
            
            logger.info(f"Successfully processed {grid_path.name}: {len(grid_df)} rows")
            
        except Exception as e:
            logger.error(f"Error processing {filename}: {e}")
            continue
    
    if combined_grid_df.empty:
        raise ValueError("No valid grid table data could be read")
    
    logger.info(f"Combined grid table: {len(combined_grid_df)} total rows from {len(grid_dataframes)} files")
    
    return grid_dataframes, combined_grid_df


def detect_duplicate_samples(grid_dataframes):
    """
    Detect duplicate samples across grid tables.
    Adapted from SPS version for ESP workflow.
    """
    logger.info("Checking for duplicate samples across grid tables...")
    
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
        logger.warning(f"Found {len(duplicates)} duplicate samples:")
        for sample, sources in duplicates.items():
            logger.warning(f"  {sample} appears in: {', '.join(sources)}")
        return duplicates
    else:
        logger.info("No duplicate samples found")
        return {}


def validate_and_merge_data(db_df, grid_df):
    """
    Validate and merge grid table data with ESP database.
    
    ESP merging strategy:
    - Grid table: ['Library Plate Label', 'Well'] 
    - Database: ['Plate_Barcode', 'Well']
    """
    logger.info("Validating and merging grid table with ESP database...")
    
    # Check required columns exist
    grid_merge_cols = ['Library Plate Label', 'Well']
    db_merge_cols = ['Plate_Barcode', 'Well']
    
    missing_grid_cols = [col for col in grid_merge_cols if col not in grid_df.columns]
    missing_db_cols = [col for col in db_merge_cols if col not in db_df.columns]
    
    if missing_grid_cols:
        raise ValueError(f"Missing grid table columns: {missing_grid_cols}")
    if missing_db_cols:
        raise ValueError(f"Missing database columns: {missing_db_cols}")
    
    # Prepare dataframes for merging
    grid_merge_df = grid_df[grid_merge_cols + ['Nucleic Acid ID', 'Illumina Library', 'Source_File']].copy()
    db_merge_df = db_df.copy()
    
    # Rename columns for merging
    grid_merge_df = grid_merge_df.rename(columns={
        'Library Plate Label': 'Plate_Barcode'  # Map to database column name
    })
    
    # Perform the merge
    merged_df = pd.merge(
        grid_merge_df,
        db_merge_df,
        on=['Plate_Barcode', 'Well'],
        how='inner',
        suffixes=('_grid', '_db')
    )
    
    logger.info(f"Merge results:")
    logger.info(f"  Grid table rows: {len(grid_df)}")
    logger.info(f"  Database rows: {len(db_df)}")
    logger.info(f"  Merged rows: {len(merged_df)}")
    
    if len(merged_df) == 0:
        logger.warning("No matching records found between grid table and database!")
    
    return merged_df


def identify_missing_samples(db_df, combined_grid_df):
    """
    Identify samples that are in the database but missing from grid tables.
    Adapted from SPS version for ESP workflow.
    """
    logger.info("Identifying missing samples...")
    
    # Get unique plate/well combinations from each dataset
    db_samples = set(zip(db_df['Plate_Barcode'], db_df['Well']))
    grid_samples = set(zip(combined_grid_df['Library Plate Label'], combined_grid_df['Well']))
    
    # Find missing samples (in database but not in grid tables)
    missing_samples = db_samples - grid_samples
    
    if missing_samples:
        logger.warning(f"Found {len(missing_samples)} samples in database but missing from grid tables:")
        for plate_barcode, well in missing_samples:
            logger.warning(f"  {plate_barcode} - {well}")
    else:
        logger.info("No missing samples found")
    
    return missing_samples


def create_smear_analysis_file(merged_df, output_dir):
    """
    Create the ESP smear analysis file for upload.
    """
    logger.info("Creating ESP smear analysis file...")
    
    if merged_df.empty:
        logger.warning("No merged data available for smear analysis file")
        return None
    
    # Create output filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"ESP_smear_analysis_{timestamp}.csv"
    output_path = Path(output_dir) / output_filename
    
    # Select and rename columns for output
    output_df = merged_df[[
        'Nucleic Acid ID',
        'Illumina Library', 
        'Plate_Barcode',
        'Well',
        'Sample',
        'ng/uL',
        'Avg. Size',
        'Passed_library',
        'Source_File'
    ]].copy()
    
    # Save the file
    output_df.to_csv(output_path, index=False)
    logger.info(f"ESP smear analysis file created: {output_path}")
    
    return output_path


def main():
    """Main execution function for ESP smear analysis file generation."""
    parser = argparse.ArgumentParser(
        description="Generate ESP smear analysis files from grid tables and database"
    )
    parser.add_argument(
        "base_dir",
        help="Base directory containing grid table CSV files and project_summary.db"
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Output directory for smear analysis files (default: current directory)"
    )
    
    args = parser.parse_args()
    
    try:
        logger.info("Starting ESP smear analysis file generation...")
        logger.info(f"Base directory: {args.base_dir}")
        logger.info(f"Output directory: {args.output_dir}")
        
        # Validate directories
        base_dir = Path(args.base_dir)
        output_dir = Path(args.output_dir)
        
        if not base_dir.exists():
            raise FileNotFoundError(f"Base directory not found: {base_dir}")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Read ESP database
        logger.info("Reading ESP project database...")
        db_df = read_project_database(base_dir)
        
        # Find and read grid tables
        logger.info("Finding grid table files...")
        grid_table_files = find_all_grid_tables(base_dir)
        
        if not grid_table_files:
            logger.error("No valid grid table files found!")
            sys.exit(1)
        
        # Read and combine grid tables
        grid_dataframes, combined_grid_df = read_multiple_grid_tables(grid_table_files)
        
        # Check for duplicates
        duplicates = detect_duplicate_samples(grid_dataframes)
        if duplicates:
            logger.warning("Duplicate samples detected - review before proceeding")
        
        # Identify missing samples
        missing_samples = identify_missing_samples(db_df, combined_grid_df)
        
        # Merge data
        merged_df = validate_and_merge_data(db_df, combined_grid_df)
        
        # Create smear analysis file
        output_file = create_smear_analysis_file(merged_df, output_dir)
        
        if output_file:
            logger.info("ESP smear analysis file generation completed successfully!")
            create_success_marker()
        else:
            logger.error("Failed to create smear analysis file")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"ESP smear analysis generation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()