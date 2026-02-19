# Laboratory Barcode Label Generation - Implementation Guide

## Overview

This guide provides everything needed to implement a simple, functional Python script for generating BarTender-compatible barcode labels for microwell plates. The approach follows the existing SPS script patterns using pure pandas operations.

## Critical Requirements

### Environment Setup (MANDATORY)
```bash
# MUST use sip-lims conda environment for ALL work
conda activate sip-lims

# Install dependencies
pip install pandas>=1.3.0 sqlalchemy>=1.4.0 pytest>=6.0.0
```

### Development Approach (MANDATORY)
- **Test-Driven Development (TDD)**: Write tests first, then implement
- **MCP Context7**: Query for latest pandas/SQLAlchemy documentation before implementing
- **Pure Functional**: No classes, just simple functions with pandas DataFrames

## Implementation Specification

### Script Structure
```python
#!/usr/bin/env python3

import pandas as pd
import random
import sys
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine

# Constants
CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
BARTENDER_HEADER = '%BTW% /AF="\\\\BARTENDER\\shared\\templates\\ECHO_BCode8.btw" /D="%Trigger File Name%" /PRN="bcode8" /R=3 /P /DD\r\n\r\n%END%\r\n\r\n\r\n'

def main():
    # Implementation here
    pass

if __name__ == "__main__":
    main()
```

### Core Functions to Implement

#### 1. CSV Processing
```python
def read_sample_csv(csv_path):
    """Read sample metadata CSV and return DataFrame."""
    df = pd.read_csv(csv_path)
    
    # Validate required columns
    required_cols = ['Proposal', 'Project', 'Sample', 'Number_of_sorted_plates']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        print(f"ERROR: Missing columns: {missing}")
        sys.exit(1)
    
    return df
```

#### 2. Plate Name Generation
```python
def make_plate_names(sample_df):
    """Generate standard plate names from sample data."""
    plates = []
    
    for _, row in sample_df.iterrows():
        project = row['Project']
        sample = row['Sample']
        num_plates = int(row['Number_of_sorted_plates'])
        
        for i in range(1, num_plates + 1):
            plates.append({
                'plate_name': f"{project}_{sample}.{i}",
                'project': project,
                'sample': sample,
                'plate_number': i,
                'is_custom': False
            })
    
    return pd.DataFrame(plates)
```

#### 3. Barcode Generation
```python
def generate_barcodes(plates_df, existing_df=None):
    """Generate unique barcodes for all plates."""
    # Get existing barcodes to avoid collisions
    existing_codes = set()
    if existing_df is not None:
        existing_codes.update(existing_df['base_barcode'].tolist())
        existing_codes.update(existing_df['echo_barcode'].tolist())
        existing_codes.update(existing_df['hamilton_barcode'].tolist())
    
    # Generate new barcodes
    for idx in plates_df.index:
        attempts = 0
        while attempts < 1000:
            base_code = ''.join(random.choices(CHARSET, k=5))
            echo_code = f"{base_code}E"
            hamilton_code = f"{base_code}H"
            
            # Check for collisions
            if (base_code not in existing_codes and 
                echo_code not in existing_codes and 
                hamilton_code not in existing_codes):
                
                plates_df.at[idx, 'base_barcode'] = base_code
                plates_df.at[idx, 'echo_barcode'] = echo_code
                plates_df.at[idx, 'hamilton_barcode'] = hamilton_code
                plates_df.at[idx, 'created_timestamp'] = datetime.now().isoformat()
                
                # Add to existing set
                existing_codes.update([base_code, echo_code, hamilton_code])
                break
            
            attempts += 1
        
        if attempts >= 1000:
            print(f"ERROR: Could not generate unique barcode for {plates_df.at[idx, 'plate_name']}")
            sys.exit(1)
    
    return plates_df
```

#### 4. Database Operations
```python
def save_to_database(df, db_path):
    """Save DataFrame to SQLite database."""
    engine = create_engine(f'sqlite:///{db_path}')
    df.to_sql('plate_barcodes', engine, if_exists='replace', index=False)
    engine.dispose()
    print(f"Saved {len(df)} plates to database")

def read_from_database(db_path):
    """Read DataFrame from SQLite database."""
    if not Path(db_path).exists():
        return None
    
    try:
        engine = create_engine(f'sqlite:///{db_path}')
        df = pd.read_sql('SELECT * FROM plate_barcodes', engine)
        engine.dispose()
        return df
    except:
        return None
```

