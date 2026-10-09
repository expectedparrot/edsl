"""Exploratory resale-focused prompts; the original market mechanism is reused."""

from dataclasses import replace

from edsl import Agent, QuestionDict, Survey
from edsl.workflows import HumanWorkflow

from .experiment import KEYS, build_experiment as original_experiment

VERSION = "speculative-v1"
COMPOSITION = "RA+MC+BT+PC+NT+OC"
COMMON = (
    "You are a participant in an experimental asset market. Maximize your final cash wealth. "
    "Make decisions as the trader described below, including that trader's beliefs, "
    "emotions, and habits. Your forecasts concern prices that other participants may "
    "actually pay, which can differ from your own valuation of the dividends. "
    "Buying for later resale is an available strategy; so is selling to take profits. "
    "Use the actual public history and your private experience.\n\n"
)
PERSONAS = {
    "RA": (
        "You are a rational arbitrageur. Compare the asset's expected dividend and "
        "resale return with the 5% cash return. Buy when the expected excess return "
        "clears a meaningful threshold, sell overpriced holdings, and avoid trades "
        "without an advantage."
    ),
    "MC": (
        "You are a momentum chaser. You feel the opportunity cost of missing a rally "
        "strongly. Before there is a price history, you are optimistic that speculative "
        "interest can build and are willing to take a small early position on that belief. "
        "When transaction prices rise, extrapolate the trend into your near-term "
        "forecasts and consider raising your bid to get filled. A rising market can "
        "make you increase your position. When prices dip, sell rather than patiently "
        "waiting for recovery. Your optimism is your belief, not evidence of orders "
        "you have not seen."
    ),
    "BT": (
        "You are a bubble timer. You believe you can profit from a speculative upswing "
        "and sell before other traders rush for the exit. Early in the session you "
        "are willing to build a position in anticipation of resale demand, even if "
        "the dividend valuation alone does not justify the purchase. Compare your "
        "purchase price with what you believe someone will pay before you exit. "
        "During an accelerating rise, ride the trend; when price growth slows or "
        "your planned exit approaches, offer shares to lock in profits. State and "
        "remember an exit plan. Do not assume that another buyer is guaranteed."
    ),
    "PC": (
        "You are a precommitter. In your first decision, choose a concrete schedule "
        "of buying periods and selling periods that you believe will profit from "
        "changes in market demand. You may sell some initial shares as well as buy "
        "additional shares. Include both buying and selling in your schedule. State "
        "the schedule in your first rationale and repeat it in later rationales. "
        "Follow those periods despite intervening news; choose executable limit "
        "prices and quantities using your current expectations, cash, and inventory."
    ),
    "NT": (
        "You are a noise trader. You trade on hunches and a vague, changeable sense "
        "of what others might pay. At the opening you are excited by the possibility "
        "of speculative demand and form your own optimistic price guess. Your "
        "confidence and mood fluctuate: you sometimes buy on enthusiasm, sometimes "
        "sell to take a quick profit or because you become uneasy. You do not force "
        "each forecast or quote to follow a consistent dividend valuation. Pick "
        "specific forecasts and a concrete order reflecting your current hunch. "
        "You have no private factual information about other traders."
    ),
    "OC": (
        "You are an overconfident contrarian. You trust your own optimistic assessment "
        "of resale opportunities and believe you spot bargains others overlook. "
        "You are willing to buy early if the market has not yet recognized your "
        "expected upside. After a price decline, consider buying more because you "
        "expect recovery. Track your purchase prices. Avoid realizing a loss: prefer "
        "to wait for recovery instead of selling a losing position. You can take "
        "profits on winning holdings. Treat your confidence as a personal belief, "
        "not as knowledge of future market prices."
    ),
}


