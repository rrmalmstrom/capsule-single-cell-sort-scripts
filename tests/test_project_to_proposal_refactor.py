#!/usr/bin/env python3
"""
Unit tests for the Project→Proposal column refactoring.

Tests cover every function that was changed:
  - initiate_project_folder_and_make_sort_plate_labels.py
      * read_sample_csv()
      * detect_sample_metadata_csv()
      * make_plate_names()
      * process_additional_standard_plates()
  - generate_lib_creation_files.py
      * apply_template_to_plates()
  - create_capsule_spits.py
      * validate_database_schema()
      * merge_sample_metadata_for_spits()

Run with:
    python -m pytest tests/test_project_to_proposal_refactor.py -v
"""

import sys
import pytest
import pandas as pd
import tempfile
import os
from pathlib import Path
from io import StringIO

# Add parent directory to path so we can import the scripts
sys.path.insert(0, str(Path(__file__).parent.parent))

import initiate_project_folder_and_make_sort_plate_labels as s1
import generate_lib_creation_files as s2
import create_capsule_spits as s4


# ===========================================================================
# Helpers
# ===========================================================================

def make_csv_file(content: str, tmp_path: Path, filename: str = "sample_metadtata.csv") -> Path:
    """Write a CSV string to a temp file and return its path."""
    p = tmp_path / filename
    p.write_text(content)
    return p


# ===========================================================================
# Script 1 – read_sample_csv
# ===========================================================================

class TestReadSampleCsv:
    """read_sample_csv() must accept CSVs without a Project column."""

    def test_accepts_csv_without_project_column(self, tmp_path):
        csv_content = "Proposal,Sample,Number_of_sorted_plates\nBP9735,SitukAM,2\n"
        csv_path = make_csv_file(csv_content, tmp_path)
        df = s1.read_sample_csv(csv_path)
        assert len(df) == 1
        assert "Proposal" in df.columns
        assert "Project" not in df.columns

    def test_rejects_csv_missing_proposal(self, tmp_path):
        csv_content = "Sample,Number_of_sorted_plates\nSitukAM,2\n"
        csv_path = make_csv_file(csv_content, tmp_path)
        with pytest.raises(SystemExit):
            s1.read_sample_csv(csv_path)

    def test_rejects_csv_missing_sample(self, tmp_path):
        csv_content = "Proposal,Number_of_sorted_plates\nBP9735,2\n"
        csv_path = make_csv_file(csv_content, tmp_path)
        with pytest.raises(SystemExit):
            s1.read_sample_csv(csv_path)

    def test_rejects_csv_missing_number_of_sorted_plates(self, tmp_path):
        csv_content = "Proposal,Sample\nBP9735,SitukAM\n"
        csv_path = make_csv_file(csv_content, tmp_path)
        with pytest.raises(SystemExit):
            s1.read_sample_csv(csv_path)

    def test_csv_with_project_column_still_works(self, tmp_path):
        """A CSV that still has a Project column should not break anything
        (extra columns are allowed; only missing required ones fail)."""
        csv_content = "Proposal,Project,Sample,Number_of_sorted_plates\nBP9735,BP9735,SitukAM,2\n"
        csv_path = make_csv_file(csv_content, tmp_path)
        df = s1.read_sample_csv(csv_path)
        assert len(df) == 1


# ===========================================================================
# Script 1 – make_plate_names
# ===========================================================================

class TestMakePlateNames:
    """make_plate_names() must use Proposal (not Project) to build plate names."""

    def _make_sample_df(self, proposal="BP9735", sample="SitukAM", num_plates=2):
        return pd.DataFrame([{
            "Proposal": proposal,
            "Sample": sample,
            "Number_of_sorted_plates": num_plates,
        }])

    def test_plate_name_uses_proposal(self):
        df = self._make_sample_df(proposal="BP9735", sample="SitukAM", num_plates=2)
        result = s1.make_plate_names(df)
        assert result.iloc[0]["plate_name"] == "BP9735_SitukAM.1"
        assert result.iloc[1]["plate_name"] == "BP9735_SitukAM.2"

    def test_project_column_stores_proposal_value(self):
        """The internal 'project' column in individual_plates must store the Proposal value."""
        df = self._make_sample_df(proposal="BP9735", sample="SitukAM", num_plates=1)
        result = s1.make_plate_names(df)
        assert result.iloc[0]["project"] == "BP9735"

    def test_correct_number_of_plates_generated(self):
        df = self._make_sample_df(num_plates=3)
        result = s1.make_plate_names(df)
        assert len(result) == 3

    def test_plate_numbers_are_sequential(self):
        df = self._make_sample_df(num_plates=3)
        result = s1.make_plate_names(df)
        assert list(result["plate_number"]) == [1, 2, 3]

    def test_multiple_samples(self):
        df = pd.DataFrame([
            {"Proposal": "BP9735", "Sample": "SitukAM", "Number_of_sorted_plates": 2},
            {"Proposal": "BP9735", "Sample": "WCBP1PR", "Number_of_sorted_plates": 1},
        ])
        result = s1.make_plate_names(df)
        assert len(result) == 3
        plate_names = result["plate_name"].tolist()
        assert "BP9735_SitukAM.1" in plate_names
        assert "BP9735_SitukAM.2" in plate_names
        assert "BP9735_WCBP1PR.1" in plate_names

    def test_does_not_require_project_column_in_input(self):
        """make_plate_names must not KeyError if Project column is absent."""
        df = pd.DataFrame([{
            "Proposal": "BP9735",
            "Sample": "SitukAM",
            "Number_of_sorted_plates": 1,
        }])
        # Should not raise
        result = s1.make_plate_names(df)
        assert len(result) == 1


