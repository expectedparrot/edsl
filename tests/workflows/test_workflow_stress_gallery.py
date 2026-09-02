from examples.workflow_stress_gallery import CASE_NARRATIVES, cases, highlight_python
from edsl.sharedstate import SQLiteStateBackend
from edsl.workflows import HumanWorkflow, SQLiteWorkflowStore, WorkflowCoordinator


def test_gallery_cases_are_portable_and_launch_with_expected_initial_fanout(tmp_path):
    expected_ready = {
        "brainstorm": 3,
        "blind-review": 1,
        "escalation": 1,
        "editorial": 1,
        "procurement": 3,
        "moderation": 3,
        "translation": 1,
        "delphi": 6,
        "public-goods": 6,
        "peer-prediction": 6,
        "mixed-research": 3,
        "ultimatum": 1,
        "trust-game": 1,
        "prisoners-dilemma": 2,
        "beauty-contest": 6,
        "dictator": 1,
        "first-price-auction": 5,
        "jury-vote": 7,
        "market-entry": 6,
        "battle-of-sexes": 2,
        "chicken": 2,
    }
    for case in cases():
        workflow = HumanWorkflow.from_dict(case.workflow.to_dict())
        root = tmp_path / case.slug
        store = SQLiteWorkflowStore(root / "workflow.sqlite")
        backends = {
            state_map.state_id: SQLiteStateBackend(
                state_map, root / f"{state_map.state_id}.sqlite"
            )
            for state_map in case.state_maps
        }
        coordinator = WorkflowCoordinator(workflow, store, state_backends=backends)
        instance_id = coordinator.launch(case.agents)

        ready = [item for item in store.items(instance_id) if item["status"] == "ready"]
        assert len(ready) == expected_ready[case.slug]


def test_every_gallery_case_has_an_explanatory_narrative():
    gallery_cases = cases()
    assert set(CASE_NARRATIVES) == {case.slug for case in gallery_cases}
    for narrative in CASE_NARRATIVES.values():
        assert len(narrative.built) > 80
        assert len(narrative.learned) > 80


def test_python_source_is_pygments_highlighted():
    rendered = highlight_python("def example():\n    return 42\n")
    assert 'class="highlight"' in rendered
    assert '<span class="k">def</span>' in rendered
    assert "linenodiv" in rendered
