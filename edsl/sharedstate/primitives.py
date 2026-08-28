from abc import ABC, abstractmethod
from collections import Counter
from statistics import median
from typing import Any
import math

from .exceptions import SharedStateAuthoringError
from .refs import AnswerRef
from .steps import BeforeQuestionAction, WriteStep


class SharedPrimitive(ABC):
    name: str
    parent: Any

    @abstractmethod
    def initial(self) -> Any: ...

    @abstractmethod
    def apply(self, state: Any, op: str, args: dict, interview_id: str) -> Any: ...

    def at_close(self, state: Any) -> Any:
        return state

    @abstractmethod
    def view(self, state: Any, closed: bool, context=None) -> dict: ...

    @abstractmethod
    def to_dict(self) -> dict: ...

    def render_markdown(self, view: dict) -> str:
        import json

        return f"```json\n{json.dumps(view, indent=2)}\n```"


class SharedLog(SharedPrimitive):
    """General append-only structured event log."""

    def __init__(self, visible_to: str | None = None, viewer_trait: str = "name"):
        self.visible_to = visible_to
        self.viewer_trait = viewer_trait

    @staticmethod
    def _value(value):
        return (
            AnswerRef(value.question_name) if hasattr(value, "question_name") else value
        )

    def append(self, **fields) -> WriteStep:
        if not fields:
            raise SharedStateAuthoringError("log append requires at least one field")
        return WriteStep(
            self,
            "append",
            {key: self._value(value) for key, value in fields.items()},
        )

    def initial(self):
        return {"entries": []}

    def apply(self, state, op, args, interview_id):
        if op != "append":
            raise SharedStateAuthoringError(f"unknown operation '{op}' for SharedLog")
        state["entries"].append(dict(args) | {"interview": interview_id})
        return state

    def view(self, state, closed, context=None):
        entries = state["entries"]
        if self.visible_to and context:
            viewer = context.get(self.viewer_trait)
            entries = [
                entry
                for entry in entries
                if viewer in entry.get(self.visible_to, [])
                or entry.get("sender") == viewer
            ]
        return {
            "entries": [
                {key: value for key, value in entry.items() if key != "interview"}
                for entry in entries
            ],
            "count": len(entries),
            "tail": [
                {key: value for key, value in entry.items() if key != "interview"}
                for entry in entries[-10:]
            ],
        }

    def to_dict(self):
        return {
            "type": "log",
            "visible_to": self.visible_to,
            "viewer_trait": self.viewer_trait,
        }


class SharedWorkPool(SharedPrimitive):
    """Atomically claimable structured work items."""

    def __init__(self, items):
        self.items = [dict(item) for item in items]
        item_ids = [item.get("id") for item in self.items]
        if any(item_id is None for item_id in item_ids) or len(set(item_ids)) != len(
            item_ids
        ):
            raise SharedStateAuthoringError(
                "work-pool items require unique non-null 'id' fields"
            )

    def claim_before(
        self, question, *, claimant="{{ agent.name }}"
    ) -> BeforeQuestionAction:
        return BeforeQuestionAction(
            self,
            "claim",
            {"claimant": claimant},
            question_name=question.question_name,
        )

    def complete(self, question, *, claimant="{{ agent.name }}") -> WriteStep:
        return WriteStep(
            self,
            "complete",
            {
                "claimant": claimant,
                "result": AnswerRef(question.question_name),
            },
        )

    def initial(self):
        return {
            "available": [dict(item) for item in self.items],
            "claims": {},
            "completed": {},
        }

    def apply(self, state, op, args, interview_id):
        if op not in {"claim", "complete"}:
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedWorkPool"
            )
        claimant = str(args["claimant"])
        if op == "claim":
            if claimant not in state["claims"]:
                state["claims"][claimant] = (
                    state["available"].pop(0) if state["available"] else None
                )
        elif claimant not in state["claims"] or state["claims"][claimant] is None:
            raise SharedStateAuthoringError(
                f"claimant '{claimant}' has no work item to complete"
            )
        else:
            state["completed"][claimant] = {
                "item": state["claims"][claimant],
                "result": args["result"],
            }
        return state

    def view(self, state, closed, context=None):
        viewer = (context or {}).get("name")
        return {
            "available_count": len(state["available"]),
            "claimed": state["claims"].get(viewer) if viewer else None,
            "claims": dict(state["claims"]) if not context else None,
            "completed": dict(state["completed"]) if not context else None,
        }

    def to_dict(self):
        return {"type": "work_pool", "items": self.items}


class SharedSignalSchedule(SharedPrimitive):
    """Reveal configured private signals to one participant just in time."""

    def __init__(self, signals: dict[str, list]):
        if not signals or any(
            not isinstance(items, list) for items in signals.values()
        ):
            raise SharedStateAuthoringError(
                "signal schedule requires a non-empty mapping of participant lists"
            )
        self.signals = {str(name): list(items) for name, items in signals.items()}

    def reveal_before(
        self,
        question,
        *,
        participant="{{ agent.name }}",
        round_number="{{ run.round }}",
    ) -> BeforeQuestionAction:
        return BeforeQuestionAction(
            self,
            "reveal",
            {"participant": participant, "round": round_number},
            question_name=question.question_name,
        )

    def initial(self):
        return {"revealed": {}, "events": []}

    def apply(self, state, op, args, interview_id):
        if op != "reveal":
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedSignalSchedule"
            )
        participant = str(args["participant"])
        round_number = int(args["round"])
        if participant not in self.signals:
            raise SharedStateAuthoringError(
                f"no private signal schedule for '{participant}'"
            )
        if round_number < 1 or round_number > len(self.signals[participant]):
            raise SharedStateAuthoringError(
                f"no signal for '{participant}' in round {round_number}"
            )
        history = state["revealed"].setdefault(participant, [])
        if not any(item["round"] == round_number for item in history):
            item = {
                "round": round_number,
                "signal": self.signals[participant][round_number - 1],
            }
            history.append(item)
            state["events"].append({"participant": participant, "round": round_number})
        return state

    def view(self, state, closed, context=None):
        viewer = (context or {}).get("name")
        history = list(state["revealed"].get(viewer, [])) if viewer else []
        return {
            "your_signal": history[-1]["signal"] if history else None,
            "your_signal_history": history,
            "release_count": len(state["events"]),
            "released_by_round": dict(
                Counter(item["round"] for item in state["events"])
            ),
        }

    def to_dict(self):
        return {"type": "signal_schedule", "signals": self.signals}


class SharedBinaryMarket(SharedPrimitive):
    """Atomic LMSR market for one mutually exclusive YES/NO contract."""

    ACTIONS = {"buy_yes", "buy_no", "hold"}

    def __init__(self, contract: str, liquidity: float = 50, initial_cash: float = 100):
        if liquidity <= 0 or initial_cash <= 0:
            raise SharedStateAuthoringError(
                "market liquidity and initial cash must be positive"
            )
        self.contract = contract
        self.liquidity = float(liquidity)
        self.initial_cash = float(initial_cash)

    def trade(
        self,
        action_question,
        quantity_question,
        *,
        trader="{{ agent.name }}",
        round_number="{{ run.round }}",
    ) -> WriteStep:
        if getattr(action_question, "question_type", None) != "multiple_choice":
            raise SharedStateAuthoringError(
                "binary-market action expects a multiple-choice question"
            )
        if set(action_question.question_options) != self.ACTIONS:
            raise SharedStateAuthoringError(
                "binary-market actions must be buy_yes, buy_no, and hold"
            )
        if getattr(quantity_question, "question_type", None) != "numerical":
            raise SharedStateAuthoringError(
                "binary-market quantity expects a numerical question"
            )
        return WriteStep(
            self,
            "trade",
            {
                "trader": trader,
                "round": round_number,
                "action": AnswerRef(action_question.question_name),
                "quantity": AnswerRef(quantity_question.question_name),
            },
        )

    def settle(self, outcome: bool) -> WriteStep:
        return WriteStep(self, "settle", {"outcome": bool(outcome)})

    def initial(self):
        return {
            "q_yes": 0.0,
            "q_no": 0.0,
            "portfolios": {},
            "trades": [],
            "outcome": None,
        }

    def _cost(self, q_yes, q_no):
        yes = q_yes / self.liquidity
        no = q_no / self.liquidity
        maximum = max(yes, no)
        return self.liquidity * (
            maximum + math.log(math.exp(yes - maximum) + math.exp(no - maximum))
        )

    def _prices(self, state):
        difference = max(
            -700, min(700, (state["q_no"] - state["q_yes"]) / self.liquidity)
        )
        yes = 1 / (1 + math.exp(difference))
        return yes, 1 - yes

    def apply(self, state, op, args, interview_id):
        if op == "settle":
            if state["outcome"] is not None:
                if state["outcome"] != bool(args["outcome"]):
                    raise SharedStateAuthoringError(
                        "a settled market cannot be resolved again differently"
                    )
                return state
            state["outcome"] = bool(args["outcome"])
            return state
        if op != "trade":
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedBinaryMarket"
            )
        if state["outcome"] is not None:
            raise SharedStateAuthoringError("cannot trade after market settlement")
        trader = str(args["trader"])
        action = str(args["action"]).lower()
        quantity = args["quantity"]
        if action not in self.ACTIONS:
            raise SharedStateAuthoringError(f"invalid market action '{action}'")
        if (
            isinstance(quantity, bool)
            or not isinstance(quantity, (int, float))
            or quantity < 0
        ):
            raise SharedStateAuthoringError(
                "market trade quantity must be a non-negative number"
            )
        portfolio = state["portfolios"].setdefault(
            trader,
            {"cash": self.initial_cash, "yes_shares": 0.0, "no_shares": 0.0},
        )
        cost = 0.0
        if action != "hold" and quantity > 0:
            old_cost = self._cost(state["q_yes"], state["q_no"])
            next_yes = state["q_yes"] + (quantity if action == "buy_yes" else 0)
            next_no = state["q_no"] + (quantity if action == "buy_no" else 0)
            cost = self._cost(next_yes, next_no) - old_cost
            if cost > portfolio["cash"] + 1e-9:
                raise SharedStateAuthoringError(
                    f"trade costs {cost:.2f}, exceeding {trader}'s available cash "
                    f"of {portfolio['cash']:.2f}"
                )
            state["q_yes"], state["q_no"] = next_yes, next_no
            portfolio["cash"] -= cost
            share_key = "yes_shares" if action == "buy_yes" else "no_shares"
            portfolio[share_key] += quantity
        yes_price, no_price = self._prices(state)
        state["trades"].append(
            {
                "trader": trader,
                "round": int(args["round"]),
                "action": action,
                "quantity": quantity,
                "cost": cost,
                "yes_price_after": yes_price,
                "no_price_after": no_price,
            }
        )
        return state

    def view(self, state, closed, context=None):
        yes_price, no_price = self._prices(state)
        viewer = (context or {}).get("name")
        result = {
            "contract": self.contract,
            "yes_price": yes_price,
            "no_price": no_price,
            "trade_count": len(state["trades"]),
            "recent_trades": state["trades"][-10:],
            "your_portfolio": state["portfolios"].get(viewer) if viewer else None,
            "portfolios": dict(state["portfolios"]) if not context else None,
            "outcome": state["outcome"],
        }
        if state["outcome"] is not None:
            result["settled_wealth"] = {
                trader: portfolio["cash"]
                + portfolio["yes_shares"] * int(state["outcome"])
                + portfolio["no_shares"] * int(not state["outcome"])
                for trader, portfolio in state["portfolios"].items()
            }
        return result

    def to_dict(self):
        return {
            "type": "binary_market",
            "contract": self.contract,
            "liquidity": self.liquidity,
            "initial_cash": self.initial_cash,
        }

    def render_markdown(self, view):
        lines = [
            f"**Contract:** {view['contract']}",
            "",
            f"**YES price:** {view['yes_price']:.3f}  ",
            f"**NO price:** {view['no_price']:.3f}  ",
            f"**Trades:** {view['trade_count']}",
        ]
        if view["outcome"] is not None:
            lines.extend(
                [
                    "",
                    f"**Resolved:** {'YES' if view['outcome'] else 'NO'}",
                    "",
                    "| Trader | Final wealth |",
                    "|---|---:|",
                ]
            )
            lines.extend(
                f"| {trader} | ${wealth:.2f} |"
                for trader, wealth in sorted(
                    view["settled_wealth"].items(), key=lambda item: -item[1]
                )
            )
        return "\n".join(lines)


