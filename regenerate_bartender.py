#!/usr/bin/env python3

"""
Quick script to regenerate BarTender file with fixed format
"""

from generate_barcode_labels import read_from_database, make_bartender_file, DATABASE_NAME, BARTENDER_FILE
from pathlib import Path

def main():
    # Read existing data from database
    df = read_from_database(DATABASE_NAME)
    
    if df is not None:
        # Generate BarTender file with fixed format
        make_bartender_file(df, Path(BARTENDER_FILE))
        print(f"✅ Regenerated BarTender file with fixed format")
    else:
        print("❌ No database found")

if __name__ == "__main__":
    main()