"""Tests for streaming CAS writes and simplified JSONL format."""

import json
import tempfile
from pathlib import Path

import pytest

from edsl.object_store.fs_backend import FileSystemBackend
from edsl.object_store.streaming_writer import StreamingCASWriter
from edsl.object_store.cas_repository import CASRepository
from edsl.results.results_serializer import ResultsSerializer


# ---------------------------------------------------------------------------
# StreamingCASWriter unit tests
# ---------------------------------------------------------------------------


class TestStreamingCASWriter:
    def _make_writer(self, tmpdir):
        backend = FileSystemBackend(tmpdir)
        return StreamingCASWriter(backend), backend

    def test_write_preamble_creates_initial_commit(self, tmp_path):
        w, backend = self._make_writer(tmp_path)
        w.write_preamble(['{"__header__": true}', '{"n_survey_lines": 0}'])

        assert w.tip is not None
        assert w.n_results == 0
        # HEAD and ref exist
        assert backend.exists("HEAD")
        assert backend.exists(f"refs/main")
        # current.jsonl is valid
        content = backend.read("current.jsonl")
        lines = [l for l in content.strip().split("\n") if l.strip()]
        assert len(lines) == 2

    def test_append_result_creates_commits(self, tmp_path):
        w, backend = self._make_writer(tmp_path)
        w.write_preamble(['{"__header__": true}', '{"n_survey_lines": 0}'])
        tip_after_preamble = w.tip

        w.append_result('{"answer": "hello"}')
        assert w.n_results == 1
        assert w.tip != tip_after_preamble

        w.append_result('{"answer": "world"}')
        assert w.n_results == 2

        # current.jsonl should have 4 lines (header, manifest, 2 results)
        content = backend.read("current.jsonl")
        lines = [l for l in content.strip().split("\n") if l.strip()]
        assert len(lines) == 4

    def test_append_results_batch(self, tmp_path):
        w, backend = self._make_writer(tmp_path)
        w.write_preamble(['{"__header__": true}', '{"n_survey_lines": 0}'])

        w.append_results_batch(['{"a": 1}', '{"a": 2}', '{"a": 3}'])
        assert w.n_results == 3

        # Should be a single commit for the batch (+ initial preamble commit)
        repo = CASRepository(tmp_path, backend=backend)
        history = repo.log()
        assert len(history) == 2  # preamble + batch

    def test_each_commit_is_loadable(self, tmp_path):
        """Every intermediate commit should be loadable via CASRepository."""
        w, backend = self._make_writer(tmp_path)
        w.write_preamble(['{"__header__": true}', '{"n_survey_lines": 0}'])

        commits = [w.tip]
        for i in range(3):
            w.append_result(json.dumps({"answer": f"result_{i}"}))
            commits.append(w.tip)

        repo = CASRepository(tmp_path, backend=backend)
        for i, commit_hash in enumerate(commits):
            content = repo.load(commit=commit_hash)
            lines = [l for l in content.strip().split("\n") if l.strip()]
            # preamble (2) + i results (commit 0 has 0 results, etc)
            assert len(lines) == 2 + i

    def test_deduplication(self, tmp_path):
        """Identical rows should share the same blob."""
        w, backend = self._make_writer(tmp_path)
        w.write_preamble(['{"__header__": true}'])
        w.append_result('{"answer": "same"}')
        w.append_result('{"answer": "same"}')

        # Count blobs
        blobs = list(backend.list_prefix("blobs/"))
        # Should have: header blob + "same" blob = 2 unique blobs
        assert len(blobs) == 2

    def test_commit_history(self, tmp_path):
        """Commit chain should be walkable."""
        w, backend = self._make_writer(tmp_path)
        w.write_preamble(['{"__header__": true}'])
        w.append_result('{"a": 1}')
        w.append_result('{"a": 2}')

        repo = CASRepository(tmp_path, backend=backend)
        history = repo.log()
        assert len(history) == 3  # preamble + 2 results
        # Newest first
        assert history[0]["message"] == "Result 2"
        assert history[1]["message"] == "Result 1"
        assert history[2]["message"] == "Job started"


# ---------------------------------------------------------------------------
# Results JSONL round-trip tests
# ---------------------------------------------------------------------------


class TestResultsJSONLFormat:
    def test_round_trip_new_format(self):
        """Results.to_jsonl -> Results.from_jsonl works with new format (no cache)."""
        from edsl.results import Results

        r = Results.example()
        jsonl_str = r.to_jsonl()

        # Verify no n_cache_lines or n_results in output
        lines = jsonl_str.strip().split("\n")
        header = json.loads(lines[0])
        manifest = json.loads(lines[1])
        assert "n_results" not in header
        assert "n_cache_lines" not in manifest

        # Round-trip
        r2 = Results.from_jsonl(jsonl_str)
        assert len(r2) == len(r)

    def test_streaming_writer_produces_loadable_results(self):
        """StreamingCASWriter output should be loadable as Results via from_jsonl."""
        from edsl.results import Results

        r = Results.example()

        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FileSystemBackend(tmpdir)
            w = StreamingCASWriter(backend)

            # Build preamble from the Results serializer
            from edsl import __version__

            survey_rows = list(r.survey.to_jsonl_rows())
            header = json.dumps({
                "__header__": True,
                "edsl_class_name": "Results",
                "edsl_version": __version__,
                "format": "inline",
            })
            manifest = json.dumps({
                "created_columns": r.created_columns,
                "name": r.name,
                "n_survey_lines": len(survey_rows),
            })
            preamble = [header, manifest] + survey_rows
            w.write_preamble(preamble)

            # Append each result
            for result in r.data:
                row = json.dumps(result.to_dict(add_edsl_version=True))
                w.append_result(row)

            # Load from current.jsonl
            content = backend.read("current.jsonl")
            r2 = Results.from_jsonl(content)
            assert len(r2) == len(r)

            # Also load from CAS repo
            repo = CASRepository(tmpdir, backend=backend)
            content_from_repo = repo.load()
            r3 = Results.from_jsonl(content_from_repo)
            assert len(r3) == len(r)


# ---------------------------------------------------------------------------
# RunnerCASIntegration tests
# ---------------------------------------------------------------------------


class TestRunnerCASIntegration:
    def test_build_preamble(self):
        """_build_preamble should produce valid header + manifest + survey rows."""
        from edsl.runner.cas_integration import RunnerCASIntegration
        from edsl.surveys import Survey
        from edsl.questions import QuestionFreeText

        q = QuestionFreeText(question_name="q0", question_text="Hello?")
        survey = Survey(questions=[q])

        preamble = RunnerCASIntegration._build_preamble(survey)
        assert len(preamble) >= 2  # header + manifest + at least some survey rows

        header = json.loads(preamble[0])
        assert header["__header__"] is True
        assert header["edsl_class_name"] == "Results"

        manifest = json.loads(preamble[1])
        assert "n_survey_lines" in manifest
        assert manifest["n_survey_lines"] == len(preamble) - 2
