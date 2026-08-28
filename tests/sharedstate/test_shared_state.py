import json

import pytest

from edsl import (
    InterviewSchedule,
    QuestionCheckBox,
    QuestionFreeText,
    QuestionNumerical,
    QuestionMatrix,
    QuestionMultipleChoice,
    QuestionRank,
    Survey,
)
from edsl.sharedstate import (
    FileStateStore,
    SharedAuction,
    SharedBinaryMarket,
    SharedBudgetPool,
    SharedCoalitionPool,
    SharedAgenda,
    SharedCounterMap,
    SharedDeferredAcceptance,
    SharedLog,
    SharedMatchPool,
    SharedMessageBoard,
    SharedMoneyRequestGame,
    SharedNegotiation,
    SharedSignalSchedule,
    SharedState,
    SharedWorkPool,
)
from edsl.sharedstate.exceptions import (
    SharedStateAuthoringError,
    SharedStateRuntimeError,
)
from edsl.sharedstate.steps import StepContext


def test_counter_replay_and_survey_round_trip(tmp_path):
    state = SharedState(
        "poll",
        FileStateStore(tmp_path / "state.jsonl"),
        votes=SharedCounterMap(["A", "B"]),
    )
    question = QuestionCheckBox(
        question_name="vote", question_text="Pick", question_options=["A", "B"]
    )
    survey = Survey([question, state.votes.tally(question)])

    assert len(survey.questions) == 1
    step = survey._shared_state_steps["vote"][0]
    assert step.execute(StepContext({"vote": ["A"]}, "i1")).ok is True
    assert step.execute(StepContext({"vote": ["A", "B"]}, "i2")).ok is True
    assert state.read().state == {"votes": {"counts": {"A": 2, "B": 1}}}

    restored = Survey.from_dict(survey.to_dict())
    assert restored.shared_state.read() == state.read()
    assert len(restored.questions) == 1


def test_shared_state_read_side_scopes_history_snapshots_and_records(tmp_path):
    state = SharedState(
        "unused",
        FileStateStore(tmp_path / "state.jsonl"),
        votes=SharedCounterMap(["A", "B"]),
    )
    question = QuestionCheckBox(
        question_name="vote", question_text="Pick", question_options=["A", "B"]
    )
    step = state.votes.tally(question)
    step.execute(StepContext({"vote": ["A"]}, "i2", scope="pair-2"))
    state.close(scope="pair-2")
    step.execute(StepContext({"vote": ["B"]}, "i1", scope="pair-1"))

    assert state.scopes() == ["pair-2", "pair-1"]
    events = state.history()
    assert [(event.scope, event.operation, event.version) for event in events] == [
        ("pair-2", "tally", 1),
        ("pair-2", "__close__", 2),
        ("pair-1", "tally", 1),
    ]
    assert events[0].timestamp.tzinfo is not None
    assert len(state.history(scope="pair-1", target="votes")) == 1

    snapshots = dict(state.snapshots())
    assert snapshots["pair-2"].closed is True
    assert snapshots["pair-1"].closed is False
    assert state.records(target="votes") == [
        {
            "counts": {"A": 1, "B": 0},
            "scope": "pair-2",
            "version": 2,
            "closed": True,
        },
        {
            "counts": {"A": 0, "B": 1},
            "scope": "pair-1",
            "version": 1,
            "closed": False,
        },
    ]


def test_match_pool_assigns_latest_request_at_close(tmp_path):
    state = SharedState(
        "jobs",
        FileStateStore(tmp_path / "jobs.jsonl"),
        pool=SharedMatchPool(["A", "B"]),
    )
    question = QuestionRank(
        question_name="ranking", question_text="Rank", question_options=["A", "B"]
    )
    step = state.pool.collect(question)
    for interview, ranking in [
        ("i1", ["A", "B"]),
        ("i2", ["A", "B"]),
        ("i1", ["B", "A"]),
    ]:
        step.execute(StepContext({"ranking": ranking}, interview))

    assert "assignments" not in state.read().state["pool"]
    state.close()
    snapshot = state.read()
    assert snapshot.closed is True
    assert snapshot.state["pool"]["assignments"] == {"i1": "B", "i2": "A"}
    assert state.read() == snapshot
    with pytest.raises(SharedStateRuntimeError, match="scope 'jobs' is closed"):
        step.execute(StepContext({"ranking": ["A", "B"]}, "i3"))