class SharedUltimatumGame(SharedPrimitive):
    """One proposer offer followed by one responder decision."""

    def __init__(self, stake: float = 100):
        if stake <= 0:
            raise SharedStateAuthoringError("ultimatum stake must be positive")
        self.stake = float(stake)

    def act(
        self,
        offer_question,
        decision_question,
        *,
        player="{{ agent.name }}",
        role="{{ agent.role }}",
    ):
        return WriteStep(
            self,
            "act",
            {
                "player": player,
                "role": role,
                "offer": AnswerRef(offer_question.question_name),
                "decision": AnswerRef(decision_question.question_name),
            },
        )

    def offer(self, question, *, player="{{ agent.name }}") -> WriteStep:
        return WriteStep(
            self,
            "offer",
            {
                "player": player,
                "role": "proposer",
                "offer": AnswerRef(question.question_name),
            },
        )

    def respond(self, question, *, player="{{ agent.name }}") -> WriteStep:
        return WriteStep(
            self,
            "respond",
            {
                "player": player,
                "role": "responder",
                "decision": AnswerRef(question.question_name),
            },
        )

    def initial(self):
        return {"offer": None, "proposer": None, "responder": None, "accepted": None}

    def apply(self, state, op, args, interview_id):
        if op not in {"act", "offer", "respond"}:
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedUltimatumGame"
            )
        role = str(args["role"])
        if role == "proposer":
            offer = args["offer"]
            if (
                isinstance(offer, bool)
                or not isinstance(offer, (int, float))
                or not 0 <= offer <= self.stake
            ):
                raise SharedStateAuthoringError(
                    f"ultimatum offer must be between 0 and {self.stake:g}"
                )
            if state["offer"] is not None:
                raise SharedStateAuthoringError("ultimatum proposer already acted")
            state["offer"], state["proposer"] = float(offer), str(args["player"])
        elif role == "responder":
            if state["offer"] is None:
                raise SharedStateAuthoringError("responder cannot act before an offer")
            decision = str(args["decision"]).lower()
            if decision not in {"accept", "reject"}:
                raise SharedStateAuthoringError("decision must be accept or reject")
            state["responder"] = str(args["player"])
            state["accepted"] = decision == "accept"
        else:
            raise SharedStateAuthoringError(f"unknown ultimatum role '{role}'")
        return state

    def terminal(self, state):
        return state["accepted"] is not None

    def view(self, state, closed, context=None):
        payoffs = None
        if state["accepted"] is not None:
            payoffs = {
                state["proposer"]: self.stake - state["offer"]
                if state["accepted"]
                else 0,
                state["responder"]: state["offer"] if state["accepted"] else 0,
            }
        return dict(state) | {"stake": self.stake, "payoffs": payoffs}

    def to_dict(self):
        return {"type": "ultimatum_game", "stake": self.stake}


class SharedMoneyRequestGame(SharedPrimitive):
    """Sealed two-player 11–20 request game with a lower-request bonus."""

    def __init__(self, minimum=11, maximum=20, bonus=20):
        if minimum >= maximum or bonus <= 0:
            raise SharedStateAuthoringError("invalid money-request game parameters")
        self.minimum, self.maximum, self.bonus = (
            int(minimum),
            int(maximum),
            float(bonus),
        )

    def submit(self, question, *, player="{{ agent.name }}") -> WriteStep:
        if getattr(question, "question_type", None) != "numerical":
            raise SharedStateAuthoringError(
                "money request expects a numerical question"
            )
        return WriteStep(
            self,
            "submit",
            {"player": player, "request": AnswerRef(question.question_name)},
        )

    def initial(self):
        return {"choices": {}}

    def apply(self, state, op, args, interview_id):
        if op != "submit":
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedMoneyRequestGame"
            )
        request = args["request"]
        if (
            isinstance(request, bool)
            or not isinstance(request, (int, float))
            or int(request) != request
        ):
            raise SharedStateAuthoringError("money request must be an integer")
        request = int(request)
        if not self.minimum <= request <= self.maximum:
            raise SharedStateAuthoringError(
                f"money request must be between {self.minimum} and {self.maximum}"
            )
        state["choices"][str(args["player"])] = request
        return state

    def at_close(self, state):
        choices = state["choices"]
        if len(choices) != 2:
            raise SharedStateAuthoringError(
                f"money-request game requires exactly two choices; received {len(choices)}"
            )
        players = list(choices)
        payoffs = {player: float(choices[player]) for player in players}
        first, second = players
        if choices[first] == choices[second] - 1:
            payoffs[first] += self.bonus
        elif choices[second] == choices[first] - 1:
            payoffs[second] += self.bonus
        state["payoffs"] = payoffs
        return state

    def complete(self, state):
        return state["submission_count"] == 2

    def view(self, state, closed, context=None):
        viewer = (context or {}).get("name")
        result = {
            "range": [self.minimum, self.maximum],
            "bonus": self.bonus,
            "submission_count": len(state["choices"]),
            "your_request": state["choices"].get(viewer) if viewer else None,
        }
        if closed:
            result.update(
                choices=dict(state["choices"]), payoffs=dict(state["payoffs"])
            )
        return result

    def to_dict(self):
        return {
            "type": "money_request_game",
            "minimum": self.minimum,
            "maximum": self.maximum,
            "bonus": self.bonus,
        }


class SharedMatrixGame(SharedPrimitive):
    """Sealed two-player normal-form game with deterministic settlement."""

    def __init__(self, actions, payoffs):
        self.actions = list(actions)
        self.payoffs = {str(key): list(value) for key, value in payoffs.items()}
        expected = {
            f"{left}|{right}" for left in self.actions for right in self.actions
        }
        if set(self.payoffs) != expected or any(
            len(value) != 2 for value in self.payoffs.values()
        ):
            raise SharedStateAuthoringError(
                "matrix game requires a two-player payoff pair for every action profile"
            )

    def submit(self, question, *, player="{{ agent.name }}", seat="{{ agent.seat }}"):
        if set(question.question_options) != set(self.actions):
            raise SharedStateAuthoringError(
                "matrix-game question options must match actions"
            )
        return WriteStep(
            self,
            "submit",
            {
                "player": player,
                "seat": seat,
                "action": AnswerRef(question.question_name),
            },
        )

    def initial(self):
        return {"choices": {}, "players": {}}

    def apply(self, state, op, args, interview_id):
        if op != "submit":
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedMatrixGame"
            )
        seat = int(args["seat"])
        if seat not in {0, 1}:
            raise SharedStateAuthoringError("matrix-game seat must be 0 or 1")
        action = str(args["action"])
        if action not in self.actions:
            raise SharedStateAuthoringError(f"unknown matrix-game action '{action}'")
        state["choices"][str(seat)] = action
        state["players"][str(seat)] = str(args["player"])
        return state

    def complete(self, view):
        return view["submission_count"] == 2

    def at_close(self, state):
        profile = f"{state['choices']['0']}|{state['choices']['1']}"
        values = self.payoffs[profile]
        state["payoffs"] = {
            state["players"]["0"]: values[0],
            state["players"]["1"]: values[1],
        }
        return state

    def view(self, state, closed, context=None):
        result = {
            "actions": self.actions,
            "submission_count": len(state["choices"]),
        }
        if closed:
            result.update(
                choices=dict(state["choices"]), payoffs=dict(state["payoffs"])
            )
        return result

    def to_dict(self):
        return {"type": "matrix_game", "actions": self.actions, "payoffs": self.payoffs}


class SharedRepeatedMatrixGame(SharedPrimitive):
    """Round-indexed sealed normal-form game with revealed completed history."""

    def __init__(self, actions, payoffs, rounds):
        self.actions, self.payoffs, self.rounds = (
            list(actions),
            {str(k): list(v) for k, v in payoffs.items()},
            int(rounds),
        )

    def submit(
        self,
        question,
        *,
        player="{{ agent.name }}",
        seat="{{ agent.seat }}",
        round_number="{{ run.round }}",
    ):
        return WriteStep(
            self,
            "submit",
            {
                "player": player,
                "seat": seat,
                "round": round_number,
                "action": AnswerRef(question.question_name),
            },
        )

    def initial(self):
        return {"rounds": {}, "players": {}}

    def apply(self, state, op, args, interview_id):
        if op != "submit" or str(args["action"]) not in self.actions:
            raise SharedStateAuthoringError("invalid repeated-matrix action")
        seat, round_number = str(int(args["seat"])), int(args["round"])
        if seat not in {"0", "1"} or not 1 <= round_number <= self.rounds:
            raise SharedStateAuthoringError("invalid repeated-matrix seat or round")
        state["players"][seat] = str(args["player"])
        state["rounds"].setdefault(str(round_number), {})[seat] = str(args["action"])
        return state

    def _history(self, state):
        history, cumulative = [], {player: 0 for player in state["players"].values()}
        for round_number in range(1, self.rounds + 1):
            choices = state["rounds"].get(str(round_number), {})
            if len(choices) != 2:
                continue
            values = self.payoffs[f"{choices['0']}|{choices['1']}"]
            payoffs = {
                state["players"]["0"]: values[0],
                state["players"]["1"]: values[1],
            }
            for player, value in payoffs.items():
                cumulative[player] += value
            history.append(
                {"round": round_number, "choices": dict(choices), "payoffs": payoffs}
            )
        return history, cumulative

    def complete(self, view):
        return len(view["history"]) == self.rounds

    def view(self, state, closed, context=None):
        history, cumulative = self._history(state)
        return {
            "actions": self.actions,
            "round_count": self.rounds,
            "history": history,
            "cumulative_payoffs": cumulative,
            "complete": len(history) == self.rounds,
        }

    def to_dict(self):
        return {
            "type": "repeated_matrix_game",
            "actions": self.actions,
            "payoffs": self.payoffs,
            "rounds": self.rounds,
        }


class SharedDictatorGame(SharedPrimitive):
    """A unilateral allocation of a fixed endowment."""

    def __init__(self, endowment=100):
        if endowment <= 0:
            raise SharedStateAuthoringError("dictator endowment must be positive")
        self.endowment = float(endowment)

    def allocate(
        self,
        question,
        *,
        dictator="{{ agent.name }}",
        recipient="{{ agent.recipient }}",
    ):
        return WriteStep(
            self,
            "allocate",
            {
                "dictator": dictator,
                "recipient": recipient,
                "transfer": AnswerRef(question.question_name),
            },
        )

    def initial(self):
        return {"dictator": None, "recipient": None, "transfer": None}

    def apply(self, state, op, args, interview_id):
        transfer = args.get("transfer")
        if (
            op != "allocate"
            or isinstance(transfer, bool)
            or not isinstance(transfer, (int, float))
            or not 0 <= transfer <= self.endowment
        ):
            raise SharedStateAuthoringError("invalid dictator allocation")
        if state["transfer"] is not None:
            raise SharedStateAuthoringError("dictator allocation already made")
        state.update(
            dictator=str(args["dictator"]),
            recipient=str(args["recipient"]),
            transfer=float(transfer),
        )
        return state

    def complete(self, view):
        return view["transfer"] is not None

    def view(self, state, closed, context=None):
        payoffs = (
            None
            if state["transfer"] is None
            else {
                state["dictator"]: self.endowment - state["transfer"],
                state["recipient"]: state["transfer"],
            }
        )
        return dict(state) | {"endowment": self.endowment, "payoffs": payoffs}

    def to_dict(self):
        return {"type": "dictator_game", "endowment": self.endowment}


