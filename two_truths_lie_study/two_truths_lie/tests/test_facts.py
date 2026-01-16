"""Tests for fact database."""

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.facts.database import Fact, FactDatabase, get_default_facts


class TestFact:
    """Tests for Fact model."""

    def test_fact_creation(self):
        """Test creating a fact."""
        fact = Fact(
            id="test_001",
            category="science",
            title="Test Fact",
            content="This is a test fact.",
            source="Test Source",
            strangeness_rating=7
        )
        assert fact.id == "test_001"
        assert fact.category == "science"
        assert fact.strangeness_rating == 7

    def test_fact_serialization(self):
        """Test fact serialization."""
        fact = Fact(
            id="test_001",
            category="science",
            title="Test Fact",
            content="This is a test fact.",
            source="Test Source"
        )
        d = fact.to_dict()
        fact2 = Fact.from_dict(d)
        assert fact == fact2


class TestFactDatabase:
    """Tests for FactDatabase."""

    def test_add_and_get_fact(self):
        """Test adding and retrieving a fact."""
        db = FactDatabase()
        fact = Fact(
            id="test_001",
            category="science",
            title="Test",
            content="Content",
            source="Source"
        )
        db.add_fact(fact)
        assert db.get_fact("test_001") == fact

    def test_get_facts_by_category(self):
        """Test filtering facts by category."""
        db = FactDatabase()
        facts = [
            Fact(id="sci_1", category="science", title="S1", content="C1", source="Src"),
            Fact(id="hist_1", category="history", title="H1", content="C2", source="Src"),
            Fact(id="sci_2", category="science", title="S2", content="C3", source="Src"),
        ]
        for f in facts:
            db.add_fact(f)

        science_facts = db.get_facts_by_category("science")
        assert len(science_facts) == 2
        assert all(f.category == "science" for f in science_facts)

    def test_get_random_fact(self):
        """Test getting a random fact."""
        db = FactDatabase()
        fact = Fact(
            id="test_001",
            category="science",
            title="Test",
            content="Content",
            source="Source"
        )
        db.add_fact(fact)
        random_fact = db.get_random_fact()
        assert random_fact == fact

    def test_get_random_facts_exclusion(self):
        """Test getting random facts with exclusion."""
        db = FactDatabase()
        facts = [
            Fact(id=f"test_{i}", category="science", title=f"T{i}", content=f"C{i}", source="Src")
            for i in range(5)
        ]
        for f in facts:
            db.add_fact(f)

        selected = db.get_random_facts(2, exclude_ids=["test_0", "test_1"])
        assert len(selected) == 2
        assert all(f.id not in ["test_0", "test_1"] for f in selected)


class TestDefaultFacts:
    """Tests for the default fact database."""

    def test_default_facts_loaded(self):
        """Test that default facts are loaded."""
        db = get_default_facts()
        assert len(db) >= 15

    def test_default_facts_have_all_categories(self):
        """Test that default facts cover all expected categories."""
        db = get_default_facts()
        expected_categories = ["science", "history", "biology", "geography", "technology", "culture"]
        for category in expected_categories:
            facts = db.get_facts_by_category(category)
            assert len(facts) >= 1, f"No facts found for category: {category}"

    def test_each_fact_has_required_fields(self):
        """Test that each fact has all required fields."""
        db = get_default_facts()
        for category in db.categories:
            for fact in db.get_facts_by_category(category):
                assert fact.id
                assert fact.category
                assert fact.title
                assert fact.content
                assert fact.source
                assert 1 <= fact.strangeness_rating <= 10
