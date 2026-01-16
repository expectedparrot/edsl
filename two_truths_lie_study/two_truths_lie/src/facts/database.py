"""Fact database for Two Truths and a Lie game."""

from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
import json
import random


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

    These are curated, verifiable facts that are surprising but true.
    """
    facts = [
        # Science facts
        Fact(
            id="sci_001",
            category="science",
            title="Neutron Star Density",
            content="A teaspoon of neutron star material would weigh about 6 billion tons on Earth. Neutron stars are so dense that a sugar-cube-sized amount of neutron-star material would weigh about as much as Mount Everest.",
            source="NASA Science",
            strangeness_rating=9
        ),
        Fact(
            id="sci_002",
            category="science",
            title="Honey Never Spoils",
            content="Archaeologists have found 3,000-year-old honey in Egyptian tombs that was still perfectly edible. Honey's low moisture content, high acidity, and natural hydrogen peroxide production make it essentially immortal.",
            source="Smithsonian Magazine",
            strangeness_rating=7
        ),
        Fact(
            id="sci_003",
            category="science",
            title="Glass is a Liquid",
            content="Glass is technically not a solid but an amorphous solid, sometimes called a supercooled liquid. However, the myth that old windows are thicker at the bottom because glass flows is false - that's due to old manufacturing techniques.",
            source="Scientific American",
            strangeness_rating=6
        ),

        # History facts
        Fact(
            id="hist_001",
            category="history",
            title="Cleopatra and the Pyramids",
            content="Cleopatra lived closer in time to the Moon landing than to the construction of the Great Pyramid. The Great Pyramid was built around 2560 BCE, Cleopatra lived around 30 BCE, and the Moon landing was in 1969 CE.",
            source="Historical Timeline Analysis",
            strangeness_rating=8
        ),
        Fact(
            id="hist_002",
            category="history",
            title="Oxford Older Than Aztec Empire",
            content="Oxford University is older than the Aztec Empire. Teaching at Oxford began in 1096, while the Aztec Empire was founded in 1428 when the Triple Alliance was formed.",
            source="Oxford University Archives",
            strangeness_rating=8
        ),
        Fact(
            id="hist_003",
            category="history",
            title="Fax Machines Before Telephones",
            content="The fax machine was invented in 1843 by Alexander Bain, 33 years before Alexander Graham Bell patented the telephone in 1876. Early fax machines used pendulums and telegraph wires.",
            source="IEEE History Center",
            strangeness_rating=7
        ),

        # Biology facts
        Fact(
            id="bio_001",
            category="biology",
            title="Octopus Hearts",
            content="Octopuses have three hearts: two branchial hearts pump blood through each of the two gills, while a third systemic heart pumps blood through the body. When an octopus swims, the systemic heart stops beating, which is why they prefer crawling.",
            source="Marine Biology Journal",
            strangeness_rating=7
        ),
        Fact(
            id="bio_002",
            category="biology",
            title="Human Shedding",
            content="Humans shed about 600,000 particles of skin every hour, amounting to about 1.5 pounds of skin per year. A significant portion of household dust is actually dead human skin cells.",
            source="American Academy of Dermatology",
            strangeness_rating=6
        ),
        Fact(
            id="bio_003",
            category="biology",
            title="Immortal Jellyfish",
            content="The Turritopsis dohrnii jellyfish is biologically immortal. When stressed, sick, or old, it can revert its cells back to their earliest form and start its life cycle over again, essentially aging backwards.",
            source="Nature Scientific Reports",
            strangeness_rating=9
        ),

        # Geography facts
        Fact(
            id="geo_001",
            category="geography",
            title="Canada's Coastline",
            content="Canada has the longest coastline of any country in the world at 202,080 kilometers. If you were to walk Canada's entire coastline at 20 km per day, it would take about 27 years.",
            source="Statistics Canada",
            strangeness_rating=5
        ),
        Fact(
            id="geo_002",
            category="geography",
            title="Russia's Time Zones",
            content="Russia spans 11 time zones, more than any other country. When it's Monday morning in Kaliningrad, it's already Monday evening in Kamchatka.",
            source="Russian Geographic Society",
            strangeness_rating=6
        ),
        Fact(
            id="geo_003",
            category="geography",
            title="Reno and Los Angeles",
            content="Reno, Nevada is actually further west than Los Angeles, California. Due to the irregular shape of California and Nevada's border, Reno sits at 119.8 degrees west longitude while LA is at 118.2 degrees.",
            source="US Geological Survey",
            strangeness_rating=7
        ),

        # Technology facts
        Fact(
            id="tech_001",
            category="technology",
            title="QWERTY Keyboard Design",
            content="The QWERTY keyboard layout was designed in the 1870s specifically to slow down typists. On early typewriters, typing too fast caused mechanical jams, so Christopher Sholes arranged the keys to separate commonly used letter pairs.",
            source="Smithsonian National Museum of American History",
            strangeness_rating=6
        ),
        Fact(
            id="tech_002",
            category="technology",
            title="Nintendo's Age",
            content="Nintendo was founded in 1889, originally as a playing card company. It's 136 years old, making it older than the Eiffel Tower (1889), Coca-Cola (1886), and the Wall Street Journal (1889).",
            source="Nintendo Company History",
            strangeness_rating=7
        ),
        Fact(
            id="tech_003",
            category="technology",
            title="Moon Computing Power",
            content="The computer guidance system used on the Apollo 11 moon landing had less processing power than a modern USB-C charger. The Apollo Guidance Computer had about 74KB of memory and operated at 0.043 MHz.",
            source="NASA Apollo Archives",
            strangeness_rating=8
        ),

        # Culture facts
        Fact(
            id="cul_001",
            category="culture",
            title="Vatican's Crime Rate",
            content="Vatican City has the highest crime rate per capita in the world, primarily due to pickpocketing and petty theft by tourists. With only about 800 residents and millions of visitors annually, the crime-per-resident ratio is extremely high.",
            source="Vatican Security Reports",
            strangeness_rating=7
        ),
        Fact(
            id="cul_002",
            category="culture",
            title="Finnish Word for Drinking Alone",
            content="The Finnish word 'kalsarikännit' specifically refers to the act of getting drunk at home, alone, in your underwear, with no intention of going out. Finland added it to their official dictionary.",
            source="Finnish Language Institute",
            strangeness_rating=8
        ),
        Fact(
            id="cul_003",
            category="culture",
            title="Traffic Lights in Japan",
            content="In Japan, traffic lights show blue instead of green. Due to historical linguistic reasons, the Japanese language traditionally used one word (青/ao) for both blue and green, so when traffic lights were standardized, they were called 'blue' lights.",
            source="Japan National Police Agency",
            strangeness_rating=7
        ),
    ]

    db = FactDatabase()
    for fact in facts:
        db.add_fact(fact)

    return db
