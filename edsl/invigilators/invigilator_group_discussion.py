"""Invigilator that runs a staged multi-agent deliberation as one question task.

The question compiles to an ordered list of **stages** (see
``QuestionGroupDiscussion.resolved_stages``); this engine executes them in order,
accumulating a single flat transcript and a ledger of named decisions. A vote is
just a stage, so it can appear anywhere — to set the agenda, as a procedural
motion, to decide an item, or to ratify. An ``agenda`` stage expands its result
into the stages that follow (dynamic agenda).

Stage types handled: ``discussion``, ``consensus``, ``vote``, ``authority``,
``moderator``, ``agenda``, ``motion``. Deterministic vote tallying (veto, quorum,
tie-break and the whole method library) lives in ``group_discussion_voting``;
this file only collects ballots from model calls and parses them.
"""

from __future__ import annotations

import copy
import json
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..base.data_transfer_models import EDSLResultObjectInput
from ..questions.exceptions import QuestionAnswerValidationError
from .group_discussion_voting import Ballot, power_indices, tally
from .invigilators import InvigilatorBase

if TYPE_CHECKING:
    from ..base.data_transfer_models import AgentResponseDict, ModelResponse
    from ..prompts import Prompt


@dataclass
class TurnTrace:
    speaker: str
    round: int
    kind: str
    stage: str
    generated_text: str
    model_response: dict
    model_outputs: "ModelResponse"


