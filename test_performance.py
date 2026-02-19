#!/usr/bin/env python3

"""
Performance Benchmarking Tests for Laboratory Barcode Label Generation Script

This module provides comprehensive performance testing and benchmarking
for the barcode generation system to ensure it meets laboratory requirements.
"""

import pytest
import time
import pandas as pd
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import patch
import sys
import os
import psutil
import gc
from datetime import datetime

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_barcode_labels import (
    read_sample_csv,
    make_plate_names,
    generate_barcodes,
    save_to_database,
    read_from_database,
    make_bartender_file,
    validate_barcode_uniqueness
)


class TestPerformanceBenchmarks:
    """Performance benchmarking tests for laboratory requirements."""
    
    def setup_method(self):
        """Set up performance monitoring."""
        self.process = psutil.Process()
        self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.start_time = time.time()
        gc.collect()  # Clean up before testing
    
    def teardown_method(self):
        """Clean up after performance tests."""
        gc.collect()
    
    def measure_performance(self, operation_name):
        """Measure and return performance metrics."""
        end_time = time.time()
        end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        
        execution_time = end_time - self.start_time
        memory_used = end_memory - self.start_memory
        
        print(f"\n📊 Performance Metrics for {operation_name}:")
        print(f"   ⏱️  Execution Time: {execution_time:.3f} seconds")
        print(f"   💾 Memory Usage: {memory_used:.2f} MB")
        
        return {
            'execution_time': execution_time,
            'memory_usage': memory_used,
            'operation': operation_name
        }
    
    def test_csv_processing_performance(self):
        """Test CSV processing performance with large datasets."""
        # Create large test dataset
        large_data = []
        for i in range(1000):  # 1000 samples
            large_data.append({
                'Proposal': f'59999{i % 10}',
                'Project': f'BP973{i % 10}',
                'Sample': f'TestSample_{i}',
                'Number_of_sorted_plates': (i % 5) + 1
            })
        
        df = pd.DataFrame(large_data)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            df.to_csv(f.name, index=False)
            test_file = Path(f.name)
        
        try:
            self.start_time = time.time()
            result = read_sample_csv(test_file)
            metrics = self.measure_performance("CSV Processing (1000 samples)")
            
            # Performance assertions
            assert metrics['execution_time'] < 5.0, "CSV processing too slow"
            assert metrics['memory_usage'] < 100, "CSV processing uses too much memory"
            assert len(result) == 1000, "Data integrity check failed"
            
        finally:
            test_file.unlink()
    
    def test_barcode_generation_performance(self):
        """Test barcode generation performance with large plate counts."""
        plate_names = [f"TestPlate_{i}" for i in range(1000)]
        existing_barcodes = set()
        
        self.start_time = time.time()
        result = generate_barcodes(plate_names, existing_barcodes)
        metrics = self.measure_performance("Barcode Generation (1000 plates)")
        
        # Performance assertions
        assert metrics['execution_time'] < 10.0, "Barcode generation too slow"
        assert metrics['memory_usage'] < 50, "Barcode generation uses too much memory"
        assert len(result) == 1000, "Generated barcode count mismatch"
        
        # Validate uniqueness
        all_barcodes = set()
        for plate_data in result:
            all_barcodes.add(plate_data['Echo_Barcode'])
            all_barcodes.add(plate_data['Hamilton_Barcode'])
        
        assert len(all_barcodes) == 2000, "Barcode uniqueness validation failed"
    
    def test_database_operations_performance(self):
        """Test database operations performance with large datasets."""
        # Generate test data
        test_data = []
        for i in range(500):
            test_data.append({
                'Plate_Name': f'TestPlate_{i}',
                'Echo_Barcode': f'TEST{i:03d}',
                'Hamilton_Barcode': f'HAM{i:03d}',
                'Project': f'BP973{i % 10}',
                'Proposal': f'59999{i % 10}',
                'Sample': f'Sample_{i}',
                'Timestamp': datetime.now().isoformat()
            })
        
        df = pd.DataFrame(test_data)
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db = Path(f.name)
        
        try:
            # Test save performance
            self.start_time = time.time()
            save_to_database(df, test_db)
            save_metrics = self.measure_performance("Database Save (500 plates)")
            
            # Test read performance
            self.start_time = time.time()
            result = read_from_database(test_db)
            read_metrics = self.measure_performance("Database Read (500 plates)")
            
            # Performance assertions
            assert save_metrics['execution_time'] < 5.0, "Database save too slow"
            assert read_metrics['execution_time'] < 2.0, "Database read too slow"
            assert len(result) == 500, "Database integrity check failed"
            
        finally:
            if test_db.exists():
                test_db.unlink()
    
    def test_bartender_file_generation_performance(self):
        """Test BarTender file generation performance."""
        # Generate large dataset
        test_data = []
        for i in range(1000):
            test_data.append({
                'Plate_Name': f'TestPlate_{i}',
                'Echo_Barcode': f'TEST{i:03d}',
                'Hamilton_Barcode': f'HAM{i:03d}'
            })
        
        df = pd.DataFrame(test_data)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            test_file = Path(f.name)
        
        try:
            self.start_time = time.time()
            make_bartender_file(df, test_file)
            metrics = self.measure_performance("BarTender File Generation (1000 plates)")
            
            # Performance assertions
            assert metrics['execution_time'] < 3.0, "BarTender file generation too slow"
            assert test_file.exists(), "BarTender file not created"
            
            # Validate file size (should be reasonable)
            file_size = test_file.stat().st_size / 1024  # KB
            assert file_size > 0, "BarTender file is empty"
            assert file_size < 1000, "BarTender file too large"  # Should be < 1MB
            
        finally:
            if test_file.exists():
                test_file.unlink()
    
    def test_memory_leak_detection(self):
        """Test for memory leaks during repeated operations."""
        initial_memory = self.process.memory_info().rss / 1024 / 1024
        
        # Perform repeated operations
        for i in range(100):
            plate_names = [f"TestPlate_{i}_{j}" for j in range(10)]
            existing_barcodes = set()
            
            # Generate barcodes
            result = generate_barcodes(plate_names, existing_barcodes)
            
            # Force garbage collection
            del result
            del plate_names
            gc.collect()
        
        final_memory = self.process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        
        print(f"\n🔍 Memory Leak Detection:")
        print(f"   Initial Memory: {initial_memory:.2f} MB")
        print(f"   Final Memory: {final_memory:.2f} MB")
        print(f"   Memory Increase: {memory_increase:.2f} MB")
        
        # Memory increase should be minimal (< 10MB for 1000 operations)
        assert memory_increase < 10, f"Potential memory leak detected: {memory_increase:.2f} MB increase"


