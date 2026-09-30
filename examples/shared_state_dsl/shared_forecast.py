"""Forecast history with live latest-response consensus statistics."""

from edsl.sharedstate import Command, Machine, T, append, choose, current, field, input_, local, map_sequence, record, reduce_, state_field

latest_map = reduce_("latest_by", field("forecasts"), field="forecaster")
latest_records = latest_map.values()
public_latest = map_sequence(latest_records, item="forecast", value_expr=record(forecaster=local("forecast").get("forecaster"), round=local("forecast").get("round"), probability=local("forecast").get("probability"), confidence=local("forecast").get("confidence")))
public_history = map_sequence(field("forecasts"), item="forecast", value_expr=record(forecaster=local("forecast").get("forecaster"), round=local("forecast").get("round"), probability=local("forecast").get("probability"), confidence=local("forecast").get("confidence")))
probabilities = map_sequence(latest_records, item="forecast", value_expr=local("forecast").get("probability"))
confidences = map_sequence(latest_records, item="forecast", value_expr=local("forecast").get("confidence"))
weighted_terms = map_sequence(latest_records, item="forecast", value_expr=local("forecast").get("probability") * local("forecast").get("confidence"))
denominator = reduce_("sum", confidences)
SPEC = Machine(
    name="SharedForecast", constants={},
    fields={"forecasts": state_field(T.sequence(T.map()), [])},
    commands={
        "submit": Command(
            inputs={"forecaster": T.text(), "round": T.integer(minimum=1), "probability": T.number(minimum=0, maximum=100), "confidence": T.number(minimum=0, maximum=100)},
            effects=(append("forecasts", record(forecaster=input_("forecaster"), round=input_("round"), probability=input_("probability"), confidence=input_("confidence"), interview=current("interview_id"))),),
        )
    },
    view={
        "latest": public_latest, "history": public_history,
        "mean_probability": reduce_("mean", probabilities),
        "median_probability": reduce_("median", probabilities),
        "confidence_weighted_probability": choose(denominator > 0, reduce_("sum", weighted_terms) / denominator, None),
    },
)
