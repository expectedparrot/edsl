"""
Service Accessors: Clean API for calling external services from ScenarioList.

Provides accessor classes that enable syntax like:
    ScenarioList.firecrawl.scrape(url)
    ScenarioList.exa.search(query)
    ScenarioList.huggingface.load(dataset)

Now uses the unified task system which supports:
- All external services
- Task dependencies
- Task groups and jobs
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Union, TYPE_CHECKING
import importlib.util

if TYPE_CHECKING:
    from edsl.scenarios import ScenarioList


# Track which service workers have been started
_active_workers: Set[str] = set()


def _ensure_service_worker(service_name: str) -> None:
    """Ensure a unified worker is running for the given service/task type.

    Uses EXPECTED_PARROT_URL and EXPECTED_PARROT_API_KEY from environment.
    """
    global _active_workers

    from . import TaskDispatcher
    from edsl.services_runner import require_client

    # Get or create server
    server = TaskDispatcher.get_default_server()
    if server is None:
        server = require_client(purpose="service execution")
        TaskDispatcher.set_default_server(server)

    # Workers are managed by the HTTP server, so we just mark this service as active
    # The server's internal worker pool handles task execution
    _active_workers.add(service_name)


# Dependency requirements for each service
SERVICE_DEPENDENCIES: Dict[str, List[tuple]] = {
    # (module_name, pip_package, optional)
    "arxiv": [("arxiv", "arxiv", False)],
    "census": [],  # uses requests only
    "crunchbase": [],  # uses requests only
    "diffbot": [],  # uses requests only
    "exa": [("exa_py", "exa-py", False)],
    "fal": [("fal_client", "fal-client", False)],
    "firecrawl": [("firecrawl", "firecrawl-py", False)],
    "fred": [],  # uses requests only
    "huggingface": [("datasets", "datasets", False)],
    "openalex": [],  # uses requests only
    "openai_images": [("openai", "openai", False)],
    "reddit": [("praw", "praw", False)],
    "reducto": [("reducto", "reductoai", False)],
    "replicate": [("replicate", "replicate", False)],
    "semantic_scholar": [],  # uses requests only
    "wikipedia": [("wikipediaapi", "wikipedia-api", True)],  # optional for search
    "worldbank": [],  # uses requests only
    "youtube": [("youtube_transcript_api", "youtube-transcript-api", False)],
    "google_sheets": [("gspread", "gspread", False)],
    "perplexity": [],  # uses requests only
    "vibes": [],  # uses openai only, already available
    "survey_vibes": [],  # uses openai only, already available
    "agent_vibes": [],  # uses openai only, already available
    "results_vibes": [],  # uses openai only, already available
    "survey_import": [("pandas", "pandas", False)],  # for Excel conversion
    "embeddings": [("openai", "openai", False)],  # for OpenAI embeddings
    "embeddings_search": [("openai", "openai", False)],  # for semantic search
}

# Services that should use replace_with() for versioned results
# Maps service name to list of class names it extends
VERSIONED_SERVICES: Dict[str, List[str]] = {
    "agent_vibes": ["AgentList"],
    "survey_vibes": ["Survey"],
    "results_vibes": ["Results"],
    "scenario_vibes": ["ScenarioList"],
    "dataset_vibes": ["Dataset"],
}

_versioned_services_registered = False


def _register_versioned_services() -> None:
    """Register metadata for versioned services.

    This allows services that run remotely to be marked as versioned,
    so the accessor knows to use replace_with() for results.

    Called lazily to avoid circular imports.

    Note: We only register metadata, not a stub service class.
    This is because services run remotely and the dispatcher should
    use result_pattern parsing, not a local parse_result method.
    """
    global _versioned_services_registered
    if _versioned_services_registered:
        return
    _versioned_services_registered = True

    from .registry import ServiceRegistry, ServiceMetadata

    for service_name, extends in VERSIONED_SERVICES.items():
        # Only register metadata if not already present
        # Don't register a service class - let the remote server handle execution
        if service_name not in ServiceRegistry._metadata:
            ServiceRegistry._metadata[service_name] = ServiceMetadata(
                name=service_name,
                service_class=None,  # No local class - runs remotely
                extends=extends,
                versioned=True,
            )
            # Update extends index for accessor lookup
            for class_name in extends:
                if class_name not in ServiceRegistry._extends_index:
                    ServiceRegistry._extends_index[class_name] = []
                if service_name not in ServiceRegistry._extends_index[class_name]:
                    ServiceRegistry._extends_index[class_name].append(service_name)


def check_dependencies(service_name: str) -> None:
    """
    Check if required dependencies for a service are installed.
    Raises ImportError with installation instructions if missing.
    """
    deps = SERVICE_DEPENDENCIES.get(service_name, [])
    missing = []

    for module_name, pip_package, optional in deps:
        if importlib.util.find_spec(module_name) is None:
            if not optional:
                missing.append(pip_package)

    if missing:
        packages = " ".join(missing)
        raise ImportError(
            f"Missing required package(s) for {service_name}. "
            f"Install with: pip install {packages}"
        )


class FirecrawlAccessor:
    """
    Accessor for Firecrawl operations on ScenarioList.

    Usage:
        >>> sl = ScenarioList.firecrawl.scrape("https://example.com")
        >>> sl = ScenarioList.firecrawl.crawl("https://docs.python.org", limit=10)
        >>> sl = ScenarioList.firecrawl.search("python web scraping")
    """

    def __init__(self):
        self._ensure_server()

    def __repr__(self) -> str:
        return """FirecrawlAccessor - Web scraping and data extraction

Methods:
  .scrape(url)              Scrape content from a URL
  .scrape([url1, url2])     Scrape multiple URLs
  .crawl(url, limit=10)     Crawl a website (follow links)
  .search(query)            Web search with content extraction
  .extract(url, schema={})  AI-powered structured extraction
  .map_urls(url)            Discover URLs without scraping

Examples:
  sl = ScenarioList.firecrawl.scrape("https://example.com")
  sl = ScenarioList.firecrawl.crawl("https://docs.python.org", limit=20)
  sl = ScenarioList.firecrawl.search("python tutorials")
  sl = ScenarioList.firecrawl.extract(url, schema={"title": "string", "price": "number"})

Requires: FIRECRAWL_API_KEY environment variable"""

    def _repr_html_(self) -> str:
        return """
<div style="font-family: monospace; padding: 10px; border: 1px solid #ddd; border-radius: 8px; background: #f9f9f9;">
<b style="color: #e74c3c;">FirecrawlAccessor</b> - Web scraping and data extraction<br><br>
<b>Methods:</b><br>
<code>.scrape(url)</code> - Scrape content from a URL<br>
<code>.scrape([url1, url2])</code> - Scrape multiple URLs<br>
<code>.crawl(url, limit=10)</code> - Crawl a website (follow links)<br>
<code>.search(query)</code> - Web search with content extraction<br>
<code>.extract(url, schema={})</code> - AI-powered structured extraction<br>
<code>.map_urls(url)</code> - Discover URLs without scraping<br><br>
<b>Examples:</b><br>
<code>sl = ScenarioList.firecrawl.scrape("https://example.com")</code><br>
<code>sl = ScenarioList.firecrawl.crawl("https://docs.python.org", limit=20)</code><br>
<code>sl = ScenarioList.firecrawl.search("python tutorials")</code><br><br>
<i style="color: #888;">Requires: FIRECRAWL_API_KEY environment variable</i>
</div>
"""

    def _ensure_server(self):
        """Ensure a server and worker are running."""
        _ensure_service_worker("firecrawl")

    def _dispatch_and_wait(self, params: dict, verbose: bool = True) -> "ScenarioList":
        """Dispatch task and wait for result."""
        from . import dispatch

        pending = dispatch("firecrawl", params)
        return pending.result(verbose=verbose)

    def scrape(
        self,
        url: Union[str, List[str]],
        verbose: bool = True,
        **kwargs,
    ) -> "ScenarioList":
        """
        Scrape content from one or more URLs.

        Args:
            url: Single URL or list of URLs to scrape
            verbose: Show progress updates
            **kwargs: Additional Firecrawl options

        Returns:
            ScenarioList with scraped content
        """
        if isinstance(url, list):
            return self._dispatch_and_wait(
                {"operation": "scrape", "urls": url, **kwargs},
                verbose=verbose,
            )
        return self._dispatch_and_wait(
            {"operation": "scrape", "url": url, **kwargs},
            verbose=verbose,
        )

    def crawl(
        self,
        url: str,
        limit: int = 10,
        verbose: bool = True,
        **kwargs,
    ) -> "ScenarioList":
        """
        Crawl a website and extract content from discovered pages.

        Args:
            url: Base URL to start crawling from
            limit: Maximum pages to crawl
            verbose: Show progress updates
            **kwargs: Additional Firecrawl options

        Returns:
            ScenarioList with crawled pages
        """
        return self._dispatch_and_wait(
            {"operation": "crawl", "url": url, "limit": limit, **kwargs},
            verbose=verbose,
        )

    def search(
        self,
        query: Union[str, List[str]],
        verbose: bool = True,
        **kwargs,
    ) -> "ScenarioList":
        """
        Search the web and extract content from results.

        Args:
            query: Search query or list of queries
            verbose: Show progress updates
            **kwargs: Additional Firecrawl options

        Returns:
            ScenarioList with search results
        """
        if isinstance(query, list):
            return self._dispatch_and_wait(
                {"operation": "search", "queries": query, **kwargs},
                verbose=verbose,
            )
        return self._dispatch_and_wait(
            {"operation": "search", "query": query, **kwargs},
            verbose=verbose,
        )

    def extract(
        self,
        url: Union[str, List[str]],
        schema: Optional[dict] = None,
        prompt: Optional[str] = None,
        verbose: bool = True,
        **kwargs,
    ) -> "ScenarioList":
        """
        Extract structured data from URLs using AI.

        Args:
            url: URL or list of URLs to extract from
            schema: JSON schema for extraction
            prompt: Natural language prompt for extraction
            verbose: Show progress updates
            **kwargs: Additional Firecrawl options

        Returns:
            ScenarioList with extracted data
        """
        params = {"operation": "extract", "schema": schema, "prompt": prompt, **kwargs}
        if isinstance(url, list):
            params["urls"] = url
        else:
            params["url"] = url
        return self._dispatch_and_wait(params, verbose=verbose)

    def map_urls(
        self,
        url: str,
        limit: Optional[int] = None,
        verbose: bool = True,
        **kwargs,
    ) -> "ScenarioList":
        """
        Discover URLs from a website without scraping content.

        Args:
            url: Base URL to discover links from
            limit: Maximum URLs to discover
            verbose: Show progress updates
            **kwargs: Additional Firecrawl options

        Returns:
            ScenarioList with discovered URLs
        """
        return self._dispatch_and_wait(
            {"operation": "map_urls", "url": url, "limit": limit, **kwargs},
            verbose=verbose,
        )


class ExaAccessor:
    """
    Accessor for Exa operations on ScenarioList.

    Usage:
        >>> sl = ScenarioList.exa.search("AI researchers at Stanford")
    """

    def __init__(self):
        self._ensure_server()

    def __repr__(self) -> str:
        return """ExaAccessor - AI-powered web search

