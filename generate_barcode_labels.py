#!/usr/bin/env python3

"""
Laboratory Barcode Label Generation Script

This script generates BarTender-compatible barcode labels for microwell plates
following laboratory safety standards and Test-Driven Development (TDD) approach.

USAGE: python generate_barcode_labels.py

CRITICAL REQUIREMENTS:
- MUST use sip-lims conda environment
- Follows existing SPS script patterns
- Implements comprehensive error handling with "FATAL ERROR" messaging
- Creates success markers for workflow manager integration

Features:
- Reads sample metadata from CSV files
- Generates unique 5-character base barcodes with Echo/Hamilton suffixes
- Stores data in SQLite database using SQLAlchemy
- Creates BarTender-compatible label files
- Handles both first-run and subsequent-run scenarios
- Archives existing files with timestamps
- Interactive user interface for custom plates

Database Schema:
- plate_barcodes table with unique constraints
- Tracks plate names, barcodes, project info, and timestamps

Safety Features:
- Comprehensive barcode uniqueness validation
- Laboratory-grade error messaging
- File archiving before updates
- Success marker creation for workflow integration
"""

import pandas as pd
import random
import sys
import shutil
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, text

# Constants following implementation guide
CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
BARTENDER_HEADER = '%BTW% /AF="\\\\BARTENDER\\shared\\templates\\ECHO_BCode8.btw" /D="%Trigger File Name%" /PRN="bcode8" /R=3 /P /DD\r\n\r\n%END%\r\n\r\n\r\n'

# Database and file names
DATABASE_NAME = "sample_metadtata.db"
BARTENDER_FILE = "BARTENDER_sort_plate_labels.txt"


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
        required_cols = ['Proposal', 'Project', 'Sample', 'Number_of_sorted_plates']
        missing = [col for col in required_cols if col not in df.columns]
        
        if missing:
            print(f"FATAL ERROR: Missing required columns in CSV file: {missing}")
            print(f"Required columns: {required_cols}")
            print(f"Found columns: {list(df.columns)}")
            print("Laboratory automation requires exact column names for safety.")
            sys.exit(1)
        
        # Validate data types
        try:
            df['Number_of_sorted_plates'] = df['Number_of_sorted_plates'].astype(int)
        except ValueError as e:
            print(f"FATAL ERROR: Invalid data in 'Number_of_sorted_plates' column: {e}")
            print("All values must be integers for laboratory automation safety.")
            sys.exit(1)
        
        print(f"✅ Successfully read {len(df)} samples from CSV file")
        return df
        
    except FileNotFoundError:
        print(f"FATAL ERROR: CSV file not found: {csv_path}")
        print("Laboratory automation requires valid input files for safety.")
        raise
    except Exception as e:
        print(f"FATAL ERROR: Could not read CSV file {csv_path}: {e}")
        print("Laboratory automation requires valid CSV format for safety.")
        sys.exit(1)


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
        project = row['Project']
        sample = row['Sample']
        num_plates = int(row['Number_of_sorted_plates'])
        
        # Generate plate names for each sample
        for i in range(1, num_plates + 1):
            plates.append({
                'plate_name': f"{project}_{sample}.{i}",
                'project': project,
                'sample': sample,
                'plate_number': i,
                'is_custom': False
            })
    
    result_df = pd.DataFrame(plates)
    print(f"✅ Generated {len(result_df)} standard plate names")
    return result_df


def generate_barcodes(plates_df, existing_df=None):
    """
    Generate unique barcodes for all plates with collision avoidance.
    
    Args:
        plates_df (pd.DataFrame): DataFrame of plates needing barcodes
        existing_df (pd.DataFrame, optional): Existing plates to avoid collisions
        
    Returns:
        pd.DataFrame: DataFrame with generated barcodes
        
    Raises:
        SystemExit: If unique barcodes cannot be generated
    """
    # Get existing barcodes to avoid collisions
    existing_codes = set()
    if existing_df is not None:
        existing_codes.update(existing_df['base_barcode'].tolist())
        existing_codes.update(existing_df['echo_barcode'].tolist())
        existing_codes.update(existing_df['hamilton_barcode'].tolist())
    
    print(f"Avoiding {len(existing_codes)} existing barcodes")
    
    # Generate new barcodes
    for idx in plates_df.index:
        attempts = 0
        max_attempts = 1000
        
        while attempts < max_attempts:
            # Generate 5-character base code
            base_code = ''.join(random.choices(CHARSET, k=5))
            echo_code = f"{base_code}E"
            hamilton_code = f"{base_code}H"
            
            # Check for collisions
            if (base_code not in existing_codes and 
                echo_code not in existing_codes and 
                hamilton_code not in existing_codes):
                
                # Assign barcodes
                plates_df.at[idx, 'base_barcode'] = base_code
                plates_df.at[idx, 'echo_barcode'] = echo_code
                plates_df.at[idx, 'hamilton_barcode'] = hamilton_code
                plates_df.at[idx, 'created_timestamp'] = datetime.now().isoformat()
                
                # Add to existing set to avoid future collisions
                existing_codes.update([base_code, echo_code, hamilton_code])
                break
            
            attempts += 1
        
        if attempts >= max_attempts:
            print(f"FATAL ERROR: Could not generate unique barcode for plate: {plates_df.at[idx, 'plate_name']}")
            print(f"Attempted {max_attempts} combinations without success.")
            print("Laboratory automation requires unique barcodes for safety.")
            sys.exit(1)
    
    print(f"✅ Generated {len(plates_df)} unique barcode sets")
    return plates_df


