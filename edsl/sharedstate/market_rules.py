"""Validated authoring objects for the version-1 call market.

These objects contain data only. The wire format remains the original Machine
constants; runtime implementation identifiers are not experimental treatments.
"""

from enum import Enum
import keyword
import math
from typing import Annotated, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

NonnegativeInt = Annotated[StrictInt, Field(ge=0)]
PositiveInt = Annotated[StrictInt, Field(gt=0)]
NonnegativeNumber = Annotated[StrictFloat, Field(ge=0, allow_inf_nan=False)]
Name = Annotated[StrictStr, Field(min_length=1)]


class MarketModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_default=True, allow_inf_nan=False
    )

    def to_dict(self):
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data):
        return cls.model_validate(data)

    def with_changes(self, **changes):
        """Unlike model_copy(update=...), revalidate every proposed change."""
        return type(self).model_validate({**self.model_dump(), **changes})


class PricingRule(str, Enum):
    MARGINAL_MIDPOINT = "marginal_midpoint"
    MARGINAL_BID = "marginal_bid"
    MARGINAL_ASK = "marginal_ask"


class DividendSampling(str, Enum):
    CHOICE = "python_random_choice_v1"
    WEIGHTED = "python_random_choices_v1"


class Endowment(MarketModel):
    cash_cents: NonnegativeInt = 10_000
    shares: NonnegativeInt = 4


class Redemption(MarketModel):
    value_cents: NonnegativeInt = 1_400


class DiscreteDistribution(MarketModel):
    values_cents: tuple[NonnegativeInt, ...] = (40, 100)
    probabilities: tuple[NonnegativeNumber, ...] = (0.5, 0.5)

    @field_validator("values_cents")
    @classmethod
    def nonempty(cls, values):
        if not values:
            raise ValueError("must contain at least one dividend")
        return values

    @field_validator("probabilities")
    @classmethod
    def probability_vector(cls, probabilities, info):
        values = info.data.get("values_cents")
        if values is not None and len(values) != len(probabilities):
            raise ValueError(
                f"expected {len(values)} probabilities matching values_cents; received {len(probabilities)}"
            )
        if not math.isclose(sum(probabilities), 1):
            raise ValueError("dividend probabilities must sum to one")
        return probabilities

    @property
    def expected_cents(self):
        return sum(v * p for v, p in zip(self.values_cents, self.probabilities))


class CashInterest(MarketModel):
    kind: Literal["cash_interest"] = "cash_interest"
    rate: NonnegativeNumber = 0.05


class ShareDividend(MarketModel):
    kind: Literal["share_dividend"] = "share_dividend"
    distribution: DiscreteDistribution = Field(default_factory=DiscreteDistribution)
    # Retain the exact random algorithm for archived v1 replays. None chooses
    # the appropriate implementation once, when authoring the specification.
    sampling: DividendSampling | None = None

    @model_validator(mode="after")
    def sampling_matches_distribution(self):
        p = self.distribution.probabilities
        equal = all(math.isclose(x, 1 / len(p)) for x in p)
        if self.sampling == DividendSampling.CHOICE and not equal:
            raise ValueError("choice sampling requires equal probabilities")
        if self.sampling is None:
            object.__setattr__(
                self,
                "sampling",
                DividendSampling.CHOICE if equal else DividendSampling.WEIGHTED,
            )
        return self

    def to_wire(self):
        return {
            "kind": self.kind,
            **self.distribution.to_dict(),
            "sampling": self.sampling.value,
        }


IncomeRule = Annotated[Union[CashInterest, ShareDividend], Field(discriminator="kind")]