Methods:
  .search(query, num_results=10)    Fast semantic search (default)
  .webset_search(query, count=100)  Structured extraction (premium, slow)
  
Search Options:
  num_results=10                Number of results
  include_text=True             Include page text content  
  search_type="auto"            "auto", "neural", "keyword", or "deep"

Webset Options (premium feature - requires credits):
  criteria=[...]                Filter criteria for results
  enrichments=[...]             Data enrichment specifications

Examples:
  # Simple search (fast, cheap)
  sl = ScenarioList.exa.search("Economists studying online labor markets")
  sl = ScenarioList.exa.search("AI startups", num_results=20)
  
  # Webset search (slow, requires credits)
  sl = ScenarioList.exa.webset_search(
      "Sales leaders at fintech companies",
      criteria=["holds sales leadership position"],
      enrichments=[{"description": "Years of experience", "format": "number"}]
  )

Requires: EXA_API_KEY environment variable"""

    def _repr_html_(self) -> str:
        return """
<div style="font-family: monospace; padding: 10px; border: 1px solid #ddd; border-radius: 8px; background: #f9f9f9;">
<b style="color: #3498db;">ExaAccessor</b> - AI-powered web search<br><br>
<b>Methods:</b><br>
<code>.search(query, num_results=10)</code> - Fast semantic search (default)<br>
<code>.webset_search(query, count=100)</code> - Structured extraction (premium)<br><br>
<b>Search Options:</b><br>
<code>num_results=10</code> - Number of results<br>
<code>include_text=True</code> - Include page text content<br>
<code>search_type="auto"</code> - "auto", "neural", "keyword", or "deep"<br><br>
<b>Webset Options (premium - requires credits):</b><br>
<code>criteria=[...]</code> - Filter criteria for results<br>
<code>enrichments=[...]</code> - Data enrichment specifications<br><br>
<b>Examples:</b><br>
<code>sl = ScenarioList.exa.search("AI startups", num_results=20)</code><br>
<code>sl = ScenarioList.exa.webset_search("Sales leaders", criteria=[...])</code><br><br>
<i style="color: #888;">Requires: EXA_API_KEY environment variable</i>
</div>
"""

    def _ensure_server(self):
        """Ensure a server and worker are running."""
        _ensure_service_worker("exa")

    def search(
        self,
        query: str,
        num_results: int = 10,
        include_text: bool = True,
        search_type: str = "auto",
        verbose: bool = True,
        **kwargs,
    ) -> "ScenarioList":
        """
        Search the web using Exa's fast semantic search.

        This is the simple/cheap mode that uses Exa's regular search API.

        Args:
            query: Search query
            num_results: Number of results to return (default 10)
            include_text: Include full page text (default True)
            search_type: "auto", "neural", "keyword", or "deep" (default "auto")
            verbose: Show progress updates
            **kwargs: Additional Exa options

        Returns:
            ScenarioList with search results
        """
        check_dependencies("exa")
        from . import dispatch

        pending = dispatch(
            "exa",
            {
                "query": query,
                "mode": "simple",
                "num_results": num_results,
                "include_text": include_text,
                "search_type": search_type,
                **kwargs,
            },
        )
        return pending.result(verbose=verbose)

    def webset_search(
        self,
        query: str,
        count: int = 100,
        criteria: Optional[List[str]] = None,
        enrichments: Optional[List[dict]] = None,
        verbose: bool = True,
        **kwargs,
    ) -> "ScenarioList":
        """
        Search using Exa's premium webset feature with structured extraction.

        NOTE: This requires Exa credits and can take 1-2 minutes.

        Args:
            query: Search query
            count: Number of results
            criteria: List of criteria to filter results
            enrichments: List of enrichment specifications
            verbose: Show progress updates
            **kwargs: Additional Exa options

        Returns:
            ScenarioList with enriched search results
        """
        check_dependencies("exa")
        from . import dispatch

        pending = dispatch(
            "exa",
            {
                "query": query,
                "mode": "webset",
                "count": count,
                "criteria": criteria,
                "enrichments": enrichments,
                **kwargs,
            },
        )
        return pending.result(verbose=verbose)


class HuggingFaceAccessor:
    """
    Accessor for HuggingFace operations on ScenarioList.

    Usage:
        >>> sl = ScenarioList.huggingface.load("squad", split="train")
    """

    def __init__(self):
        self._ensure_server()

    def __repr__(self) -> str:
        return """HuggingFaceAccessor - Load datasets from Hugging Face Hub

Methods:
  .load(dataset_name)           Load a dataset
  
Options:
  config_name="..."             Configuration (if dataset has multiple)
  split="train"                 Split to load (train/test/validation)

Examples:
  sl = ScenarioList.huggingface.load("squad")
  sl = ScenarioList.huggingface.load("squad", split="validation")
  sl = ScenarioList.huggingface.load("glue", config_name="cola", split="train")
  sl = ScenarioList.huggingface.load("rotten_tomatoes", split="test")

Browse datasets: https://huggingface.co/datasets
Optional: HUGGINGFACE_TOKEN for private datasets"""

    def _repr_html_(self) -> str:
        return """
<div style="font-family: monospace; padding: 10px; border: 1px solid #ddd; border-radius: 8px; background: #f9f9f9;">
<b style="color: #ff9900;">HuggingFaceAccessor</b> - Load datasets from Hugging Face Hub<br><br>
<b>Methods:</b><br>
<code>.load(dataset_name)</code> - Load a dataset<br><br>
<b>Options:</b><br>
<code>config_name="..."</code> - Configuration (if dataset has multiple)<br>
<code>split="train"</code> - Split to load (train/test/validation)<br><br>
<b>Examples:</b><br>
<code>sl = ScenarioList.huggingface.load("squad")</code><br>
<code>sl = ScenarioList.huggingface.load("squad", split="validation")</code><br>
<code>sl = ScenarioList.huggingface.load("glue", config_name="cola")</code><br><br>
<i style="color: #888;">Browse: <a href="https://huggingface.co/datasets">huggingface.co/datasets</a></i><br>
<i style="color: #888;">Optional: HUGGINGFACE_TOKEN for private datasets</i>
</div>
"""

    def _ensure_server(self):
        """Ensure a server and worker are running."""
        _ensure_service_worker("huggingface")

    def load(
        self,
        dataset_name: str,
        config_name: Optional[str] = None,
        split: Optional[str] = None,
        verbose: bool = True,
        **kwargs,
    ) -> "ScenarioList":
        """
        Load a dataset from Hugging Face Hub.

        Args:
            dataset_name: Name of the dataset (e.g., "squad", "glue")
            config_name: Configuration name if dataset has multiple
            split: Split to load (e.g., "train", "test")
            verbose: Show progress updates
            **kwargs: Additional load_dataset options

        Returns:
            ScenarioList with dataset records
        """
        from . import dispatch

        pending = dispatch(
            "huggingface",
            {
                "dataset_name": dataset_name,
                "config_name": config_name,
                "split": split,
                **kwargs,
            },
        )
        return pending.result(verbose=verbose)


class WikipediaAccessor:
    """
    Accessor for Wikipedia operations on ScenarioList.

    Usage:
        >>> sl = ScenarioList.wikipedia.tables("https://en.wikipedia.org/wiki/...")
        >>> sl = ScenarioList.wikipedia.search("machine learning")
    """

    def __init__(self):
        self._ensure_server()

    def __repr__(self) -> str:
        return """WikipediaAccessor - Extract data from Wikipedia

Methods:
  .tables(url)                  Extract tables from a Wikipedia page
  .search(query)                Search Wikipedia articles
  .summary(title)               Get article summary
  .content(title)               Get full article content
  
Tables Options:
  table_index=0                 Which table to extract (None = all)

Search Options:
  num_results=10                Number of results
  language="en"                 Wikipedia language code

Examples:
  # Extract tables
  sl = ScenarioList.wikipedia.tables(
      "https://en.wikipedia.org/wiki/List_of_countries_by_GDP"
  )
  
  # Search articles
  sl = ScenarioList.wikipedia.search("machine learning", num_results=5)
  
  # Get article summary
  sl = ScenarioList.wikipedia.summary("Python (programming language)")

No API key required"""

    def _repr_html_(self) -> str:
        return """
