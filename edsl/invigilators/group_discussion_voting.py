"""Deterministic voting / aggregation library for group-discussion decisions.

Pure functions with no LLM and no EDSL dependencies, so they are fast and fully
unit-testable. The group-discussion invigilator collects ballots from model
calls, then hands them here to produce an auditable outcome.

A ``Ballot`` carries one voter's expressed preference, the shape of which depends
on the method:

- single choice (plurality/majority/supermajority/weighted/unanimous/authority):
  ``choice`` is an option string (or ``None`` to abstain).
- approval:        ``choice`` is a list of approved option strings.
- ranked_choice:   ``choice`` is an ordered list of option strings (best first).
- quadratic:       ``choice`` is a dict ``{option: credits}``.

Every method returns a ``VoteResult`` with ``decided`` (did it resolve?),
``winner`` (the chosen option, or ``None``), the ``counts`` it was based on, and
a human-readable ``reason`` — plus quorum and veto bookkeeping.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Dict, List, Optional


@dataclass
class Ballot:
    voter: str
    choice: Any = None  # str | list | dict | None  (None = abstain)
    weight: float = 1.0
    holds_veto: bool = False

    def is_abstain(self) -> bool:
        if self.choice is None:
            return True
        if isinstance(self.choice, (list, dict)) and not self.choice:
            return True
        return False


@dataclass
class VoteResult:
    method: str
    decided: bool
    winner: Any = None
    counts: Dict[str, float] = field(default_factory=dict)
    quorum_met: bool = True
    vetoed_by: Optional[str] = None
    reason: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "decided": self.decided,
            "winner": self.winner,
            "counts": self.counts,
            "quorum_met": self.quorum_met,
            "vetoed_by": self.vetoed_by,
            "reason": self.reason,
            "detail": self.detail,
        }


def _cast_ballots(ballots: List[Ballot]) -> List[Ballot]:
    return [b for b in ballots if not b.is_abstain()]


def _quorum_met(ballots: List[Ballot], quorum: float, electorate: int) -> bool:
    """quorum as an int = minimum voters; as a float in (0,1] = fraction."""
    if not quorum:
        return True
    present = len(_cast_ballots(ballots))
    if 0 < quorum <= 1:
        need = math.ceil(quorum * max(electorate, 1))
    else:
        need = int(quorum)
    return present >= need


def _apply_veto(winner: Optional[str], ballots: List[Ballot]) -> Optional[str]:
    """Return the name of a veto-holder blocking ``winner`` (not supporting it)."""
    if winner is None:
        return None
    for b in ballots:
        if not b.holds_veto or b.is_abstain():
            continue
        # single-choice: a veto-holder who did not back the winner blocks it.
        if isinstance(b.choice, str) and b.choice != winner:
            return b.voter
        if isinstance(b.choice, list) and winner not in b.choice:
            return b.voter
    return None


def tally(
    method: str,
    ballots: List[Ballot],
    options: Optional[List[str]] = None,
    *,
    threshold: Optional[float] = None,
    quorum: float = 0,
    electorate: Optional[int] = None,
    decider: Optional[str] = None,
    tie_breaker: Optional[str] = None,
    basis: str = "cast",
) -> VoteResult:
    """Resolve ``ballots`` under ``method`` into a :class:`VoteResult`.

    Args:
        method: one of plurality, majority, supermajority, unanimous, weighted,
            approval, ranked_choice, quadratic, authority.
        options: the ballot options (required except for authority/ranked where
            it is inferred from ballots if omitted).
        threshold: fraction required for supermajority (e.g. 0.667) or majority
            override; ignored by methods that don't use it.
        quorum: minimum participation (int voters, or fraction of electorate).
        electorate: total eligible voters (for fractional quorum); defaults to
            the ballot count.
        decider: for ``authority`` — whose ballot is binding.
        tie_breaker: voter whose choice breaks an exact tie, if any.
        basis: ``"cast"`` (default) counts the threshold against ballots cast;
            ``"electorate"`` counts it against the full membership weight, so
            abstentions and absences count against the bar (parliamentary
            investiture: an absolute majority of all members).
    """
    electorate = electorate if electorate is not None else len(ballots)
    quorum_ok = _quorum_met(ballots, quorum, electorate)
    if not quorum_ok:
        return VoteResult(
            method=method,
            decided=False,
            quorum_met=False,
            reason=f"Quorum not met ({len(_cast_ballots(ballots))} present).",
        )

    # Full-membership weight: every ballot's weight (incl. abstentions/absences).
    electorate_weight = sum(b.weight for b in ballots)

    fn = _METHODS.get(method)
    if fn is None:
        raise ValueError(f"Unknown vote method: {method!r}")
    result = fn(
        ballots,
        options or [],
        threshold=threshold,
        decider=decider,
        tie_breaker=tie_breaker,
        basis=basis,
        electorate_weight=electorate_weight,
    )

    # Veto applies to any method that produced a single-option winner.
    if result.decided and isinstance(result.winner, str):
        blocker = _apply_veto(result.winner, ballots)
        if blocker is not None:
            result.decided = False
            result.vetoed_by = blocker
            result.reason = f"'{result.winner}' vetoed by {blocker}."
    return result


# ---- individual methods -----------------------------------------------------


def _count_first(ballots: List[Ballot]) -> Dict[str, float]:
    counts: Dict[str, float] = defaultdict(float)
    for b in _cast_ballots(ballots):
        choice = b.choice[0] if isinstance(b.choice, list) else b.choice
        counts[choice] += 1
    return dict(counts)


def _weighted_first(ballots: List[Ballot]) -> Dict[str, float]:
    counts: Dict[str, float] = defaultdict(float)
    for b in _cast_ballots(ballots):
        choice = b.choice[0] if isinstance(b.choice, list) else b.choice
        counts[choice] += b.weight
    return dict(counts)


def _winner_from_counts(
    counts: Dict[str, float], tie_breaker_choice: Optional[str] = None
):
    if not counts:
        return None, []
    top = max(counts.values())
    winners = sorted([o for o, c in counts.items() if c == top])
    if len(winners) == 1:
        return winners[0], winners
    if tie_breaker_choice in winners:
        return tie_breaker_choice, winners
    return None, winners


def _tie_breaker_choice(ballots: List[Ballot], tie_breaker: Optional[str]):
    if not tie_breaker:
        return None
    for b in ballots:
        if b.voter == tie_breaker and not b.is_abstain():
            return b.choice[0] if isinstance(b.choice, list) else b.choice
    return None


def _m_plurality(ballots, options, *, tie_breaker=None, **_):
    counts = _count_first(ballots)
    tb = _tie_breaker_choice(ballots, tie_breaker)
    winner, winners = _winner_from_counts(counts, tb)
    if winner is not None:
        return VoteResult(
            "plurality", True, winner, counts, reason=f"Plurality winner: {winner}."
        )
    return VoteResult(
        "plurality",
        False,
        None,
        counts,
        reason=f"Tie among {winners}.",
        detail={"tie": winners},
    )


def _m_majority(ballots, options, *, tie_breaker=None, **_):
    counts = _count_first(ballots)
    total = sum(counts.values())
    winner, winners = _winner_from_counts(
        counts, _tie_breaker_choice(ballots, tie_breaker)
    )
    if winner is not None and total and counts[winner] > total / 2:
        return VoteResult(
            "majority",
            True,
            winner,
            counts,
            reason=f"{winner} has a majority ({counts[winner]}/{total}).",
        )
    return VoteResult(
        "majority", False, None, counts, reason="No option has a strict majority."
    )


def _m_supermajority(ballots, options, *, threshold=None, tie_breaker=None, **_):
    threshold = threshold if threshold is not None else 0.667
    counts = _count_first(ballots)
    total = sum(counts.values())
    if not total:
        return VoteResult("supermajority", False, None, counts, reason="No votes.")
    winner, _ = _winner_from_counts(counts, _tie_breaker_choice(ballots, tie_breaker))
    # Snap the threshold to a simple fraction (0.667 -> 2/3) and compare with
    # exact integer cross-multiplication, so "two-thirds of 3" counts 2 as enough.
    frac = Fraction(threshold).limit_denominator(100)
    meets = winner is not None and (
        counts[winner] * frac.denominator >= frac.numerator * total
    )
    if meets:
        return VoteResult(
            "supermajority",
            True,
            winner,
            counts,
            reason=f"{winner} reached {threshold:.0%} " f"({counts[winner]}/{total}).",
            detail={"threshold": threshold},
        )
    return VoteResult(
        "supermajority",
        False,
        None,
        counts,
        reason=f"No option reached the {threshold:.0%} threshold.",
        detail={"threshold": threshold},
    )


def _m_unanimous(ballots, options, **_):
    cast = _cast_ballots(ballots)
    counts = _count_first(ballots)
    chosen = {b.choice[0] if isinstance(b.choice, list) else b.choice for b in cast}
    abstained = len(cast) < len(ballots)
    if len(chosen) == 1 and not abstained:
        w = next(iter(chosen))
        return VoteResult(
            "unanimous",
            True,
            w,
            counts,
            reason="Unanimous.",
            detail={"unanimous": True},
        )
    return VoteResult(
        "unanimous",
        False,
        None,
        counts,
        reason="Not unanimous." + (" (abstentions present)" if abstained else ""),
        detail={"unanimous": False, "positions": sorted(chosen)},
    )


def _m_weighted(
    ballots,
    options,
    *,
    threshold=None,
    tie_breaker=None,
    basis="cast",
    electorate_weight=0,
    **_,
):
    counts = _weighted_first(ballots)
    cast_total = sum(counts.values())
    winner, winners = _winner_from_counts(
        counts, _tie_breaker_choice(ballots, tie_breaker)
    )
    if winner is None:
        return VoteResult(
            "weighted",
            False,
            None,
            counts,
            reason=f"Weighted tie among {winners}.",
            detail={"tie": winners},
        )

    # Base the threshold on the full membership (abstentions count against it)
    # when basis == "electorate"; otherwise on the weight actually cast.
    base_total = electorate_weight if basis == "electorate" else cast_total

    if threshold is None:
        return VoteResult(
            "weighted",
            True,
            winner,
            counts,
            reason=f"{winner} has the most weight ({counts[winner]}/{base_total}).",
            detail={"basis": basis, "base_total": base_total},
        )

    # With an explicit threshold: a simple majority needs a strict half; any
    # higher bar (e.g. 2/3) uses exact-fraction comparison.
    if abs(threshold - 0.5) < 1e-9:
        meets = counts[winner] > base_total / 2
        label = "absolute majority"
    else:
        frac = Fraction(threshold).limit_denominator(100)
        meets = counts[winner] * frac.denominator >= frac.numerator * base_total
        label = f"{threshold:.0%}"
    need = (
        int(base_total // 2) + 1
        if abs(threshold - 0.5) < 1e-9
        else math.ceil(threshold * base_total)
    )
    return VoteResult(
        "weighted",
        bool(meets),
        winner if meets else None,
        counts,
        reason=(
            f"{winner} {counts[winner]:.0f} vs {label} bar {need} "
            f"of {base_total:.0f} ({basis}) — "
            f"{'reached' if meets else 'not reached'}."
        ),
        detail={
            "basis": basis,
            "base_total": base_total,
            "needed": need,
            "winner_weight": counts[winner],
        },
    )


def _m_approval(ballots, options, *, tie_breaker=None, **_):
    counts: Dict[str, float] = defaultdict(float)
    for b in _cast_ballots(ballots):
        approved = b.choice if isinstance(b.choice, list) else [b.choice]
        for o in approved:
            counts[o] += 1
    winner, winners = _winner_from_counts(
        dict(counts), _tie_breaker_choice(ballots, tie_breaker)
    )
    if winner is not None:
        return VoteResult(
            "approval",
            True,
            winner,
            dict(counts),
            reason=f"{winner} has the most approvals.",
        )
    return VoteResult(
        "approval",
        False,
        None,
        dict(counts),
        reason=f"Approval tie among {winners}.",
        detail={"tie": winners},
    )


def _m_ranked_choice(ballots, options, **_):
    """Instant-runoff: eliminate the lowest first-choice until one has >50%."""
    cast = _cast_ballots(ballots)
    rankings = [list(b.choice) for b in cast if isinstance(b.choice, list) and b.choice]
    if not rankings:
        return VoteResult("ranked_choice", False, None, {}, reason="No rankings.")
    eliminated: set = set()
    rounds = []
    while True:
        counts: Dict[str, float] = defaultdict(float)
        for r in rankings:
            top = next((c for c in r if c not in eliminated), None)
            if top is not None:
                counts[top] += 1
        total = sum(counts.values())
        rounds.append(dict(counts))
        if not total:
            return VoteResult(
                "ranked_choice",
                False,
                None,
                dict(counts),
                reason="All candidates eliminated.",
                detail={"rounds": rounds},
            )
        leader = max(counts, key=counts.get)
        if counts[leader] > total / 2:
            return VoteResult(
                "ranked_choice",
                True,
                leader,
                dict(counts),
                reason=f"{leader} wins IRV with a majority.",
                detail={"rounds": rounds},
            )
        # eliminate the lowest; stop if everyone remaining is tied
        active = {o: c for o, c in counts.items()}
        low = min(active.values())
        losers = [o for o, c in active.items() if c == low]
        if len(losers) == len(active):
            return VoteResult(
                "ranked_choice",
                False,
                None,
                dict(counts),
                reason=f"Deadlocked tie among {sorted(active)}.",
                detail={"rounds": rounds},
            )
        for o in losers:
            eliminated.add(o)


def _m_quadratic(ballots, options, **_):
    """Quadratic voting: a ballot's dict maps option -> votes bought; the cost of
    v votes is v**2 credits (enforcement is the caller's concern). We sum the
    net votes per option and pick the max."""
    counts: Dict[str, float] = defaultdict(float)
    for b in _cast_ballots(ballots):
        if isinstance(b.choice, dict):
            for o, v in b.choice.items():
                counts[o] += float(v)
    winner, winners = _winner_from_counts(dict(counts))
    if winner is not None:
        return VoteResult(
            "quadratic",
            True,
            winner,
            dict(counts),
            reason=f"{winner} has the most quadratic votes.",
        )
    return VoteResult(
        "quadratic",
        False,
        None,
        dict(counts),
        reason=f"Quadratic tie among {winners}.",
        detail={"tie": winners},
    )


def _m_numeric(ballots, options, **_):
    """Delphi-style numeric aggregation: each ballot is a number; the group
    estimate is the median (robust to outliers)."""
    vals = []
    for b in _cast_ballots(ballots):
        try:
            vals.append(float(b.choice))
        except (TypeError, ValueError):
            continue
    if not vals:
        return VoteResult("numeric", False, None, {}, reason="No numeric estimates.")
    median = statistics.median(vals)
    detail = {
        "n": len(vals),
        "median": median,
        "mean": round(statistics.fmean(vals), 4),
        "stdev": round(statistics.pstdev(vals), 4) if len(vals) > 1 else 0.0,
        "min": min(vals),
        "max": max(vals),
    }
    return VoteResult(
        "numeric",
        True,
        median,
        {"median": median},
        reason=f"Median estimate {median} (n={len(vals)}).",
        detail=detail,
    )


def _m_authority(ballots, options, *, decider=None, **_):
    for b in ballots:
        if b.voter == decider and not b.is_abstain():
            choice = b.choice[0] if isinstance(b.choice, list) else b.choice
            return VoteResult(
                "authority",
                True,
                choice,
                {choice: 1},
                reason=f"Decided by {decider}.",
                detail={"decider": decider},
            )
    return VoteResult(
        "authority", False, None, {}, reason=f"Authority {decider} made no decision."
    )


_METHODS = {
    "plurality": _m_plurality,
    "majority": _m_majority,
    "supermajority": _m_supermajority,
    "unanimous": _m_unanimous,
    "weighted": _m_weighted,
    "approval": _m_approval,
    "ranked_choice": _m_ranked_choice,
    "quadratic": _m_quadratic,
    "numeric": _m_numeric,
    "authority": _m_authority,
}

VOTE_METHODS = tuple(_METHODS.keys())


# ---- voting power indices ---------------------------------------------------


def power_indices(
    weights: Dict[str, float], quota: float, *, strict: bool = True
) -> Optional[Dict[str, Any]]:
    """Banzhaf and Shapley-Shubik voting-power indices for a weighted body.

    A coalition *wins* when its summed weight passes ``quota`` (``> quota`` when
    ``strict``, else ``>= quota``). A member is a *swing* for a coalition of the
    others when adding them turns a loss into a win. Both indices are returned
    normalized to sum to 1. Enumerates subsets, so it is exact for up to ~16
    members and returns ``None`` beyond that.
    """
    players = list(weights)
    n = len(players)
    if n == 0:
        return None
    if n > 16:
        return {"note": f"power indices skipped (n={n} too large to enumerate)"}

    def wins(total: float) -> bool:
        return total > quota if strict else total >= quota - 1e-9

    fact = math.factorial
    banzhaf = {p: 0 for p in players}
    shapley = {p: 0.0 for p in players}
    others = {p: [q for q in players if q != p] for p in players}

    for p in players:
        wp = weights[p]
        rest = others[p]
        m = len(rest)
        for mask in range(1 << m):
            coalition_w = 0.0
            size = 0
            for j in range(m):
                if mask & (1 << j):
                    coalition_w += weights[rest[j]]
                    size += 1
            if not wins(coalition_w) and wins(coalition_w + wp):
                banzhaf[p] += 1
                shapley[p] += fact(size) * fact(n - size - 1) / fact(n)

    total_swings = sum(banzhaf.values())
    banzhaf_norm = (
        {p: round(v / total_swings, 4) for p, v in banzhaf.items()}
        if total_swings
        else {p: 0.0 for p in players}
    )
    shapley_norm = {p: round(v, 4) for p, v in shapley.items()}
    return {
        "quota": quota,
        "strict": strict,
        "banzhaf": banzhaf_norm,
        "shapley_shubik": shapley_norm,
    }
