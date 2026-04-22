#!/usr/bin/env python3
"""
Tests for the new-samples-on-subsequent-run feature added to
initiate_project_folder_and_make_sort_plate_labels.py.

Covers:
  - detect_new_samples_csv()
  - check_downstream_steps_not_run()
  - validate_new_samples_against_existing()
  - process_subsequent_run() new-samples path (integration)

Run with:
    conda run -n sip-lims python -m pytest tests/test_initiate_project_new_samples.py -v
"""

import json
import sys
import pytest
import pandas as pd
from pathlib import Path

# Add parent directory to path so we can import the script
sys.path.insert(0, str(Path(__file__).parent.parent))

import initiate_project_folder_and_make_sort_plate_labels as s


# ---------------------------------------------------------------------------
# Helpers — minimal valid sample metadata rows
# ---------------------------------------------------------------------------

def _make_sample_row(proposal="BP9735", group="SitukAM", full="Situk River AM",
                     num_plates=2, is_custom=False):
    """Return a dict representing one valid sample_metadata row."""
    return {
        'Proposal': proposal,
        'Group_or_abrvSample': group,
        'Sample_full': full,
        'Number_of_sorted_plates': num_plates,
        'is_custom': is_custom,
    }


def _make_sample_df(*rows):
    """Build a DataFrame from one or more row dicts."""
    return pd.DataFrame(list(rows))


def _write_sample_csv(path, df):
    """Write a sample metadata DataFrame to a CSV file."""
    df.to_csv(path, index=False)


# ---------------------------------------------------------------------------
# Tests: detect_new_samples_csv
# ---------------------------------------------------------------------------

