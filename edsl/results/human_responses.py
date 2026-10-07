"""Build Results from stored human survey responses.

A humanize survey collects answers from people, so there is nothing to run: each stored
response becomes one Result directly, with every value taken from what was recorded.
Running the survey with a stand-in agent instead would re-evaluate survey logic, use the
survey definition's options rather than the ones the respondent saw, and drop the
per-question timing.

HumanResponseRow is the row format Expected Parrot sends for each response, and
HumanResponseEntry one question's entry within it. Unknown keys are ignored, so a newer
server's extra fields never break an older client.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable, Mapping, Optional, Union, cast

from pydantic import BaseModel, JsonValue, TypeAdapter

from .exceptions import ResultsError

if TYPE_CHECKING:
    from ..language_models import LanguageModel
    from ..surveys import Survey
    from .result import AnswerValue
    from .results import Results

# Per-question entry fields written to the raw_model_response.{q}_{field} columns.
RAW_MODEL_RESPONSE_FIELDS = ("started_at", "answered_at", "question_presented")

MISSING_UUID_MESSAGE = "One of your responses is missing a unique identifier."


class HumanResponseEntry(BaseModel):
    """What was recorded for one question of a response."""

    answer: JsonValue = None
    comment: Optional[str] = None
    # ISO-8601 UTC: when the respondent reached the question, and when they answered it.
    started_at: Optional[str] = None
    answered_at: Optional[str] = None
    # False when survey logic skipped the question.
    question_presented: Optional[bool] = None
    # The options as the respondent saw them, after piping and any reordering. Any JSON
    # value: question types allow strings, ints, floats and, for multiple choice and
    # dropdown, lists.
    question_options: Optional[list[JsonValue]] = None


ENTRIES = TypeAdapter(dict[str, HumanResponseEntry])
JSON_OBJECT = TypeAdapter(dict[str, JsonValue])


class HumanResponseRow(BaseModel):
    """One stored response, as Expected Parrot sends it.

    The fields are JSON strings, which is the format older clients and servers expect;
    entries(), agent_traits() and scenario() parse them.
    """

    response_uuid: str
    # JSON of {question_name: HumanResponseEntry}. Entries for instructions may appear;
    # only the survey's questions are read.
    response_json_string: Optional[str] = None
    # JSON of the respondent's agent traits, used as is.
    agent_traits_json_string: Optional[str] = None
    # JSON of the scenario the respondent saw.
    scenario_json_string: Optional[str] = None

    @classmethod
    def coerce(cls, row: Union["HumanResponseRow", Mapping[str, object]]) -> "HumanResponseRow":
        """Return row as a HumanResponseRow, validating it if it is a plain mapping."""
        if isinstance(row, HumanResponseRow):
            return row
        if row.get("response_uuid") is None:
            raise ResultsError(MISSING_UUID_MESSAGE)
        return cls.model_validate(row)

    def entries(self) -> dict[str, HumanResponseEntry]:
        return ENTRIES.validate_json(self.response_json_string or "{}")

    def agent_traits(self) -> dict[str, JsonValue]:
        return JSON_OBJECT.validate_json(self.agent_traits_json_string or "{}")

    def scenario(self) -> Optional[dict[str, JsonValue]]:
        if self.scenario_json_string is None:
            return None
        return JSON_OBJECT.validate_json(self.scenario_json_string)


class HumanResponsesBuilder:
    """Turns stored human survey responses into a Results object."""

    @staticmethod
    def build(
        survey: "Survey",
        responses: Iterable[Union[HumanResponseRow, Mapping[str, object]]],
        decode_answers: bool = True,
    ) -> "Results":
        """Return a Results with one Result per response, in the order given.

        responses are HumanResponseRow objects or plain dicts in the same shape, such
        as rows straight from the API; plain dicts are validated first.

        Only the survey's questions become columns, so entries for instructions are
        ignored. A question with no entry reads as None throughout.

        decode_answers turns stored file uploads back into FileStore objects. Pass
        False to keep the stored, JSON-ready dicts.
        """
        from ..agents import Agent
        from ..language_models import Model
        from ..runner.models import _decode_answer_value
        from ..scenarios import Scenario
        from .result import Result
        from .results import Results

        question_names: list[str] = survey.question_names
        # Survey.question_to_attributes is loosely typed in EDSL: question attributes
        # of any kind, keyed by attribute name.
        question_attributes: dict[str, dict[str, Any]] = survey.question_to_attributes()
        # A human answer has no model; every Result records one, so use the test model,
        # as Results built by running the survey always have. Model() is a factory that
        # returns a LanguageModel.
        model = cast("LanguageModel", Model("test"))
        no_entry = HumanResponseEntry()

        data: list[Result] = []
        for row in map(HumanResponseRow.coerce, responses):
            entries = row.entries()
            scenario = row.scenario()

            answers: dict[str, "AnswerValue"] = {}
            comments: dict[str, Optional[str]] = {}
            raw_model_response: dict[str, Union[str, bool, None]] = {}
            attributes: dict[str, dict[str, Any]] = {}
            for qn in question_names:
                entry = entries.get(qn, no_entry)
                answers[qn] = (
                    _decode_answer_value(entry.answer) if decode_answers else entry.answer
                )
                comments[f"{qn}_comment"] = entry.comment
                for field in RAW_MODEL_RESPONSE_FIELDS:
                    raw_model_response[f"{qn}_{field}"] = getattr(entry, field)
                attributes[qn] = dict(question_attributes[qn])
                if entry.question_options is not None:
                    attributes[qn]["question_options"] = entry.question_options

            data.append(
                Result(
                    # An empty instruction: the default one describes an AI playing a
                    # human, which would be wrong on a real person's response.
                    agent=Agent(
                        name=row.response_uuid,
                        instruction="",
                        traits=row.agent_traits(),
                    ),
                    scenario=(
                        Scenario.from_dict(scenario) if scenario is not None else Scenario({})
                    ),
                    model=model,
                    iteration=0,
                    answer=answers,
                    raw_model_response=raw_model_response,
                    survey=survey,
                    question_to_attributes=attributes,
                    comments_dict=comments,
                    # No indices: Results would write its own position into
                    # agent.agent_index over the respondent's agent_index trait.
                    indices=None,
                )
            )

        return Results(survey=survey, data=data)