class CallMarketRules(MarketModel):
    periods: PositiveInt = Field(
        30, description="Number of trading and income periods."
    )
    endowment: Endowment = Field(default_factory=Endowment)
    initial_reference_price: NonnegativeNumber | None = 14.0
    redemption: Redemption = Field(default_factory=Redemption)
    pricing: PricingRule = PricingRule.MARGINAL_MIDPOINT
    maximum_buy_quantity: PositiveInt | None = None
    income: tuple[IncomeRule, ...] = Field(
        default_factory=lambda: (CashInterest(), ShareDividend())
    )
    forecast_keys: tuple[Name, ...] = (
        "forecast_0",
        "forecast_2",
        "forecast_5",
        "forecast_10",
    )

    @field_validator("income")
    @classmethod
    def one_of_each(cls, income):
        if len(income) != 2 or {type(r) for r in income} != {
            CashInterest,
            ShareDividend,
        }:
            raise ValueError("income must order one interest and one dividend payment")
        return income

    @field_validator("forecast_keys")
    @classmethod
    def distinct_forecasts(cls, keys):
        if any(
            not k.isidentifier()
            or k.startswith("_")
            or keyword.iskeyword(k)
            or hasattr(MarketModel, k)
            for k in keys
        ):
            raise ValueError(
                "forecast_keys must be public identifiers that do not shadow model attributes"
            )
        if len(keys) != len(set(keys)) or set(keys) & {
            "side",
            "price",
            "quantity",
            "rationale",
        }:
            raise ValueError(
                "forecast_keys must be distinct and cannot overlap order fields"
            )
        return keys

    @property
    def interest(self):
        return next(r for r in self.income if isinstance(r, CashInterest))

    @property
    def dividend(self):
        return next(r for r in self.income if isinstance(r, ShareDividend))

    def fundamental_value(self, period=1):
        """Pre-trade risk-neutral value in dollars, ignoring cent rounding.

        Backward induction uses the actual payment order and terminal value;
        it also works at zero interest and when value changes over time.
        """
        if (
            isinstance(period, bool)
            or not isinstance(period, int)
            or not 1 <= period <= self.periods + 1
        ):
            raise ValueError("period must be between 1 and periods + 1")
        rate = self.interest.rate
        dividend = self.dividend.distribution.expected_cents / 100
        if isinstance(self.income[0], ShareDividend):
            dividend *= 1 + rate
        value = self.redemption.value_cents / 100
        for _ in range(self.periods - period + 1):
            value = (value + dividend) / (1 + rate)
        return value

    def instructions(self, trader_count):
        """Economic rules for trader prompts, generated from executed settings."""
        if (
            isinstance(trader_count, bool)
            or not isinstance(trader_count, int)
            or trader_count < 1
        ):
            raise ValueError("trader_count must be a positive integer")
        d = self.dividend.distribution
        if len(d.values_cents) == 2 and d.probabilities == (0.5, 0.5):
            distribution = (
                " or ".join(f"${v / 100:.2f}" for v in d.values_cents)
                + ", equally likely"
            )
        else:
            distribution = ", ".join(
                f"${v / 100:.2f} (probability {p:g})"
                for v, p in zip(d.values_cents, d.probabilities)
            )
        income = [
            (
                f"cash earns {r.rate * 100:g}% interest"
                if isinstance(r, CashInterest)
                else f"each held share pays the same dividend: {distribution}"
            )
            for r in self.income
        ]
        extra = ""
        if self.pricing != PricingRule.MARGINAL_MIDPOINT:
            boundary = "bid" if self.pricing == PricingRule.MARGINAL_BID else "ask"
            extra += f" The clearing price is the last matched {boundary}."
        if (
            self.maximum_buy_quantity is not None
            and self.maximum_buy_quantity < trader_count * self.endowment.shares
        ):
            extra += (
                f" Each buy order is also capped at {self.maximum_buy_quantity} shares."
            )
        return (
            f"There are {trader_count} traders. Each began with ${self.endowment.cash_cents / 100:g} cash and {self.endowment.shares} shares. Submit one "
            "sealed limit order: buy, sell, or hold. A buy limit is the most you will "
            "pay per share; a sell limit is the least you will accept. The exchange "
            "matches crossing orders and all filled orders receive one clearing price. "
            "Unmatched orders expire. You cannot borrow or short shares. Buy quantities "
            "are capped by cash divided by your limit; sells by your inventory. Quotes "
            f"round to cents.{extra} After trading, " + ", then ".join(income) + ". "
            f"After period {self.periods}'s income, each remaining share is redeemed for ${self.redemption.value_cents / 100:g}; you keep all cash.\n\n"
        )

    def to_constants(self, trader_count, seed):
        if (
            isinstance(trader_count, bool)
            or not isinstance(trader_count, int)
            or trader_count < 1
        ):
            raise ValueError("trader_count must be a positive integer")
        total = self.endowment.shares * trader_count
        data = dict(
            periods=self.periods,
            seed=seed,
            total_shares=total,
            maximum_buy_quantity=self.maximum_buy_quantity or max(1, total),
            redemption_cents=self.redemption.value_cents,
            pricing_rule=self.pricing.value,
            rounding="half_up",
            money_decimals=2,
            borrowing=False,
            short_selling=False,
            tie_breaking="seeded_price_priority_v1",
            unfilled_orders="expire",
            redemption_timing="after_final_income",
            forecast_keys=list(self.forecast_keys),
            income_schedule=[
                r.to_wire() if isinstance(r, ShareDividend) else r.to_dict()
                for r in self.income
            ],
        )
        MarketConstants.model_validate(data)
        return data

    @classmethod
    def from_legacy(cls, **options):
        """Validate the original keyword API through the same typed rules."""
        aliases = {
            "initial_cash_cents",
            "initial_shares",
            "redemption_cents",
            "pricing_rule",
            "income_schedule",
        }
        allowed = {
            "periods",
            "initial_reference_price",
            "maximum_buy_quantity",
            "forecast_keys",
        } | aliases
        unknown = set(options) - allowed
        if unknown:
            raise ValueError(f"unknown call_market options: {sorted(unknown)}")
        data = {k: v for k, v in options.items() if k not in aliases}
        data["endowment"] = {
            "cash_cents": options.get("initial_cash_cents", 10000),
            "shares": options.get("initial_shares", 4),
        }
        data["redemption"] = {"value_cents": options.get("redemption_cents", 1400)}
        data["pricing"] = options.get("pricing_rule", PricingRule.MARGINAL_MIDPOINT)
        if options.get("income_schedule") is not None:
            # Validate wire records before reading keys, preserving useful paths.
            schedule = IncomeSchedule(schedule=options["income_schedule"]).schedule
            data["income"] = tuple(
                (
                    r.to_authoring()
                    if isinstance(r, WireDividend)
                    else CashInterest(rate=r.rate)
                )
                for r in schedule
            )
        return cls.model_validate(data)


