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


def read_project_database(base_dir):
    """Read the ESP project database from project_summary.db into pandas DataFrames."""
    db_path = Path(base_dir) / "project_summary.db"
    
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        master_plate_df = pd.read_sql_query("SELECT * FROM master_plate_data", conn)
        individual_plates_df = pd.read_sql_query("SELECT * FROM individual_plates", conn)
        conn.close()
        return master_plate_df, individual_plates_df
        
    except Exception as e:
        print(f"ERROR reading database: {e}")
        raise


def identify_expected_grid_samples(master_plate_df, individual_plates_df):
    """
    Identify which samples should be present in grid tables based on pooling selection.
    
    Logic:
    1. Find plates selected for pooling from individual_plates table
    2. Find samples selected for pooling from master_plate_data table
    3. Return samples that meet both criteria
    """
    if 'selected_for_pooling' not in individual_plates_df.columns:
        print("ERROR: Missing 'selected_for_pooling' column in individual_plates table")
        print("SCRIPT TERMINATED: Cannot determine which plates are selected for pooling")
        sys.exit()
    
    if 'selected_for_pooling' not in master_plate_df.columns:
        print("ERROR: Missing 'selected_for_pooling' column in master_plate_data table")
        print("SCRIPT TERMINATED: Cannot determine which samples are selected for pooling")
        sys.exit()
    
    selected_plates = individual_plates_df[
        individual_plates_df['selected_for_pooling'] == True
    ]['barcode'].tolist()
    
    expected_samples = master_plate_df[
        (master_plate_df['selected_for_pooling'] == True) &
        (master_plate_df['Plate_Barcode'].isin(selected_plates))
    ].copy()
    
    if len(expected_samples) == 0:
        print("ERROR: No samples found that are selected for pooling from plates selected for pooling")
        print("SCRIPT TERMINATED: No expected grid table samples identified")
        sys.exit()
    
    return expected_samples, selected_plates


def validate_grid_table_columns(csv_file):
    """Check if CSV file has required grid table columns without full validation."""
    is_valid, error_msg = validate_grid_table_columns_detailed(csv_file)
    
    if not is_valid:
        print(f"ERROR: Invalid grid table file {csv_file}: {error_msg}")
        print("SCRIPT TERMINATED: Required columns are missing from grid table file")
        sys.exit()
    
    return True


def find_csv_files(base_dir):
    """Find all CSV files in the 4_plate_selection_and_pooling subdirectory."""
    csv_files = []
    try:
        grid_table_dir = Path(base_dir) / "4_plate_selection_and_pooling"
        if not grid_table_dir.exists():
            print(f"ERROR: Grid table directory not found: {grid_table_dir}")
            print("SCRIPT TERMINATED: Required grid table directory does not exist")
            sys.exit()
        
        for file_path in grid_table_dir.glob("*.csv"):
            csv_files.append(str(file_path))
        return csv_files
    except Exception as e:
        print(f"ERROR finding CSV files: {e}")
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
    csv_files = find_csv_files(base_dir)
    
    if not csv_files:
        print("ERROR: No CSV files found in 4_plate_selection_and_pooling directory")
        print("SCRIPT TERMINATED: Grid table directory contains no CSV files")
        sys.exit()
    
    valid_files = []
    invalid_files = []
    
    for csv_file in csv_files:
        is_valid, error_msg = validate_grid_table_columns_detailed(csv_file)
        if is_valid:
            valid_files.append(csv_file)
        else:
            invalid_files.append((csv_file, error_msg))
    
    if len(valid_files) == 0:
        print(f"ERROR: No valid grid table found in 4_plate_selection_and_pooling directory")
        print(f"Found {len(csv_files)} CSV file(s), but none contain the required columns:")
        for csv_file, error_msg in invalid_files:
            print(f"  - {Path(csv_file).name}: {error_msg}")
        print("A grid table CSV file must contain: Well, Library Plate Label, Illumina Library, Library Plate Container Barcode, Nucleic Acid ID")
        print("SCRIPT TERMINATED: No valid grid table files found")
        sys.exit()
    
    return valid_files


def validate_grid_table_columns_detailed(csv_file):
    """Check if CSV file has required grid table columns with detailed error reporting."""
    required_cols = ['Well', 'Library Plate Label', 'Illumina Library', 'Library Plate Container Barcode', 'Nucleic Acid ID']
    
    try:
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
        
        try:
            grid_df = pd.read_csv(filename)
            grid_dataframes[grid_path.name] = grid_df
            grid_df['Source_File'] = grid_path.name
            
            if combined_grid_df.empty:
                combined_grid_df = grid_df.copy()
            else:
                combined_grid_df = pd.concat([combined_grid_df, grid_df], ignore_index=True)
            
        except Exception as e:
            print(f"ERROR processing {filename}: {e}")
            continue
    
    if combined_grid_df.empty:
        raise ValueError("No valid grid table data could be read")
    
    return grid_dataframes, combined_grid_df