def validate_barcode_uniqueness(df):
    """
    Validate that all barcodes in DataFrame are unique.
    
    Args:
        df (pd.DataFrame): DataFrame with barcode columns
        
    Returns:
        bool: True if all barcodes are unique, False otherwise
    """
    all_barcodes = (df['base_barcode'].tolist() + 
                   df['echo_barcode'].tolist() + 
                   df['hamilton_barcode'].tolist())
    
    return len(all_barcodes) == len(set(all_barcodes))


def save_to_database(df, db_path):
    """
    Save DataFrame to SQLite database using SQLAlchemy.
    
    Args:
        df (pd.DataFrame): DataFrame to save
        db_path (Path): Path to database file
        
    Raises:
        SystemExit: If database operation fails
    """
    try:
        engine = create_engine(f'sqlite:///{db_path}')
        
        # Save with replace to handle updates
        df.to_sql('plate_barcodes', engine, if_exists='replace', index=False)
        
        # Properly dispose of engine
        engine.dispose()
        
        print(f"✅ Saved {len(df)} plates to database: {db_path}")
        
    except Exception as e:
        print(f"FATAL ERROR: Could not save to database {db_path}: {e}")
        print("Laboratory automation requires reliable data storage for safety.")
        sys.exit(1)


def read_from_database(db_path):
    """
    Read DataFrame from SQLite database using SQLAlchemy.
    
    Args:
        db_path (Path): Path to database file
        
    Returns:
        pd.DataFrame or None: DataFrame if successful, None if file doesn't exist
        
    Raises:
        SystemExit: If database read fails unexpectedly
    """
    if not Path(db_path).exists():
        return None
    
    try:
        engine = create_engine(f'sqlite:///{db_path}')
        df = pd.read_sql('SELECT * FROM plate_barcodes', engine)
        engine.dispose()
        
        print(f"✅ Read {len(df)} plates from database: {db_path}")
        return df
        
    except Exception as e:
        print(f"FATAL ERROR: Could not read from database {db_path}: {e}")
        print("Laboratory automation requires reliable data access for safety.")
        sys.exit(1)


def make_bartender_file(df, output_path):
    """
    Generate BarTender label file with exact format specification.
    
    Args:
        df (pd.DataFrame): DataFrame with barcode data
        output_path (Path): Path for output file
        
    Raises:
        SystemExit: If file creation fails
    """
    try:
        with open(output_path, 'w', newline='') as f:
            # Write header
            f.write(BARTENDER_HEADER)
            
            # Write Echo labels
            for _, row in df.iterrows():
                f.write(f'{row["echo_barcode"]},"{row["plate_name"]} Echo"\r\n')
            f.write(',\r\n')
            
            # Write Hamilton labels
            for _, row in df.iterrows():
                f.write(f'{row["hamilton_barcode"]},"{row["plate_name"]} Hamilton"\r\n')
            
            # Add proper trailing empty lines for BarTender compatibility
            f.write('\r\n')
        
        print(f"✅ Created BarTender file: {output_path}")
        print(f"   Echo labels: {len(df)}")
        print(f"   Hamilton labels: {len(df)}")
        
    except Exception as e:
        print(f"FATAL ERROR: Could not create BarTender file {output_path}: {e}")
        print("Laboratory automation requires valid label files for safety.")
        sys.exit(1)


def get_csv_file():
    """
    Prompt user for CSV file path with validation.
    
    Returns:
        str: Valid CSV file path
    """
    while True:
        path = input("Enter CSV file path: ").strip()
        if Path(path).exists():
            return path
        print("File not found. Try again.")