class SharedTrustGame(SharedPrimitive):
    """Sender transfer, multiplied funds, then receiver return."""

    def __init__(self, endowment=100, multiplier=3):
        if endowment <= 0 or multiplier <= 0:
            raise SharedStateAuthoringError("trust-game parameters must be positive")
        self.endowment, self.multiplier = float(endowment), float(multiplier)

    def send(self, question, *, player="{{ agent.name }}"):
        return WriteStep(
            self,
            "send",
            {"player": player, "amount": AnswerRef(question.question_name)},
        )

    def return_funds(self, question, *, player="{{ agent.name }}"):
        return WriteStep(
            self,
            "return",
            {"player": player, "amount": AnswerRef(question.question_name)},
        )

    def initial(self):
        return {"sender": None, "receiver": None, "sent": None, "returned": None}

    def apply(self, state, op, args, interview_id):
        amount = args.get("amount")
        if (
            isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or amount < 0
        ):
            raise SharedStateAuthoringError("trust-game amount must be non-negative")
        if op == "send":
            if amount > self.endowment or state["sent"] is not None:
                raise SharedStateAuthoringError("invalid or duplicate trust transfer")
            state["sender"], state["sent"] = str(args["player"]), float(amount)
        elif op == "return":
            available = (state["sent"] or 0) * self.multiplier
            if (
                state["sent"] is None
                or amount > available
                or state["returned"] is not None
            ):
                raise SharedStateAuthoringError("invalid or duplicate trust return")
            state["receiver"], state["returned"] = str(args["player"]), float(amount)
        else:
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedTrustGame"
            )
        return state

    def complete(self, view):
        return view["returned"] is not None

    def view(self, state, closed, context=None):
        available = (
            state["sent"] * self.multiplier if state["sent"] is not None else None
        )
        payoffs = (
            None
            if state["returned"] is None
            else {
                state["sender"]: self.endowment - state["sent"] + state["returned"],
                state["receiver"]: available - state["returned"],
            }
        )
        return dict(state) | {
            "endowment": self.endowment,
            "multiplier": self.multiplier,
            "receiver_available": available,
            "payoffs": payoffs,
        }

    def to_dict(self):
        return {
            "type": "trust_game",
            "endowment": self.endowment,
            "multiplier": self.multiplier,
        }


class SharedBeautyContest(SharedPrimitive):
    def __init__(self, player_count, factor=2 / 3):
        self.player_count, self.factor = int(player_count), float(factor)

    def submit(self, question, *, player="{{ agent.name }}"):
        return WriteStep(
            self,
            "submit",
            {"player": player, "choice": AnswerRef(question.question_name)},
        )

    def initial(self):
        return {"choices": {}}

    def apply(self, state, op, args, interview_id):
        choice = args.get("choice")
        if (
            op != "submit"
            or isinstance(choice, bool)
            or not isinstance(choice, (int, float))
            or not 0 <= choice <= 100
        ):
            raise SharedStateAuthoringError(
                "beauty-contest choice must be between 0 and 100"
            )
        state["choices"][str(args["player"])] = float(choice)
        return state

    def complete(self, view):
        return view["submission_count"] == self.player_count

    def at_close(self, state):
        mean = sum(state["choices"].values()) / len(state["choices"])
        target = self.factor * mean
        distance = {
            player: abs(choice - target) for player, choice in state["choices"].items()
        }
        closest = min(distance.values())
        state.update(
            mean=mean,
            target=target,
            winners=[p for p, d in distance.items() if abs(d - closest) < 1e-9],
        )
        return state

    def view(self, state, closed, context=None):
        result = {
            "factor": self.factor,
            "submission_count": len(state["choices"]),
            "player_count": self.player_count,
        }
        if closed:
            result.update(
                choices=dict(state["choices"]),
                mean=state["mean"],
                target=state["target"],
                winners=state["winners"],
            )
        return result

    def to_dict(self):
        return {
            "type": "beauty_contest",
            "player_count": self.player_count,
            "factor": self.factor,
        }


class SharedCommonPoolGame(SharedPrimitive):
    def __init__(self, player_count, stock=60, max_request=20):
        self.player_count, self.stock, self.max_request = (
            int(player_count),
            float(stock),
            float(max_request),
        )

    def extract(self, question, *, player="{{ agent.name }}"):
        return WriteStep(
            self,
            "extract",
            {"player": player, "amount": AnswerRef(question.question_name)},
        )

    def initial(self):
        return {"requests": {}}

    def apply(self, state, op, args, interview_id):
        amount = args.get("amount")
        if (
            op != "extract"
            or isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or not 0 <= amount <= self.max_request
        ):
            raise SharedStateAuthoringError("invalid common-pool extraction")
        state["requests"][str(args["player"])] = float(amount)
        return state

    def complete(self, view):
        return view["submission_count"] == self.player_count

    def at_close(self, state):
        total = sum(state["requests"].values())
        if total <= self.stock:
            remainder_share = (self.stock - total) / self.player_count
            payoffs = {
                player: amount + remainder_share
                for player, amount in state["requests"].items()
            }
        else:
            payoffs = {
                player: self.stock * amount / total
                for player, amount in state["requests"].items()
            }
        state.update(
            total_requested=total, overdrawn=total > self.stock, payoffs=payoffs
        )
        return state

    def view(self, state, closed, context=None):
        result = {
            "stock": self.stock,
            "max_request": self.max_request,
            "player_count": self.player_count,
            "submission_count": len(state["requests"]),
        }
        if closed:
            result.update(
                requests=dict(state["requests"]),
                total_requested=state["total_requested"],
                overdrawn=state["overdrawn"],
                payoffs=dict(state["payoffs"]),
            )
        return result

    def to_dict(self):
        return {
            "type": "common_pool_game",
            "player_count": self.player_count,
            "stock": self.stock,
            "max_request": self.max_request,
        }


class SharedCentipedeGame(SharedPrimitive):
    """Finite alternating take-or-pass game with early terminal settlement."""

    def __init__(self, take_payoffs, final_pass_payoffs):
        self.take_payoffs = [list(pair) for pair in take_payoffs]
        self.final_pass_payoffs = list(final_pass_payoffs)

    def move(self, question, *, player="{{ agent.player }}", node="{{ agent.node }}"):
        return WriteStep(
            self,
            "move",
            {
                "player": player,
                "node": node,
                "action": AnswerRef(question.question_name),
            },
        )

    def initial(self):
        return {"history": [], "outcome": None, "payoffs": None}

    def apply(self, state, op, args, interview_id):
        if op != "move" or state["outcome"] is not None:
            raise SharedStateAuthoringError("invalid move in terminal centipede game")
        node, action = int(args["node"]), str(args["action"]).lower()
        if node != len(state["history"]) + 1 or not 1 <= node <= len(self.take_payoffs):
            raise SharedStateAuthoringError("centipede move arrived out of node order")
        if action not in {"take", "pass"}:
            raise SharedStateAuthoringError("centipede action must be take or pass")
        state["history"].append(
            {"node": node, "player": str(args["player"]), "action": action}
        )
        if action == "take":
            state["outcome"], state["payoffs"] = (
                f"take_at_{node}",
                list(self.take_payoffs[node - 1]),
            )
        elif node == len(self.take_payoffs):
            state["outcome"], state["payoffs"] = (
                "pass_to_end",
                list(self.final_pass_payoffs),
            )
        return state

    def terminal(self, view):
        return view["outcome"] is not None

    def view(self, state, closed, context=None):
        return {
            "node_count": len(self.take_payoffs),
            "history": list(state["history"]),
            "outcome": state["outcome"],
            "payoffs": state["payoffs"],
        }

    def to_dict(self):
        return {
            "type": "centipede_game",
            "take_payoffs": self.take_payoffs,
            "final_pass_payoffs": self.final_pass_payoffs,
        }


class SharedMarketEntryGame(SharedPrimitive):
    def __init__(
        self, player_count, outside_payoff=2, entry_value=10, congestion_cost=3
    ):
        self.player_count, self.outside_payoff = (
            int(player_count),
            float(outside_payoff),
        )
        self.entry_value, self.congestion_cost = (
            float(entry_value),
            float(congestion_cost),
        )

    def submit(self, question, *, player="{{ agent.name }}"):
        return WriteStep(
            self,
            "submit",
            {"player": player, "action": AnswerRef(question.question_name)},
        )

    def initial(self):
        return {"choices": {}}

    def apply(self, state, op, args, interview_id):
        action = str(args.get("action")).lower()
        if op != "submit" or action not in {"enter", "stay_out"}:
            raise SharedStateAuthoringError(
                "market-entry action must be enter or stay_out"
            )
        state["choices"][str(args["player"])] = action
        return state

    def complete(self, view):
        return view["submission_count"] == self.player_count

    def at_close(self, state):
        entrants = sum(action == "enter" for action in state["choices"].values())
        entrant_payoff = self.entry_value - self.congestion_cost * entrants
        state.update(
            entrant_count=entrants,
            entrant_payoff=entrant_payoff,
            payoffs={
                player: entrant_payoff if action == "enter" else self.outside_payoff
                for player, action in state["choices"].items()
            },
        )
        return state

    def view(self, state, closed, context=None):
        result = {
            "player_count": self.player_count,
            "submission_count": len(state["choices"]),
            "outside_payoff": self.outside_payoff,
            "entry_value": self.entry_value,
            "congestion_cost": self.congestion_cost,
        }
        if closed:
            result.update(
                choices=dict(state["choices"]),
                entrant_count=state["entrant_count"],
                entrant_payoff=state["entrant_payoff"],
                payoffs=dict(state["payoffs"]),
            )
        return result

    def to_dict(self):
        return {
            "type": "market_entry_game",
            "player_count": self.player_count,
            "outside_payoff": self.outside_payoff,
            "entry_value": self.entry_value,
            "congestion_cost": self.congestion_cost,
        }


class SharedSealedAuction(SharedPrimitive):
    """First-price, second-price, or all-pay sealed-bid auction."""

    def __init__(self, mechanism, bidder_count):
        if mechanism not in {"first_price", "second_price", "all_pay"}:
            raise SharedStateAuthoringError("unknown sealed-auction mechanism")
        self.mechanism, self.bidder_count = mechanism, int(bidder_count)

    def bid(
        self,
        question,
        *,
        bidder="{{ agent.name }}",
        seat="{{ agent.seat }}",
        private_value="{{ agent.private_value }}",
    ):
        return WriteStep(
            self,
            "bid",
            {
                "bidder": bidder,
                "seat": seat,
                "private_value": private_value,
                "amount": AnswerRef(question.question_name),
            },
        )

    def initial(self):
        return {"bids": {}}

    def apply(self, state, op, args, interview_id):
        amount, value = args.get("amount"), args.get("private_value")
        if op != "bid" or any(
            isinstance(x, bool) or not isinstance(x, (int, float)) or x < 0
            for x in (amount, value)
        ):
            raise SharedStateAuthoringError(
                "auction bid and private value must be non-negative"
            )
        state["bids"][str(args["bidder"])] = {
            "amount": float(amount),
            "value": float(value),
            "seat": int(args["seat"]),
        }
        return state

    def complete(self, view):
        return view["bid_count"] == self.bidder_count

    def at_close(self, state):
        ranked = sorted(
            state["bids"].items(),
            key=lambda item: (-item[1]["amount"], item[1]["seat"]),
        )
        winner, winning = ranked[0]
        second_bid = ranked[1][1]["amount"] if len(ranked) > 1 else 0
        payments = {bidder: 0.0 for bidder in state["bids"]}
        if self.mechanism == "first_price":
            payments[winner] = winning["amount"]
        elif self.mechanism == "second_price":
            payments[winner] = second_bid
        else:
            payments = {bidder: bid["amount"] for bidder, bid in state["bids"].items()}
        state.update(
            winner=winner,
            winning_bid=winning["amount"],
            price=payments[winner],
            revenue=sum(payments.values()),
            utilities={
                bidder: (bid["value"] if bidder == winner else 0) - payments[bidder]
                for bidder, bid in state["bids"].items()
            },
        )
        return state

    def view(self, state, closed, context=None):
        result = {
            "mechanism": self.mechanism,
            "bidder_count": self.bidder_count,
            "bid_count": len(state["bids"]),
        }
        if closed:
            result.update(
                bids={bidder: bid["amount"] for bidder, bid in state["bids"].items()},
                winner=state["winner"],
                winning_bid=state["winning_bid"],
                price=state["price"],
                revenue=state["revenue"],
                utilities=dict(state["utilities"]),
            )
        return result

    def to_dict(self):
        return {
            "type": "sealed_auction",
            "mechanism": self.mechanism,
            "bidder_count": self.bidder_count,
        }