def detect_duplicate_samples(grid_dataframes):
    """
    Detect duplicate samples across grid tables.
    Adapted from SPS version for ESP workflow.
    """
    all_samples = []
    sample_sources = {}
    
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
    
    duplicates = {sample: sources for sample, sources in sample_sources.items() 
                 if len(sources) > 1}
    
    if duplicates:
        print(f"ERROR: Found {len(duplicates)} duplicate samples:")
        for sample, sources in duplicates.items():
            print(f"  {sample} appears in: {', '.join(sources)}")
        print("SCRIPT TERMINATED: Duplicate samples detected - data integrity compromised")
        sys.exit()
    else:
        return {}


def validate_grid_table_completeness(expected_samples, combined_grid_df):
    """
    Validate that grid table contains exactly the expected samples (no more, no less).
    """
    expected_set = set(zip(expected_samples['Plate_Barcode'], expected_samples['Well']))
    grid_set = set(zip(combined_grid_df['Library Plate Label'], combined_grid_df['Well']))
    
    missing_from_grid = expected_set - grid_set
    unexpected_in_grid = grid_set - expected_set
    
    if missing_from_grid:
        print(f"ERROR: Found {len(missing_from_grid)} expected samples missing from grid tables:")
        for plate_barcode, well in missing_from_grid:
            print(f"  {plate_barcode} - {well}")
        print("SCRIPT TERMINATED: Expected samples missing from grid tables")
        sys.exit()
    
    if unexpected_in_grid:
        print(f"ERROR: Found {len(unexpected_in_grid)} unexpected samples in grid tables:")
        for plate_barcode, well in unexpected_in_grid:
            print(f"  {plate_barcode} - {well}")
        print("SCRIPT TERMINATED: Grid tables contain samples not selected for pooling")
        sys.exit()
    
    return True


def validate_and_merge_data(master_plate_df, expected_samples, grid_df):
    """
    Validate and merge grid table data with master plate dataframe.
    Only expected samples should have grid data, but all master data is preserved.
    
    ESP merging strategy:
    - Grid table: ['Library Plate Label', 'Well']
    - Master plate data: ['Plate_Barcode', 'Well']
    """
    grid_merge_cols = ['Library Plate Label', 'Well']
    db_merge_cols = ['Plate_Barcode', 'Well']
    
    missing_grid_cols = [col for col in grid_merge_cols if col not in grid_df.columns]
    missing_db_cols = [col for col in db_merge_cols if col not in master_plate_df.columns]
    
    if missing_grid_cols:
        print(f"ERROR: Missing grid table columns: {missing_grid_cols}")
        print("SCRIPT TERMINATED: Required columns missing from grid table")
        sys.exit()
    if missing_db_cols:
        print(f"ERROR: Missing master plate data columns: {missing_db_cols}")
        print("SCRIPT TERMINATED: Required columns missing from database")
        sys.exit()
    
    grid_data_cols = ['Illumina Library', 'Nucleic Acid ID', 'Library Plate Container Barcode']
    grid_merge_df = grid_df[grid_merge_cols + grid_data_cols].copy()
    
    grid_merge_df = grid_merge_df.rename(columns={
        'Library Plate Label': 'Plate_Barcode'
    })
    
    merged_df = pd.merge(
        master_plate_df,
        grid_merge_df,
        on=['Plate_Barcode', 'Well'],
        how='left',
        suffixes=(None, '_y')
    )
    
    columns_to_remove = ['Well_y']
    for col in columns_to_remove:
        if col in merged_df.columns:
            merged_df = merged_df.drop(columns=[col])
    
    missing_grid_data = []
    for _, row in expected_samples.iterrows():
        merged_row = merged_df[
            (merged_df['Plate_Barcode'] == row['Plate_Barcode']) &
            (merged_df['Well'] == row['Well'])
        ]
        if merged_row.empty or pd.isna(merged_row.iloc[0]['Nucleic Acid ID']):
            missing_grid_data.append((row['Plate_Barcode'], row['Well']))
    
    if missing_grid_data:
        print("ERROR: Some expected samples are missing grid table data:")
        for plate_barcode, well in missing_grid_data:
            print(f"  {plate_barcode} - {well}")
        print("SCRIPT TERMINATED: Incomplete merge - not all expected samples have grid data")
        sys.exit()
    
    return merged_df


