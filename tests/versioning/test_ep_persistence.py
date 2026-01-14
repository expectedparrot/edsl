"""Tests for GitMixin disk persistence (to_ep/from_ep)."""

import os
import tempfile
import pytest

from edsl.scenarios import Scenario, ScenarioList
from edsl.versioning.exceptions import StagedChangesError, InvalidEPFileError


class TestToDisk:
    """Tests for to_ep method."""

    def test_basic_save(self):
        """Test basic save creates .ep file."""
        sl = ScenarioList([Scenario({"a": 1}), Scenario({"a": 2})])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test")
            sl.to_ep(path)

            # Should create file with .ep extension
            assert os.path.exists(path + ".ep")

    def test_auto_adds_extension(self):
        """Test .ep extension is auto-added if missing."""
        sl = ScenarioList([Scenario({"x": 1})])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "myfile")
            sl.to_ep(path)

            assert os.path.exists(path + ".ep")
            assert not os.path.exists(path)

    def test_respects_existing_extension(self):
        """Test .ep extension is not doubled if already present."""
        sl = ScenarioList([Scenario({"x": 1})])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "myfile.ep")
            sl.to_ep(path)

            assert os.path.exists(path)
            assert not os.path.exists(path + ".ep")

    def test_error_on_uncommitted_changes(self):
        """Test raises error when there are uncommitted changes."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl = sl.append(Scenario({"a": 2}))  # Creates pending event

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(StagedChangesError):
                sl.to_ep(os.path.join(tmpdir, "test"))

    def test_save_after_commit(self):
        """Test save works after committing changes."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("added entry")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.ep")
            sl.to_ep(path)
            assert os.path.exists(path)