def test_log_shape_unknown_scope_and_authoring_errors(tmp_path):
    store = FileStateStore(tmp_path / "state.jsonl")
    state = SharedState("poll", store, votes=SharedCounterMap(["A"]))
    question = QuestionCheckBox(
        question_name="vote", question_text="Pick", question_options=["A"]
    )
    state.votes.tally(question).execute(StepContext({"vote": ["A"]}, "respondent"))
    record = json.loads((tmp_path / "state.jsonl").read_text().splitlines()[0])
    assert record["interview"] == "respondent"
    assert store.read("other", state).version == 0

    with pytest.raises(SharedStateAuthoringError, match="must follow"):
        Survey([state.votes.tally(question), question])
    free_text = QuestionFreeText(question_name="text", question_text="Text")
    with pytest.raises(SharedStateAuthoringError, match="checkbox"):
        state.votes.tally(free_text)


def test_ordinary_survey_serialization_is_unchanged():
    question = QuestionFreeText(question_name="q", question_text="Text")
    survey = Survey([question])
    assert "shared_state" not in survey.to_dict(add_edsl_version=False)


def test_shared_writes_add_only_in_interview_causal_dependencies(tmp_path):
    from edsl.runner.service import JobService
    from edsl.runner.storage import InMemoryStorage

    state = SharedState(
        "poll", FileStateStore(tmp_path / "state.jsonl"), votes=SharedCounterMap(["A"])
    )
    write_question = QuestionCheckBox(
        question_name="write", question_text="Pick", question_options=["A"]
    )
    read_one = QuestionFreeText(
        question_name="read_one",
        question_text="{{ shared_state.votes.counts }}",
    )
    read_two = QuestionFreeText(
        question_name="read_two",
        question_text="{{ shared_state.votes.counts }}",
    )
    survey = Survey(
        [write_question, state.votes.tally(write_question), read_one, read_two]
    )

    dag = JobService(InMemoryStorage())._extract_dag(survey)
    assert dag["read_one"] == {"write"}
    assert dag["read_two"] == {"write"}


def test_auction_is_advisory_until_close_and_round_trips(tmp_path):
    state = SharedState(
        "auction",
        FileStateStore(tmp_path / "auction.jsonl"),
        auction=SharedAuction("signed print", increment=10),
    )
    question = QuestionNumerical(
        question_name="bid", question_text="Bid", min_value=0, max_value=100
    )
    survey = Survey([question, state.auction.bid(question)])
    step = survey._shared_state_steps["bid"][0]
    step.execute(StepContext({"bid": 20}, "low"))
    step.execute(StepContext({"bid": 40}, "high"))

    open_snapshot = state.read()
    assert open_snapshot.state["auction"]["highest_bid"] == 40
    assert "winner" not in open_snapshot.state["auction"]
    restored = Survey.from_dict(survey.to_dict())
    assert restored.shared_state.read() == open_snapshot

    state.close()
    assert state.read().state["auction"] | {} == {
        "item": "signed print",
        "highest_bid": 40,
        "bid_count": 2,
        "increment": 10,
        "winner": "high",
        "winning_bid": 40,
    }


