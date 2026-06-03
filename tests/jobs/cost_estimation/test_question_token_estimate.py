from edsl.jobs.cost_estimation.question_token_estimate import QuestionTokenEstimate


class TestTotals:
    """total_input_tokens and total_output_tokens sum their respective fields, treating None as 0."""

    def test_total_input_tokens(self):
        e = QuestionTokenEstimate(prompt_tokens=10, file_tokens=5, memory_tokens=3)
        assert e.total_input_tokens == 18

    def test_total_output_tokens(self):
        e = QuestionTokenEstimate(
            answer_tokens=20, comment_tokens=10, thinking_tokens=5
        )
        assert e.total_output_tokens == 35

    def test_none_fields_count_as_zero(self):
        e = QuestionTokenEstimate(prompt_tokens=10)
        assert e.total_input_tokens == 10
        assert e.total_output_tokens == 0

    def test_total_tokens(self):
        e = QuestionTokenEstimate(prompt_tokens=10, answer_tokens=5)
        assert e.total_tokens == 15


class TestMerge:
    """merge() applies non-None fields from the override, leaving the rest unchanged."""

    def test_override_replaces_non_none_fields(self):
        base = QuestionTokenEstimate(prompt_tokens=10, answer_tokens=20)
        override = QuestionTokenEstimate(answer_tokens=99)
        merged = base.merge(override)
        assert merged.prompt_tokens == 10
        assert merged.answer_tokens == 99

    def test_none_override_fields_leave_base_unchanged(self):
        base = QuestionTokenEstimate(prompt_tokens=10, comment_tokens=5)
        override = QuestionTokenEstimate(prompt_tokens=50)
        merged = base.merge(override)
        assert merged.comment_tokens == 5

    def test_billable_false_cannot_be_overridden(self):
        """A non-billable question stays non-billable even if the override sets billable=True."""
        base = QuestionTokenEstimate(billable=False)
        override = QuestionTokenEstimate(billable=True)
        merged = base.merge(override)
        assert merged.billable is False

    def test_billable_true_preserved_when_override_is_also_true(self):
        base = QuestionTokenEstimate(billable=True)
        override = QuestionTokenEstimate(answer_tokens=10)
        merged = base.merge(override)
        assert merged.billable is True


class TestDescribe:
    def test_single_field(self):
        assert QuestionTokenEstimate(answer_tokens=50).describe() == "answer_tokens=50"

    def test_multiple_fields(self):
        assert QuestionTokenEstimate(answer_tokens=50, comment_tokens=10).describe() == "answer_tokens=50, comment_tokens=10"

    def test_all_token_fields(self):
        e = QuestionTokenEstimate(
            prompt_tokens=100, file_tokens=20, memory_tokens=30,
            answer_tokens=50, comment_tokens=10, thinking_tokens=5,
        )
        assert e.describe() == "prompt_tokens=100, file_tokens=20, memory_tokens=30, answer_tokens=50, comment_tokens=10, thinking_tokens=5"

    def test_no_fields_set(self):
        assert QuestionTokenEstimate().describe() == "no token fields set"

    def test_none_fields_excluded(self):
        desc = QuestionTokenEstimate(prompt_tokens=10).describe()
        assert "file_tokens" not in desc
        assert "answer_tokens" not in desc


class TestToDetailRow:
    """to_detail_row() returns a flat dict suitable for a Dataset row."""

    def test_none_fields_render_as_zero(self):
        e = QuestionTokenEstimate(prompt_tokens=10)
        row = e.to_detail_row()
        assert row["file_tokens"] == 0
        assert row["memory_tokens"] == 0
        assert row["comment_tokens"] == 0
        assert row["thinking_tokens"] == 0

    def test_populated_fields_appear_correctly(self):
        e = QuestionTokenEstimate(prompt_tokens=10, answer_tokens=5, comment_tokens=3)
        row = e.to_detail_row()
        assert row["prompt_tokens"] == 10
        assert row["answer_tokens"] == 5
        assert row["comment_tokens"] == 3

    def test_includes_totals(self):
        e = QuestionTokenEstimate(prompt_tokens=10, answer_tokens=5)
        row = e.to_detail_row()
        assert row["total_input_tokens"] == 10
        assert row["total_output_tokens"] == 5

    def test_billable_included(self):
        row = QuestionTokenEstimate(billable=False).to_detail_row()
        assert row["billable"] is False

        row = QuestionTokenEstimate(billable=True).to_detail_row()
        assert row["billable"] is True
