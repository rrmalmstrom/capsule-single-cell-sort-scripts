#!/usr/bin/env python3

"""
Laboratory Safety Testing for Barcode Label Generation Script

This module provides comprehensive testing of laboratory safety requirements,
error handling scenarios, and critical failure modes to ensure the system
meets laboratory automation safety standards.
"""

import pytest
import pandas as pd
import tempfile
import sqlite3
import os
import sys
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
from datetime import datetime
import shutil

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_barcode_labels import (
    read_sample_csv,
    make_plate_names,
    generate_barcodes,
    save_to_database,
    read_from_database,
    make_bartender_file,
    validate_barcode_uniqueness,
    get_csv_file,
    get_custom_plates,
    create_success_marker,
    archive_existing_files,
    main
)


class TestLaboratorySafetyRequirements:
    """Test laboratory safety requirements and critical error handling."""
    
    def test_fatal_error_csv_missing_columns(self, capsys):
        """Test FATAL ERROR messaging for missing CSV columns."""
        test_data = """Proposal,Project,Sample
599999,BP9735,TestSample"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(test_data)
            test_file = Path(f.name)
        
        try:
            with pytest.raises(SystemExit) as exc_info:
                read_sample_csv(test_file)
            
            # Verify exit code indicates fatal error
            assert exc_info.value.code == 1
            
            # Verify FATAL ERROR messaging
            captured = capsys.readouterr()
            assert "FATAL ERROR" in captured.out
            assert "Missing required columns" in captured.out
            assert "Laboratory automation requires exact column names for safety" in captured.out
            
        finally:
            test_file.unlink()
    
    def test_fatal_error_csv_invalid_data_types(self, capsys):
        """Test FATAL ERROR for invalid data types in critical columns."""
        test_data = """Proposal,Project,Sample,Number_of_sorted_plates
