"""Build the PDF report for the repeated shared-state activity poll."""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
from PIL import Image


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "shared-state-activity-poll-repeated.json"
BUILD_DIR = ROOT / "shared-state-path-dependence-report-build"
TEX_PATH = BUILD_DIR / "shared_state_path_dependence_report.tex"
PDF_PATH = ROOT / "shared_state_path_dependence_report.pdf"

ACTIVITIES = ("bike ride", "sailing", "hike", "beach day")
COLORS = {
    "bike ride": "#2563EB",
    "sailing": "#0891B2",
    "hike": "#16A34A",
    "beach day": "#EA580C",
}


def latex_escape(value: object) -> str:
    text = str(value)
    for old, new in (
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
    ):
        text = text.replace(old, new)
    return text


def cumulative_paths(vote_sequence: list[dict[str, object]]) -> dict[str, list[int]]:
    totals = Counter()
    paths = {activity: [0] for activity in ACTIVITIES}
    for vote in vote_sequence:
        totals[str(vote["choice"])] += 1
        for activity in ACTIVITIES:
            paths[activity].append(totals[activity])
    return paths


def make_figures(data: dict[str, object]) -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )

    frequencies = data["winner_frequency"]
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    values = [frequencies.get(activity, 0) for activity in ACTIVITIES]
    bars = ax.bar(
        ACTIVITIES,
        values,
        color=[COLORS[activity] for activity in ACTIVITIES],
        width=0.68,
    )
    ax.set_ylabel("Runs won")
    ax.set_ylim(0, max(values) + 1)
    ax.set_title("Different activities win despite balanced starting preferences", loc="left", weight="bold")
    ax.grid(axis="y", color="#E5E7EB", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.bar_label(bars, padding=3, fontsize=10, weight="bold")
    fig.tight_layout()
    winner_path = BUILD_DIR / "winner_frequency.png"
    fig.savefig(
        winner_path,
        dpi=180,
        bbox_inches="tight",
        facecolor="white",
        transparent=False,
    )
    plt.close(fig)
    with Image.open(winner_path) as image:
        image.convert("RGB").save(winner_path)

    fig, axes = plt.subplots(5, 2, figsize=(7.4, 11), sharex=True, sharey=True)
    for ax, run in zip(axes.flat, data["runs"], strict=True):
        paths = cumulative_paths(run["vote_sequence"])
        for activity in ACTIVITIES:
            ax.plot(
                range(17),
                paths[activity],
                label=activity,
                color=COLORS[activity],
                linewidth=2,
            )
        winner = ", ".join(run["winners"])
        ax.set_title(f"Run {run['run']}: {winner} wins ({run['winning_count']}/16)", loc="left", fontsize=9, weight="bold")
        ax.set_xlim(0, 16)
        ax.set_ylim(0, 16)
        ax.set_xticks((0, 4, 8, 12, 16))
        ax.set_yticks((0, 4, 8, 12, 16))
        ax.grid(color="#E5E7EB", linewidth=0.6)
    for ax in axes[-1, :]:
        ax.set_xlabel("Vote / state version")
    for ax in axes[:, 0]:
        ax.set_ylabel("Cumulative votes")
    handles = [plt.Line2D([0], [0], color=COLORS[a], lw=2.5) for a in ACTIVITIES]
    fig.legend(handles, ACTIVITIES, loc="lower center", ncol=4, frameon=False)
    fig.suptitle("The ten realized vote paths", x=0.08, ha="left", fontsize=14, weight="bold")
    fig.tight_layout(rect=(0, 0.035, 1, 0.975))
    paths_path = BUILD_DIR / "vote_paths.png"
    fig.savefig(
        paths_path,
        dpi=180,
        bbox_inches="tight",
        facecolor="white",
        transparent=False,
    )
    plt.close(fig)
    with Image.open(paths_path) as image:
        image.convert("RGB").save(paths_path)


def build_tex(data: dict[str, object]) -> str:
    runs = data["runs"]
    mean_winning_count = sum(run["winning_count"] for run in runs) / len(runs)
    preference_rate = sum(
        vote["followed_preference"] for run in runs for vote in run["vote_sequence"]
    ) / sum(len(run["vote_sequence"]) for run in runs)

    early_leader_matches = 0
    rows = []
    for run in runs:
        early = Counter(run["first_three_votes"])
        early_max = max(early.values())
        early_leaders = {name for name, count in early.items() if count == early_max}
        if early_leaders.intersection(run["winners"]):
            early_leader_matches += 1
        counts = run["counts"]
        rows.append(
            " & ".join(
                [
                    str(run["run"]),
                    latex_escape(", ".join(run["first_three_votes"])),
                    *(str(counts[a]) for a in ACTIVITIES),
                    latex_escape(", ".join(run["winners"])),
                ]
            )
            + r" \\"
        )

    winner_summary = ", ".join(
        f"{activity}: {data['winner_frequency'].get(activity, 0)}"
        for activity in ACTIVITIES
    )

    return rf"""\documentclass[11pt]{{article}}
\usepackage[margin=0.8in]{{geometry}}
\usepackage{{fontspec}}
\setmainfont{{Avenir Next}}
\setsansfont{{Avenir Next}}
\usepackage{{booktabs}}
\usepackage{{graphicx}}
\usepackage{{xcolor}}
\usepackage{{hyperref}}
\usepackage{{microtype}}
\usepackage{{enumitem}}
\usepackage{{fancyhdr}}
\definecolor{{navy}}{{HTML}}{{15324A}}
\definecolor{{muted}}{{HTML}}{{536471}}
\definecolor{{panel}}{{HTML}}{{F2F6F8}}
\hypersetup{{colorlinks=true,linkcolor=navy,urlcolor=navy}}
\pagestyle{{fancy}}
\fancyhf{{}}
\lhead{{\small Shared-state activity poll}}
\rhead{{\small \thepage}}
\renewcommand{{\headrulewidth}}{{0.3pt}}
\setlength{{\parindent}}{{0pt}}
\setlength{{\parskip}}{{0.6em}}
\setlist{{nosep,leftmargin=1.4em}}

\begin{{document}}

{{\color{{navy}}\LARGE\bfseries Path Dependence in a Shared-State Activity Poll}}

\vspace{{0.4em}}
{{\Large Ten repeated EDSL simulations with sequentially visible votes}}

\vspace{{1.2em}}
\colorbox{{panel}}{{\parbox{{0.94\linewidth}}{{
\textbf{{Main result.}} The same balanced preference distribution produced four different
winners. Winner frequency was {latex_escape(winner_summary)}. Once an early lead formed,
later agents' desire to join the group often amplified it into a large majority.
}}}}

\section*{{Research question}}

Can sequentially visible choices produce different collective outcomes when the group's
underlying activity preferences begin balanced? This demonstration repeats the same
shared-state survey ten times. It is designed to make the mechanism observable: every
agent reads the current vote register, answers once, and writes one vote.

\section*{{Experimental design}}

Each run contains 16 simulated participants and four activities: \textit{{bike ride}},
\textit{{sailing}}, \textit{{hike}}, and \textit{{beach day}}. Exactly four participants
prefer each activity before ordering. Each participant also receives:

\begin{{itemize}}
  \item a preference strength drawn from 0.60 to 0.90; and
  \item a conformity value drawn from 0.55 to 0.90.
\end{{itemize}}

The ordering and trait values vary with the run seed. Agents are prompted through
Gemini 2.5 Flash using local EDSL orchestration. A grouped round-robin schedule creates
an ordering barrier, so voter $t$ sees the state committed by voters $1,\ldots,t-1$.
Across the ten runs there are 160 decisions.

\section*{{Shared-state mechanism}}

For each participant, the survey executes the following sequence:

\begin{{center}}
\fbox{{\parbox{{0.84\linewidth}}{{
\textbf{{1. Read}} the vote register at version $t-1$ $\rightarrow$
\textbf{{2. Ask}} the activity question with that snapshot $\rightarrow$
\textbf{{3. Write}} the selected activity $\rightarrow$
\textbf{{4. Commit}} version $t$.
}}}}
\end{{center}}

The explicit read is important. It records what the participant could observe and makes
the prompt's state dependency auditable in the Results provenance. Concurrency limits
alone would not create this sequence; the schedule supplies the barrier between turns.

\clearpage
\section*{{Outcomes across repetitions}}

\begin{{center}}
\includegraphics[width=0.78\linewidth]{{winner_frequency.png}}
\end{{center}}

The mean winning total was {mean_winning_count:.1f} of 16 votes. Participants selected
their initially preferred activity in {preference_rate:.1%} of decisions; the remaining
choices provide a direct descriptive measure of departures from baseline preference.

\begin{{center}}
\centering
\footnotesize
\resizebox{{\linewidth}}{{!}}{{%
\begin{{tabular}}{{r p{{3.0cm}} rrrr l}}
\toprule
Run & First three votes & Bike & Sail & Hike & Beach & Winner \\
\midrule
{chr(10).join(rows)}
\bottomrule
\end{{tabular}}
}}

\smallskip
{{\small\textbf{{Table 1.}} Final counts and the earliest observed path. Preferences were balanced 4--4--4--4 in every run.}}
\end{{center}}

\clearpage
\section*{{How the vote paths evolved}}

\begin{{center}}
\includegraphics[height=0.84\textheight]{{vote_paths.png}}
\end{{center}}

\clearpage
\section*{{What the repetitions show}}

\textbf{{Multiple outcomes occurred.}} Bike ride, sailing, hike, and beach day each won
at least once, even though every run began with four agents assigned to prefer each
activity.

\textbf{{Early positions were informative.}} The eventual winner was among the activity
or activities tied for the lead after three votes in {early_leader_matches} of 10 runs.
This wording matters: runs with three different opening votes have a three-way early tie,
not a unique predictor.

\textbf{{Some paths cascaded.}} Runs 3 and 9 ended 16--0; runs 4, 7, 8, and 10 ended
15--1. The line plots expose when those gaps opened and whether later voters reinforced
them.

\textbf{{Interpretation.}} The simulations are consistent with a path-dependent process:
early random variation changes the public state, and the public state can influence later
choices. They do not, by themselves, estimate a causal conformity effect. Both the trait
draws and model sampling vary across runs.

\section*{{Limitations and next tests}}

\begin{{itemize}}
  \item Ten repetitions are illustrative rather than a stable estimate of outcome probabilities.
  \item The agents are language-model simulations, not human participants.
  \item Ordering, trait values, and model stochasticity vary together in this version.
  \item A stronger test would hold personas fixed, randomly permute only their order, and run many more repetitions.
  \item A no-visibility control would separate preference-driven choices from responses to the live vote register.
\end{{itemize}}

\section*{{Reproducibility}}

The report is generated from
\nolinkurl{{shared-state-activity-poll-repeated.json}}. The single-run implementation is
\nolinkurl{{shared_state_activity_poll.py}}, the ten-run driver is
\nolinkurl{{shared_state_activity_poll_repeated.py}}, and the report builder is
\nolinkurl{{build_shared_state_path_dependence_report.py}}.

\vfill
{{\small\color{{muted}} Generated from the saved event-level output on 30 August 2026.}}

\end{{document}}
"""


def main() -> None:
    BUILD_DIR.mkdir(exist_ok=True)
    data = json.loads(DATA_PATH.read_text())
    make_figures(data)
    TEX_PATH.write_text(build_tex(data))
    subprocess.run(
        [
            "xelatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-output-directory",
            str(BUILD_DIR),
            str(TEX_PATH),
        ],
        cwd=BUILD_DIR,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    built_pdf = BUILD_DIR / "shared_state_path_dependence_report.pdf"
    PDF_PATH.write_bytes(built_pdf.read_bytes())
    print(PDF_PATH)


if __name__ == "__main__":
    main()
