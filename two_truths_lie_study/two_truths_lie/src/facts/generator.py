"""LLM-based fact generator using multiple models for diversity."""

import json
import re
from typing import List, Dict, Optional
from pathlib import Path

from edsl import Model, QuestionFreeText

from .schema import Fact, CATEGORIES
from ..logging_config import get_logger

logger = get_logger("fact_generator")


# Best models for fact generation
# Using proven models that work with EDSL API proxy
BEST_MODELS = [
    "claude-3-7-sonnet-20250219",  # Sonnet 3.7 - latest stable Claude model
    "chatgpt-4o-latest",           # GPT-4o - strong factual recall
    "gemini-2.5-flash"             # Gemini 2.5 Flash - fast and capable
]


class FactGenerator:
    """Generates unusual-but-true facts using LLMs."""

    def __init__(self, model_name: str):
        """Initialize generator with specific model.

        Args:
            model_name: EDSL model name
        """
        self.model_name = model_name
        self.model = Model(model_name)
        logger.info(f"Initialized FactGenerator with model: {model_name}")

    def generate_facts(
        self,
        category: str,
        count: int = 10,
        use_api_proxy: bool = True
    ) -> List[dict]:
        """Generate facts for a category.

        Args:
            category: Category from CATEGORIES list
            count: Number of facts to generate
            use_api_proxy: Use EDSL API proxy (default True)

        Returns:
            List of fact dictionaries (not yet Fact objects)
        """
        if category not in CATEGORIES:
            raise ValueError(f"Invalid category: {category}. Must be one of {CATEGORIES}")

        logger.info(f"Generating {count} facts for category '{category}' using {self.model_name}")

        prompt = self._build_generation_prompt(category, count)

        question = QuestionFreeText(
            question_name="facts",
            question_text=prompt
        )

        try:
            results = question.by(self.model).run(
                use_api_proxy=use_api_proxy,
                offload_execution=False,
                progress_bar=True
            )

            response = results.select("answer.facts").first()
            logger.debug(f"Raw response: {response[:200]}...")

            facts = self._parse_facts(response, category)
            logger.info(f"Successfully parsed {len(facts)} facts from response")

            return facts

        except Exception as e:
            logger.error(f"Fact generation failed: {e}", exc_info=True)
            return []

    def _build_generation_prompt(self, category: str, count: int) -> str:
        """Build the fact generation prompt.

        Args:
            category: Fact category
            count: Number of facts to generate

        Returns:
            Formatted prompt string
        """
        category_descriptions = {
            "historical_oddities": "surprising events from history, unusual laws, wars over trivial causes",
            "scientific_discoveries": "counter-intuitive scientific findings, quantum phenomena, biological anomalies",
            "cultural_traditions": "unusual customs from around the world, festival rituals, social norms",
            "natural_phenomena": "strange occurrences in nature, weather anomalies, geological formations",
            "animal_behaviors": "unexpected animal adaptations and actions, mating rituals, survival mechanisms",
            "food_origins": "surprising histories of common foods, accidental inventions, cultural transfers",
            "unlikely_inventions": "products with unexpected origin stories, failed experiments that became hits",
            "archaeological_mysteries": "puzzling discoveries from the past, artifacts that challenge timelines",
            "forgotten_figures": "remarkable people lost to history, unsung heroes, eccentric geniuses",
            "unexpected_connections": "surprising links between unrelated things, historical coincidences",
            "sports": "unusual sporting events, bizarre records, unexpected athletic feats, strange rules"
        }

        description = category_descriptions.get(category, category.replace("_", " "))

        return f"""You are an expert curator of unusual but TRUE facts, like a researcher for Ripley's Believe It or Not.

Your task: Generate {count} fascinating TRUE facts in the category: {category}
Category description: {description}

Requirements:
- Facts MUST be genuinely TRUE and verifiable
- Facts should be surprising, counter-intuitive, or little-known
- Include rich specific details (dates, names, numbers, locations)
- Provide reputable source citations
- NEVER fabricate facts - if uncertain, skip it

For each fact, provide a JSON object with these fields:
- "core_claim": The surprising fact in 1-2 clear sentences
- "supporting_details": Object with specific details like {{"date": "1932", "location": "Australia", "participants": "..."}}
- "source_citation": Verifiable source (book, paper, museum, reputable website)
- "why_strange": Brief note (1 sentence) on what makes it unbelievable

Return ONLY a valid JSON array of fact objects. No other text.

Example format:
[
  {{
    "core_claim": "The Great Emu War of 1932 was an actual military operation where the Australian army deployed soldiers with machine guns against emus—and lost.",
    "supporting_details": {{
      "date": "November 1932",
      "location": "Campion district, Western Australia",
      "participants": "Royal Australian Artillery",
      "weapons": "Two Lewis guns, 10,000 rounds",
      "outcome": "Emus won; operation ineffective"
    }},
    "source_citation": "Australian Parliament Hansard, 1932; Museum of Australian Democracy",
    "why_strange": "A modern military lost a war against birds"
  }}
]

Generate {count} facts now:"""

    def _parse_facts(self, response: str, category: str) -> List[dict]:
        """Parse LLM response into structured facts.

        Args:
            response: Raw LLM response
            category: Category for these facts

        Returns:
            List of fact dictionaries
        """
        try:
            # Try to find JSON array in response
            start = response.find('[')
            end = response.rfind(']') + 1

            if start >= 0 and end > start:
                json_str = response[start:end]

                # Try standard JSON parsing first
                try:
                    facts = json.loads(json_str)
                except json.JSONDecodeError:
                    # Try with json-repair for malformed JSON
                    try:
                        from json_repair import repair_json
                        facts = json.loads(repair_json(json_str))
                    except Exception as e:
                        logger.warning(f"JSON repair failed: {e}")
                        facts = []

                if not isinstance(facts, list):
                    logger.warning("Parsed JSON is not a list")
                    return []

                # Validate and enrich each fact
                valid_facts = []
                for i, fact in enumerate(facts):
                    if not isinstance(fact, dict):
                        logger.warning(f"Fact {i} is not a dictionary, skipping")
                        continue

                    # Ensure required fields exist
                    if "core_claim" not in fact and "content" not in fact:
                        logger.warning(f"Fact {i} missing core_claim/content, skipping")
                        continue

                    # Add metadata
                    fact['category'] = category
                    fact['model_generated_by'] = self.model_name

                    valid_facts.append(fact)

                return valid_facts

        except Exception as e:
            logger.error(f"Failed to parse facts: {e}", exc_info=True)

        return []


