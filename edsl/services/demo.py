#!/usr/bin/env python
"""
Demo script for EDSL External Services.

Tests each service accessor with example queries.
Run individual tests or all at once.

Usage:
    python demo.py              # Run all tests
    python demo.py openalex     # Run single test
    python demo.py --list       # List available services
"""

import sys
import signal
from contextlib import contextmanager


class TimeoutError(Exception):
    pass


@contextmanager
def timeout(seconds):
    """Context manager for timeout on Unix systems."""

    def handler(signum, frame):
        raise TimeoutError(f"Timed out after {seconds} seconds")

    old_handler = signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


# Service definitions: (name, test_func, description, timeout_secs)
SERVICES = {
    # Free services (no API key)
    "openalex": (
        lambda sl: sl.openalex.works("machine learning", per_page=3),
        "Open scholarly metadata (papers, authors)",
        30,
    ),
    "worldbank": (
        lambda sl: sl.worldbank.indicator(
            "NY.GDP.MKTP.CD", country="US", date="2020:2023"
        ),
        "World Bank development indicators",
        30,
    ),
    "wikipedia": (
        lambda sl: sl.wikipedia.tables(
            "https://en.wikipedia.org/wiki/List_of_countries_by_GDP_(nominal)",
            table_index=2,
        ),
        "Wikipedia table extraction",
        30,
    ),
    "arxiv": (
        lambda sl: sl.arxiv.search("transformer attention", max_results=3),
        "arXiv academic papers (requires: pip install arxiv)",
        30,
    ),
    "youtube": (
        lambda sl: sl.youtube.transcript("dQw4w9WgXcQ"),
        "YouTube transcripts (requires: pip install youtube-transcript-api)",
        30,
    ),
    "semantic_scholar": (
        lambda sl: sl.semantic_scholar.search("deep learning", limit=3),
        "Semantic Scholar papers (optional API key)",
        30,
    ),
    "census": (
        lambda sl: sl.census.get(["NAME", "B01001_001E"], geography="state:06"),
        "US Census data (optional API key)",
        30,
    ),
    # Services requiring API keys
    "exa": (
        lambda sl: sl.exa.search("AI startups", num_results=3),
        "AI web search (requires: EXA_API_KEY, pip install exa-py)",
        30,
    ),
    "firecrawl": (
        lambda sl: sl.firecrawl.scrape("https://example.com"),
        "Web scraping (requires: FIRECRAWL_API_KEY)",
        30,
    ),
    "fred": (
        lambda sl: sl.fred.series("UNRATE", observation_start="2023-01-01"),
        "Federal Reserve data (requires: FRED_API_KEY)",
        30,
    ),
    "reddit": (
        lambda sl: sl.reddit.subreddit("MachineLearning", limit=3),
        "Reddit posts (requires: REDDIT_CLIENT_ID/SECRET, pip install praw)",
        30,
    ),
    "huggingface": (
        lambda sl: sl.huggingface.load("rotten_tomatoes", split="test"),
        "HuggingFace datasets (requires: pip install datasets)",
        60,
    ),
    # Image generation
    "replicate": (
        lambda sl: sl.replicate.generate_image("A cat", model="flux"),
        "Replicate ML models (requires: REPLICATE_API_TOKEN, pip install replicate)",
        60,
    ),
    "fal": (
        lambda sl: sl.fal.generate("Abstract art"),
        "fal.ai images (requires: FAL_KEY, pip install fal-client)",
        60,
    ),
    "dalle": (
        lambda sl: sl.dalle.generate("A sunset"),
        "DALL-E images (requires: OPENAI_API_KEY, pip install openai)",
        60,
    ),
}


def test_service(name: str):
    """Test a single service."""
    if name not in SERVICES:
        print(f"Unknown service: {name}")
        print(f"Available: {', '.join(SERVICES.keys())}")
        return False

    func, description, timeout_secs = SERVICES[name]

    print(f"\n{'='*60}")
    print(f"📦 ScenarioList.{name}")
    print(f"   {description}")
    print("=" * 60)

    # Lazy import to avoid loading all services at once
    from edsl import ScenarioList

    try:
        with timeout(timeout_secs):
            result = func(ScenarioList)
            print(f"✅ Success! Got {len(result)} results")
            if len(result) > 0:
                first = dict(list(result)[0])
                keys = list(first.keys())[:3]
                preview = {k: str(first.get(k, ""))[:40] for k in keys}
                print(f"   Preview: {preview}")
            return True
    except TimeoutError as e:
        print(f"⏱️  Timeout: {e}")
        return False
    except ImportError as e:
        print(f"⚠️  Missing package: {e}")
        return False
    except ValueError as e:
        if "API" in str(e) or "KEY" in str(e) or "required" in str(e).lower():
            print(f"🔑 Missing API key: {e}")
        else:
            print(f"❌ Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        return False


def list_services():
    """List all available services."""
    print("\n📋 Available EDSL Service Accessors:\n")

    print("FREE (no API key):")
    free = [
        "openalex",
        "worldbank",
        "wikipedia",
        "arxiv",
        "youtube",
        "semantic_scholar",
        "census",
    ]
    for name in free:
        if name in SERVICES:
            _, desc, _ = SERVICES[name]
            print(f"  • ScenarioList.{name:<20} {desc[:50]}")

    print("\nREQUIRES API KEY:")
    paid = [
        "exa",
        "firecrawl",
        "fred",
        "reddit",
        "huggingface",
        "replicate",
        "fal",
        "dalle",
    ]
    for name in paid:
        if name in SERVICES:
            _, desc, _ = SERVICES[name]
            print(f"  • ScenarioList.{name:<20} {desc[:50]}")


def main():
    args = sys.argv[1:]

    if "--list" in args or "-l" in args:
        list_services()
        return

    if "--help" in args or "-h" in args:
        print(__doc__)
        return

    if args:
        # Test specific services
        for name in args:
            test_service(name)
    else:
        # Test free services only by default
        print("\n🚀 EDSL External Services Demo")
        print("Testing FREE services (no API key required)...\n")

        free_services = ["openalex", "worldbank", "wikipedia"]

        results = {}
        for name in free_services:
            results[name] = test_service(name)

        print("\n" + "=" * 60)
        success = sum(1 for v in results.values() if v)
        print(f"\n✅ {success}/{len(results)} services succeeded")

        print("\n💡 To test more services:")
        print("   python demo.py arxiv          # Test arxiv (needs pip install arxiv)")
        print("   python demo.py exa            # Test exa (needs API key)")
        print("   python demo.py --list         # See all services")


if __name__ == "__main__":
    main()