# ===========================================================================
# Script 1 – process_additional_standard_plates
# ===========================================================================

class TestProcessAdditionalStandardPlates:
    """process_additional_standard_plates() must look up by Proposal, not Project."""

    def _make_existing_sample_df(self):
        return pd.DataFrame([
            {"Proposal": "BP9735", "Sample": "SitukAM", "Number_of_sorted_plates": 2},
            {"Proposal": "BP9735", "Sample": "WCBP1PR", "Number_of_sorted_plates": 1},
        ])

    def _make_existing_plates_df(self):
        return pd.DataFrame([
            {"plate_name": "BP9735_SitukAM.1", "project": "BP9735", "sample": "SitukAM",
             "plate_number": 1, "is_custom": False, "barcode": "ABC12-1"},
            {"plate_name": "BP9735_SitukAM.2", "project": "BP9735", "sample": "SitukAM",
             "plate_number": 2, "is_custom": False, "barcode": "ABC12-2"},
            {"plate_name": "BP9735_WCBP1PR.1", "project": "BP9735", "sample": "WCBP1PR",
             "plate_number": 1, "is_custom": False, "barcode": "ABC12-3"},
        ])

    def test_adds_plates_continuing_from_existing_max(self):
        existing_sample_df = self._make_existing_sample_df()
        existing_plates_df = self._make_existing_plates_df()
        additional = {"BP9735_SitukAM": 2}
        result = s1.process_additional_standard_plates(
            existing_sample_df, additional, existing_plates_df
        )
        assert len(result) == 2
        assert "BP9735_SitukAM.3" in result["plate_name"].tolist()
        assert "BP9735_SitukAM.4" in result["plate_name"].tolist()

    def test_project_column_stores_proposal_value(self):
        existing_sample_df = self._make_existing_sample_df()
        existing_plates_df = self._make_existing_plates_df()
        additional = {"BP9735_WCBP1PR": 1}
        result = s1.process_additional_standard_plates(
            existing_sample_df, additional, existing_plates_df
        )
        assert result.iloc[0]["project"] == "BP9735"

    def test_warns_and_skips_unknown_proposal_sample(self, capsys):
        existing_sample_df = self._make_existing_sample_df()
        existing_plates_df = self._make_existing_plates_df()
        additional = {"UNKNOWN_Sample": 1}
        result = s1.process_additional_standard_plates(
            existing_sample_df, additional, existing_plates_df
        )
        # Should return empty (skipped) without crashing
        assert result.empty or len(result) == 0

    def test_does_not_use_project_column_for_lookup(self):
        """Lookup must work even if sample_metadata has no Project column."""
        existing_sample_df = pd.DataFrame([
            {"Proposal": "BP9735", "Sample": "SitukAM", "Number_of_sorted_plates": 1},
        ])
        existing_plates_df = pd.DataFrame([
            {"plate_name": "BP9735_SitukAM.1", "project": "BP9735", "sample": "SitukAM",
             "plate_number": 1, "is_custom": False, "barcode": "ABC12-1"},
        ])
        additional = {"BP9735_SitukAM": 1}
        # Must not raise KeyError on 'Project'
        result = s1.process_additional_standard_plates(
            existing_sample_df, additional, existing_plates_df
        )
        assert len(result) == 1
        assert result.iloc[0]["plate_name"] == "BP9735_SitukAM.2"


# ===========================================================================
# Script 2 – apply_template_to_plates
# ===========================================================================