class MultiModelFactGenerator:
    """Generates facts using multiple models for diversity."""

    def __init__(self, models: Optional[List[str]] = None):
        """Initialize with list of models.

        Args:
            models: List of model names (default: BEST_MODELS)
        """
        self.models = models or BEST_MODELS
        logger.info(f"Initialized MultiModelFactGenerator with models: {', '.join(self.models)}")

    def generate_facts(
        self,
        category: str,
        count: int,
        distribute_evenly: bool = True
    ) -> List[dict]:
        """Generate facts using multiple models.

        Args:
            category: Category from CATEGORIES
            count: Total number of facts to generate
            distribute_evenly: Split count evenly across models

        Returns:
            List of fact dictionaries from all models
        """
        all_facts = []

        if distribute_evenly:
            # Split evenly, handle remainder
            base_count = count // len(self.models)
            remainder = count % len(self.models)

            for i, model_name in enumerate(self.models):
                model_count = base_count + (1 if i < remainder else 0)

                logger.info(f"Generating {model_count} facts with {model_name}")

                generator = FactGenerator(model_name)
                facts = generator.generate_facts(category, model_count)
                all_facts.extend(facts)

        else:
            # Each model generates full count (for redundancy)
            for model_name in self.models:
                generator = FactGenerator(model_name)
                facts = generator.generate_facts(category, count)
                all_facts.extend(facts)

        logger.info(f"Total facts generated: {len(all_facts)}")
        return all_facts

    def generate_all_categories(
        self,
        facts_per_category: int = 10,
        categories: Optional[List[str]] = None
    ) -> Dict[str, List[dict]]:
        """Generate facts for all categories.

        Args:
            facts_per_category: Number of facts per category
            categories: List of categories (default: all CATEGORIES)

        Returns:
            Dictionary mapping category -> list of facts
        """
        categories = categories or CATEGORIES
        results = {}

        for category in categories:
            logger.info(f"Generating facts for category: {category}")
            facts = self.generate_facts(category, facts_per_category)
            results[category] = facts

        return results
