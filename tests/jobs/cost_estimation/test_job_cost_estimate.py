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

    def test_total_input_tokens_reach_weighted(self):
        # q1 reach=1.0 contributes 500 tokens; q2 reach=0.5 contributes 250
        rows = [
            make_row(question_name="q1", total_input_tokens=500, reach_probability=1.0),
            make_row(question_name="q2", total_input_tokens=500, reach_probability=0.5),
        ]
        result = JobCostEstimate(rows=rows, warnings=[])
        assert result.total_input_tokens == 750

    def test_total_output_tokens_reach_weighted(self):
        rows = [
            make_row(
                question_name="q1", total_output_tokens=100, reach_probability=1.0
            ),
            make_row(
                question_name="q2", total_output_tokens=100, reach_probability=0.5
            ),
        ]
        result = JobCostEstimate(rows=rows, warnings=[])
        assert result.total_output_tokens == 150


class TestSummaryByModel:
    """summary_by_model token totals must be reach-weighted to match cost_usd."""

    def _make_row(self, q_name, reach, input_tokens, output_tokens, cost_usd):
        return make_row(
            question_name=q_name,
            reach_probability=reach,
            total_input_tokens=input_tokens,
            total_output_tokens=output_tokens,
            cost_usd=cost_usd,
            model="gpt-4o",
            inference_service="openai",
            input_price_per_million=1.0,
            output_price_per_million=2.0,
        )

    def test_tokens_reach_weighted_in_summary(self):
        # q1 reach=1.0, q2 reach=0.5 — raw totals would be 1000/200 but weighted are 750/150
        rows = [
            self._make_row("q1", 1.0, 500, 100, 0.0007),
            self._make_row("q2", 0.5, 500, 100, 0.00035),
        ]
        result = JobCostEstimate(rows=rows, warnings=[])
        summary = result.summary_by_model()
        assert len(summary) == 1
        m = summary[0]
        assert m["total_input_tokens"] == 750
        assert m["total_output_tokens"] == 150

    def test_token_cost_equation_holds(self):
        # With reach-weighted tokens, total_cost ≈ (input × $/M + output × $/M) / 1_000_000
        rows = [
            self._make_row("q1", 1.0, 500, 100, 0.0007),
            self._make_row("q2", 0.5, 500, 100, 0.00035),
        ]
        result = JobCostEstimate(rows=rows, warnings=[])
        m = result.summary_by_model()[0]
        derived = (
            m["total_input_tokens"] * m["input_price_per_million"] / 1_000_000
            + m["total_output_tokens"] * m["output_price_per_million"] / 1_000_000
        )
        assert abs(derived - m["total_cost_usd"]) < 0.0001

    def test_all_reach_one_unchanged(self):
        # When reach is 1.0 everywhere the weighted sum equals the raw sum
        rows = [
            self._make_row("q1", 1.0, 500, 100, 0.0007),
            self._make_row("q2", 1.0, 500, 100, 0.0007),
        ]
        result = JobCostEstimate(rows=rows, warnings=[])
        m = result.summary_by_model()[0]
        assert m["total_input_tokens"] == 1000
        assert m["total_output_tokens"] == 200


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
