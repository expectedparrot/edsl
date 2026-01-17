"""Fact database for Two Truths and a Lie game."""

from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
import json
import random
from pathlib import Path


@dataclass(frozen=True)
class Fact:
    """Represents a strange-but-true fact.

    Attributes:
        id: Unique identifier
        category: Category (science, history, culture, biology, geography, technology)
        title: Short title for the fact
        content: The actual fact content
        source: Source/citation for the fact
        strangeness_rating: How surprising/strange this fact is (1-10)
    """

    id: str
    category: str
    title: str
    content: str
    source: str
    strangeness_rating: int = 5

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "Fact":
        """Create from dictionary."""
        return cls(**data)


class FactDatabase:
    """Database of strange-but-true facts."""

    def __init__(self, facts: Optional[List[Fact]] = None):
        self._facts: Dict[str, Fact] = {}
        self._by_category: Dict[str, List[str]] = {}

        if facts:
            for fact in facts:
                self.add_fact(fact)

    def add_fact(self, fact: Fact) -> None:
        """Add a fact to the database."""
        self._facts[fact.id] = fact

        if fact.category not in self._by_category:
            self._by_category[fact.category] = []
        self._by_category[fact.category].append(fact.id)

    def get_fact(self, fact_id: str) -> Optional[Fact]:
        """Get a fact by ID."""
        return self._facts.get(fact_id)

    def get_facts_by_category(self, category: str) -> List[Fact]:
        """Get all facts in a category."""
        fact_ids = self._by_category.get(category, [])
        return [self._facts[fid] for fid in fact_ids]

    def get_random_fact(self, category: Optional[str] = None) -> Optional[Fact]:
        """Get a random fact, optionally from a specific category."""
        if category:
            facts = self.get_facts_by_category(category)
        else:
            facts = list(self._facts.values())

        if not facts:
            return None
        return random.choice(facts)

    def get_random_facts(
        self,
        count: int,
        category: Optional[str] = None,
        exclude_ids: Optional[List[str]] = None
    ) -> List[Fact]:
        """Get multiple random facts without replacement."""
        if category:
            facts = self.get_facts_by_category(category)
        else:
            facts = list(self._facts.values())

        if exclude_ids:
            facts = [f for f in facts if f.id not in exclude_ids]

        if len(facts) < count:
            raise ValueError(
                f"Not enough facts available. Need {count}, have {len(facts)}"
            )

        return random.sample(facts, count)

    @property
    def categories(self) -> List[str]:
        """Get all available categories."""
        return list(self._by_category.keys())

    def __len__(self) -> int:
        """Get total number of facts."""
        return len(self._facts)


def get_default_facts() -> FactDatabase:
    """Get the default database of strange-but-true facts.

    Loads facts from two sources:
    1. data/curated_facts.json - Manually curated facts (original 18)
    2. data/raw/*.json - LLM-generated facts (81+ facts)

    Returns:
        FactDatabase with all available facts
    """
    db = FactDatabase()
    base_dir = Path(__file__).parent.parent.parent  # Get to project root

    # Load curated facts (manually maintained)
    curated_file = base_dir / "data" / "curated_facts.json"
    if curated_file.exists():
        try:
            with open(curated_file, 'r') as f:
                curated_data = json.load(f)
                for fact_dict in curated_data:
                    # Only keep core fields that match our Fact dataclass
                    fact = Fact(
                        id=fact_dict["id"],
                        category=fact_dict["category"],
                        title=fact_dict["title"],
                        content=fact_dict["content"],
                        source=fact_dict["source"],
                        strangeness_rating=fact_dict.get("strangeness_rating", 5)
                    )
                    db.add_fact(fact)
        except Exception as e:
            print(f"Warning: Failed to load curated facts: {e}")

    # Load generated facts (LLM-generated)
    raw_dir = base_dir / "data" / "raw"
    if raw_dir.exists():
        for json_file in raw_dir.glob("*.json"):
            try:
                with open(json_file, 'r') as f:
                    generated_data = json.load(f)
                    for fact_dict in generated_data:
                        # Extract core_claim or content
                        content = fact_dict.get("core_claim") or fact_dict.get("content", "")

                        # Extract source_citation or source
                        source = fact_dict.get("source_citation") or fact_dict.get("source", "")

                        # Generate ID if not present
                        fact_id = fact_dict.get("id")
                        if not fact_id:
                            category_prefix = fact_dict["category"][:4]
                            fact_id = f"{category_prefix}_{hash(content) % 10000:04d}"

                        # Create title from first 50 chars of content
                        title = fact_dict.get("title") or (content[:50] + "..." if len(content) > 50 else content)

                        fact = Fact(
                            id=fact_id,
                            category=fact_dict["category"],
                            title=title,
                            content=content,
                            source=source,
                            strangeness_rating=fact_dict.get("strangeness_rating", 7)
                        )
                        db.add_fact(fact)
            except Exception as e:
                print(f"Warning: Failed to load {json_file.name}: {e}")

    return db