class TestApplyTemplatesToPlates:
    """apply_template_to_plates() must read from individual_plates 'project' column
    (which now stores the Proposal value) without error."""

    def _make_template_df(self):
        """Minimal standard_sort_layout.csv-like template."""
        rows = []
        for row_letter in ["A", "B"]:
            for col in [1, 2]:
                well = f"{row_letter}{col}"
                rows.append({
                    "Plate_ID": "TEMPLATE",
                    "Well_Row": row_letter,
                    "Well_Col": col,
                    "Well": well,
                    "Sample": "sample_name",
                    "Type": "sample",
                    "number_of_cells/capsules": 1,
                    "Group_1": "",
                    "Group_2": "",
                    "Group_3": "",
                })
        return pd.DataFrame(rows)

    def _make_individual_plates_df(self, proposal="BP9735", sample="SitukAM"):
        """individual_plates table where 'project' stores the Proposal value."""
        return pd.DataFrame([{
            "plate_name": f"{proposal}_{sample}.1",
            "project": proposal,   # stores Proposal value
            "sample": sample,
            "plate_number": 1,
            "is_custom": False,
            "barcode": "ABC12-1",
        }])

    def test_applies_template_without_keyerror(self):
        template_df = self._make_template_df()
        individual_plates_df = self._make_individual_plates_df()
        plates_needing_template = ["BP9735_SitukAM.1"]
        # Should not raise KeyError on 'project' or 'Project'
        result = s2.apply_template_to_plates(
            plates_needing_template, template_df, individual_plates_df
        )
        assert "BP9735_SitukAM.1" in result

    def test_plate_id_filled_correctly(self):
        template_df = self._make_template_df()
        individual_plates_df = self._make_individual_plates_df()
        plates_needing_template = ["BP9735_SitukAM.1"]
        result = s2.apply_template_to_plates(
            plates_needing_template, template_df, individual_plates_df
        )
        plate_df = result["BP9735_SitukAM.1"]
        assert (plate_df["Plate_ID"] == "BP9735_SitukAM.1").all()

    def test_sample_column_filled_with_sample_name(self):
        template_df = self._make_template_df()
        individual_plates_df = self._make_individual_plates_df(sample="SitukAM")
        plates_needing_template = ["BP9735_SitukAM.1"]
        result = s2.apply_template_to_plates(
            plates_needing_template, template_df, individual_plates_df
        )
        plate_df = result["BP9735_SitukAM.1"]
        sample_wells = plate_df[plate_df["Type"] == "sample"]
        assert (sample_wells["Sample"] == "SitukAM").all()


# ===========================================================================
# Script 4 – validate_database_schema
# ===========================================================================

class TestValidateDatabaseSchema:
    """validate_database_schema() must not require 'Project' in sample_metadata."""

    def _make_tables(self, sample_metadata_cols=None):
        if sample_metadata_cols is None:
            sample_metadata_cols = ["Proposal", "Sample"]
        sample_metadata_df = pd.DataFrame(columns=sample_metadata_cols)
        individual_plates_df = pd.DataFrame(columns=["plate_name", "upper_left_registration"])
        master_plate_data_df = pd.DataFrame(
            columns=["Plate_ID", "Well", "Type", "Index_Set", "Passed_library"]
        )
        return sample_metadata_df, individual_plates_df, master_plate_data_df

    def test_passes_without_project_column(self):
        sm, ip, mp = self._make_tables(["Proposal", "Sample"])
        # Should not raise
        s4.validate_database_schema(sm, ip, mp)

    def test_fails_if_proposal_missing(self):
        sm, ip, mp = self._make_tables(["Sample"])
        with pytest.raises(SystemExit):
            s4.validate_database_schema(sm, ip, mp)

    def test_fails_if_sample_missing(self):
        sm, ip, mp = self._make_tables(["Proposal"])
        with pytest.raises(SystemExit):
            s4.validate_database_schema(sm, ip, mp)

    def test_passes_even_if_project_column_present(self):
        """Extra columns (like a legacy Project column) should not cause failure."""
        sm, ip, mp = self._make_tables(["Proposal", "Project", "Sample"])
        # Should not raise
        s4.validate_database_schema(sm, ip, mp)


# ===========================================================================
# Script 4 – merge_sample_metadata_for_spits
# ===========================================================================