class TestStressTests:
    """Stress testing for laboratory edge cases."""
    
    def test_maximum_plate_capacity(self):
        """Test system behavior at maximum expected plate capacity."""
        # Laboratory maximum: 10,000 plates
        max_plates = 10000
        plate_names = [f"StressTest_Plate_{i:05d}" for i in range(max_plates)]
        existing_barcodes = set()
        
        start_time = time.time()
        result = generate_barcodes(plate_names, existing_barcodes)
        execution_time = time.time() - start_time
        
        print(f"\n🔥 Stress Test - Maximum Capacity:")
        print(f"   Plates Generated: {len(result)}")
        print(f"   Execution Time: {execution_time:.2f} seconds")
        print(f"   Plates/Second: {len(result)/execution_time:.1f}")
        
        # Should complete within reasonable time (< 2 minutes)
        assert execution_time < 120, "Maximum capacity test too slow"
        assert len(result) == max_plates, "Not all plates generated"
        
        # Validate all barcodes are unique
        all_barcodes = set()
        for plate_data in result:
            all_barcodes.add(plate_data['Echo_Barcode'])
            all_barcodes.add(plate_data['Hamilton_Barcode'])
        
        assert len(all_barcodes) == max_plates * 2, "Barcode uniqueness failed at scale"
    
    def test_collision_avoidance_stress(self):
        """Test barcode collision avoidance under stress."""
        # Pre-populate with many existing barcodes to force collisions
        existing_barcodes = set()
        
        # Generate 50,000 existing barcodes to create high collision probability
        import random
        charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        for _ in range(50000):
            barcode = ''.join(random.choices(charset, k=5))
            existing_barcodes.add(barcode)
        
        print(f"\n⚡ Collision Avoidance Stress Test:")
        print(f"   Existing Barcodes: {len(existing_barcodes)}")
        
        # Try to generate 1000 new unique barcodes
        plate_names = [f"CollisionTest_{i}" for i in range(1000)]
        
        start_time = time.time()
        result = generate_barcodes(plate_names, existing_barcodes)
        execution_time = time.time() - start_time
        
        print(f"   New Plates: {len(result)}")
        print(f"   Execution Time: {execution_time:.2f} seconds")
        
        # Should still complete in reasonable time
        assert execution_time < 60, "Collision avoidance too slow under stress"
        assert len(result) == 1000, "Failed to generate required plates"
        
        # Validate no collisions occurred
        new_barcodes = set()
        for plate_data in result:
            echo_code = plate_data['Echo_Barcode']
            hamilton_code = plate_data['Hamilton_Barcode']
            
            assert echo_code not in existing_barcodes, f"Echo collision: {echo_code}"
            assert hamilton_code not in existing_barcodes, f"Hamilton collision: {hamilton_code}"
            assert echo_code not in new_barcodes, f"Echo duplicate: {echo_code}"
            assert hamilton_code not in new_barcodes, f"Hamilton duplicate: {hamilton_code}"
            
            new_barcodes.add(echo_code)
            new_barcodes.add(hamilton_code)


