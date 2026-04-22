# Laboratory Capsule Sorting Scripts Documentation

This directory contains comprehensive documentation for the six-script laboratory workflow that processes microwell plates from initial project setup through final pooling preparation.

## Documentation Structure

### Workflow Overview
- **[00_workflow_overview.md](00_workflow_overview.md)** - Complete workflow architecture, data flow, and integration points

### Individual Script Documentation
1. **[01_initiate_project_folder_and_make_sort_plate_labels.md](01_initiate_project_folder_and_make_sort_plate_labels.md)** - Project initialization and barcode generation
2. **[02_generate_lib_creation_files.md](02_generate_lib_creation_files.md)** - Library preparation and index assignment
3. **[03_capsule_fa_analysis.md](03_capsule_fa_analysis.md)** - Fragment Analyzer quality analysis
4. **[04_create_capsule_spits.md](04_create_capsule_spits.md)** - Plate selection and SPITS file generation
5. **[05_process_grid_tables_and_generate_barcodes.md](05_process_grid_tables_and_generate_barcodes.md)** - Grid processing, container barcode mapping, and barcode scanning material generation
6. **[06_verify_scanning_and_generate_ESP_files.md](06_verify_scanning_and_generate_ESP_files.md)** - Barcode verification and ESP file generation

### Deprecated Script Documentation (March 2026)
- **[old_05_make_ESP_smear_analysis_file.md](old_05_make_ESP_smear_analysis_file.md)** - *(Deprecated)* Former ESP file generation script
- **[old_06_relabel_lib_plates_for_pooling.md](old_06_relabel_lib_plates_for_pooling.md)** - *(Deprecated)* Former physical labeling materials script

## Workflow Update (March 2026)

**Important**: Scripts 5 and 6 have been refactored to improve safety and data integrity:

- **Script 5** (`process_grid_tables_and_generate_barcodes.py`): Now handles grid table processing, container barcode mapping, and generates barcode scanning materials
- **Script 6** (`verify_scanning_and_generate_ESP_files.py`): Now performs mandatory barcode verification before ESP file generation
- **Key Change**: Barcode scanning verification now occurs **before** ESP file generation, adding a mandatory quality gate
- **Safety Feature**: Any barcode mismatch causes Script 6 to exit immediately - no ESP files are generated with incorrect barcodes

The older scripts (`make_ESP_smear_analysis_file.py` and `relabel_lib_plates_for_pooling.py`) are **no longer used** and have been replaced.

## Quick Start Guide

### Prerequisites
- Python environment with required packages (pandas, openpyxl, sqlalchemy, matplotlib, etc.)
- Access to laboratory instruments (Fragment Analyzer, BarTender system)
- Sample metadata CSV file with required columns

### Execution Order
The scripts must be run in numerical order (1→2→3→4→5→6) as each script depends on outputs from previous scripts.

### Key Input Files
- **Script 1**: `sample_metadata.csv` (sample metadata); optionally `new_samples.csv` to add new samples on re-runs
- **Script 2**: `library_sort_plates.txt` (plates to process)
- **Script 3**: FA instrument output files in subdirectories; `thresholds.txt` (manually renamed from Script 2 output)
- **Script 4**: `plate_selection.csv` (user-created selection criteria)
- **Script 5**: Grid table CSV files from external system
- **Script 6**: Completed Excel scanning file from Script 5 output

### Manual Steps Between Scripts
- **Between Scripts 2 and 3**: Script 2 generates `3_FA_analysis/thresholds_{timestamp}.txt`. The user must fill in the `DNA_conc_threshold_(nmol/L)` values for each plate and rename the file to `thresholds.txt` before running Script 3.
- **Between Scripts 5 and 6**: User must scan physical barcodes into Excel template and verify all Checker values show TRUE

### Key Output Files
- **Database**: `project_summary.db` (central data repository)
- **Labels**: BarTender files for physical plate labeling
- **Protocols**: Transfer files for laboratory instruments
- **Submissions**: SPITS and ESP files for external systems
- **Visualizations**: Quality analysis plots and statistics

## Database Architecture

