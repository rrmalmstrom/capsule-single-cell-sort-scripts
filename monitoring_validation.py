#!/usr/bin/env python3

"""
Monitoring and Validation Scripts for Laboratory Barcode Label Generation

This module provides comprehensive monitoring and validation tools for
ensuring the barcode generation system operates correctly in laboratory environments.
"""

import pandas as pd
import sqlite3
import json
import time
import hashlib
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import subprocess

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_barcode_labels import (
    DATABASE_NAME,
    BARTENDER_FILE,
    BARTENDER_HEADER,
    read_from_database
)


class LabMonitor:
    """Comprehensive monitoring system for laboratory barcode generation."""
    
    def __init__(self, monitoring_dir: str = "monitoring_logs"):
        """Initialize the monitoring system."""
        self.monitoring_dir = Path(monitoring_dir)
        self.monitoring_dir.mkdir(exist_ok=True)
        
        self.status_file = self.monitoring_dir / "system_status.json"
        self.metrics_file = self.monitoring_dir / "performance_metrics.json"
        self.alerts_file = self.monitoring_dir / "alerts.json"
        
        # Initialize status tracking
        self.current_status = {
            'last_check': datetime.now().isoformat(),
            'system_healthy': True,
            'database_status': 'unknown',
            'bartender_status': 'unknown',
            'barcode_integrity': 'unknown',
            'alerts': []
        }
    
    def check_system_health(self) -> Dict[str, Any]:
        """Perform comprehensive system health check."""
        print("🏥 Performing system health check...")
        
        health_report = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'healthy',
            'components': {},
            'alerts': [],
            'recommendations': []
        }
        
        # Check database health
        db_health = self._check_database_health()
        health_report['components']['database'] = db_health
        
        # Check BarTender file health
        bartender_health = self._check_bartender_health()
        health_report['components']['bartender'] = bartender_health
        
        # Check file system health
        filesystem_health = self._check_filesystem_health()
        health_report['components']['filesystem'] = filesystem_health
        
        # Check barcode integrity
        integrity_health = self._check_barcode_integrity()
        health_report['components']['barcode_integrity'] = integrity_health
        
        # Determine overall status
        component_statuses = [comp['status'] for comp in health_report['components'].values()]
        if 'critical' in component_statuses:
            health_report['overall_status'] = 'critical'
        elif 'warning' in component_statuses:
            health_report['overall_status'] = 'warning'
        
        # Collect all alerts
        for component in health_report['components'].values():
            health_report['alerts'].extend(component.get('alerts', []))
        
        # Save health report
        self._save_health_report(health_report)
        
        print(f"🏥 System health: {health_report['overall_status'].upper()}")
        if health_report['alerts']:
            print(f"⚠️  {len(health_report['alerts'])} alerts found")
        
        return health_report
    
    def _check_database_health(self) -> Dict[str, Any]:
        """Check database health and integrity."""
        db_path = Path(DATABASE_NAME)
        health = {
            'status': 'healthy',
            'alerts': [],
            'metrics': {}
        }
        
        try:
            if not db_path.exists():
                health['status'] = 'warning'
                health['alerts'].append("Database file does not exist")
                health['metrics']['record_count'] = 0
                return health
            
            # Check database connectivity and integrity
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check table existence
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='plate_barcodes';")
            if not cursor.fetchone():
                health['status'] = 'critical'
                health['alerts'].append("plate_barcodes table missing")
                conn.close()
                return health
            
            # Get record count
            cursor.execute("SELECT COUNT(*) FROM plate_barcodes")
            record_count = cursor.fetchone()[0]
            health['metrics']['record_count'] = record_count
            
            # Check for duplicate barcodes
            cursor.execute("""
                SELECT COUNT(*) FROM (
                    SELECT echo_barcode FROM plate_barcodes GROUP BY echo_barcode HAVING COUNT(*) > 1
                    UNION ALL
                    SELECT hamilton_barcode FROM plate_barcodes GROUP BY hamilton_barcode HAVING COUNT(*) > 1
                )
            """)
            duplicate_count = cursor.fetchone()[0]
            
            if duplicate_count > 0:
                health['status'] = 'critical'
                health['alerts'].append(f"Found {duplicate_count} duplicate barcodes")
            
            # Check database file size
            file_size = db_path.stat().st_size
            health['metrics']['file_size_mb'] = file_size / (1024 * 1024)
            
            # Check for recent activity
            cursor.execute("SELECT MAX(created_timestamp) FROM plate_barcodes")
            last_update = cursor.fetchone()[0]
            if last_update:
                last_update_dt = datetime.fromisoformat(last_update)
                days_since_update = (datetime.now() - last_update_dt).days
                health['metrics']['days_since_last_update'] = days_since_update
                
                if days_since_update > 30:
                    health['status'] = 'warning'
                    health['alerts'].append(f"No database updates in {days_since_update} days")
            
            conn.close()
            
        except Exception as e:
            health['status'] = 'critical'
            health['alerts'].append(f"Database error: {str(e)}")
        
        return health
    
    def _check_bartender_health(self) -> Dict[str, Any]:
        """Check BarTender file health and format."""
        bartender_path = Path(BARTENDER_FILE)
        health = {
            'status': 'healthy',
            'alerts': [],
            'metrics': {}
        }
        
        try:
            if not bartender_path.exists():
                health['status'] = 'warning'
                health['alerts'].append("BarTender file does not exist")
                return health
            
            # Read and analyze file
            with open(bartender_path, 'rb') as f:
                binary_content = f.read()
            
            # Convert to text for analysis
            content = binary_content.decode('utf-8')
            
            # Check file size
            file_size = len(content)
            health['metrics']['file_size_bytes'] = file_size
            
            if file_size == 0:
                health['status'] = 'critical'
                health['alerts'].append("BarTender file is empty")
                return health
            
            # Check for required header
            if BARTENDER_HEADER.strip() not in content:
                health['status'] = 'critical'
                health['alerts'].append("BarTender header missing or incorrect")
            
            # Count labels
            echo_count = content.count('Echo')
            hamilton_count = content.count('Hamilton')
            health['metrics']['echo_labels'] = echo_count
            health['metrics']['hamilton_labels'] = hamilton_count
            health['metrics']['total_labels'] = echo_count + hamilton_count
            
            # Check label balance
            if echo_count != hamilton_count:
                health['status'] = 'warning'
                health['alerts'].append(f"Label count mismatch: Echo={echo_count}, Hamilton={hamilton_count}")
            
            # Check line endings (should be Windows format for BarTender)
            if b'\r\n' not in binary_content:
                health['status'] = 'warning'
                health['alerts'].append("Missing Windows line endings (may cause BarTender issues)")
            
            # Check file modification time
            mod_time = datetime.fromtimestamp(bartender_path.stat().st_mtime)
            hours_since_mod = (datetime.now() - mod_time).total_seconds() / 3600
            health['metrics']['hours_since_modification'] = hours_since_mod
            
        except Exception as e:
            health['status'] = 'critical'
            health['alerts'].append(f"BarTender file error: {str(e)}")
        
        return health
    
    def _check_filesystem_health(self) -> Dict[str, Any]:
        """Check file system health and permissions."""
        health = {
            'status': 'healthy',
            'alerts': [],
            'metrics': {}
        }
        
        try:
            # Check working directory permissions
            cwd = Path.cwd()
            
            # Test write permissions
            test_file = cwd / ".permission_test"
            try:
                test_file.write_text("test")
                test_file.unlink()
                health['metrics']['write_permission'] = True
            except Exception:
                health['status'] = 'critical'
                health['alerts'].append("No write permission in working directory")
                health['metrics']['write_permission'] = False
            
            # Check disk space
            import shutil
            total, used, free = shutil.disk_usage(cwd)
            free_gb = free / (1024**3)
            health['metrics']['free_space_gb'] = free_gb
            
            if free_gb < 1.0:  # Less than 1GB free
                health['status'] = 'critical'
                health['alerts'].append(f"Low disk space: {free_gb:.1f}GB remaining")
            elif free_gb < 5.0:  # Less than 5GB free
                health['status'] = 'warning'
                health['alerts'].append(f"Disk space warning: {free_gb:.1f}GB remaining")
            
            # Check for required directories
            required_dirs = ['test_input_data_files', '.workflow_status']
            for dir_name in required_dirs:
                dir_path = cwd / dir_name
                if not dir_path.exists():
                    health['status'] = 'warning'
                    health['alerts'].append(f"Missing directory: {dir_name}")
            
        except Exception as e:
            health['status'] = 'critical'
            health['alerts'].append(f"Filesystem error: {str(e)}")
        
        return health
    
    def _check_barcode_integrity(self) -> Dict[str, Any]:
        """Check barcode integrity and uniqueness."""
        health = {
            'status': 'healthy',
            'alerts': [],
            'metrics': {}
        }
        
        try:
            db_path = Path(DATABASE_NAME)
            if not db_path.exists():
                health['status'] = 'warning'
                health['alerts'].append("No database to check barcode integrity")
                return health
            
            # Read all barcodes
            df = read_from_database(db_path)
            total_plates = len(df)
            health['metrics']['total_plates'] = total_plates
            
            if total_plates == 0:
                health['status'] = 'warning'
                health['alerts'].append("No plates in database")
                return health
            
            # Check Echo barcode uniqueness
            echo_codes = df['echo_barcode'].tolist()
            unique_echo = len(set(echo_codes))
            health['metrics']['unique_echo_codes'] = unique_echo
            
            if unique_echo != total_plates:
                health['status'] = 'critical'
                health['alerts'].append(f"Echo barcode duplicates: {total_plates - unique_echo} conflicts")
            
            # Check Hamilton barcode uniqueness
            hamilton_codes = df['hamilton_barcode'].tolist()
            unique_hamilton = len(set(hamilton_codes))
            health['metrics']['unique_hamilton_codes'] = unique_hamilton
            
            if unique_hamilton != total_plates:
                health['status'] = 'critical'
                health['alerts'].append(f"Hamilton barcode duplicates: {total_plates - unique_hamilton} conflicts")
            
            # Check for cross-contamination
            echo_set = set(echo_codes)
            hamilton_set = set(hamilton_codes)
            cross_contamination = echo_set.intersection(hamilton_set)
            
            if cross_contamination:
                health['status'] = 'critical'
                health['alerts'].append(f"Cross-contamination: {len(cross_contamination)} codes appear in both Echo and Hamilton")
            
            # Check barcode format
            invalid_echo = [code for code in echo_codes if len(code) != 5 or not code.isalnum()]
            invalid_hamilton = [code for code in hamilton_codes if len(code) != 5 or not code.isalnum()]
            
            if invalid_echo or invalid_hamilton:
                health['status'] = 'critical'
                health['alerts'].append(f"Invalid barcode format: Echo={len(invalid_echo)}, Hamilton={len(invalid_hamilton)}")
            
        except Exception as e:
            health['status'] = 'critical'
            health['alerts'].append(f"Barcode integrity check error: {str(e)}")
        
        return health
    
    def _save_health_report(self, health_report: Dict[str, Any]):
        """Save health report to monitoring files."""
        # Update current status
        self.current_status.update({
            'last_check': health_report['timestamp'],
            'system_healthy': health_report['overall_status'] == 'healthy',
            'database_status': health_report['components']['database']['status'],
            'bartender_status': health_report['components']['bartender']['status'],
            'barcode_integrity': health_report['components']['barcode_integrity']['status'],
            'alerts': health_report['alerts']
        })
        
        # Save status file
        with open(self.status_file, 'w') as f:
            json.dump(self.current_status, f, indent=2)
        
        # Append to metrics history
        metrics_entry = {
            'timestamp': health_report['timestamp'],
            'overall_status': health_report['overall_status'],
            'component_metrics': {
                comp: data.get('metrics', {})
                for comp, data in health_report['components'].items()
            }
        }
        
        # Load existing metrics or create new
        if self.metrics_file.exists():
            with open(self.metrics_file, 'r') as f:
                metrics_history = json.load(f)
        else:
            metrics_history = []
        
        metrics_history.append(metrics_entry)
        
        # Keep only last 100 entries
        if len(metrics_history) > 100:
            metrics_history = metrics_history[-100:]
        
        with open(self.metrics_file, 'w') as f:
            json.dump(metrics_history, f, indent=2)
        
        # Save alerts if any critical issues
        if health_report['overall_status'] in ['critical', 'warning']:
            alert_entry = {
                'timestamp': health_report['timestamp'],
                'severity': health_report['overall_status'],
                'alerts': health_report['alerts']
            }
            
            # Load existing alerts or create new
            if self.alerts_file.exists():
                with open(self.alerts_file, 'r') as f:
                    alerts_history = json.load(f)
            else:
                alerts_history = []
            
            alerts_history.append(alert_entry)
            
            # Keep only last 50 alerts
            if len(alerts_history) > 50:
                alerts_history = alerts_history[-50:]
            
            with open(self.alerts_file, 'w') as f:
                json.dump(alerts_history, f, indent=2)
    
    def validate_bartender_format(self, bartender_path: Path = None) -> Dict[str, Any]:
        """Comprehensive BarTender file format validation."""
        if bartender_path is None:
            bartender_path = Path(BARTENDER_FILE)
        
        print(f"🔍 Validating BarTender format: {bartender_path}")
        
        validation = {
            'file_valid': False,
            'format_issues': [],
            'recommendations': [],
            'metrics': {}
        }
        
        try:
            if not bartender_path.exists():
                validation['format_issues'].append("File does not exist")
                validation['recommendations'].append("Generate BarTender file")
                return validation
            
            with open(bartender_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            validation['metrics']['total_lines'] = len(lines)
            validation['metrics']['file_size'] = len(content)
            
            # Check header
            if not content.startswith('%BTW%'):
                validation['format_issues'].append("Missing or incorrect BarTender header")
                validation['recommendations'].append("Regenerate file with correct header")
            
            # Check for required elements
            required_elements = ['%BTW%', '/AF=', '/D=', '/PRN=', '/R=', '/P', '/DD', '%END%']
            missing_elements = [elem for elem in required_elements if elem not in content]
            
            if missing_elements:
                validation['format_issues'].append(f"Missing required elements: {missing_elements}")
                validation['recommendations'].append("Regenerate file with complete header")
            
            # Count labels
            echo_count = content.count('Echo')
            hamilton_count = content.count('Hamilton')
            validation['metrics']['echo_labels'] = echo_count
            validation['metrics']['hamilton_labels'] = hamilton_count
            
            if echo_count == 0 and hamilton_count == 0:
                validation['format_issues'].append("No labels found in file")
                validation['recommendations'].append("Ensure plates are processed before generating file")
            elif echo_count != hamilton_count:
                validation['format_issues'].append(f"Label count mismatch: Echo={echo_count}, Hamilton={hamilton_count}")
                validation['recommendations'].append("Regenerate file to fix label count mismatch")
            
            # Check line endings
            if '\r\n' not in content:
                validation['format_issues'].append("Missing Windows line endings")
                validation['recommendations'].append("Convert to Windows line endings for BarTender compatibility")
            
            # Check for empty lines at end
            if not content.endswith('\r\n\r\n'):
                validation['format_issues'].append("Missing trailing empty lines")
                validation['recommendations'].append("Add proper trailing empty lines")
            
            # Validate barcode format in content
            import re
            barcode_pattern = r'[A-Z0-9]{5}'
            found_barcodes = re.findall(barcode_pattern, content)
            validation['metrics']['barcodes_found'] = len(found_barcodes)
            
            if len(found_barcodes) != (echo_count + hamilton_count):
                validation['format_issues'].append("Barcode count doesn't match label count")
                validation['recommendations'].append("Verify barcode format and regenerate if needed")
            
            # Overall validation
            validation['file_valid'] = len(validation['format_issues']) == 0
            
            if validation['file_valid']:
                print("✅ BarTender format validation PASSED")
            else:
                print(f"❌ BarTender format validation FAILED: {len(validation['format_issues'])} issues")
        
        except Exception as e:
            validation['format_issues'].append(f"Validation error: {str(e)}")
            validation['recommendations'].append("Check file permissions and format")
        
        return validation
    
    def run_continuous_monitoring(self, interval_minutes: int = 60):
        """Run continuous monitoring with specified interval."""
        print(f"🔄 Starting continuous monitoring (interval: {interval_minutes} minutes)")
        
        try:
            while True:
                print(f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Running health check...")
                
                health_report = self.check_system_health()
                
                if health_report['overall_status'] == 'critical':
                    print("🚨 CRITICAL ISSUES DETECTED!")
                    for alert in health_report['alerts']:
                        print(f"   ❌ {alert}")
                elif health_report['overall_status'] == 'warning':
                    print("⚠️  Warning issues detected")
                    for alert in health_report['alerts']:
                        print(f"   ⚠️  {alert}")
                else:
                    print("✅ System healthy")
                
                print(f"💤 Sleeping for {interval_minutes} minutes...")
                time.sleep(interval_minutes * 60)
                
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user")
        except Exception as e:
            print(f"\n❌ Monitoring error: {e}")


def run_validation_suite():
    """Run complete validation suite."""
    print("🧪 Laboratory Barcode Generation - Validation Suite")
    print("=" * 60)
    
    monitor = LabMonitor()
    
    # System health check
    health_report = monitor.check_system_health()
    
    # BarTender format validation
    bartender_validation = monitor.validate_bartender_format()
    
    # Summary
    print("\n📊 VALIDATION SUMMARY")
    print("-" * 30)
    print(f"System Health: {health_report['overall_status'].upper()}")
    print(f"BarTender Format: {'VALID' if bartender_validation['file_valid'] else 'INVALID'}")
    
    if health_report['alerts'] or not bartender_validation['file_valid']:
        print("\n⚠️  ISSUES REQUIRING ATTENTION:")
        for alert in health_report['alerts']:
            print(f"   • {alert}")
        for issue in bartender_validation['format_issues']:
            print(f"   • BarTender: {issue}")
    else:
        print("\n✅ All validations passed - system ready for laboratory use")
    
    return health_report, bartender_validation


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "monitor":
        # Continuous monitoring mode
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 60
        monitor = LabMonitor()
        monitor.run_continuous_monitoring(interval)
    else:
        # One-time validation
        run_validation_suite()