class WireInterest(CashInterest):
    rate: NonnegativeNumber


class WireDividend(MarketModel):
    kind: Literal["share_dividend"]
    values_cents: tuple[NonnegativeInt, ...]
    probabilities: tuple[NonnegativeNumber, ...]
    sampling: DividendSampling

    @model_validator(mode="after")
    def validate_distribution(self):
        self.to_authoring()
        return self

    def to_authoring(self):
        return ShareDividend(
            distribution=DiscreteDistribution(
                values_cents=self.values_cents, probabilities=self.probabilities
            ),
            sampling=self.sampling,
        )


WireIncome = Annotated[Union[WireInterest, WireDividend], Field(discriminator="kind")]


class IncomeSchedule(MarketModel):
    schedule: tuple[WireIncome, ...]

    @field_validator("schedule")
    @classmethod
    def one_of_each(cls, schedule):
        if len(schedule) != 2 or {type(r) for r in schedule} != {
            WireInterest,
            WireDividend,
        }:
            raise ValueError(
                "income_schedule must order one interest and one dividend payment"
            )
        return schedule


class MarketConstants(MarketModel):
    """Strict schema for the existing v1 wire format, including fixed policies."""

    periods: PositiveInt
    seed: StrictStr | StrictInt
    total_shares: NonnegativeInt
    maximum_buy_quantity: PositiveInt
    redemption_cents: NonnegativeInt
    pricing_rule: PricingRule
    rounding: Literal["half_up"]
    money_decimals: Literal[2]
    borrowing: Literal[False]
    short_selling: Literal[False]
    tie_breaking: Literal["seeded_price_priority_v1"]
    unfilled_orders: Literal["expire"]
    redemption_timing: Literal["after_final_income"]
    forecast_keys: tuple[Name, ...]
    income_schedule: tuple[WireIncome, ...]

    @field_validator("money_decimals", "borrowing", "short_selling", mode="before")
    @classmethod
    def exact_literal_type(cls, value, info):
        expected = int if info.field_name == "money_decimals" else bool
        if type(value) is not expected:
            raise ValueError(f"expected {expected.__name__}")
        return value

    @field_validator("forecast_keys")
    @classmethod
    def forecasts(cls, keys):
        return CallMarketRules.distinct_forecasts(keys)

    @field_validator("income_schedule")
    @classmethod
    def income_order(cls, schedule):
        return IncomeSchedule.one_of_each(schedule)