def test_message_board_appends_posts_and_replies(tmp_path):
    state = SharedState(
        "family",
        FileStateStore(tmp_path / "board.jsonl"),
        board=SharedMessageBoard(),
    )
    author = QuestionFreeText(question_name="author", question_text="Name")
    reply_to = QuestionFreeText(question_name="reply_to", question_text="Reply target")
    message = QuestionFreeText(question_name="message", question_text="Message")
    survey = Survey(
        [author, reply_to, message, state.board.add(author, message, reply_to)]
    )
    step = survey._shared_state_steps["message"][0]
    step.execute(
        StepContext(
            {"author": "John", "reply_to": "NONE", "message": "Let's sail."}, "i1"
        )
    )
    step.execute(
        StepContext(
            {
                "author": "Robin",
                "reply_to": "John",
                "message": "I'd rather kayak.",
            },
            "i2",
        )
    )

    messages = state.read().state["board"]["messages"]
    assert messages == [
        {"author": "John", "message": "Let's sail.", "reply_to": None},
        {"author": "Robin", "message": "I'd rather kayak.", "reply_to": "John"},
    ]
    assert (
        Survey.from_dict(survey.to_dict()).shared_state.read().state
        == state.read().state
    )
    markdown = state.render_markdown()
    assert "# Shared state: family" in markdown
    assert "### 1. John" in markdown
    assert "### 2. Robin ↪ replying to John" in markdown
    assert "> I'd rather kayak." in markdown


def test_serial_interview_schedule_chains_agent_list_order():
    from edsl import Agent, AgentList, Model
    from edsl.runner.service import JobService
    from edsl.runner.storage import InMemoryStorage

    survey = Survey(
        [QuestionFreeText(question_name="comment", question_text="Comment")]
    )
    agents = AgentList([Agent(name="John"), Agent(name="Robin"), Agent(name="Ada")])
    jobs = survey.by(agents).by(Model("test"))
    _, _, job_data = JobService(InMemoryStorage()).submit_job(
        jobs, interview_schedule="serial"
    )

    interviews = list(job_data["interview_defs"].values())
    tasks = job_data["task_defs"]
    ordered_task_ids = [definition["task_ids"][0] for definition in interviews]
    assert tasks[ordered_task_ids[0]]["depends_on"] == []
    assert tasks[ordered_task_ids[1]]["depends_on"] == [ordered_task_ids[0]]
    assert tasks[ordered_task_ids[2]]["depends_on"] == [ordered_task_ids[1]]


def test_grouped_round_robin_chains_pairs_but_not_groups():
    from edsl import Agent, AgentList, InterviewSchedule, Model
    from edsl.runner.service import JobService
    from edsl.runner.storage import InMemoryStorage

    survey = Survey([QuestionFreeText(question_name="offer", question_text="Offer")])
    agents = AgentList(
        [
            Agent(name="a1", traits={"pair_id": "p1", "turn_order": 0}),
            Agent(name="a2", traits={"pair_id": "p1", "turn_order": 1}),
            Agent(name="a3", traits={"pair_id": "p2", "turn_order": 0}),
            Agent(name="a4", traits={"pair_id": "p2", "turn_order": 1}),
        ]
    )
    schedule = InterviewSchedule.grouped_round_robin("pair_id", "turn_order")
    _, _, job_data = JobService(InMemoryStorage()).submit_job(
        survey.by(agents).by(Model("test")), n=2, interview_schedule=schedule
    )
    names_by_agent_id = {
        agent_id: data["name"] for agent_id, data in job_data["agents"].items()
    }
    interviews = {}
    for definition in job_data["interview_defs"].values():
        key = (names_by_agent_id[definition["agent_id"]], definition["iteration"])
        interviews[key] = definition["task_ids"][0]
    tasks = job_data["task_defs"]

    for first, second in (("a1", "a2"), ("a3", "a4")):
        chain = [
            interviews[(first, 0)],
            interviews[(second, 0)],
            interviews[(first, 1)],
            interviews[(second, 1)],
        ]
        assert tasks[chain[0]]["depends_on"] == []
        for previous, current in zip(chain, chain[1:]):
            assert tasks[current]["depends_on"] == [previous]