class SharedBilateralTrade(SharedPrimitive):
    """Buyer posts a price, then privately informed seller accepts or rejects."""

    def __init__(self):
        pass

    def offer(
        self,
        question,
        *,
        buyer="{{ agent.name }}",
        buyer_value="{{ agent.buyer_value }}",
    ):
        return WriteStep(
            self,
            "offer",
            {
                "buyer": buyer,
                "buyer_value": buyer_value,
                "price": AnswerRef(question.question_name),
            },
        )

    def respond(
        self,
        question,
        *,
        seller="{{ agent.name }}",
        seller_cost="{{ agent.seller_cost }}",
    ):
        return WriteStep(
            self,
            "respond",
            {
                "seller": seller,
                "seller_cost": seller_cost,
                "decision": AnswerRef(question.question_name),
            },
        )

    def initial(self):
        return {
            "buyer": None,
            "seller": None,
            "buyer_value": None,
            "seller_cost": None,
            "price": None,
            "accepted": None,
        }

    def apply(self, state, op, args, interview_id):
        if op == "offer":
            price, value = args["price"], args["buyer_value"]
            if (
                any(
                    isinstance(x, bool) or not isinstance(x, (int, float)) or x < 0
                    for x in (price, value)
                )
                or price > value
            ):
                raise SharedStateAuthoringError(
                    "trade offer must lie between zero and buyer value"
                )
            state.update(
                buyer=str(args["buyer"]), buyer_value=float(value), price=float(price)
            )
        elif op == "respond":
            if state["price"] is None:
                raise SharedStateAuthoringError(
                    "seller cannot respond before buyer offer"
                )
            decision, cost = str(args["decision"]).lower(), args["seller_cost"]
            if (
                decision not in {"accept", "reject"}
                or isinstance(cost, bool)
                or not isinstance(cost, (int, float))
                or cost < 0
            ):
                raise SharedStateAuthoringError("invalid seller response")
            state.update(
                seller=str(args["seller"]),
                seller_cost=float(cost),
                accepted=decision == "accept",
            )
        else:
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedBilateralTrade"
            )
        return state

    def terminal(self, view):
        return view["accepted"] is not None

    def view(self, state, closed, context=None):
        viewer = (context or {}).get("role")
        result = {
            "buyer": state["buyer"],
            "seller": state["seller"],
            "price": state["price"],
            "accepted": state["accepted"],
        }
        if viewer == "buyer":
            result["your_value"] = state["buyer_value"]
        elif viewer == "seller":
            result["your_cost"] = state["seller_cost"]
        if state["accepted"] is not None:
            result["payoffs"] = {
                state["buyer"]: state["buyer_value"] - state["price"]
                if state["accepted"]
                else 0,
                state["seller"]: state["price"] - state["seller_cost"]
                if state["accepted"]
                else 0,
            }
        return result

    def to_dict(self):
        return {"type": "bilateral_trade"}


class SharedSignalingGame(SharedPrimitive):
    """Privately typed worker signals, then employer observes signal and hires."""

    def __init__(self, wage=60):
        self.wage = float(wage)

    def signal(
        self,
        question,
        *,
        worker="{{ agent.name }}",
        productivity="{{ agent.productivity }}",
        signal_cost="{{ agent.signal_cost }}",
    ):
        return WriteStep(
            self,
            "signal",
            {
                "worker": worker,
                "productivity": productivity,
                "signal_cost": signal_cost,
                "education": AnswerRef(question.question_name),
            },
        )

    def decide(self, question, *, employer="{{ agent.name }}"):
        return WriteStep(
            self,
            "decide",
            {"employer": employer, "decision": AnswerRef(question.question_name)},
        )

    def initial(self):
        return {
            "worker": None,
            "employer": None,
            "education": None,
            "productivity": None,
            "signal_cost": None,
            "hired": None,
        }

    def apply(self, state, op, args, interview_id):
        if op == "signal":
            education = args["education"]
            if (
                isinstance(education, bool)
                or not isinstance(education, (int, float))
                or not 0 <= education <= 3
            ):
                raise SharedStateAuthoringError(
                    "education signal must be between 0 and 3"
                )
            state.update(
                worker=str(args["worker"]),
                education=float(education),
                productivity=float(args["productivity"]),
                signal_cost=float(args["signal_cost"]),
            )
        elif op == "decide":
            decision = str(args["decision"]).lower()
            if state["education"] is None or decision not in {"hire", "do_not_hire"}:
                raise SharedStateAuthoringError(
                    "invalid signaling-game employer decision"
                )
            state.update(employer=str(args["employer"]), hired=decision == "hire")
        else:
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedSignalingGame"
            )
        return state

    def terminal(self, view):
        return view["hired"] is not None

    def view(self, state, closed, context=None):
        result = {
            "worker": state["worker"],
            "employer": state["employer"],
            "education": state["education"],
            "wage": self.wage,
            "hired": state["hired"],
        }
        if state["hired"] is not None:
            cost = state["education"] * state["signal_cost"]
            result["payoffs"] = {
                state["worker"]: (self.wage if state["hired"] else 0) - cost,
                state["employer"]: state["productivity"] - self.wage
                if state["hired"]
                else 0,
            }
        return result

    def to_dict(self):
        return {"type": "signaling_game", "wage": self.wage}


class SharedNashDemandGame(SharedPrimitive):
    def __init__(self, pie=100):
        self.pie = float(pie)

    def demand(self, question, *, player="{{ agent.name }}", seat="{{ agent.seat }}"):
        return WriteStep(
            self,
            "demand",
            {
                "player": player,
                "seat": seat,
                "amount": AnswerRef(question.question_name),
            },
        )

    def initial(self):
        return {"demands": {}, "players": {}}

    def apply(self, state, op, args, interview_id):
        amount, seat = args.get("amount"), str(int(args.get("seat")))
        if (
            op != "demand"
            or seat not in {"0", "1"}
            or isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or not 0 <= amount <= self.pie
        ):
            raise SharedStateAuthoringError("invalid Nash demand")
        state["demands"][seat], state["players"][seat] = (
            float(amount),
            str(args["player"]),
        )
        return state

    def complete(self, view):
        return view["submission_count"] == 2

    def at_close(self, state):
        feasible = sum(state["demands"].values()) <= self.pie
        state.update(
            feasible=feasible,
            payoffs={
                state["players"][seat]: amount if feasible else 0
                for seat, amount in state["demands"].items()
            },
        )
        return state

    def view(self, state, closed, context=None):
        result = {"pie": self.pie, "submission_count": len(state["demands"])}
        if closed:
            result.update(
                demands={
                    state["players"][seat]: amount
                    for seat, amount in state["demands"].items()
                },
                feasible=state["feasible"],
                payoffs=dict(state["payoffs"]),
            )
        return result

    def to_dict(self):
        return {"type": "nash_demand_game", "pie": self.pie}


class SharedVotingGame(SharedPrimitive):
    """Sealed rankings resolved under plurality, Borda, and Condorcet rules."""

    def __init__(self, candidates, voter_count):
        self.candidates, self.voter_count = list(candidates), int(voter_count)

    def vote(self, question, *, voter="{{ agent.name }}"):
        if set(question.question_options) != set(self.candidates):
            raise SharedStateAuthoringError("voting options must match candidates")
        return WriteStep(
            self, "vote", {"voter": voter, "ranking": AnswerRef(question.question_name)}
        )

    def initial(self):
        return {"ballots": {}}

    def apply(self, state, op, args, interview_id):
        ranking = list(args.get("ranking", []))
        if (
            op != "vote"
            or len(ranking) != len(self.candidates)
            or set(ranking) != set(self.candidates)
        ):
            raise SharedStateAuthoringError(
                "vote must rank every candidate exactly once"
            )
        state["ballots"][str(args["voter"])] = ranking
        return state

    def complete(self, view):
        return view["ballot_count"] == self.voter_count

    def at_close(self, state):
        plurality = Counter(ballot[0] for ballot in state["ballots"].values())
        borda = Counter()
        for ballot in state["ballots"].values():
            for index, candidate in enumerate(ballot):
                borda[candidate] += len(self.candidates) - index - 1
        pairwise = {candidate: 0 for candidate in self.candidates}
        for left in self.candidates:
            for right in self.candidates:
                if left >= right:
                    continue
                left_votes = sum(
                    ballot.index(left) < ballot.index(right)
                    for ballot in state["ballots"].values()
                )
                right_votes = self.voter_count - left_votes
                if left_votes > right_votes:
                    pairwise[left] += 1
                elif right_votes > left_votes:
                    pairwise[right] += 1
        state["results"] = {
            "plurality_scores": dict(plurality),
            "plurality_winner": max(
                self.candidates, key=lambda c: (plurality[c], -self.candidates.index(c))
            ),
            "borda_scores": dict(borda),
            "borda_winner": max(
                self.candidates, key=lambda c: (borda[c], -self.candidates.index(c))
            ),
            "condorcet_winner": next(
                (c for c, wins in pairwise.items() if wins == len(self.candidates) - 1),
                None,
            ),
        }
        return state

    def view(self, state, closed, context=None):
        result = {
            "candidates": self.candidates,
            "voter_count": self.voter_count,
            "ballot_count": len(state["ballots"]),
        }
        if closed:
            result.update(
                ballots=dict(state["ballots"]), results=dict(state["results"])
            )
        return result

    def to_dict(self):
        return {
            "type": "voting_game",
            "candidates": self.candidates,
            "voter_count": self.voter_count,
        }


class SharedCheapTalkGame(SharedPrimitive):
    """Privately informed sender messages, then receiver chooses an action."""

    def message(
        self,
        question,
        *,
        sender="{{ agent.name }}",
        state="{{ agent.private_state }}",
        preference="{{ agent.sender_preference }}",
    ):
        return WriteStep(
            self,
            "message",
            {
                "sender": sender,
                "state": state,
                "preference": preference,
                "message": AnswerRef(question.question_name),
            },
        )

    def act(self, question, *, receiver="{{ agent.name }}"):
        return WriteStep(
            self,
            "act",
            {"receiver": receiver, "action": AnswerRef(question.question_name)},
        )

    def initial(self):
        return {
            "sender": None,
            "receiver": None,
            "state": None,
            "preference": None,
            "message": None,
            "action": None,
        }

    def apply(self, state, op, args, interview_id):
        if op == "message":
            private_state, message = str(args["state"]), str(args["message"])
            if private_state not in {"L", "R"} or message not in {"L", "R"}:
                raise SharedStateAuthoringError(
                    "cheap-talk state and message must be L or R"
                )
            state.update(
                sender=str(args["sender"]),
                state=private_state,
                preference=str(args["preference"]),
                message=message,
            )
        elif op == "act":
            action = str(args["action"])
            if state["message"] is None or action not in {"L", "R"}:
                raise SharedStateAuthoringError("invalid cheap-talk receiver action")
            state.update(receiver=str(args["receiver"]), action=action)
        else:
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedCheapTalkGame"
            )
        return state

    def terminal(self, view):
        return view["action"] is not None

    def view(self, state, closed, context=None):
        result = {
            "sender": state["sender"],
            "receiver": state["receiver"],
            "message": state["message"],
            "action": state["action"],
        }
        if state["action"] is not None:
            receiver_payoff = int(state["action"] == state["state"])
            sender_target = state["state"] if state["preference"] == "aligned" else "R"
            result["payoffs"] = {
                state["sender"]: int(state["action"] == sender_target),
                state["receiver"]: receiver_payoff,
            }
            result["truthful"] = state["message"] == state["state"]
            result["correct_action"] = state["action"] == state["state"]
        return result

    def to_dict(self):
        return {"type": "cheap_talk_game"}


