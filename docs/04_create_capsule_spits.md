# Script 4: create_capsule_spits.py

## Overview
This is the **fourth script** in the laboratory workflow that processes plate selection input to generate SPITS (Sample Processing and Information Tracking System) files for selected plates and wells. It implements intelligent well selection based on plate layout types and FA quality results, creating standardized submission files for downstream processing.

## Primary Functions

### Plate Selection Processing
- **CSV-driven selection**: Reads plate and index set specifications from input file
- **Layout-aware processing**: Handles both upper left registration and full plate layouts differently
- **Quality-based filtering**: Applies FA results to determine eligible wells
- **Index set filtering**: Supports selective processing of specific index sets

### SPITS File Generation
- **Standardized format**: Creates JGI-compatible submission files with required fields
- **Dynamic field population**: Merges database information with fixed laboratory parameters
- **Template-based naming**: Generates sample names using configurable templates
- **Metadata integration**: Incorporates sample collection and location data

### Database Status Tracking
- **Selection marking**: Updates database to track which plates/wells were selected
- **Status columns**: Adds `selected_for_pooling` flags to both plate and well levels
- **Audit trail**: Maintains record of selection decisions for traceability

## Input Requirements

### Plate Selection File
- **Location**: `4_plate_selection_and_pooling/plate_selection.csv`
- **Format**: Two-column CSV with headers
- **Columns**:
  - `Plate_ID`: Plate identifier (e.g., `9735_SitukAM.1`)
  - `Index_sets`: Comma-separated index sets or empty for all (e.g., `PE17,PE19`)

### Database Dependencies
- **Complete three-table structure** from Script 3:
  - `sample_metadata`: Proposal and collection information (no `Project` column)
  - `individual_plates`: Plate inventory with layout detection results
  - `master_plate_data`: Well-level data with FA results and quality assessments

### Required Database Columns
```sql
-- individual_plates table
plate_name, upper_left_registration

-- master_plate_data table  
Plate_ID, Well, Type, Index_Set, Passed_library

-- sample_metadata table
Proposal, Sample  (join keys for metadata lookup; Project column removed)
```

## Output Files

### SPITS Submission File
- **Location**: `4_plate_selection_and_pooling/A_spits_file/`
- **Filename**: `{proposal}_capsule_sort_SPITS.csv`
- **Format**: 30-column CSV with JGI-required headers
- **Content**: Selected wells with complete metadata and laboratory parameters

### SPITS File Columns
```csv
Sample Name*,Concentration* (ng/ul),Volume* (ul),Tube or Plate Label*,
Sample Container*,Plate location (well #)*,Sample Format*,
Was Sample DNAse treated?*,Known / Suspected Organisms,
Biosafety Material Category*,Sample Isolation Method*,
Collection Year*,Collection Month*,Collection Day*,
Sample Isolated From*,Collection Site or Growth Conditions*,
Latitude*,Longitude*,Depth* (in meters),Maximum depth (in meters),
Elevation* (in meters),Maximum elevation (in meters),Country*,
Sample Contact Name,Seq Project PI Name,Proposal ID,Control Type,
Control Organism Name,Control Organism Tax ID,Internal Collaborator Sample Name
```

### Archived Input Files
- **Processed selection file**: Moved to `A_spits_file/` with timestamp
- **Database backups**: Timestamped copies in `archived_files/`

## Key Features

### Well Selection Logic

#### Upper Left Registration Plates
```python
def select_wells_from_upper_left_plate(plate_wells):
    # Select sample/neg_cntrl wells that passed FA analysis
    selected = plate_wells[
        (Type in ['sample', 'neg_cntrl']) & 
        (Passed_library == 1)
    ]
    # Quality-based selection ensures only good wells are pooled
```

#### Full Plates
```python
def select_wells_from_full_plate(plate_wells, index_sets_str):
    # Select sample/neg_cntrl wells from specified index sets
    # Ignores FA results - includes all wells from selected index sets
    target_sets = parse_index_sets(index_sets_str) or all_available_sets
    selected = plate_wells[
        (Type in ['sample', 'neg_cntrl']) & 
        (Index_Set in target_sets)
    ]
```

### Sample Name Generation
- **Template**: `"Uncultured microbe JGI {groups}_{plate_id}_{well}"`
- **Group filtering**: Only includes non-empty Group_1, Group_2, Group_3 values
- **Fallback**: Uses plate_id and well if no groups available
- **Example**: `"Uncultured microbe JGI SitukAM_Sediment_9735_SitukAM.1_A1"`

### Fixed Laboratory Parameters
```python
SPITS_FIXED_VALUES = {
    'Concentration* (ng/ul)': 10,
    'Volume* (ul)': 25,
    'Sample Container*': 384,
    'Sample Format*': 'MDA reaction buffer',
    'Was Sample DNAse treated?*': 'N',
    'Biosafety Material Category*': 'Metagenome (Environmental)',
    'Sample Isolation Method*': 'flow sorting',
    'QC Result': 'Pass',
    'Failure Mode': '',  # Always empty
}
```