<div style="font-family: monospace; padding: 10px; border: 1px solid #ddd; border-radius: 8px; background: #f9f9f9;">
<b style="color: #2ecc71;">WikipediaAccessor</b> - Extract data from Wikipedia<br><br>
<b>Methods:</b><br>
<code>.tables(url)</code> - Extract tables from a Wikipedia page<br>
<code>.search(query)</code> - Search Wikipedia articles<br>
<code>.summary(title)</code> - Get article summary<br>
<code>.content(title)</code> - Get full article content<br><br>
<b>Tables Options:</b><br>
<code>table_index=0</code> - Which table to extract (None = all)<br><br>
<b>Search Options:</b><br>
<code>num_results=10</code> - Number of results<br>
<code>language="en"</code> - Wikipedia language code<br><br>
<b>Examples:</b><br>
<code>sl = ScenarioList.wikipedia.tables("https://...wiki/List_of...")</code><br>
<code>sl = ScenarioList.wikipedia.search("machine learning")</code><br>
<code>sl = ScenarioList.wikipedia.summary("Python (programming language)")</code><br><br>
<i style="color: #888;">No API key required</i>
</div>
"""

    def _ensure_server(self):
        """Ensure a server and worker are running."""
        _ensure_service_worker("wikipedia")

    def tables(
        self,
        url: str,
        table_index: Optional[int] = None,
        verbose: bool = True,
        **kwargs,
    ) -> "ScenarioList":
        """
        Extract tables from a Wikipedia page.

        Args:
            url: Wikipedia page URL
            table_index: Which table to extract (None = all tables)
            verbose: Show progress updates
            **kwargs: Additional options

        Returns:
            ScenarioList with table rows
        """
        from . import dispatch

        pending = dispatch(
            "wikipedia",
            {
                "mode": "tables",
                "url": url,
                "table_index": table_index,
                **kwargs,
            },
        )
        return pending.result(verbose=verbose)

    def _check_wikipedia_api(self) -> None:
        """Check if wikipedia-api is installed (required for search/summary/content)."""
        if importlib.util.find_spec("wikipediaapi") is None:
            raise ImportError(
                "wikipedia-api is required for search/summary/content operations.\n"
                "Install with: pip install wikipedia-api\n\n"
                "Note: .tables() works without this dependency."
            )

    def search(
        self,
        query: str,
        num_results: int = 10,
        language: str = "en",
        verbose: bool = True,
        **kwargs,
    ) -> "ScenarioList":
        """
        Search Wikipedia for articles.

        Args:
            query: Search query
            num_results: Number of results to return
            language: Wikipedia language code
            verbose: Show progress updates
            **kwargs: Additional options

        Returns:
            ScenarioList with search results
        """
        self._check_wikipedia_api()
        from . import dispatch

        pending = dispatch(
            "wikipedia",
            {
                "mode": "search",
                "query": query,
                "num_results": num_results,
                "language": language,
                **kwargs,
            },
        )
        return pending.result(verbose=verbose)

    def summary(
        self,
        title: str,
        language: str = "en",
        verbose: bool = True,
        **kwargs,
    ) -> "ScenarioList":
        """
        Get the summary of a Wikipedia article.

        Args:
            title: Article title
            language: Wikipedia language code
            verbose: Show progress updates
            **kwargs: Additional options

        Returns:
            ScenarioList with article summary
        """
        self._check_wikipedia_api()
        from . import dispatch

        pending = dispatch(
            "wikipedia",
            {
                "mode": "summary",
                "title": title,
                "language": language,
                **kwargs,
            },
        )
        return pending.result(verbose=verbose)

    def content(
        self,
        title: str,
        language: str = "en",
        verbose: bool = True,
        **kwargs,
    ) -> "ScenarioList":
        """
        Get the full content of a Wikipedia article.

        Args:
            title: Article title
            language: Wikipedia language code
            verbose: Show progress updates
            **kwargs: Additional options

        Returns:
            ScenarioList with full article content
        """
        self._check_wikipedia_api()
        from . import dispatch

        pending = dispatch(
            "wikipedia",
            {
                "mode": "content",
                "title": title,
                "language": language,
                **kwargs,
            },
        )
        return pending.result(verbose=verbose)


class ReductoAccessor:
    """
    Accessor for Reducto document processing on ScenarioList.

    Usage:
        >>> sl = ScenarioList.reducto.parse("https://example.com/document.pdf")
    """

    def __init__(self):
        self._ensure_server()

    def __repr__(self) -> str:
        return """ReductoAccessor - AI-powered PDF and document parsing

Methods:
  .parse(document_url)          Parse a document and extract content
  .extract(document_url, schema) Extract structured data with a schema
  
Options:
  document_path="..."           Local file path instead of URL

Examples:
  # Parse a PDF
  sl = ScenarioList.reducto.parse("https://example.com/report.pdf")
  
  # Extract structured data
  sl = ScenarioList.reducto.extract(
      "https://example.com/invoice.pdf",
      schema={
          "invoice_number": "string",
          "total": "number",
          "items": [{"description": "string", "amount": "number"}]
      }
  )

Requires: REDUCTO_API_KEY environment variable"""

    def _repr_html_(self) -> str:
        return """
<div style="font-family: monospace; padding: 10px; border: 1px solid #ddd; border-radius: 8px; background: #f9f9f9;">
<b style="color: #9b59b6;">ReductoAccessor</b> - AI-powered PDF and document parsing<br><br>
<b>Methods:</b><br>
<code>.parse(document_url)</code> - Parse a document and extract content<br>
<code>.extract(document_url, schema)</code> - Extract structured data with a schema<br><br>
<b>Options:</b><br>
<code>document_path="..."</code> - Local file path instead of URL<br><br>
<b>Examples:</b><br>
<code>sl = ScenarioList.reducto.parse("https://example.com/report.pdf")</code><br>
<code>sl = ScenarioList.reducto.extract(url, schema={...})</code><br><br>
<i style="color: #888;">Requires: REDUCTO_API_KEY environment variable</i>
</div>
"""

    def _ensure_server(self):
        """Ensure a server and worker are running."""
        _ensure_service_worker("reducto")

    def parse(
        self,
        document_url: Optional[str] = None,
        document_path: Optional[str] = None,
        verbose: bool = True,
        **kwargs,
    ) -> "ScenarioList":
        """
        Parse a document and extract all content.

        Args:
            document_url: URL of the document
            document_path: Local path to the document
            verbose: Show progress updates
            **kwargs: Additional Reducto options

        Returns:
            ScenarioList with extracted content
        """
        from . import dispatch

        pending = dispatch(
            "reducto",
            {
                "mode": "parse",
                "document_url": document_url,
                "document_path": document_path,
                **kwargs,
            },
        )
        return pending.result(verbose=verbose)

    def extract(
        self,
        document_url: Optional[str] = None,
        document_path: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        verbose: bool = True,
        **kwargs,
    ) -> "ScenarioList":
        """
        Extract structured data from a document using a schema.

        Args:
            document_url: URL of the document
            document_path: Local path to the document
            schema: Extraction schema defining fields to extract
            verbose: Show progress updates
            **kwargs: Additional Reducto options

        Returns:
            ScenarioList with extracted structured data
        """
        from . import dispatch

        pending = dispatch(
            "reducto",
            {
                "mode": "extract",
                "document_url": document_url,
                "document_path": document_path,
                "schema": schema,
                **kwargs,
            },
        )
        return pending.result(verbose=verbose)


class ArxivAccessor:
    """Accessor for arXiv academic paper search."""

    def __init__(self):
        self._ensure_server()

    def __repr__(self) -> str:
        return """ArxivAccessor - Search arXiv for academic papers

Methods:
  .search(query)                Search for papers

Options:
  max_results=10                Number of results
  sort_by="relevance"           Sort: relevance, lastUpdatedDate, submittedDate

Examples:
  sl = ScenarioList.arxiv.search("transformer neural networks")
  sl = ScenarioList.arxiv.search("machine learning", max_results=50)

No API key required
Requires: pip install arxiv"""

    def _ensure_server(self):
        _ensure_service_worker("arxiv")

    def search(
        self, query: str, max_results: int = 10, verbose: bool = True, **kwargs
    ) -> "ScenarioList":
        check_dependencies("arxiv")
        from . import dispatch

        pending = dispatch(
            "arxiv", {"query": query, "max_results": max_results, **kwargs}
        )
        return pending.result(verbose=verbose)


class SemanticScholarAccessor:
    """Accessor for Semantic Scholar academic paper search."""

    def __init__(self):
        self._ensure_server()

    def __repr__(self) -> str:
        return """SemanticScholarAccessor - Search academic papers with citations

Methods:
  .search(query)                Search for papers

Options:
  limit=20                      Number of results
  year="2020-2024"              Filter by year range

Examples:
  sl = ScenarioList.semantic_scholar.search("deep learning")
  sl = ScenarioList.semantic_scholar.search("NLP", year="2022-2024")

Optional: SEMANTIC_SCHOLAR_API_KEY for higher rate limits"""

    def _ensure_server(self):
        _ensure_service_worker("semantic_scholar")

    def search(
        self, query: str, limit: int = 20, verbose: bool = True, **kwargs
    ) -> "ScenarioList":
        from . import dispatch

        pending = dispatch(
            "semantic_scholar", {"query": query, "limit": limit, **kwargs}
        )
        return pending.result(verbose=verbose)


class OpenAlexAccessor:
    """Accessor for OpenAlex scholarly data."""

    def __init__(self):
        self._ensure_server()

    def __repr__(self) -> str:
        return """OpenAlexAccessor - Open scholarly metadata (papers, authors, institutions)

Methods:
  .works(search)                Search papers/works
  .authors(search)              Search authors
  .institutions(search)         Search institutions

Options:
  per_page=25                   Results per page
  filter="..."                  OpenAlex filter string

Examples:
  sl = ScenarioList.openalex.works("climate change")
  sl = ScenarioList.openalex.authors("machine learning")

No API key required"""

    def _ensure_server(self):
        _ensure_service_worker("openalex")

    def works(
        self, search: str, per_page: int = 25, verbose: bool = True, **kwargs
    ) -> "ScenarioList":
        from . import dispatch

        pending = dispatch(
            "openalex",
            {"entity": "works", "search": search, "per_page": per_page, **kwargs},
        )
        return pending.result(verbose=verbose)

    def authors(
        self, search: str, per_page: int = 25, verbose: bool = True, **kwargs
    ) -> "ScenarioList":
        from . import dispatch

        pending = dispatch(
            "openalex",
            {"entity": "authors", "search": search, "per_page": per_page, **kwargs},
        )
        return pending.result(verbose=verbose)

    def institutions(
        self, search: str, per_page: int = 25, verbose: bool = True, **kwargs
    ) -> "ScenarioList":
        from . import dispatch

        pending = dispatch(
            "openalex",
            {
                "entity": "institutions",
                "search": search,
                "per_page": per_page,
                **kwargs,
            },
        )
        return pending.result(verbose=verbose)


class YouTubeAccessor:
    """Accessor for YouTube transcript extraction."""

    def __init__(self):
        self._ensure_server()

    def __repr__(self) -> str:
        return """YouTubeAccessor - Extract transcripts from YouTube videos