class SharedPrincipalAgentGame(SharedPrimitive):
    """Principal offers success bonus; agent privately chooses costly effort."""

    def __init__(
        self, output_value=100, high_probability=0.8, low_probability=0.2, high_cost=20
    ):
        self.output_value, self.high_probability = (
            float(output_value),
            float(high_probability),
        )
        self.low_probability, self.high_cost = float(low_probability), float(high_cost)

    def contract(self, question, *, principal="{{ agent.name }}"):
        return WriteStep(
            self,
            "contract",
            {"principal": principal, "bonus": AnswerRef(question.question_name)},
        )

    def effort(self, question, *, worker="{{ agent.name }}"):
        return WriteStep(
            self,
            "effort",
            {"worker": worker, "effort": AnswerRef(question.question_name)},
        )

    def initial(self):
        return {"principal": None, "worker": None, "bonus": None, "effort": None}

    def apply(self, state, op, args, interview_id):
        if op == "contract":
            bonus = args["bonus"]
            if (
                isinstance(bonus, bool)
                or not isinstance(bonus, (int, float))
                or not 0 <= bonus <= self.output_value
            ):
                raise SharedStateAuthoringError(
                    "bonus must lie between zero and output value"
                )
            state.update(principal=str(args["principal"]), bonus=float(bonus))
        elif op == "effort":
            effort = str(args["effort"]).lower()
            if state["bonus"] is None or effort not in {"high", "low"}:
                raise SharedStateAuthoringError("invalid principal-agent effort")
            state.update(worker=str(args["worker"]), effort=effort)
        else:
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedPrincipalAgentGame"
            )
        return state

    def terminal(self, view):
        return view["effort_chosen"]

    def view(self, state, closed, context=None):
        result = {
            "principal": state["principal"],
            "worker": state["worker"],
            "bonus": state["bonus"],
            "effort_chosen": state["effort"] is not None,
        }
        if state["effort"] is not None:
            probability = (
                self.high_probability
                if state["effort"] == "high"
                else self.low_probability
            )
            cost = self.high_cost if state["effort"] == "high" else 0
            result.update(
                effort=state["effort"] if closed else "private",
                success_probability=probability,
                expected_payoffs={
                    state["principal"]: probability
                    * (self.output_value - state["bonus"]),
                    state["worker"]: probability * state["bonus"] - cost,
                },
            )
        return result

    def to_dict(self):
        return {
            "type": "principal_agent_game",
            "output_value": self.output_value,
            "high_probability": self.high_probability,
            "low_probability": self.low_probability,
            "high_cost": self.high_cost,
        }


class SharedCoalitionPool(SharedPrimitive):
    """Capacity-constrained coalitions with atomic, exclusive membership moves."""

    def __init__(self, coalitions: dict[str, dict]):
        if not coalitions:
            raise SharedStateAuthoringError("coalition pool requires coalitions")
        self.coalitions = {name: dict(config) for name, config in coalitions.items()}
        for name, config in self.coalitions.items():
            capacity = config.get("capacity")
            if (
                not isinstance(capacity, int)
                or isinstance(capacity, bool)
                or capacity < 1
            ):
                raise SharedStateAuthoringError(
                    f"coalition '{name}' requires a positive integer capacity"
                )

    def request(
        self,
        question,
        *,
        member="{{ agent.name }}",
        round_number="{{ run.round }}",
    ) -> WriteStep:
        if getattr(question, "question_type", None) != "multiple_choice":
            raise SharedStateAuthoringError(
                "coalition request expects a multiple-choice question"
            )
        if set(question.question_options) != set(self.coalitions):
            raise SharedStateAuthoringError(
                "coalition question options must exactly match configured coalitions"
            )
        return WriteStep(
            self,
            "request",
            {
                "member": member,
                "coalition": AnswerRef(question.question_name),
                "round": round_number,
            },
        )

    def initial(self):
        return {
            "memberships": {},
            "members": {name: [] for name in self.coalitions},
            "requests": [],
        }

    def apply(self, state, op, args, interview_id):
        if op != "request":
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedCoalitionPool"
            )
        member = str(args["member"])
        coalition = str(args["coalition"])
        if coalition not in self.coalitions:
            raise SharedStateAuthoringError(f"unknown coalition '{coalition}'")
        previous = state["memberships"].get(member)
        accepted = (
            previous == coalition
            or len(state["members"][coalition]) < self.coalitions[coalition]["capacity"]
        )
        if accepted and previous != coalition:
            if previous is not None:
                state["members"][previous].remove(member)
            state["members"][coalition].append(member)
            state["memberships"][member] = coalition
        state["requests"].append(
            {
                "member": member,
                "round": int(args["round"]),
                "coalition": coalition,
                "previous": previous,
                "accepted": accepted,
                "reason": None if accepted else "coalition_full",
            }
        )
        return state

    def view(self, state, closed, context=None):
        viewer = (context or {}).get("name")
        coalitions = {
            name: {
                "platform": config.get("platform", ""),
                "capacity": config["capacity"],
                "members": list(state["members"][name]),
                "open_seats": config["capacity"] - len(state["members"][name]),
            }
            for name, config in self.coalitions.items()
        }
        return {
            "coalitions": coalitions,
            "your_membership": state["memberships"].get(viewer),
            "your_last_request": next(
                (
                    request
                    for request in reversed(state["requests"])
                    if request["member"] == viewer
                ),
                None,
            )
            if viewer
            else None,
            "recent_requests": state["requests"][-10:],
        }

    def to_dict(self):
        return {"type": "coalition_pool", "coalitions": self.coalitions}

    def render_markdown(self, view):
        rows = ["| Coalition | Platform | Capacity | Members |", "|---|---|---:|---|"]
        rows.extend(
            f"| {name} | {coalition['platform']} | {coalition['capacity']} | "
            f"{', '.join(coalition['members']) or '—'} |"
            for name, coalition in view["coalitions"].items()
        )
        rejected = [
            request for request in view["recent_requests"] if not request["accepted"]
        ]
        if rejected:
            rows.extend(["", "**Recent rejected requests**", ""])
            rows.extend(
                f"- Round {request['round']}: {request['member']} → "
                f"{request['coalition']} ({request['reason']})"
                for request in rejected
            )
        return "\n".join(rows)


class SharedBudgetPool(SharedPrimitive):
    """Finite shared budget with atomic partial funding under contention."""

    def __init__(self, total: float, projects: dict[str, str]):
        if total <= 0 or not projects:
            raise SharedStateAuthoringError(
                "budget pool requires a positive total and at least one project"
            )
        self.total = float(total)
        self.projects = dict(projects)

    def fund(
        self,
        project_question,
        amount_question,
        *,
        sponsor="{{ agent.name }}",
        round_number="{{ run.round }}",
    ) -> WriteStep:
        if getattr(project_question, "question_type", None) != "multiple_choice":
            raise SharedStateAuthoringError(
                "budget project expects a multiple-choice question"
            )
        if set(project_question.question_options) != set(self.projects):
            raise SharedStateAuthoringError(
                "budget project options must exactly match configured projects"
            )
        if getattr(amount_question, "question_type", None) != "numerical":
            raise SharedStateAuthoringError(
                "budget amount expects a numerical question"
            )
        return WriteStep(
            self,
            "fund",
            {
                "sponsor": sponsor,
                "round": round_number,
                "project": AnswerRef(project_question.question_name),
                "amount": AnswerRef(amount_question.question_name),
            },
        )

    def initial(self):
        return {
            "remaining": self.total,
            "funded": {project: 0.0 for project in self.projects},
            "allocations": [],
        }

    def apply(self, state, op, args, interview_id):
        if op != "fund":
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedBudgetPool"
            )
        project = str(args["project"])
        amount = args["amount"]
        if project not in self.projects:
            raise SharedStateAuthoringError(f"unknown budget project '{project}'")
        if (
            isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or amount < 0
        ):
            raise SharedStateAuthoringError(
                "budget request amount must be a non-negative number"
            )
        granted = min(float(amount), state["remaining"])
        state["remaining"] -= granted
        state["funded"][project] += granted
        state["allocations"].append(
            {
                "sponsor": str(args["sponsor"]),
                "round": int(args["round"]),
                "project": project,
                "requested": float(amount),
                "granted": granted,
                "partial": 0 < granted < amount,
            }
        )
        return state

    def exhausted(self, view):
        return view["remaining"] <= 1e-9

    def view(self, state, closed, context=None):
        return {
            "total": self.total,
            "remaining": state["remaining"],
            "projects": {
                name: {"description": description, "funded": state["funded"][name]}
                for name, description in self.projects.items()
            },
            "recent_allocations": state["allocations"][-10:],
        }

    def to_dict(self):
        return {"type": "budget_pool", "total": self.total, "projects": self.projects}

    def render_markdown(self, view):
        rows = [
            f"**Remaining:** ${view['remaining']:g} of ${view['total']:g}",
            "",
            "| Project | Description | Funded |",
            "|---|---|---:|",
        ]
        rows.extend(
            f"| {name} | {project['description']} | ${project['funded']:g} |"
            for name, project in view["projects"].items()
        )
        return "\n".join(rows)


class SharedDocument(SharedPrimitive):
    """Versioned shared text revised atomically as a whole document."""

    def __init__(self, title: str, initial_text: str):
        self.title = title
        self.initial_text = initial_text

    def revise(
        self,
        text_question,
        rationale_question,
        *,
        author="{{ agent.name }}",
        round_number="{{ run.round }}",
    ) -> WriteStep:
        return WriteStep(
            self,
            "revise",
            {
                "author": author,
                "round": round_number,
                "text": AnswerRef(text_question.question_name),
                "rationale": AnswerRef(rationale_question.question_name),
            },
        )

    def initial(self):
        return {"text": self.initial_text, "revisions": []}

    def apply(self, state, op, args, interview_id):
        if op != "revise":
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedDocument"
            )
        previous = state["text"]
        state["text"] = str(args["text"])
        state["revisions"].append(
            {
                "author": str(args["author"]),
                "round": int(args["round"]),
                "rationale": str(args["rationale"]),
                "changed": state["text"] != previous,
            }
        )
        return state

    def view(self, state, closed, context=None):
        return {
            "title": self.title,
            "text": state["text"],
            "revision_count": len(state["revisions"]),
            "recent_revisions": state["revisions"][-10:],
        }

    def to_dict(self):
        return {
            "type": "document",
            "title": self.title,
            "initial_text": self.initial_text,
        }

    def render_markdown(self, view):
        lines = [
            f"### {view['title']}",
            "",
            view["text"],
            "",
            "### Revision history",
            "",
        ]
        lines.extend(
            f"- Round {item['round']}: **{item['author']}** — {item['rationale']}"
            for item in view["recent_revisions"]
        )
        return "\n".join(lines)


class SharedCounterMap(SharedPrimitive):
    def __init__(self, keys):
        self.keys = list(keys)

    def tally(self, question) -> WriteStep:
        if getattr(question, "question_type", None) != "checkbox":
            raise SharedStateAuthoringError(
                f"tally expects a checkbox question; '{question.question_name}' is "
                f"{getattr(question, 'question_type', type(question).__name__)}"
            )
        options = set(question.question_options)
        if not options.issubset(set(self.keys)):
            missing = sorted(options - set(self.keys))
            raise SharedStateAuthoringError(
                f"tally options for '{question.question_name}' are not counter keys: {missing}"
            )
        return WriteStep(self, "tally", {"values": AnswerRef(question.question_name)})

    def initial(self):
        return {key: 0 for key in self.keys}

    def apply(self, state, op, args, interview_id):
        if op != "tally":
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedCounterMap"
            )
        for key in args["values"]:
            if key not in state:
                raise SharedStateAuthoringError(
                    f"tally value '{key}' is not a configured key"
                )
            state[key] += 1
        return state

    def view(self, state, closed, context=None):
        return {"counts": dict(state)}

    def to_dict(self):
        return {"type": "counter_map", "keys": self.keys}

    def render_markdown(self, view):
        rows = ["| Option | Count |", "|---|---:|"]
        rows.extend(f"| {key} | {count} |" for key, count in view["counts"].items())
        return "\n".join(rows)


