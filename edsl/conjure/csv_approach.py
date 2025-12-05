import csv


# What kind of question is this? (free_text, multiple_choice, etc.)
# Is this a prepended data field?
# Is this a column-spanning question?
# What is the question text row?
# What is the question_name row (if any)?
# What were the question options?


class Column:
    """A column of values from a CSV file."""

    def __init__(self, name: str, values: list):
        self.name = name
        self._values = values

    def __repr__(self):
        return repr(self._values)

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __getitem__(self, index):
        return self._values[index]

    def __add__(self, other):
        new_data = []
        for a, b in zip(self._values, other._values):
            if isinstance(a, list) and isinstance(b, list):
                new_data.append(a + b)
            elif isinstance(a, list) and isinstance(b, str):
                if b == "":
                    new_data.append(a)
                else:
                    new_data.append(a + [b])
            elif isinstance(a, str) and isinstance(b, list):
                if a == "":
                    new_data.append(b)
                else:
                    new_data.append([a] + b)
            elif isinstance(a, str) and isinstance(b, str):
                if b == "":
                    new_data.append(a)
                elif a == "":
                    new_data.append(b)
                else:
                    new_data.append([a, b])
            else:
                raise ValueError(f"Cannot add {type(a)} and {type(b)}")
        return Column(self.name + other.name, new_data)

    def first_n_rows(self, n: int = 5):
        return "\n".join([f"{i}: {row}" for i, row in enumerate(self._values[:n])])