class TestFromDisk:
    """Tests for from_ep method."""

    def test_basic_load(self):
        """Test basic load restores data."""
        sl = ScenarioList([Scenario({"a": 1}), Scenario({"a": 2})])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.ep")
            sl.to_ep(path)

            sl2 = ScenarioList.from_ep(path)

            assert len(sl2) == 2
            assert sl2[0]["a"] == 1
            assert sl2[1]["a"] == 2

    def test_auto_adds_extension_on_load(self):
        """Test .ep extension is auto-added when loading if file doesn't exist."""
        sl = ScenarioList([Scenario({"x": 1})])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test")
            sl.to_ep(path)  # Creates test.ep

            # Load without extension
            sl2 = ScenarioList.from_ep(path)
            assert len(sl2) == 1
            assert sl2[0]["x"] == 1

    def test_load_at_main_by_default(self):
        """Test loads at 'main' branch by default."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("feature work")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.ep")
            sl.to_ep(path)

            # Default load should be at main (1 entry)
            sl_main = ScenarioList.from_ep(path)
            assert len(sl_main) == 1

    def test_load_at_specific_branch(self):
        """Test loading at a specific branch."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("feature work")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.ep")
            sl.to_ep(path)

            # Load at feature branch (2 entries)
            sl_feature = ScenarioList.from_ep(path, ref="feature")
            assert len(sl_feature) == 2

    def test_load_at_commit_hash(self):
        """Test loading at a specific commit hash."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("second entry")
        commit_hash = sl.commit_hash

        sl = sl.append(Scenario({"a": 3}))
        sl.git_commit("third entry")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.ep")
            sl.to_ep(path)

            # Load at the second commit (2 entries, not 3)
            sl_at_commit = ScenarioList.from_ep(path, ref=commit_hash)
            assert len(sl_at_commit) == 2


class TestRoundTrip:
    """Tests for round-trip serialization."""

    def test_data_equality(self):
        """Test data is equal after round-trip."""
        sl = ScenarioList([Scenario({"a": 1}), Scenario({"b": 2})])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.ep")
            sl.to_ep(path)
            sl2 = ScenarioList.from_ep(path)

            assert sl == sl2

    def test_commit_hash_preserved(self):
        """Test commit hash is preserved after round-trip."""
        sl = ScenarioList([Scenario({"a": 1})])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.ep")
            sl.to_ep(path)
            sl2 = ScenarioList.from_ep(path)

            assert sl.commit_hash == sl2.commit_hash

    def test_git_log_preserved(self):
        """Test full git log is preserved after round-trip."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("added second")
        sl = sl.append(Scenario({"a": 3}))
        sl.git_commit("added third")

        log_before = sl.git_log()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.ep")
            sl.to_ep(path)
            sl2 = ScenarioList.from_ep(path)

            log_after = sl2.git_log()

            assert len(log_before) == len(log_after)
            for b, a in zip(log_before, log_after):
                assert b.commit_id == a.commit_id
                assert b.message == a.message

    def test_branches_preserved(self):
        """Test all branches are preserved after round-trip."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_branch("feature-1")
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("feature-1 work")

        sl.git_checkout("main")
        sl.git_branch("feature-2")
        sl = sl.append(Scenario({"a": 3}))
        sl.git_commit("feature-2 work")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.ep")
            sl.to_ep(path)

            # Load and verify all branches exist
            sl_main = ScenarioList.from_ep(path, ref="main")
            sl_f1 = ScenarioList.from_ep(path, ref="feature-1")
            sl_f2 = ScenarioList.from_ep(path, ref="feature-2")

            assert len(sl_main) == 1
            assert len(sl_f1) == 2
            assert len(sl_f2) == 2

    def test_multiple_saves_same_file(self):
        """Test saving to the same file overwrites correctly."""
        sl1 = ScenarioList([Scenario({"version": 1})])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.ep")

            sl1.to_ep(path)
            loaded1 = ScenarioList.from_ep(path)
            assert loaded1[0]["version"] == 1

            sl2 = ScenarioList([Scenario({"version": 2})])
            sl2.to_ep(path)
            loaded2 = ScenarioList.from_ep(path)
            assert loaded2[0]["version"] == 2


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_scenario_list(self):
        """Test saving and loading empty ScenarioList."""
        sl = ScenarioList([])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.ep")
            sl.to_ep(path)
            sl2 = ScenarioList.from_ep(path)

            assert len(sl2) == 0
            assert sl == sl2

    def test_complex_scenario_data(self):
        """Test with complex nested data."""
        sl = ScenarioList(
            [
                Scenario(
                    {
                        "name": "test",
                        "nested": {"a": 1, "b": [1, 2, 3]},
                        "list": [{"x": 1}, {"x": 2}],
                    }
                )
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.ep")
            sl.to_ep(path)
            sl2 = ScenarioList.from_ep(path)

            assert sl == sl2
            assert sl2[0]["nested"]["b"] == [1, 2, 3]
            assert sl2[0]["list"][1]["x"] == 2

    def test_unicode_data(self):
        """Test with unicode characters."""
        sl = ScenarioList(
            [Scenario({"emoji": "🎉", "chinese": "你好", "arabic": "مرحبا"})]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.ep")
            sl.to_ep(path)
            sl2 = ScenarioList.from_ep(path)

            assert sl2[0]["emoji"] == "🎉"
            assert sl2[0]["chinese"] == "你好"
            assert sl2[0]["arabic"] == "مرحبا"

    def test_file_not_found(self):
        """Test appropriate error when file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            ScenarioList.from_ep("/nonexistent/path/file.ep")

    def test_invalid_ep_file(self):
        """Test InvalidEPFileError when file is not valid .ep format."""
        with tempfile.NamedTemporaryFile(suffix=".ep", delete=False) as tmp:
            tmp.write(b"not a valid gzip file")
            filepath = tmp.name

        try:
            with pytest.raises(InvalidEPFileError):
                ScenarioList.from_ep(filepath)
        finally:
            os.remove(filepath)

    def test_invalid_json_in_ep_file(self):
        """Test InvalidEPFileError when gzip contains invalid JSON."""
        import gzip

        with tempfile.NamedTemporaryFile(suffix=".ep", delete=False) as tmp:
            filepath = tmp.name

        # Write valid gzip but invalid JSON
        with gzip.open(filepath, "wt") as f:
            f.write("not valid json {{{")

        try:
            with pytest.raises(InvalidEPFileError):
                ScenarioList.from_ep(filepath)
        finally:
            os.remove(filepath)

    def test_missing_git_key_in_ep_file(self):
        """Test InvalidEPFileError when .ep file missing required 'git' key."""
        import gzip
        import json

        with tempfile.NamedTemporaryFile(suffix=".ep", delete=False) as tmp:
            filepath = tmp.name

        # Write valid gzip/JSON but missing git key
        with gzip.open(filepath, "wt") as f:
            json.dump({"edsl_class_name": "ScenarioList"}, f)

        try:
            with pytest.raises(InvalidEPFileError) as exc_info:
                ScenarioList.from_ep(filepath)
            assert "missing 'git' key" in str(exc_info.value)
        finally:
            os.remove(filepath)

    def test_invalid_ref(self):
        """Test loading with invalid ref falls back to saved base_commit."""
        sl = ScenarioList([Scenario({"a": 1})])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.ep")
            sl.to_ep(path)

            # Load with non-existent ref - should fall back gracefully
            sl2 = ScenarioList.from_ep(path, ref="nonexistent-branch")
            # Should still load the data
            assert len(sl2) == 1
