#!/usr/bin/env python3

"""
Test suite for Laboratory Barcode Label Generation Script
Following Test-Driven Development (TDD) approach

This test file must be written FIRST before implementing any functions.
All tests should initially FAIL, then we implement functions to make them pass.
"""

import pytest
import pandas as pd
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import patch, mock_open
from datetime import datetime
import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import functions from the main script (will fail initially - that's expected in TDD)
try:
    from generate_barcode_labels import (
        read_sample_csv,
        make_plate_names,
        generate_barcodes,
        save_to_database,
        read_from_database,
        make_bartender_file,
        get_csv_file,
        get_custom_plates,
        detect_csv_file,
        read_custom_plates_file,
        read_additional_standard_plates_file,
        validate_barcode_uniqueness,
        create_success_marker,
        archive_existing_files
    )
except ImportError:
    # Expected in TDD - we haven't implemented the functions yet
    pass


class TestCSVProcessing:
    """Test CSV reading and validation functions."""
    
    def test_read_sample_csv_valid_file(self):
        """Test reading a valid CSV file with all required columns."""
        test_data = """Proposal,Project,Sample,Number_of_sorted_plates
599999,BP9735,TestSample,3
599999,BP9735,TestSample2,2"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(test_data)
            test_file = Path(f.name)
        
        try:
            result = read_sample_csv(test_file)
            
            assert len(result) == 2
            assert result.iloc[0]['Project'] == 'BP9735'
            assert result.iloc[0]['Sample'] == 'TestSample'
            assert result.iloc[0]['Number_of_sorted_plates'] == 3
            assert result.iloc[1]['Number_of_sorted_plates'] == 2
            
        finally:
            test_file.unlink()
    
    def test_read_sample_csv_missing_columns(self):
        """Test CSV file missing required columns raises error."""
        test_data = """Proposal,Project,Sample
599999,BP9735,TestSample"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(test_data)
            test_file = Path(f.name)
        
        try:
            with pytest.raises(SystemExit):
                read_sample_csv(test_file)
        finally:
            test_file.unlink()
    
    def test_read_sample_csv_file_not_found(self):
        """Test non-existent CSV file raises error."""
        with pytest.raises(FileNotFoundError):
            read_sample_csv(Path("nonexistent.csv"))
    
    def test_read_sample_csv_with_bom(self):
        """Test CSV file with BOM (Byte Order Mark) is handled correctly."""
        test_data = "﻿Proposal,Project,Sample,Number_of_sorted_plates\n599999,BP9735,TestSample,3"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8-sig') as f:
            f.write(test_data)
            test_file = Path(f.name)
        
        try:
            result = read_sample_csv(test_file)
            assert len(result) == 1
            assert 'Proposal' in result.columns  # Should not have BOM prefix
        finally:
            test_file.unlink()


class TestPlateNameGeneration:
    """Test plate name generation functions."""
    
    def test_make_plate_names_single_sample(self):
        """Test generating plate names for a single sample."""
        sample_df = pd.DataFrame({
            'Proposal': [599999],
            'Project': ['BP9735'],
            'Sample': ['TestSample'],
            'Number_of_sorted_plates': [3]
        })
        
        result = make_plate_names(sample_df)
        
        assert len(result) == 3
        assert result.iloc[0]['plate_name'] == 'BP9735_TestSample.1'
        assert result.iloc[1]['plate_name'] == 'BP9735_TestSample.2'
        assert result.iloc[2]['plate_name'] == 'BP9735_TestSample.3'
        assert all(result['project'] == 'BP9735')
        assert all(result['sample'] == 'TestSample')
        assert all(result['is_custom'] == False)
    
    def test_make_plate_names_multiple_samples(self):
        """Test generating plate names for multiple samples."""
        sample_df = pd.DataFrame({
            'Proposal': [599999, 599999],
            'Project': ['BP9735', 'BP9735'],
            'Sample': ['Sample1', 'Sample2'],
            'Number_of_sorted_plates': [2, 1]
        })
        
        result = make_plate_names(sample_df)
        
        assert len(result) == 3
        expected_names = ['BP9735_Sample1.1', 'BP9735_Sample1.2', 'BP9735_Sample2.1']
        assert result['plate_name'].tolist() == expected_names
    
    def test_make_plate_names_zero_plates(self):
        """Test handling of zero plates for a sample."""
        sample_df = pd.DataFrame({
            'Proposal': [599999],
            'Project': ['BP9735'],
            'Sample': ['TestSample'],
            'Number_of_sorted_plates': [0]
        })
        
        result = make_plate_names(sample_df)
        assert len(result) == 0


class TestBarcodeGeneration:
    """Test barcode generation and validation functions."""
    
    def test_generate_barcodes_uniqueness(self):
        """Test that generated barcodes are unique."""
        plates_df = pd.DataFrame({
            'plate_name': ['TEST1', 'TEST2', 'TEST3'],
            'project': ['TEST', 'TEST', 'TEST'],
            'sample': ['SAMPLE', 'SAMPLE', 'SAMPLE'],
            'plate_number': [1, 2, 3],
            'is_custom': [False, False, False]
        })
        
        result = generate_barcodes(plates_df)
        
        assert len(result) == 3
        # Check all barcodes are unique
        all_barcodes = (result['base_barcode'].tolist() + 
                       result['echo_barcode'].tolist() + 
                       result['hamilton_barcode'].tolist())
        assert len(all_barcodes) == len(set(all_barcodes))
        
        # Check barcode format
        for _, row in result.iterrows():
            assert len(row['base_barcode']) == 5
            assert row['echo_barcode'] == row['base_barcode'] + 'E'
            assert row['hamilton_barcode'] == row['base_barcode'] + 'H'
            assert 'created_timestamp' in row
    
    def test_generate_barcodes_collision_avoidance(self):
        """Test that new barcodes avoid collisions with existing ones."""
        # Create existing data
        existing_df = pd.DataFrame({
            'plate_name': ['EXISTING1'],
            'base_barcode': ['ABC12'],
            'echo_barcode': ['ABC12E'],
            'hamilton_barcode': ['ABC12H'],
            'project': ['TEST'],
            'sample': ['SAMPLE'],
            'plate_number': [1],
            'is_custom': [False],
            'created_timestamp': ['2026-01-01T00:00:00']
        })
        
        # Create new plates
        plates_df = pd.DataFrame({
            'plate_name': ['NEW1'],
            'project': ['TEST'],
            'sample': ['SAMPLE'],
            'plate_number': [2],
            'is_custom': [False]
        })
        
        result = generate_barcodes(plates_df, existing_df)
        
        # Ensure no collisions
        existing_codes = set(['ABC12', 'ABC12E', 'ABC12H'])
        new_codes = set([result.iloc[0]['base_barcode'], 
                        result.iloc[0]['echo_barcode'], 
                        result.iloc[0]['hamilton_barcode']])
        
        assert len(existing_codes.intersection(new_codes)) == 0
    
    def test_validate_barcode_uniqueness(self):
        """Test barcode uniqueness validation function."""
        df = pd.DataFrame({
            'base_barcode': ['ABC12', 'DEF34'],
            'echo_barcode': ['ABC12E', 'DEF34E'],
            'hamilton_barcode': ['ABC12H', 'DEF34H']
        })
        
        # Should pass validation
        assert validate_barcode_uniqueness(df) == True
        
        # Test with duplicates
        df_dup = pd.DataFrame({
            'base_barcode': ['ABC12', 'ABC12'],
            'echo_barcode': ['ABC12E', 'ABC12E'],
            'hamilton_barcode': ['ABC12H', 'ABC12H']
        })
        
        assert validate_barcode_uniqueness(df_dup) == False


class TestDatabaseOperations:
    """Test database save/load operations."""
    
    def test_save_to_database(self):
        """Test saving DataFrame to SQLite database."""
        test_df = pd.DataFrame({
            'plate_name': ['TEST1', 'TEST2'],
            'base_barcode': ['ABC12', 'DEF34'],
            'echo_barcode': ['ABC12E', 'DEF34E'],
            'hamilton_barcode': ['ABC12H', 'DEF34H'],
            'project': ['TEST', 'TEST'],
            'sample': ['SAMPLE', 'SAMPLE'],
            'plate_number': [1, 2],
            'is_custom': [False, False],
            'created_timestamp': ['2026-01-01T00:00:00', '2026-01-01T00:00:00']
        })
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db = Path(f.name)
        
        try:
            save_to_database(test_df, test_db)
            
            # Verify database was created and contains data
            conn = sqlite3.connect(test_db)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM plate_barcodes")
            count = cursor.fetchone()[0]
            conn.close()
            
            assert count == 2
        finally:
            test_db.unlink()
    
    def test_read_from_database(self):
        """Test reading DataFrame from SQLite database."""
        test_df = pd.DataFrame({
            'plate_name': ['TEST1'],
            'base_barcode': ['ABC12'],
            'echo_barcode': ['ABC12E'],
            'hamilton_barcode': ['ABC12H'],
            'project': ['TEST'],
            'sample': ['SAMPLE'],
            'plate_number': [1],
            'is_custom': [False],
            'created_timestamp': ['2026-01-01T00:00:00']
        })
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db = Path(f.name)
        
        try:
            save_to_database(test_df, test_db)
            result = read_from_database(test_db)
            
            assert len(result) == 1
            assert result.iloc[0]['plate_name'] == 'TEST1'
            assert result.iloc[0]['base_barcode'] == 'ABC12'
        finally:
            test_db.unlink()
    
    def test_read_from_nonexistent_database(self):
        """Test reading from non-existent database returns None."""
        result = read_from_database(Path("nonexistent.db"))
        assert result is None


class TestBarTenderFileGeneration:
    """Test BarTender file generation."""
    
    def test_make_bartender_file(self):
        """Test generating BarTender label file."""
        test_df = pd.DataFrame({
            'plate_name': ['TEST1', 'TEST2'],
            'echo_barcode': ['ABC12E', 'DEF34E'],
            'hamilton_barcode': ['ABC12H', 'DEF34H']
        })
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            test_file = Path(f.name)
        
        try:
            make_bartender_file(test_df, test_file)
            
            with open(test_file, 'r') as f:
                content = f.read()
            
            # Check header is present
            assert '%BTW%' in content
            assert 'ECHO_BCode8.btw' in content
            
            # Check Echo labels
            assert 'ABC12E,"TEST1 Echo"' in content
            assert 'DEF34E,"TEST2 Echo"' in content
            
            # Check Hamilton labels
            assert 'ABC12H,"TEST1 Hamilton"' in content
            assert 'DEF34H,"TEST2 Hamilton"' in content
            
        finally:
            test_file.unlink()
    
    def test_make_bartender_file_empty_dataframe(self):
        """Test BarTender file generation with empty DataFrame."""
        empty_df = pd.DataFrame(columns=['plate_name', 'echo_barcode', 'hamilton_barcode'])
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            test_file = Path(f.name)
        
        try:
            make_bartender_file(empty_df, test_file)
            
            with open(test_file, 'r') as f:
                content = f.read()
            
            # Should still have header
            assert '%BTW%' in content
            
        finally:
            test_file.unlink()


class TestUserInteraction:
    """Test user interaction functions."""
    
    def test_detect_csv_file_valid(self):
        """Test automatic detection of valid CSV file."""
        result = detect_csv_file()
        # Should find the sample_metadtata.csv file in current directory
        assert result.name == 'sample_metadtata.csv'
        assert result.exists()
    
    def test_read_custom_plates_file_no_file(self):
        """Test reading custom plates when no file exists."""
        result = read_custom_plates_file()
        assert result == []
    
    def test_read_custom_plates_file_with_file(self):
        """Test reading custom plates from file."""
        import tempfile
        import os
        
        # Create temporary custom plates file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('Custom_Plate_1\n')
            f.write('Custom_Plate_2\n')
            temp_file = f.name
        
        # Copy to expected location
        import shutil
        shutil.copy(temp_file, 'custom_plate_names.txt')
        
        try:
            result = read_custom_plates_file()
            assert result == ['Custom_Plate_1', 'Custom_Plate_2']
        finally:
            # Clean up
            os.unlink(temp_file)
            if os.path.exists('custom_plate_names.txt'):
                os.unlink('custom_plate_names.txt')
    
    def test_read_additional_standard_plates_file_no_file(self):
        """Test reading additional plates when no file exists."""
        result = read_additional_standard_plates_file()
        assert result == {}
    
    def test_read_additional_standard_plates_file_with_file(self):
        """Test reading additional plates from file."""
        import tempfile
        import os
        
        # Create temporary additional plates file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('BP9735_SitukAM:2\n')
            f.write('BP9735_WCBP1PR:1\n')
            temp_file = f.name
        
        # Copy to expected location
        import shutil
        shutil.copy(temp_file, 'additional_standard_plates.txt')
        
        try:
            result = read_additional_standard_plates_file()
            assert result == {'BP9735_SitukAM': 2, 'BP9735_WCBP1PR': 1}
        finally:
            # Clean up
            os.unlink(temp_file)
            if os.path.exists('additional_standard_plates.txt'):
                os.unlink('additional_standard_plates.txt')
    
    # Legacy function compatibility tests
    def test_get_csv_file_compatibility(self):
        """Test that get_csv_file() still works (calls detect_csv_file())."""
        result = get_csv_file()
        assert result.name == 'sample_metadtata.csv'
    
    def test_get_custom_plates_compatibility(self):
        """Test that get_custom_plates() still works (calls read_custom_plates_file())."""
        result = get_custom_plates()
        assert result == []  # No file exists, should return empty list


class TestFileManagement:
    """Test file management and archiving functions."""
    
    def test_create_success_marker(self):
        """Test creating success marker file."""
        # Clean up any existing marker
        status_dir = Path(".workflow_status")
        if status_dir.exists():
            import shutil
            shutil.rmtree(status_dir)
        
        create_success_marker()
        
        marker_file = status_dir / "generate_barcode_labels.success"
        assert marker_file.exists()
        
        with open(marker_file, 'r') as f:
            content = f.read()
        
        assert "SUCCESS" in content
        assert "generate_barcode_labels" in content
    
    def test_archive_existing_files(self):
        """Test archiving existing files."""
        # Create test files
        test_db = Path("test_sample_metadtata.db")
        test_bartender = Path("test_BARTENDER_sort_plate_labels.txt")
        
        test_db.write_text("test database content")
        test_bartender.write_text("test bartender content")
        
        try:
            archive_existing_files([test_db, test_bartender])
            
            # Check archive directory was created
            archive_dir = Path("archived_files")
            assert archive_dir.exists()
            
            # Check files were moved to archive
            archived_files = list(archive_dir.glob("*"))
            assert len(archived_files) >= 2
            
        finally:
            # Clean up
            if test_db.exists():
                test_db.unlink()
            if test_bartender.exists():
                test_bartender.unlink()
            if Path("archived_files").exists():
                import shutil
                shutil.rmtree("archived_files")


class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_complete_workflow_first_run(self):
        """Test complete workflow for first run scenario."""
        # This test will be implemented after all functions are created
        # It should test the entire main() function workflow
        pass
    
    def test_complete_workflow_subsequent_run(self):
        """Test complete workflow for subsequent run scenario."""
        # This test will be implemented after all functions are created
        # It should test adding plates to existing database
        pass
    
    def test_real_data_processing(self):
        """Test processing with real sample data files."""
        # Test with actual files in test_input_data_files/
        csv_file = Path("test_input_data_files/sample_metadtata.csv")
        assert csv_file.exists()
        
        # This will be expanded once functions are implemented
        pass


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])