class SharedMatchPool(SharedPrimitive):
    def __init__(self, items, rule="serial_dictatorship", capacity=1):
        if rule != "serial_dictatorship":
            raise SharedStateAuthoringError(
                f"unknown match rule '{rule}'; v0 supports 'serial_dictatorship'"
            )
        self.items = list(items)
        self.rule = rule
        self.capacity = capacity

    def collect(
        self,
        question,
        *,
        claimant=None,
        priority=None,
    ) -> WriteStep:
        if getattr(question, "question_type", None) != "rank":
            raise SharedStateAuthoringError(
                f"collect expects a rank question; '{question.question_name}' is "
                f"{getattr(question, 'question_type', type(question).__name__)}"
            )
        if list(question.question_options) != self.items:
            raise SharedStateAuthoringError(
                f"collect options for '{question.question_name}' must exactly equal the match-pool items"
            )
        args = {"ranking": AnswerRef(question.question_name)}
        if claimant is not None:
            args["claimant"] = claimant
        if priority is not None:
            args["priority"] = priority
        return WriteStep(self, "collect", args)

    def initial(self):
        return {"requests": []}

    def apply(self, state, op, args, interview_id):
        if op != "collect":
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedMatchPool"
            )
        state["requests"].append(
            {
                "interview": interview_id,
                "claimant": args.get("claimant"),
                "priority": args.get("priority"),
                "ranking": list(args["ranking"]),
            }
        )
        return state

    def at_close(self, state):
        latest = {}
        for index, request in enumerate(state["requests"]):
            claimant = request.get("claimant") or request["interview"]
            latest[claimant] = (
                request.get("priority"),
                index,
                request["ranking"],
            )
        remaining = {item: self.capacity for item in self.items}
        assignments = {}
        for interview, (_, _, ranking) in sorted(
            latest.items(),
            key=lambda pair: (
                pair[1][0] is None,
                pair[1][0] if pair[1][0] is not None else pair[1][1],
                pair[1][1],
            ),
        ):
            for item in ranking:
                if remaining.get(item, 0) > 0:
                    assignments[interview] = item
                    remaining[item] -= 1
                    break
        state["assignments"] = assignments
        return state

    def view(self, state, closed, context=None):
        latest = {}
        for request in state["requests"]:
            claimant = request.get("claimant") or request["interview"]
            latest[claimant] = request["ranking"]
        counts = Counter(ranking[0] for ranking in latest.values() if ranking)
        result = {"request_counts": {item: counts[item] for item in self.items}}
        if closed:
            result["assignments"] = dict(state.get("assignments", {}))
        return result

    def to_dict(self):
        return {
            "type": "match_pool",
            "items": self.items,
            "rule": self.rule,
            "capacity": self.capacity,
        }

    def render_markdown(self, view):
        rows = ["| Item | First-choice requests |", "|---|---:|"]
        rows.extend(
            f"| {item} | {count} |" for item, count in view["request_counts"].items()
        )
        if "assignments" in view:
            rows.extend(["", "### Assignments", ""])
            rows.extend(
                f"- `{interview}` → **{item}**"
                for interview, item in view["assignments"].items()
            )
        return "\n".join(rows)


class SharedDeferredAcceptance(SharedPrimitive):
    """Student-proposing deferred acceptance with fixed institution priorities."""

    def __init__(self, capacities: dict[str, int], priorities: dict[str, list[str]]):
        if not capacities or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 1
            for value in capacities.values()
        ):
            raise SharedStateAuthoringError(
                "deferred acceptance requires positive integer capacities"
            )
        if set(priorities) != set(capacities):
            raise SharedStateAuthoringError(
                "institution priorities must exactly match capacity keys"
            )
        if any(len(order) != len(set(order)) for order in priorities.values()):
            raise SharedStateAuthoringError(
                "institution priority lists cannot contain duplicates"
            )
        self.capacities = dict(capacities)
        self.priorities = {name: list(order) for name, order in priorities.items()}
        self.institutions = list(capacities)

    def collect(self, question, *, student="{{ agent.name }}") -> WriteStep:
        if getattr(question, "question_type", None) != "rank":
            raise SharedStateAuthoringError(
                "deferred acceptance expects a rank question"
            )
        if list(question.question_options) != self.institutions:
            raise SharedStateAuthoringError(
                "rank options must exactly equal the configured institutions"
            )
        return WriteStep(
            self,
            "collect",
            {"student": student, "ranking": AnswerRef(question.question_name)},
        )

    def initial(self):
        return {"requests": []}

    def apply(self, state, op, args, interview_id):
        if op != "collect":
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedDeferredAcceptance"
            )
        ranking = list(args["ranking"])
        if len(ranking) != len(self.institutions) or set(ranking) != set(
            self.institutions
        ):
            raise SharedStateAuthoringError(
                "student ranking must contain every institution exactly once"
            )
        state["requests"].append(
            {
                "interview": interview_id,
                "student": str(args["student"]),
                "ranking": ranking,
            }
        )
        return state

    def at_close(self, state):
        latest = {}
        for request in state["requests"]:
            latest[request["student"]] = list(request["ranking"])
        rank = {
            institution: {student: index for index, student in enumerate(order)}
            for institution, order in self.priorities.items()
        }
        held = {institution: [] for institution in self.institutions}
        next_choice = {student: 0 for student in latest}
        unmatched = sorted(latest)
        while unmatched:
            student = unmatched.pop(0)
            choice_index = next_choice[student]
            if choice_index >= len(latest[student]):
                continue
            institution = latest[student][choice_index]
            next_choice[student] += 1
            candidates = held[institution] + [student]
            candidates.sort(
                key=lambda name: (rank[institution].get(name, math.inf), name)
            )
            held[institution] = candidates[: self.capacities[institution]]
            rejected = candidates[self.capacities[institution] :]
            unmatched.extend(rejected)
        state["matches"] = {
            student: institution
            for institution, students in held.items()
            for student in students
        }
        state["institution_matches"] = held
        return state

    def view(self, state, closed, context=None):
        first_choices = Counter(
            request["ranking"][0] for request in state["requests"] if request["ranking"]
        )
        result = {
            "preference_count": len({r["student"] for r in state["requests"]}),
            "first_choice_demand": {
                institution: first_choices[institution]
                for institution in self.institutions
            },
        }
        if closed:
            result["matches"] = dict(state.get("matches", {}))
            result["institution_matches"] = dict(state.get("institution_matches", {}))
        return result

    def to_dict(self):
        return {
            "type": "deferred_acceptance",
            "capacities": self.capacities,
            "priorities": self.priorities,
        }

    def render_markdown(self, view):
        rows = ["| Institution | First-choice demand |", "|---|---:|"]
        rows.extend(
            f"| {institution} | {count} |"
            for institution, count in view["first_choice_demand"].items()
        )
        if "matches" in view:
            rows.extend(["", "### Final matches", ""])
            rows.extend(
                f"- **{student}** → {institution}"
                for student, institution in sorted(view["matches"].items())
            )
        return "\n".join(rows)


class SharedDoubleAuction(SharedPrimitive):
    """Atomic unit-order book with price-time priority and immediate matching."""

    ACTIONS = {"buy", "sell", "cancel", "hold"}

    def __init__(self, participants: dict[str, dict[str, float]]):
        if not participants:
            raise SharedStateAuthoringError(
                "double auction requires at least one participant"
            )
        normalized = {}
        for name, account in participants.items():
            cash = account.get("cash", 0)
            inventory = account.get("inventory", 0)
            if cash < 0 or inventory < 0:
                raise SharedStateAuthoringError(
                    "double-auction cash and inventory cannot be negative"
                )
            normalized[str(name)] = {
                "cash": float(cash),
                "inventory": int(inventory),
            }
        self.participants = normalized

    def submit(
        self,
        action_question,
        price_question,
        *,
        trader="{{ agent.name }}",
        round_number="{{ run.round }}",
    ) -> WriteStep:
        if getattr(action_question, "question_type", None) != "multiple_choice":
            raise SharedStateAuthoringError(
                "double-auction action expects a multiple-choice question"
            )
        if set(action_question.question_options) != self.ACTIONS:
            raise SharedStateAuthoringError(
                "double-auction actions must be buy, sell, cancel, and hold"
            )
        if getattr(price_question, "question_type", None) != "numerical":
            raise SharedStateAuthoringError(
                "double-auction price expects a numerical question"
            )
        return WriteStep(
            self,
            "submit",
            {
                "trader": trader,
                "round": round_number,
                "action": AnswerRef(action_question.question_name),
                "price": AnswerRef(price_question.question_name),
            },
        )

    def initial(self):
        return {
            "accounts": {
                name: dict(account) for name, account in self.participants.items()
            },
            "orders": [],
            "trades": [],
        }

    def apply(self, state, op, args, interview_id):
        if op != "submit":
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedDoubleAuction"
            )
        trader = str(args["trader"])
        action = str(args["action"])
        if trader not in state["accounts"]:
            raise SharedStateAuthoringError(f"unknown trader '{trader}'")
        if action not in self.ACTIONS:
            raise SharedStateAuthoringError(f"unknown order action '{action}'")
        open_orders = [
            order
            for order in state["orders"]
            if order["trader"] == trader and order["status"] == "open"
        ]
        if action == "cancel":
            for order in open_orders:
                order["status"] = "cancelled"
            return state
        if action == "hold":
            return state
        if open_orders:
            raise SharedStateAuthoringError(
                f"trader '{trader}' must cancel an open order before replacing it"
            )
        price = args["price"]
        if isinstance(price, bool) or not isinstance(price, (int, float)) or price <= 0:
            raise SharedStateAuthoringError("order price must be positive")
        account = state["accounts"][trader]
        if action == "buy" and account["cash"] < price:
            raise SharedStateAuthoringError(f"trader '{trader}' has insufficient cash")
        if action == "sell" and account["inventory"] < 1:
            raise SharedStateAuthoringError(
                f"trader '{trader}' has insufficient inventory"
            )
        order = {
            "id": f"O{len(state['orders']) + 1}",
            "trader": trader,
            "side": action,
            "price": float(price),
            "round": int(args["round"]),
            "status": "open",
            "interview": interview_id,
        }
        state["orders"].append(order)
        opposite = "sell" if action == "buy" else "buy"
        compatible = [
            candidate
            for candidate in state["orders"]
            if candidate["status"] == "open"
            and candidate["side"] == opposite
            and (
                candidate["price"] <= order["price"]
                if action == "buy"
                else candidate["price"] >= order["price"]
            )
        ]
        if not compatible:
            return state
        resting = sorted(
            compatible,
            key=lambda candidate: (
                candidate["price"] if action == "buy" else -candidate["price"],
                int(candidate["id"][1:]),
            ),
        )[0]
        buyer_order, seller_order = (
            (order, resting) if action == "buy" else (resting, order)
        )
        trade_price = resting["price"]
        buyer = state["accounts"][buyer_order["trader"]]
        seller = state["accounts"][seller_order["trader"]]
        if buyer["cash"] < trade_price or seller["inventory"] < 1:
            raise SharedStateAuthoringError("resting order is no longer collateralized")
        buyer["cash"] -= trade_price
        buyer["inventory"] += 1
        seller["cash"] += trade_price
        seller["inventory"] -= 1
        buyer_order["status"] = "filled"
        seller_order["status"] = "filled"
        state["trades"].append(
            {
                "buyer": buyer_order["trader"],
                "seller": seller_order["trader"],
                "price": trade_price,
                "round": int(args["round"]),
                "maker_order": resting["id"],
                "taker_order": order["id"],
            }
        )
        return state

    def at_close(self, state):
        for order in state["orders"]:
            if order["status"] == "open":
                order["status"] = "expired"
        return state

    def view(self, state, closed, context=None):
        open_orders = [order for order in state["orders"] if order["status"] == "open"]
        bids = sorted(
            (order for order in open_orders if order["side"] == "buy"),
            key=lambda order: (-order["price"], int(order["id"][1:])),
        )
        asks = sorted(
            (order for order in open_orders if order["side"] == "sell"),
            key=lambda order: (order["price"], int(order["id"][1:])),
        )
        result = {
            "best_bid": bids[0]["price"] if bids else None,
            "best_ask": asks[0]["price"] if asks else None,
            "bids": [{"trader": o["trader"], "price": o["price"]} for o in bids],
            "asks": [{"trader": o["trader"], "price": o["price"]} for o in asks],
            "trades": list(state["trades"]),
        }
        viewer = (context or {}).get("name")
        if viewer in state["accounts"]:
            result["your_account"] = dict(state["accounts"][viewer])
            result["your_open_orders"] = [
                order for order in open_orders if order["trader"] == viewer
            ]
        elif not context:
            result["accounts"] = {
                name: dict(account) for name, account in state["accounts"].items()
            }
        if closed:
            result["closed"] = True
        return result

    def to_dict(self):
        return {"type": "double_auction", "participants": self.participants}

    def render_markdown(self, view):
        rows = ["| Buyer | Seller | Price | Round |", "|---|---|---:|---:|"]
        rows.extend(
            f"| {trade['buyer']} | {trade['seller']} | {trade['price']:g} | {trade['round']} |"
            for trade in view["trades"]
        )
        if not view["trades"]:
            rows.append("| — | — | — | — |")
        return "\n".join(rows)


