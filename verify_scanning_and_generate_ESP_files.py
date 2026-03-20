#!/usr/bin/env python3
"""
Barcode Scanning Verification and ESP File Generation Script

New Script 2 in the refactored ESP workflow.

Workflow position:
  process_grid_tables_and_generate_barcodes.py → Manual barcode scanning → [This script]

This script:
1. Gets the proposal value from the database
2. Finds the completed Excel barcode scanning file in B_new_plate_barcode_labels/
3. Validates barcode scanning completion (checks Checker column for FALSE values)
4. If validation passes, reads the database (READ-ONLY for data, then updates ESP status)
5. Generates ESP smear analysis files in C_smear_file_for_ESP_upload/
6. Updates individual_plates table with ESP generation status (esp_generation_status,
   esp_generated_timestamp, esp_batch_id)
7. Creates success marker

Key design principles:
- FAIL FAST: Any FALSE in Checker column → sys.exit() immediately
- Database is read for plate/sample data, then updated with ESP status columns only
- No grid table processing (that was Script 1's job)
- No barcode mapping changes (library_plate_container_barcode already set by Script 1)

Output directory: 4_plate_selection_and_pooling/C_smear_file_for_ESP_upload/
"""

import os
import sys
import sqlite3
import openpyxl
import pandas as pd
import argparse
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# Success marker
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Database reading (read-only for plate data)
# ---------------------------------------------------------------------------

def read_project_database(base_dir):
    """
    Read the ESP project database from project_summary.db into pandas DataFrames.
    Used read-only for plate/sample data retrieval.
    """
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


def get_proposal_from_database(base_dir):
    """
    Get proposal value from sample_metadata table.

    Args:
        base_dir: Project base directory

    Returns:
        Proposal value as string

    Raises:
        SystemExit: If proposal cannot be retrieved
    """
    db_path = Path(base_dir) / "project_summary.db"

    if not db_path.exists():
        print(f"ERROR: Database not found: {db_path}")
        print("SCRIPT TERMINATED: project_summary.db is required")
        sys.exit()

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        query = "SELECT DISTINCT Proposal FROM sample_metadata WHERE Proposal IS NOT NULL"
        cursor.execute(query)
        results = cursor.fetchall()
        conn.close()

        if not results:
            print("ERROR: No proposal values found in sample_metadata table")
            print("SCRIPT TERMINATED: Cannot determine proposal for file lookup")
            sys.exit()

        if len(results) > 1:
            proposals = [str(row[0]) for row in results]
            print(f"ERROR: Multiple proposal values found: {proposals}. Expected only one.")
            print("SCRIPT TERMINATED: Ambiguous proposal value")
            sys.exit()

        return str(results[0][0])

    except sqlite3.Error as e:
        print(f"ERROR reading proposal from database: {e}")
        print("SCRIPT TERMINATED: Database error during proposal lookup")
        sys.exit()


# ---------------------------------------------------------------------------
# Excel barcode scanning validation
# ---------------------------------------------------------------------------

def find_barcode_scanning_file(base_dir, proposal):
    """
    Find the completed Excel barcode scanning file.

    Looks in: 4_plate_selection_and_pooling/B_new_plate_barcode_labels/
    Expected filename: {proposal}_pool_label_scan_verificiation_tool.xlsx

    Args:
        base_dir: Project base directory
        proposal: Proposal value for filename matching

    Returns:
        Path to Excel file

    Raises:
        SystemExit: If Excel file not found
    """
    search_dir = (
        Path(base_dir) / "4_plate_selection_and_pooling" / "B_new_plate_barcode_labels"
    )
    expected_filename = f"{proposal}_pool_label_scan_verificiation_tool.xlsx"
    excel_path = search_dir / expected_filename

    if not excel_path.exists():
        print(f"ERROR: Barcode scanning file not found: {excel_path}")
        print(f"Expected location: {search_dir}")
        print(f"Expected filename: {expected_filename}")
        print("SCRIPT TERMINATED: Complete barcode scanning before running this script")
        sys.exit()

    return excel_path