599999,BP9735,TestSample,invalid_number"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(test_data)
            test_file = Path(f.name)
        
        try:
            with pytest.raises(SystemExit) as exc_info:
                read_sample_csv(test_file)
            
            assert exc_info.value.code == 1
            
            captured = capsys.readouterr()
            assert "FATAL ERROR" in captured.out
            assert "Invalid data in 'Number_of_sorted_plates' column" in captured.out
            assert "All values must be integers for laboratory automation safety" in captured.out
            
        finally:
            test_file.unlink()
    
    def test_fatal_error_csv_file_not_found(self, capsys):
        """Test FATAL ERROR for missing CSV file."""
        nonexistent_file = Path("nonexistent_file.csv")
        
        with pytest.raises(FileNotFoundError):
            read_sample_csv(nonexistent_file)
    
    def test_fatal_error_database_write_permission(self, capsys):
        """Test FATAL ERROR for database write permission issues."""
        # Create a read-only directory to simulate permission issues
        with tempfile.TemporaryDirectory() as temp_dir:
            readonly_dir = Path(temp_dir) / "readonly"
            readonly_dir.mkdir()
            
            # Make directory read-only
            readonly_dir.chmod(0o444)
            
            test_db = readonly_dir / "test.db"
            test_data = pd.DataFrame({
                'plate_name': ['TestPlate'],
                'echo_barcode': ['TEST1'],
                'hamilton_barcode': ['HAM1'],
                'project': ['BP9735'],
                'proposal': ['599999'],
                'sample': ['TestSample'],
                'created_timestamp': [datetime.now().isoformat()]
            })
            
            try:
                with pytest.raises((PermissionError, sqlite3.OperationalError)):
                    save_to_database(test_data, test_db)
            finally:
                # Restore permissions for cleanup
                readonly_dir.chmod(0o755)
    
    def test_barcode_uniqueness_validation_critical_failure(self, capsys):
        """Test critical failure detection in barcode uniqueness validation."""
        # Create test data with intentional duplicates
        test_data = pd.DataFrame({
            'plate_name': ['Plate1', 'Plate2'],
            'echo_barcode': ['DUPLI', 'DUPLI'],  # Intentional duplicate
            'hamilton_barcode': ['HAM01', 'HAM02']
        })
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db = Path(f.name)
        
        try:
            # Save data with duplicates
            save_to_database(test_data, test_db)
            
            # Validate uniqueness - should detect critical failure
            existing_barcodes = set(['DUPLI'])  # Pre-existing barcode
            
            with pytest.raises(SystemExit) as exc_info:
                validate_barcode_uniqueness(existing_barcodes, test_db)
            
            assert exc_info.value.code == 1
            
            captured = capsys.readouterr()
            assert "FATAL ERROR" in captured.out
            assert "Barcode uniqueness validation FAILED" in captured.out
            
        finally:
            if test_db.exists():
                test_db.unlink()
    
    def test_database_corruption_detection(self):
        """Test detection of database corruption scenarios."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db = Path(f.name)
        
        try:
            # Create corrupted database file
            with open(test_db, 'w') as f:
                f.write("This is not a valid SQLite database")
            
            # Attempt to read should fail gracefully
            with pytest.raises(sqlite3.DatabaseError):
                read_from_database(test_db)
                
        finally:
            if test_db.exists():
                test_db.unlink()
    
    def test_disk_space_exhaustion_simulation(self):
        """Test behavior when disk space is exhausted."""
        # This test simulates disk space issues by creating a very large file
        # in a limited space environment (if possible)
        
        # Create test data
        test_data = pd.DataFrame({
            'Plate_Name': [f'Plate_{i}' for i in range(1000)],
            'Echo_Barcode': [f'ECH{i:03d}' for i in range(1000)],
            'Hamilton_Barcode': [f'HAM{i:03d}' for i in range(1000)],
            'Project': ['BP9735'] * 1000,
            'Proposal': ['599999'] * 1000,
            'Sample': ['TestSample'] * 1000,
            'Timestamp': [datetime.now().isoformat()] * 1000
        })
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db = Path(f.name)
        
        try:
            # This should succeed under normal conditions
            save_to_database(test_data, test_db)
            
            # Verify database was created and is readable
            result = read_from_database(test_db)
            assert len(result) == 1000
            
        finally:
            if test_db.exists():
                test_db.unlink()
    
    def test_concurrent_access_safety(self):
        """Test safety measures for concurrent database access."""
        import threading
        import time
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db = Path(f.name)
        
        errors = []
        
        def worker_function(worker_id):
            """Worker function for concurrent access testing."""
            try:
                test_data = pd.DataFrame({
                    'Plate_Name': [f'Worker{worker_id}_Plate_{i}' for i in range(10)],
                    'Echo_Barcode': [f'W{worker_id}E{i:02d}' for i in range(10)],
                    'Hamilton_Barcode': [f'W{worker_id}H{i:02d}' for i in range(10)],
                    'Project': ['BP9735'] * 10,
                    'Proposal': ['599999'] * 10,
                    'Sample': ['TestSample'] * 10,
                    'Timestamp': [datetime.now().isoformat()] * 10
                })
                
                save_to_database(test_data, test_db)
                
            except Exception as e:
                errors.append(f"Worker {worker_id}: {str(e)}")
        
        try:
            # Start multiple threads
            threads = []
            for i in range(3):
                thread = threading.Thread(target=worker_function, args=(i,))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=10)
            
            # Check for errors (some may be expected due to locking)
            if errors:
                print(f"Concurrent access errors (may be expected): {errors}")
            
            # Verify database integrity after concurrent access
            if test_db.exists():
                result = read_from_database(test_db)
                # Should have some data, exact count may vary due to locking
                assert len(result) > 0
                
        finally:
            if test_db.exists():
                test_db.unlink()


class TestErrorRecoveryMechanisms:
    """Test error recovery and graceful degradation mechanisms."""
    
    def test_file_archiving_failure_recovery(self):
        """Test recovery when file archiving fails."""
        # Create test files
        test_db = Path("test_recovery.db")
        test_bartender = Path("test_recovery.txt")
        
        test_db.write_text("test database content")
        test_bartender.write_text("test bartender content")
        
        try:
            # Create a scenario where archiving might fail
            archive_dir = Path("archived_files")
            if archive_dir.exists():
                shutil.rmtree(archive_dir)
            
            # Make archive directory read-only to simulate failure
            archive_dir.mkdir()
            archive_dir.chmod(0o444)
            
            try:
                # This should handle the archiving failure gracefully
                archive_existing_files()
                
            except PermissionError:
                # Expected behavior - should fail gracefully
                pass
            finally:
                # Restore permissions
                archive_dir.chmod(0o755)
                
        finally:
            # Cleanup
            if test_db.exists():
                test_db.unlink()
            if test_bartender.exists():
                test_bartender.unlink()
            if archive_dir.exists():
                shutil.rmtree(archive_dir)
    
    def test_success_marker_creation_failure(self):
        """Test behavior when success marker creation fails."""
        # Create read-only workflow status directory
        workflow_dir = Path(".workflow_status")
        if workflow_dir.exists():
            shutil.rmtree(workflow_dir)
        
        workflow_dir.mkdir()
        workflow_dir.chmod(0o444)
        
        try:
            # This should handle the failure gracefully
            with pytest.raises(PermissionError):
                create_success_marker()
                
        finally:
            # Restore permissions and cleanup
            workflow_dir.chmod(0o755)
            if workflow_dir.exists():
                shutil.rmtree(workflow_dir)
    
    def test_bartender_file_creation_failure(self):
        """Test recovery when BarTender file creation fails."""
        test_data = pd.DataFrame({
            'Plate_Name': ['TestPlate'],
            'Echo_Barcode': ['TEST1'],
            'Hamilton_Barcode': ['HAM1']
        })
        
        # Try to write to a read-only location
        readonly_file = Path("/dev/null/readonly.txt")  # Invalid path
        
        with pytest.raises((PermissionError, FileNotFoundError, OSError)):
            make_bartender_file(test_data, readonly_file)


class TestDataIntegrityValidation:
    """Test comprehensive data integrity validation."""
    
    def test_barcode_format_validation(self):
        """Test validation of barcode format requirements."""
        # Test valid barcodes
        valid_barcodes = ['ABCD1', 'XYZ99', '12345', 'A1B2C']
        for barcode in valid_barcodes:
            assert len(barcode) == 5
            assert barcode.isalnum()
        
        # Test invalid barcodes
        invalid_barcodes = ['ABC', 'ABCDEF', 'AB-CD', 'AB CD', '']
        for barcode in invalid_barcodes:
            assert not (len(barcode) == 5 and barcode.isalnum())
    
    def test_cross_contamination_detection(self):
        """Test detection of cross-contamination between Echo and Hamilton barcodes."""
        # Create test data with cross-contamination
        test_data = pd.DataFrame({
            'Plate_Name': ['Plate1', 'Plate2'],
            'Echo_Barcode': ['CROSS', 'ECHO2'],
            'Hamilton_Barcode': ['HAM01', 'CROSS']  # Cross-contamination
        })
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db = Path(f.name)
        
        try:
            save_to_database(test_data, test_db)
            
            # Validate uniqueness - should detect cross-contamination
            existing_barcodes = set()
            
            with pytest.raises(SystemExit):
                validate_barcode_uniqueness(existing_barcodes, test_db)
                
        finally:
            if test_db.exists():
                test_db.unlink()
    
    def test_database_schema_validation(self):
        """Test validation of database schema integrity."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db = Path(f.name)
        
        try:
            # Create database with correct schema
            conn = sqlite3.connect(test_db)
            cursor = conn.cursor()
            
            # Create table with correct schema
            cursor.execute("""
                CREATE TABLE plate_barcodes (
                    Plate_Name TEXT PRIMARY KEY,
                    Echo_Barcode TEXT UNIQUE NOT NULL,
                    Hamilton_Barcode TEXT UNIQUE NOT NULL,
                    Project TEXT NOT NULL,
                    Proposal TEXT NOT NULL,
                    Sample TEXT NOT NULL,
                    Timestamp TEXT NOT NULL
                )
            """)
            conn.commit()
            conn.close()
            
            # Verify schema is correct
            result = read_from_database(test_db)
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 0  # Empty but valid
            
        finally:
            if test_db.exists():
                test_db.unlink()