def test_templated_scopes_isolate_pairs_and_negotiation_round_trips(tmp_path):
    state = SharedState(
        "{{ agent.pair_id }}",
        FileStateStore(tmp_path / "negotiations.jsonl"),
        negotiation=SharedNegotiation("used sailboat"),
    )
    action = QuestionFreeText(question_name="action", question_text="Action")
    amount = QuestionNumerical(
        question_name="amount", question_text="Amount", min_value=0
    )
    message = QuestionFreeText(question_name="message", question_text="Message")
    survey = Survey(
        [
            action,
            amount,
            message,
            state.negotiation.record(action, amount, message),
        ]
    )
    step = survey._shared_state_steps["message"][0]
    step.execute(
        StepContext(
            {"action": "offer", "amount": 70, "message": "Opening offer"},
            "buyer-p1",
            scope=state.resolve_scope({"pair_id": "p1"}),
            agent_traits={"name": "Buyer 1", "role": "buyer"},
        )
    )
    step.execute(
        StepContext(
            {"action": "offer", "amount": 130, "message": "Counteroffer"},
            "seller-p1",
            scope=state.resolve_scope({"pair_id": "p1"}),
            agent_traits={"name": "Seller 1", "role": "seller"},
        )
    )
    step.execute(
        StepContext(
            {"action": "offer", "amount": 90, "message": "Separate pair"},
            "buyer-p2",
            scope=state.resolve_scope({"pair_id": "p2"}),
            agent_traits={"name": "Buyer 2", "role": "buyer"},
        )
    )

    pair_one = state.read(agent_traits={"pair_id": "p1"}).state["negotiation"]
    pair_two = state.read(agent_traits={"pair_id": "p2"}).state["negotiation"]
    assert [turn["speaker"] for turn in pair_one["turns"]] == [
        "Buyer 1",
        "Seller 1",
    ]
    assert [turn["amount"] for turn in pair_two["turns"]] == [90]
    restored = Survey.from_dict(survey.to_dict()).shared_state
    assert restored.read(agent_traits={"pair_id": "p1"}) == state.read(
        agent_traits={"pair_id": "p1"}
    )


def test_group_stop_condition_skips_only_terminal_pair(tmp_path):
    from edsl import Agent, AgentList, InterviewSchedule, Model
    from edsl.runner.service import JobService
    from edsl.runner.storage import InMemoryStorage

    state = SharedState(
        "{{ agent.pair_id }}",
        FileStateStore(tmp_path / "stops.jsonl"),
        negotiation=SharedNegotiation("boat"),
    )
    action = QuestionFreeText(question_name="action", question_text="Action")
    amount = QuestionNumerical(
        question_name="amount", question_text="Amount", min_value=0
    )
    message = QuestionFreeText(question_name="message", question_text="Message")
    survey = Survey(
        [action, amount, message, state.negotiation.record(action, amount, message)]
    )
    step = survey._shared_state_steps["message"][0]
    step.execute(
        StepContext(
            {"action": "accept", "amount": 90, "message": "Deal"},
            "p1-complete",
            scope="p1",
            agent_traits={"name": "Buyer p1", "role": "buyer"},
        )
    )
    agents = AgentList(
        [
            Agent(
                name="Buyer p1",
                traits={"pair_id": "p1", "turn_order": 0, "role": "buyer"},
            ),
            Agent(
                name="Buyer p2",
                traits={"pair_id": "p2", "turn_order": 0, "role": "buyer"},
            ),
        ]
    )
    schedule = InterviewSchedule.grouped_round_robin(
        "pair_id", "turn_order", stop_when=state.negotiation.is_terminal
    )
    service = JobService(InMemoryStorage())
    job_id, _, job_data = service.submit_job(
        survey.by(agents).by(Model("test")), interview_schedule=schedule
    )
    agent_names = {
        agent_id: data["name"] for agent_id, data in job_data["agents"].items()
    }
    decisions = {}
    for interview_id, interview in job_data["interview_defs"].items():
        task_id = interview["task_ids"][0]
        decisions[agent_names[interview["agent_id"]]] = service.should_skip_task(
            job_id, interview_id, task_id
        )[0]

    assert decisions == {"Buyer p1": True, "Buyer p2": False}