class SharedResourceBoard(SharedPrimitive):
    """Atomic assignment of capability-constrained resources to incidents."""

    def __init__(self, incidents: list[dict], resources: dict[str, str]):
        self.incidents = [dict(item) for item in incidents]
        self.resources = dict(resources)
        ids = [item.get("id") for item in self.incidents]
        if any(item_id is None for item_id in ids) or len(ids) != len(set(ids)):
            raise SharedStateAuthoringError(
                "resource-board incidents require unique non-null ids"
            )
        if not self.resources:
            raise SharedStateAuthoringError("resource board requires resources")

    def allocate(
        self,
        incident_question,
        resource_question,
        *,
        responder="{{ agent.name }}",
        round_number="{{ run.round }}",
    ) -> WriteStep:
        if getattr(incident_question, "question_type", None) != "multiple_choice":
            raise SharedStateAuthoringError(
                "incident allocation expects a multiple-choice incident question"
            )
        if getattr(resource_question, "question_type", None) != "multiple_choice":
            raise SharedStateAuthoringError(
                "incident allocation expects a multiple-choice resource question"
            )
        return WriteStep(
            self,
            "allocate",
            {
                "responder": responder,
                "round": round_number,
                "incident": AnswerRef(incident_question.question_name),
                "resource": AnswerRef(resource_question.question_name),
            },
        )

    def initial(self):
        return {"assignments": {}, "resource_use": {}, "attempts": []}

    def apply(self, state, op, args, interview_id):
        if op != "allocate":
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedResourceBoard"
            )
        incident_id = str(args["incident"])
        resource = str(args["resource"])
        attempt = {
            "responder": str(args["responder"]),
            "round": int(args["round"]),
            "incident": incident_id,
            "resource": resource,
            "accepted": False,
        }
        incident = next(
            (item for item in self.incidents if str(item["id"]) == incident_id), None
        )
        if incident_id == "none" or resource == "none":
            attempt["reason"] = "held"
        elif incident is None or resource not in self.resources:
            attempt["reason"] = "unknown incident or resource"
        elif incident.get("round", 1) > attempt["round"]:
            attempt["reason"] = "incident not yet released"
        elif incident_id in state["assignments"]:
            attempt["reason"] = "incident already assigned"
        elif resource in state["resource_use"]:
            attempt["reason"] = "resource already committed"
        elif self.resources[resource] != incident.get("capability"):
            attempt["reason"] = "capability mismatch"
        else:
            attempt["accepted"] = True
            attempt["reason"] = "assigned"
            state["assignments"][incident_id] = {
                "resource": resource,
                "responder": attempt["responder"],
                "round": attempt["round"],
            }
            state["resource_use"][resource] = incident_id
        state["attempts"].append(attempt)
        return state

    def view(self, state, closed, context=None):
        assigned = set(state["assignments"])
        return {
            "unassigned_incidents": [
                item for item in self.incidents if str(item["id"]) not in assigned
            ],
            "available_resources": {
                name: capability
                for name, capability in self.resources.items()
                if name not in state["resource_use"]
            },
            "assignments": dict(state["assignments"]),
            "recent_attempts": list(state["attempts"][-10:]),
            "closed": closed,
        }

    def to_dict(self):
        return {
            "type": "resource_board",
            "incidents": self.incidents,
            "resources": self.resources,
        }

    def render_markdown(self, view):
        rows = ["| Incident | Resource | Responder | Round |", "|---|---|---|---:|"]
        rows.extend(
            f"| {incident} | {assignment['resource']} | {assignment['responder']} | {assignment['round']} |"
            for incident, assignment in view["assignments"].items()
        )
        if not view["assignments"]:
            rows.append("| — | — | — | — |")
        return "\n".join(rows)


class SharedAuction(SharedPrimitive):
    """Append-only ascending-price auction resolved deterministically at close."""

    def __init__(self, item: str, increment: float = 1):
        if increment <= 0:
            raise SharedStateAuthoringError(
                "auction increment must be greater than zero"
            )
        self.item = item
        self.increment = increment

    def bid(self, question) -> WriteStep:
        if getattr(question, "question_type", None) != "numerical":
            raise SharedStateAuthoringError(
                f"bid expects a numerical question; '{question.question_name}' is "
                f"{getattr(question, 'question_type', type(question).__name__)}"
            )
        return WriteStep(self, "bid", {"amount": AnswerRef(question.question_name)})

    def initial(self):
        return {"bids": []}

    def apply(self, state, op, args, interview_id):
        if op != "bid":
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedAuction"
            )
        amount = args.get("amount")
        if (
            isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or amount < 0
        ):
            raise SharedStateAuthoringError(
                f"auction bid must be a non-negative number; received {amount!r}"
            )
        state["bids"].append({"interview": interview_id, "amount": amount})
        return state

    def at_close(self, state):
        positive = [bid for bid in state["bids"] if bid["amount"] > 0]
        if positive:
            winning = max(positive, key=lambda bid: bid["amount"])
            state["winner"] = winning["interview"]
            state["winning_bid"] = winning["amount"]
        else:
            state["winner"] = None
            state["winning_bid"] = None
        return state

    def view(self, state, closed, context=None):
        positive = [bid for bid in state["bids"] if bid["amount"] > 0]
        result = {
            "item": self.item,
            "highest_bid": max((bid["amount"] for bid in positive), default=0),
            "bid_count": len(positive),
            "increment": self.increment,
        }
        if closed:
            result.update(
                winner=state.get("winner"), winning_bid=state.get("winning_bid")
            )
        return result

    def to_dict(self):
        return {"type": "auction", "item": self.item, "increment": self.increment}

    def render_markdown(self, view):
        lines = [
            f"**Item:** {view['item']}",
            "",
            f"**Current highest bid:** ${view['highest_bid']:g}",
            f"**Bids placed:** {view['bid_count']}",
            f"**Minimum increment:** ${view['increment']:g}",
        ]
        if "winner" in view:
            lines.extend(
                [
                    "",
                    f"**Winner:** `{view['winner']}`"
                    if view["winner"]
                    else "**Winner:** None",
                    f"**Winning bid:** ${view['winning_bid']:g}"
                    if view["winning_bid"] is not None
                    else "**Winning bid:** None",
                ]
            )
        return "\n".join(lines)


class SharedMessageBoard(SharedPrimitive):
    """An append-only board whose entries may name another author as a reply target."""

    def add(
        self, author_question, message_question, reply_to_question=None
    ) -> WriteStep:
        for question, role in (
            (author_question, "author"),
            (message_question, "message"),
            (reply_to_question, "reply target"),
        ):
            if (
                question is not None
                and getattr(question, "question_type", None) != "free_text"
            ):
                raise SharedStateAuthoringError(
                    f"message-board {role} expects a free-text question; "
                    f"'{question.question_name}' is {getattr(question, 'question_type', type(question).__name__)}"
                )
        args = {
            "author": AnswerRef(author_question.question_name),
            "message": AnswerRef(message_question.question_name),
        }
        if reply_to_question is not None:
            args["reply_to"] = AnswerRef(reply_to_question.question_name)
        return WriteStep(self, "add", args)

    def initial(self):
        return {"messages": []}

    def apply(self, state, op, args, interview_id):
        if op != "add":
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedMessageBoard"
            )
        author = str(args.get("author", "")).strip()
        message = str(args.get("message", "")).strip()
        reply_to = str(args.get("reply_to", "")).strip() or None
        if reply_to and reply_to.casefold() in {"none", "new", "new message", "n/a"}:
            reply_to = None
        if not author or not message:
            raise SharedStateAuthoringError(
                "message-board entries require non-empty author and message values"
            )
        state["messages"].append(
            {
                "author": author,
                "message": message,
                "reply_to": reply_to,
                "interview": interview_id,
            }
        )
        return state

    def view(self, state, closed, context=None):
        return {
            "messages": [
                {
                    "author": entry["author"],
                    "message": entry["message"],
                    "reply_to": entry["reply_to"],
                }
                for entry in state["messages"]
            ],
            "message_count": len(state["messages"]),
        }

    def to_dict(self):
        return {"type": "message_board"}

    def render_markdown(self, view):
        if not view["messages"]:
            return "_No messages yet._"
        blocks = []
        for index, entry in enumerate(view["messages"], 1):
            heading = f"### {index}. {entry['author']}"
            if entry["reply_to"]:
                heading += f" ↪ replying to {entry['reply_to']}"
            quoted = "\n".join(f"> {line}" for line in entry["message"].splitlines())
            blocks.append(f"{heading}\n\n{quoted}")
        return "\n\n---\n\n".join(blocks)


class SharedNegotiation(SharedPrimitive):
    """Append-only transcript for alternating bilateral negotiation turns."""

    def __init__(self, subject: str):
        self.subject = subject

    @staticmethod
    def _value(value):
        return (
            AnswerRef(value.question_name) if hasattr(value, "question_name") else value
        )

    def record(
        self,
        action_question,
        amount_question,
        message_question,
        *,
        speaker="{{ agent.name }}",
        role="{{ agent.role }}",
    ) -> WriteStep:
        return WriteStep(
            self,
            "record",
            {
                "speaker": self._value(speaker),
                "role": self._value(role),
                "action": self._value(action_question),
                "amount": self._value(amount_question),
                "message": self._value(message_question),
            },
        )

    def initial(self):
        return {"turns": []}

    @property
    def is_terminal(self):
        from edsl.jobs.interview_schedule import GroupStopCondition

        return GroupStopCondition(self.name, "is_terminal_state")

    def is_terminal_state(self, state) -> bool:
        return any(turn["action"] in {"accept", "walk away"} for turn in state["turns"])

    def apply(self, state, op, args, interview_id):
        if op != "record":
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedNegotiation"
            )
        speaker = str(args["speaker"]).strip()
        role = str(args["role"]).strip().lower()
        action = str(args["action"]).strip().lower()
        message = str(args["message"]).strip()
        amount = args.get("amount")
        if role not in {"buyer", "seller"}:
            raise SharedStateAuthoringError("negotiation role must be buyer or seller")
        if action not in {"offer", "accept", "reject", "walk away"}:
            raise SharedStateAuthoringError(
                "negotiation action must be offer, accept, reject, or walk away"
            )
        if (
            isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or amount < 0
        ):
            raise SharedStateAuthoringError(
                f"negotiation amount must be a non-negative number; received {amount!r}"
            )
        role_round = 1 + sum(turn["role"] == role for turn in state["turns"])
        state["turns"].append(
            {
                "turn": len(state["turns"]) + 1,
                "round": role_round,
                "speaker": speaker,
                "role": role,
                "action": action,
                "amount": amount,
                "message": message,
                "interview": interview_id,
            }
        )
        return state

    def view(self, state, closed, context=None):
        turns = [
            {key: value for key, value in turn.items() if key != "interview"}
            for turn in state["turns"]
        ]
        agreement = None
        for index, turn in enumerate(turns):
            if turn["action"] == "accept":
                prior_offers = [t for t in turns[:index] if t["action"] == "offer"]
                if prior_offers:
                    agreement = prior_offers[-1]["amount"]
        return {
            "subject": self.subject,
            "turns": turns,
            "turn_count": len(turns),
            "agreement": agreement,
        }

    def to_dict(self):
        return {"type": "negotiation", "subject": self.subject}

    def render_markdown(self, view):
        lines = [f"**Subject:** {view['subject']}", ""]
        if not view["turns"]:
            return "\n".join(lines + ["_No offers yet._"])
        lines.extend(
            [
                "| Turn | Round | Speaker | Action | Amount | Message |",
                "|---:|---:|---|---|---:|---|",
            ]
        )
        for turn in view["turns"]:
            message = turn["message"].replace("|", "\\|").replace("\n", " ")
            lines.append(
                f"| {turn['turn']} | {turn['round']} | {turn['speaker']} ({turn['role']}) "
                f"| {turn['action']} | ${turn['amount']:g} | {message} |"
            )
        if view["agreement"] is not None:
            lines.extend(["", f"**Agreement:** ${view['agreement']:g}"])
        return "\n".join(lines)