def create_smear_analysis_file(merged_df, base_dir):
    """
    Create the ESP smear analysis file for upload in the proper ESP format.
    
    This function transforms the merged dataframe into the ESP smear file format
    with the required 13 columns and proper data mapping.
    """
    if merged_df.empty:
        print("ERROR: No merged data available for smear analysis file")
        print("SCRIPT TERMINATED: Cannot create output file without merged data")
        sys.exit()
    
    grid_samples = merged_df[merged_df['Nucleic Acid ID'].notna()].copy()
    
    if grid_samples.empty:
        print("ERROR: No samples with grid table data found for smear analysis file")
        print("SCRIPT TERMINATED: Cannot create smear file without grid table samples")
        sys.exit()
    
    smear_df = pd.DataFrame()
    
    smear_df['Well'] = grid_samples['Well']
    smear_df['Sample ID'] = grid_samples['Illumina Library']
    smear_df['Range'] = '400 bp to 800 bp'
    smear_df['ng/uL'] = grid_samples['ng/uL']
    smear_df['%Total'] = 15
    smear_df['nmole/L'] = grid_samples['nmole/L']
    smear_df['Avg. Size'] = grid_samples['Avg. Size']
    smear_df['%CV'] = 20
    smear_df['Volume uL'] = 20
    smear_df['QC Result'] = 'Pass'
    smear_df['Failure Mode'] = ''
    smear_df['Index Name'] = grid_samples['Index_Name']
    smear_df['PCR Cycles'] = 12
    
    expected_columns = ['Well', 'Sample ID', 'Range', 'ng/uL', '%Total', 'nmole/L',
                       'Avg. Size', '%CV', 'Volume uL', 'QC Result', 'Failure Mode',
                       'Index Name', 'PCR Cycles']
    
    missing_columns = [col for col in expected_columns if col not in smear_df.columns]
    if missing_columns:
        print(f"ERROR: Missing required ESP format columns: {missing_columns}")
        print("SCRIPT TERMINATED: Cannot create complete ESP smear file")
        sys.exit()
    
    smear_df = smear_df[expected_columns]
    
    unique_plates = grid_samples['Library Plate Container Barcode'].unique()
    
    esp_smear_dir = Path(base_dir) / "4_plate_selection_and_pooling" / "B_smear_file_for_ESP_upload"
    esp_smear_dir.mkdir(parents=True, exist_ok=True)
    
    output_files = []
    for plate_barcode in unique_plates:
        plate_samples = grid_samples[grid_samples['Library Plate Container Barcode'] == plate_barcode]
        plate_smear_df = smear_df[grid_samples['Library Plate Container Barcode'] == plate_barcode].copy()
        
        output_filename = f'ESP_smear_file_for_upload_{plate_barcode}.csv'
        output_path = esp_smear_dir / output_filename
        
        plate_smear_df.to_csv(output_path, index=False)
        output_files.append(output_path)
        print(f"✓ Created ESP smear file: {output_filename} ({len(plate_smear_df)} samples)")
    
    return output_files


def archive_grid_table_files(base_dir, grid_table_files):
    """
    Create 'previously_processed_grid_files' folder and move all grid table files there.
    
    Args:
        base_dir (Path): Base directory containing the 4_plate_selection_and_pooling folder
        grid_table_files (list): List of grid table file paths to move
    """
    archive_dir = Path(base_dir) / "4_plate_selection_and_pooling" / "previously_processed_grid_files"
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    moved_files = []
    for grid_file_path in grid_table_files:
        grid_file = Path(grid_file_path)
        if grid_file.exists():
            dest_path = archive_dir / grid_file.name
            grid_file.rename(dest_path)
            moved_files.append(dest_path)
        else:
            print(f"⚠️ Grid table file not found for archiving: {grid_file_path}")
    
    return moved_files


