#!/usr/bin/env python3
"""
Test script to demonstrate new BarTender file output using sample data.
This shows the simplified barcode system in action.
"""

import pandas as pd
import sys
from pathlib import Path

# Add current directory to path to import our functions
sys.path.append('.')
from generate_barcode_labels import read_sample_csv, make_plate_names, generate_simple_barcodes, make_bartender_file

def test_bartender_output():
    """Generate example BarTender file using sample data."""
    
    print("=" * 60)
    print("Testing New BarTender File Output")
    print("Using sample_metadtata.csv with simplified barcode system")
    print("=" * 60)
    
    # Read sample CSV
    print("\n1. Reading sample CSV file...")
    sample_df = read_sample_csv('sample_metadtata.csv')
    print(f"   Found {len(sample_df)} samples")
    
    # Generate plate names
    print("\n2. Generating plate names...")
    plates_df = make_plate_names(sample_df)
    print(f"   Generated {len(plates_df)} plates")
    
    # Generate simplified barcodes
    print("\n3. Generating simplified barcodes...")
    plates_df = generate_simple_barcodes(plates_df)
    print(f"   Generated barcodes for {len(plates_df)} plates")
    
    # Show first few plates with barcodes
    print("\n4. Sample plates with new barcodes:")
    for i, row in plates_df.head(10).iterrows():
        print(f"   {row['plate_name']} → {row['barcode']}")
    
    # Generate BarTender file
    print("\n5. Generating BarTender file...")
    bartender_file = 'test_bartender_output.csv'
    make_bartender_file(plates_df, bartender_file)
    print(f"   Created: {bartender_file}")
    
    # Show the BarTender file contents
    print(f"\n6. BarTender file contents ({bartender_file}):")
    print("-" * 60)
    with open(bartender_file, 'r') as f:
        content = f.read()
        print(content)
    print("-" * 60)
    
    print(f"\n✅ Test completed! BarTender file created with {len(plates_df)} plates")
    print(f"   Each plate has echo and hamilton variants with lowercase prefixes")
    print(f"   Barcodes use simplified incremental system (e.g., BP9735.1, BP9735.2)")

if __name__ == "__main__":
    test_bartender_output()