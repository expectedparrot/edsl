from edsl import Agent, QuestionMatrix, ScenarioList, Survey


def test_dynamic_matrix_rows_are_isolated_recorded_and_used_by_direct_answers():
    """Each interview uses and records its own reproducible resolved row order."""
    seen_rows = []

    def answer_question_directly(self, question, scenario):
        seen_rows.append((scenario["respondent"], list(question.question_items)))
        return {item: "Never" for item in question.question_items}

    agent = Agent()
    agent.add_direct_question_answering_method(answer_question_directly)
    question = QuestionMatrix(
        question_name="ratings",
        question_text="Rate each item.",
        question_items="{{ scenario.rows }}",
        question_options=["Never", "Often"],
        randomize_items=True,
        items_to_pin=["Other"],
    )
    scenarios = ScenarioList.from_list(
        "rows",
        [["A", "B", "Other"], ["X", "Y", "Other"]],
    )
    scenarios[0]["respondent"] = "first"
    scenarios[1]["respondent"] = "second"

    results = (
        Survey([question])
        .by(scenarios)
        .by(agent)
        .run(
            disable_remote_inference=True,
            disable_remote_cache=True,
        )
    )

    recorded_rows = dict(
        results.select(
            "scenario.respondent", "question_items.ratings_question_items"
        ).to_list()
    )
    direct_rows = dict(seen_rows)

    assert recorded_rows == direct_rows
    assert {frozenset(rows) for rows in recorded_rows.values()} == {
        frozenset(["A", "B", "Other"]),
        frozenset(["X", "Y", "Other"]),
    }
    assert all(rows[-1] == "Other" for rows in recorded_rows.values())
    assert results.select("question_options.ratings_question_options").to_list() == [
        ["Never", "Often"],
        ["Never", "Often"],
    ]