def test_agenda_proposals_and_matrix_votes(tmp_path):
    state = SharedState(
        "meeting",
        FileStateStore(tmp_path / "agenda.jsonl"),
        agenda=SharedAgenda(),
    )
    proposal = QuestionFreeText(question_name="proposal", question_text="Propose")
    proposal_step = state.agenda.propose(proposal)
    for name, title in (("Maya", "Set roadmap"), ("Eli", "Review reliability")):
        proposal_step.execute(
            StepContext(
                {"proposal": title},
                name,
                agent_traits={"name": name},
            )
        )
    vote = QuestionMatrix(
        question_name="votes",
        question_text="Vote",
        question_items=["A1", "A2"],
        question_options=["up", "neutral", "down"],
    )
    survey = Survey([vote, state.agenda.vote(vote)])
    step = survey._shared_state_steps["votes"][0]
    step.execute(
        StepContext(
            {"votes": {"A1": "up", "A2": "down"}},
            "Maya-vote",
            agent_traits={"name": "Maya"},
        )
    )
    step.execute(
        StepContext(
            {"votes": {"A1": "neutral", "A2": "up"}},
            "Eli-vote",
            agent_traits={"name": "Eli"},
        )
    )
    view = state.read().state["agenda"]
    assert [(item["id"], item["score"]) for item in view["proposals"]] == [
        ("A1", 1),
        ("A2", 0),
    ]
    assert view["ballot_count"] == 2
    assert Survey.from_dict(survey.to_dict()).shared_state.read() == state.read()


def test_deferred_acceptance_settles_stable_capacity_match(tmp_path):
    state = SharedState(
        "match",
        FileStateStore(tmp_path / "match.jsonl"),
        market=SharedDeferredAcceptance(
            {"A": 1, "B": 1},
            {"A": ["s2", "s1"], "B": ["s1", "s2"]},
        ),
    )
    ranking = QuestionRank(
        question_name="ranking",
        question_text="Rank",
        question_options=["A", "B"],
    )
    step = state.market.collect(ranking)
    step.execute(
        StepContext({"ranking": ["A", "B"]}, "i1", agent_traits={"name": "s1"})
    )
    step.execute(
        StepContext({"ranking": ["A", "B"]}, "i2", agent_traits={"name": "s2"})
    )

    state.close()

    assert state.read().state["market"]["matches"] == {"s2": "A", "s1": "B"}
    assert SharedState.from_dict(state.to_dict()).read() == state.read()


def test_generic_log_resolves_answers_and_agent_fields(tmp_path):
    state = SharedState(
        "game", FileStateStore(tmp_path / "log.jsonl"), events=SharedLog()
    )
    amount = QuestionNumerical(
        question_name="amount", question_text="Amount", min_value=0
    )
    survey = Survey(
        [amount, state.events.append(actor="{{ agent.name }}", amount=amount)]
    )
    survey._shared_state_steps["amount"][0].execute(
        StepContext({"amount": 12}, "i1", agent_traits={"name": "Avery"})
    )
    assert state.read().state["events"] == {
        "entries": [{"actor": "Avery", "amount": 12}],
        "count": 1,
        "tail": [{"actor": "Avery", "amount": 12}],
    }
    assert Survey.from_dict(survey.to_dict()).shared_state.read() == state.read()


def test_filtered_log_view_is_agent_relative(tmp_path):
    state = SharedState(
        "network",
        FileStateStore(tmp_path / "network.jsonl"),
        messages=SharedLog(visible_to="recipients"),
    )
    append = state.messages.append(
        sender="Alice", recipients=["Ben"], message="Private edge message"
    )
    append.execute(StepContext({}, "i1"))

    assert state.read(agent_traits={"name": "Ben"}).state["messages"]["count"] == 1
    assert state.read(agent_traits={"name": "Alice"}).state["messages"]["count"] == 1
    assert state.read(agent_traits={"name": "Cara"}).state["messages"]["count"] == 0
    assert state.read().state["messages"]["count"] == 1


def test_versioned_reads_replay_exact_watermark(tmp_path):
    state = SharedState(
        "events", FileStateStore(tmp_path / "versions.jsonl"), events=SharedLog()
    )
    state.events.append(value="first").execute(StepContext({}, "i1"))
    state.events.append(value="second").execute(StepContext({}, "i2"))

    assert state.read(at_version=0).state["events"]["entries"] == []
    assert state.read(at_version=1).state["events"]["entries"] == [{"value": "first"}]
    assert state.read(at_version=2).state["events"]["count"] == 2


