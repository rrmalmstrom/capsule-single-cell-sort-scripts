# Capsule Workflow — SNAPSHOT_ITEMS Audit

**Status:** Verified via conversation with architect (2026-04-15)  
**Purpose:** Documents the confirmed `SNAPSHOT_ITEMS` for each Capsule workflow script, ready for Stage 1 implementation.  
**Related spec:** [`sip_lims_workflow_manager/plans/undo_system_redesign.md`](../../sip_lims_workflow_manager/plans/undo_system_redesign.md)

---

## Key Design Principles (confirmed during audit)

1. **`SNAPSHOT_ITEMS`** lists only files/folders the script **modifies, deletes, or replaces**. Files that the script creates from scratch on first run are NOT needed in `SNAPSHOT_ITEMS` — if they don't exist at snapshot time they are simply skipped. On undo, the manifest diff identifies them as newly-created and deletes them.

2. **User-placed input files** (e.g. `plate_selection.csv`, grid CSV files) are placed by the user between steps. They appear in `current_paths - prev_manifest_paths` and are automatically captured as "newly-added user files" in the snapshot ZIP. They do NOT need to be listed in `SNAPSHOT_ITEMS`.

3. **`archived_files/` timestamped copies** created by each script are newly-created files caught by manifest diff and deleted on undo. They do NOT need to be in `SNAPSHOT_ITEMS`.

4. **`archived_files/FA_results_archive/capsule_fa_analysis_results/`** is the Capsule workflow's permanently protected FA archive subfolder (after Stage 1 update). Legacy projects may have files at `archived_files/capsule_fa_analysis_results/` — both paths are covered by `PERMANENT_EXCLUSIONS` in `src/logic.py`.

---

## PERMANENT_EXCLUSIONS — RESOLVED

**Decision (2026-04-15):** `PERMANENT_EXCLUSIONS` is a single module-level constant in `src/logic.py` containing five entries — one universal forward-looking path and four legacy paths for existing in-progress projects:

```python
PERMANENT_EXCLUSIONS = {
    "archived_files/FA_results_archive",            # All workflows going forward (universal)
    "archived_files/first_lib_attempt_fa_results",  # SIP + SPS-CE legacy projects
    "archived_files/second_lib_attempt_fa_results", # SIP + SPS-CE legacy projects
    "archived_files/third_lib_attempt_fa_results",  # SIP + SPS-CE legacy projects
    "archived_files/capsule_fa_analysis_results",   # Capsule legacy projects
}
```

**Rationale:** Each workflow uses a different subfolder name for FA archives. Rather than making `PERMANENT_EXCLUSIONS` workflow-aware, a consistent intermediate folder `archived_files/FA_results_archive/` is introduced. FA analysis scripts are updated to archive into this subfolder (e.g. `archived_files/FA_results_archive/capsule_fa_analysis_results/`). The four legacy entries protect existing projects that already have files at the old paths. The `src/logic.py` constant remains workflow-agnostic.

**Stage 1 impact for Capsule:** `capsule_fa_analysis.py` line 1519 must be updated from:
```python
archive_fa_results(fa_result_dirs_to_archive, "capsule_fa_analysis_results", batch_id)
```
to:
```python
archive_fa_results(fa_result_dirs_to_archive, "FA_results_archive/capsule_fa_analysis_results", batch_id)
```
The `archive_fa_results()` function itself does not change. This update is part of the Stage 1 commit for `capsule_fa_analysis.py`.

**Note on Script 3 SNAPSHOT_ITEMS:** The `NOTE` comment in Script 3's `SNAPSHOT_ITEMS` block (below) references `archived_files/capsule_fa_analysis_results`. After the Stage 1 update, the actual archive path will be `archived_files/FA_results_archive/capsule_fa_analysis_results`. The comment should reflect the new path.

---

## Confirmed SNAPSHOT_ITEMS Per Script

### Script 1: `initiate_project_folder_and_make_sort_plate_labels.py`

```python
# === WORKFLOW SNAPSHOT ITEMS ===
# Files and folders this script modifies, deletes, or replaces.
# The workflow manager reads this list before running the script to create
# a pre-run backup. Keep this list accurate — an incomplete list means
# incomplete rollback capability.
SNAPSHOT_ITEMS = [
    "project_summary.db",
    "sample_metadata.csv",
    "individual_plates.csv",
    "1_make_barcode_labels/",
]
# === END WORKFLOW SNAPSHOT ITEMS ===
```

**Notes:**
- `archived_files/` timestamped copies handled by manifest diff
- `1_make_barcode_labels/previously_process_label_input_files/` is included via the whole folder — on re-run, input files moved into this subfolder are restored correctly because they were inside `1_make_barcode_labels/` at snapshot time

---

### Script 2: `generate_lib_creation_files.py`

