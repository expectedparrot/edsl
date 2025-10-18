"""
Firecrawl integration for EDSL scenarios.

This module provides a FirecrawlScenario class that wraps the Firecrawl SDK
and returns EDSL Scenario and ScenarioList objects for all Firecrawl features:
- Scrape: single URL scraping
- Crawl: full website crawling
- Search: web search with content extraction
- Map: fast URL discovery
- Extract: structured data extraction with AI

Requires:
- firecrawl-py: pip install firecrawl-py
- python-dotenv: pip install python-dotenv

Environment Variables:
- FIRECRAWL_API_KEY: Your Firecrawl API key from https://firecrawl.dev
"""

from __future__ import annotations
import os
from typing import List, Optional, Dict, Any, Union
from functools import wraps
from dotenv import load_dotenv

# Load environment variables
load_dotenv()



def sum_credits_used(data):
    """
    Recursively search through a dictionary (and lists inside it)
    to find all 'creditsUsed' keys and sum their values.
    Works for dicts, lists, or a mix of both.
    """
    total = 0

    if isinstance(data, dict):
        for key, value in data.items():
            if key == "creditsUsed":
                try:
                    total += float(value)  # handles int/float values
                except (ValueError, TypeError):
                    pass  # ignore non-numeric values
            # recurse into subkeys
            total += sum_credits_used(value)

    elif isinstance(data, list):
        for item in data:
            total += sum_credits_used(item)

    return total