def test_round_schedule_adds_barrier_between_concurrent_rounds():
    from edsl import Agent, AgentList, InterviewSchedule, Model
    from edsl.runner.service import JobService
    from edsl.runner.storage import InMemoryStorage

    survey = Survey([QuestionFreeText(question_name="move", question_text="Move")])
    agents = AgentList([Agent(name="a"), Agent(name="b")])
    schedule = InterviewSchedule.rounds(count=2)
    _, _, job_data = JobService(InMemoryStorage()).submit_job(
        survey.by(agents).by(Model("test")), n=2, interview_schedule=schedule
    )
    interviews = list(job_data["interview_defs"].values())
    tasks = job_data["task_defs"]
    by_round = {}
    for interview in interviews:
        by_round.setdefault(interview["iteration"], []).append(interview["task_ids"][0])

    assert all(tasks[task_id]["depends_on"] == [] for task_id in by_round[0])
    for task_id in by_round[1]:
        assert set(tasks[task_id]["depends_on"]) == set(by_round[0])


def test_serial_round_schedule_can_rotate_agent_order():
    from edsl import Agent, AgentList, InterviewSchedule, Model
    from edsl.runner.service import JobService
    from edsl.runner.storage import InMemoryStorage

    survey = Survey([QuestionFreeText(question_name="move", question_text="Move")])
    agents = AgentList(
        [Agent(name=name, traits={"seat": seat}) for seat, name in enumerate("abc")]
    )
    schedule = InterviewSchedule.rounds(
        count=3,
        within_round="serial",
        state_visibility="live",
        order_by="seat",
        round_order="rotate",
    )
    _, _, job_data = JobService(InMemoryStorage()).submit_job(
        survey.by(agents).by(Model("test")), n=3, interview_schedule=schedule
    )
    names = {agent_id: data["name"] for agent_id, data in job_data["agents"].items()}
    interviews = list(job_data["interview_defs"].values())
    tasks = job_data["task_defs"]
    for round_number, expected in enumerate(("abc", "bca", "cab")):
        round_tasks = {
            names[item["agent_id"]]: item["task_ids"][0]
            for item in interviews
            if item["iteration"] == round_number
        }
        all_round_tasks = set(round_tasks.values())
        assert not (
            set(tasks[round_tasks[expected[0]]]["depends_on"]) & all_round_tasks
        )
        for previous, current in zip(expected, expected[1:]):
            assert round_tasks[previous] in tasks[round_tasks[current]]["depends_on"]


def test_snapshot_round_reuses_watermark_for_every_agent(tmp_path):
    from edsl import Agent, AgentList, InterviewSchedule, Model
    from edsl.runner.service import JobService
    from edsl.runner.storage import InMemoryStorage

    state = SharedState(
        "game", FileStateStore(tmp_path / "watermarks.jsonl"), events=SharedLog()
    )
    question = QuestionFreeText(question_name="move", question_text="Move")
    survey = Survey([question, state.events.append(value=question)])
    agents = AgentList([Agent(name="a"), Agent(name="b")])
    schedule = InterviewSchedule.rounds(count=2)
    service = JobService(InMemoryStorage())
    job_id, _, job_data = service.submit_job(
        survey.by(agents).by(Model("test")), n=2, interview_schedule=schedule
    )
    definitions = [
        service.tasks.get_definition(job_id, interview_id, data["task_ids"][0])
        for interview_id, data in job_data["interview_defs"].items()
    ]
    round_zero = [definition for definition in definitions if definition.iteration == 0]
    round_one = [definition for definition in definitions if definition.iteration == 1]
    traits = {"name": "a"}

    assert service.shared_state_read_version(job_id, round_zero[0], state, traits) == 0
    state.events.append(value="round-zero-write").execute(StepContext({}, "i1"))
    assert (
        service.shared_state_read_version(job_id, round_zero[1], state, {"name": "b"})
        == 0
    )
    assert service.shared_state_read_version(job_id, round_one[0], state, traits) == 1