Methods:
  .transcript(video_id)         Get transcript from video ID
  .transcript(video_url)        Get transcript from URL

Options:
  languages=["en"]              Preferred languages

Examples:
  sl = ScenarioList.youtube.transcript("dQw4w9WgXcQ")
  sl = ScenarioList.youtube.transcript("https://youtube.com/watch?v=...")

No API key required
Requires: pip install youtube-transcript-api"""

    def _ensure_server(self):
        _ensure_service_worker("youtube")

    def transcript(
        self,
        video: str,
        languages: Optional[List[str]] = None,
        verbose: bool = True,
        **kwargs,
    ) -> "ScenarioList":
        check_dependencies("youtube")
        from . import dispatch

        params = {"languages": languages or ["en"], **kwargs}
        if video.startswith("http"):
            params["video_url"] = video
        else:
            params["video_id"] = video
        pending = dispatch("youtube", params)
        return pending.result(verbose=verbose)


class RedditAccessor:
    """Accessor for Reddit data."""

    def __init__(self):
        self._ensure_server()

    def __repr__(self) -> str:
        return """RedditAccessor - Fetch posts and comments from Reddit

Methods:
  .subreddit(name)              Get posts from a subreddit
  .search(query)                Search Reddit

Options:
  sort="hot"                    Sort: hot, new, top, rising
  limit=25                      Number of posts
  include_comments=False        Include top comments

Examples:
  sl = ScenarioList.reddit.subreddit("MachineLearning")
  sl = ScenarioList.reddit.search("AI agents", limit=50)

Requires: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET
Requires: pip install praw"""

    def _ensure_server(self):
        _ensure_service_worker("reddit")

    def subreddit(
        self,
        name: str,
        sort: str = "hot",
        limit: int = 25,
        verbose: bool = True,
        **kwargs,
    ) -> "ScenarioList":
        check_dependencies("reddit")
        from . import dispatch

        pending = dispatch(
            "reddit", {"subreddit": name, "sort": sort, "limit": limit, **kwargs}
        )
        return pending.result(verbose=verbose)

    def search(
        self, query: str, limit: int = 25, verbose: bool = True, **kwargs
    ) -> "ScenarioList":
        check_dependencies("reddit")
        from . import dispatch

        pending = dispatch("reddit", {"search_query": query, "limit": limit, **kwargs})
        return pending.result(verbose=verbose)


class FREDAccessor:
    """Accessor for Federal Reserve Economic Data."""

    def __init__(self):
        self._ensure_server()

    def __repr__(self) -> str:
        return """FREDAccessor - Federal Reserve Economic Data

Methods:
  .series(series_id)            Get data for a series
  .search(text)                 Search for series

Common Series IDs:
  GDP, UNRATE, CPIAUCSL, FEDFUNDS, SP500, MORTGAGE30US

Examples:
  sl = ScenarioList.fred.series("GDP")
  sl = ScenarioList.fred.series("UNRATE", observation_start="2020-01-01")
  sl = ScenarioList.fred.search("inflation")

Requires: FRED_API_KEY (free at fred.stlouisfed.org)"""

    def _ensure_server(self):
        _ensure_service_worker("fred")

    def series(self, series_id: str, verbose: bool = True, **kwargs) -> "ScenarioList":
        from . import dispatch

        pending = dispatch("fred", {"series_id": series_id, **kwargs})
        return pending.result(verbose=verbose)

    def search(
        self, text: str, limit: int = 100, verbose: bool = True, **kwargs
    ) -> "ScenarioList":
        from . import dispatch

        pending = dispatch("fred", {"search_text": text, "limit": limit, **kwargs})
        return pending.result(verbose=verbose)


class WorldBankAccessor:
    """Accessor for World Bank data."""

    def __init__(self):
        self._ensure_server()

    def __repr__(self) -> str:
        return """WorldBankAccessor - Global development indicators

Methods:
  .indicator(code)              Get data for an indicator
  .search(text)                 Search for indicators

Common Indicators:
  gdp, gdp_per_capita, population, life_expectancy, unemployment

Examples:
  sl = ScenarioList.worldbank.indicator("gdp", country="US")
  sl = ScenarioList.worldbank.indicator("NY.GDP.MKTP.CD", date="2010:2023")

No API key required"""

    def _ensure_server(self):
        _ensure_service_worker("worldbank")

    def indicator(
        self, indicator: str, country: str = "all", verbose: bool = True, **kwargs
    ) -> "ScenarioList":
        from . import dispatch

        pending = dispatch(
            "worldbank", {"indicator": indicator, "country": country, **kwargs}
        )
        return pending.result(verbose=verbose)

    def search(self, text: str, verbose: bool = True, **kwargs) -> "ScenarioList":
        from . import dispatch

        pending = dispatch("worldbank", {"search_indicator": text, **kwargs})
        return pending.result(verbose=verbose)


class CensusAccessor:
    """Accessor for US Census data."""

    def __init__(self):
        self._ensure_server()

    def __repr__(self) -> str:
        return """CensusAccessor - US Census Bureau demographic data

Methods:
  .get(variables)               Get census variables

Options:
  geography="state:*"           Geography level
  year=2022                     Data year
  dataset="acs/acs5"            Census dataset

Variable Shortcuts:
  population, median_income, median_age, total_households

Examples:
  sl = ScenarioList.census.get(["population", "median_income"])
  sl = ScenarioList.census.get(["NAME", "B01001_001E"], geography="county:*&in=state:06")

Optional: CENSUS_API_KEY for higher rate limits"""

    def _ensure_server(self):
        _ensure_service_worker("census")

    def get(
        self,
        variables: List[str],
        geography: str = "state:*",
        year: int = 2022,
        verbose: bool = True,
        **kwargs,
    ) -> "ScenarioList":
        from . import dispatch

        pending = dispatch(
            "census",
            {"variables": variables, "geography": geography, "year": year, **kwargs},
        )
        return pending.result(verbose=verbose)


class CrunchbaseAccessor:
    """Accessor for Crunchbase company data."""

    def __init__(self):
        self._ensure_server()

    def __repr__(self) -> str:
        return """CrunchbaseAccessor - Startup and company data

Methods:
  .search(query)                Search for companies/startups

Options:
  limit=25                      Number of results

Examples:
  sl = ScenarioList.crunchbase.search("AI startups")
  sl = ScenarioList.crunchbase.search("fintech", limit=50)

Requires: CRUNCHBASE_API_KEY"""

    def _ensure_server(self):
        _ensure_service_worker("crunchbase")

    def search(
        self, query: str, limit: int = 25, verbose: bool = True, **kwargs
    ) -> "ScenarioList":
        from . import dispatch

        pending = dispatch(
            "crunchbase", {"search_query": query, "limit": limit, **kwargs}
        )
        return pending.result(verbose=verbose)


class DiffbotAccessor:
    """Accessor for Diffbot structured data extraction."""

    def __init__(self):
        self._ensure_server()

    def __repr__(self) -> str:
        return """DiffbotAccessor - Extract structured data from URLs

Methods:
  .extract(url)                 Extract data from URL
  .article(url)                 Extract article content
  .product(url)                 Extract product data

Examples:
  sl = ScenarioList.diffbot.extract("https://example.com/article")
  sl = ScenarioList.diffbot.article("https://nytimes.com/...")

Requires: DIFFBOT_TOKEN"""

    def _ensure_server(self):
        _ensure_service_worker("diffbot")

    def extract(self, url: str, verbose: bool = True, **kwargs) -> "ScenarioList":
        from . import dispatch

        pending = dispatch("diffbot", {"url": url, "api": "analyze", **kwargs})
        return pending.result(verbose=verbose)

    def article(self, url: str, verbose: bool = True, **kwargs) -> "ScenarioList":
        from . import dispatch

        pending = dispatch("diffbot", {"url": url, "api": "article", **kwargs})
        return pending.result(verbose=verbose)

    def product(self, url: str, verbose: bool = True, **kwargs) -> "ScenarioList":
        from . import dispatch

        pending = dispatch("diffbot", {"url": url, "api": "product", **kwargs})
        return pending.result(verbose=verbose)


class ReplicateAccessor:
    """Accessor for Replicate ML models."""

    def __init__(self):
        self._ensure_server()

    def __repr__(self) -> str:
        return """ReplicateAccessor - Run ML models (image generation, etc.)

Methods:
  .run(model, input)            Run any model
  .generate_image(prompt)       Generate image with FLUX

Model Shortcuts:
  sdxl, flux, flux-pro, llama, whisper

Examples:
  sl = ScenarioList.replicate.generate_image("A cat in space")
  sl = ScenarioList.replicate.run("flux", {"prompt": "..."})

Requires: REPLICATE_API_TOKEN
Requires: pip install replicate"""

    def _ensure_server(self):
        _ensure_service_worker("replicate")

    def run(
        self, model: str, input: Dict[str, Any], verbose: bool = True, **kwargs
    ) -> "ScenarioList":
        check_dependencies("replicate")
        from . import dispatch

        pending = dispatch("replicate", {"model": model, "input": input, **kwargs})
        return pending.result(verbose=verbose)

    def generate_image(
        self, prompt: str, model: str = "flux", verbose: bool = True, **kwargs
    ) -> "ScenarioList":
        check_dependencies("replicate")
        from . import dispatch

        pending = dispatch(
            "replicate", {"model": model, "input": {"prompt": prompt}, **kwargs}
        )
        return pending.result(verbose=verbose)


class FalAccessor:
    """Accessor for fal.ai image generation."""

    def __init__(self):
        self._ensure_server()

    def __repr__(self) -> str:
        return """FalAccessor - Fast image generation

Methods:
  .generate(prompt)             Generate image with FLUX

Options:
  model="flux-schnell"          Model: flux-schnell, flux-dev, sdxl
  image_size="landscape_4_3"    Size preset
  num_images=1                  Number of images

