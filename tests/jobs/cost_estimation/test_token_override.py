from edsl.jobs.cost_estimation.token_override import TokenOverride


class TestMatches:
    def test_global_matches_any_service_and_model(self):
        o = TokenOverride(answer_tokens=50)
        assert o.matches("openai", "gpt-4o")
        assert o.matches("google", "gemini-3.5-flash")
        assert o.matches("anthropic", "claude-sonnet-4-6")

    def test_service_only_matches_correct_service(self):
        o = TokenOverride(answer_tokens=50, service="openai")
        assert o.matches("openai", "gpt-4o")
        assert o.matches("openai", "gpt-4o-mini")
        assert not o.matches("google", "gemini-3.5-flash")

    def test_model_only_matches_correct_model(self):
        o = TokenOverride(answer_tokens=50, model="gpt-4o")
        assert o.matches("openai", "gpt-4o")
        assert o.matches("other_service", "gpt-4o")
        assert not o.matches("openai", "gpt-4o-mini")

    def test_service_and_model_both_must_match(self):
        o = TokenOverride(answer_tokens=50, service="openai", model="gpt-4o")
        assert o.matches("openai", "gpt-4o")
        assert not o.matches("openai", "gpt-4o-mini")
        assert not o.matches("google", "gpt-4o")


class TestSpecificity:
    def test_global_is_zero(self):
        assert TokenOverride(answer_tokens=50).specificity() == 0

    def test_service_only_is_one(self):
        assert TokenOverride(answer_tokens=50, service="openai").specificity() == 1

    def test_model_only_is_one(self):
        assert TokenOverride(answer_tokens=50, model="gpt-4o").specificity() == 1

    def test_service_and_model_is_two(self):
        assert (
            TokenOverride(
                answer_tokens=50, service="openai", model="gpt-4o"
            ).specificity()
            == 2
        )

    def test_most_specific_wins_via_max(self):
        overrides = [
            TokenOverride(answer_tokens=100),
            TokenOverride(answer_tokens=200, service="openai"),
            TokenOverride(answer_tokens=300, service="openai", model="gpt-4o"),
        ]
        best = max(overrides, key=lambda o: o.specificity())
        assert best.answer_tokens == 300


class TestDescribe:
    def test_single_field_no_scope(self):
        assert TokenOverride(answer_tokens=50).describe() == "answer_tokens=50"

    def test_multiple_fields(self):
        assert (
            TokenOverride(answer_tokens=50, comment_tokens=10).describe()
            == "answer_tokens=50, comment_tokens=10"
        )

    def test_scope_appears_in_brackets(self):
        desc = TokenOverride(
            answer_tokens=50, service="openai", model="gpt-4o"
        ).describe()
        assert "[openai, gpt-4o]" in desc

    def test_service_only_scope(self):
        desc = TokenOverride(answer_tokens=50, service="google").describe()
        assert "[google]" in desc

    def test_note_appended(self):
        desc = TokenOverride(answer_tokens=50, note="from pilot").describe()
        assert "from pilot" in desc
        assert "answer_tokens=50" in desc

    def test_no_fields_set(self):
        assert TokenOverride().describe() == "no fields set"
