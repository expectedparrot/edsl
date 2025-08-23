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
    elif hasattr(obj, '__dict__'):
        # Convert object with attributes to dict
        result = {}
        for key, value in obj.__dict__.items():
            if not key.startswith('_'):  # Skip private attributes
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
            raise ValueError(
                "FIRECRAWL_API_KEY not found. Please provide it as a parameter, "
                "set it as an environment variable, or add it to a .env file."
            )
        
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
        self,
        url_or_urls: Union[str, List[str]],
        max_concurrent: int = 10,
        **kwargs
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
                >>> firecrawl = FirecrawlRequest(api_key="your_key")
                >>> result = firecrawl.scrape("https://example.com")
                >>> print(result["content"])  # Scraped markdown content
                
            Multiple URLs with custom options:
                >>> urls = ["https://example.com", "https://example.org"]
                >>> results = firecrawl.scrape(
                ...     urls, 
                ...     max_concurrent=5,
                ...     formats=["markdown", "html"],
                ...     only_main_content=False
                ... )
                
            Descriptor pattern (no API key):
                >>> class MyClass:
                ...     scraper = FirecrawlRequest()  # No exception here
                >>> # my_instance.scraper.scrape("url")  # Would raise ValueError
        """
        return {
            "method": "scrape",
            "api_key": self.api_key,
            "url_or_urls": url_or_urls,
            "max_concurrent": max_concurrent,
            "kwargs": kwargs
        }
    
    @has_key
    def search(
        self,
        query_or_queries: Union[str, List[str]],
        max_concurrent: int = 5,
        **kwargs
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
            **kwargs: Additional search parameters:
                limit: Maximum number of search results to return per query.
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
                >>> firecrawl = FirecrawlRequest(api_key="your_key")
                >>> results = firecrawl.search("python web scraping")
                >>> for result in results:
                ...     print(f"Title: {result['title']}")
                ...     print(f"Content: {result['content'][:100]}...")
                
            Multiple queries with options:
                >>> queries = ["AI research", "machine learning trends"]
                >>> results = firecrawl.search(
                ...     queries,
                ...     limit=5,
                ...     sources=["web", "news"],
                ...     location="US"
                ... )
                
            News search with custom formatting:
                >>> results = firecrawl.search(
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
            "kwargs": kwargs
        }
    
    @has_key
    def extract(
        self,
        url_or_urls: Union[str, List[str]],
        schema: Optional[Dict[str, Any]] = None,
        prompt: Optional[str] = None,
        max_concurrent: int = 5,
        **kwargs
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
                >>> schema = {
                ...     "title": "string",
                ...     "price": "number", 
                ...     "description": "string",
                ...     "availability": "boolean"
                ... }
                >>> firecrawl = FirecrawlRequest(api_key="your_key")
                >>> result = firecrawl.extract("https://shop.example.com/product", schema=schema)
                >>> print(result["extracted_data"]["title"])
                
            Prompt-based extraction:
                >>> result = firecrawl.extract(
                ...     "https://news.example.com/article",
                ...     prompt="Extract the article headline, author, and publication date"
                ... )
                >>> print(result["extracted_data"])
                
            Multiple URLs with schema:
                >>> urls = ["https://shop1.com/item1", "https://shop2.com/item2"]
                >>> results = firecrawl.extract(
                ...     urls,
                ...     schema={"name": "string", "price": "number"},
                ...     max_concurrent=3
                ... )
                >>> for result in results:
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
            "kwargs": kwargs
        }
    
    @has_key
    def crawl(
        self,
        url: str,
        limit: Optional[int] = None,
        max_depth: Optional[int] = None,
        include_paths: Optional[List[str]] = None,
        exclude_paths: Optional[List[str]] = None,
        formats: Optional[List[str]] = None,
        only_main_content: bool = True,
        **kwargs
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
                >>> firecrawl = FirecrawlRequest(api_key="your_key")
                >>> results = firecrawl.crawl("https://example.com")
                >>> print(f"Crawled {len(results)} pages")
                >>> for page in results:
                ...     print(f"Page: {page['url']} - {page['title']}")
                
            Limited crawl with constraints:
                >>> results = firecrawl.crawl(
                ...     "https://docs.example.com",
                ...     limit=50,
                ...     max_depth=3,
                ...     include_paths=["/docs/*", "/api/*"],
                ...     exclude_paths=["/docs/deprecated/*"]
                ... )
                
            Full content crawl with multiple formats:
                >>> results = firecrawl.crawl(
                ...     "https://blog.example.com",
                ...     formats=["markdown", "html"],
                ...     only_main_content=False,
                ...     limit=100
                ... )
                >>> for post in results:
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
            "kwargs": kwargs
        }
    
    @has_key
    def map_urls(
        self,
        url: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Discover and map all URLs from a website without scraping content.
        
        This method performs fast URL discovery to map the structure of a website
        without downloading and processing the full content of each page. When an 
        API key is present, it executes the mapping and returns discovered URLs.
        Without an API key, it raises an exception.
        
        Args:
            url: Base URL to discover links from. Should be a valid HTTP/HTTPS URL.
                The mapper will analyze this page and discover all linked URLs.
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
                >>> firecrawl = FirecrawlRequest(api_key="your_key")
                >>> urls = firecrawl.map_urls("https://example.com")
                >>> print(f"Discovered {len(urls)} URLs")
                >>> for url_info in urls:
                ...     print(f"URL: {url_info['discovered_url']}")
                ...     if 'title' in url_info:
                ...         print(f"Title: {url_info['title']}")
                
            Website structure analysis:
                >>> urls = firecrawl.map_urls("https://docs.example.com")
                >>> # Group URLs by path pattern
                >>> doc_urls = [u for u in urls if '/docs/' in u['discovered_url']]
                >>> api_urls = [u for u in urls if '/api/' in u['discovered_url']]
                >>> print(f"Documentation pages: {len(doc_urls)}")
                >>> print(f"API reference pages: {len(api_urls)}")
                
            Link discovery for targeted crawling:
                >>> # First map URLs to understand site structure
                >>> all_urls = firecrawl.map_urls("https://blog.example.com")
                >>> # Then crawl specific sections
                >>> blog_posts = [u['discovered_url'] for u in all_urls 
                ...               if '/posts/' in u['discovered_url']]
                >>> # Use discovered URLs for targeted scraping
                >>> content = firecrawl.scrape(blog_posts[:10])
        """
        return {
            "method": "map_urls",
            "api_key": self.api_key,
            "url": url,
            "kwargs": kwargs
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
            from firecrawl import Firecrawl
        except ImportError:
            raise ImportError(
                "firecrawl-py is required. Install it with: pip install firecrawl-py"
            )
        
        # Get API key from parameter, environment, or .env file
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY")
        if not self.api_key:
            raise ValueError(
                "FIRECRAWL_API_KEY not found. Please provide it as a parameter, "
                "set it as an environment variable, or add it to a .env file."
            )
        
        self.client = Firecrawl(api_key=self.api_key)
    
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
            kwargs = request_dict.get("kwargs", {})
            return firecrawl.scrape(url_or_urls, max_concurrent=max_concurrent, **kwargs)
            
        elif method == "search":
            query_or_queries = request_dict.get("query_or_queries")
            max_concurrent = request_dict.get("max_concurrent", 5)
            kwargs = request_dict.get("kwargs", {})
            return firecrawl.search(query_or_queries, max_concurrent=max_concurrent, **kwargs)
            
        elif method == "extract":
            url_or_urls = request_dict.get("url_or_urls")
            schema = request_dict.get("schema")
            prompt = request_dict.get("prompt")
            max_concurrent = request_dict.get("max_concurrent", 5)
            kwargs = request_dict.get("kwargs", {})
            return firecrawl.extract(url_or_urls, schema=schema, prompt=prompt, max_concurrent=max_concurrent, **kwargs)
            
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
                url, limit=limit, max_depth=max_depth, 
                include_paths=include_paths, exclude_paths=exclude_paths,
                formats=formats, only_main_content=only_main_content, **kwargs
            )
            
        elif method == "map_urls":
            url = request_dict.get("url")
            kwargs = request_dict.get("kwargs", {})
            return firecrawl.map_urls(url, **kwargs)
            
        else:
            raise ValueError(f"Unknown method: {method}")
    
    def scrape(
        self,
        url_or_urls: Union[str, List[str]],
        max_concurrent: int = 10,
        **kwargs
    ):
        """
        Smart scrape method that handles both single URLs and batches.
        
        Args:
            url_or_urls: Single URL string or list of URLs
            max_concurrent: Maximum concurrent requests for batch processing
            **kwargs: Additional parameters passed to scrape method
            
        Returns:
            Scenario object for single URL, ScenarioList for multiple URLs
        """
        if isinstance(url_or_urls, str):
            # Single URL - return Scenario
            return self._scrape_single(url_or_urls, **kwargs)
        elif isinstance(url_or_urls, list):
            # Multiple URLs - return ScenarioList
            import asyncio
            return asyncio.run(self._scrape_batch(url_or_urls, max_concurrent, **kwargs))
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
        **kwargs
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
        
        # Build scrape parameters
        scrape_params = {
            "formats": formats,
            "only_main_content": only_main_content,
            **kwargs
        }
        
        # Add optional parameters if provided
        if include_tags:
            scrape_params["includeTags"] = include_tags
        if exclude_tags:
            scrape_params["excludeTags"] = exclude_tags
        if headers:
            scrape_params["headers"] = headers
        if wait_for:
            scrape_params["waitFor"] = wait_for
        if timeout:
            scrape_params["timeout"] = timeout
        if actions:
            scrape_params["actions"] = actions
        
        try:
            result = self.client.scrape(url, **scrape_params)
            
            # Handle the Document object response format
            if hasattr(result, 'metadata') and result.metadata:
                metadata = result.metadata
                source_url = getattr(metadata, 'sourceURL', url) if hasattr(metadata, 'sourceURL') else url
                title = getattr(metadata, 'title', '') if hasattr(metadata, 'title') else ''
                description = getattr(metadata, 'description', '') if hasattr(metadata, 'description') else ''
                status_code = getattr(metadata, 'statusCode', None) if hasattr(metadata, 'statusCode') else None
            else:
                source_url = url
                title = ''
                description = ''
                status_code = None
            
            # Create scenario with all available data
            scenario_data = {
                "url": url,
                "source_url": source_url,
                "title": title,
                "description": description,
                "status_code": status_code,
                "scrape_status": "success"
            }
            
            # Add format-specific content from the Document object
            if hasattr(result, 'markdown') and result.markdown:
                scenario_data["markdown"] = result.markdown
                scenario_data["content"] = result.markdown  # Default content field
            if hasattr(result, 'html') and result.html:
                scenario_data["html"] = result.html
            if hasattr(result, 'links') and result.links:
                scenario_data["links"] = _convert_to_dict(result.links)
            if hasattr(result, 'screenshot') and result.screenshot:
                scenario_data["screenshot"] = result.screenshot
            if hasattr(result, 'json') and result.json:
                scenario_data["structured_data"] = _convert_to_dict(result.json)
            
            # Add full metadata (convert to dict for serialization)
            if hasattr(result, 'metadata') and result.metadata:
                scenario_data["metadata"] = _convert_to_dict(result.metadata)
            
            # Add action results if present (convert to dict for serialization)
            if hasattr(result, 'actions') and result.actions:
                scenario_data["actions"] = _convert_to_dict(result.actions)
            
            return Scenario(scenario_data)
            
        except Exception as e:
            # Return scenario with error information
            return Scenario({
                "url": url,
                "scrape_status": "error",
                "error": str(e),
                "content": "",
                "markdown": ""
            })
    
    def crawl(
        self,
        url: str,
        limit: Optional[int] = None,
        max_depth: Optional[int] = None,
        include_paths: Optional[List[str]] = None,
        exclude_paths: Optional[List[str]] = None,
        formats: Optional[List[str]] = None,
        only_main_content: bool = True,
        **kwargs
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
        
        # Build scrape options for the crawl
        scrape_options = {
            "formats": formats,
            "only_main_content": only_main_content
        }
        
        # Build crawl parameters
        crawl_params = {
            "scrape_options": scrape_options,
            **kwargs
        }
        
        # Add optional parameters if provided
        if limit:
            crawl_params["limit"] = limit
        if max_depth:
            crawl_params["max_discovery_depth"] = max_depth
        if include_paths:
            crawl_params["include_paths"] = include_paths
        if exclude_paths:
            crawl_params["exclude_paths"] = exclude_paths
        
        try:
            result = self.client.crawl(url, **crawl_params)
            
            # Handle CrawlJob response - check if crawl completed successfully
            if not hasattr(result, 'data') or not result.data:
                raise Exception(f"Crawling failed or returned no data: {result.status if hasattr(result, 'status') else 'Unknown status'}")
            
            scenarios = []
            # Process each Document in the crawl results
            for document in result.data:
                # Extract metadata
                if hasattr(document, 'metadata') and document.metadata:
                    metadata = document.metadata
                    source_url = getattr(metadata, 'sourceURL', '') if hasattr(metadata, 'sourceURL') else ''
                    title = getattr(metadata, 'title', '') if hasattr(metadata, 'title') else ''
                    description = getattr(metadata, 'description', '') if hasattr(metadata, 'description') else ''
                    status_code = getattr(metadata, 'statusCode', None) if hasattr(metadata, 'statusCode') else None
                else:
                    source_url = ''
                    title = ''
                    description = ''
                    status_code = None
                
                scenario_data = {
                    "url": source_url,
                    "title": title,
                    "description": description,
                    "status_code": status_code,
                    "crawl_status": "success"
                }
                
                # Add format-specific content from the Document object
                if hasattr(document, 'markdown') and document.markdown:
                    scenario_data["markdown"] = document.markdown
                    scenario_data["content"] = document.markdown
                if hasattr(document, 'html') and document.html:
                    scenario_data["html"] = document.html
                if hasattr(document, 'links') and document.links:
                    scenario_data["links"] = _convert_to_dict(document.links)
                if hasattr(document, 'metadata') and document.metadata:
                    scenario_data["metadata"] = _convert_to_dict(document.metadata)
                
                scenarios.append(scenario_data)
            
            from .scenario import Scenario
            return ScenarioList([Scenario(data) for data in scenarios])
            
        except Exception as e:
            # Return single scenario with error
            from .scenario import Scenario
            return ScenarioList([Scenario({
                "url": url,
                "crawl_status": "error",
                "error": str(e),
                "content": "",
                "markdown": ""
            })])
    
    def search(
        self,
        query_or_queries: Union[str, List[str]],
        max_concurrent: int = 5,
        **kwargs
    ):
        """
        Smart search method that handles both single queries and batches.
        
        Args:
            query_or_queries: Single query string or list of queries
            max_concurrent: Maximum concurrent requests for batch processing
            **kwargs: Additional parameters passed to search method
            
        Returns:
            ScenarioList for both single and multiple queries
        """
        if isinstance(query_or_queries, str):
            # Single query - return ScenarioList (search always returns multiple results)
            return self._search_single(query_or_queries, **kwargs)
        elif isinstance(query_or_queries, list):
            # Multiple queries - return combined ScenarioList
            import asyncio
            return asyncio.run(self._search_batch(query_or_queries, max_concurrent, **kwargs))
        else:
            raise ValueError("query_or_queries must be a string or list of strings")
    
    def _search_single(
        self,
        query: str,
        limit: Optional[int] = None,
        sources: Optional[List[str]] = None,
        formats: Optional[List[str]] = None,
        location: Optional[str] = None,
        **kwargs
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
        
        # Build scrape options if formats specified
        search_params = {}
        if formats:
            search_params["scrape_options"] = {"formats": formats}
        
        # Add search parameters
        if limit:
            search_params["limit"] = limit
        if sources:
            search_params["sources"] = sources
        if location:
            search_params["location"] = location
        
        # Add any additional kwargs
        search_params.update(kwargs)
        
        try:
            result = self.client.search(query, **search_params)
            
            # Handle SearchData object response
            scenarios = []
            
            # Process web results
            if hasattr(result, 'web') and result.web:
                for item in result.web:
                    scenario_data = {
                        "search_query": query,
                        "result_type": "web",
                        "url": getattr(item, "url", "") if hasattr(item, "url") else "",
                        "title": getattr(item, "title", "") if hasattr(item, "title") else "",
                        "description": getattr(item, "description", "") if hasattr(item, "description") else "",
                        "position": getattr(item, "position", None) if hasattr(item, "position") else None,
                        "search_status": "success"
                    }
                    
                    # Add scraped content if available
                    if hasattr(item, "markdown") and item.markdown:
                        scenario_data["markdown"] = item.markdown
                        scenario_data["content"] = item.markdown
                    if hasattr(item, "html") and item.html:
                        scenario_data["html"] = item.html
                    
                    scenarios.append(Scenario(scenario_data))
            
            # Process news results
            if hasattr(result, 'news') and result.news:
                for item in result.news:
                    scenario_data = {
                        "search_query": query,
                        "result_type": "news",
                        "url": getattr(item, "url", "") if hasattr(item, "url") else "",
                        "title": getattr(item, "title", "") if hasattr(item, "title") else "",
                        "snippet": getattr(item, "snippet", "") if hasattr(item, "snippet") else "",
                        "date": getattr(item, "date", "") if hasattr(item, "date") else "",
                        "position": getattr(item, "position", None) if hasattr(item, "position") else None,
                        "search_status": "success"
                    }
                    scenarios.append(Scenario(scenario_data))
            
            # Process image results
            if hasattr(result, 'images') and result.images:
                for item in result.images:
                    scenario_data = {
                        "search_query": query,
                        "result_type": "image",
                        "url": getattr(item, "url", "") if hasattr(item, "url") else "",
                        "title": getattr(item, "title", "") if hasattr(item, "title") else "",
                        "image_url": getattr(item, "imageUrl", "") if hasattr(item, "imageUrl") else "",
                        "image_width": getattr(item, "imageWidth", None) if hasattr(item, "imageWidth") else None,
                        "image_height": getattr(item, "imageHeight", None) if hasattr(item, "imageHeight") else None,
                        "position": getattr(item, "position", None) if hasattr(item, "position") else None,
                        "search_status": "success"
                    }
                    scenarios.append(Scenario(scenario_data))
            
            return ScenarioList(scenarios)
            
        except Exception as e:
            # Return single scenario with error
            return ScenarioList([Scenario({
                "search_query": query,
                "search_status": "error",
                "error": str(e),
                "content": ""
            })])
    
    def map_urls(self, url: str, **kwargs):
        """
        Get all URLs from a website (fast URL discovery).
        
        Args:
            url: Website URL to map
            **kwargs: Additional parameters passed to Firecrawl
            
        Returns:
            ScenarioList containing scenarios for each discovered URL
        """
        from .scenario_list import ScenarioList
        from .scenario import Scenario
        
        try:
            result = self.client.map(url, **kwargs)
            
            # Handle MapData object response
            if not hasattr(result, 'links') or not result.links:
                raise Exception(f"URL mapping failed or returned no links")
            
            scenarios = []
            for link_result in result.links:
                scenario_data = {
                    "discovered_url": getattr(link_result, "url", "") if hasattr(link_result, "url") else "",
                    "source_url": url,
                    "map_status": "success"
                }
                
                # Add any additional metadata from the LinkResult (convert to dict)
                if hasattr(link_result, "title") and link_result.title:
                    scenario_data["title"] = link_result.title
                if hasattr(link_result, "description") and link_result.description:
                    scenario_data["description"] = link_result.description
                
                # Store the full link result as a dict for completeness
                scenario_data["link_data"] = _convert_to_dict(link_result)
                
                scenarios.append(Scenario(scenario_data))
            
            return ScenarioList(scenarios)
            
        except Exception as e:
            # Return single scenario with error
            return ScenarioList([Scenario({
                "source_url": url,
                "map_status": "error",
                "error": str(e)
            })])
    
    def extract(
        self,
        url_or_urls: Union[str, List[str]],
        schema: Optional[Dict[str, Any]] = None,
        prompt: Optional[str] = None,
        max_concurrent: int = 5,
        **kwargs
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
            Scenario object for single URL, ScenarioList for multiple URLs
        """
        if isinstance(url_or_urls, str):
            # Single URL - return Scenario
            return self._extract_single(url_or_urls, schema, prompt, **kwargs)
        elif isinstance(url_or_urls, list):
            # Multiple URLs - return ScenarioList
            import asyncio
            return asyncio.run(self._extract_batch(url_or_urls, prompt, schema, max_concurrent, **kwargs))
        else:
            raise ValueError("url_or_urls must be a string or list of strings")
    
    def _extract_single(
        self,
        url: str,
        schema: Optional[Dict[str, Any]] = None,
        prompt: Optional[str] = None,
        formats: Optional[List[str]] = None,
        **kwargs
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
        
        # Build extraction parameters - note: extract now takes urls (list) not url
        extract_params = {"urls": [url], **kwargs}
        
        if schema:
            extract_params["schema"] = schema
        if prompt:
            extract_params["prompt"] = prompt
        if formats:
            extract_params["scrape_options"] = {"formats": formats}
        
        try:
            result = self.client.extract(**extract_params)
            
            # Handle ExtractResponse object
            if not hasattr(result, 'success') or not result.success:
                error_msg = getattr(result, 'error', 'Unknown extraction error')
                raise Exception(f"Extraction failed: {error_msg}")
            
            # Get the extracted data
            extracted_data = getattr(result, 'data', {}) if hasattr(result, 'data') else {}
            
            scenario_data = {
                "url": url,
                "extract_status": "success",
                "extracted_data": extracted_data,
                "extraction_prompt": prompt,
                "extraction_schema": schema
            }
            
            # Add sources if available (convert to dict for serialization)
            if hasattr(result, 'sources') and result.sources:
                scenario_data["sources"] = _convert_to_dict(result.sources)
                # Try to get metadata from first source
                if len(result.sources) > 0 and hasattr(result.sources[0], 'metadata'):
                    metadata = result.sources[0].metadata
                    if metadata:
                        scenario_data["title"] = getattr(metadata, 'title', '') if hasattr(metadata, 'title') else ''
                        scenario_data["description"] = getattr(metadata, 'description', '') if hasattr(metadata, 'description') else ''
            
            # Add markdown/html from sources if available
            if hasattr(result, 'sources') and result.sources:
                for source in result.sources:
                    if hasattr(source, 'markdown') and source.markdown:
                        scenario_data["markdown"] = source.markdown
                        break
                for source in result.sources:
                    if hasattr(source, 'html') and source.html:
                        scenario_data["html"] = source.html
                        break
            
            return Scenario(scenario_data)
            
        except Exception as e:
            # Return scenario with error information
            return Scenario({
                "url": url,
                "extract_status": "error",
                "error": str(e),
                "extracted_data": {},
                "extraction_prompt": prompt,
                "extraction_schema": schema
            })
    
    # Async batch methods for concurrent processing
    async def _scrape_batch(
        self,
        urls: List[str],
        max_concurrent: int = 10,
        **kwargs
    ):
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
                return await loop.run_in_executor(None, self._scrape_single, url, **kwargs)
        
        # Create tasks for all URLs
        tasks = [scrape_single(url) for url in urls]
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert any exceptions to error scenarios
        scenarios = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                from .scenario import Scenario
                scenarios.append(Scenario({
                    "url": urls[i],
                    "scrape_status": "error",
                    "error": str(result),
                    "content": "",
                    "markdown": ""
                }))
            else:
                scenarios.append(result)
        
        return ScenarioList(scenarios)
    
    async def _search_batch(
        self,
        queries: List[str],
        max_concurrent: int = 5,
        **kwargs
    ):
        """
        Search multiple queries concurrently.
        
        Args:
            queries: List of search queries
            max_concurrent: Maximum number of concurrent requests
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
                return await loop.run_in_executor(None, self._search_single, query, **kwargs)
        
        # Create tasks for all queries
        tasks = [search_single(query) for query in queries]
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine all results into a single ScenarioList
        all_scenarios = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                from .scenario import Scenario
                all_scenarios.append(Scenario({
                    "search_query": queries[i],
                    "search_status": "error",
                    "error": str(result),
                    "content": ""
                }))
            else:
                # Add all scenarios from this search result
                all_scenarios.extend(result)
        
        return ScenarioList(all_scenarios)
    
    async def _extract_batch(
        self,
        urls: List[str],
        prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        max_concurrent: int = 5,
        **kwargs
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
                return await loop.run_in_executor(None, self._extract_single, url, schema, prompt, None, **kwargs)
        
        # Create tasks for all URLs
        tasks = [extract_single(url) for url in urls]
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert any exceptions to error scenarios
        scenarios = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                from .scenario import Scenario
                scenarios.append(Scenario({
                    "url": urls[i],
                    "extract_status": "error",
                    "error": str(result),
                    "extracted_data": {},
                    "extraction_prompt": prompt,
                    "extraction_schema": schema
                }))
            else:
                scenarios.append(result)
        
        return ScenarioList(scenarios)


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
def create_scrape_request(url_or_urls: Union[str, List[str]], api_key: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Create a serializable scrape request."""
    request = FirecrawlRequest(api_key=api_key)
    return request.scrape(url_or_urls, **kwargs)


def create_search_request(query_or_queries: Union[str, List[str]], api_key: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Create a serializable search request."""
    request = FirecrawlRequest(api_key=api_key)
    return request.search(query_or_queries, **kwargs)


def create_extract_request(url_or_urls: Union[str, List[str]], api_key: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Create a serializable extract request."""
    request = FirecrawlRequest(api_key=api_key)
    return request.extract(url_or_urls, **kwargs)


def create_crawl_request(url: str, api_key: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Create a serializable crawl request."""
    request = FirecrawlRequest(api_key=api_key)
    return request.crawl(url, **kwargs)


def create_map_request(url: str, api_key: Optional[str] = None, **kwargs) -> Dict[str, Any]:
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


async def extract_data_batch(urls: List[str], prompt: Optional[str] = None, 
                           schema: Optional[Dict[str, Any]] = None, 
                           max_concurrent: int = 5, **kwargs):
    """DEPRECATED: Use extract_data(urls, prompt=prompt, schema=schema) instead."""
    firecrawl = FirecrawlScenario()
    return await firecrawl._extract_batch(urls, prompt, schema, max_concurrent, **kwargs)
