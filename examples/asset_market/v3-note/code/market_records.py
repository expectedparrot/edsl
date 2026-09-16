"""Call-market decision contracts and validated wire records.

Rejected orders retain their original, possibly invalid payload. They are audit
records, not valid TraderDecisions. No validator silently repairs a decision.
"""

from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from functools import lru_cache
from typing import Any

from pydantic import (
    StrictInt,
    StrictStr,
    ValidationError,
    create_model,
    model_validator,
)

from .market_rules import (
    CallMarketRules,
    MarketModel,
    Name,
    NonnegativeInt,
    NonnegativeNumber,
    PositiveInt,
)


def cents(value):
    return int(
        (Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class OrderIntent(MarketModel):
    side: OrderSide
    price: NonnegativeNumber
    quantity: NonnegativeInt

    @model_validator(mode="after")
    def executable_order(self):
        if self.side != OrderSide.HOLD and (
            cents(self.price) <= 0 or self.quantity == 0
        ):
            raise ValueError("active orders require positive price and quantity")
        return self

    @classmethod
    def rejection(cls, answer):
        """Preserve v1 rejection messages and order-admission semantics."""
        try:
            cls.model_validate({key: answer.get(key) for key in cls.model_fields})
        except ValidationError as exc:
            fields = {e["loc"][0] for e in exc.errors() if e["loc"]}
            for key, message in (
                ("side", "invalid side"),
                ("quantity", "quantity must be a nonnegative integer"),
                ("price", "price must be finite and nonnegative"),
            ):
                if key in fields:
                    return message
            return "active orders require positive price and quantity"
        return None


class TraderDecision(OrderIntent):
    rationale: StrictStr


class DecisionSchema(MarketModel):
    """Shared field definitions for QuestionDict and runtime validation.

    QuestionDict supports primitive value types. Enum membership, finiteness,
    positivity and cross-field constraints are enforced here on submission.
    """

    forecast_keys: tuple[Name, ...] = (
        "forecast_0",
        "forecast_2",
        "forecast_5",
        "forecast_10",
    )

    @model_validator(mode="after")
    def distinct_keys(self):
        CallMarketRules.distinct_forecasts(self.forecast_keys)
        return self

    def response_model(self):
        return _response_model(self.forecast_keys, TraderDecision)

    def validate_decision(self, answer):
        return self.response_model().model_validate(answer)

    def validate_forecasts(self, answer):
        model = _response_model(self.forecast_keys, MarketModel)
        return model.model_validate(
            {key: answer.get(key) for key in self.forecast_keys}
        )

    def question(self, *, question_name, question_text):
        from edsl import QuestionDict

        order_types = {
            "side": "str",
            "price": "float",
            "quantity": "int",
            "rationale": "str",
        }
        return QuestionDict(
            question_name=question_name,
            question_text=question_text,
            answer_keys=[*self.forecast_keys, *TraderDecision.model_fields],
            value_types=["float"] * len(self.forecast_keys)
            + [order_types[key] for key in TraderDecision.model_fields],
            include_comment=False,
        )


@lru_cache(maxsize=128)
def _response_model(keys, base):
    return create_model(
        "MarketResponse",
        __base__=base,
        **{key: (NonnegativeNumber, ...) for key in keys},
    )


class AcceptedOrder(MarketModel):
    """Admission outcome, including rejected submissions for the audit trail."""

    trader: Name
    period: PositiveInt
    decision: dict[str, Any]
    side: Any  # A rejected order must retain the invalid submitted side.
    limit_cents: NonnegativeInt
    accepted_quantity: NonnegativeInt
    rejection: StrictStr | None

    @model_validator(mode="after")
    def admitted_or_rejected(self):
        if self.rejection is None:
            OrderIntent.model_validate(
                {k: self.decision.get(k) for k in OrderIntent.model_fields}
            )
            if self.side != self.decision["side"] or self.limit_cents != cents(
                self.decision["price"]
            ):
                raise ValueError(
                    "admitted order must match its submitted side and limit"
                )
            if self.accepted_quantity > self.decision["quantity"]:
                raise ValueError("admitted quantity exceeds submitted quantity")
            if self.side == OrderSide.HOLD and self.accepted_quantity:
                raise ValueError("hold orders cannot be admitted for trading")
        elif self.accepted_quantity or self.limit_cents:
            raise ValueError(
                "rejected orders must have zero admitted quantity and limit"
            )
        return self


class TradeFill(AcceptedOrder):
    fill: StrictInt
    transaction_price: NonnegativeNumber | None
    interest: NonnegativeNumber
    dividend_per_share: NonnegativeNumber

    @model_validator(mode="after")
    def fill_matches_order(self):
        if abs(self.fill) > self.accepted_quantity:
            raise ValueError("fill exceeds admitted quantity")
        if self.fill and (
            self.transaction_price is None
            or (self.fill > 0 and self.side != OrderSide.BUY)
            or (self.fill < 0 and self.side != OrderSide.SELL)
        ):
            raise ValueError("fill must match order side and have a transaction price")
        return self


class Account(MarketModel):
    cash_cents: NonnegativeInt
    shares: NonnegativeInt
    history: tuple[TradeFill, ...] = ()
    redeemed_shares: NonnegativeInt | None = None

    def to_dict(self):
        exclude = {"redeemed_shares"} if self.redeemed_shares is None else set()
        return self.model_dump(mode="json", exclude=exclude)


class RoundOutcome(MarketModel):
    period: PositiveInt
    price: NonnegativeNumber | None
    reference_price: NonnegativeNumber | None
    volume: NonnegativeInt
    dividend: NonnegativeNumber
    total_interest: NonnegativeNumber
    total_cash: NonnegativeNumber
    total_shares: NonnegativeInt

    @model_validator(mode="after")
    def price_requires_trade(self):
        if (self.volume == 0) != (self.price is None):
            raise ValueError("price is present exactly when volume is positive")
        return self