## Technical Implementation

### Database Schema Updates
```sql
-- Add selection tracking columns
ALTER TABLE individual_plates ADD COLUMN selected_for_pooling BOOLEAN DEFAULT 0;
ALTER TABLE master_plate_data ADD COLUMN selected_for_pooling INTEGER DEFAULT 0;
```

### Validation Pipeline
1. **File validation**: Ensures plate_selection.csv exists and has correct format
2. **Database validation**: Verifies all plates exist and have required columns
3. **Plate validation**: Confirms plates have completed FA analysis
4. **Index validation**: Ensures specified index sets exist on plates

### Error Handling
- **Missing plates**: Clear error messages with available plate lists
- **Invalid index sets**: Validation against PE17/PE18/PE19/PE20
- **No FA results**: Prevents processing plates without quality data
- **Empty selections**: Ensures each plate contributes at least some wells

## Integration Points
- **Input from Script 3**: Reads FA results and quality decisions from [`capsule_fa_analysis.py`](03_capsule_fa_analysis.md)
- **Output to Script 5**: Selection status feeds into [`make_ESP_smear_analysis_file.py`](05_make_ESP_smear_analysis_file.md)
- **Manual input**: Requires user-created `plate_selection.csv` based on FA analysis results

## Usage Examples

### Basic Usage
```bash
python create_capsule_spits.py
```

### Plate Selection File Format
```csv
Plate_ID,Index_sets
9735_SitukAM.1,PE17,PE19
9735_SitukAM.2,
4444_RexRM.1,PE18
Custom_Plate.1,
```

### Selection Scenarios
- **Empty Index_sets**: Selects from all available index sets on the plate
- **Specific index sets**: Only processes wells from specified sets
- **Upper left plates**: Quality-filtered selection regardless of index specification
- **Full plates**: Index-based selection regardless of quality

### Output Summary
```
✅ Upper left plate '9735_SitukAM.1': Selected 23 wells that passed FA analysis
✅ Full plate '4444_RexRM.1': Selected 48 wells from index sets ['PE18']
✅ Total wells selected for SPITS processing: 71
📄 Generated: 9735_capsule_sort_SPITS.csv
🔬 Processed 71 wells from 2 plates
```

## Quality Control Features
- **Plate type detection**: Automatically identifies layout patterns
- **FA result integration**: Incorporates quality assessments into selection logic
- **Index set validation**: Ensures specified sets exist on target plates
- **Selection verification**: Confirms each plate contributes wells before proceeding

## File Management
- **Organized output**: Creates dedicated subfolder for SPITS files
- **Input archiving**: Moves processed selection file with timestamp
- **Database preservation**: Archives existing database before updates
- **CSV regeneration**: Creates fresh CSV files from updated database

## Metadata Integration

### Per-Sample Metadata Join
Each well's metadata is looked up individually by parsing its `Plate_ID` to extract the `Proposal` and `Sample` components, then joining against the `sample_metadata` table on those two fields.

```
Plate_ID '9735_SitukAM.1'  →  Proposal='9735', Sample='SitukAM'
                             →  joined to sample_metadata row where Proposal='9735' AND Sample='SitukAM'
```

Both join keys are cast to `str` before merging to prevent type mismatches when pandas infers a numeric dtype for the `Proposal` column read from SQLite (since Proposal values are typically numeric).

This ensures that when multiple samples from different proposals are processed together, each well receives the correct collection date, location, and environmental context for its own sample — not metadata from another sample.

- **Geographic information**: Includes latitude, longitude, depth, elevation
- **Temporal data**: Collection year, month, day
- **Environmental context**: Sample source and isolation details

### Custom Plates and Metadata
Custom plates are now designated via the `is_custom` column in `sample_metadata.csv` (Script 1). Because all samples — including custom ones — must be present in the metadata CSV before Script 1 runs, every plate in the database is guaranteed to have a corresponding `Proposal`/`Sample` row in `sample_metadata`. The previous scenario where custom plates could be added without metadata (via `custom_plate_names.txt`) no longer applies.

### Required `sample_metadata` Columns for Join
The following columns must exist in `sample_metadata` for the join to work:
```
Proposal, Sample
```
These are validated at startup by `validate_database_schema()`. If either is missing, the script exits with a FATAL ERROR before processing begins.

> **Note**: The `Project` column has been removed from `sample_metadata`. `Proposal` now serves as the sole project identifier and is used as the join key when merging metadata onto selected wells.

This script serves as the critical decision point in the workflow, translating FA quality results into actionable well selections for downstream processing and submission to external systems.