### Core Tables
- **`sample_metadata`**: Project and collection information
- **`individual_plates`**: Plate inventory with barcodes and status tracking
- **`master_plate_data`**: Comprehensive well-level data with index assignments and quality results

### Data Evolution
Each script enhances the database with additional information:
1. Basic project structure and plate barcodes
2. Index assignments and FA well mappings
3. Quality results and failure analysis
4. Selection status and pooling decisions
5. Grid table data, container barcode mapping, and barcode scanning materials
6. ESP generation status and barcode verification results

## File Organization

### Directory Structure
```
project_root/
├── 1_make_barcode_labels/          # Barcode generation outputs
├── 2_library_creation/             # Library preparation files
├── 3_FA_analysis/                  # Fragment Analyzer results
├── 4_plate_selection_and_pooling/  # Selection and pooling files
│   ├── B_new_plate_barcode_labels/ # Script 5: Barcode scanning materials
│   ├── C_smear_file_for_ESP_upload/ # Script 6: ESP files
│   └── previously_processed_grid_files/ # Archived grid tables
├── archived_files/                 # Timestamped file archives
└── docs/                          # This documentation
```

### Archiving Strategy
- All processed input files are moved to timestamped archive folders
- Database snapshots are created before each major update
- Original templates and layouts are preserved
- Processing history is maintained for audit trails

## Quality Control Features

### Error Handling
- Laboratory-grade "FATAL ERROR" messaging for safety
- Comprehensive input validation at every stage
- Fail-fast design prevents processing with bad data
- Clear guidance for error resolution

### Barcode Verification Safety (New in March 2026)
- **Mandatory scanning verification**: Script 6 validates all barcode scans before ESP generation
- **Fail-safe design**: Any `FALSE` value in Excel Checker column causes immediate `sys.exit()`
- **Zero tolerance**: ESP files are never generated with mismatched barcodes
- **Quality gate**: Barcode verification now occurs before ESP file creation, not after

### Data Integrity
- Perfect merge validation ensures no data loss
- Barcode uniqueness enforcement prevents conflicts
- Cross-table consistency checks validate relationships
- Incremental processing prevents duplicate work

### Audit Trail
- Timestamped processing records
- Batch identification for tracking
- Status flags for processing state
- Complete archive preservation

## Integration Points

### Laboratory Instruments
- **Echo/Hamilton**: Liquid handling robots (barcode prefixes)
- **Fragment Analyzer**: DNA quality assessment
- **BarTender**: Label printing system

### External Systems
- **JGI SPITS**: Sample submission system
- **ESP**: External sample processing
- **Grid Tables**: External pooling system output

### Manual Processes
- Plate selection decisions based on FA results (between Scripts 3 and 4)
- Grid table creation from external systems (input to Script 5)
- **Barcode scanning verification**: Physical barcode scanning into Excel template (between Scripts 5 and 6)
- Physical barcode verification during pooling

## Troubleshooting

### Common Issues
1. **Missing input files**: Check file locations and naming conventions
2. **Database errors**: Verify table structure and data completeness
3. **Format validation**: Ensure CSV files have required columns
4. **Capacity limits**: Verify plate counts don't exceed template limits

### Recovery Procedures
1. **Restore from archives**: Use timestamped database backups
2. **Resume processing**: Scripts can safely re-run from any point
3. **Regenerate files**: Database can recreate most output files
4. **Status reset**: Processing flags can be manually adjusted if needed

## Performance Considerations

### Scalability
- Handles projects with hundreds of plates
- Memory-efficient processing for large datasets
- Parallel file generation where possible
- Incremental updates minimize processing time

### Optimization
- Skip logic avoids reprocessing completed items
- Batch operations reduce database overhead
- Efficient merge strategies minimize memory usage
- Targeted updates preserve existing data

## Support and Maintenance

### Documentation Updates
- Individual script documentation reflects current implementation
- Workflow overview maintained for architecture changes
- Examples updated for new features or requirements
- Error handling documentation expanded as needed

### Version Control
- Scripts and documentation maintained together
- Database schema changes documented
- Breaking changes clearly identified
- Migration procedures provided for updates

For detailed information about any specific script, refer to its individual documentation file. For questions about the overall workflow architecture, see the workflow overview document.