Examples:
  sl = ScenarioList.fal.generate("A beautiful sunset")
  sl = ScenarioList.fal.generate("Abstract art", model="sdxl", num_images=4)

Requires: FAL_KEY
Requires: pip install fal-client"""

    def _ensure_server(self):
        _ensure_service_worker("fal")

    def generate(
        self, prompt: str, model: str = "flux-schnell", verbose: bool = True, **kwargs
    ) -> "ScenarioList":
        check_dependencies("fal")
        from . import dispatch

        pending = dispatch("fal", {"prompt": prompt, "model": model, **kwargs})
        return pending.result(verbose=verbose)


class DalleAccessor:
    """Accessor for OpenAI DALL-E image generation."""

    def __init__(self):
        self._ensure_server()

    def __repr__(self) -> str:
        return """DalleAccessor - OpenAI DALL-E image generation

Methods:
  .generate(prompt)             Generate image with DALL-E

Options:
  model="dall-e-3"              Model: dall-e-3, dall-e-2
  size="1024x1024"              Image size
  quality="standard"            Quality: standard, hd
  style="vivid"                 Style: vivid, natural

Examples:
  sl = ScenarioList.dalle.generate("A white siamese cat")
  sl = ScenarioList.dalle.generate("Oil painting", quality="hd", style="natural")

Requires: OPENAI_API_KEY"""

    def _ensure_server(self):
        _ensure_service_worker("openai_images")

    def generate(
        self, prompt: str, model: str = "dall-e-3", verbose: bool = True, **kwargs
    ) -> "ScenarioList":
        check_dependencies("openai_images")
        from . import dispatch

        pending = dispatch(
            "openai_images", {"prompt": prompt, "model": model, **kwargs}
        )
        return pending.result(verbose=verbose)


class GoogleSheetsAccessor:
    """
    Accessor for Google Sheets operations on ScenarioList.

    Uses OAuth2 browser-based authentication. First use will open a browser
    for Google login. Credentials are cached locally for future use.

    Usage:
        >>> sl = ScenarioList.google_sheets.read("https://docs.google.com/spreadsheets/d/...")
        >>> sl = ScenarioList.google_sheets.read(spreadsheet_id, sheet_name="Sheet2")
    """

    def __init__(self):
        self._ensure_server()

    def __repr__(self) -> str:
        return """GoogleSheetsAccessor - Read data from Google Sheets

Methods:
  .read(url)                    Read data from a Google Sheet
  .logout()                     Clear saved credentials

Options:
  sheet_name="Sheet1"           Name of sheet to read
  range="A1:Z1000"              Cell range to read
  header_row=0                  Row to use as column headers

Examples:
  # Read from Google Sheets URL
  sl = ScenarioList.google_sheets.read(
      "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit"
  )
  
  # Read specific sheet and range
  sl = ScenarioList.google_sheets.read(
      "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
      sheet_name="Data",
      range="A1:D100"
  )
  
  # Switch Google accounts
  ScenarioList.google_sheets.logout()

Authentication:
  First use will open a browser for Google login.
  Credentials are saved to ~/.config/gspread/
  
Requires: pip install gspread"""

    def _repr_html_(self) -> str:
        return """
<div style="font-family: monospace; padding: 10px; border: 1px solid #ddd; border-radius: 8px; background: #f9f9f9;">
<b style="color: #4285F4;">GoogleSheetsAccessor</b> - Read data from Google Sheets<br><br>
<b>Methods:</b><br>
<code>.read(url)</code> - Read data from a Google Sheet<br>
<code>.logout()</code> - Clear saved credentials<br><br>
<b>Options:</b><br>
<code>sheet_name="Sheet1"</code> - Name of sheet to read<br>
<code>range="A1:Z1000"</code> - Cell range to read<br><br>
<b>Examples:</b><br>
<code>sl = ScenarioList.google_sheets.read("https://docs.google.com/spreadsheets/d/...")</code><br><br>
<i style="color: #888;">First use opens browser for Google login. No API key setup needed!</i>
</div>
"""

    def _ensure_server(self):
        """Ensure a server and worker are running."""
        _ensure_service_worker("google_sheets")

    def read(
        self,
        url: str,
        sheet_name: Optional[str] = None,
        range: Optional[str] = None,
        header_row: int = 0,
        verbose: bool = True,
        **kwargs,
    ) -> "ScenarioList":
        """
        Read data from a Google Sheet.

        Args:
            url: Google Sheets URL or spreadsheet ID
            sheet_name: Name of the sheet to read (default: first sheet)
            range: Cell range to read (e.g., "A1:Z1000")
            header_row: Row number to use as headers (0-indexed)
            verbose: Show progress updates
            **kwargs: Additional options

        Returns:
            ScenarioList with sheet data (one Scenario per row)

        Example:
            >>> sl = ScenarioList.google_sheets.read(
            ...     "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit"
            ... )
        """
        from . import dispatch

        params = {
            "url": url,
            "sheet_name": sheet_name,
            "range": range,
            "header_row": header_row,
            **kwargs,
        }

        pending = dispatch("google_sheets", params)
        return pending.result(verbose=verbose)

    def logout(self):
        """
        Clear saved Google credentials.

        Use this to switch Google accounts or revoke access.
        """
        from .builtin.google_sheets import GoogleSheetsService

        GoogleSheetsService.logout()


class PerplexityAccessor:
    """
    Accessor for Perplexity AI search on ScenarioList.

    Perplexity provides AI-powered search with citations - answers
    grounded in real sources from the web.

    Usage:
        >>> sl = ScenarioList.perplexity.search("What are the latest AI breakthroughs?")
    """

    def __init__(self):
        self._ensure_server()

    def __repr__(self) -> str:
        return """PerplexityAccessor - AI-powered search with citations

Methods:
  .search(query)                Search and get AI-synthesized answer with sources

Options:
  model="sonar"                 Model: sonar (default), sonar-pro, sonar-reasoning
  search_recency_filter="week"  Filter: "day", "week", "month", "year"
  system_prompt="..."           Custom instructions for the AI

Examples:
  # Basic search
  sl = ScenarioList.perplexity.search("What is quantum computing?")
  
  # Recent news only
  sl = ScenarioList.perplexity.search(
      "Latest AI regulations",
      search_recency_filter="week"
  )
  
  # Custom instructions
  sl = ScenarioList.perplexity.search(
      "Climate change solutions",
      system_prompt="Focus on peer-reviewed research. Be concise."
  )

Returns ScenarioList with:
  - answer: The AI-generated response
  - citations: List of source URLs
  - citation_count: Number of sources used

Requires: PERPLEXITY_API_KEY (get at perplexity.ai/settings/api)"""

    def _repr_html_(self) -> str:
        return """