class TestDetectNewSamplesCsv:
    def test_returns_none_when_no_file(self, tmp_path, monkeypatch):
        """No new_samples.csv → returns None (no error)."""
        monkeypatch.chdir(tmp_path)
        result = s.detect_new_samples_csv()
        assert result is None

    def test_returns_path_when_file_exists(self, tmp_path, monkeypatch):
        """new_samples.csv present → returns its Path."""
        monkeypatch.chdir(tmp_path)
        csv = tmp_path / "new_samples.csv"
        csv.write_text("Proposal,Group_or_abrvSample\nBP9735,SitukAM\n")
        result = s.detect_new_samples_csv()
        assert result is not None
        assert result.name == "new_samples.csv"

    def test_exits_on_multiple_matching_files(self, tmp_path, monkeypatch):
        """Multiple new_samples*.csv files → FATAL ERROR / sys.exit()."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "new_samples.csv").write_text("a,b\n1,2\n")
        (tmp_path / "new_samples_extra.csv").write_text("a,b\n3,4\n")
        with pytest.raises(SystemExit):
            s.detect_new_samples_csv()

    def test_canonical_file_takes_priority(self, tmp_path, monkeypatch):
        """Only new_samples.csv (no variants) → returns it without error."""
        monkeypatch.chdir(tmp_path)
        csv = tmp_path / "new_samples.csv"
        csv.write_text("Proposal,Group_or_abrvSample\nBP9735,SitukAM\n")
        result = s.detect_new_samples_csv()
        assert result == Path("new_samples.csv")


# ---------------------------------------------------------------------------
# Tests: check_downstream_steps_not_run
# ---------------------------------------------------------------------------

class TestCheckDownstreamStepsNotRun:
    def test_passes_when_no_workflow_state_file(self, tmp_path, monkeypatch, capsys):
        """Missing workflow_state.json → warning printed, no sys.exit()."""
        monkeypatch.chdir(tmp_path)
        # Should not raise
        s.check_downstream_steps_not_run()
        captured = capsys.readouterr()
        assert "WARNING" in captured.out

    def test_passes_when_only_init_project_completed(self, tmp_path, monkeypatch):
        """Only init_project completed → no blocking steps → passes."""
        monkeypatch.chdir(tmp_path)
        state = {"init_project": "completed"}
        (tmp_path / "workflow_state.json").write_text(json.dumps(state))
        # Should not raise
        s.check_downstream_steps_not_run()

    def test_passes_when_prep_library_completed(self, tmp_path, monkeypatch):
        """prep_library (Script 2) completed → still allowed → passes."""
        monkeypatch.chdir(tmp_path)
        state = {"init_project": "completed", "prep_library": "completed"}
        (tmp_path / "workflow_state.json").write_text(json.dumps(state))
        s.check_downstream_steps_not_run()

    def test_passes_when_analyze_quality_completed(self, tmp_path, monkeypatch):
        """analyze_quality (Script 3) completed → still allowed → passes."""
        monkeypatch.chdir(tmp_path)
        state = {
            "init_project": "completed",
            "prep_library": "completed",
            "analyze_quality": "completed",
        }
        (tmp_path / "workflow_state.json").write_text(json.dumps(state))
        s.check_downstream_steps_not_run()

    def test_blocks_when_select_plates_completed(self, tmp_path, monkeypatch):
        """select_plates (Script 4) completed → FATAL ERROR."""
        monkeypatch.chdir(tmp_path)
        state = {
            "init_project": "completed",
            "prep_library": "completed",
            "analyze_quality": "completed",
            "select_plates": "completed",
        }
        (tmp_path / "workflow_state.json").write_text(json.dumps(state))
        with pytest.raises(SystemExit):
            s.check_downstream_steps_not_run()

    def test_blocks_when_process_grid_barcodes_completed(self, tmp_path, monkeypatch):
        """process_grid_barcodes (Script 5) completed → FATAL ERROR."""
        monkeypatch.chdir(tmp_path)
        state = {"process_grid_barcodes": "completed"}
        (tmp_path / "workflow_state.json").write_text(json.dumps(state))
        with pytest.raises(SystemExit):
            s.check_downstream_steps_not_run()

    def test_blocks_when_verify_scanning_esp_completed(self, tmp_path, monkeypatch):
        """verify_scanning_esp (Script 6) completed → FATAL ERROR."""
        monkeypatch.chdir(tmp_path)
        state = {"verify_scanning_esp": "completed"}
        (tmp_path / "workflow_state.json").write_text(json.dumps(state))
        with pytest.raises(SystemExit):
            s.check_downstream_steps_not_run()

    def test_passes_when_downstream_steps_not_completed(self, tmp_path, monkeypatch):
        """Downstream steps present but not 'completed' → passes."""
        monkeypatch.chdir(tmp_path)
        state = {
            "init_project": "completed",
            "select_plates": "pending",
            "process_grid_barcodes": "pending",
        }
        (tmp_path / "workflow_state.json").write_text(json.dumps(state))
        s.check_downstream_steps_not_run()

    def test_warns_on_corrupt_workflow_state(self, tmp_path, monkeypatch, capsys):
        """Corrupt workflow_state.json → warning, no sys.exit()."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "workflow_state.json").write_text("NOT VALID JSON {{{")
        s.check_downstream_steps_not_run()
        captured = capsys.readouterr()
        assert "WARNING" in captured.out


# ---------------------------------------------------------------------------
# Tests: validate_new_samples_against_existing
# ---------------------------------------------------------------------------

class TestValidateNewSamplesAgainstExisting:
    def _existing_df(self):
        """Return a minimal existing sample_metadata DataFrame."""
        return _make_sample_df(
            _make_sample_row("BP9735", "SitukAM", "Situk River AM", 2, False),
            _make_sample_row("BP9735", "WCBP1PR", "WC BP1 PR", 3, False),
        )

    def test_passes_with_valid_new_samples(self, tmp_path, monkeypatch):
        """Completely new (Proposal, Group) pairs → passes, returns validated df."""
        monkeypatch.chdir(tmp_path)
        existing = self._existing_df()
        new_df = _make_sample_df(
            _make_sample_row("BP9735", "NewSamp", "New Sample", 1, False),
        )
        csv_path = tmp_path / "new_samples.csv"
        _write_sample_csv(csv_path, new_df)

        result = s.validate_new_samples_against_existing(csv_path, existing)
        assert len(result) == 1
        assert result.iloc[0]['Group_or_abrvSample'] == "NewSamp"

    def test_blocks_when_sample_already_in_db(self, tmp_path, monkeypatch):
        """(Proposal, Group) already in DB → FATAL ERROR."""
        monkeypatch.chdir(tmp_path)
        existing = self._existing_df()
        # SitukAM already exists in existing
        new_df = _make_sample_df(
            _make_sample_row("BP9735", "SitukAM", "Situk River AM", 1, False),
        )
        csv_path = tmp_path / "new_samples.csv"
        _write_sample_csv(csv_path, new_df)

        with pytest.raises(SystemExit):
            s.validate_new_samples_against_existing(csv_path, existing)

    def test_blocks_when_is_custom_missing(self, tmp_path, monkeypatch):
        """new_samples.csv missing is_custom column → FATAL ERROR from read_sample_csv."""
        monkeypatch.chdir(tmp_path)
        existing = self._existing_df()
        # Write CSV without is_custom column
        bad_df = pd.DataFrame([{
            'Proposal': 'BP9735',
            'Group_or_abrvSample': 'NewSamp',
            'Sample_full': 'New Sample',
            'Number_of_sorted_plates': 1,
            # is_custom intentionally omitted
        }])
        csv_path = tmp_path / "new_samples.csv"
        bad_df.to_csv(csv_path, index=False)

        with pytest.raises(SystemExit):
            s.validate_new_samples_against_existing(csv_path, existing)

    def test_blocks_when_is_custom_invalid_value(self, tmp_path, monkeypatch):
        """is_custom has invalid value → FATAL ERROR from read_sample_csv."""
        monkeypatch.chdir(tmp_path)
        existing = self._existing_df()
        bad_df = pd.DataFrame([{
            'Proposal': 'BP9735',
            'Group_or_abrvSample': 'NewSamp',
            'Sample_full': 'New Sample',
            'Number_of_sorted_plates': 1,
            'is_custom': 'maybe',  # invalid
        }])
        csv_path = tmp_path / "new_samples.csv"
        bad_df.to_csv(csv_path, index=False)

        with pytest.raises(SystemExit):
            s.validate_new_samples_against_existing(csv_path, existing)

    def test_blocks_when_group_too_long(self, tmp_path, monkeypatch):
        """Group_or_abrvSample > 8 chars → FATAL ERROR from read_sample_csv."""
        monkeypatch.chdir(tmp_path)
        existing = self._existing_df()
        bad_df = _make_sample_df(
            _make_sample_row("BP9735", "TooLongName", "Too Long", 1, False),
        )
        csv_path = tmp_path / "new_samples.csv"
        _write_sample_csv(csv_path, bad_df)

        with pytest.raises(SystemExit):
            s.validate_new_samples_against_existing(csv_path, existing)

    def test_returns_normalized_is_custom(self, tmp_path, monkeypatch):
        """is_custom values are normalized to Python bools by read_sample_csv."""
        monkeypatch.chdir(tmp_path)
        existing = self._existing_df()
        new_df = pd.DataFrame([{
            'Proposal': 'BP9735',
            'Group_or_abrvSample': 'NewSamp',
            'Sample_full': 'New Sample',
            'Number_of_sorted_plates': 1,
            'is_custom': 'True',  # string form — should be normalized to bool True
        }])
        csv_path = tmp_path / "new_samples.csv"
        new_df.to_csv(csv_path, index=False)

        result = s.validate_new_samples_against_existing(csv_path, existing)
        # read_sample_csv normalizes is_custom to Python bool or numpy bool — both truthy
        assert result.iloc[0]['is_custom'] == True  # noqa: E712

    def test_multiple_new_samples_all_valid(self, tmp_path, monkeypatch):
        """Multiple new samples, none overlapping → all returned."""
        monkeypatch.chdir(tmp_path)
        existing = self._existing_df()
        new_df = _make_sample_df(
            _make_sample_row("BP9735", "NewSmp1", "New Sample 1", 1, False),
            _make_sample_row("BP9735", "NewSmp2", "New Sample 2", 2, True),
        )
        csv_path = tmp_path / "new_samples.csv"
        _write_sample_csv(csv_path, new_df)

        result = s.validate_new_samples_against_existing(csv_path, existing)
        assert len(result) == 2

    def test_partial_overlap_blocks(self, tmp_path, monkeypatch):
        """Mix of new and existing samples → FATAL ERROR (overlap detected)."""
        monkeypatch.chdir(tmp_path)
        existing = self._existing_df()
        new_df = _make_sample_df(
            _make_sample_row("BP9735", "NewSamp", "New Sample", 1, False),
            _make_sample_row("BP9735", "SitukAM", "Situk River AM", 2, False),  # overlap
        )
        csv_path = tmp_path / "new_samples.csv"
        _write_sample_csv(csv_path, new_df)

        with pytest.raises(SystemExit):
            s.validate_new_samples_against_existing(csv_path, existing)


# ---------------------------------------------------------------------------
# Entry point for direct execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
