#!/usr/bin/env python3

"""
Debugging Utilities for Laboratory Barcode Label Generation Script

This module provides comprehensive debugging tools and utilities for
troubleshooting barcode generation issues in laboratory environments.
"""

import pandas as pd
import sqlite3
import json
import logging
import sys
import os
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import hashlib

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
    DATABASE_NAME,
    BARTENDER_FILE
)


class LabDebugger:
    """Comprehensive debugging utility for laboratory barcode generation."""
    
    def __init__(self, debug_dir: str = "debug_logs"):
        """Initialize the debugger with logging setup."""
        self.debug_dir = Path(debug_dir)
        self.debug_dir.mkdir(exist_ok=True)
        
        # Debug session info
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.debug_data = {
            'session_id': self.session_id,
            'timestamp': datetime.now().isoformat(),
            'issues_found': [],
            'recommendations': [],
            'system_state': {}
        }
        
        # Set up logging
        self.setup_logging()
        self.logger = logging.getLogger('LabDebugger')
    
    def setup_logging(self):
        """Set up comprehensive logging for debugging."""
        log_file = self.debug_dir / f"debug_{self.session_id}.log"
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        
        # Configure logger
        logger = logging.getLogger('LabDebugger')
        logger.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        # Prevent duplicate logs
        logger.propagate = False
    
    def log_issue(self, severity: str, component: str, description: str, 
                  details: Optional[Dict] = None):
        """Log a debugging issue with structured data."""
        issue = {
            'timestamp': datetime.now().isoformat(),
            'severity': severity,
            'component': component,
            'description': description,
            'details': details or {}
        }
        
        self.debug_data['issues_found'].append(issue)
        
        # Log to file
        log_level = getattr(logging, severity.upper(), logging.INFO)
        self.logger.log(log_level, f"[{component}] {description}")
        
        if details:
            self.logger.debug(f"Details: {json.dumps(details, indent=2)}")
    
    def add_recommendation(self, action: str, reason: str, priority: str = "medium"):
        """Add a debugging recommendation."""
        recommendation = {
            'action': action,
            'reason': reason,
            'priority': priority,
            'timestamp': datetime.now().isoformat()
        }
        
        self.debug_data['recommendations'].append(recommendation)
        self.logger.info(f"RECOMMENDATION [{priority.upper()}]: {action} - {reason}")
    
    def diagnose_csv_issues(self, csv_path: Path) -> Dict[str, Any]:
        """Diagnose CSV file issues."""
        self.logger.info(f"🔍 Diagnosing CSV file: {csv_path}")
        diagnosis = {
            'file_exists': False,
            'file_readable': False,
            'encoding_issues': False,
            'column_issues': [],
            'data_issues': [],
            'recommendations': []
        }
        
        try:
            # Check file existence
            if not csv_path.exists():
                self.log_issue("ERROR", "CSV", f"File does not exist: {csv_path}")
                diagnosis['recommendations'].append("Verify file path and ensure file exists")
                return diagnosis
            
            diagnosis['file_exists'] = True
            
            # Check file readability
            try:
                with open(csv_path, 'r') as f:
                    f.read(100)  # Try to read first 100 chars
                diagnosis['file_readable'] = True
            except Exception as e:
                self.log_issue("ERROR", "CSV", f"File not readable: {e}")
                diagnosis['recommendations'].append("Check file permissions and corruption")
                return diagnosis
            
            # Try different encodings
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
            successful_encoding = None
            
            for encoding in encodings:
                try:
                    df = pd.read_csv(csv_path, encoding=encoding)
                    successful_encoding = encoding
                    self.logger.info(f"✅ Successfully read with encoding: {encoding}")
                    break
                except Exception as e:
                    self.logger.debug(f"Failed with encoding {encoding}: {e}")
            
            if not successful_encoding:
                self.log_issue("ERROR", "CSV", "Could not read file with any encoding")
                diagnosis['encoding_issues'] = True
                diagnosis['recommendations'].append("Check file encoding and format")
                return diagnosis
            
            # Analyze columns
            required_cols = ['Proposal', 'Project', 'Sample', 'Number_of_sorted_plates']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                self.log_issue("ERROR", "CSV", f"Missing required columns: {missing_cols}")
                diagnosis['column_issues'] = missing_cols
                diagnosis['recommendations'].append(f"Add missing columns: {missing_cols}")
            
            # Analyze data quality
            if 'Number_of_sorted_plates' in df.columns:
                try:
                    pd.to_numeric(df['Number_of_sorted_plates'])
                except ValueError as e:
                    self.log_issue("ERROR", "CSV", f"Invalid numeric data: {e}")
                    diagnosis['data_issues'].append("Number_of_sorted_plates contains non-numeric values")
                    diagnosis['recommendations'].append("Ensure Number_of_sorted_plates contains only integers")
            
            # Check for empty rows
            empty_rows = df.isnull().all(axis=1).sum()
            if empty_rows > 0:
                self.log_issue("WARNING", "CSV", f"Found {empty_rows} empty rows")
                diagnosis['data_issues'].append(f"{empty_rows} empty rows found")
                diagnosis['recommendations'].append("Remove empty rows from CSV file")
            
            # Check for duplicate samples
            if 'Sample' in df.columns:
                duplicates = df['Sample'].duplicated().sum()
                if duplicates > 0:
                    self.log_issue("WARNING", "CSV", f"Found {duplicates} duplicate sample names")
                    diagnosis['data_issues'].append(f"{duplicates} duplicate sample names")
                    diagnosis['recommendations'].append("Review and resolve duplicate sample names")
            
            self.logger.info(f"✅ CSV diagnosis completed. Issues found: {len(diagnosis['data_issues']) + len(diagnosis['column_issues'])}")
            
        except Exception as e:
            self.log_issue("ERROR", "CSV", f"Unexpected error during diagnosis: {e}")
            diagnosis['recommendations'].append("Contact system administrator for assistance")
        
        return diagnosis
    
    def diagnose_database_issues(self, db_path: Path = None) -> Dict[str, Any]:
        """Diagnose database-related issues."""
        if db_path is None:
            db_path = Path(DATABASE_NAME)
        
        self.logger.info(f"🔍 Diagnosing database: {db_path}")
        diagnosis = {
            'file_exists': False,
            'file_readable': False,
            'schema_valid': False,
            'data_integrity': True,
            'barcode_conflicts': [],
            'recommendations': []
        }
        
        try:
            # Check file existence
            if not db_path.exists():
                self.log_issue("INFO", "DATABASE", f"Database file does not exist: {db_path}")
                diagnosis['recommendations'].append("Database will be created on first run")
                return diagnosis
            
            diagnosis['file_exists'] = True
            
            # Check database connectivity
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Check schema
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                
                if ('plate_barcodes',) not in tables:
                    self.log_issue("ERROR", "DATABASE", "Missing plate_barcodes table")
                    diagnosis['schema_valid'] = False
                    diagnosis['recommendations'].append("Recreate database with correct schema")
                else:
                    diagnosis['schema_valid'] = True
                    
                    # Check data integrity
                    cursor.execute("SELECT COUNT(*) FROM plate_barcodes")
                    total_records = cursor.fetchone()[0]
                    
                    self.logger.info(f"📊 Database contains {total_records} records")
                    
                    # Check for barcode conflicts
                    cursor.execute("""
                        SELECT echo_barcode, COUNT(*) as count
                        FROM plate_barcodes
                        GROUP BY echo_barcode
                        HAVING count > 1
                    """)
                    echo_conflicts = cursor.fetchall()
                    
                    cursor.execute("""
                        SELECT hamilton_barcode, COUNT(*) as count
                        FROM plate_barcodes
                        GROUP BY hamilton_barcode
                        HAVING count > 1
                    """)
                    hamilton_conflicts = cursor.fetchall()
                    
                    if echo_conflicts or hamilton_conflicts:
                        diagnosis['data_integrity'] = False
                        diagnosis['barcode_conflicts'] = {
                            'echo': echo_conflicts,
                            'hamilton': hamilton_conflicts
                        }
                        self.log_issue("CRITICAL", "DATABASE", 
                                     f"Barcode conflicts found: Echo={len(echo_conflicts)}, Hamilton={len(hamilton_conflicts)}")
                        diagnosis['recommendations'].append("CRITICAL: Resolve barcode conflicts immediately")
                    
                conn.close()
                diagnosis['file_readable'] = True
                
            except sqlite3.Error as e:
                self.log_issue("ERROR", "DATABASE", f"Database error: {e}")
                diagnosis['recommendations'].append("Database may be corrupted - consider backup and recreation")
        
        except Exception as e:
            self.log_issue("ERROR", "DATABASE", f"Unexpected error during diagnosis: {e}")
            diagnosis['recommendations'].append("Contact system administrator for database issues")
        
        return diagnosis
    
    def diagnose_bartender_file(self, bartender_path: Path = None) -> Dict[str, Any]:
        """Diagnose BarTender file issues."""
        if bartender_path is None:
            bartender_path = Path(BARTENDER_FILE)
        
        self.logger.info(f"🔍 Diagnosing BarTender file: {bartender_path}")
        diagnosis = {
            'file_exists': False,
            'file_readable': False,
            'format_valid': False,
            'header_present': False,
            'label_count': 0,
            'format_issues': [],
            'recommendations': []
        }
        
        try:
            # Check file existence
            if not bartender_path.exists():
                self.log_issue("INFO", "BARTENDER", f"BarTender file does not exist: {bartender_path}")
                diagnosis['recommendations'].append("BarTender file will be created when script runs")
                return diagnosis
            
            diagnosis['file_exists'] = True
            
            # Read and analyze file
            try:
                # Read in binary mode to properly detect line endings
                with open(bartender_path, 'rb') as f:
                    binary_content = f.read()
                
                # Convert to text for analysis
                content = binary_content.decode('utf-8')
                
                diagnosis['file_readable'] = True
                
                # Check for required header
                if '%BTW%' in content:
                    diagnosis['header_present'] = True
                else:
                    self.log_issue("ERROR", "BARTENDER", "Missing BarTender header (%BTW%)")
                    diagnosis['format_issues'].append("Missing BarTender header")
                    diagnosis['recommendations'].append("Regenerate BarTender file with correct header")
                
                # Count labels
                echo_count = content.count('Echo')
                hamilton_count = content.count('Hamilton')
                diagnosis['label_count'] = echo_count + hamilton_count
                
                self.logger.info(f"📊 BarTender file contains {echo_count} Echo and {hamilton_count} Hamilton labels")
                
                # Validate format
                if echo_count != hamilton_count:
                    self.log_issue("WARNING", "BARTENDER",
                                 f"Mismatched label counts: Echo={echo_count}, Hamilton={hamilton_count}")
                    diagnosis['format_issues'].append("Mismatched Echo/Hamilton label counts")
                    diagnosis['recommendations'].append("Regenerate BarTender file to fix label count mismatch")
                
                # Check for proper line endings using binary content
                if b'\r\n' not in binary_content:
                    self.log_issue("WARNING", "BARTENDER", "Missing Windows line endings (\\r\\n)")
                    diagnosis['format_issues'].append("Incorrect line endings")
                    diagnosis['recommendations'].append("Ensure Windows line endings for BarTender compatibility")
                
                if len(diagnosis['format_issues']) == 0:
                    diagnosis['format_valid'] = True
                    self.logger.info("✅ BarTender file format appears valid")
                
            except Exception as e:
                self.log_issue("ERROR", "BARTENDER", f"Could not read BarTender file: {e}")
                diagnosis['recommendations'].append("Check file permissions and encoding")
        
        except Exception as e:
            self.log_issue("ERROR", "BARTENDER", f"Unexpected error during diagnosis: {e}")
            diagnosis['recommendations'].append("Contact system administrator for file system issues")
        
        return diagnosis
    
    def validate_barcode_uniqueness_debug(self, db_path: Path = None) -> Dict[str, Any]:
        """Comprehensive barcode uniqueness validation with debugging."""
        if db_path is None:
            db_path = Path(DATABASE_NAME)
        
        self.logger.info("🔍 Performing comprehensive barcode uniqueness validation")
        validation = {
            'total_plates': 0,
            'unique_echo_codes': 0,
            'unique_hamilton_codes': 0,
            'echo_duplicates': [],
            'hamilton_duplicates': [],
            'cross_contamination': [],  # Echo codes that appear as Hamilton codes
            'validation_passed': False,
            'recommendations': []
        }
        
        try:
            if not db_path.exists():
                self.log_issue("INFO", "VALIDATION", "No database found - validation skipped")
                validation['validation_passed'] = True
                return validation
            
            # Read all barcodes from database
            df = read_from_database(db_path)
            validation['total_plates'] = len(df)
            
            # Analyze Echo barcodes
            echo_codes = df['echo_barcode'].tolist()
            unique_echo = set(echo_codes)
            validation['unique_echo_codes'] = len(unique_echo)
            
            # Find Echo duplicates
            echo_counts = pd.Series(echo_codes).value_counts()
            echo_duplicates = echo_counts[echo_counts > 1]
            validation['echo_duplicates'] = echo_duplicates.to_dict()
            
            # Analyze Hamilton barcodes
            hamilton_codes = df['hamilton_barcode'].tolist()
            unique_hamilton = set(hamilton_codes)
            validation['unique_hamilton_codes'] = len(unique_hamilton)
            
            # Find Hamilton duplicates
            hamilton_counts = pd.Series(hamilton_codes).value_counts()
            hamilton_duplicates = hamilton_counts[hamilton_counts > 1]
            validation['hamilton_duplicates'] = hamilton_duplicates.to_dict()
            
            # Check for cross-contamination (Echo codes appearing as Hamilton codes)
            cross_contamination = unique_echo.intersection(unique_hamilton)
            validation['cross_contamination'] = list(cross_contamination)
            
            # Determine validation status
            issues_found = (
                len(validation['echo_duplicates']) > 0 or
                len(validation['hamilton_duplicates']) > 0 or
                len(validation['cross_contamination']) > 0
            )
            
            validation['validation_passed'] = not issues_found
            
            # Log findings
            if validation['echo_duplicates']:
                self.log_issue("CRITICAL", "VALIDATION", 
                             f"Echo barcode duplicates found: {validation['echo_duplicates']}")
                validation['recommendations'].append("CRITICAL: Resolve Echo barcode duplicates immediately")
            
            if validation['hamilton_duplicates']:
                self.log_issue("CRITICAL", "VALIDATION", 
                             f"Hamilton barcode duplicates found: {validation['hamilton_duplicates']}")
                validation['recommendations'].append("CRITICAL: Resolve Hamilton barcode duplicates immediately")
            
            if validation['cross_contamination']:
                self.log_issue("CRITICAL", "VALIDATION", 
                             f"Cross-contamination found: {validation['cross_contamination']}")
                validation['recommendations'].append("CRITICAL: Resolve barcode cross-contamination immediately")
            
            if validation['validation_passed']:
                self.logger.info("✅ Barcode uniqueness validation PASSED")
            else:
                self.logger.error("❌ Barcode uniqueness validation FAILED")
        
        except Exception as e:
            self.log_issue("ERROR", "VALIDATION", f"Validation error: {e}")
            validation['recommendations'].append("Contact system administrator for validation issues")
        
        return validation
    
    def generate_debug_report(self) -> Path:
        """Generate comprehensive debug report."""
        self.logger.info("📋 Generating comprehensive debug report")
        
        # Perform all diagnostics
        csv_path = Path("test_input_data_files/sample_metadtata.csv")
        
        self.debug_data['diagnostics'] = {
            'csv': self.diagnose_csv_issues(csv_path),
            'database': self.diagnose_database_issues(),
            'bartender': self.diagnose_bartender_file(),
            'barcode_validation': self.validate_barcode_uniqueness_debug()
        }
        
        # System state
        self.debug_data['system_state'] = {
            'working_directory': str(Path.cwd()),
            'database_exists': Path(DATABASE_NAME).exists(),
            'bartender_exists': Path(BARTENDER_FILE).exists(),
            'test_data_exists': csv_path.exists(),
            'python_version': sys.version,
            'timestamp': datetime.now().isoformat()
        }
        
        # Generate report file
        report_file = self.debug_dir / f"debug_report_{self.session_id}.json"
        
        with open(report_file, 'w') as f:
            json.dump(self.debug_data, f, indent=2, default=str)
        
        # Generate human-readable summary
        summary_file = self.debug_dir / f"debug_summary_{self.session_id}.txt"
        self._generate_summary_report(summary_file)
        
        self.logger.info(f"📋 Debug report generated: {report_file}")
        self.logger.info(f"📋 Debug summary generated: {summary_file}")
        
        return report_file
    
    def _generate_summary_report(self, summary_file: Path):
        """Generate human-readable summary report."""
        with open(summary_file, 'w') as f:
            f.write("LABORATORY BARCODE GENERATION - DEBUG REPORT\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Session ID: {self.session_id}\n")
            f.write(f"Timestamp: {self.debug_data['timestamp']}\n\n")
            
            # Issues summary
            f.write("ISSUES FOUND:\n")
            f.write("-" * 20 + "\n")
            if not self.debug_data['issues_found']:
                f.write("✅ No issues found\n")
            else:
                for issue in self.debug_data['issues_found']:
                    f.write(f"❌ [{issue['severity']}] {issue['component']}: {issue['description']}\n")
            
            f.write("\n")
            
            # Recommendations
            f.write("RECOMMENDATIONS:\n")
            f.write("-" * 20 + "\n")
            if not self.debug_data['recommendations']:
                f.write("✅ No recommendations needed\n")
            else:
                for rec in self.debug_data['recommendations']:
                    f.write(f"💡 [{rec['priority'].upper()}] {rec['action']}\n")
                    f.write(f"   Reason: {rec['reason']}\n\n")
            
            # System state
            f.write("SYSTEM STATE:\n")
            f.write("-" * 20 + "\n")
            for key, value in self.debug_data['system_state'].items():
                f.write(f"{key}: {value}\n")


def quick_debug():
    """Quick debugging function for immediate troubleshooting."""
    print("🔧 Laboratory Barcode Generation - Quick Debug")
    print("=" * 50)
    
    debugger = LabDebugger()
    
    # Quick checks
    csv_path = Path("test_input_data_files/sample_metadtata.csv")
    db_path = Path(DATABASE_NAME)
    bartender_path = Path(BARTENDER_FILE)
    
    print(f"📁 CSV File: {'✅' if csv_path.exists() else '❌'} {csv_path}")
    print(f"💾 Database: {'✅' if db_path.exists() else '❌'} {db_path}")
    print(f"🏷️  BarTender: {'✅' if bartender_path.exists() else '❌'} {bartender_path}")
    
    # Generate full report
    report_file = debugger.generate_debug_report()
    print(f"\n📋 Full debug report: {report_file}")
    
    return debugger


if __name__ == "__main__":
    quick_debug()