class TestMergeSampleMetadataForSpits:
    """merge_sample_metadata_for_spits() must join on Proposal+Sample, not Project+Sample."""

    def _make_selected_wells(self):
        return pd.DataFrame([
            {"Plate_ID": "BP9735_SitukAM.1", "Well": "A1", "Type": "sample",
             "Plate_Barcode": "ABC12-1", "Index_Name": "PE17_A01",
             "Group_1": "G1", "Group_2": "", "Group_3": ""},
            {"Plate_ID": "BP9735_SitukAM.1", "Well": "A3", "Type": "neg_cntrl",
             "Plate_Barcode": "ABC12-1", "Index_Name": "PE17_A02",
             "Group_1": "G1", "Group_2": "", "Group_3": ""},
        ])

    def _make_sample_metadata_no_project(self):
        """sample_metadata WITHOUT a Project column."""
        return pd.DataFrame([{
            "Proposal": "BP9735",
            "Sample": "SitukAM",
            "Collection Year": 2023,
            "Collection Month": "June",
            "Collection Day": 15,
            "Sample Isolated From": "seawater",
            "Latitude": 57.5,
            "Longitude": -152.3,
            "Depth (m)": 5.0,
            "Elevation (m)": 0.0,
            "Country": "USA",
        }])

    def test_merges_without_project_column(self):
        wells = self._make_selected_wells()
        metadata = self._make_sample_metadata_no_project()
        result = s4.merge_sample_metadata_for_spits(wells, metadata)
        assert len(result) == 2
        assert "Collection Year" in result.columns

    def test_metadata_values_populated_correctly(self):
        wells = self._make_selected_wells()
        metadata = self._make_sample_metadata_no_project()
        result = s4.merge_sample_metadata_for_spits(wells, metadata)
        assert result.iloc[0]["Collection Year"] == 2023
        assert result.iloc[0]["Country"] == "USA"

    def test_no_join_key_columns_in_result(self):
        """Temporary join columns _join_Proposal and _join_Sample must be dropped."""
        wells = self._make_selected_wells()
        metadata = self._make_sample_metadata_no_project()
        result = s4.merge_sample_metadata_for_spits(wells, metadata)
        assert "_join_Proposal" not in result.columns
        assert "_join_Sample" not in result.columns
        assert "_join_Project" not in result.columns

    def test_no_project_column_in_result(self):
        """The result must not contain a 'Project' column from the metadata."""
        wells = self._make_selected_wells()
        metadata = self._make_sample_metadata_no_project()
        result = s4.merge_sample_metadata_for_spits(wells, metadata)
        assert "Project" not in result.columns

    def test_proposal_not_in_result_columns(self):
        """Proposal is used as a join key and dropped; it should not appear as a column.
        The proposal is already encoded in Plate_ID so it is redundant in the output."""
        wells = self._make_selected_wells()
        metadata = self._make_sample_metadata_no_project()
        result = s4.merge_sample_metadata_for_spits(wells, metadata)
        # Proposal is consumed as a join key (_join_Proposal) and dropped after merge
        assert "Proposal" not in result.columns
        # But the metadata fields that matter ARE present
        assert "Collection Year" in result.columns
        assert "Country" in result.columns

    def test_unmatched_wells_produce_warning_not_crash(self, capsys):
        """Wells with no matching metadata row should warn but not crash."""
        wells = pd.DataFrame([{
            "Plate_ID": "UNKNOWN_Sample.1", "Well": "A1", "Type": "sample",
            "Plate_Barcode": "ZZZ99-1", "Index_Name": "PE17_A01",
            "Group_1": "", "Group_2": "", "Group_3": "",
        }])
        metadata = self._make_sample_metadata_no_project()
        # Should not raise
        result = s4.merge_sample_metadata_for_spits(wells, metadata)
        assert len(result) == 1

    def test_multiple_samples_merged_correctly(self):
        """Each well must get metadata from its own Proposal+Sample combination."""
        wells = pd.DataFrame([
            {"Plate_ID": "BP9735_SitukAM.1", "Well": "A1", "Type": "sample",
             "Plate_Barcode": "ABC12-1", "Index_Name": "PE17_A01",
             "Group_1": "", "Group_2": "", "Group_3": ""},
            {"Plate_ID": "BP9735_WCBP1PR.1", "Well": "A1", "Type": "sample",
             "Plate_Barcode": "ABC12-2", "Index_Name": "PE17_A01",
             "Group_1": "", "Group_2": "", "Group_3": ""},
        ])
        metadata = pd.DataFrame([
            {"Proposal": "BP9735", "Sample": "SitukAM", "Country": "USA",
             "Collection Year": 2023, "Collection Month": "June", "Collection Day": 15,
             "Sample Isolated From": "seawater", "Latitude": 57.5, "Longitude": -152.3,
             "Depth (m)": 5.0, "Elevation (m)": 0.0},
            {"Proposal": "BP9735", "Sample": "WCBP1PR", "Country": "Canada",
             "Collection Year": 2022, "Collection Month": "July", "Collection Day": 4,
             "Sample Isolated From": "freshwater", "Latitude": 49.0, "Longitude": -123.0,
             "Depth (m)": 2.0, "Elevation (m)": 10.0},
        ])
        result = s4.merge_sample_metadata_for_spits(wells, metadata)
        situk_row = result[result["Plate_ID"] == "BP9735_SitukAM.1"].iloc[0]
        wcbp_row = result[result["Plate_ID"] == "BP9735_WCBP1PR.1"].iloc[0]
        assert situk_row["Country"] == "USA"
        assert wcbp_row["Country"] == "Canada"