def test_before_question_work_claims_are_atomic_and_idempotent(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    items = [{"id": f"task-{index}"} for index in range(5)]
    state = SharedState(
        "reviews",
        FileStateStore(tmp_path / "claims.jsonl"),
        work=SharedWorkPool(items),
    )
    review = QuestionFreeText(question_name="review", question_text="Review")
    action = state.work.claim_before(review)
    survey = Survey([action, review, state.work.complete(review)])
    restored = Survey.from_dict(survey.to_dict())
    assert len(restored.questions) == 1
    assert len(restored._before_question_actions["review"]) == 1

    def claim(index):
        context = StepContext(
            {},
            f"interview-{index}",
            agent_traits={"name": f"reviewer-{index}"},
        )
        action.execute(context)
        action.execute(context)

    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(claim, range(10)))

    snapshot = state.read().state["work"]
    claimed = [item for item in snapshot["claims"].values() if item is not None]
    assert len(claimed) == 5
    assert len({item["id"] for item in claimed}) == 5
    assert state.read().version == 10


def test_binary_market_prices_cash_and_settlement_round_trip(tmp_path):
    state = SharedState(
        "market",
        FileStateStore(tmp_path / "market.jsonl"),
        market=SharedBinaryMarket("Event occurs", liquidity=20, initial_cash=50),
    )
    action = QuestionMultipleChoice(
        question_name="action",
        question_text="Trade",
        question_options=["buy_yes", "buy_no", "hold"],
    )
    quantity = QuestionNumerical(
        question_name="quantity", question_text="Quantity", min_value=0, max_value=10
    )
    survey = Survey([action, quantity, state.market.trade(action, quantity)])
    step = survey._shared_state_steps["quantity"][0]
    step.execute(
        StepContext(
            {"action": "buy_yes", "quantity": 10},
            "alice-trade",
            agent_traits={"name": "Alice"},
            run_context={"round": 1},
        )
    )
    after_yes = state.read().state["market"]
    assert after_yes["yes_price"] > 0.5
    assert after_yes["portfolios"]["Alice"]["cash"] < 50

    step.execute(
        StepContext(
            {"action": "buy_no", "quantity": 10},
            "bob-trade",
            agent_traits={"name": "Bob"},
            run_context={"round": 1},
        )
    )
    assert state.read().state["market"]["yes_price"] == pytest.approx(0.5)
    state.market.settle(True).execute(StepContext({}, "resolution"))
    settled = state.read().state["market"]
    assert settled["outcome"] is True
    assert settled["settled_wealth"]["Alice"] > settled["settled_wealth"]["Bob"]
    assert Survey.from_dict(survey.to_dict()).shared_state.read() == state.read()


def test_coalition_moves_are_atomic_exclusive_and_round_trip(tmp_path):
    state = SharedState(
        "coalitions",
        FileStateStore(tmp_path / "coalitions.jsonl"),
        pool=SharedCoalitionPool(
            {
                "A": {"platform": "alpha", "capacity": 1},
                "B": {"platform": "beta", "capacity": 1},
            }
        ),
    )
    choice = QuestionMultipleChoice(
        question_name="choice",
        question_text="Choose",
        question_options=["A", "B"],
    )
    survey = Survey([choice, state.pool.request(choice)])
    step = survey._shared_state_steps["choice"][0]

    def request(member, coalition, round_number):
        step.execute(
            StepContext(
                {"choice": coalition},
                f"{member}-{round_number}",
                agent_traits={"name": member},
                run_context={"round": round_number},
            )
        )

    request("Alice", "A", 1)
    request("Bob", "A", 1)
    rejected = state.read(agent_traits={"name": "Bob"}).state["pool"]
    assert rejected["your_membership"] is None
    assert rejected["your_last_request"]["reason"] == "coalition_full"

    request("Alice", "B", 2)
    request("Bob", "A", 2)
    view = state.read().state["pool"]
    assert view["coalitions"]["A"]["members"] == ["Bob"]
    assert view["coalitions"]["B"]["members"] == ["Alice"]
    assert Survey.from_dict(survey.to_dict()).shared_state.read() == state.read()