class SurveyResponses:
    """Reads a CSV file and creates Column objects for each column."""

    def __init__(self, csv_file: str):
        self.csv_file = csv_file
        self.columns: list[Column] = []
        self._read_csv()

    def _read_csv(self):
        with open(self.csv_file, "r", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

            if not rows:
                return

            num_columns = len(rows[0])
            data = [[] for _ in range(num_columns)]

            for row in rows:
                for i, value in enumerate(row):
                    data[i].append(value)

            self.columns = [Column(i, values) for i, values in enumerate(data)]

    def __getitem__(self, index):
        return self.columns[index]

    def __len__(self):
        return len(self.columns)

    def __iter__(self):
        return iter(self.columns)

    def to_scenario_list(self):
        from edsl import Scenario, ScenarioList

        scenarios = ScenarioList()
        for column in self.columns:
            scenarios.append(Scenario(first_n_rows=column.first_n_rows(), n=5))
        return scenarios


ImportedSurvey = SurveyResponses("web_takeoff_monadic_results.csv")

from edsl import (
    QuestionMultipleChoice,
    QuestionMultipleChoiceWithOther,
    QuestionFreeText,
)


def tally_by_index(imported_survey, index):
    column = imported_survey.columns[index]
    responses_tally = Counter(column[2:])
    return [x for x in list(responses_tally.keys()) if x != ""]


def second_line_by_index(imported_survey, index):
    column = imported_survey.columns[index]
    return column[1]


survey_monkey_headers = [
    "Respondent ID",
    "Collector ID",
    "Start Date",
    "End Date",
    "Email Address",
    "First Name",
    "Last Name",
]
from edsl import Survey

survey = Survey()
from collections import Counter

index = 0
column_group = []
from edsl import QuestionCheckBox

from dataclasses import dataclass
from typing import List, Any


@dataclass
class PrependData:
    column_index: int
    column_name: str
    values: List[Any]


from enum import Enum


class DataType(Enum):
    PREPEND = "prepend"
    SURVEY_RESPONSE = "survey_response"


@dataclass
class GroupData:
    data_type: DataType | None
    start_index: int | None
    end_index: int | None

    def __len__(self):
        return self.end_index - self.start_index + 1

    def __getitem__(self, index):
        return self.data[index]

    def first_lines(self):
        return [first_lines[i] for i in range(self.start_index, self.end_index + 1)]

    def second_lines(self):
        return [second_lines[i] for i in range(self.start_index, self.end_index + 1)]


from enum import auto
from edsl.conjure.text_differ import extract_template, SlotInfo, TemplateResult


class ColumnType(Enum):
    PREPEND = auto()
    QUESTION_START = auto()
    QUESTION_CONTINUATION = auto()
    QUESTION_VIEWED = auto()


@dataclass
class MonadicQuestion:
    """A question where the text varies per row with parameterized values."""

    question_template: str
    slots: List[SlotInfo]  # List of slots (x, y, z...) with their values
    responses: List[str]
    column_index: int


def detect_monadic_question(group, columns, second_lines) -> MonadicQuestion | None:
    """
    Detect if a group represents a monadic question (varying question text per row).

    Monadic questions have:
    - 2 columns: "Question Viewed" column + "Response" column
    - The "Question Viewed" column has varying text per row (e.g., different prices)
    """
    if len(group) != 2:
        return None

    first_second_line = second_lines[group.start_index]
    second_second_line = second_lines[group.start_index + 1]

    if first_second_line != "Question Viewed" or second_second_line != "Response":
        return None

    # Get the question texts from the first column (rows 2+, i.e., data rows)
    question_texts = list(columns[group.start_index][2:])
    responses = list(columns[group.start_index + 1][2:])

    # Use tokenization-based template extraction
    result = extract_template(question_texts)
    if result is None:
        return None

    return MonadicQuestion(
        question_template=result.template,
        slots=result.slots,
        responses=responses,
        column_index=group.start_index,
    )


def classify_column(first_line: str, headers: list[str]) -> ColumnType:
    """Classify a column based on its first line."""
    if "Custom" in first_line or first_line in headers:
        return ColumnType.PREPEND
    if first_line == "Question Viewed":
        return ColumnType.QUESTION_VIEWED
    if first_line != "":
        return ColumnType.QUESTION_START
    return ColumnType.QUESTION_CONTINUATION


def extract_headers(columns) -> tuple[list[str], list[str]]:
    """Extract first and second row values from all columns."""
    first_lines = [col[0] for col in columns]
    second_lines = [col[1] for col in columns]
    return first_lines, second_lines


def close_and_start_group(
    current_group, groups, index, new_data_type, next_start_offset=0
):
    """Close the current group and start a new one."""
    current_group.end_index = index - 1
    groups.append(current_group)
    return GroupData(
        data_type=new_data_type, start_index=index + next_start_offset, end_index=None
    )


def is_continuation_of_previous(
    index: int, first_lines: list[str], second_lines: list[str]
) -> bool:
    """
    Check if this column continues the previous group.

    A column is a continuation if:
    - Its first_line is empty (standard Survey Monkey multi-column), OR
    - Its first_line matches the previous column's first_line (monadic questions)
    """
    if index == 0:
        return False

    current_first = first_lines[index]
    prev_first = first_lines[index - 1]

    # Empty first line = standard continuation
    if current_first == "":
        return True

    # Same first line as previous = monadic question continuation
    # (e.g., both columns have same question text, but different second lines)
    if current_first == prev_first and current_first != "":
        return True

    return False


def build_groups_from_columns(columns, headers: list[str]):
    """
    Parse Survey Monkey CSV columns into logical groups.

    Groups are determined by:
    - PREPEND: Custom fields or standard Survey Monkey headers (respondent ID, dates, etc.)
    - SURVEY_RESPONSE: Actual survey questions, which may span multiple columns

    Multi-column questions are detected when:
    - first_line is empty (standard checkbox/multi-select), OR
    - first_line matches the previous column (monadic/price-sensitivity questions)
    """
    first_lines, second_lines = extract_headers(columns)

    groups = []
    prepend_data = []
    current_group = GroupData(data_type=DataType.PREPEND, start_index=0, end_index=None)

    for index, column in enumerate(columns):
        # Check if this column continues the previous group
        if is_continuation_of_previous(index, first_lines, second_lines):
            # Group continues, nothing to do
            continue

        col_type = classify_column(first_lines[index], headers)

        if col_type == ColumnType.PREPEND:
            prepend_data.append(PrependData(index, first_lines[index], column[2:]))
            current_group = close_and_start_group(
                current_group, groups, index, DataType.PREPEND, next_start_offset=1
            )
        elif col_type in (ColumnType.QUESTION_START, ColumnType.QUESTION_VIEWED):
            current_group = close_and_start_group(
                current_group,
                groups,
                index,
                DataType.SURVEY_RESPONSE,
                next_start_offset=0,
            )

    # Close the final group
    if current_group.end_index is None:
        current_group.end_index = len(columns) - 1
        groups.append(current_group)

    return groups, prepend_data, first_lines, second_lines


# Build groups from the imported survey
groups, prepend_data, first_lines, second_lines = build_groups_from_columns(
    ImportedSurvey.columns, survey_monkey_headers
)

survey = Survey()
monadic_questions = []  # Track monadic questions for scenario generation

for group in groups:
    if group.data_type == DataType.PREPEND:
        pass
    elif group.data_type == DataType.SURVEY_RESPONSE:
        question_text = first_lines[group.start_index]

        # Check for monadic question (varying text per row, e.g., price sensitivity)
        monadic = detect_monadic_question(group, ImportedSurvey.columns, second_lines)
        if monadic:
            print(f"Detected monadic question with {len(monadic.slots)} slot(s)")
            print(f"  Template: {monadic.question_template[:80]}...")
            for slot in monadic.slots:
                print(f"  {slot.name} = {slot.unique_values}")
            monadic_questions.append(monadic)

            # Create question with template variable(s)
            q = QuestionMultipleChoice(
                question_name=f"index_{group.start_index}",
                question_text=monadic.question_template,
                question_options=["Yes", "No"],  # Typical for price sensitivity
            )
            survey.add_question(q)
            continue

        if len(group) == 1:
            if second_lines[group.start_index] == "Response":
                print("Adding a multiple choice question")
                q = QuestionMultipleChoice(
                    question_name=f"index_{group.start_index}",
                    question_text=question_text,
                    question_options=tally_by_index(ImportedSurvey, group.start_index),
                )
                survey.add_question(q)
            elif second_lines[group.start_index] == "Open-ended response":
                q = QuestionFreeText(
                    question_name=f"index_{group.start_index}",
                    question_text=question_text,
                )
                survey.add_question(q)
        elif len(group) > 1:
            options = group.second_lines()
            if options == ["Response", "Other (please specify)"]:
                print("Adding a multiple choice question with other")
                q = QuestionMultipleChoiceWithOther(
                    question_name=f"index_{group.start_index}",
                    question_text=question_text,
                    question_options=tally_by_index(ImportedSurvey, group.start_index),
                )
                survey.add_question(q)
            else:
                print("Adding a check box question")
                q = QuestionCheckBox(
                    question_name=f"index_{group.start_index}",
                    question_text=question_text,
                    question_options=options,
                )
                survey.add_question(q)

from edsl import ScenarioList, Scenario

# Build scenario list from UNIQUE values and track agent-to-scenario mapping
sl = ScenarioList()
agent_to_scenario_idx = {}  # agent_index -> scenario_index they should match

if monadic_questions:
    print("\n=== Monadic Questions Detected ===")

    # For now, handle the first monadic question (extend later if needed)
    mq = monadic_questions[0]
    slot = mq.slots[0]  # Primary slot (e.g., price)

    print(f"Column {mq.column_index}:")
    print(f"  Slot: {slot.name}")
    print(f"  Unique values: {slot.unique_values}")

    # Build mapping from value -> scenario index
    value_to_scenario_idx = {}
    for idx, value in enumerate(slot.unique_values):
        sl.append(Scenario({slot.name: value, "_index": idx}))
        value_to_scenario_idx[value] = idx

    # Track which scenario each agent (row) should be paired with
    for agent_idx, value in enumerate(slot.values_per_row):
        agent_to_scenario_idx[agent_idx] = value_to_scenario_idx[value]

    print(f"  Created {len(sl)} scenarios from {len(slot.values_per_row)} agent rows")


@dataclass
class QuestionMapping:
    """Maps a question name to its column indices and type."""

    question_name: str
    column_indices: List[int]
    is_checkbox: bool


def build_question_mappings(groups, columns, second_lines) -> List[QuestionMapping]:
    """Build mappings from question names to their column indices and types."""
    mappings = []

    for group in groups:
        if group.data_type != DataType.SURVEY_RESPONSE:
            continue

        question_name = f"index_{group.start_index}"
        column_indices = list(range(group.start_index, group.end_index + 1))

        # Check for monadic question (2 columns: Question Viewed + Response)
        if len(group) == 2:
            first_second = second_lines[group.start_index]
            second_second = second_lines[group.start_index + 1]
            if first_second == "Question Viewed" and second_second == "Response":
                # Monadic: only use the Response column
                mappings.append(
                    QuestionMapping(
                        question_name=question_name,
                        column_indices=[group.start_index + 1],
                        is_checkbox=False,
                    )
                )
                continue

        # Determine if checkbox based on group size and second line values
        if len(group) == 1:
            is_checkbox = False
        else:
            options = [second_lines[i] for i in column_indices]
            # Multiple choice with other has exactly these options
            is_checkbox = options != ["Response", "Other (please specify)"]

        mappings.append(
            QuestionMapping(
                question_name=question_name,
                column_indices=column_indices,
                is_checkbox=is_checkbox,
            )
        )

    return mappings


def build_response_records(
    columns, question_mappings: List[QuestionMapping]
) -> List[dict]:
    """
    Build a list of dictionaries, one per respondent row.

    Each dictionary has question_name as keys and response values:
    - Checkbox questions: list of selected options (e.g., ['a', 'b', 'c'])
    - Other question types: single text value
    """
    # Determine number of data rows (skip header rows 0 and 1)
    num_rows = len(columns[0]) - 2

    records = []
    for row_idx in range(num_rows):
        data_row_idx = row_idx + 2  # Skip header rows
        record = {}

        for mapping in question_mappings:
            if mapping.is_checkbox:
                # Collect all non-empty values from the checkbox columns
                selected = []
                for col_idx in mapping.column_indices:
                    value = columns[col_idx][data_row_idx]
                    if value != "":
                        selected.append(value)
                record[mapping.question_name] = selected
            else:
                # Single value from the first (or only) column
                col_idx = mapping.column_indices[0]
                record[mapping.question_name] = columns[col_idx][data_row_idx]

        records.append(record)

    return records


# Build question mappings and response records
question_mappings = build_question_mappings(
    groups, ImportedSurvey.columns, second_lines
)
response_records = build_response_records(ImportedSurvey.columns, question_mappings)

from edsl import Agent

from typing import Callable
from edsl import AgentList

al = AgentList()
for index, record in enumerate(response_records):
    a = Agent()

    def construct_answer_dict_function(record: dict) -> Callable:

        def func(self, question: "QuestionBase", scenario=None):
            return record.get(question.question_name, None)

        return func

    a.add_direct_question_answering_method(construct_answer_dict_function(record))
    a.traits["_index"] = index
    # Store which scenario this agent should be paired with
    if index in agent_to_scenario_idx:
        a.traits["_scenario_index"] = agent_to_scenario_idx[index]
    al.append(a)

# Run without scenarios (non-monadic questions only)
# new_results = survey.by(al).run(disable_remote_inference=True)

# Run with scenario filtering - each agent only gets their matching scenario
if monadic_questions and len(sl) > 0:
    jobs = (
        survey.by(al)
        .by(sl)
        .include_when("{{ scenario._index == agent.traits['_scenario_index'] }}")
    )
    new_results = jobs.run(disable_remote_inference=True, stop_on_exception=True)
else:
    new_results = survey.by(al).run(disable_remote_inference=True)


# # Preview the first few records
# print("\n=== Response Records ===")
# for i, record in enumerate(response_records[:3]):
#     print(f"Row {i}: {record}")