class InvigilatorGroupDiscussion(InvigilatorBase):
    """Runs a staged deliberation as a single question task."""

    # ---- EDSL plumbing ------------------------------------------------------

    def get_prompts(self) -> Dict[str, "Prompt"]:
        from ..prompts import Prompt

        return {
            "user_prompt": Prompt(
                "Multi-agent deliberation managed internally by "
                "InvigilatorGroupDiscussion."
            ),
            "system_prompt": Prompt(
                "Each participant turn and ballot is a separate model call."
            ),
        }

    def _replacement_dict(self) -> dict[str, Any]:
        return (
            self.scenario
            | self.prompt_constructor.prior_answers_dict()
            | {"agent": self.agent.traits}
        )

    def _rendered_question(self):
        if "{{" in (self.question.question_text or ""):
            return self.question.render(self._replacement_dict())
        return self.question

    async def _call_model(
        self, *, user_prompt: str, system_prompt: str
    ) -> tuple[str, "AgentResponseDict"]:
        model = copy.copy(self.model)
        if self.key_lookup:
            model.set_key_lookup(self.key_lookup)
        response = await model.async_get_response(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            cache=self.cache,
            iteration=self.iteration,
            invigilator=self,
            question_type="free_text",
        )
        text = response.edsl_dict.answer or ""
        return str(text).strip(), response

    # ---- transcript helpers -------------------------------------------------

    @staticmethod
    def _text(turn: dict) -> str:
        return "\n".join(
            c.get("text", "") for c in turn.get("content", []) if isinstance(c, dict)
        ).strip()

    def _visible(self, viewer: Optional[str], anonymous: bool = False) -> str:
        """Format the transcript as this viewer may see it.

        Caucus turns tagged ``private_to`` are hidden from anyone not listed.
        Under ``anonymous`` the speaker identities are masked (Delphi).
        """
        rows = []
        for t in self._transcript:
            pv = t.get("private_to")
            if pv and viewer is not None and viewer not in pv:
                continue
            speaker = t.get("speaker", "?")
            if anonymous and t.get("kind") in ("discussion", "vote"):
                speaker = "a participant"
            tag = {
                "vote": "VOTE",
                "decision": "DECISION",
                "event": "EVENT",
                "caucus": "CAUCUS",
            }.get(t.get("kind"), None)
            prefix = f"[{tag}] " if tag else ""
            rows.append(f"{prefix}[r{t.get('round')}] {speaker}: {self._text(t)}")
        return "\n".join(rows) if rows else "(nothing said yet)"

    def _decisions_summary(self) -> str:
        if not self._decisions:
            return ""
        lines = [
            f"- {name}: {d.get('summary') or d.get('winner') or '(no decision)'}"
            for name, d in self._decisions.items()
        ]
        return "Decisions already made in this meeting:\n" + "\n".join(lines)

    def _record(self, speaker, rnd, kind, stage, text, response, private_to=None):
        self._traces.append(
            TurnTrace(
                speaker,
                rnd,
                kind,
                stage,
                text,
                response.model_outputs.response,
                response.model_outputs,
            )
        )
        turn = {
            "speaker": speaker,
            "round": rnd,
            "kind": kind,
            "stage": stage,
            "content": [{"type": "text", "text": text}],
        }
        if private_to:
            turn["private_to"] = list(private_to)
        self._transcript.append(turn)

    def _system_prompt(self, p: dict) -> str:
        pieces = [
            f"You are {p['name']}"
            + (f", the {p['role']}" if p.get("role") and p["role"] != "member" else "")
            + ", a participant in a group deliberation.",
            "Speak only as yourself, stay in character, and do not narrate others.",
        ]
        if p.get("persona"):
            pieces.append(f"About you: {p['persona']}")
        if p.get("goal"):
            pieces.append(f"Your goal: {p['goal']}")
        if p.get("private_info"):
            pieces.append(
                f"PRIVATE (only you know this; reveal strategically): {p['private_info']}"
            )
        return "\n\n".join(pieces)

    def _participants_for(self, stage, rq) -> List[dict]:
        if not stage["participants"]:
            return list(rq.participants)
        wanted = list(stage["participants"])
        chosen = [rq.participant_by_name(n) for n in wanted]
        return [p for p in chosen if p] or list(rq.participants)

    def _order(self, participants, salt=0):
        if getattr(self.question, "turn_order", "fixed") == "random":
            order = list(participants)
            random.Random((self.iteration or 0) * 997 + salt).shuffle(order)
            return order
        return participants

    # ---- ballot parsing -----------------------------------------------------

    @staticmethod
    def _match_option(text: str, options: List[str]) -> Optional[str]:
        if not text or not options:
            return None
        first = text.strip().splitlines()[0].strip().lower()
        full = text.strip().lower()
        for o in options:
            if first == o.lower():
                return o
        for o in options:
            if o.lower() in first or first in o.lower():
                return o
        for o in options:
            if o.lower() in full:
                return o
        return None

    def _parse_ballot(self, text, stage) -> Any:
        """Parse a voter's free text into the shape the method needs."""
        options = stage["options"] or []
        method = stage["method"]
        if method == "numeric":
            import re

            m = re.search(r"-?\d[\d,]*\.?\d*", text.replace(",", ""))
            return float(m.group()) if m else None
        if method == "approval":
            low = text.lower()
            approved = [o for o in options if o.lower() in low]
            return approved or ([self._match_option(text, options)] if options else [])
        if method == "ranked_choice":
            low = text.lower()
            found = [(low.index(o.lower()), o) for o in options if o.lower() in low]
            ranked = [o for _i, o in sorted(found)]
            # append any options not mentioned, preserving given order
            ranked += [o for o in options if o not in ranked]
            return ranked
        if method == "quadratic":
            alloc = {}
            for o in options:
                for line in text.splitlines():
                    if o.lower() in line.lower():
                        num = "".join(ch for ch in line if ch.isdigit() or ch == ".")
                        if num:
                            try:
                                alloc[o] = float(num)
                            except ValueError:
                                pass
            return alloc
        # single choice
        return self._match_option(text, options) if options else text.strip()

    @staticmethod
    def _parse_allocation(text, budget) -> Optional[Dict[str, float]]:
        """Pull 'label: $amount' pairs out of a decision and (optionally) scale
        them to sum to the budget."""
        import re

        pairs = re.findall(
            r"([A-Za-z][\w &/\-]*?)\s*[:=]\s*\$?\s*([\d,]+(?:\.\d+)?)", text
        )
        alloc = {}
        for label, amt in pairs:
            try:
                alloc[label.strip()] = float(amt.replace(",", ""))
            except ValueError:
                continue
        if not alloc:
            return None
        if budget:
            total = sum(alloc.values())
            if total and abs(total - budget) > 1e-6:
                alloc = {k: round(v * budget / total, 2) for k, v in alloc.items()}
        return alloc

    # ---- stage runners ------------------------------------------------------

    async def _run_discussion(self, stage, rq, participants, kind="discussion"):
        private_to = stage.get("private_to")
        instruction = stage["turn_instruction"] or self.question.turn_instruction
        for r in range(stage["rounds"]):
            self._round += 1
            for p in self._order(participants, salt=self._round):
                ctx = self._decisions_summary()
                topic = stage["prompt"] or rq.question_text
                usr = (
                    f"Premise:\n{rq.question_text}\n\n"
                    + (f"{ctx}\n\n" if ctx else "")
                    + (
                        f"This part of the meeting is about:\n{topic}\n\n"
                        if stage["prompt"]
                        else ""
                    )
                    + f"Transcript so far:\n{self._visible(p['name'], stage['anonymous'])}\n\n"
                    f"{instruction}\n\nYou are {p['name']}. Give only your own next "
                    f"contribution as plain text."
                )
                text, resp = await self._call_model(
                    user_prompt=usr, system_prompt=self._system_prompt(p)
                )
                self._record(
                    p["name"],
                    self._round,
                    kind,
                    stage["name"],
                    text,
                    resp,
                    private_to=private_to,
                )

    async def _run_moderator(self, stage, rq, extra=""):
        mod = rq.moderator
        self._round += 1
        usr = (
            f"You are {mod['name']}, {mod['persona']}.\n\n"
            f"Premise:\n{rq.question_text}\n\n"
            + (f"{self._decisions_summary()}\n\n" if self._decisions else "")
            + f"Question to resolve:\n{stage['prompt'] or rq.question_text}\n\n"
            f"Discussion so far:\n{self._visible(None)}\n\n"
            + (extra + "\n\n" if extra else "")
            + "Announce the decision in two to four sentences: state the concrete "
            "outcome plainly first, then one line of rationale. Do not introduce "
            "options the group never discussed."
        )
        text, resp = await self._call_model(
            user_prompt=usr,
            system_prompt=f"You are {mod['name']}, {mod['persona']}. You record what "
            f"the group decided; you do not advocate.",
        )
        self._record(mod["name"], self._round, "decision", stage["name"], text, resp)
        outcome = {"summary": text}
        if stage["outcome"] == "allocation":
            alloc = self._parse_allocation(text, stage.get("budget"))
            if alloc:
                outcome["allocation"] = alloc
        return outcome

    async def _run_consensus(self, stage, rq, participants):
        # One (or more) convergence rounds, then the moderator records the plan.
        conv = dict(stage)
        conv["turn_instruction"] = (
            "This is the convergence phase: move toward a shared plan everyone can "
            "accept. Name the compromises you will make and what you need in return. "
            "One short paragraph."
        )
        await self._run_discussion(conv, rq, participants)
        return await self._run_moderator(stage, rq)

    def _ballot_ask(self, stage, rq) -> str:
        options = stage["options"]
        if stage["method"] == "numeric":
            return (
                f"Give your best single numeric estimate for:\n"
                f"{stage['prompt'] or rq.question_text}\n"
                "Reply with the number on the first line, then one sentence why."
            )
        if not options:
            return (
                "State your final position in one or two sentences, making "
                "clear the concrete outcome you support."
            )
        opt_txt = "\n".join(f"- {o}" for o in options)
        if stage["method"] == "approval":
            return (
                f"Approve ALL options you find acceptable from:\n{opt_txt}\n"
                "List each acceptable option on its own line."
            )
        if stage["method"] == "ranked_choice":
            return (
                f"Rank ALL options best-to-worst from:\n{opt_txt}\n"
                "List them in order, best first, one per line."
            )
        if stage["method"] == "quadratic":
            return (
                f"You have 16 vote-credits; buying v votes for an option costs "
                f"v*v credits. Distribute across:\n{opt_txt}\n"
                "Write 'option: votes' lines."
            )
        return (
            f"Choose exactly ONE option from:\n{opt_txt}\n"
            "Put the chosen option on the first line, then one sentence why."
        )

    def _ballot_prompt(self, stage, rq, v) -> str:
        ask = self._ballot_ask(stage, rq)
        # Independent/secret ballot: don't show the running tally of other
        # members' votes (keeps large bodies O(n), models a recorded vote).
        if stage.get("independent"):
            discussion_block = ""
        else:
            discussion_block = (
                f"Discussion:\n{self._visible(v['name'], stage['anonymous'])}\n\n"
            )
        return (
            f"Premise:\n{rq.question_text}\n\n"
            + (f"{self._decisions_summary()}\n\n" if self._decisions else "")
            + f"Decision to vote on:\n{stage['prompt'] or rq.question_text}\n\n"
            + discussion_block
            + f"You are {v['name']}. {ask}"
        )

    async def _collect_ballots(self, stage, rq, voters) -> List[Ballot]:
        self._round += 1
        eligible = [
            v for v in self._order(voters, salt=self._round) if v.get("can_vote", True)
        ]

        async def one(v):
            text, resp = await self._call_model(
                user_prompt=self._ballot_prompt(stage, rq, v),
                system_prompt=self._system_prompt(v),
            )
            return v, text, resp

        if stage.get("independent"):
            # Independent ballots have no ordering dependency — run them with
            # bounded concurrency so a 400-member vote finishes in parallel.
            import asyncio

            sem = asyncio.Semaphore(int(stage.get("concurrency", 24) or 24))

            async def guarded(v):
                async with sem:
                    return await one(v)

            results = await asyncio.gather(*(guarded(v) for v in eligible))
        else:
            results = [await one(v) for v in eligible]

        ballots: List[Ballot] = []
        for v, text, resp in results:
            self._record(v["name"], self._round, "vote", stage["name"], text, resp)
            ballots.append(
                Ballot(
                    voter=v["name"],
                    choice=self._parse_ballot(text, stage),
                    weight=float(v.get("vote_weight", 1.0)),
                    holds_veto=bool(v.get("veto", False)),
                )
            )
        return ballots

    async def _run_vote(self, stage, rq, voters):
        ballots = await self._collect_ballots(stage, rq, voters)
        result = None
        if stage["options"] or stage["method"] == "numeric":
            result = tally(
                stage["method"],
                ballots,
                stage["options"],
                threshold=stage["threshold"],
                quorum=stage["quorum"],
                electorate=len([v for v in voters if v.get("can_vote", True)]),
                decider=stage["decider"],
                tie_breaker=stage["tie_breaker"],
                basis=stage.get("basis", "cast"),
            )
        # Independent/large votes: synthesize the result from the tally (no
        # moderator call over hundreds of ballots). Otherwise the moderator
        # announces and can resolve ties / free-form ballots.
        if stage.get("independent") and result is not None:
            verb = "passed" if result.decided else "did not pass"
            self._round += 1
            summary = f"The vote {verb}. {result.reason}"
            self._transcript.append(
                {
                    "speaker": rq.moderator["name"],
                    "round": self._round,
                    "kind": "decision",
                    "stage": stage["name"],
                    "content": [{"type": "text", "text": summary}],
                }
            )
            outcome = {"summary": summary}
        else:
            extra = ""
            if result is not None:
                extra = f"Vote result: {json.dumps(result.to_dict())}"
            outcome = await self._run_moderator(stage, rq, extra=extra)
        if result is not None:
            outcome.update(
                {
                    "method": stage["method"],
                    "winner": result.winner,
                    "decided": result.decided,
                    "counts": result.counts,
                    "vetoed_by": result.vetoed_by,
                    "quorum_met": result.quorum_met,
                    "reason": result.reason,
                    "detail": result.detail,
                }
            )
            # Voting-power analysis when weights differ (Shapley/Banzhaf).
            eligible = [v for v in voters if v.get("can_vote", True)]
            weights = {v["name"]: float(v.get("vote_weight", 1.0)) for v in eligible}
            if weights and (
                len(set(weights.values())) > 1 or stage["method"] == "weighted"
            ):
                total = sum(weights.values())
                if stage["method"] == "supermajority":
                    quota, strict = stage["threshold"] * total, False
                else:
                    quota, strict = total / 2, True
                pi = power_indices(weights, quota, strict=strict)
                if pi:
                    outcome["power"] = pi
        return outcome

    async def _run_authority(self, stage, rq, participants):
        who = stage["decider"]
        decider = rq.participant_by_name(who) if who else None
        if decider is None:
            return await self._run_moderator(stage, rq)
        self._round += 1
        usr = (
            f"Premise:\n{rq.question_text}\n\n"
            + (f"{self._decisions_summary()}\n\n" if self._decisions else "")
            + f"You must now decide:\n{stage['prompt'] or rq.question_text}\n\n"
            f"You have heard everyone. Transcript:\n{self._visible(decider['name'])}\n\n"
            "As the person with the authority to decide, state your decision in two "
            "to four sentences — the concrete outcome first, then your reasoning."
        )
        text, resp = await self._call_model(
            user_prompt=usr, system_prompt=self._system_prompt(decider)
        )
        self._record(
            decider["name"], self._round, "decision", stage["name"], text, resp
        )
        outcome = {"summary": text, "decided_by": decider["name"]}
        if stage["outcome"] == "allocation":
            alloc = self._parse_allocation(text, stage.get("budget"))
            if alloc:
                outcome["allocation"] = alloc
        return outcome

    async def _run_agenda(self, stage, rq, voters):
        """Vote to order candidate topics, then expand per_item into new stages."""
        ballots = await self._collect_ballots(stage, rq, voters)
        order: List[str] = []
        if stage["options"]:
            if stage["method"] == "ranked_choice":
                # order by Borda-like position sum across ballots
                score: Dict[str, float] = {o: 0.0 for o in stage["options"]}
                for b in ballots:
                    if isinstance(b.choice, list):
                        for i, o in enumerate(b.choice):
                            if o in score:
                                score[o] += len(b.choice) - i
                order = sorted(stage["options"], key=lambda o: -score[o])
            else:  # approval / plurality: by approval/first-choice count
                res = tally(
                    "approval" if stage["method"] == "approval" else "plurality",
                    ballots,
                    stage["options"],
                )
                counts = res.counts
                order = sorted(stage["options"], key=lambda o: -counts.get(o, 0))
            top_k = stage["top_k"] or len(order)
            order = order[:top_k]
        outcome = {"agenda": order, "summary": "Agenda set: " + ", ".join(order)}
        # Record the agenda as a decision turn (no extra model call needed).
        mod = rq.moderator
        self._round += 1
        self._transcript.append(
            {
                "speaker": mod["name"],
                "round": self._round,
                "kind": "decision",
                "stage": stage["name"],
                "content": [{"type": "text", "text": outcome["summary"]}],
            }
        )
        # Expand per_item template into concrete stages (in agenda order).
        expanded = []
        if stage.get("per_item"):
            from ..questions.question_group_discussion import _normalize_stage

            for i, item in enumerate(order):
                tmpl = json.loads(json.dumps(stage["per_item"]))  # deep copy
                tmpl["name"] = tmpl.get("name", "item").replace("{item}", item) or item
                if "{item}" not in (tmpl.get("name") or ""):
                    tmpl["name"] = f"{tmpl.get('name','item')}:{item}"
                tmpl["prompt"] = (tmpl.get("prompt", "") or "").replace(
                    "{item}", item
                ) or f"Decide on: {item}"
                expanded.append(_normalize_stage(tmpl, i))
        return outcome, expanded

    async def _run_motion(self, stage, rq, voters):
        """A procedural vote that changes flow (table/extend/amend), not the
        substantive outcome. Returns (outcome, flow_action)."""
        ballots = await self._collect_ballots(stage, rq, voters)
        result = tally(
            stage["method"],
            ballots,
            stage["options"] or ["aye", "nay"],
            threshold=stage["threshold"],
            quorum=stage["quorum"],
            tie_breaker=stage["tie_breaker"],
        )
        winner = (result.winner or "").lower() if result else ""
        action = None
        if any(k in winner for k in ("table", "postpone", "skip")):
            action = "skip_next"
        elif "extend" in winner:
            action = "extend_next"
        outcome = {
            "motion": stage["name"],
            "carried": result.decided if result else False,
            "winner": result.winner if result else None,
            "summary": result.reason if result else "",
            "flow_action": action,
        }
        self._round += 1
        self._transcript.append(
            {
                "speaker": rq.moderator["name"],
                "round": self._round,
                "kind": "decision",
                "stage": stage["name"],
                "content": [
                    {
                        "type": "text",
                        "text": f"Motion '{stage['name']}': {outcome['summary']}",
                    }
                ],
            }
        )
        return outcome, action

    async def _run_deliberate(self, stage, rq, participants):
        """Iterate discussion + straw poll until the rule is met (consensus) or
        positions stop moving for ``patience`` rounds (deadlock -> no decision)."""
        method = stage["method"] if stage["method"] != "plurality" else "unanimous"
        options = stage["options"]
        voters = [p for p in participants if p.get("can_vote", True)]
        prev = None
        stale = 0
        result = None
        rounds_used = 0
        for _rnd in range(stage["rounds"]):
            rounds_used += 1
            conv = dict(stage)
            conv["turn_instruction"] = (
                "Deliberate toward agreement: respond to others and say whether you "
                "could accept their position, and under what condition. One paragraph."
            )
            conv["rounds"] = 1
            await self._run_discussion(conv, rq, participants)
            ballots = await self._collect_ballots(stage, rq, voters)
            result = tally(
                method,
                ballots,
                options,
                threshold=stage["threshold"],
                quorum=stage["quorum"],
                electorate=len(voters),
                tie_breaker=stage["tie_breaker"],
            )
            positions = tuple(sorted((b.voter, str(b.choice)) for b in ballots))
            if result.decided:
                break  # consensus reached -> early stop
            stale = stale + 1 if positions == prev else 0
            prev = positions
            if stale >= stage["patience"]:
                break  # deadlock
        status = (
            "consensus reached"
            if (result and result.decided)
            else "deadlock — no decision (hung)"
        )
        outcome = await self._run_moderator(
            stage,
            rq,
            extra=f"Outcome: {status}. Final straw poll: "
            f"{json.dumps(result.to_dict()) if result else '{}'}",
        )
        if result:
            outcome.update(
                {
                    "method": method,
                    "winner": result.winner,
                    "decided": result.decided,
                    "counts": result.counts,
                    "rounds_used": rounds_used,
                    "status": status,
                }
            )
        return outcome

    async def _run_negotiation(self, stage, rq, participants):
        """Parties exchange numeric offers each round; a deal closes when the
        spread falls within ``tolerance``, else it is no-deal (BATNA/walk-away)."""
        import re

        latest: Dict[str, float] = {}
        walked: set = set()
        rounds_used = 0

        def spread_ok() -> bool:
            if len(latest) < 2:
                return False
            vals = list(latest.values())
            denom = max(abs(max(vals)), 1.0)
            return (max(vals) - min(vals)) / denom <= stage["tolerance"]

        for _rnd in range(stage["rounds"]):
            rounds_used += 1
            self._round += 1
            for p in self._order(participants, salt=self._round):
                table = (
                    "Offers on the table: "
                    + ", ".join(f"{k}: {v}" for k, v in latest.items())
                    if latest
                    else "No offers yet."
                )
                usr = (
                    f"Premise:\n{rq.question_text}\n\n"
                    f"{stage['prompt'] or ''}\n\n{table}\n\n"
                    f"Transcript:\n{self._visible(p['name'])}\n\n"
                    "State your CURRENT numeric offer. Put the number on the first "
                    "line (or write WALK to walk away for your better alternative), "
                    "then one sentence of rationale."
                )
                text, resp = await self._call_model(
                    user_prompt=usr, system_prompt=self._system_prompt(p)
                )
                self._record(p["name"], self._round, "vote", stage["name"], text, resp)
                head = text.strip().splitlines()[0].lower() if text.strip() else ""
                if "walk" in head:
                    walked.add(p["name"])
                else:
                    m = re.search(r"-?\d[\d,]*\.?\d*", text.replace(",", ""))
                    if m:
                        latest[p["name"]] = float(m.group())
            if walked or spread_ok():
                break

        deal = (not walked) and spread_ok()
        price = (
            round(sum(latest.values()) / len(latest), 2) if deal and latest else None
        )
        status = (
            f"DEAL at {price}"
            if deal
            else ("WALK-AWAY (no deal)" if walked else "NO DEAL (gap too wide)")
        )
        outcome = await self._run_moderator(
            stage, rq, extra=f"Final offers: {json.dumps(latest)}. Outcome: {status}."
        )
        outcome.update(
            {
                "deal": deal,
                "price": price,
                "final_offers": latest,
                "walked": sorted(walked),
                "rounds_used": rounds_used,
                "status": status,
            }
        )
        return outcome

    # ---- main loop ----------------------------------------------------------

    async def async_answer_question(self) -> EDSLResultObjectInput:
        rq = self._rendered_question()
        self._transcript: List[dict] = []
        self._traces: List[TurnTrace] = []
        self._decisions: Dict[str, Any] = {}
        self._round = 0
        exception_occurred = None
        validated = False

        try:
            queue = list(rq.resolved_stages())
            idx = 0
            while idx < len(queue):
                stage = queue[idx]
                idx += 1
                participants = self._participants_for(stage, rq)

                # Injected event announced before the stage runs.
                if stage.get("event"):
                    self._round += 1
                    self._transcript.append(
                        {
                            "speaker": "narrator",
                            "round": self._round,
                            "kind": "event",
                            "stage": stage["name"],
                            "content": [{"type": "text", "text": stage["event"]}],
                        }
                    )

                stype = stage["type"]
                if stype == "discussion":
                    kind = "caucus" if stage.get("private_to") else "discussion"
                    await self._run_discussion(stage, rq, participants, kind=kind)
                elif stype == "consensus":
                    self._decisions[stage["name"]] = await self._run_consensus(
                        stage, rq, participants
                    )
                elif stype == "moderator":
                    self._decisions[stage["name"]] = await self._run_moderator(
                        stage, rq
                    )
                elif stype == "authority":
                    self._decisions[stage["name"]] = await self._run_authority(
                        stage, rq, participants
                    )
                elif stype == "vote":
                    self._decisions[stage["name"]] = await self._run_vote(
                        stage, rq, participants
                    )
                elif stype == "deliberate":
                    self._decisions[stage["name"]] = await self._run_deliberate(
                        stage, rq, participants
                    )
                elif stype == "negotiation":
                    self._decisions[stage["name"]] = await self._run_negotiation(
                        stage, rq, participants
                    )
                elif stype == "agenda":
                    outcome, expanded = await self._run_agenda(stage, rq, participants)
                    self._decisions[stage["name"]] = outcome
                    queue[idx:idx] = expanded  # insert agenda items next
                elif stype == "motion":
                    outcome, action = await self._run_motion(stage, rq, participants)
                    self._decisions[stage["name"]] = outcome
                    if action == "skip_next" and idx < len(queue):
                        queue.pop(idx)
                    elif action == "extend_next" and idx < len(queue):
                        queue[idx]["rounds"] = queue[idx].get("rounds", 1) + 1

            generated_tokens = json.dumps(
                {
                    "transcript": self._transcript,
                    "decisions": self._decisions,
                    "turns": [self._trace_dict(t) for t in self._traces],
                }
            )
            validated_answer = rq._validate_answer(
                {"answer": self._transcript, "generated_tokens": generated_tokens}
            )
            answer = validated_answer["answer"]
            comment = self._final_comment()
            validated = True
        except QuestionAnswerValidationError as e:
            answer, comment, exception_occurred = None, "Transcript not valid.", e
            generated_tokens = json.dumps({"transcript": self._transcript})
        except Exception as e:
            answer, comment, exception_occurred = None, "Deliberation failed.", e
            generated_tokens = json.dumps({"transcript": self._transcript})

        self.generated_tokens = generated_tokens
        self.raw_model_response = [t.model_response for t in self._traces]
        return EDSLResultObjectInput(
            **self._result_data(
                answer, comment, generated_tokens, validated, exception_occurred
            )
        )

    # ---- assembly helpers ---------------------------------------------------

    def _final_comment(self) -> str:
        parts = []
        for name, d in self._decisions.items():
            s = d.get("summary") or d.get("winner") or "(no decision)"
            parts.append(f"[{name}] {s}")
        return "  ".join(parts)

    @staticmethod
    def _trace_dict(t: TurnTrace) -> dict:
        mo = t.model_outputs
        return {
            "speaker": t.speaker,
            "round": t.round,
            "kind": t.kind,
            "stage": t.stage,
            "generated_text": t.generated_text,
            "cache_used": mo.cache_used,
            "cache_key": mo.cache_key,
            "input_tokens": mo.input_tokens,
            "output_tokens": mo.output_tokens,
            "thinking_tokens": mo.thinking_tokens,
            "total_cost": mo.total_cost,
        }

    @staticmethod
    def _sum(values):
        nums = [v for v in values if isinstance(v, (int, float))]
        return sum(nums) if nums else None

    def _result_data(self, answer, comment, generated_tokens, validated, exc) -> dict:
        tr = self._traces
        return {
            "answer": answer,
            "comment": comment,
            "generated_tokens": generated_tokens,
            "question_name": self.question.question_name,
            "prompts": self.get_prompts(),
            "cached_response": [t.model_outputs.cached_response for t in tr],
            "raw_model_response": self.raw_model_response,
            "cache_used": any(t.model_outputs.cache_used for t in tr),
            "cache_key": [t.model_outputs.cache_key for t in tr],
            "validated": validated,
            "exception_occurred": exc,
            "input_tokens": self._sum([t.model_outputs.input_tokens for t in tr]),
            "output_tokens": self._sum([t.model_outputs.output_tokens for t in tr]),
            "thinking_tokens": self._sum([t.model_outputs.thinking_tokens for t in tr]),
            "input_price_per_million_tokens": (
                tr[0].model_outputs.input_price_per_million_tokens if tr else None
            ),
            "output_price_per_million_tokens": (
                tr[0].model_outputs.output_price_per_million_tokens if tr else None
            ),
            "total_cost": self._sum([t.model_outputs.total_cost for t in tr]),
        }
