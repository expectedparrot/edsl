"""Module for generating surveys from topics or question texts.

This module provides functionality for automatically generating surveys using LLMs,
including type inference and question generation from natural language descriptions.
"""

import re
import uuid
from typing import List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..language_models import LanguageModel
    from ..questions import QuestionBase
    from .survey import Survey


class SurveyGenerator:
    """Handles automatic survey generation from topics or question texts."""

    @staticmethod
    def generate_from_topic(
        survey_class: type["Survey"],
        topic: str,
        n_questions: int = 5,
        model: Optional["LanguageModel"] = None,
        scenario_keys: Optional[List[str]] = None,
        verbose: bool = True,
    ) -> "Survey":
        """Generate a survey from a topic using an LLM.

        This method uses a language model to generate a well-balanced survey
        for the given topic with the specified number of questions.

        Args:
            survey_class: The Survey class to instantiate.
            topic: The topic to generate questions about
            n_questions: Number of questions to generate (default: 5)
            model: Language model to use for generation. If None, uses default model.
            scenario_keys: Optional list of scenario keys to include in question texts.
                          Each key will be added as {{ scenario.<key> }} in the questions.
            verbose: Whether to show the underlying survey generation process (default: True)

        Returns:
            Survey: A new Survey instance with generated questions

        Examples:
            >>> from edsl import Survey
            >>> survey = Survey.generate_from_topic("workplace satisfaction", n_questions=3)  # doctest: +SKIP
            >>> survey = Survey.generate_from_topic("product feedback", scenario_keys=["product_name", "version"])  # doctest: +SKIP
            >>> survey = Survey.generate_from_topic("feedback", verbose=False)  # doctest: +SKIP
        """
        from ..language_models import Model
        from ..questions import (
            QuestionList,
            QuestionFreeText,
            QuestionMultipleChoice,
            QuestionLinearScale,
            QuestionCheckBox,
        )

        # Use default model if none provided
        m = model or Model()

        # Generate questions using LLM
        scenario_instruction = ""
        if scenario_keys:
            scenario_vars = ", ".join(
                [f"{{{{ scenario.{key} }}}}" for key in scenario_keys]
            )
            scenario_instruction = f"\n\nIMPORTANT: Include these scenario variables in your questions where appropriate: {scenario_vars}"

        system_prompt = f"""
Draft a concise, well-balanced survey for the given topic.
Return only JSON (a list), where each element includes:
- question_text
- question_type ∈ {{"FreeText","MultipleChoice","LinearScale","CheckBox"}}
- question_options (REQUIRED for all but FreeText; for LinearScale return a list of integers like [1,2,3,4,5])
- question_name (optional, short slug like "feel_today" not "how_do_you_feel_today", max 20 chars)

Design tips:
- Prefer MultipleChoice for attitudes/preferences; FreeText for open feedback; LinearScale for intensity; CheckBox for multi-select.
- Keep options 3–7 items where possible; be neutral & non-leading.
- Avoid duplicative questions.
- For LinearScale: use integer lists like [1,2,3,4,5] or [1,2,3,4,5,6,7,8,9,10]
- Question names should be short, unique references (like "satisfaction", "age", "preference"){scenario_instruction}
        """.strip()

        q = QuestionList(
            question_name="topic_questions",
            question_text=(
                f"{system_prompt}\n\nTOPIC: {topic}\nN_QUESTIONS: {n_questions}"
                "\nReturn ONLY JSON."
            ),
            max_list_items=n_questions,
        )

        # Try LLM generation first
        items = []
        try:
            if verbose:
                result = q.by(m).run()
            else:
                # Suppress output when verbose=False
                import sys
                from io import StringIO

                old_stdout = sys.stdout
                sys.stdout = StringIO()
                try:
                    result = q.by(m).run()
                finally:
                    sys.stdout = old_stdout

            items = result.select("topic_questions").to_list()[0]
        except Exception:
            # LLM call failed, will use fallback
            pass

        # Handle case where LLM doesn't return expected format or fails
        if not items:
            # Fallback: create simple questions based on topic with pattern-based types
            questions = []
            for i in range(n_questions):
                # Add scenario variables to fallback questions if provided
                if scenario_keys:
                    scenario_vars = " ".join(
                        [f"{{{{ scenario.{key} }}}}" for key in scenario_keys]
                    )
                    question_text = f"What are your thoughts on {topic} regarding {scenario_vars}? (Question {i+1})"
                else:
                    question_text = (
                        f"What are your thoughts on {topic}? (Question {i+1})"
                    )

                # Use pattern-based type inference for fallback questions
                text_lower = question_text.lower()
                if any(
                    word in text_lower
                    for word in [
                        "satisfied",
                        "satisfaction",
                        "happy",
                        "pleased",
                        "likely",
                        "probability",
                        "chance",
                        "often",
                        "frequency",
                        "agree",
                        "disagree",
                        "opinion",
                    ]
                ):
                    question_obj = QuestionMultipleChoice(
                        question_name=f"q{i}",
                        question_text=question_text,
                        question_options=[
                            "Very satisfied",
                            "Satisfied",
                            "Neutral",
                            "Dissatisfied",
                            "Very dissatisfied",
                        ],
                    )
                elif any(
                    word in text_lower
                    for word in [
                        "features",
                        "functionality",
                        "capabilities",
                        "value",
                        "like",
                        "benefits",
                        "advantages",
                        "perks",
                        "important",
                        "channels",
                        "methods",
                        "ways",
                        "prefer",
                        "contact",
                    ]
                ):
                    question_obj = QuestionCheckBox(
                        question_name=f"q{i}",
                        question_text=question_text,
                        question_options=[
                            "User interface",
                            "Performance",
                            "Security",
                            "Customer support",
                            "Pricing",
                        ],
                    )
                elif any(
                    word in text_lower
                    for word in ["rate", "rating", "scale", "level", "score"]
                ):
                    question_obj = QuestionLinearScale(
                        question_name=f"q{i}",
                        question_text=question_text,
                        question_options=[1, 2, 3, 4, 5],
                    )
                else:
                    question_obj = QuestionFreeText(
                        question_name=f"q{i}", question_text=question_text
                    )

                questions.append(question_obj)
        else:
            # Convert to proper question objects and ensure scenario variables are included
            questions = []
            for i, item in enumerate(items):
                # Ensure scenario variables are included in question text
                if scenario_keys and "question_text" in item:
                    original_text = item["question_text"]
                    # Check if scenario variables are already in the text
                    has_scenario_vars = any(
                        f"{{{{ scenario.{key} }}}}" in original_text
                        for key in scenario_keys
                    )
                    if not has_scenario_vars:
                        # Add scenario variables to the question text
                        scenario_vars = " ".join(
                            [f"{{{{ scenario.{key} }}}}" for key in scenario_keys]
                        )
                        item["question_text"] = (
                            f"{original_text} (Context: {scenario_vars})"
                        )

                question_obj = SurveyGenerator._create_question_from_dict(item, f"q{i}")
                questions.append(question_obj)

        return survey_class(questions)

    @staticmethod
    def generate_from_questions(
        survey_class: type["Survey"],
        question_texts: List[str],
        question_types: Optional[List[str]] = None,
        question_names: Optional[List[str]] = None,
        model: Optional["LanguageModel"] = None,
        scenario_keys: Optional[List[str]] = None,
        verbose: bool = True,
    ) -> "Survey":
        """Generate a survey from a list of question texts.

        This method takes a list of question texts and optionally infers question types
        and generates question names using an LLM.

        Args:
            survey_class: The Survey class to instantiate.
            question_texts: List of question text strings
            question_types: Optional list of question types corresponding to each text.
                          If None, types will be inferred by the model.
            question_names: Optional list of question names. If None, names will be generated.
            model: Language model to use for inference. If None, uses default model.
            scenario_keys: Optional list of scenario keys to include in question texts.
                          Each key will be added as {{ scenario.<key> }} in the questions.
            verbose: Whether to show the underlying survey generation process (default: True)

        Returns:
            Survey: A new Survey instance with the questions

        Examples:
            >>> from edsl import Survey
            >>> texts = ["How satisfied are you?", "What is your age?"]
            >>> survey = Survey.generate_from_questions(texts)  # doctest: +SKIP
            >>> types = ["LinearScale", "Numerical"]
            >>> names = ["satisfaction", "age"]
            >>> survey = Survey.generate_from_questions(texts, types, names)  # doctest: +SKIP
            >>> survey = Survey.generate_from_questions(texts, scenario_keys=["product_name"])  # doctest: +SKIP
            >>> survey = Survey.generate_from_questions(texts, verbose=False)  # doctest: +SKIP
        """
        from ..language_models import Model

        # Use default model if none provided
        m = model or Model()

        # Prepare question data
        question_data = []
        for i, text in enumerate(question_texts):
            # Add scenario variables to question text if provided
            if scenario_keys:
                # Create a prompt to enhance the question text with scenario variables
                scenario_vars = ", ".join(
                    [f"{{{{ scenario.{key} }}}}" for key in scenario_keys]
                )
                enhanced_text = (
                    f"{text} (Use these variables where appropriate: {scenario_vars})"
                )
            else:
                enhanced_text = text

            data = {"question_text": enhanced_text}

            # Add question type if provided
            if question_types and i < len(question_types):
                data["question_type"] = question_types[i]

            # Add question name if provided
            if question_names and i < len(question_names):
                data["question_name"] = question_names[i]
            else:
                data["question_name"] = f"q{i}"

            question_data.append(data)

        # Infer missing question types
        if question_types is None or any(not qt for qt in question_types):
            # First try pattern-based inference (more reliable)
            for data in question_data:
                if "question_type" not in data or not data["question_type"]:
                    text = data["question_text"].lower()
                    if any(
                        word in text
                        for word in [
                            "satisfied",
                            "satisfaction",
                            "happy",
                            "pleased",
                            "likely",
                            "probability",
                            "chance",
                            "often",
                            "frequency",
                            "agree",
                            "disagree",
                            "opinion",
                        ]
                    ):
                        data["question_type"] = "MultipleChoice"
                    elif any(
                        word in text
                        for word in [
                            "features",
                            "functionality",
                            "capabilities",
                            "value",
                            "like",
                            "benefits",
                            "advantages",
                            "perks",
                            "important",
                            "channels",
                            "methods",
                            "ways",
                            "prefer",
                            "contact",
                        ]
                    ):
                        data["question_type"] = "CheckBox"
                    elif any(
                        word in text
                        for word in ["rate", "rating", "scale", "level", "score"]
                    ):
                        data["question_type"] = "LinearScale"
                    else:
                        data["question_type"] = "FreeText"

            # Then try LLM inference to refine types and add options
            try:
                if verbose:
                    question_data = SurveyGenerator._infer_question_types(question_data, m)
                else:
                    # Suppress output when verbose=False
                    import sys
                    from io import StringIO

                    old_stdout = sys.stdout
                    sys.stdout = StringIO()
                    try:
                        question_data = SurveyGenerator._infer_question_types(question_data, m)
                    finally:
                        sys.stdout = old_stdout
            except Exception:
                # LLM inference failed, but we already have types from pattern matching
                pass

        # Convert to proper question objects and ensure scenario variables are included
        questions = []
        for i, data in enumerate(question_data):
            # Ensure scenario variables are included in question text
            if scenario_keys and "question_text" in data:
                original_text = data["question_text"]
                # Check if scenario variables are already in the text
                has_scenario_vars = any(
                    f"{{{{ scenario.{key} }}}}" in original_text
                    for key in scenario_keys
                )
                if not has_scenario_vars:
                    # Add scenario variables to the question text
                    scenario_vars = " ".join(
                        [f"{{{{ scenario.{key} }}}}" for key in scenario_keys]
                    )
                    data["question_text"] = (
                        f"{original_text} (Context: {scenario_vars})"
                    )

            question_obj = SurveyGenerator._create_question_from_dict(data, f"q{i}")
            questions.append(question_obj)

        return survey_class(questions)

    @staticmethod
    def _infer_question_types(
        question_data: List[Dict[str, Any]], model: "LanguageModel"
    ) -> List[Dict[str, Any]]:
        """Infer question types for question data using an LLM."""
        from ..questions import QuestionList

        prompt = """
You are helping construct a structured survey schema.

For EACH input item, output a JSON list of objects where every object has:
- question_text (string; required)
- question_type (one of: "FreeText", "MultipleChoice", "LinearScale", "CheckBox"; required)
- question_name (short slug; lowercase letters, numbers, underscores; optional if provided already)
- question_options (array; REQUIRED for all types except FreeText; for LinearScale, provide an ordered array of numeric labels)

Guidelines:
- Preserve intent and wording where possible.
- If the input already includes 'question_type' and/or 'question_options', respect them unless obviously invalid.
- If no name is provided, generate a SHORT slug from the text (max 20 chars, like "feel_today" not "how_do_you_feel_today").
- ALWAYS generate appropriate question_options for MultipleChoice, LinearScale, and CheckBox questions.
- For MultipleChoice/CheckBox: provide 3-7 relevant, mutually exclusive options.
- For LinearScale: provide integer arrays like [1,2,3,4,5] or [1,2,3,4,5,6,7,8,9,10].
- Keep options concise, neutral, and non-leading.
- If the question text mentions scenario variables (like {{ scenario.key }}), incorporate them naturally into the final question_text.
- Return ONLY valid JSON (a list). No commentary.
        """.strip()

        q = QuestionList(
            question_name="design",
            question_text=prompt + "\n\nINPUT:\n" + str(question_data),
            max_list_items=len(question_data),
        )

        # Get the structured response
        result = q.by(model).run()
        out = result.select("design").to_list()[0]

        # Handle case where LLM doesn't return expected format
        if not out:
            # Fallback: return original data with FreeText type
            normalized = []
            for i, data in enumerate(question_data):
                normalized_row = {
                    "question_text": data["question_text"],
                    "question_type": data.get("question_type", "FreeText"),
                    "question_name": data.get("question_name", f"q{i}"),
                    "question_options": data.get("question_options", []),
                }
                normalized.append(normalized_row)
            return normalized

        # Normalize the response
        normalized = []
        for i, row in enumerate(out):
            normalized_row = {
                "question_text": row.get(
                    "question_text", question_data[i]["question_text"]
                ).strip(),
                "question_type": row.get("question_type", "FreeText").strip(),
                "question_name": row.get("question_name")
                or question_data[i].get("question_name", f"q{i}"),
                "question_options": row.get("question_options", []),
            }
            normalized.append(normalized_row)

        return normalized

    @staticmethod
    def _create_question_from_dict(
        data: Dict[str, Any], default_name: str
    ) -> "QuestionBase":
        """Create a question object from a dictionary."""
        from ..questions import (
            QuestionFreeText,
            QuestionMultipleChoice,
            QuestionLinearScale,
            QuestionCheckBox,
            QuestionNumerical,
            QuestionLikertFive,
            QuestionYesNo,
            QuestionRank,
            QuestionBudget,
            QuestionList,
            QuestionMatrix,
        )

        def _slugify(text: str, fallback_len: int = 8) -> str:
            # Remove common question words and create shorter slugs
            text = text.lower()

            # Remove question marks and extra whitespace first
            text = re.sub(r"[?]+", "", text).strip()

            # Split into words
            words = re.findall(r"\b\w+\b", text)

            # Remove common question words from the beginning
            question_words = {
                "what",
                "how",
                "when",
                "where",
                "why",
                "which",
                "who",
                "do",
                "are",
                "would",
                "have",
                "did",
                "will",
                "can",
                "should",
                "could",
                "is",
                "was",
                "were",
                "does",
                "you",
                "your",
                "the",
                "a",
                "an",
            }

            # Filter out question words and common words
            meaningful_words = [word for word in words if word not in question_words]

            # Take first 2 meaningful words
            if len(meaningful_words) >= 2:
                slug = "_".join(meaningful_words[:2])
            elif len(meaningful_words) == 1:
                slug = meaningful_words[0]
            elif len(words) >= 2:
                # Fallback: use first 2 words even if they contain question words
                slug = "_".join(words[:2])
            elif len(words) == 1:
                slug = words[0]
            else:
                slug = f"q_{uuid.uuid4().hex[:fallback_len]}"

            # Clean up the slug
            slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
            if not slug:
                slug = f"q_{uuid.uuid4().hex[:fallback_len]}"
            return slug[:20]  # Shorter max length

        qtype = data.get("question_type", "FreeText").lower()
        name = data.get("question_name") or _slugify(data["question_text"])
        text = data["question_text"]
        opts = data.get("question_options", [])

        if qtype in ("freetext", "free_text", "text"):
            return QuestionFreeText(question_name=name, question_text=text)

        if qtype in ("multiplechoice", "multiple_choice", "mc", "single_select"):
            # Provide default options if none given
            if not opts:
                # Generate more contextual options based on question text
                if any(
                    word in text.lower()
                    for word in ["satisfied", "satisfaction", "happy", "pleased"]
                ):
                    opts = [
                        "Very satisfied",
                        "Satisfied",
                        "Neutral",
                        "Dissatisfied",
                        "Very dissatisfied",
                    ]
                elif any(
                    word in text.lower() for word in ["likely", "probability", "chance"]
                ):
                    opts = [
                        "Very likely",
                        "Likely",
                        "Neutral",
                        "Unlikely",
                        "Very unlikely",
                    ]
                elif any(
                    word in text.lower() for word in ["often", "frequency", "regularly"]
                ):
                    opts = ["Very often", "Often", "Sometimes", "Rarely", "Never"]
                elif any(
                    word in text.lower() for word in ["agree", "disagree", "opinion"]
                ):
                    opts = [
                        "Strongly agree",
                        "Agree",
                        "Neutral",
                        "Disagree",
                        "Strongly disagree",
                    ]
                else:
                    opts = ["Yes", "No", "Maybe"]
            return QuestionMultipleChoice(
                question_name=name,
                question_text=text,
                question_options=opts,
            )

        if qtype in ("linearscale", "linear_scale", "scale", "likert"):
            # Handle LinearScale options properly
            if isinstance(opts, dict):
                # Convert dict format to list of integers
                if "min" in opts and "max" in opts:
                    min_val = opts["min"]
                    max_val = opts["max"]
                    opts = list(range(min_val, max_val + 1))
                elif "scale_min" in opts and "scale_max" in opts:
                    min_val = opts["scale_min"]
                    max_val = opts["scale_max"]
                    opts = list(range(min_val, max_val + 1))
                else:
                    opts = [1, 2, 3, 4, 5]  # Default
            elif not opts:
                opts = [1, 2, 3, 4, 5]  # Default

            return QuestionLinearScale(
                question_name=name,
                question_text=text,
                question_options=opts,
            )

        if qtype in ("checkbox", "check_box", "multi_select", "multiselect"):
            # Provide default options if none given
            if not opts:
                # Generate more contextual options based on question text
                if any(
                    word in text.lower()
                    for word in [
                        "features",
                        "functionality",
                        "capabilities",
                        "value",
                        "like",
                    ]
                ):
                    opts = [
                        "User interface",
                        "Performance",
                        "Security",
                        "Customer support",
                        "Pricing",
                    ]
                elif any(
                    word in text.lower()
                    for word in ["benefits", "advantages", "perks", "important"]
                ):
                    opts = [
                        "Health insurance",
                        "Retirement plan",
                        "Remote work",
                        "Paid time off",
                        "Professional development",
                    ]
                elif any(
                    word in text.lower()
                    for word in ["channels", "methods", "ways", "prefer", "contact"]
                ):
                    opts = ["Email", "Phone", "In-person", "Online chat", "Mobile app"]
                else:
                    opts = ["Option 1", "Option 2", "Option 3", "Option 4"]
            return QuestionCheckBox(
                question_name=name,
                question_text=text,
                question_options=opts,
            )

        if qtype in ("numerical", "number", "numeric"):
            min_val = data.get("min_value")
            max_val = data.get("max_value")
            return QuestionNumerical(
                question_name=name,
                question_text=text,
                min_value=min_val,
                max_value=max_val,
            )

        if qtype in ("likert_five", "likert5", "likert"):
            return QuestionLikertFive(
                question_name=name,
                question_text=text,
            )

        if qtype in ("yes_no", "yesno", "boolean"):
            return QuestionYesNo(
                question_name=name,
                question_text=text,
            )

        if qtype in ("rank", "ranking"):
            if not opts:
                opts = ["Option 1", "Option 2", "Option 3", "Option 4"]
            return QuestionRank(
                question_name=name,
                question_text=text,
                question_options=opts,
            )

        if qtype in ("budget", "allocation"):
            if not opts:
                opts = ["Option 1", "Option 2", "Option 3", "Option 4"]
            return QuestionBudget(
                question_name=name,
                question_text=text,
                question_options=opts,
                budget_sum=100,  # Default budget
            )

        if qtype in ("list", "array"):
            max_items = data.get("max_items", 10)
            return QuestionList(
                question_name=name,
                question_text=text,
                max_list_items=max_items,
            )

        if qtype in ("matrix", "grid"):
            # Matrix requires rows (items) and columns (options)
            rows = data.get("rows", opts if opts else ["Row 1", "Row 2", "Row 3"])
            columns = data.get("columns", ["Column 1", "Column 2", "Column 3"])
            return QuestionMatrix(
                question_name=name,
                question_text=text,
                question_items=rows,
                question_options=columns,
            )

        # Fallback to FreeText
        return QuestionFreeText(question_name=name, question_text=text)