```python
# === WORKFLOW SNAPSHOT ITEMS ===
SNAPSHOT_ITEMS = [
    "project_summary.db",
    "master_plate_data.csv",
    "individual_plates.csv",
    "2_library_creation/",
    "3_FA_analysis/thresholds.txt",
]
# === END WORKFLOW SNAPSHOT ITEMS ===
```

**Notes:**
- `2_library_creation/` covers: Illumina index files, FA transfer files, FA upload files, BarTender file, `previously_processed_files/` subfolder
- `3_FA_analysis/thresholds.txt` is written by this script (not Script 3)
- Input plate layout CSV files moved into `2_library_creation/previously_processed_files/` are user-placed files captured by manifest diff

---

### Script 3: `capsule_fa_analysis.py`

```python
# === WORKFLOW SNAPSHOT ITEMS ===
SNAPSHOT_ITEMS = [
    "project_summary.db",
    "master_plate_data.csv",
    "individual_plates.csv",
    "3_FA_analysis/",
]
# NOTE: archived_files/FA_results_archive/capsule_fa_analysis_results is NOT listed here.
# It is permanently protected and never touched by the undo system.
# The script itself archives FA results there on each run — that is intentional.
# === END WORKFLOW SNAPSHOT ITEMS ===
```

**Notes:**
- `3_FA_analysis/` covers: `fa_summary_statistics_{timestamp}.csv`, `FA_plate_visualizations_combined_{timestamp}.pdf`, `previously_processed_threshold_files/`
- FA result subdirectories inside `3_FA_analysis/` (e.g. `3_FA_analysis/2023 07 21/`) are user-placed instrument output — captured by manifest diff as newly-added user files
- `archived_files/FA_results_archive/capsule_fa_analysis_results/` is excluded via `PERMANENT_EXCLUSIONS` (universal path, resolved — see section above)
- Archive call in script (after Stage 1 update): `archive_fa_results(fa_result_dirs_to_archive, "FA_results_archive/capsule_fa_analysis_results", batch_id)` at line 1519

---

### Script 4: `create_capsule_spits.py`

```python
# === WORKFLOW SNAPSHOT ITEMS ===
SNAPSHOT_ITEMS = [
    "project_summary.db",
    "master_plate_data.csv",
    "individual_plates.csv",
    "4_plate_selection_and_pooling/A_spits_file/",
]
# === END WORKFLOW SNAPSHOT ITEMS ===
```

**Notes:**
- `plate_selection.csv` is a user-placed file at `4_plate_selection_and_pooling/plate_selection.csv`. It is moved by the script into `A_spits_file/` with a timestamp. It is captured by manifest diff as a newly-added user file — does NOT need to be in `SNAPSHOT_ITEMS`.

---

### Script 5: `process_grid_tables_and_generate_barcodes.py`

```python
# === WORKFLOW SNAPSHOT ITEMS ===
SNAPSHOT_ITEMS = [
    "project_summary.db",
    "master_plate_data.csv",
    "individual_plates.csv",
    "4_plate_selection_and_pooling/",
]
# === END WORKFLOW SNAPSHOT ITEMS ===
```

**Notes:**
- Whole `4_plate_selection_and_pooling/` folder included (not just `B_new_plate_barcode_labels/`) for safety — covers `A_spits_file/`, `B_new_plate_barcode_labels/`, and `previously_processed_grid_files/`
- Grid CSV files (user-placed in `4_plate_selection_and_pooling/`) are captured by manifest diff as newly-added user files

---

### Script 6: `verify_scanning_and_generate_ESP_files.py`

```python
# === WORKFLOW SNAPSHOT ITEMS ===
SNAPSHOT_ITEMS = [
    "project_summary.db",
    "master_plate_data.csv",
    "individual_plates.csv",
    "4_plate_selection_and_pooling/C_smear_file_for_ESP_upload/",
]
# === END WORKFLOW SNAPSHOT ITEMS ===
```

**Notes:**
- Script writes to DB (`update_individual_plates_with_esp_status`, `add_pcr_cycles_column_to_master_plate_data`) — DB must be in `SNAPSHOT_ITEMS`
- The completed Excel file in `B_new_plate_barcode_labels/` is only read, not modified
- `archived_files/` CSV copies handled by manifest diff

---

## Implementation Instructions for Stage 1

Add the `SNAPSHOT_ITEMS` block to each script near the top of the file, **after imports and module-level constants, before any function definitions**. Use the exact comment block format shown above.

The implementation agent should:
1. Read each script to confirm the `SNAPSHOT_ITEMS` placement location
2. Add the block using the exact content from this document
3. For `capsule_fa_analysis.py` only: also update line 1519 — change the `archive_fa_results()` call argument from `"capsule_fa_analysis_results"` to `"FA_results_archive/capsule_fa_analysis_results"`. No other logic changes.
4. Commit all 6 scripts together as a single Stage 1 commit with message: `Stage 1: Add SNAPSHOT_ITEMS to all 6 Capsule scripts; update FA archive path to FA_results_archive subfolder`
5. Do NOT modify any other logic in the scripts
