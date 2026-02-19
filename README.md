# Laboratory Barcode Label Generation Script

A comprehensive Python script for generating barcode labels for laboratory samples, designed for integration with BARTENDER label printing software and laboratory workflows.

## Project Overview

This script automates the generation of barcode labels for laboratory samples, providing:
- Unique barcode generation for sample tracking
- Integration with BARTENDER template system
- Robust data validation and error handling
- Performance optimization for large datasets
- Comprehensive testing and safety validation

## Laboratory Use Case

Designed for laboratory environments where:
- Sample tracking and identification is critical
- Large batches of samples need barcode labels
- Integration with existing BARTENDER printing systems is required
- Data integrity and safety validation are paramount

## Prerequisites

### System Requirements
- **Operating System**: macOS, Linux, or Windows
- **Python**: Version 3.8 or higher
- **BARTENDER Software**: Compatible version installed (for label printing)

### Required Python Packages
The script uses standard Python libraries and requires:
- `pandas` - Data manipulation and analysis
- `pytest` - Testing framework
- `pytest-cov` - Coverage reporting
- `pytest-benchmark` - Performance testing

## Environment Setup

### 1. Conda Environment Setup (Recommended)

Create and activate the `sip-lims` conda environment:

```bash
# Create the conda environment
conda create -n sip-lims python=3.8 pandas pytest pytest-cov pytest-benchmark

# Activate the environment
conda activate sip-lims
```

### 2. Alternative: pip Installation

If not using conda:

```bash
# Install required packages
pip install pandas pytest pytest-cov pytest-benchmark
```

## Installation and Setup

### 1. Clone or Download Project
```bash
# If using git
git clone <repository-url>
cd capsule_sort_scripts

# Or download and extract the project files
```

### 2. Verify Installation
```bash
# Activate conda environment
conda activate sip-lims

# Run tests to verify setup
pytest test_barcode_labels.py -v
```

## Usage Instructions

### Basic Usage

#### 1. Prepare Input Data
Create a CSV file with sample metadata containing at least:
- Sample identifiers
- Sort plate information
- Any additional metadata fields

Example CSV format:
```csv
sample_id,sort_plate,additional_field
SAMPLE001,PLATE_A,metadata1
SAMPLE002,PLATE_A,metadata2
SAMPLE003,PLATE_B,metadata3
```

#### 2. Run the Script
```python
from generate_barcode_labels import BarcodeGenerator

# Initialize the generator
generator = BarcodeGenerator()

# Generate labels from CSV file
result = generator.generate_labels_from_csv('path/to/your/sample_data.csv')

# Check results
if result['success']:
    print(f"Generated {result['labels_generated']} labels")
    print(f"Output file: {result['output_file']}")
else:
    print(f"Error: {result['error']}")
```

#### 3. Use Generated Labels
The script generates a BARTENDER-compatible text file that can be imported into BARTENDER for label printing.

### Advanced Usage

#### Custom Configuration
```python
# Initialize with custom settings
generator = BarcodeGenerator(
    barcode_prefix="LAB",
    output_filename="custom_labels.txt",
    validate_uniqueness=True
)
```

#### Batch Processing
```python
# Process multiple files
files = ['batch1.csv', 'batch2.csv', 'batch3.csv']
for file in files:
    result = generator.generate_labels_from_csv(file)
    print(f"Processed {file}: {result['labels_generated']} labels")
```

## File Structure and Components

### Core Implementation
- **[`generate_barcode_labels.py`](generate_barcode_labels.py)** - Main script with BarcodeGenerator class
- **[`regenerate_bartender.py`](regenerate_bartender.py)** - Utility for BARTENDER template management

### Testing Suite
- **[`test_barcode_labels.py`](test_barcode_labels.py)** - Core unit tests
- **[`test_workflow.py`](test_workflow.py)** - Workflow integration tests
- **[`test_performance.py`](test_performance.py)** - Performance benchmarks
- **[`test_laboratory_safety.py`](test_laboratory_safety.py)** - Safety validation tests

### Development Tools
- **[`debug_utilities.py`](debug_utilities.py)** - Debugging and logging utilities
- **[`monitoring_validation.py`](monitoring_validation.py)** - System monitoring tools