def test_private_signals_reveal_by_round_and_viewer(tmp_path):
    state = SharedState(
        "signals",
        FileStateStore(tmp_path / "signals.jsonl"),
        news=SharedSignalSchedule({"Alice": ["a1", "a2"], "Bob": ["b1", "b2"]}),
    )
    action = QuestionFreeText(question_name="act", question_text="Act")
    survey = Survey([state.news.reveal_before(action), action])
    reveal = survey._before_question_actions["act"][0]
    reveal.execute(
        StepContext(
            {},
            "alice-round-1",
            agent_traits={"name": "Alice"},
            run_context={"round": 1},
        )
    )
    alice = state.read(agent_traits={"name": "Alice"}).state["news"]
    bob = state.read(agent_traits={"name": "Bob"}).state["news"]
    assert alice["your_signal"] == "a1"
    assert bob["your_signal"] is None
    assert alice["release_count"] == 1
    assert Survey.from_dict(survey.to_dict()).shared_state.read() == state.read()


def test_budget_partially_fills_final_atomic_request(tmp_path):
    state = SharedState(
        "budget",
        FileStateStore(tmp_path / "budget.jsonl"),
        pool=SharedBudgetPool(10, {"A": "alpha", "B": "beta"}),
    )
    project = QuestionMultipleChoice(
        question_name="project", question_text="Project", question_options=["A", "B"]
    )
    amount = QuestionNumerical(
        question_name="amount", question_text="Amount", min_value=0, max_value=10
    )
    survey = Survey([project, amount, state.pool.fund(project, amount)])
    step = survey._shared_state_steps["amount"][0]
    for name, answer in (
        ("Alice", {"project": "A", "amount": 7}),
        ("Bob", {"project": "B", "amount": 8}),
    ):
        step.execute(
            StepContext(
                answer,
                name,
                agent_traits={"name": name},
                run_context={"round": 1},
            )
        )
    view = state.read().state["pool"]
    assert view["remaining"] == 0
    assert view["projects"]["A"]["funded"] == 7
    assert view["projects"]["B"]["funded"] == 3
    assert view["recent_allocations"][-1]["partial"] is True
    assert state.pool.exhausted(view)


def test_sealed_money_game_hides_choices_until_close(tmp_path):
    state = SharedState(
        "pair",
        FileStateStore(tmp_path / "money-game.jsonl"),
        game=SharedMoneyRequestGame(),
    )
    request = QuestionNumerical(
        question_name="request", question_text="Request", min_value=11, max_value=20
    )
    step = Survey([request, state.game.submit(request)])._shared_state_steps["request"][
        0
    ]
    for player, amount in (("A", 20), ("B", 19)):
        step.execute(
            StepContext({"request": amount}, player, agent_traits={"name": player})
        )
    open_view = state.read(agent_traits={"name": "A"}).state["game"]
    assert open_view["submission_count"] == 2
    assert "choices" not in open_view
    assert state.game.complete(open_view)
    state.close()
    closed = state.read().state["game"]
    assert closed["choices"] == {"A": 20, "B": 19}
    assert closed["payoffs"] == {"A": 20.0, "B": 39.0}


def test_agent_trait_skip_rules_author_and_round_trip():
    proposer = QuestionFreeText(question_name="offer", question_text="Offer")
    responder = QuestionFreeText(question_name="response", question_text="Respond")
    survey = Survey([proposer, responder])
    survey.add_skip_rule("offer", "'{{ agent.role }}' != 'proposer'")
    survey.add_skip_rule("response", "'{{ agent.role }}' != 'responder'")
    restored = Survey.from_dict(survey.to_dict())
    assert len(restored.rule_collection.non_default_rules) == 2


def test_after_round_reveal_declares_snapshot_visibility():
    schedule = InterviewSchedule.rounds(count=1, reveal="after_round")
    assert schedule.reveal == "after_round"
    assert schedule.state_visibility == "snapshot"
