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
5. **[05_make_ESP_smear_analysis_file.md](05_make_ESP_smear_analysis_file.md)** - ESP file generation and external integration
6. **[06_relabel_lib_plates_for_pooling.md](06_relabel_lib_plates_for_pooling.md)** - Physical labeling materials creation

## Quick Start Guide

### Prerequisites
- Python environment with required packages (pandas, openpyxl, sqlalchemy, matplotlib, etc.)
- Access to laboratory instruments (Fragment Analyzer, BarTender system)
- Sample metadata CSV file with required columns

### Execution Order
The scripts must be run in numerical order (1→2→3→4→5→6) as each script depends on outputs from previous scripts.

### Key Input Files
- **Script 1**: `sample_metadtata.csv` (sample metadata)
- **Script 2**: `library_sort_plates.txt` (plates to process)
- **Script 3**: FA instrument output files in subdirectories
- **Script 4**: `plate_selection.csv` (user-created selection criteria)
- **Script 5**: Grid table CSV files from external system
- **Script 6**: Uses database data only

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
5. External system identifiers and grid table data
6. Read-only access for label generation

## File Organization

### Directory Structure
```
project_root/
├── 1_make_barcode_labels/          # Barcode generation outputs
├── 2_library_creation/             # Library preparation files
├── 3_FA_analysis/                  # Fragment Analyzer results
├── 4_plate_selection_and_pooling/  # Selection and pooling files
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
- Plate selection decisions based on FA results
- Physical barcode verification during pooling
- Grid table creation from external systems

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