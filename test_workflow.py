#!/usr/bin/env python3

"""
Test script to validate the complete workflow with real data
"""

import sys
from pathlib import Path
from unittest.mock import patch
from generate_barcode_labels import main

def test_first_run_workflow():
    """Test the complete first-run workflow with real data."""
    print("=" * 60)
    print("TESTING FIRST RUN WORKFLOW")
    print("=" * 60)
    
    # Clean up any existing files
    db_file = Path("sample_metadtata.db")
    bartender_file = Path("BARTENDER_sort_plate_labels.txt")
    
    if db_file.exists():
        db_file.unlink()
    if bartender_file.exists():
        bartender_file.unlink()
    
    # Mock user inputs for first run
    user_inputs = [
        'test_input_data_files/sample_metadtata.csv',  # CSV file path
        'y',  # Add custom plates
        'Custom_Test_Plate.1',  # Custom plate 1
        'Custom_Test_Plate.2',  # Custom plate 2
        ''    # Empty line to finish custom plates
    ]
    
    with patch('builtins.input', side_effect=user_inputs):
        try:
            main()
            print("\n✅ First run workflow completed successfully!")
            
            # Verify files were created
            assert db_file.exists(), "Database file was not created"
            assert bartender_file.exists(), "BarTender file was not created"
            
            print(f"✅ Database file created: {db_file}")
            print(f"✅ BarTender file created: {bartender_file}")
            
            # Check file contents
            with open(bartender_file, 'r') as f:
                content = f.read()
                assert '%BTW%' in content, "BarTender header missing"
                assert 'Echo' in content, "Echo labels missing"
                assert 'Hamilton' in content, "Hamilton labels missing"
                print("✅ BarTender file format validated")
            
            return True
            
        except Exception as e:
            print(f"❌ First run workflow failed: {e}")
            return False

def test_subsequent_run_workflow():
    """Test the subsequent run workflow."""
    print("\n" + "=" * 60)
    print("TESTING SUBSEQUENT RUN WORKFLOW")
    print("=" * 60)
    
    # Mock user inputs for subsequent run
    user_inputs = [
        'y',  # Add custom plates
        'Additional_Plate.1',  # Additional custom plate
        ''    # Empty line to finish
    ]
    
    with patch('builtins.input', side_effect=user_inputs):
        try:
            main()
            print("\n✅ Subsequent run workflow completed successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Subsequent run workflow failed: {e}")
            return False

if __name__ == "__main__":
    print("Laboratory Barcode Label Generation - Workflow Testing")
    print("Using sip-lims environment with real sample data")
    
    # Test first run
    first_run_success = test_first_run_workflow()
    
    if first_run_success:
        # Test subsequent run
        subsequent_run_success = test_subsequent_run_workflow()
        
        if subsequent_run_success:
            print("\n" + "=" * 60)
            print("🎉 ALL WORKFLOW TESTS PASSED!")
            print("=" * 60)
            print("✅ First run workflow: PASSED")
            print("✅ Subsequent run workflow: PASSED")
            print("✅ File generation: PASSED")
            print("✅ Database operations: PASSED")
            print("✅ BarTender format: PASSED")
            print("=" * 60)
        else:
            print("\n❌ Subsequent run workflow failed")
            sys.exit(1)
    else:
        print("\n❌ First run workflow failed")
        sys.exit(1)