def archive_database_file(base_dir):
    """
    Archive existing database file with timestamp suffix by copying (not moving).
    Follows the capsule_fa_analysis.py copy-for-archive pattern for safer database handling.
    """
    db_path = Path(base_dir) / "project_summary.db"
    
    if db_path.exists():
        timestamp = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
        archive_dir = Path(base_dir) / "archived_files"
        archive_dir.mkdir(exist_ok=True)
        
        stem = db_path.stem
        suffix = db_path.suffix
        archive_name = f"{stem}_{timestamp}{suffix}"
        archive_path = archive_dir / archive_name
        
        import shutil
        shutil.copy2(str(db_path), str(archive_path))
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
    mapping_df = combined_grid_df[['Library Plate Label', 'Library Plate Container Barcode']].drop_duplicates()
    barcode_mapping = dict(zip(mapping_df['Library Plate Label'], mapping_df['Library Plate Container Barcode']))
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
            result = conn.execute(text("PRAGMA table_info(individual_plates)"))
            existing_columns = [row[1] for row in result]
            
            if 'esp_generation_status' not in existing_columns:
                conn.execute(text("ALTER TABLE individual_plates ADD COLUMN esp_generation_status TEXT DEFAULT 'pending'"))
                conn.commit()
                
            if 'esp_generated_timestamp' not in existing_columns:
                conn.execute(text("ALTER TABLE individual_plates ADD COLUMN esp_generated_timestamp TEXT"))
                conn.commit()
                
            if 'esp_batch_id' not in existing_columns:
                conn.execute(text("ALTER TABLE individual_plates ADD COLUMN esp_batch_id TEXT"))
                conn.commit()
                
            if 'library_plate_container_barcode' not in existing_columns:
                conn.execute(text("ALTER TABLE individual_plates ADD COLUMN library_plate_container_barcode TEXT"))
                conn.commit()
            
            for barcode in processed_plate_barcodes:
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
                
                if not container_barcode:
                    print(f"⚠️ No Library Plate Container Barcode found for plate {barcode}")
            
            conn.commit()
        
    except Exception as e:
        print(f"ERROR updating individual_plates table: {e}")
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
        merged_df.to_sql('master_plate_data', engine, if_exists='replace', index=False)
        
    except Exception as e:
        print(f"ERROR updating master_plate_data table: {e}")
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
    
    master_csv_path = Path(base_dir) / "master_plate_data.csv"
    if master_csv_path.exists():
        archive_name = f"master_plate_data_{timestamp}.csv"
        archive_path = archive_dir / archive_name
        import shutil
        shutil.move(str(master_csv_path), str(archive_path))
        archived_files['master_plate_data'] = archive_path
    
    plates_csv_path = Path(base_dir) / "individual_plates.csv"
    if plates_csv_path.exists():
        archive_name = f"individual_plates_{timestamp}.csv"
        archive_path = archive_dir / archive_name
        import shutil
        shutil.move(str(plates_csv_path), str(archive_path))
        archived_files['individual_plates'] = archive_path
    
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
        master_csv_path = Path(base_dir) / "master_plate_data.csv"
        updated_master_df.to_csv(master_csv_path, index=False)
        
        sql_db_path = Path(base_dir) / 'project_summary.db'
        from sqlalchemy import create_engine
        engine = create_engine(f'sqlite:///{sql_db_path}')
        individual_plates_df = pd.read_sql('SELECT * FROM individual_plates', engine)
        engine.dispose()
        
        plates_csv_path = Path(base_dir) / "individual_plates.csv"
        individual_plates_df.to_csv(plates_csv_path, index=False)
        
    except Exception as e:
        print(f"ERROR generating fresh CSV files: {e}")
        raise


def main():
    """Main execution function for ESP smear analysis file generation."""
    parser = argparse.ArgumentParser(
        description="Generate ESP smear analysis files from grid tables and database"
    )
    args = parser.parse_args()
    
    try:
        print("Starting ESP smear analysis file generation...")
        
        base_dir = Path.cwd()
        
        if not base_dir.exists():
            raise FileNotFoundError(f"Base directory not found: {base_dir}")
        
        master_plate_df, individual_plates_df = read_project_database(base_dir)
        expected_samples, selected_plates = identify_expected_grid_samples(master_plate_df, individual_plates_df)
        grid_table_files = find_all_grid_tables(base_dir)
        
        if not grid_table_files:
            print("ERROR: No valid grid table files found!")
            sys.exit()
        
        grid_dataframes, combined_grid_df = read_multiple_grid_tables(grid_table_files)
        detect_duplicate_samples(grid_dataframes)
        validate_grid_table_completeness(expected_samples, combined_grid_df)
        merged_df = validate_and_merge_data(master_plate_df, expected_samples, combined_grid_df)
        output_files = create_smear_analysis_file(merged_df, base_dir)
        
        if output_files:
            archive_grid_table_files(base_dir, grid_table_files)
            
            grid_samples = merged_df[merged_df['Nucleic Acid ID'].notna()].copy()
            processed_plate_barcodes = list(grid_samples['Plate_Barcode'].unique())
            batch_id = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
            
            barcode_mapping = extract_library_plate_container_barcode_mapping(combined_grid_df)
            update_individual_plates_with_esp_status(base_dir, processed_plate_barcodes, batch_id, barcode_mapping)
            update_master_plate_data_table(base_dir, merged_df)
            archive_csv_files(base_dir)
            generate_fresh_csv_files(base_dir, merged_df)
            
            print(f"\n🎉 ESP smear analysis completed successfully!")
            print(f"📊 Generated {len(output_files)} ESP smear file(s) for {len(processed_plate_barcodes)} plate(s)")

            create_success_marker()

        else:
            print("ERROR: Failed to create smear analysis file")
            sys.exit()

    except Exception as e:
        print(f"ERROR: ESP smear analysis generation failed: {e}")
        sys.exit()


if __name__ == "__main__":
    main()