def get_custom_plates():
    """
    Get custom plate names from user input.
    
    Returns:
        list: List of custom plate names
    """
    custom = input("Add custom plates? (y/n): ").lower().strip()
    if custom != 'y':
        return []
    
    plates = []
    print("Enter custom plate names (empty line to finish):")
    while True:
        name = input("Plate name: ").strip()
        if not name:
            break
        plates.append(name)
    
    return plates


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
        sys.exit(1)


def archive_existing_files(file_list):
    """
    Archive existing files with timestamp.
    
    Args:
        file_list (list): List of Path objects to archive
    """
    timestamp = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
    archive_dir = Path("archived_files")
    archive_dir.mkdir(exist_ok=True)
    
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


def main():
    """
    Main script execution following laboratory safety standards.
    """
    print("=" * 60)
    print("Laboratory Barcode Label Generation")
    print("Following SPS Laboratory Safety Standards")
    print("=" * 60)
    
    # Check if database exists (first run vs subsequent run)
    existing_df = read_from_database(DATABASE_NAME)
    
    if existing_df is None:
        # First run - process CSV file
        print("\n🔬 FIRST RUN DETECTED")
        print("Processing sample metadata CSV file...")
        
        csv_file = get_csv_file()
        sample_df = read_sample_csv(csv_file)
        plates_df = make_plate_names(sample_df)
        
        # Add custom plates if requested
        custom_plates = get_custom_plates()
        if custom_plates:
            custom_df = pd.DataFrame([
                {'plate_name': name, 'project': 'CUSTOM', 'sample': 'CUSTOM', 
                 'plate_number': 1, 'is_custom': True}
                for name in custom_plates
            ])
            plates_df = pd.concat([plates_df, custom_df], ignore_index=True)
            print(f"✅ Added {len(custom_plates)} custom plates")
        
    else:
        # Subsequent run - add additional plates
        print(f"\n🔄 SUBSEQUENT RUN DETECTED")
        print(f"Found existing database with {len(existing_df)} plates")
        
        # Get additional plates (simplified for this implementation)
        custom_plates = get_custom_plates()
        if not custom_plates:
            print("No new plates to add. Exiting.")
            return
        
        plates_df = pd.DataFrame([
            {'plate_name': name, 'project': 'CUSTOM', 'sample': 'CUSTOM', 
             'plate_number': 1, 'is_custom': True}
            for name in custom_plates
        ])
        print(f"✅ Prepared {len(custom_plates)} new plates for processing")
    
    # Generate barcodes for new plates
    print(f"\n🏷️  GENERATING BARCODES")
    print(f"Generating barcodes for {len(plates_df)} plates...")
    plates_df = generate_barcodes(plates_df, existing_df)
    
    # Validate barcode uniqueness
    if not validate_barcode_uniqueness(plates_df):
        print("FATAL ERROR: Generated barcodes are not unique!")
        print("Laboratory automation requires unique identifiers for safety.")
        sys.exit(1)
    
    # Combine with existing data
    if existing_df is not None:
        final_df = pd.concat([existing_df, plates_df], ignore_index=True)
    else:
        final_df = plates_df
    
    # Final validation
    if not validate_barcode_uniqueness(final_df):
        print("FATAL ERROR: Final barcode set contains duplicates!")
        print("Laboratory automation requires unique identifiers for safety.")
        sys.exit(1)
    
    # Archive existing files
    print(f"\n📁 ARCHIVING EXISTING FILES")
    files_to_archive = [Path(DATABASE_NAME), Path(BARTENDER_FILE)]
    archive_existing_files(files_to_archive)
    
    # Save to database
    print(f"\n💾 SAVING TO DATABASE")
    save_to_database(final_df, DATABASE_NAME)
    
    # Generate BarTender file
    print(f"\n🏷️  GENERATING BARTENDER FILE")
    make_bartender_file(final_df, BARTENDER_FILE)
    
    # Summary
    print(f"\n" + "=" * 60)
    print("🎉 SUCCESS! Laboratory barcode generation completed")
    print("=" * 60)
    print(f"Total plates processed: {len(final_df)}")
    print(f"New plates added: {len(plates_df)}")
    print(f"Database file: {DATABASE_NAME}")
    print(f"BarTender file: {BARTENDER_FILE}")
    print(f"Unique barcodes validated: ✅")
    print("=" * 60)
    
    # Create success marker for workflow manager
    create_success_marker()
    
    print("\n✅ Laboratory barcode generation workflow completed successfully!")
    print("Ready for laboratory automation systems.")


if __name__ == "__main__":
    main()