<div style="font-family: monospace; padding: 10px; border: 1px solid #ddd; border-radius: 8px; background: #f9f9f9;">
<b style="color: #7C3AED;">PerplexityAccessor</b> - AI-powered search with citations<br><br>
<b>Methods:</b><br>
<code>.search(query)</code> - Search and get AI answer with sources<br><br>
<b>Options:</b><br>
<code>model="sonar"</code> - sonar (default), sonar-pro (better), sonar-reasoning<br>
<code>search_recency_filter="week"</code> - day, week, month, year<br><br>
<b>Examples:</b><br>
<code>sl = ScenarioList.perplexity.search("Latest AI breakthroughs")</code><br>
<code>sl = ScenarioList.perplexity.search("News today", search_recency_filter="day")</code><br><br>
<i style="color: #888;">Requires: PERPLEXITY_API_KEY</i>
</div>
"""

    def _ensure_server(self):
        """Ensure a server and worker are running."""
        _ensure_service_worker("perplexity")

    def search(
        self,
        query: str,
        model: str = "sonar",
        system_prompt: Optional[str] = None,
        search_recency_filter: Optional[str] = None,
        verbose: bool = True,
        **kwargs,
    ) -> "ScenarioList":
        """
        Search using Perplexity AI.

        Args:
            query: The question or search query
            model: Model to use (sonar, sonar-pro, sonar-reasoning)
            system_prompt: Optional instructions for the AI
            search_recency_filter: Filter by time: "day", "week", "month", "year"
            verbose: Show progress updates
            **kwargs: Additional options

        Returns:
            ScenarioList with answer and citations
        """
        from . import dispatch

        params = {
            "query": query,
            "model": model,
            "system_prompt": system_prompt,
            "search_recency_filter": search_recency_filter,
            **kwargs,
        }

        pending = dispatch("perplexity", params)
        return pending.result(verbose=verbose)


# Singleton instances for class-level access
_firecrawl_accessor = None
_exa_accessor = None
_huggingface_accessor = None
_wikipedia_accessor = None
_reducto_accessor = None
_arxiv_accessor = None
_semantic_scholar_accessor = None
_openalex_accessor = None
_youtube_accessor = None
_reddit_accessor = None
_fred_accessor = None
_worldbank_accessor = None
_census_accessor = None
_crunchbase_accessor = None
_diffbot_accessor = None
_replicate_accessor = None
_fal_accessor = None
_dalle_accessor = None
_google_sheets_accessor = None
_perplexity_accessor = None


def get_firecrawl_accessor() -> FirecrawlAccessor:
    global _firecrawl_accessor
    if _firecrawl_accessor is None:
        _firecrawl_accessor = FirecrawlAccessor()
    return _firecrawl_accessor


def get_exa_accessor() -> ExaAccessor:
    global _exa_accessor
    if _exa_accessor is None:
        _exa_accessor = ExaAccessor()
    return _exa_accessor


def get_huggingface_accessor() -> HuggingFaceAccessor:
    global _huggingface_accessor
    if _huggingface_accessor is None:
        _huggingface_accessor = HuggingFaceAccessor()
    return _huggingface_accessor


def get_wikipedia_accessor() -> WikipediaAccessor:
    global _wikipedia_accessor
    if _wikipedia_accessor is None:
        _wikipedia_accessor = WikipediaAccessor()
    return _wikipedia_accessor


def get_reducto_accessor() -> ReductoAccessor:
    global _reducto_accessor
    if _reducto_accessor is None:
        _reducto_accessor = ReductoAccessor()
    return _reducto_accessor


def get_arxiv_accessor() -> ArxivAccessor:
    global _arxiv_accessor
    if _arxiv_accessor is None:
        _arxiv_accessor = ArxivAccessor()
    return _arxiv_accessor


def get_semantic_scholar_accessor() -> SemanticScholarAccessor:
    global _semantic_scholar_accessor
    if _semantic_scholar_accessor is None:
        _semantic_scholar_accessor = SemanticScholarAccessor()
    return _semantic_scholar_accessor


def get_openalex_accessor() -> OpenAlexAccessor:
    global _openalex_accessor
    if _openalex_accessor is None:
        _openalex_accessor = OpenAlexAccessor()
    return _openalex_accessor


def get_youtube_accessor() -> YouTubeAccessor:
    global _youtube_accessor
    if _youtube_accessor is None:
        _youtube_accessor = YouTubeAccessor()
    return _youtube_accessor


def get_reddit_accessor() -> RedditAccessor:
    global _reddit_accessor
    if _reddit_accessor is None:
        _reddit_accessor = RedditAccessor()
    return _reddit_accessor


def get_fred_accessor() -> FREDAccessor:
    global _fred_accessor
    if _fred_accessor is None:
        _fred_accessor = FREDAccessor()
    return _fred_accessor


def get_worldbank_accessor() -> WorldBankAccessor:
    global _worldbank_accessor
    if _worldbank_accessor is None:
        _worldbank_accessor = WorldBankAccessor()
    return _worldbank_accessor


def get_census_accessor() -> CensusAccessor:
    global _census_accessor
    if _census_accessor is None:
        _census_accessor = CensusAccessor()
    return _census_accessor


def get_crunchbase_accessor() -> CrunchbaseAccessor:
    global _crunchbase_accessor
    if _crunchbase_accessor is None:
        _crunchbase_accessor = CrunchbaseAccessor()
    return _crunchbase_accessor


def get_diffbot_accessor() -> DiffbotAccessor:
    global _diffbot_accessor
    if _diffbot_accessor is None:
        _diffbot_accessor = DiffbotAccessor()
    return _diffbot_accessor


def get_replicate_accessor() -> ReplicateAccessor:
    global _replicate_accessor
    if _replicate_accessor is None:
        _replicate_accessor = ReplicateAccessor()
    return _replicate_accessor


def get_fal_accessor() -> FalAccessor:
    global _fal_accessor
    if _fal_accessor is None:
        _fal_accessor = FalAccessor()
    return _fal_accessor


def get_dalle_accessor() -> DalleAccessor:
    global _dalle_accessor
    if _dalle_accessor is None:
        _dalle_accessor = DalleAccessor()
    return _dalle_accessor


def get_google_sheets_accessor() -> GoogleSheetsAccessor:
    global _google_sheets_accessor
    if _google_sheets_accessor is None:
        _google_sheets_accessor = GoogleSheetsAccessor()
    return _google_sheets_accessor


def get_perplexity_accessor() -> PerplexityAccessor:
    global _perplexity_accessor
    if _perplexity_accessor is None:
        _perplexity_accessor = PerplexityAccessor()
    return _perplexity_accessor


# =============================================================================
# Survey Import Accessor
# =============================================================================


class SurveyImportAccessor:
    """
    Accessor for importing survey data from Qualtrics and SurveyMonkey.

    This accessor is attached to the Results class and provides methods
    for importing survey exports via the worker framework.

    Usage:
        >>> results = Results.import_.qualtrics("qualtrics_export.csv")
        >>> results = Results.import_.survey_monkey("survey_export.xlsx")
    """

    def __repr__(self) -> str:
        return """SurveyImportAccessor - Import survey data via worker framework

Methods:
  .qualtrics(filepath)       Import from Qualtrics CSV/tab export
  .survey_monkey(filepath)   Import from SurveyMonkey CSV/Excel export

Examples:
  Results.importer.qualtrics("qualtrics_export.csv")
  Results.importer.survey_monkey("survey_results.xlsx")
  Results.importer.qualtrics("export.tab", create_semantic_names=True)

Options:
  verbose=True              Show progress during import
  create_semantic_names=True  Use meaningful question names
  vibe_config=True          Enable AI-powered question enhancement (Qualtrics)
  repair_excel_dates=True   Fix Excel date mangling (SurveyMonkey)
  order_options_semantically=True  Reorder options logically (SurveyMonkey)

Requires: pandas (for Excel support)"""

    def _repr_html_(self) -> str:
        return """
<div style="font-family: monospace; padding: 10px; border: 1px solid #ddd; border-radius: 8px; background: #f9f9f9;">
<b style="color: #10B981;">SurveyImportAccessor</b> - Import survey data via worker framework<br><br>
<b>Methods:</b><br>
<code>.qualtrics(filepath)</code> - Import from Qualtrics CSV/tab<br>
<code>.survey_monkey(filepath)</code> - Import from SurveyMonkey CSV/Excel<br><br>
<b>Examples:</b><br>
<code>Results.importer.qualtrics("export.csv")</code><br>
<code>Results.importer.survey_monkey("results.xlsx")</code><br><br>
<i style="color: #888;">Requires: pandas (for Excel)</i>
</div>
"""

    def _ensure_server(self):
        """Ensure a server and worker are running for survey import operations."""
        _ensure_service_worker("survey_import")

    def qualtrics(
        self,
        filepath: str,
        *,
        verbose: bool = False,
        create_semantic_names: bool = False,
        vibe_config: bool = True,
        disable_remote_inference: bool = True,
    ) -> "Results":
        """Import from a Qualtrics CSV or tab-delimited export.

        This method imports a Qualtrics export (CSV or tab with 3-row headers)
        and generates a Results object by running agents through the reconstructed survey.

        Args:
            filepath: Path to the Qualtrics export file (CSV, .tab, or .tsv)
            verbose: Print progress information during parsing
            create_semantic_names: Use semantic names derived from question text
                instead of Q1, Q2, etc.
            vibe_config: Enable AI-powered question cleanup and enhancement.
                Set to False to disable.
            disable_remote_inference: Run locally without remote API calls (default True)

        Returns:
            Results: A Results object containing the imported survey responses

        Examples:
            >>> results = Results.import_.qualtrics("qualtrics_export.csv")
            >>> results = Results.import_.qualtrics(
            ...     "export.tab",
            ...     verbose=True,
            ...     create_semantic_names=True
            ... )
        """
        import base64
        import os

        from . import dispatch

        self._ensure_server()

        # Read file and encode as base64
        with open(filepath, "rb") as f:
            file_content = base64.b64encode(f.read()).decode("utf-8")

        filename = os.path.basename(filepath)

        pending = dispatch(
            "survey_import",
            {
                "operation": "qualtrics",
                "file_content": file_content,
                "filename": filename,
                "verbose": verbose,
                "create_semantic_names": create_semantic_names,
                "vibe_config": vibe_config,
                "disable_remote_inference": disable_remote_inference,
            },
        )

        return pending.result(verbose=verbose)

    def survey_monkey(
        self,
        filepath: str,
        *,
        verbose: bool = False,
        create_semantic_names: bool = False,
        repair_excel_dates: bool = True,
        order_options_semantically: bool = True,
        disable_remote_inference: bool = True,
    ) -> "Results":
        """Import from a SurveyMonkey CSV or Excel export.

        This method imports a SurveyMonkey export (CSV or Excel) and generates
        a Results object by running agents through the reconstructed survey.

        Args:
            filepath: Path to the SurveyMonkey export file (.csv, .xlsx, .xls)
            verbose: Print progress information during parsing
            create_semantic_names: Use semantic names derived from question text
            repair_excel_dates: Use LLM to detect and repair Excel-mangled
                date formatting (e.g., "5-Mar" → "3-5"). Default True.
            order_options_semantically: Use LLM to reorder multiple choice
                options in semantically correct order. Default True.
            disable_remote_inference: Run locally without remote API calls (default True)

        Returns:
            Results: A Results object containing the imported survey responses

        Examples:
            >>> results = Results.import_.survey_monkey("survey_results.csv")
            >>> results = Results.import_.survey_monkey(
            ...     "results.xlsx",
            ...     verbose=True,
            ...     create_semantic_names=True
            ... )
        """
        import base64
        import os

        from . import dispatch

        self._ensure_server()

        # Read file and encode as base64
        with open(filepath, "rb") as f:
            file_content = base64.b64encode(f.read()).decode("utf-8")

        filename = os.path.basename(filepath)

        pending = dispatch(
            "survey_import",
            {
                "operation": "survey_monkey",
                "file_content": file_content,
                "filename": filename,
                "verbose": verbose,
                "create_semantic_names": create_semantic_names,
                "repair_excel_dates": repair_excel_dates,
                "order_options_semantically": order_options_semantically,
                "disable_remote_inference": disable_remote_inference,
            },
        )

        return pending.result(verbose=verbose)


class EmbeddingsAccessor:
    """
    Accessor for embedding operations on ScenarioList.

    Provides methods to generate embeddings, perform semantic search,
    and cluster scenarios by similarity.

    Usage:
        # Generate embeddings for a column
        sl_with_embeddings = sl.embeddings.generate("text_column")

        # Generate a single embedding
        embedding = ScenarioList.embeddings.embed("Hello world")

        # Search for similar items
        results = sl.embeddings.search("query text", column="text_column", top_k=5)

    Requires: OPENAI_API_KEY environment variable
    """

    def __init__(self, scenario_list: Optional["ScenarioList"] = None):
        """
        Initialize the embeddings accessor.

        Args:
            scenario_list: Optional ScenarioList to operate on
        """
        self._scenario_list = scenario_list

    def _ensure_server(self) -> None:
        """Ensure the service worker is running."""
        _ensure_service_worker("embeddings")

    def __repr__(self) -> str:
        return """EmbeddingsAccessor - Generate and work with text embeddings

Methods:
    .embed(text, model="text-embedding-3-small")
        Generate embedding for a single text
        
    .generate(column, model="text-embedding-3-small")
        Generate embeddings for all texts in a column
        Adds "embedding" column with EmbeddingStore objects
        
    .search(query, column, top_k=5, model="text-embedding-3-small")
        Find most similar items using semantic search