### Documentation
- **[`PROJECT_STATUS.md`](PROJECT_STATUS.md)** - Current project status and development summary
- **[`MANUAL_VALIDATION_REPORT.md`](MANUAL_VALIDATION_REPORT.md)** - Validation procedures and results
- **[`TESTING_DOCUMENTATION.md`](TESTING_DOCUMENTATION.md)** - Testing strategy and results
- **[`plans/IMPLEMENTATION_GUIDE.md`](plans/IMPLEMENTATION_GUIDE.md)** - Technical implementation details

### Test Data
- **[`test_input_data_files/`](test_input_data_files/)** - Sample data files for testing

## Running Tests

### Complete Test Suite
```bash
# Run all tests with coverage
pytest --cov=generate_barcode_labels --cov-report=html

# Run specific test categories
pytest test_barcode_labels.py -v          # Unit tests
pytest test_workflow.py -v                # Workflow tests
pytest test_performance.py -v             # Performance tests
pytest test_laboratory_safety.py -v       # Safety tests
```

### Performance Benchmarks
```bash
# Run performance benchmarks
pytest test_performance.py --benchmark-only
```

### Coverage Reports
After running tests with coverage, view detailed reports:
```bash
# Open HTML coverage report
open htmlcov/index.html  # macOS
# or
xdg-open htmlcov/index.html  # Linux
```

## Debugging and Monitoring

### Debug Mode
```python
from debug_utilities import DebugUtilities

# Enable debug logging
debug = DebugUtilities()
debug.enable_debug_mode()

# Run with debugging
generator = BarcodeGenerator(debug_mode=True)
result = generator.generate_labels_from_csv('data.csv')

# Generate debug report
debug.generate_debug_report()
```

### System Monitoring
```python
from monitoring_validation import SystemMonitor

# Monitor system performance
monitor = SystemMonitor()
monitor.start_monitoring()

# Your barcode generation code here

monitor.stop_monitoring()
monitor.generate_report()
```

## Troubleshooting

### Common Issues

#### 1. Import Errors
```bash
# Ensure conda environment is activated
conda activate sip-lims

# Verify required packages are installed
conda list pandas pytest
```

#### 2. File Not Found Errors
- Verify input file paths are correct
- Ensure files are in the expected format (CSV with headers)
- Check file permissions

#### 3. BARTENDER Integration Issues
- Verify BARTENDER software is installed
- Check template compatibility
- Ensure output file format matches BARTENDER requirements

#### 4. Performance Issues
- For large datasets (>10,000 samples), ensure adequate system memory
- Consider processing in smaller batches
- Monitor system resources during processing

### Debug Logs
Debug information is automatically saved to:
- **[`debug_logs/`](debug_logs/)** - Detailed debug logs and reports
- **[`monitoring_logs/`](monitoring_logs/)** - System monitoring data

## Safety and Validation

### Laboratory Safety Features
- **Sample Tracking Integrity**: Ensures no sample data is lost or corrupted
- **Barcode Uniqueness**: Validates all generated barcodes are unique
- **Data Consistency**: Verifies data integrity throughout processing
- **Error Recovery**: Robust error handling with detailed reporting

### Validation Procedures
See [`MANUAL_VALIDATION_REPORT.md`](MANUAL_VALIDATION_REPORT.md) for comprehensive validation procedures and results.

## Development and Testing Approach

This project was developed using **Test-Driven Development (TDD)** methodology:
- Tests written before implementation
- 100% code coverage achieved
- Comprehensive validation of all features
- Multiple test categories for different aspects

## Future Enhancements

### Planned Features
- Network-based label printing support
- Integration with Laboratory Information Management Systems (LIMS)
- Advanced reporting and analytics
- Mobile device compatibility

### Contributing
For development contributions:
1. Ensure all tests pass: `pytest`
2. Maintain 100% code coverage
3. Follow existing code style and documentation standards
4. Add appropriate tests for new features

## Support and Maintenance

### Getting Help
1. Check [`TESTING_DOCUMENTATION.md`](TESTING_DOCUMENTATION.md) for test-related issues
2. Review [`PROJECT_STATUS.md`](PROJECT_STATUS.md) for current implementation status
3. Examine debug logs in [`debug_logs/`](debug_logs/) for detailed error information

### Reporting Issues
When reporting issues, include:
- Error messages and stack traces
- Input data format and sample size
- System environment details
- Debug log files if available

## License and Usage

This script is designed for laboratory use and should be validated in your specific laboratory environment before production deployment.

---

**Project Status**: Ready for Laboratory Validation  
**Last Updated**: February 19, 2026  
**Development Approach**: Test-Driven Development (TDD)  
**Test Coverage**: 100%