"""Enhanced fact schema for fact database generator."""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict
from datetime import datetime
import json


# Category definitions
CATEGORIES = [
    "historical_oddities",
    "scientific_discoveries",
    "cultural_traditions",
    "natural_phenomena",
    "animal_behaviors",
    "food_origins",
    "unlikely_inventions",
    "archaeological_mysteries",
    "forgotten_figures",
    "unexpected_connections",
    "sports"  # Added per user request
]


@dataclass
class Fact:
    """Enhanced fact schema matching spec requirements.

    Attributes:
        id: Unique identifier (e.g., "hist_001")
        category: Category ID from CATEGORIES
        title: Short title (for backward compatibility)
        content: The core fact claim (1-2 sentences)
        source: Source citation (verifiable)
        strangeness_rating: How implausible it sounds (1-10)
        supporting_details: Specific names, dates, numbers, locations
        verification_status: "verified", "likely_true", "uncertain", "likely_false"
        specificity_score: How many concrete details (1-10)
        created_at: ISO timestamp
        model_generated_by: Which LLM generated this fact
    """

    # Core fields (required)
    id: str
    category: str
    title: str
    content: str  # Maps to core_claim in spec
    source: str  # Maps to source_citation in spec
    strangeness_rating: int = 5

    # Enhanced fields (optional for backward compatibility)
    supporting_details: Optional[Dict[str, str]] = None
    verification_status: str = "verified"
    specificity_score: Optional[int] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    model_generated_by: Optional[str] = None

    def __post_init__(self):
        """Validate fields."""
        if self.category not in CATEGORIES:
            raise ValueError(
                f"Invalid category '{self.category}'. "
                f"Must be one of: {', '.join(CATEGORIES)}"
            )

        if not (1 <= self.strangeness_rating <= 10):
            raise ValueError("strangeness_rating must be between 1 and 10")

        if self.specificity_score is not None:
            if not (1 <= self.specificity_score <= 10):
                raise ValueError("specificity_score must be between 1 and 10")

        if self.verification_status not in ["verified", "likely_true", "uncertain", "likely_false", "needs_review"]:
            raise ValueError(
                f"Invalid verification_status '{self.verification_status}'. "
                f"Must be one of: verified, likely_true, uncertain, likely_false, needs_review"
            )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "Fact":
        """Create from dictionary."""
        return cls(**data)

    @classmethod
    def from_generated(cls, gen_data: dict, category: str, fact_id: str) -> "Fact":
        """Create from LLM-generated data.

        Args:
            gen_data: Dictionary from LLM with keys:
                - core_claim or content
                - supporting_details
                - source_citation or source
                - why_strange (optional)
            category: Category for this fact
            fact_id: Unique ID to assign

        Returns:
            Fact instance
        """
        # Extract core claim
        content = gen_data.get("core_claim") or gen_data.get("content", "")

        # Extract source
        source = gen_data.get("source_citation") or gen_data.get("source", "")

        # Extract supporting details
        details = gen_data.get("supporting_details", {})

        # Generate title from first 50 chars of content
        title = content[:50] + "..." if len(content) > 50 else content

        # Get model if provided
        model = gen_data.get("model_generated_by")

        return cls(
            id=fact_id,
            category=category,
            title=title,
            content=content,
            source=source,
            supporting_details=details,
            verification_status="needs_review",
            model_generated_by=model
        )


@dataclass
class FactDatabaseMetadata:
    """Metadata for fact database."""

    version: str = "1.0.0"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    total_facts: int = 0
    categories: list = field(default_factory=list)
    generation_models: list = field(default_factory=list)
    min_strangeness: int = 6
    min_specificity: int = 5

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)