def validate_barcode_scanning_completion(excel_path):
    """
    Validate that barcode scanning was completed successfully.

    Reads the Excel file with data_only=True to get formula-evaluated values.

    Template structure:
        - Checker column = Column D
        - Data rows start at row 2
        - "plate name" rows (even rows starting at 2): D2, D4, D6... up to D40
        - Checker values: True (boolean) = match, "empty" (string) = unused slot
        - Checker value: False (boolean) = MISMATCH → FATAL ERROR

    Args:
        excel_path: Path to Excel barcode scanning file

    Raises:
        SystemExit: If any FALSE values found in Checker column, or file cannot be read
    """
    try:
        workbook = openpyxl.load_workbook(excel_path, data_only=True)
        worksheet = workbook['Sheet1']

        checker_column = 4  # Column D
        false_found = False
        false_rows = []

        # Check only "plate name" rows (rows 2, 4, 6, ... 40)
        # These are the rows that have Checker formulas
        for row in range(2, 42, 2):
            cell_value = worksheet.cell(row=row, column=checker_column).value

            # False (boolean) = barcode mismatch → FATAL
            if cell_value is False or cell_value == "FALSE":
                false_found = True
                false_rows.append(row)

        workbook.close()

        if false_found:
            print("FATAL ERROR: Barcode scanning validation failed!")
            print(f"Found FALSE values in Checker column (Column D) at rows: {false_rows}")
            print("This means scanned barcodes do not match expected barcodes.")
            print("Please review and correct the barcode scanning before proceeding.")
            print("SCRIPT TERMINATED: Barcode scanning validation failed")
            sys.exit()

        print("✓ Barcode scanning validation passed (no FALSE values in Checker column)")

    except Exception as e:
        print(f"ERROR reading barcode scanning file: {e}")
        print("SCRIPT TERMINATED: Could not validate barcode scanning")
        sys.exit()


# ---------------------------------------------------------------------------
# ESP smear file generation
# ---------------------------------------------------------------------------