Models:
    text-embedding-3-small (1536 dimensions, fast, cheap)
    text-embedding-3-large (3072 dimensions, more accurate)
    text-embedding-ada-002 (1536 dimensions, legacy)

Examples:
    # Generate embeddings for a column
    sl_with_embeddings = sl.embeddings.generate("description")
    
    # Generate single embedding
    emb = ScenarioList.embeddings.embed("Hello world")
    
    # Semantic search
    results = sl.embeddings.search("python programming", column="text")
    
Requires: OPENAI_API_KEY
"""

    def _repr_html_(self) -> str:
        return """
        <div style="font-family: monospace; padding: 15px; border: 1px solid #ddd; border-radius: 8px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">
            <div style="font-size: 16px; font-weight: bold; margin-bottom: 10px;">📊 EmbeddingsAccessor</div>
            <div style="font-size: 12px; margin-bottom: 15px;">Generate and work with text embeddings</div>
            
            <div style="background: rgba(255,255,255,0.1); padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                <div style="font-weight: bold; margin-bottom: 5px;">Methods:</div>
                <div><code>.embed(text)</code> - Single text → EmbeddingStore</div>
                <div><code>.generate(column)</code> - Column → ScenarioList with embeddings</div>
                <div><code>.search(query, column)</code> - Semantic search</div>
            </div>
            
            <div style="background: rgba(255,255,255,0.1); padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                <div style="font-weight: bold; margin-bottom: 5px;">Models:</div>
                <div>• text-embedding-3-small (1536d, fast)</div>
                <div>• text-embedding-3-large (3072d, accurate)</div>
            </div>
            
            <div style="font-size: 11px; opacity: 0.8;">
                Requires: OPENAI_API_KEY
            </div>
        </div>
        """

    def embed(
        self,
        text: str,
        *,
        model: str = "text-embedding-3-small",
        dimensions: Optional[int] = None,
        verbose: bool = True,
    ) -> "EmbeddingStore":
        """
        Generate an embedding for a single text.

        Args:
            text: The text to embed
            model: The embedding model to use
            dimensions: Optional reduced dimensions (for v3 models only)
            verbose: Show progress spinner

        Returns:
            EmbeddingStore object with the embedding and similarity methods

        Examples:
            >>> emb = ScenarioList.embeddings.embed("Hello world")
            >>> emb.dimensions
            1536
            >>> emb.cosine_similarity(other_emb)
            0.85
        """
        check_dependencies("embeddings")
        self._ensure_server()

        from . import dispatch

        pending = dispatch(
            "embeddings",
            {
                "operation": "embed",
                "texts": [text],
                "model": model,
                "dimensions": dimensions,
            },
        )

        return pending.result(verbose=verbose)

    def generate(
        self,
        column: str,
        *,
        model: str = "text-embedding-3-small",
        dimensions: Optional[int] = None,
        output_column: str = "embedding",
        verbose: bool = True,
    ) -> "ScenarioList":
        """
        Generate embeddings for all texts in a column.

        Args:
            column: Name of the column containing texts to embed
            model: The embedding model to use
            dimensions: Optional reduced dimensions (for v3 models only)
            output_column: Name for the new column with embeddings
            verbose: Show progress spinner

        Returns:
            New ScenarioList with an additional column containing EmbeddingStore objects

        Examples:
            >>> sl = ScenarioList([
            ...     Scenario({"text": "Python is great"}),
            ...     Scenario({"text": "JavaScript is popular"}),
            ... ])
            >>> sl_with_emb = sl.embeddings.generate("text")
            >>> sl_with_emb[0]["embedding"].dimensions
            1536
        """
        if self._scenario_list is None:
            raise ValueError("No ScenarioList attached. Use sl.embeddings.generate()")

        check_dependencies("embeddings")
        self._ensure_server()

        from . import dispatch
        from edsl.scenarios import ScenarioList, Scenario

        # Extract texts from the column
        texts = [s.get(column, "") for s in self._scenario_list]

        if not texts:
            return self._scenario_list

        # Generate embeddings
        pending = dispatch(
            "embeddings",
            {
                "operation": "batch",
                "texts": texts,
                "model": model,
                "dimensions": dimensions,
            },
        )

        result = pending.result(verbose=verbose)

        # Get the embedding list
        from edsl.scenarios.embedding_store import EmbeddingList

        if isinstance(result, EmbeddingList):
            embeddings = result.embeddings
        else:
            embeddings = [result]

        # Create new ScenarioList with embeddings added
        new_scenarios = []
        for scenario, embedding in zip(self._scenario_list, embeddings):
            new_data = dict(scenario)
            new_data[output_column] = embedding
            new_scenarios.append(Scenario(new_data))

        return ScenarioList(new_scenarios)

    def search(
        self,
        query: str,
        column: str,
        *,
        top_k: int = 5,
        model: str = "text-embedding-3-small",
        verbose: bool = True,
    ) -> "ScenarioList":
        """
        Find the most similar items using semantic search.

        Args:
            query: The search query
            column: Name of the column to search through
            top_k: Number of results to return
            model: The embedding model to use
            verbose: Show progress spinner

        Returns:
            ScenarioList of the top_k most similar items, with added
            "similarity_score" column

        Examples:
            >>> results = sl.embeddings.search(
            ...     "machine learning frameworks",
            ...     column="description",
            ...     top_k=3
            ... )
            >>> results[0]["similarity_score"]
            0.92
        """
        if self._scenario_list is None:
            raise ValueError("No ScenarioList attached. Use sl.embeddings.search()")

        check_dependencies("embeddings_search")
        _ensure_service_worker("embeddings_search")

        from . import dispatch
        from edsl.scenarios import ScenarioList, Scenario

        # Extract texts from the column
        texts = [s.get(column, "") for s in self._scenario_list]

        if not texts:
            return ScenarioList([])

        # Perform search
        pending = dispatch(
            "embeddings_search",
            {
                "query": query,
                "texts": texts,
                "top_k": top_k,
                "model": model,
            },
        )

        results = pending.result(verbose=verbose)

        # Build result ScenarioList with similarity scores
        result_scenarios = []
        for sim_result in results:
            original_idx = sim_result.embedding.get("metadata", {}).get(
                "original_index", 0
            )
            original_scenario = self._scenario_list[original_idx]

            # Add similarity score to scenario
            new_data = dict(original_scenario)
            new_data["similarity_score"] = sim_result.score
            new_data["embedding"] = sim_result.embedding
            result_scenarios.append(Scenario(new_data))

        return ScenarioList(result_scenarios)

    def cluster(
        self,
        column: str,
        *,
        n_clusters: int = 3,
        model: str = "text-embedding-3-small",
        verbose: bool = True,
    ) -> "ScenarioList":
        """
        Cluster scenarios by embedding similarity.

        First generates embeddings for the column, then uses k-means
        to cluster them.

        Args:
            column: Name of the column to embed and cluster
            n_clusters: Number of clusters
            model: The embedding model to use
            verbose: Show progress spinner

        Returns:
            ScenarioList with added "cluster" column

        Examples:
            >>> clustered = sl.embeddings.cluster("description", n_clusters=5)
            >>> clustered.filter("cluster == 0")
            ScenarioList(...)
        """
        if self._scenario_list is None:
            raise ValueError("No ScenarioList attached")

        # First generate embeddings
        sl_with_embeddings = self.generate(column, model=model, verbose=verbose)

        # Extract embeddings for clustering
        from edsl.scenarios.embedding_store import EmbeddingList

        embeddings = [s["embedding"] for s in sl_with_embeddings]
        embedding_list = EmbeddingList(embeddings)

        # Cluster
        clusters = embedding_list.cluster(n_clusters=n_clusters)

        # Add cluster labels back to scenarios
        from edsl.scenarios import ScenarioList, Scenario

        # Create index -> cluster mapping
        idx_to_cluster = {}
        for cluster_id, cluster_embeddings in clusters.items():
            for emb in cluster_embeddings:
                idx = emb.get("metadata", {}).get("index", 0)
                idx_to_cluster[idx] = cluster_id

        # Build result
        new_scenarios = []
        for i, scenario in enumerate(sl_with_embeddings):
            new_data = dict(scenario)
            new_data["cluster"] = idx_to_cluster.get(i, 0)
            new_scenarios.append(Scenario(new_data))

        return ScenarioList(new_scenarios)


# Singleton for Results import accessor
_survey_import_accessor: Optional[SurveyImportAccessor] = None


def get_survey_import_accessor() -> SurveyImportAccessor:
    global _survey_import_accessor
    if _survey_import_accessor is None:
        _survey_import_accessor = SurveyImportAccessor()
    return _survey_import_accessor


# Singleton for class-level embeddings accessor
_embeddings_accessor: Optional[EmbeddingsAccessor] = None


def get_embeddings_accessor() -> EmbeddingsAccessor:
    """Get the singleton embeddings accessor for class-level access."""
    global _embeddings_accessor
    if _embeddings_accessor is None:
        _embeddings_accessor = EmbeddingsAccessor()
    return _embeddings_accessor


# =============================================================================
# Remote Service Accessor (for services only available on remote server)
# =============================================================================


class RemoteServiceAccessor:
    """
    Accessor for services that exist only on the remote server.

    This accessor is used when a service is not registered locally but
    is available via RemoteMetadataCache. It provides a similar interface
    to ServiceAccessor but works without a local service class.
    """

    def __init__(
        self,
        service_name: str,
        remote_info: "RemoteServiceInfo",
        instance: Any = None,
    ):
        self._service_name = service_name
        self._remote_info = remote_info
        self._instance = instance

    def __repr__(self) -> str:
        info = self._remote_info
        lines = [
            f"{self._service_name.title()}Accessor (remote) - {info.description}",
            "",
        ]
        if info.operations:
            lines.append(
                "Methods: " + ", ".join(f".{m}()" for m in info.operations.keys())
            )
        if info.required_keys:
            lines.append("Required keys: " + ", ".join(info.required_keys))
        return "\n".join(lines)

    def _repr_html_(self) -> str:
        info = self._remote_info
        methods_html = (
            ", ".join(f"<code>.{m}()</code>" for m in info.operations.keys())
            if info.operations
            else "Any method name is forwarded to the service"
        )
        keys_html = (
            "<br>".join(f"• {k}" for k in info.required_keys)
            if info.required_keys
            else "None"
        )
        return f"""
