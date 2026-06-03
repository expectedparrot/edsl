from edsl.jobs.cost_estimation.job_cost_estimate import JobCostEstimate


def make_row(**kwargs):
    """Minimal valid detail row with sensible defaults."""
    defaults = {
        "interview_index": 0,
        "question_name": "q0",
        "agent_index": 0,
        "scenario_index": 0,
        "model": "test",
        "inference_service": "test",
        "estimator_used": "FreeTextStyleEstimator(output=TokenRatio(1.0))",
        "reach_probability": 1.0,
        "prompt_tokens": 10,
        "file_tokens": 0,
        "memory_tokens": 0,
        "answer_tokens": 5,
        "comment_tokens": 0,
        "thinking_tokens": 0,
        "total_input_tokens": 10,
        "total_output_tokens": 5,
        "billable": True,
        "cost_usd": 0.5,
    }
    defaults.update(kwargs)
    return defaults


class TestTotals:
    """Aggregate properties sum across all rows."""

    def test_total_cost_usd(self):
        rows = [make_row(cost_usd=1.0), make_row(cost_usd=2.5)]
        result = JobCostEstimate(rows=rows, warnings=[])
        assert result.total_cost_usd == 3.5

    def test_total_input_tokens(self):
        rows = [make_row(total_input_tokens=10), make_row(total_input_tokens=20)]
        result = JobCostEstimate(rows=rows, warnings=[])
        assert result.total_input_tokens == 30

    def test_total_output_tokens(self):
        rows = [make_row(total_output_tokens=5), make_row(total_output_tokens=7)]
        result = JobCostEstimate(rows=rows, warnings=[])
        assert result.total_output_tokens == 12

    def test_num_questions(self):
        rows = [make_row(), make_row(question_name="q1"), make_row(question_name="q2")]
        result = JobCostEstimate(rows=rows, warnings=[])
        assert result.num_questions == 3

    def test_empty_rows(self):
        result = JobCostEstimate(rows=[], warnings=[])
        assert result.total_cost_usd == 0
        assert result.total_input_tokens == 0
        assert result.total_output_tokens == 0
        assert result.num_questions == 0


class TestDetailDataset:
    """detail property returns a Dataset with one entry per row and all expected columns."""

    EXPECTED_COLUMNS = [
        "question_name",
        "model",
        "inference_service",
        "estimator_used",
        "reach_probability",
        "prompt_tokens",
        "file_tokens",
        "memory_tokens",
        "answer_tokens",
        "comment_tokens",
        "thinking_tokens",
        "total_input_tokens",
        "total_output_tokens",
        "billable",
        "cost_usd",
    ]

    def test_detail_has_expected_columns(self):
        result = JobCostEstimate(rows=[make_row()], warnings=[])
        detail_keys = result.detail.keys()
        for col in self.EXPECTED_COLUMNS:
            assert col in detail_keys, f"Missing column: {col}"

    def test_detail_empty_rows(self):
        result = JobCostEstimate(rows=[], warnings=[])
        assert result.detail is not None


class TestWarnings:
    def test_warnings_preserved(self):
        warnings = ["No branch_weights provided.", "Some other warning."]
        result = JobCostEstimate(rows=[], warnings=warnings)
        assert result.warnings == warnings

    def test_warnings_is_list(self):
        result = JobCostEstimate(rows=[], warnings=[])
        assert isinstance(result.warnings, list)