#### 5. BarTender File Generation
```python
def make_bartender_file(df, output_path):
    """Generate BarTender label file."""
    with open(output_path, 'w') as f:
        f.write(BARTENDER_HEADER)
        
        # Echo labels
        for _, row in df.iterrows():
            f.write(f'{row["echo_barcode"]},"{row["plate_name"]} Echo"\r\n')
        f.write(',\r\n')
        
        # Hamilton labels
        for _, row in df.iterrows():
            f.write(f'{row["hamilton_barcode"]},"{row["plate_name"]} Hamilton"\r\n')
    
    print(f"Created BarTender file: {output_path}")
```

#### 6. User Interaction
```python
def get_csv_file():
    """Prompt user for CSV file."""
    while True:
        path = input("Enter CSV file path: ").strip()
        if Path(path).exists():
            return path
        print("File not found. Try again.")

def get_custom_plates():
    """Get custom plate names from user."""
    custom = input("Add custom plates? (y/n): ").lower()
    if custom != 'y':
        return []
    
    plates = []
    print("Enter custom plate names (empty line to finish):")
    while True:
        name = input("Plate name: ").strip()
        if not name:
            break
        plates.append(name)
    
    return plates
```

### Main Workflow
```python
def main():
    """Main script execution."""
    print("Laboratory Barcode Label Generation")
    print("=" * 40)
    
    db_path = "sample_metadtata.db"
    
    # Check if database exists
    existing_df = read_from_database(db_path)
    
    if existing_df is None:
        # First run - process CSV
        print("First run detected")
        csv_file = get_csv_file()
        sample_df = read_sample_csv(csv_file)
        plates_df = make_plate_names(sample_df)
        
        # Add custom plates
        custom_plates = get_custom_plates()
        if custom_plates:
            custom_df = pd.DataFrame([
                {'plate_name': name, 'project': 'CUSTOM', 'sample': 'CUSTOM', 
                 'plate_number': 1, 'is_custom': True}
                for name in custom_plates
            ])
            plates_df = pd.concat([plates_df, custom_df], ignore_index=True)
        
    else:
        # Subsequent run - add plates
        print(f"Found existing database with {len(existing_df)} plates")
        
        # Get additional plates (simplified for brevity)
        custom_plates = get_custom_plates()
        if not custom_plates:
            print("No new plates to add. Exiting.")
            return
        
        plates_df = pd.DataFrame([
            {'plate_name': name, 'project': 'CUSTOM', 'sample': 'CUSTOM', 
             'plate_number': 1, 'is_custom': True}
            for name in custom_plates
        ])
    
    # Generate barcodes
    print(f"Generating barcodes for {len(plates_df)} plates...")
    plates_df = generate_barcodes(plates_df, existing_df)
    
    # Combine with existing data
    if existing_df is not None:
        final_df = pd.concat([existing_df, plates_df], ignore_index=True)
    else:
        final_df = plates_df
    
    # Archive existing files
    timestamp = datetime.now().strftime("%Y_%m_%d-Time%H-%M-%S")
    archive_dir = Path("archived_files")
    archive_dir.mkdir(exist_ok=True)
    
    # Save to database
    save_to_database(final_df, db_path)
    
    # Generate BarTender file
    bartender_file = "BARTENDER_sort_plate_labels.txt"
    make_bartender_file(final_df, bartender_file)
    
    # Summary
    print(f"\nSUCCESS!")
    print(f"Total plates: {len(final_df)}")
    print(f"Files created: {db_path}, {bartender_file}")
    
    # Create success marker
    Path(".workflow_status").mkdir(exist_ok=True)
    with open(".workflow_status/barcode_generator.success", "w") as f:
        f.write(f"SUCCESS: completed at {datetime.now()}\n")
```

## Database Schema

Simple SQLite table that mirrors the pandas DataFrame:

```sql
CREATE TABLE plate_barcodes (
    plate_name TEXT PRIMARY KEY,
    base_barcode TEXT UNIQUE NOT NULL,
    echo_barcode TEXT UNIQUE NOT NULL,
    hamilton_barcode TEXT UNIQUE NOT NULL,
    project TEXT NOT NULL,
    sample TEXT NOT NULL,
    plate_number INTEGER NOT NULL,
    is_custom BOOLEAN DEFAULT FALSE,
    created_timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);
```

## TDD Testing Approach

### Test Structure (Write These First)
```python
# test_barcode_generator.py

import pytest
import pandas as pd
from pathlib import Path
import tempfile

def test_read_sample_csv_valid_file():
    """Test reading valid CSV file."""
    test_data = """Proposal,Project,Sample,Number_of_sorted_plates
599999,BP9735,TestSample,3"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(test_data)
        test_file = Path(f.name)
    
    from barcode_generator import read_sample_csv
    result = read_sample_csv(test_file)
    
    assert len(result) == 1
    assert result.iloc[0]['Project'] == 'BP9735'
    
    test_file.unlink()

def test_generate_barcodes_uniqueness():
    """Test barcode generation produces unique codes."""
    plates_df = pd.DataFrame({
        'plate_name': ['TEST1', 'TEST2'],
        'project': ['TEST', 'TEST'],
        'sample': ['SAMPLE', 'SAMPLE'],
        'plate_number': [1, 2],
        'is_custom': [False, False]
    })
    
    from barcode_generator import generate_barcodes
    result = generate_barcodes(plates_df)
    
    assert len(result) == 2
    assert result['base_barcode'].iloc[0] != result['base_barcode'].iloc[1]
    assert len(result['base_barcode'].iloc[0]) == 5

def test_database_operations():
    """Test database save/load operations."""
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
    
    from barcode_generator import save_to_database, read_from_database
    save_to_database(test_df, test_db)
    result = read_from_database(test_db)
    
    assert len(result) == 1
    assert result.iloc[0]['plate_name'] == 'TEST1'
    
    test_db.unlink()
```

### Running Tests
```bash
# MUST be in sip-lims environment
conda activate sip-lims

# Run tests
pytest test_barcode_generator.py -v

# Run with coverage
pytest --cov=barcode_generator test_barcode_generator.py
```

## MCP Context7 Integration

Before implementing each function, query Context7 for latest documentation:

```
# For pandas operations
Query: "pandas read_csv latest parameters and error handling"
Query: "pandas DataFrame to_sql SQLAlchemy integration current best practices"

# For SQLAlchemy operations  
Query: "SQLAlchemy create_engine dispose pattern latest version"
Query: "SQLAlchemy pandas integration current documentation"
```

## Development Workflow

1. **Setup Environment**:
   ```bash
   conda activate sip-lims
   pip install pandas sqlalchemy pytest
   ```

2. **Write Tests First** (TDD):
   ```bash
   # Create test file
   touch test_barcode_generator.py
   # Write failing tests
   # Run tests (should fail)
   pytest test_barcode_generator.py -v
   ```

3. **Implement Functions**:
   ```bash
   # Query Context7 for latest docs
   # Implement minimal function to pass test
   # Run tests again
   pytest test_barcode_generator.py -v
   ```

4. **Integration Testing**:
   ```bash
   # Test complete workflow
   python barcode_generator.py
   ```

## File Structure

```
barcode_label_generator.py    # Main script (implement this)
test_barcode_generator.py     # Test file (write first)
sample_metadata.csv          # Input data (user provided)
sample_metadtata.db          # Generated database
BARTENDER_sort_plate_labels.txt  # Generated labels
archived_files/              # Archived files
.workflow_status/            # Success markers
```

## Dependencies

Only two required packages:
- `pandas>=1.3.0` - DataFrame operations
- `sqlalchemy>=1.4.0` - Database connectivity

## Critical Reminders

1. **ALWAYS** use `sip-lims` conda environment
2. **ALWAYS** write tests before implementing (TDD)
3. **ALWAYS** query MCP Context7 for latest documentation
4. Keep it simple - pure functional approach with pandas DataFrames
5. Follow the existing SPS script patterns

This guide provides everything needed to implement the barcode generation script following laboratory-grade standards.