<div style="font-family: monospace; padding: 10px; border: 1px solid #ddd; border-radius: 8px; background: #f9f9f9;">
<b style="color: #3498db;">{self._service_name.title()}Accessor</b> (remote)<br>
{info.description}<br><br>
<b>Methods:</b> {methods_html}<br><br>
<b>Required Keys:</b><br>{keys_html}
</div>
"""

    def __getattr__(self, method_name: str):
        """Dynamically handle method calls by dispatching to the remote service."""
        if method_name.startswith("_"):
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{method_name}'"
            )

        def method_wrapper(*args, verbose: bool = True, **kwargs):
            """Dispatch the method call to the remote service."""
            from . import dispatch

            # Ensure worker is available
            _ensure_service_worker(self._service_name)

            # Build params
            timeout = kwargs.pop("timeout", None)
            poll_interval = kwargs.pop("poll_interval", None)

            params = {"operation": method_name}
            params.update(kwargs)

            # Get operation schema if available
            op_schema = self._remote_info.operations.get(method_name, {})
            input_param = op_schema.get("input_param")
            defaults = op_schema.get("defaults", {})

            # Apply defaults first (kwargs will override)
            if defaults:
                for key, value in defaults.items():
                    if key not in params:
                        params[key] = value

            # Handle positional args using input_param from schema
            if args:
                first_arg = args[0]
                if input_param:
                    # Use the schema-defined parameter name
                    params[input_param] = first_arg
                else:
                    # Fallback for services without schema
                    if method_name in ("scrape", "crawl", "extract", "parse"):
                        params["url"] = first_arg
                    elif method_name in ("search", "query"):
                        params["query"] = first_arg
                    elif method_name in ("load", "get"):
                        params["name"] = first_arg
                    elif method_name in ("generate", "from_vibes", "create"):
                        params["description"] = first_arg
                    else:
                        params["input"] = first_arg

                if len(args) > 1:
                    params["args"] = args[1:]

            # Include instance data if available
            if self._instance is not None:
                if hasattr(self._instance, "to_dict"):
                    params["data"] = self._instance.to_dict()
                    params["data_type"] = type(self._instance).__name__.lower()

            # Dispatch and wait for result
            pending = dispatch(self._service_name, params)

            result_kwargs = {"verbose": verbose}
            if timeout is not None:
                result_kwargs["timeout"] = timeout
            if poll_interval is not None:
                result_kwargs["poll_interval"] = poll_interval

            raw_result = pending.result(**result_kwargs)

            # If result is already parsed (not a dict), return it directly
            if not isinstance(raw_result, dict):
                return raw_result

            # Parse the result using the pattern from remote metadata
            from .result_parsers import ResultParser

            # Extract the inner result if wrapped
            if "result" in raw_result:
                result_to_parse = raw_result["result"]
            else:
                result_to_parse = raw_result

            # If inner result is also not a dict, return it directly
            if not isinstance(result_to_parse, dict):
                return result_to_parse

            return ResultParser.parse(
                result_to_parse,
                self._remote_info.result_pattern,
                self._remote_info.result_field,
            )

        return method_wrapper

    def __dir__(self):
        """Support tab completion for service methods."""
        base = ["_service_name", "_instance", "_remote_info"]
        if self._remote_info.operations:
            return base + list(self._remote_info.operations.keys())
        return base + ["generate", "search", "scrape", "load", "get"]


# =============================================================================
# Unified Service Discovery
# =============================================================================


def get_service_accessor(name: str, instance: Any = None, owner_class: type = None):
    """
    Get a service accessor by name using automatic discovery from ServiceRegistry.

    This function automatically discovers services registered in ServiceRegistry
    and returns a generic ServiceAccessor that works with any registered service.

    Args:
        name: The service name (e.g., 'firecrawl', 'wikipedia', 'exa', 'answer_analysis')
        instance: Optional EDSL object instance for instance-level access
        owner_class: Optional class type for class-level access

    Returns:
        ServiceAccessor instance, or None if service not found

    Examples:
        >>> accessor = get_service_accessor('firecrawl')
        >>> accessor  # Shows helpful repr with available methods

        >>> accessor = get_service_accessor('exa')
        >>> accessor.search("AI research")  # Dispatches to ExaService

        >>> accessor = get_service_accessor('answer_analysis', results_instance)
        >>> accessor.summary(question='how_feeling')  # Dispatches to AnswerAnalysisService
    """
    # Quick check: Skip common Python methods/attributes to avoid loading all services
    # These are never service names
    _SKIP_NAMES = frozenset(
        {
            # Python internals
            "__class__",
            "__dict__",
            "__doc__",
            "__module__",
            "__weakref__",
            "__init__",
            "__new__",
            "__del__",
            "__repr__",
            "__str__",
            "__hash__",
            "__eq__",
            "__ne__",
            "__lt__",
            "__le__",
            "__gt__",
            "__ge__",
            "__getattr__",
            "__setattr__",
            "__delattr__",
            "__getattribute__",
            "__iter__",
            "__next__",
            "__len__",
            "__getitem__",
            "__setitem__",
            "__delitem__",
            "__contains__",
            "__call__",
            "__enter__",
            "__exit__",
            "__add__",
            "__sub__",
            "__mul__",
            "__div__",
            "__truediv__",
            "__bool__",
            "__int__",
            "__float__",
            "__index__",
            "__neg__",
            "_repr_html_",
            "_ipython_display_",
            "_ipython_canary_method_should_not_exist_",
            # Common EDSL method names that aren't services
            "select",
            "filter",
            "sort",
            "table",
            "to_dict",
            "to_list",
            "to_pandas",
            "to_scenario_list",
            "to_dataset",
            "example",
            "from_dict",
            "from_list",
            "append",
            "extend",
            "insert",
            "remove",
            "pop",
            "clear",
            "copy",
            "keys",
            "values",
            "items",
            "get",
            "set",
            "update",
            "save",
            "load",
            "push",
            "pull",
            "rich_print",
            "print",
            "show",
            "data",
            "store",
            "codebook",
            "metadata",
            "name",
            "description",
            "report_from_template",
            "long_view",
            "augment_agents",
            "agents",
            "expand",
            "to_markdown",
            "flip",
            "to_string",
            "view",
            "to_docx",
            "to_survey",
            "rename",
            "zip",
            "string_cat",
            "string_cat_if",
            "if_",
            "when",
            "add_value",
            "to_ranked_scenario_list",
            "to_true_skill_ranked_list",
            "to_agent_blueprint",
            "add_scenario_reference",
            "choose_k",
            "full_replace",
            "then",
            "else_",
            "otherwise",
            "end",
            "unpack_dict",
            "to_excel",
            "chunk_text",
            "replace_value",
            "sample",
            "add_weighted_linear_scale_sum",
        }
    )

    if name in _SKIP_NAMES or name.startswith("_"):
        return None

    # Ensure versioned services are registered before checking registry
    _register_versioned_services()

    from .accessor import get_accessor
    from .registry import ServiceRegistry

    # Check if service exists in local registry (either as class or metadata-only)
    service_exists = ServiceRegistry.exists(name) or name in ServiceRegistry._metadata
    if service_exists:
        # Use the generic ServiceAccessor which handles everything
        accessor = get_accessor(name, instance=instance, owner_class=owner_class)
        if accessor is not None:
            return accessor
        # If local registry has the service but it doesn't extend the instance's class,
        # fall through to check remote cache for a class-appropriate service

    # Check remote metadata cache for server-side services
    from .remote_metadata import RemoteMetadataCache

    cache = RemoteMetadataCache.get_instance()

    # If we have an instance, use context-aware lookup to find a service
    # that extends the instance's class. This handles cases like "vibe"
    # resolving to "vibes" for ScenarioList but "results_vibes" for Results.
    if instance is not None:
        class_name = instance.__class__.__name__
        remote_info = cache.get_for_class(name, class_name)
    else:
        remote_info = cache.get(name)

    if remote_info is not None:
        # Service exists on remote server - create a RemoteServiceAccessor
        return RemoteServiceAccessor(name, remote_info, instance=instance)

    return None


def list_available_services() -> List[str]:
    """
    Return a sorted list of available service names from ServiceRegistry.

    Returns:
        List of service names that can be accessed via ScenarioList.{name}

    Examples:
        >>> services = list_available_services()
        >>> 'firecrawl' in services
        True
        >>> len(services) > 50  # Many services available
        True
    """
    from .registry import ServiceRegistry

    return sorted(ServiceRegistry.list())


def service_directory(force_refresh: bool = False) -> "ScenarioList":
    """
    Return all available services from the remote server as a ScenarioList.

    Each scenario contains metadata about one service including its name,
    description, required API keys, and available operations.

    Args:
        force_refresh: If True, bypass cache and fetch fresh data

    Returns:
        ScenarioList with one scenario per service

    Example:
        >>> from edsl import service_directory
        >>> services = service_directory()
        >>> services.select('name', 'description')  # doctest: +SKIP
    """
    from edsl.scenarios import ScenarioList
    from .remote_metadata import RemoteMetadataCache

    cache = RemoteMetadataCache.get_instance()

    if not cache.is_remote_configured():
        raise RuntimeError(
            "Remote service runner not configured. "
            "Set EXPECTED_PARROT_SERVICE_RUNNER_URL environment variable."
        )

    services = cache.fetch_all_services(force=force_refresh)

    if not services:
        return ScenarioList([])

    service_dicts = [
        {
            "name": info.name,
            "description": info.description,
            "docstring": info.docstring,
            "version": info.version,
            "aliases": info.aliases,
            "required_keys": info.required_keys,
            "operations": info.operations,
            "extends": info.extends,
            "result_pattern": info.result_pattern,
            "result_field": info.result_field,
        }
        for info in services.values()
    ]

    return ScenarioList.from_list_of_dicts(service_dicts)