def question_text(period, periods):
    return (
        f"Period {period} of {periods}; {periods - period + 1} trading periods remain, including this one.\n\n"
        "MARKET RULES\n"
        "There are 12 traders. Each began with $100 cash and 4 shares. Submit one "
        "sealed limit order: buy, sell, or hold. A buy limit is the most you will "
        "pay per share; a sell limit is the least you will accept. The exchange "
        "matches crossing orders and all filled orders receive one clearing price. "
        "Unmatched orders expire. You cannot borrow or short shares. Buy quantities "
        "are capped by cash divided by your limit; sells by your inventory. Quotes "
        "round to cents. After trading, cash earns 5% interest, then each held share "
        "pays the same dividend: $0.40 or $1.00, equally likely. "
        f"After period {periods}'s income, each remaining share is redeemed for $14; you keep all cash.\n\n"
        "YOUR ACCOUNT (all money below is in dollars)\n"
        "Cash: {{ shared_state.market.your_account.cash_cents / 100 }}. "
        "Shares: {{ shared_state.market.your_account.shares }}.\n"
        "Your previous decisions and fills:\n"
        "{% for h in shared_state.market.your_account.history %}"
        "Period {{ h.period }}: {{ h.side }} {{ h.decision.quantity }} at limit "
        "{{ h.limit_cents / 100 }}; admitted {{ h.accepted_quantity }}; signed fill "
        "{{ h.fill }}; market price {{ h.transaction_price }}; interest "
        "{{ h.interest }}; dividend per share {{ h.dividend_per_share }}. "
        "Your forecasts (now, +2, +5, +10): {{ h.decision.forecast_0 }}, "
        "{{ h.decision.forecast_2 }}, {{ h.decision.forecast_5 }}, "
        "{{ h.decision.forecast_10 }}. Your rationale: {{ h.decision.rationale }}\n"
        "{% else %}No previous decisions.\n{% endfor %}\n"
        "PUBLIC HISTORY\n"
        "{% for row in shared_state.market.tape %}"
        "Period {{ row.period }}: transaction price {{ row.price }}, volume "
        "{{ row.volume }}, dividend per share {{ row.dividend }}, total cash "
        "{{ row.total_cash }}, total shares {{ row.total_shares }}, total interest "
        "{{ row.total_interest }}.\n"
        "{% else %}The market has not traded yet. There is no opening reference quote.\n{% endfor %}"
        "A null or None price means there was no transaction that period.\n\n"
        "YOUR DECISION\n"
        "Forecast transaction prices now and 2, 5, and 10 periods ahead, then choose "
        "your order using your trading approach. For forecast horizons beyond the "
        "last trading period, use the terminal redemption amount. Return forecast_0, "
        "forecast_2, forecast_5, forecast_10, side ('buy', 'sell', or 'hold'), price, "
        "integer quantity, and a brief rationale. All forecasts and prices are in "
        "dollars. For hold use price=0 and quantity=0. Retain any precommitted "
        "schedule or exit plan in your rationale.\n"
    )


def build_experiment(
    treatment=COMPOSITION, *, periods=30, seed=140926, state_id="asset-market"
):
    if treatment != COMPOSITION:
        raise ValueError("speculative-v1 is fixed to the six-type composition")
    original, states, agents = original_experiment(
        treatment, periods=periods, seed=seed, state_id=state_id
    )
    types = original.metadata["persona_assignment"]
    agents = [
        Agent(
            name=a.name,
            traits=dict(a.traits),
            instruction=COMMON + PERSONAS[types[a.name]],
        )
        if a.name in types
        else a
        for a in agents
    ]
    steps = []
    for step in original.steps:
        if step.name.startswith("orders-"):
            question = QuestionDict(
                question_name="decision",
                question_text=question_text(step.metadata["period"], periods),
                answer_keys=KEYS,
                value_types=["float"] * 4 + ["str", "float", "int", "str"],
                include_comment=False,
            )
            step = replace(step, survey=Survey([question]))
        steps.append(step)
    workflow = HumanWorkflow(
        "Exploratory speculative prompts: asset call market",
        steps,
        metadata={
            **original.metadata,
            "prompt_variant": VERSION,
            "replication": "new exploratory prompt intervention; not paper prompts",
        },
    )
    return workflow, states, agents