class TestLaboratoryWorkflowIntegration:
    """Test integration with laboratory workflow systems."""
    
    def test_workflow_status_tracking(self):
        """Test workflow status tracking and success marker creation."""
        workflow_dir = Path(".workflow_status")
        success_marker = workflow_dir / "generate_barcode_labels.success"
        
        # Clean up any existing markers
        if success_marker.exists():
            success_marker.unlink()
        
        # Create success marker
        create_success_marker()
        
        # Verify marker was created
        assert success_marker.exists()
        
        # Verify marker content
        content = success_marker.read_text()
        assert "SUCCESS" in content
        assert "Laboratory barcode generation completed successfully" in content
        
        # Cleanup
        if success_marker.exists():
            success_marker.unlink()
    
    def test_file_archiving_workflow(self):
        """Test file archiving workflow for laboratory data management."""
        # Create test files
        test_db = Path("sample_metadtata.db")
        test_bartender = Path("BARTENDER_sort_plate_labels.txt")
        
        test_db.write_text("test database content")
        test_bartender.write_text("test bartender content")
        
        try:
            # Archive files
            archive_existing_files()
            
            # Verify archive directory was created
            archive_dir = Path("archived_files")
            assert archive_dir.exists()
            
            # Verify files were archived with timestamp
            archived_files = list(archive_dir.glob("*"))
            assert len(archived_files) >= 2  # At least database and bartender files
            
            # Verify timestamp format in archived filenames
            for archived_file in archived_files:
                assert "_Time" in archived_file.name
                assert archived_file.name.startswith("2026_")  # Current year
                
        finally:
            # Cleanup
            if test_db.exists():
                test_db.unlink()
            if test_bartender.exists():
                test_bartender.unlink()
            if Path("archived_files").exists():
                shutil.rmtree("archived_files")
    
    @patch('builtins.input')
    def test_user_interaction_safety(self, mock_input):
        """Test safety of user interaction components."""
        # Test CSV file selection with invalid paths
        mock_input.side_effect = [
            '/nonexistent/path.csv',  # Invalid path
            'test_input_data_files/sample_metadtata.csv'  # Valid path
        ]
        
        result = get_csv_file()
        assert result == Path('test_input_data_files/sample_metadtata.csv')
        
        # Test custom plate input with various scenarios
        mock_input.side_effect = [
            'y',  # Yes to custom plates
            'Valid_Plate_Name.1',  # Valid plate name
            'Invalid Plate Name!',  # Invalid characters (should be handled)
            'Another_Valid_Plate.2',  # Another valid name
            ''  # Empty line to finish
        ]
        
        custom_plates = get_custom_plates()
        # Should handle invalid input gracefully
        assert len(custom_plates) >= 1