def _convert_to_dict(obj):
    """
    Convert SDK objects to JSON-serializable dictionaries.

    Args:
        obj: Any object that might need conversion

    Returns:
        JSON-serializable version of the object
    """
    if obj is None:
        return None
    elif hasattr(obj, "__dict__"):
        # Convert object with attributes to dict
        result = {}
        for key, value in obj.__dict__.items():
            if not key.startswith("_"):  # Skip private attributes
                result[key] = _convert_to_dict(value)
        return result
    elif isinstance(obj, list):
        # Convert list items
        return [_convert_to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        # Convert dict values
        return {key: _convert_to_dict(value) for key, value in obj.items()}
    else:
        # Return primitive types as-is
        return obj


def has_key(func):
    """
    Decorator that checks if API key is available before calling a method.
    If API key is present, executes the request via FirecrawlScenario and returns the result.
    If API key is missing, raises an exception.
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.api_key:
            ## NB: This is where we could send the request to Coop
            ## and use coop credits.
            from edsl.coop import Coop

            coop = Coop()
            request_dict = func(self, *args, **kwargs)
            result = coop.execute_firecrawl_request(request_dict)
            return result
            # raise ValueError(
            #     "FIRECRAWL_API_KEY not found. Please provide it as a parameter, "
            #     "set it as an environment variable, or add it to a .env file."
            # )

        # Create the request dictionary
        request_dict = func(self, *args, **kwargs)

        # Execute the request using FirecrawlScenario and return the actual result
        return FirecrawlScenario.from_request(request_dict)

    return wrapper


class FirecrawlRequest:
    """
    Firecrawl request class that can operate in two modes:

    1. With API key present: Automatically executes requests via FirecrawlScenario and returns results
    2. Without API key: Can be used as a descriptor/placeholder, raises exception when methods are called

    This supports both direct execution and distributed processing patterns.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize FirecrawlRequest with API key.

        Args:
            api_key: Firecrawl API key. If not provided, will look for FIRECRAWL_API_KEY
                    environment variable or .env file.
        """
        # Get API key from parameter, environment, or .env file
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY")
        # Note: No longer raises exception here - only when methods are called

    @has_key
    def scrape(
        self, url_or_urls: Union[str, List[str]], max_concurrent: int = 10, limit: Optional[int] = None, **kwargs
    ) -> Dict[str, Any]:
        """Scrape content from one or more URLs using Firecrawl.

        This method extracts clean, structured content from web pages. When an API key
        is present, it automatically executes the request and returns Scenario objects.
        Without an API key, it raises an exception when called.

        Args:
            url_or_urls: Single URL string or list of URLs to scrape. Each URL should
                be a valid HTTP/HTTPS URL.
            max_concurrent: Maximum number of concurrent requests when scraping multiple
                URLs. Only applies when url_or_urls is a list. Defaults to 10.
            limit: Maximum number of URLs to scrape when url_or_urls is a list. If None,
                scrapes all provided URLs. Defaults to None.
            **kwargs: Additional scraping parameters:
                formats: List of output formats (e.g., ["markdown", "html", "links"]).
                    Defaults to ["markdown"].
                only_main_content: Whether to extract only main content, skipping
                    navigation, ads, etc. Defaults to True.
                include_tags: List of HTML tags to specifically include in extraction.
                exclude_tags: List of HTML tags to exclude from extraction.
                headers: Custom HTTP headers as a dictionary.
                wait_for: Time to wait before scraping in milliseconds.
                timeout: Request timeout in milliseconds.
                actions: List of browser actions to perform before scraping
                    (e.g., clicking, scrolling).

        Returns:
            When API key is present:
                - For single URL: Scenario object containing scraped content
                - For multiple URLs: ScenarioList containing Scenario objects
            When API key is missing: Raises ValueError

        Raises:
            ValueError: If FIRECRAWL_API_KEY is not found in environment, parameters,
                or .env file.

        Examples:
            Basic scraping:
                >>> firecrawl = FirecrawlRequest(api_key="your_key")  # doctest: +SKIP
                >>> result = firecrawl.scrape("https://example.com")  # doctest: +SKIP
                >>> print(result["content"])  # Scraped markdown content  # doctest: +SKIP

            Multiple URLs with custom options:
                >>> urls = ["https://example.com", "https://example.org"]  # doctest: +SKIP
                >>> results = firecrawl.scrape(  # doctest: +SKIP
                ...     urls,
                ...     max_concurrent=5,
                ...     limit=2,
                ...     formats=["markdown", "html"],
                ...     only_main_content=False
                ... )

            Descriptor pattern (no API key):
                >>> class MyClass:  # doctest: +SKIP
                ...     scraper = FirecrawlRequest()  # No exception here
                >>> # my_instance.scraper.scrape("url")  # Would raise ValueError
        """
        return {
            "method": "scrape",
            "api_key": self.api_key,
            "url_or_urls": url_or_urls,
            "max_concurrent": max_concurrent,
            "limit": limit,
            "kwargs": kwargs,
        }

    @has_key
    def search(
        self, query_or_queries: Union[str, List[str]], max_concurrent: int = 5, limit: Optional[int] = None, **kwargs
    ) -> Dict[str, Any]:
        """Search the web and extract content from results using Firecrawl.

        This method performs web searches and automatically scrapes content from the
        search results. When an API key is present, it executes the search and returns
        ScenarioList objects with the results. Without an API key, it raises an exception.

        Args:
            query_or_queries: Single search query string or list of queries to search for.
                Each query should be a natural language search term.
            max_concurrent: Maximum number of concurrent requests when processing multiple
                queries. Only applies when query_or_queries is a list. Defaults to 5.
            limit: Maximum number of search results to return per query. If None, returns
                all available results. Defaults to None.
            **kwargs: Additional search parameters:
                sources: List of sources to search (e.g., ["web", "news", "images"]).
                    Defaults to ["web"].
                location: Geographic location for localized search results.
                formats: List of output formats for scraped content from results
                    (e.g., ["markdown", "html"]).

        Returns:
            When API key is present:
                ScenarioList containing Scenario objects for each search result.
                Each scenario includes search metadata (query, position, result type)
                and scraped content from the result URL.
            When API key is missing: Raises ValueError

        Raises:
            ValueError: If FIRECRAWL_API_KEY is not found in environment, parameters,
                or .env file.

        Examples:
            Basic web search:
                >>> firecrawl = FirecrawlRequest(api_key="your_key")  # doctest: +SKIP
                >>> results = firecrawl.search("python web scraping")  # doctest: +SKIP
                >>> for result in results:  # doctest: +SKIP
                ...     print(f"Title: {result['title']}")
                ...     print(f"Content: {result['content'][:100]}...")

            Multiple queries with options:
                >>> queries = ["AI research", "machine learning trends"]  # doctest: +SKIP
                >>> results = firecrawl.search(  # doctest: +SKIP
                ...     queries,
                ...     limit=5,
                ...     sources=["web", "news"],
                ...     location="US"
                ... )

            News search with custom formatting:
                >>> results = firecrawl.search(  # doctest: +SKIP
                ...     "climate change news",
                ...     sources=["news"],
                ...     formats=["markdown", "html"]
                ... )
        """
        return {
            "method": "search",
            "api_key": self.api_key,
            "query_or_queries": query_or_queries,
            "max_concurrent": max_concurrent,
            "limit": limit,
            "kwargs": kwargs,
        }

    @has_key
    def extract(
        self,
        url_or_urls: Union[str, List[str]],
        schema: Optional[Dict[str, Any]] = None,
        prompt: Optional[str] = None,
        max_concurrent: int = 5,
        limit: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Extract structured data from web pages using AI-powered analysis.

        This method uses AI to extract specific information from web pages based on
        either a JSON schema or natural language prompt. When an API key is present,
        it executes the extraction and returns structured data. Without an API key,
        it raises an exception.

        Args:
            url_or_urls: Single URL string or list of URLs to extract data from.
                Each URL should be a valid HTTP/HTTPS URL.
            schema: JSON schema defining the structure of data to extract. Should be
                a dictionary with field names and their types/descriptions. Takes
                precedence over prompt if both are provided.
            prompt: Natural language description of what data to extract. Used when
                schema is not provided. Should be clear and specific.
            max_concurrent: Maximum number of concurrent requests when processing multiple
                URLs. Only applies when url_or_urls is a list. Defaults to 5.
            limit: Maximum number of URLs to extract data from when url_or_urls is a list.
                If None, extracts from all provided URLs. Defaults to None.
            **kwargs: Additional extraction parameters:
                formats: List of output formats for the scraped content before extraction
                    (e.g., ["markdown", "html"]).

        Returns:
            When API key is present:
                - For single URL: Scenario object containing extracted structured data
                - For multiple URLs: ScenarioList containing Scenario objects
                Each result includes the extracted data in the 'extracted_data' field.
            When API key is missing: Raises ValueError

        Raises:
            ValueError: If FIRECRAWL_API_KEY is not found in environment, parameters,
                or .env file.

        Examples:
            Schema-based extraction:
                >>> schema = {  # doctest: +SKIP
                ...     "title": "string",
                ...     "price": "number",
                ...     "description": "string",
                ...     "availability": "boolean"
                ... }
                >>> firecrawl = FirecrawlRequest(api_key="your_key")  # doctest: +SKIP
                >>> result = firecrawl.extract("https://shop.example.com/product", schema=schema)  # doctest: +SKIP
                >>> print(result["extracted_data"]["title"])  # doctest: +SKIP

            Prompt-based extraction:
                >>> result = firecrawl.extract(  # doctest: +SKIP
                ...     "https://news.example.com/article",
                ...     prompt="Extract the article headline, author, and publication date"
                ... )
                >>> print(result["extracted_data"])  # doctest: +SKIP

            Multiple URLs with schema:
                >>> urls = ["https://shop1.com/item1", "https://shop2.com/item2"]  # doctest: +SKIP
                >>> results = firecrawl.extract(  # doctest: +SKIP
                ...     urls,
                ...     schema={"name": "string", "price": "number"},
                ...     max_concurrent=3,
                ...     limit=2
                ... )
                >>> for result in results:  # doctest: +SKIP
                ...     data = result["extracted_data"]
                ...     print(f"{data['name']}: ${data['price']}")
        """
        return {
            "method": "extract",
            "api_key": self.api_key,
            "url_or_urls": url_or_urls,
            "schema": schema,
            "prompt": prompt,
            "max_concurrent": max_concurrent,
            "limit": limit,
            "kwargs": kwargs,
        }

    @has_key
    def crawl(
        self,
        url: str,
        limit: Optional[int] = 10,
        max_depth: Optional[int] = 3,
        include_paths: Optional[List[str]] = None,
        exclude_paths: Optional[List[str]] = None,
        formats: Optional[List[str]] = None,
        only_main_content: bool = True,
        **kwargs,
    ) -> Dict[str, Any]:
        """Crawl an entire website and extract content from all discovered pages.

        This method performs comprehensive website crawling, discovering and scraping
        content from multiple pages within a website. When an API key is present,
        it executes the crawl and returns a ScenarioList with all pages. Without
        an API key, it raises an exception.

        Args:
            url: Base URL to start crawling from. Should be a valid HTTP/HTTPS URL.
                The crawler will discover and follow links from this starting point.
            limit: Maximum number of pages to crawl. If None, crawls all discoverable
                pages (subject to other constraints). Use this to control crawl scope.
            max_depth: Maximum crawl depth from the starting URL. Depth 0 is just the
                starting page, depth 1 includes pages directly linked from the start,
                etc. If None, no depth limit is imposed.
            include_paths: List of URL path patterns to include in the crawl. Only URLs
                matching these patterns will be crawled. Supports wildcard patterns.
            exclude_paths: List of URL path patterns to exclude from the crawl. URLs
                matching these patterns will be skipped. Applied after include_paths.
            formats: List of output formats for each crawled page (e.g., ["markdown", "html"]).
                Defaults to ["markdown"] if not specified.
            only_main_content: Whether to extract only main content from each page,
                skipping navigation, ads, footers, etc. Defaults to True.
            **kwargs: Additional crawling parameters passed to the Firecrawl API.

        Returns:
            When API key is present:
                ScenarioList containing Scenario objects for each crawled page.
                Each scenario includes the page content, URL, title, and metadata.
            When API key is missing: Raises ValueError

        Raises:
            ValueError: If FIRECRAWL_API_KEY is not found in environment, parameters,
                or .env file.

        Examples:
            Basic website crawl:
                >>> firecrawl = FirecrawlRequest(api_key="your_key")  # doctest: +SKIP
                >>> results = firecrawl.crawl("https://example.com")  # doctest: +SKIP
                >>> print(f"Crawled {len(results)} pages")  # doctest: +SKIP
                >>> for page in results:  # doctest: +SKIP
                ...     print(f"Page: {page['url']} - {page['title']}")

            Limited crawl with constraints:
                >>> results = firecrawl.crawl(  # doctest: +SKIP
                ...     "https://docs.example.com",
                ...     limit=50,
                ...     max_depth=3,
                ...     include_paths=["/docs/*", "/api/*"],
                ...     exclude_paths=["/docs/deprecated/*"]
                ... )

            Full content crawl with multiple formats:
                >>> results = firecrawl.crawl(  # doctest: +SKIP
                ...     "https://blog.example.com",
                ...     formats=["markdown", "html"],
                ...     only_main_content=False,
                ...     limit=100
                ... )
                >>> for post in results:  # doctest: +SKIP
                ...     print(f"Title: {post['title']}")
                ...     print(f"Content length: {len(post['content'])}")
        """
        return {
            "method": "crawl",
            "api_key": self.api_key,
            "url": url,
            "limit": limit,
            "max_depth": max_depth,
            "include_paths": include_paths,
            "exclude_paths": exclude_paths,
            "formats": formats,
            "only_main_content": only_main_content,
            "kwargs": kwargs,
        }

    @has_key
    def map_urls(self, url: str, limit: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """Discover and map all URLs from a website without scraping content.

        This method performs fast URL discovery to map the structure of a website
        without downloading and processing the full content of each page. When an
        API key is present, it executes the mapping and returns discovered URLs.
        Without an API key, it raises an exception.

        Args:
            url: Base URL to discover links from. Should be a valid HTTP/HTTPS URL.
                The mapper will analyze this page and discover all linked URLs.
            limit: Maximum number of URLs to discover and map. If None, discovers all
                available linked URLs. Defaults to None.
            **kwargs: Additional mapping parameters passed to the Firecrawl API.
                Common options may include depth limits or filtering criteria.

        Returns:
            When API key is present:
                ScenarioList containing Scenario objects for each discovered URL.
                Each scenario includes the discovered URL, source URL, and any
                available metadata (title, description) without full content.
            When API key is missing: Raises ValueError

        Raises:
            ValueError: If FIRECRAWL_API_KEY is not found in environment, parameters,
                or .env file.

        Examples:
            Basic URL mapping:
                >>> firecrawl = FirecrawlRequest(api_key="your_key")  # doctest: +SKIP
                >>> urls = firecrawl.map_urls("https://example.com")  # doctest: +SKIP
                >>> print(f"Discovered {len(urls)} URLs")  # doctest: +SKIP
                >>> for url_info in urls:  # doctest: +SKIP
                ...     print(f"URL: {url_info['discovered_url']}")
                ...     if 'title' in url_info:
                ...         print(f"Title: {url_info['title']}")

            Website structure analysis:
                >>> urls = firecrawl.map_urls("https://docs.example.com", limit=100)  # doctest: +SKIP
                >>> # Group URLs by path pattern
                >>> doc_urls = [u for u in urls if '/docs/' in u['discovered_url']]  # doctest: +SKIP
                >>> api_urls = [u for u in urls if '/api/' in u['discovered_url']]  # doctest: +SKIP
                >>> print(f"Documentation pages: {len(doc_urls)}")  # doctest: +SKIP
                >>> print(f"API reference pages: {len(api_urls)}")  # doctest: +SKIP

            Link discovery for targeted crawling:
                >>> # First map URLs to understand site structure
                >>> all_urls = firecrawl.map_urls("https://blog.example.com")  # doctest: +SKIP
                >>> # Then crawl specific sections
                >>> blog_posts = [u['discovered_url'] for u in all_urls  # doctest: +SKIP
                ...               if '/posts/' in u['discovered_url']]
                >>> # Use discovered URLs for targeted scraping
                >>> content = firecrawl.scrape(blog_posts[:10])  # doctest: +SKIP
        """
        return {
            "method": "map_urls",
            "api_key": self.api_key,
            "url": url,
            "limit": limit,
            "kwargs": kwargs,
        }


class FirecrawlScenario:
    """
    EDSL integration for Firecrawl web scraping and data extraction.

    This class provides methods to use all Firecrawl features and return
    results as EDSL Scenario and ScenarioList objects.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize FirecrawlScenario with API key.

        Args:
            api_key: Firecrawl API key. If not provided, will look for FIRECRAWL_API_KEY
                    environment variable or .env file.
        """
        try:
            import httpx  # noqa: F401
        except ImportError:
            raise ImportError(
                "httpx is required. Install it with: pip install httpx"
            )

        # Get API key from parameter, environment, or .env file
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY")
        if not self.api_key:
            raise ValueError(
                "FIRECRAWL_API_KEY not found. Please provide it as a parameter, "
                "set it as an environment variable, or add it to a .env file."
            )

        self.base_url = "https://api.firecrawl.dev/v2"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make an HTTP request to the Firecrawl API."""
        import httpx
        
        url = f"{self.base_url}/{endpoint}"
        
        with httpx.Client(timeout=300.0) as client:
            if method.upper() == "GET":
                response = client.get(url, headers=self.headers, params=data)
            else:
                response = client.request(method, url, headers=self.headers, json=data)
            
            response.raise_for_status()
            return response.json()

    @classmethod
    def from_request(cls, request_dict: Dict[str, Any]):
        """
        Execute a serialized Firecrawl request and return results.

        This method allows for distributed processing where requests are serialized,
        sent to an API, reconstituted here, executed, and results returned.

        Args:
            request_dict: Dictionary containing the serialized request

        Returns:
            Scenario or ScenarioList depending on the method and input
        """
        method = request_dict.get("method")
        api_key = request_dict.get("api_key")

        if not method:
            raise ValueError("Request dictionary must contain 'method' field")
        if not api_key:
            raise ValueError("Request dictionary must contain 'api_key' field")

        # Create FirecrawlScenario instance with the API key from request
        firecrawl = cls(api_key=api_key)

        # Execute the appropriate method based on the request
        if method == "scrape":
            url_or_urls = request_dict.get("url_or_urls")
            max_concurrent = request_dict.get("max_concurrent", 10)
            limit = request_dict.get("limit")
            kwargs = request_dict.get("kwargs", {})
            # Remove limit from kwargs since it's handled separately
            if "limit" in kwargs:
                del kwargs["limit"]
            return firecrawl.scrape(
                url_or_urls, max_concurrent=max_concurrent, limit=limit, **kwargs
            )

        elif method == "search":
            query_or_queries = request_dict.get("query_or_queries")
            max_concurrent = request_dict.get("max_concurrent", 5)
            limit = request_dict.get("limit")
            kwargs = request_dict.get("kwargs", {})
            # Remove limit from kwargs since it's handled separately
            if "limit" in kwargs:
                del kwargs["limit"]
            return firecrawl.search(
                query_or_queries, max_concurrent=max_concurrent, limit=limit, **kwargs
            )

        elif method == "extract":
            url_or_urls = request_dict.get("url_or_urls")
            schema = request_dict.get("schema")
            prompt = request_dict.get("prompt")
            max_concurrent = request_dict.get("max_concurrent", 5)
            limit = request_dict.get("limit")
            kwargs = request_dict.get("kwargs", {})
            # Remove limit from kwargs since it's handled separately
            if "limit" in kwargs:
                del kwargs["limit"]
            return firecrawl.extract(
                url_or_urls,
                schema=schema,
                prompt=prompt,
                max_concurrent=max_concurrent,
                limit=limit,
                **kwargs,
            )

        elif method == "crawl":
            url = request_dict.get("url")
            limit = request_dict.get("limit")
            max_depth = request_dict.get("max_depth")
            include_paths = request_dict.get("include_paths")
            exclude_paths = request_dict.get("exclude_paths")
            formats = request_dict.get("formats")
            only_main_content = request_dict.get("only_main_content", True)
            kwargs = request_dict.get("kwargs", {})
            return firecrawl.crawl(
                url,
                limit=limit,
                max_depth=max_depth,
                include_paths=include_paths,
                exclude_paths=exclude_paths,
                formats=formats,
                only_main_content=only_main_content,
                **kwargs,
            )

        elif method == "map_urls":
            url = request_dict.get("url")
            limit = request_dict.get("limit")
            kwargs = request_dict.get("kwargs", {})
            # Remove limit from kwargs since it's handled separately
            if "limit" in kwargs:
                del kwargs["limit"]
            return firecrawl.map_urls(url, limit=limit, **kwargs)

        else:
            raise ValueError(f"Unknown method: {method}")

    def scrape(
        self, url_or_urls: Union[str, List[str]], max_concurrent: int = 10, limit: Optional[int] = None, return_credits: bool = False, **kwargs
    ):
        """
        Smart scrape method that handles both single URLs and batches.

        Args:
            url_or_urls: Single URL string or list of URLs
            max_concurrent: Maximum concurrent requests for batch processing
            **kwargs: Additional parameters passed to scrape method

        Returns:
            Scenario/ScenarioList object, or tuple (object, credits_used) if return_credits=True
        """
        if isinstance(url_or_urls, str):
            # Single URL - return Scenario
            scenario, credits = self._scrape_single(url_or_urls, **kwargs)
            return (scenario, credits) if return_credits else scenario
        elif isinstance(url_or_urls, list):
            # Multiple URLs - return ScenarioList
            import asyncio
            
            # Apply limit if specified
            if limit is not None:
                url_or_urls = url_or_urls[:limit]

            result, credits = asyncio.run(
                self._scrape_batch(url_or_urls, max_concurrent, **kwargs)
            )
            return (result, credits) if return_credits else result
        else:
            raise ValueError("url_or_urls must be a string or list of strings")

    def _scrape_single(
        self,
        url: str,
        formats: Optional[List[str]] = None,
        only_main_content: bool = True,
        include_tags: Optional[List[str]] = None,
        exclude_tags: Optional[List[str]] = None,
        headers: Optional[Dict[str, str]] = None,
        wait_for: Optional[int] = None,
        timeout: Optional[int] = None,
        actions: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ):
        """
        Scrape a single URL and return a Scenario object.

        Args:
            url: URL to scrape
            formats: List of formats to return (e.g., ["markdown", "html", "links"])
            only_main_content: Whether to extract only main content
            include_tags: HTML tags to include
            exclude_tags: HTML tags to exclude
            headers: Custom headers for the request
            wait_for: Time to wait before scraping (milliseconds)
            timeout: Request timeout (milliseconds)
            actions: List of actions to perform before scraping
            **kwargs: Additional parameters passed to Firecrawl

        Returns:
            Scenario object containing the scraped data
        """
        from .scenario import Scenario

        # Set default formats if not provided
        if formats is None:
            formats = ["markdown"]

        # Build scrape parameters with correct API parameter names
        scrape_params = {
            "formats": formats,
            "onlyMainContent": only_main_content,  # API expects camelCase
            **kwargs,
        }

        # Add optional parameters if provided (using correct API parameter names)
        if include_tags:
            scrape_params["includeTags"] = include_tags  # API expects camelCase
        if exclude_tags:
            scrape_params["excludeTags"] = exclude_tags  # API expects camelCase
        if headers:
            scrape_params["headers"] = headers
        if wait_for:
            scrape_params["waitFor"] = wait_for  # API expects camelCase
        if timeout:
            scrape_params["timeout"] = timeout
        if actions:
            scrape_params["actions"] = actions

        try:
            # Prepare request payload
            payload = {"url": url, **scrape_params}
            
            # Make HTTP request to Firecrawl API
            result = self._make_request("POST", "scrape", payload)
            
            # Track credits used
            credits_used = sum_credits_used(result)

            # Extract data from response
            if result.get("success") and result.get("data"):
                data = result["data"]
                metadata = data.get("metadata", {})
                
                source_url = metadata.get("sourceURL", url)
                title = metadata.get("title", "")
                description = metadata.get("description", "")
                status_code = metadata.get("statusCode")

                # Create scenario with all available data
                scenario_data = {
                    "url": url,
                    "source_url": source_url,
                    "title": title,
                    "description": description,
                    "status_code": status_code,
                    "scrape_status": "success",
                }

                # Add format-specific content
                if data.get("markdown"):
                    scenario_data["markdown"] = data["markdown"]
                    scenario_data["content"] = data["markdown"]  # Default content field
                if data.get("html"):
                    scenario_data["html"] = data["html"]
                if data.get("links"):
                    scenario_data["links"] = data["links"]
                if data.get("screenshot"):
                    scenario_data["screenshot"] = data["screenshot"]
                if data.get("json"):
                    scenario_data["structured_data"] = data["json"]

                # Add full metadata
                scenario_data["metadata"] = metadata

                # Add action results if present
                if data.get("actions"):
                    scenario_data["actions"] = data["actions"]
            else:
                raise Exception(f"Scraping failed: {result.get('error', 'Unknown error')}")

            return Scenario(scenario_data), credits_used

        except Exception as e:
            # Return scenario with error information and 0 credits
            return Scenario(
                {
                    "url": url,
                    "scrape_status": "error",
                    "error": str(e),
                    "content": "",
                    "markdown": "",
                }
            ), 0

    def crawl(
        self,
        url: str,
        limit: Optional[int] = 10,
        max_depth: Optional[int] = 3,
        include_paths: Optional[List[str]] = None,
        exclude_paths: Optional[List[str]] = None,
        formats: Optional[List[str]] = None,
        only_main_content: bool = True,
        scrape_options: Optional[Dict[str, Any]] = None,
        return_credits: bool = False,
        **kwargs,
    ):
        """
        Crawl a website and return a ScenarioList with all pages.

        Args:
            url: Base URL to crawl
            limit: Maximum number of pages to crawl
            max_depth: Maximum crawl depth (now max_discovery_depth)
            include_paths: URL patterns to include
            exclude_paths: URL patterns to exclude
            formats: List of formats to return for each page
            only_main_content: Whether to extract only main content
            **kwargs: Additional parameters passed to Firecrawl

        Returns:
            ScenarioList containing scenarios for each crawled page
        """
        from .scenario_list import ScenarioList

        # Set default formats if not provided
        if formats is None:
            formats = ["markdown"]

        # Build crawl parameters with correct API parameter names (camelCase)
        crawl_params = {}
        
        # Build scrapeOptions
        scrape_opts = {"formats": formats}
        if only_main_content is not True:
            scrape_opts["onlyMainContent"] = only_main_content
            
        # Merge with provided scrape_options if any
        if scrape_options:
            scrape_opts.update(scrape_options)
            
        crawl_params["scrapeOptions"] = scrape_opts

        # Add optional parameters with correct API names (camelCase)
        if limit:
            crawl_params["limit"] = limit
        if max_depth:
            crawl_params["maxDiscoveryDepth"] = max_depth  # API expects camelCase
        if include_paths:
            crawl_params["includePaths"] = include_paths    # API expects camelCase
        if exclude_paths:
            crawl_params["excludePaths"] = exclude_paths    # API expects camelCase
            
        # Add any additional kwargs
        crawl_params.update(kwargs)

        try:
            # Prepare request payload
            payload = {"url": url, **crawl_params}
            
            # Make HTTP request to Firecrawl API
            result = self._make_request("POST", "crawl", payload)
            
            # Track credits used


            # Handle response - check if crawl completed successfully
            if not result.get("success"):
                raise Exception(f"Crawling failed: {result.get('error', 'Unknown error')}")
                
            # For crawl jobs, we need to poll for completion
            crawl_id = result.get("id")
            if crawl_id:
                # Poll for completion
                import time
                max_retries = 60  # 10 minutes max
                retry_count = 0
                
                while retry_count < max_retries:
                    status_result = self._make_request("GET", f"crawl/{crawl_id}")
                    
                    if status_result.get("status") == "completed":
                        result = status_result
                        break
                    elif status_result.get("status") in ["failed", "cancelled"]:
                        raise Exception(f"Crawl failed with status: {status_result.get('status')}")
                    
                    time.sleep(10)  # Wait 10 seconds between polls
                    retry_count += 1
                
                if retry_count >= max_retries:
                    raise Exception("Crawl timed out")

            credits_used = sum_credits_used(result)

            # Process crawl results
            data = result.get("data", [])
            if not data:
                raise Exception("Crawling returned no data")

            scenarios = []
            # Process each document in the crawl results
            for document in data:
                metadata = document.get("metadata", {})
                
                source_url = metadata.get("sourceURL", "")
                title = metadata.get("title", "")
                description = metadata.get("description", "")
                status_code = metadata.get("statusCode")

                scenario_data = {
                    "url": source_url,
                    "title": title,
                    "description": description,
                    "status_code": status_code,
                    "crawl_status": "success",
                }

                # Add format-specific content
                if document.get("markdown"):
                    scenario_data["markdown"] = document["markdown"]
                    scenario_data["content"] = document["markdown"]
                if document.get("html"):
                    scenario_data["html"] = document["html"]
                if document.get("links"):
                    scenario_data["links"] = document["links"]
                if metadata:
                    scenario_data["metadata"] = metadata

                scenarios.append(scenario_data)

            from .scenario import Scenario

            result = ScenarioList([Scenario(data) for data in scenarios])
            return (result, credits_used) if return_credits else result

        except Exception as e:
            # Return single scenario with error and 0 credits
            from .scenario import Scenario

            result = ScenarioList(
                [
                    Scenario(
                        {
                            "url": url,
                            "crawl_status": "error",
                            "error": str(e),
                            "content": "",
                            "markdown": "",
                        }
                    )
                ]
            )
            return (result, 0) if return_credits else result

    def search(
        self, query_or_queries: Union[str, List[str]], max_concurrent: int = 5, limit: Optional[int] = None, 
        sources: Optional[List[str]] = None, location: Optional[str] = None, 
        scrape_options: Optional[Dict[str, Any]] = None, return_credits: bool = False, **kwargs
    ):
        """
        Smart search method that handles both single queries and batches.

        Args:
            query_or_queries: Single query string or list of queries
            max_concurrent: Maximum concurrent requests for batch processing
            **kwargs: Additional parameters passed to search method

        Returns:
            ScenarioList for both single and multiple queries, or (ScenarioList, credits) if return_credits=True
        """
        if isinstance(query_or_queries, str):
            # Single query - return ScenarioList (search always returns multiple results)
            result, credits = self._search_single(
                query_or_queries, limit=limit, sources=sources, 
                location=location, scrape_options=scrape_options, **kwargs
            )
            return (result, credits) if return_credits else result
        elif isinstance(query_or_queries, list):
            # Multiple queries - return combined ScenarioList
            import asyncio

            result, credits = asyncio.run(
                self._search_batch(
                    query_or_queries, max_concurrent, limit=limit, sources=sources,
                    location=location, scrape_options=scrape_options, **kwargs
                )
            )
            return (result, credits) if return_credits else result
        else:
            raise ValueError("query_or_queries must be a string or list of strings")

    def _search_single(
        self,
        query: str,
        limit: Optional[int] = None,
        sources: Optional[List[str]] = None,
        formats: Optional[List[str]] = None,
        location: Optional[str] = None,
        scrape_options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """
        Search the web and return scraped results as a ScenarioList.

        Args:
            query: Search query
            limit: Maximum number of results
            sources: Sources to search (e.g., ["web", "news", "images"])
            formats: Formats to return for each result (passed via scrape_options)
            location: Geographic location for search
            **kwargs: Additional parameters passed to Firecrawl

        Returns:
            ScenarioList containing scenarios for each search result
        """
        from .scenario_list import ScenarioList
        from .scenario import Scenario

        # Build search parameters according to API spec
        search_params = {}
        
        # Add basic search parameters
        if limit:
            search_params["limit"] = limit
        if sources:
            search_params["sources"] = sources
        if location:
            search_params["location"] = location

        # Build scrapeOptions if any scraping parameters are specified
        final_scrape_options = {}
        
        # Add formats if specified
        if formats:
            final_scrape_options["formats"] = formats
            
        # Merge with provided scrape_options
        if scrape_options:
            final_scrape_options.update(scrape_options)
            
        # Extract common scrape options from kwargs
        scrape_option_keys = ['onlyMainContent', 'includeTags', 'excludeTags', 'maxAge', 
                             'headers', 'waitFor', 'mobile', 'skipTlsVerification', 'timeout',
                             'parsers', 'actions', 'removeBase64Images', 'blockAds', 'proxy', 'storeInCache']
        
        for key in scrape_option_keys:
            if key in kwargs:
                final_scrape_options[key] = kwargs.pop(key)
        
        # Add scrapeOptions to search params if any were specified
        if final_scrape_options:
            search_params["scrapeOptions"] = final_scrape_options
            
        # Add any remaining kwargs directly to search params
        search_params.update(kwargs)

        try:
            # Prepare request payload
            payload = {"query": query, **search_params}
            
            # Make HTTP request to Firecrawl API
            result = self._make_request("POST", "search", payload)
            
            # Track credits used
            credits_used = sum_credits_used(result)

            # Handle search response
            if not result.get("success"):
                raise Exception(f"Search failed: {result.get('error', 'Unknown error')}")
                
            scenarios = []
            data = result.get("data", {})
            
            # Process web search results
            web_results = data.get("web", []) if isinstance(data, dict) else []
            for item in web_results:
                scenario_data = {
                    "search_query": query,
                    "result_type": "web",
                    "url": item.get("url", ""),
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                    "position": item.get("position", 0),
                    "search_status": "success",
                }

                # Add scraped content if available
                if item.get("markdown"):
                    scenario_data["markdown"] = item["markdown"]
                    scenario_data["content"] = item["markdown"]
                if item.get("html"):
                    scenario_data["html"] = item["html"]
                if item.get("links"):
                    scenario_data["links"] = item["links"]

                scenarios.append(Scenario(scenario_data))
            
            # Process news results if available
            news_results = data.get("news", []) if isinstance(data, dict) else []
            for item in news_results:
                scenario_data = {
                    "search_query": query,
                    "result_type": "news",
                    "url": item.get("url", ""),
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                    "position": item.get("position", 0),
                    "search_status": "success",
                }
                scenarios.append(Scenario(scenario_data))
            
            # Process image results if available  
            image_results = data.get("images", []) if isinstance(data, dict) else []
            for item in image_results:
                scenario_data = {
                    "search_query": query,
                    "result_type": "image",
                    "url": item.get("url", ""),
                    "title": item.get("title", ""),
                    "image_url": item.get("imageUrl", item.get("url", "")),
                    "position": item.get("position", 0),
                    "search_status": "success",
                }
                scenarios.append(Scenario(scenario_data))

            result = ScenarioList(scenarios)
            return result, credits_used

        except Exception as e:
            # Return single scenario with error
            result = ScenarioList(
                [
                    Scenario(
                        {
                            "search_query": query,
                            "search_status": "error",
                            "error": str(e),
                            "content": "",
                        }
                    )
                ]
            )
            return result, 0

    def map_urls(self, url: str, limit: Optional[int] = None, return_credits: bool = False, **kwargs):
        """
        Get all URLs from a website (fast URL discovery).

        Args:
            url: Website URL to map
            limit: Maximum number of URLs to discover and map. If None, discovers all
                available linked URLs. Defaults to None.
            **kwargs: Additional parameters passed to Firecrawl

        Returns:
            ScenarioList containing scenarios for each discovered URL
        """
        from .scenario_list import ScenarioList
        from .scenario import Scenario

        try:
            # Prepare request payload
            payload = {"url": url, **kwargs}
            
            # Make HTTP request to Firecrawl API
            result = self._make_request("POST", "map", payload)
            
            # Track credits used - default to 1 for map operations if not specified
            credits_used = sum_credits_used(result)
            if credits_used == 0:
                credits_used = 1  # Default to 1 credit for map_urls operations

            # Handle response
            if not result.get("success"):
                raise Exception(f"URL mapping failed: {result.get('error', 'Unknown error')}")
                
            links = result.get("links", [])
            if not links:
                raise Exception("URL mapping returned no links")

            scenarios = []
            # Apply limit if specified
            links_to_process = links
            if limit is not None:
                links_to_process = links[:limit]
                
            for link_result in links_to_process:
                scenario_data = {
                    "discovered_url": link_result.get("url", ""),
                    "source_url": url,
                    "map_status": "success",
                }

                # Add any additional metadata
                if link_result.get("title"):
                    scenario_data["title"] = link_result["title"]
                if link_result.get("description"):
                    scenario_data["description"] = link_result["description"]

                # Store the full link result for completeness
                scenario_data["link_data"] = link_result

                scenarios.append(Scenario(scenario_data))

            result = ScenarioList(scenarios)
            return (result, credits_used) if return_credits else result

        except Exception as e:
            # Return single scenario with error
            result = ScenarioList(
                [Scenario({"source_url": url, "map_status": "error", "error": str(e)})]
            )
            return (result, 0) if return_credits else result

    def extract(
        self,
        url_or_urls: Union[str, List[str]],
        schema: Optional[Dict[str, Any]] = None,
        prompt: Optional[str] = None,
        max_concurrent: int = 5,
        limit: Optional[int] = None,
        scrape_options: Optional[Dict[str, Any]] = None,
        return_credits: bool = False,
        **kwargs,
    ):
        """
        Smart extract method that handles both single URLs and batches.

        Args:
            url_or_urls: Single URL string or list of URLs
            schema: JSON schema for structured extraction
            prompt: Natural language prompt for extraction
            max_concurrent: Maximum concurrent requests for batch processing
            **kwargs: Additional parameters passed to extract method

        Returns:
            Scenario object for single URL, ScenarioList for multiple URLs, or (object, credits) if return_credits=True
        """
        if isinstance(url_or_urls, str):
            # Single URL - return Scenario
            result, credits = self._extract_single(url_or_urls, schema, prompt, scrape_options=scrape_options, **kwargs)
            return (result, credits) if return_credits else result
        elif isinstance(url_or_urls, list):
            # Multiple URLs - return ScenarioList
            import asyncio
            
            # Apply limit if specified
            if limit is not None:
                url_or_urls = url_or_urls[:limit]

            result, credits = asyncio.run(
                self._extract_batch(
                    url_or_urls, prompt, schema, max_concurrent, scrape_options=scrape_options, **kwargs
                )
            )
            return (result, credits) if return_credits else result
        else:
            raise ValueError("url_or_urls must be a string or list of strings")

    def _extract_single(
        self,
        url: str,
        schema: Optional[Dict[str, Any]] = None,
        prompt: Optional[str] = None,
        formats: Optional[List[str]] = None,
        scrape_options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """
        Extract structured data from a URL using AI.

        Args:
            url: URL to extract data from
            schema: JSON schema for structured extraction
            prompt: Natural language prompt for extraction
            formats: Formats to include in extraction (passed via scrape_options)
            **kwargs: Additional parameters passed to Firecrawl

        Returns:
            Scenario object containing extracted structured data
        """
        from .scenario import Scenario

        # Build extraction parameters according to API spec with proper defaults
        extract_params = {
            "urls": [url],
            "enableWebSearch": False,
            "ignoreSitemap": False,
            "includeSubdomains": True,
            "showSources": False,
            "ignoreInvalidURLs": True
        }

        if schema:
            # Convert simple schema format to API expected format
            if isinstance(schema, dict) and all(isinstance(v, str) for v in schema.values()):
                # Convert simple {"field": "type"} to API format
                api_schema = {
                    "type": "object",
                    "properties": {}
                }
                for field, field_type in schema.items():
                    if field_type == "string":
                        api_schema["properties"][field] = {"type": "string"}
                    elif field_type == "number":
                        api_schema["properties"][field] = {"type": "number"}
                    elif field_type == "boolean":
                        api_schema["properties"][field] = {"type": "boolean"}
                    else:
                        # Default to string for unknown types
                        api_schema["properties"][field] = {"type": "string"}
                extract_params["schema"] = api_schema
            else:
                # Assume it's already in correct API format
                extract_params["schema"] = schema
        if prompt:
            extract_params["prompt"] = prompt
            
        # Build scrapeOptions
        final_scrape_options = {}
        if formats:
            final_scrape_options["formats"] = formats
        if scrape_options:
            final_scrape_options.update(scrape_options)
            
        if final_scrape_options:
            extract_params["scrapeOptions"] = final_scrape_options
            
        # Add any additional kwargs directly to extract params
        extract_params.update(kwargs)

        try:
            # Make HTTP request to Firecrawl API
            result = self._make_request("POST", "extract", extract_params)

            # Handle response
            if not result.get("success"):
                error_msg = result.get("error", "Unknown extraction error")
                raise Exception(f"Extraction failed: {error_msg}")

            # For extract jobs, we need to poll for completion if we get an ID
            extract_id = result.get("id")
            if extract_id:
                # Poll for completion
                import time
                max_retries = 60  # 10 minutes max
                retry_count = 0
                
                while retry_count < max_retries:
                    status_result = self._make_request("GET", f"extract/{extract_id}")
                    
                    if status_result.get("status") == "completed":
                        result = status_result
                        break
                    elif status_result.get("status") in ["failed", "cancelled"]:
                        raise Exception(f"Extract failed with status: {status_result.get('status')}")
                    
                    time.sleep(10)  # Wait 10 seconds between polls
                    retry_count += 1
                
                if retry_count >= max_retries:
                    raise Exception("Extract timed out")

            credits_used = sum_credits_used(result)

            # Get the extracted data
            extracted_data = result.get("data", {})

            scenario_data = {
                "url": url,
                "extract_status": "success",
                "extracted_data": extracted_data,
                "extraction_prompt": prompt,
                "extraction_schema": schema,
            }

            # Add sources if available
            sources = result.get("sources", [])
            if sources:
                scenario_data["sources"] = sources
                # Try to get metadata from first source
                if sources and isinstance(sources[0], dict):
                    first_source = sources[0]
                    metadata = first_source.get("metadata", {})
                    if metadata:
                        scenario_data["title"] = metadata.get("title", "")
                        scenario_data["description"] = metadata.get("description", "")

            # Add markdown/html from sources if available
            if sources:
                for source in sources:
                    if isinstance(source, dict) and source.get("markdown"):
                        scenario_data["markdown"] = source["markdown"]
                        break
                for source in sources:
                    if isinstance(source, dict) and source.get("html"):
                        scenario_data["html"] = source["html"]
                        break

            return Scenario(scenario_data), credits_used

        except Exception as e:
            # Return scenario with error information
            return Scenario(
                {
                    "url": url,
                    "extract_status": "error",
                    "error": str(e),
                    "extracted_data": {},
                    "extraction_prompt": prompt,
                    "extraction_schema": schema,
                }
            ), 0

    # Async batch methods for concurrent processing
    async def _scrape_batch(self, urls: List[str], max_concurrent: int = 10, **kwargs):
        """
        Scrape multiple URLs concurrently.

        Args:
            urls: List of URLs to scrape
            max_concurrent: Maximum number of concurrent requests
            **kwargs: Additional parameters passed to scrape method

        Returns:
            ScenarioList containing scenarios for each URL
        """
        import asyncio
        from .scenario_list import ScenarioList

        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(max_concurrent)

        async def scrape_single(url):
            async with semaphore:
                # Run the sync scrape method in executor
                loop = asyncio.get_event_loop()
                # Extract specific parameters from kwargs
                formats = kwargs.get('formats')
                only_main_content = kwargs.get('only_main_content', True)
                include_tags = kwargs.get('include_tags')
                exclude_tags = kwargs.get('exclude_tags')
                headers = kwargs.get('headers')
                wait_for = kwargs.get('wait_for')
                timeout = kwargs.get('timeout')
                actions = kwargs.get('actions')
                other_kwargs = {k: v for k, v in kwargs.items() if k not in [
                    'formats', 'only_main_content', 'include_tags', 'exclude_tags',
                    'headers', 'wait_for', 'timeout', 'actions'
                ]}
                
                return await loop.run_in_executor(
                    None, self._scrape_single, url, formats, only_main_content,
                    include_tags, exclude_tags, headers, wait_for, timeout, actions,
                    **other_kwargs
                )

        # Create tasks for all URLs
        tasks = [scrape_single(url) for url in urls]

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert any exceptions to error scenarios and track credits
        scenarios = []
        total_credits = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                from .scenario import Scenario

                scenarios.append(
                    Scenario(
                        {
                            "url": urls[i],
                            "scrape_status": "error",
                            "error": str(result),
                            "content": "",
                            "markdown": "",
                        }
                    )
                )
            else:
                # Result is a tuple (scenario, credits)
                scenario, credits = result
                scenarios.append(scenario)
                total_credits += credits

        return ScenarioList(scenarios), total_credits

    async def _search_batch(
        self, queries: List[str], max_concurrent: int = 5, limit: Optional[int] = None,
        sources: Optional[List[str]] = None, location: Optional[str] = None,
        scrape_options: Optional[Dict[str, Any]] = None, **kwargs
    ):
        """
        Search multiple queries concurrently.

        Args:
            queries: List of search queries
            max_concurrent: Maximum number of concurrent requests
            limit: Maximum number of search results to return per query. If None, returns
                all available results. Defaults to None.
            **kwargs: Additional parameters passed to search method

        Returns:
            ScenarioList containing scenarios for all search results
        """
        import asyncio
        from .scenario_list import ScenarioList

        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(max_concurrent)

        async def search_single(query):
            async with semaphore:
                # Run the sync search method in executor
                loop = asyncio.get_event_loop()
                # Extract specific parameters from kwargs
                formats = kwargs.get('formats')
                other_kwargs = {k: v for k, v in kwargs.items() if k != 'formats'}
                
                return await loop.run_in_executor(
                    None, self._search_single, query, limit, sources, formats, location, scrape_options, **other_kwargs
                )

        # Create tasks for all queries
        tasks = [search_single(query) for query in queries]

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine all results into a single ScenarioList and track total credits
        all_scenarios = []
        total_credits = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                from .scenario import Scenario

                all_scenarios.append(
                    Scenario(
                        {
                            "search_query": queries[i],
                            "search_status": "error",
                            "error": str(result),
                            "content": "",
                        }
                    )
                )
            else:
                # Result is a tuple (scenario_list, credits)
                scenario_list, credits = result
                all_scenarios.extend(scenario_list)
                total_credits += credits

        return ScenarioList(all_scenarios), total_credits

    async def _extract_batch(
        self,
        urls: List[str],
        prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        max_concurrent: int = 5,
        scrape_options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """
        Extract data from multiple URLs concurrently.

        Args:
            urls: List of URLs to extract from
            prompt: Natural language prompt for extraction
            schema: JSON schema for structured extraction
            max_concurrent: Maximum number of concurrent requests
            **kwargs: Additional parameters passed to extract method

        Returns:
            ScenarioList containing scenarios for each extraction
        """
        import asyncio
        from .scenario_list import ScenarioList

        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(max_concurrent)

        async def extract_single(url):
            async with semaphore:
                # Run the sync extract method in executor
                loop = asyncio.get_event_loop()
                # Extract specific parameters from kwargs
                formats = kwargs.get('formats')
                other_kwargs = {k: v for k, v in kwargs.items() if k != 'formats'}
                
                return await loop.run_in_executor(
                    None, self._extract_single, url, schema, prompt, formats, scrape_options, **other_kwargs
                )

        # Create tasks for all URLs
        tasks = [extract_single(url) for url in urls]

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert any exceptions to error scenarios and track credits
        scenarios = []
        total_credits = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                from .scenario import Scenario

                scenarios.append(
                    Scenario(
                        {
                            "url": urls[i],
                            "extract_status": "error",
                            "error": str(result),
                            "extracted_data": {},
                            "extraction_prompt": prompt,
                            "extraction_schema": schema,
                        }
                    )
                )
            else:
                # Result is a tuple (scenario, credits)
                scenario, credits = result
                scenarios.append(scenario)
                total_credits += credits

        return ScenarioList(scenarios), total_credits


# Convenience functions for direct usage (now support both single and batch)
def scrape_url(url_or_urls: Union[str, List[str]], **kwargs):
    """Convenience function to scrape single URL or multiple URLs."""
    firecrawl = FirecrawlScenario()
    return firecrawl.scrape(url_or_urls, **kwargs)


def crawl_website(url: str, **kwargs):
    """Convenience function to crawl a website."""
    firecrawl = FirecrawlScenario()
    return firecrawl.crawl(url, **kwargs)


def search_web(query_or_queries: Union[str, List[str]], **kwargs):
    """Convenience function to search the web with single query or multiple queries."""
    firecrawl = FirecrawlScenario()
    return firecrawl.search(query_or_queries, **kwargs)


def map_website_urls(url: str, **kwargs):
    """Convenience function to map website URLs."""
    firecrawl = FirecrawlScenario()
    return firecrawl.map_urls(url, **kwargs)


def extract_data(url_or_urls: Union[str, List[str]], **kwargs):
    """Convenience function to extract structured data from single URL or multiple URLs."""
    firecrawl = FirecrawlScenario()
    return firecrawl.extract(url_or_urls, **kwargs)


# Request-based convenience functions for distributed processing
def create_scrape_request(
    url_or_urls: Union[str, List[str]], api_key: Optional[str] = None, **kwargs
) -> Dict[str, Any]:
    """Create a serializable scrape request."""
    request = FirecrawlRequest(api_key=api_key)
    return request.scrape(url_or_urls, **kwargs)


def create_search_request(
    query_or_queries: Union[str, List[str]], api_key: Optional[str] = None, **kwargs
) -> Dict[str, Any]:
    """Create a serializable search request."""
    request = FirecrawlRequest(api_key=api_key)
    return request.search(query_or_queries, **kwargs)


def create_extract_request(
    url_or_urls: Union[str, List[str]], api_key: Optional[str] = None, **kwargs
) -> Dict[str, Any]:
    """Create a serializable extract request."""
    request = FirecrawlRequest(api_key=api_key)
    return request.extract(url_or_urls, **kwargs)


def create_crawl_request(
    url: str, api_key: Optional[str] = None, **kwargs
) -> Dict[str, Any]:
    """Create a serializable crawl request."""
    request = FirecrawlRequest(api_key=api_key)
    return request.crawl(url, **kwargs)


def create_map_request(
    url: str, api_key: Optional[str] = None, **kwargs
) -> Dict[str, Any]:
    """Create a serializable map_urls request."""
    request = FirecrawlRequest(api_key=api_key)
    return request.map_urls(url, **kwargs)


def execute_request(request_dict: Dict[str, Any]):
    """Execute a serialized Firecrawl request and return results."""
    return FirecrawlScenario.from_request(request_dict)


# Legacy async functions (deprecated - use the smart methods instead)
async def scrape_urls_batch(urls: List[str], max_concurrent: int = 10, **kwargs):
    """DEPRECATED: Use scrape_url(urls) instead."""
    firecrawl = FirecrawlScenario()
    return await firecrawl._scrape_batch(urls, max_concurrent, **kwargs)


async def search_queries_batch(queries: List[str], max_concurrent: int = 5, **kwargs):
    """DEPRECATED: Use search_web(queries) instead."""
    firecrawl = FirecrawlScenario()
    return await firecrawl._search_batch(queries, max_concurrent, **kwargs)


async def extract_data_batch(
    urls: List[str],
    prompt: Optional[str] = None,
    schema: Optional[Dict[str, Any]] = None,
    max_concurrent: int = 5,
    **kwargs,
):
    """DEPRECATED: Use extract_data(urls, prompt=prompt, schema=schema) instead."""
    firecrawl = FirecrawlScenario()
    return await firecrawl._extract_batch(
        urls, prompt, schema, max_concurrent, **kwargs
    )