class SharedAgenda(SharedPrimitive):
    """Shared proposal slate with matrix-based up, neutral, and down votes."""

    VOTE_VALUES = {"up": 1, "neutral": 0, "down": -1}

    def propose(self, question, *, proposer="{{ agent.name }}") -> WriteStep:
        return WriteStep(
            self,
            "propose",
            {
                "proposer": proposer,
                "title": AnswerRef(question.question_name),
            },
        )

    def vote(self, question, *, voter="{{ agent.name }}") -> WriteStep:
        if getattr(question, "question_type", None) != "matrix":
            raise SharedStateAuthoringError(
                f"agenda voting expects a matrix question; '{question.question_name}' "
                f"is {getattr(question, 'question_type', type(question).__name__)}"
            )
        if set(question.question_options) != set(self.VOTE_VALUES):
            raise SharedStateAuthoringError(
                "agenda matrix options must be up, neutral, and down"
            )
        return WriteStep(
            self,
            "vote",
            {"voter": voter, "votes": AnswerRef(question.question_name)},
        )

    def initial(self):
        return {"proposals": [], "ballots": []}

    def apply(self, state, op, args, interview_id):
        if op == "propose":
            title = str(args["title"]).strip()
            proposer = str(args["proposer"]).strip()
            if not title or not proposer:
                raise SharedStateAuthoringError(
                    "agenda proposals require a proposer and title"
                )
            item_id = f"A{len(state['proposals']) + 1}"
            state["proposals"].append(
                {"id": item_id, "title": title, "proposer": proposer}
            )
        elif op == "vote":
            votes = dict(args["votes"])
            item_ids = {item["id"] for item in state["proposals"]}
            if set(votes) != item_ids:
                raise SharedStateAuthoringError(
                    "agenda ballot must vote exactly once on every proposal"
                )
            invalid = {
                value for value in votes.values() if value not in self.VOTE_VALUES
            }
            if invalid:
                raise SharedStateAuthoringError(
                    f"invalid agenda vote values: {sorted(invalid)}"
                )
            state["ballots"].append(
                {
                    "voter": str(args["voter"]).strip(),
                    "votes": votes,
                    "interview": interview_id,
                }
            )
        else:
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedAgenda"
            )
        return state

    def view(self, state, closed, context=None):
        totals = {item["id"]: 0 for item in state["proposals"]}
        for ballot in state["ballots"]:
            for item_id, vote in ballot["votes"].items():
                totals[item_id] += self.VOTE_VALUES[vote]
        proposals = [
            item | {"score": totals[item["id"]]} for item in state["proposals"]
        ]
        return {
            "proposals": proposals,
            "ballots": [
                {"voter": ballot["voter"], "votes": dict(ballot["votes"])}
                for ballot in state["ballots"]
            ],
            "ballot_count": len(state["ballots"]),
        }

    def to_dict(self):
        return {"type": "agenda"}

    def render_markdown(self, view):
        if not view["proposals"]:
            return "_No agenda items proposed._"
        lines = [
            "| Rank | Item | Proposed by | Score |",
            "|---:|---|---|---:|",
        ]
        ranked = sorted(
            view["proposals"], key=lambda item: (-item["score"], item["id"])
        )
        for rank, item in enumerate(ranked, 1):
            lines.append(
                f"| {rank} | **{item['id']}** — {item['title']} | "
                f"{item['proposer']} | {item['score']:+d} |"
            )
        lines.extend(["", f"**Ballots cast:** {view['ballot_count']}"])
        return "\n".join(lines)


class SharedDelphiPanel(SharedPrimitive):
    """Anonymous repeated estimates with explicit convergence diagnostics."""

    def __init__(
        self,
        panel_size: int,
        range_threshold: float = 15,
        median_shift_threshold: float = 3,
        min_rounds: int = 2,
    ):
        if panel_size < 2 or min_rounds < 2:
            raise SharedStateAuthoringError(
                "Delphi panel_size and min_rounds must both be at least two"
            )
        if range_threshold < 0 or median_shift_threshold < 0:
            raise SharedStateAuthoringError(
                "Delphi convergence thresholds cannot be negative"
            )
        self.panel_size = int(panel_size)
        self.range_threshold = float(range_threshold)
        self.median_shift_threshold = float(median_shift_threshold)
        self.min_rounds = int(min_rounds)

    def submit(
        self,
        estimate_question,
        confidence_question,
        rationale_question,
        *,
        expert="{{ agent.name }}",
        round_number="{{ run.round }}",
    ) -> WriteStep:
        for question, label in (
            (estimate_question, "estimate"),
            (confidence_question, "confidence"),
        ):
            if getattr(question, "question_type", None) != "numerical":
                raise SharedStateAuthoringError(
                    f"Delphi {label} expects a numerical question"
                )
        if getattr(rationale_question, "question_type", None) != "free_text":
            raise SharedStateAuthoringError(
                "Delphi rationale expects a free-text question"
            )
        return WriteStep(
            self,
            "submit",
            {
                "expert": expert,
                "round": round_number,
                "estimate": AnswerRef(estimate_question.question_name),
                "confidence": AnswerRef(confidence_question.question_name),
                "rationale": AnswerRef(rationale_question.question_name),
            },
        )

    def initial(self):
        return {"responses": []}

    def apply(self, state, op, args, interview_id):
        if op != "submit":
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedDelphiPanel"
            )
        estimate, confidence = args["estimate"], args["confidence"]
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 <= value <= 100
            for value in (estimate, confidence)
        ):
            raise SharedStateAuthoringError(
                "Delphi estimate and confidence must be numbers from 0 to 100"
            )
        expert = str(args["expert"])
        round_number = int(args["round"])
        state["responses"] = [
            response
            for response in state["responses"]
            if not (response["expert"] == expert and response["round"] == round_number)
        ]
        state["responses"].append(
            {
                "expert": expert,
                "round": round_number,
                "estimate": float(estimate),
                "confidence": float(confidence),
                "rationale": str(args["rationale"]),
                "interview": interview_id,
            }
        )
        return state

    def _summaries(self, state):
        grouped = {}
        for response in state["responses"]:
            grouped.setdefault(response["round"], []).append(response)
        summaries = []
        for round_number, responses in sorted(grouped.items()):
            estimates = [response["estimate"] for response in responses]
            denominator = sum(response["confidence"] for response in responses)
            summaries.append(
                {
                    "round": round_number,
                    "response_count": len(responses),
                    "complete": len(responses) >= self.panel_size,
                    "mean": sum(estimates) / len(estimates),
                    "median": median(estimates),
                    "minimum": min(estimates),
                    "maximum": max(estimates),
                    "range": max(estimates) - min(estimates),
                    "confidence_weighted_mean": (
                        sum(
                            response["estimate"] * response["confidence"]
                            for response in responses
                        )
                        / denominator
                        if denominator
                        else None
                    ),
                    "anonymous_rationales": [
                        {
                            "estimate": response["estimate"],
                            "confidence": response["confidence"],
                            "rationale": response["rationale"],
                        }
                        for response in responses
                    ],
                }
            )
        return summaries

    def view(self, state, closed, context=None):
        summaries = self._summaries(state)
        viewer = (context or {}).get("name")
        result = {
            "rounds": summaries,
            "latest_complete_round": next(
                (item for item in reversed(summaries) if item["complete"]), None
            ),
            "converged": self.converged({"rounds": summaries}),
            "criteria": {
                "range_at_most": self.range_threshold,
                "median_shift_at_most": self.median_shift_threshold,
                "minimum_rounds": self.min_rounds,
            },
            "closed": closed,
        }
        if viewer:
            result["your_history"] = [
                {
                    key: value
                    for key, value in response.items()
                    if key not in {"expert", "interview"}
                }
                for response in state["responses"]
                if response["expert"] == viewer
            ]
        return result

    def converged(self, view):
        complete = [item for item in view.get("rounds", []) if item["complete"]]
        if len(complete) < self.min_rounds:
            return False
        latest, previous = complete[-1], complete[-2]
        return (
            latest["range"] <= self.range_threshold
            and abs(latest["median"] - previous["median"])
            <= self.median_shift_threshold
        )

    def to_dict(self):
        return {
            "type": "delphi_panel",
            "panel_size": self.panel_size,
            "range_threshold": self.range_threshold,
            "median_shift_threshold": self.median_shift_threshold,
            "min_rounds": self.min_rounds,
        }

    def render_markdown(self, view):
        rows = [
            "| Round | N | Mean | Median | Range | Weighted mean |",
            "|---:|---:|---:|---:|---:|---:|",
        ]
        rows.extend(
            f"| {item['round']} | {item['response_count']} | {item['mean']:.1f}% | "
            f"{item['median']:.1f}% | {item['range']:.1f} | "
            f"{item['confidence_weighted_mean']:.1f}% |"
            for item in view["rounds"]
        )
        rows.extend(["", f"**Converged:** {'Yes' if view['converged'] else 'No'}"])
        return "\n".join(rows)


class SharedForecast(SharedPrimitive):
    """A history of probabilistic forecasts with a live consensus view."""

    def submit(
        self,
        probability_question,
        confidence_question,
        *,
        forecaster="{{ agent.name }}",
        round_number="{{ run.round }}",
    ) -> WriteStep:
        for question, label in (
            (probability_question, "probability"),
            (confidence_question, "confidence"),
        ):
            if getattr(question, "question_type", None) != "numerical":
                raise SharedStateAuthoringError(
                    f"forecast {label} expects a numerical question; "
                    f"'{question.question_name}' is "
                    f"{getattr(question, 'question_type', type(question).__name__)}"
                )
        return WriteStep(
            self,
            "submit",
            {
                "forecaster": forecaster,
                "round": round_number,
                "probability": AnswerRef(probability_question.question_name),
                "confidence": AnswerRef(confidence_question.question_name),
            },
        )

    def initial(self):
        return {"forecasts": []}

    def apply(self, state, op, args, interview_id):
        if op != "submit":
            raise SharedStateAuthoringError(
                f"unknown operation '{op}' for SharedForecast"
            )
        probability = args["probability"]
        confidence = args["confidence"]
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 <= value <= 100
            for value in (probability, confidence)
        ):
            raise SharedStateAuthoringError(
                "forecast probability and confidence must be numbers from 0 to 100"
            )
        state["forecasts"].append(
            {
                "forecaster": str(args["forecaster"]),
                "round": int(args["round"]),
                "probability": probability,
                "confidence": confidence,
                "interview": interview_id,
            }
        )
        return state

    def view(self, state, closed, context=None):
        latest = {}
        for forecast in state["forecasts"]:
            latest[forecast["forecaster"]] = forecast
        probabilities = [forecast["probability"] for forecast in latest.values()]
        weighted_denominator = sum(
            forecast["confidence"] for forecast in latest.values()
        )
        weighted_probability = (
            sum(
                forecast["probability"] * forecast["confidence"]
                for forecast in latest.values()
            )
            / weighted_denominator
            if weighted_denominator
            else None
        )
        return {
            "latest": [
                {key: value for key, value in forecast.items() if key != "interview"}
                for forecast in latest.values()
            ],
            "history": [
                {key: value for key, value in forecast.items() if key != "interview"}
                for forecast in state["forecasts"]
            ],
            "mean_probability": sum(probabilities) / len(probabilities)
            if probabilities
            else None,
            "median_probability": median(probabilities) if probabilities else None,
            "confidence_weighted_probability": weighted_probability,
        }

    def to_dict(self):
        return {"type": "forecast"}

    def render_markdown(self, view):
        if not view["latest"]:
            return "_No forecasts submitted._"
        lines = [
            "| Forecaster | Round | Probability | Confidence |",
            "|---|---:|---:|---:|",
        ]
        for forecast in view["latest"]:
            lines.append(
                f"| {forecast['forecaster']} | {forecast['round']} | "
                f"{forecast['probability']:g}% | {forecast['confidence']:g}% |"
            )
        lines.extend(
            [
                "",
                f"**Mean forecast:** {view['mean_probability']:.1f}%  ",
                f"**Median forecast:** {view['median_probability']:.1f}%  ",
                "**Confidence-weighted forecast:** "
                f"{view['confidence_weighted_probability']:.1f}%",
            ]
        )
        return "\n".join(lines)