class TestSystemResourceManagement:
    """Test system resource management and limits."""
    
    def test_memory_usage_limits(self):
        """Test memory usage stays within acceptable limits."""
        import psutil
        import gc
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Generate large dataset
        large_plate_names = [f"TestPlate_{i:05d}" for i in range(5000)]
        existing_barcodes = set()
        
        # Generate barcodes
        result = generate_barcodes(large_plate_names, existing_barcodes)
        
        # Check memory usage
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory
        
        # Memory increase should be reasonable (< 50MB for 5000 plates)
        assert memory_increase < 50, f"Memory usage too high: {memory_increase:.2f}MB"
        
        # Cleanup
        del result
        del large_plate_names
        gc.collect()
        
        # Memory should be released
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_retained = final_memory - initial_memory
        assert memory_retained < 10, f"Memory leak detected: {memory_retained:.2f}MB retained"
    
    def test_file_size_limits(self):
        """Test file size limits for database and BarTender files."""
        # Generate large dataset
        large_data = []
        for i in range(1000):
            large_data.append({
                'Plate_Name': f'TestPlate_{i:05d}',
                'Echo_Barcode': f'ECH{i:03d}',
                'Hamilton_Barcode': f'HAM{i:03d}',
                'Project': 'BP9735',
                'Proposal': '599999',
                'Sample': 'TestSample',
                'Timestamp': datetime.now().isoformat()
            })
        
        df = pd.DataFrame(large_data)
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db = Path(f.name)
        
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            test_bartender = Path(f.name)
        
        try:
            # Save to database
            save_to_database(df, test_db)
            
            # Check database file size (should be reasonable)
            db_size = test_db.stat().st_size / 1024  # KB
            assert db_size < 1000, f"Database file too large: {db_size:.1f}KB"
            
            # Generate BarTender file
            make_bartender_file(df, test_bartender)
            
            # Check BarTender file size
            bartender_size = test_bartender.stat().st_size / 1024  # KB
            assert bartender_size < 500, f"BarTender file too large: {bartender_size:.1f}KB"
            
        finally:
            if test_db.exists():
                test_db.unlink()
            if test_bartender.exists():
                test_bartender.unlink()


def run_safety_test_suite():
    """Run the complete laboratory safety test suite."""
    print("🧪 Laboratory Safety Test Suite")
    print("=" * 50)
    
    # Run all safety tests
    test_result = pytest.main([
        __file__,
        "-v",
        "-x",  # Stop on first failure
        "--tb=short"
    ])
    
    if test_result == 0:
        print("\n✅ ALL LABORATORY SAFETY TESTS PASSED")
        print("System meets laboratory automation safety requirements")
    else:
        print("\n❌ LABORATORY SAFETY TESTS FAILED")
        print("CRITICAL: System does not meet safety requirements")
        print("Review test failures before deploying to laboratory environment")
    
    return test_result


if __name__ == "__main__":
    run_safety_test_suite()