class TestConcurrencySimulation:
    """Simulate concurrent laboratory operations."""
    
    def test_concurrent_database_access_simulation(self):
        """Simulate multiple laboratory stations accessing database."""
        import threading
        import queue
        
        results_queue = queue.Queue()
        errors_queue = queue.Queue()
        
        def worker_thread(worker_id, test_db_path):
            """Simulate a laboratory workstation."""
            try:
                # Each worker generates some plates
                plate_names = [f"Worker{worker_id}_Plate_{i}" for i in range(10)]
                existing_barcodes = set()
                
                # Generate barcodes
                barcode_data = generate_barcodes(plate_names, existing_barcodes)
                df = pd.DataFrame(barcode_data)
                
                # Try to save to database (this would normally require locking)
                save_to_database(df, test_db_path)
                
                results_queue.put(f"Worker {worker_id} completed successfully")
                
            except Exception as e:
                errors_queue.put(f"Worker {worker_id} failed: {e}")
        
        # Create test database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db = Path(f.name)
        
        try:
            # Start multiple worker threads
            threads = []
            num_workers = 5
            
            for worker_id in range(num_workers):
                thread = threading.Thread(target=worker_thread, args=(worker_id, test_db))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=30)  # 30 second timeout
            
            # Check results
            successful_workers = 0
            while not results_queue.empty():
                result = results_queue.get()
                print(f"✅ {result}")
                successful_workers += 1
            
            failed_workers = 0
            while not errors_queue.empty():
                error = errors_queue.get()
                print(f"❌ {error}")
                failed_workers += 1
            
            print(f"\n🔄 Concurrency Simulation Results:")
            print(f"   Successful Workers: {successful_workers}/{num_workers}")
            print(f"   Failed Workers: {failed_workers}/{num_workers}")
            
            # At least some workers should succeed (database locking may cause some failures)
            assert successful_workers > 0, "No workers completed successfully"
            
        finally:
            if test_db.exists():
                test_db.unlink()


if __name__ == "__main__":
    print("🧪 Laboratory Barcode Generation - Performance Testing")
    print("=" * 60)
    
    # Run performance benchmarks
    pytest.main([__file__, "-v", "-s"])