def create_smear_analysis_file(merged_df, base_dir):
    """
    Create the ESP smear analysis files for upload in the proper ESP format.

    Generates one CSV file per Library Plate Container Barcode.
    Output directory: 4_plate_selection_and_pooling/C_smear_file_for_ESP_upload/

    ESP format columns (13 total):
        Well, Sample ID, Range, ng/uL, %Total, nmole/L, Avg. Size,
        %CV, Volume uL, QC Result, Failure Mode, Index Name, PCR Cycles

    Args:
        merged_df: Master plate dataframe with grid table data merged in
        base_dir: Project base directory

    Returns:
        list: Paths to created ESP smear files
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

    expected_columns = [
        'Well', 'Sample ID', 'Range', 'ng/uL', '%Total', 'nmole/L',
        'Avg. Size', '%CV', 'Volume uL', 'QC Result', 'Failure Mode',
        'Index Name', 'PCR Cycles',
    ]

    missing_columns = [col for col in expected_columns if col not in smear_df.columns]
    if missing_columns:
        print(f"ERROR: Missing required ESP format columns: {missing_columns}")
        print("SCRIPT TERMINATED: Cannot create complete ESP smear file")
        sys.exit()

    smear_df = smear_df[expected_columns]

    unique_plates = grid_samples['Library Plate Container Barcode'].unique()

    esp_smear_dir = (
        Path(base_dir) / "4_plate_selection_and_pooling" / "C_smear_file_for_ESP_upload"
    )
    esp_smear_dir.mkdir(parents=True, exist_ok=True)

    output_files = []
    for plate_barcode in unique_plates:
        plate_mask = grid_samples['Library Plate Container Barcode'] == plate_barcode
        plate_smear_df = smear_df[plate_mask].copy()

        output_filename = f'ESP_smear_file_for_upload_{plate_barcode}.csv'
        output_path = esp_smear_dir / output_filename

        plate_smear_df.to_csv(output_path, index=False)
        output_files.append(output_path)
        print(f"  ✓ Created ESP smear file: {output_filename} ({len(plate_smear_df)} samples)")

    return output_files


# ---------------------------------------------------------------------------
# CSV file archiving and regeneration
# ---------------------------------------------------------------------------

def archive_individual_plates_csv(base_dir):
    """
    Archive the existing individual_plates.csv with a timestamp suffix.
    Follows the same pattern as Script 1 (capsule_fa_analysis.py pattern).

    Args:
        base_dir: Project base directory

    Returns:
        Path to archived file, or None if no file existed
    """
    import shutil
    timestamp = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
    archive_dir = Path(base_dir) / "archived_files"
    archive_dir.mkdir(exist_ok=True)

    plates_csv_path = Path(base_dir) / "individual_plates.csv"
    if plates_csv_path.exists():
        archive_name = f"individual_plates_{timestamp}.csv"
        archive_path = archive_dir / archive_name
        shutil.move(str(plates_csv_path), str(archive_path))
        return archive_path
    return None


def regenerate_individual_plates_csv(base_dir):
    """
    Generate a fresh individual_plates.csv from the updated database.
    Ensures the CSV reflects the latest ESP status columns added by Script 2.

    Args:
        base_dir: Project base directory
    """
    try:
        sql_db_path = Path(base_dir) / 'project_summary.db'
        from sqlalchemy import create_engine
        engine = create_engine(f'sqlite:///{sql_db_path}')
        individual_plates_df = pd.read_sql('SELECT * FROM individual_plates', engine)
        engine.dispose()

        plates_csv_path = Path(base_dir) / "individual_plates.csv"
        individual_plates_df.to_csv(plates_csv_path, index=False)

    except Exception as e:
        print(f"ERROR regenerating individual_plates.csv: {e}")
        raise


# ---------------------------------------------------------------------------
# Database update: ESP status (Script 2 responsibility)
# ---------------------------------------------------------------------------

def update_individual_plates_with_esp_status(base_dir, processed_plate_barcodes, batch_id):
    """
    Update individual_plates table with ESP generation status.

    This is Script 2's database responsibility — adding ESP-related columns
    once the ESP smear files have actually been generated.

    Adds columns if they don't exist:
        - esp_generation_status (TEXT, default 'pending')
        - esp_generated_timestamp (TEXT)
        - esp_batch_id (TEXT)

    Args:
        base_dir: Project base directory
        processed_plate_barcodes: List of plate barcodes that generated ESP files
        batch_id: Batch ID for this processing run
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
                conn.execute(text(
                    "ALTER TABLE individual_plates ADD COLUMN esp_generation_status TEXT DEFAULT 'pending'"
                ))
                conn.commit()

            if 'esp_generated_timestamp' not in existing_columns:
                conn.execute(text(
                    "ALTER TABLE individual_plates ADD COLUMN esp_generated_timestamp TEXT"
                ))
                conn.commit()

            if 'esp_batch_id' not in existing_columns:
                conn.execute(text(
                    "ALTER TABLE individual_plates ADD COLUMN esp_batch_id TEXT"
                ))
                conn.commit()

            for barcode in processed_plate_barcodes:
                update_query = text("""
                    UPDATE individual_plates
                    SET esp_generation_status = :status,
                        esp_generated_timestamp = :timestamp,
                        esp_batch_id = :batch_id
                    WHERE barcode = :barcode
                """)

                conn.execute(update_query, {
                    'status': 'generated',
                    'timestamp': timestamp,
                    'batch_id': batch_id,
                    'barcode': barcode,
                })

            conn.commit()

    except Exception as e:
        print(f"ERROR updating individual_plates ESP status: {e}")
        raise
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def main():
    """Main execution function for barcode verification and ESP file generation."""
    parser = argparse.ArgumentParser(
        description=(
            "Verify barcode scanning completion and generate ESP smear analysis files. "
            "Run from within a project directory after completing barcode scanning in Excel."
        )
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    args = parser.parse_args()

    try:
        print("=" * 60)
        print("Starting barcode verification and ESP file generation...")
        print("=" * 60)

        base_dir = Path.cwd()

        if not base_dir.exists():
            raise FileNotFoundError(f"Base directory not found: {base_dir}")

        # ------------------------------------------------------------------
        # Step 1: Get proposal value from database
        # ------------------------------------------------------------------
        print("\n[Step 1] Getting proposal value from database...")
        proposal = get_proposal_from_database(base_dir)
        print(f"  ✓ Proposal: {proposal}")

        # ------------------------------------------------------------------
        # Step 2: Find the completed Excel barcode scanning file
        # ------------------------------------------------------------------
        print("\n[Step 2] Finding barcode scanning file...")
        excel_path = find_barcode_scanning_file(base_dir, proposal)
        print(f"  ✓ Found: {excel_path.name}")

        # ------------------------------------------------------------------
        # Step 3: Validate barcode scanning (FATAL if any FALSE in Checker)
        # ------------------------------------------------------------------
        print("\n[Step 3] Validating barcode scanning completion...")
        validate_barcode_scanning_completion(excel_path)

        # ------------------------------------------------------------------
        # Step 4: Read database for ESP file generation
        # ------------------------------------------------------------------
        print("\n[Step 4] Reading project database...")
        master_plate_df, individual_plates_df = read_project_database(base_dir)
        print(f"  ✓ master_plate_data: {len(master_plate_df)} rows")
        print(f"  ✓ individual_plates: {len(individual_plates_df)} rows")

        # Verify library_plate_container_barcode column exists (Script 1 must have run)
        if 'library_plate_container_barcode' not in individual_plates_df.columns:
            print("ERROR: 'library_plate_container_barcode' column missing from individual_plates")
            print("SCRIPT TERMINATED: Run process_grid_tables_and_generate_barcodes.py first")
            sys.exit()

        # Verify Library Plate Container Barcode column exists in master_plate_data
        if 'Library Plate Container Barcode' not in master_plate_df.columns:
            print("ERROR: 'Library Plate Container Barcode' column missing from master_plate_data")
            print("SCRIPT TERMINATED: Run process_grid_tables_and_generate_barcodes.py first")
            sys.exit()

        # ------------------------------------------------------------------
        # Step 5: Generate ESP smear files
        # ------------------------------------------------------------------
        print("\n[Step 5] Generating ESP smear analysis files...")
        output_files = create_smear_analysis_file(master_plate_df, base_dir)

        if not output_files:
            print("ERROR: Failed to create any ESP smear analysis files")
            sys.exit()

        # ------------------------------------------------------------------
        # Step 6: Update individual_plates with ESP status
        # ------------------------------------------------------------------
        print("\n[Step 6] Updating database with ESP generation status...")
        grid_samples = master_plate_df[master_plate_df['Nucleic Acid ID'].notna()].copy()
        processed_plate_barcodes = list(grid_samples['Plate_Barcode'].unique())
        batch_id = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")

        update_individual_plates_with_esp_status(base_dir, processed_plate_barcodes, batch_id)
        print(f"  ✓ ESP status updated for {len(processed_plate_barcodes)} plate(s)")

        # ------------------------------------------------------------------
        # Step 7: Archive old individual_plates.csv and regenerate from DB
        # ------------------------------------------------------------------
        print("\n[Step 7] Refreshing individual_plates.csv...")
        archived = archive_individual_plates_csv(base_dir)
        if archived:
            print(f"  ✓ Archived: {archived.name}")
        regenerate_individual_plates_csv(base_dir)
        print(f"  ✓ Fresh individual_plates.csv generated (includes ESP status columns)")

        # ------------------------------------------------------------------
        # Done
        # ------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("🎉 Barcode verification and ESP file generation completed successfully!")
        print(f"📊 Generated {len(output_files)} ESP smear file(s)")
        print(f"📁 Output directory: 4_plate_selection_and_pooling/C_smear_file_for_ESP_upload/")
        print("=" * 60)

        create_success_marker()

    except Exception as e:
        print(f"\nERROR: ESP file generation failed: {e}")
        sys.exit()


if __name__ == "__main__":
    main()
