Firecrawl Integration
=====================

The EDSL Firecrawl integration provides seamless access to the Firecrawl web scraping platform, allowing you to scrape, crawl, search, and extract structured data from web content directly into EDSL Scenarios and ScenarioLists.

Features
--------

- **Scrape**: Extract clean content from single URLs or batches of URLs
- **Crawl**: Comprehensively crawl entire websites and extract content from all pages
- **Search**: Perform web searches and scrape content from search results
- **Map URLs**: Fast URL discovery without full content extraction
- **Extract**: AI-powered structured data extraction using schemas or natural language prompts

All methods return EDSL Scenario or ScenarioList objects, making web data immediately ready for survey research, analysis, and other EDSL workflows.

Installation
------------

Install the required dependencies:

.. code-block:: bash

    pip install firecrawl-py python-dotenv

Setup
-----

Get your Firecrawl API key from `https://firecrawl.dev <https://firecrawl.dev>`_ and set it as an environment variable:

.. code-block:: bash

    export FIRECRAWL_API_KEY=your_api_key_here

Or add it to a `.env` file in your project:

.. code-block:: text

    FIRECRAWL_API_KEY=your_api_key_here

Basic Usage
-----------

Quick Start Examples
~~~~~~~~~~~~~~~~~~~~

**Scraping a single URL:**

.. code-block:: python

    from edsl.scenarios.firecrawl_scenario import scrape_url
    
    # Scrape a single URL
    result = scrape_url("https://example.com")
    print(result["content"])  # Scraped markdown content
    print(result["title"])    # Page title

**Scraping multiple URLs:**

.. code-block:: python

    from edsl.scenarios.firecrawl_scenario import scrape_url
    
    # Scrape multiple URLs
    urls = ["https://example.com", "https://example.org"]
    results = scrape_url(urls, max_concurrent=5)
    
    for result in results:
        print(f"URL: {result['url']}")
        print(f"Title: {result['title']}")
        print(f"Content: {result['content'][:100]}...")

**Web search with content extraction:**

.. code-block:: python

    from edsl.scenarios.firecrawl_scenario import search_web
    
    # Search and extract content from results
    results = search_web("python web scraping tutorials")
    
    for result in results:
        print(f"Title: {result['title']}")
        print(f"URL: {result['url']}")
        print(f"Content: {result['content'][:100]}...")

**Crawling an entire website:**

.. code-block:: python

    from edsl.scenarios.firecrawl_scenario import crawl_website
    
    # Crawl a website with limits
    results = crawl_website(
        "https://docs.example.com",
        limit=50,                     # Max 50 pages
        max_depth=3,                  # Max depth of 3
        include_paths=["/docs/*"]     # Only crawl documentation
    )
    
    print(f"Crawled {len(results)} pages")

**Structured data extraction:**

.. code-block:: python

    from edsl.scenarios.firecrawl_scenario import extract_data
    
    # Define what data to extract
    schema = {
        "title": "string",
        "price": "number",
        "description": "string",
        "availability": "boolean"
    }
    
    # Extract structured data
    result = extract_data("https://shop.example.com/product", schema=schema)
    extracted = result["extracted_data"]
    print(f"Product: {extracted['title']}")
    print(f"Price: ${extracted['price']}")

Class-Based API
---------------

For more control, use the class-based API:

FirecrawlScenario Class
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from edsl.scenarios.firecrawl_scenario import FirecrawlScenario
    
    # Initialize with API key (optional if set in environment)
    firecrawl = FirecrawlScenario(api_key="your_key_here")
    
    # Use any method
    result = firecrawl.scrape("https://example.com")

FirecrawlRequest Class
~~~~~~~~~~~~~~~~~~~~~~

For distributed processing or when you need to separate request creation from execution:

.. code-block:: python

    from edsl.scenarios.firecrawl_scenario import FirecrawlRequest, FirecrawlScenario
    
    # Create request without executing (useful for distributed systems)
    request = FirecrawlRequest(api_key="your_key")
    request_dict = request.scrape("https://example.com")
    
    # Execute the request later (potentially on a different machine)
    result = FirecrawlScenario.from_request(request_dict)

Detailed Method Documentation
-----------------------------

Scraping Methods
~~~~~~~~~~~~~~~~

**scrape_url(url_or_urls, max_concurrent=10, \\*\\*kwargs)**

Scrape content from one or more URLs.

Parameters:
    - ``url_or_urls``: Single URL string or list of URLs
    - ``max_concurrent``: Maximum concurrent requests for batch processing (default: 10)
    - ``formats``: List of output formats (default: ["markdown"])
    - ``only_main_content``: Extract only main content, skip navigation/ads (default: True)
    - ``include_tags``: HTML tags to specifically include
    - ``exclude_tags``: HTML tags to exclude
    - ``headers``: Custom HTTP headers as dictionary
    - ``wait_for``: Time to wait before scraping (milliseconds)
    - ``timeout``: Request timeout (milliseconds)
    - ``actions``: Browser actions to perform before scraping

Returns:
    - Single URL: Scenario object with scraped content
    - Multiple URLs: ScenarioList with Scenario objects

**crawl_website(url, \\*\\*kwargs)**

Crawl an entire website and extract content from all discovered pages.

Parameters:
    - ``url``: Base URL to start crawling from
    - ``limit``: Maximum number of pages to crawl
    - ``max_depth``: Maximum crawl depth from starting URL
    - ``include_paths``: URL path patterns to include (supports wildcards)
    - ``exclude_paths``: URL path patterns to exclude
    - ``formats``: Output formats for each page (default: ["markdown"])
    - ``only_main_content``: Extract only main content (default: True)

Returns:
    ScenarioList containing Scenario objects for each crawled page

Search Methods
~~~~~~~~~~~~~~

**search_web(query_or_queries, max_concurrent=5, \\*\\*kwargs)**

Search the web and extract content from results.

Parameters:
    - ``query_or_queries``: Single search query or list of queries
    - ``max_concurrent``: Maximum concurrent requests for batch processing (default: 5)
    - ``limit``: Maximum number of search results per query
    - ``sources``: Sources to search (e.g., ["web", "news", "images"])
    - ``location``: Geographic location for localized results
    - ``formats``: Output formats for scraped content from results

Returns:
    ScenarioList containing Scenario objects for each search result

**map_website_urls(url, \\*\\*kwargs)**

Discover and map all URLs from a website without scraping content (fast URL discovery).

Parameters:
    - ``url``: Base URL to discover links from
    - Additional mapping parameters via kwargs

Returns:
    ScenarioList containing Scenario objects for each discovered URL

Extraction Methods
~~~~~~~~~~~~~~~~~~

**extract_data(url_or_urls, schema=None, prompt=None, \\*\\*kwargs)**

Extract structured data from web pages using AI-powered analysis.

Parameters:
    - ``url_or_urls``: Single URL string or list of URLs
    - ``schema``: JSON schema defining data structure to extract
    - ``prompt``: Natural language description of what to extract
    - ``max_concurrent``: Maximum concurrent requests for batch processing (default: 5)
    - ``formats``: Output formats for scraped content before extraction

Returns:
    - Single URL: Scenario object with extracted structured data
    - Multiple URLs: ScenarioList with Scenario objects

Note: Either ``schema`` or ``prompt`` should be provided. Schema takes precedence if both are given.

Working with Results
--------------------

Scenario Fields
~~~~~~~~~~~~~~~

All methods return Scenario or ScenarioList objects with standardized fields:

**Common fields for all methods:**
    - ``url``: The scraped/crawled/searched URL
    - ``title``: Page title (when available)
    - ``description``: Page description (when available)
    - ``content``: Primary content (usually markdown format)
    - ``status_code``: HTTP status code (when available)

**Scraping-specific fields:**
    - ``scrape_status``: "success" or "error"
    - ``markdown``: Markdown content
    - ``html``: HTML content (if requested)
    - ``links``: Extracted links (if requested)
    - ``screenshot``: Screenshot data (if requested)
    - ``metadata``: Full page metadata

**Search-specific fields:**
    - ``search_query``: The original search query
    - ``search_status``: "success" or "error"
    - ``result_type``: "web", "news", or "image"
    - ``position``: Result position in search results

**Extraction-specific fields:**
    - ``extract_status``: "success" or "error"
    - ``extracted_data``: The structured data extracted by AI
    - ``extraction_prompt``: The prompt used (if any)
    - ``extraction_schema``: The schema used (if any)

**Crawl-specific fields:**
    - ``crawl_status``: "success" or "error"

**URL mapping fields:**
    - ``discovered_url``: The discovered URL
    - ``source_url``: The URL it was discovered from
    - ``map_status``: "success" or "error"

Advanced Usage
--------------

Concurrent Processing
~~~~~~~~~~~~~~~~~~~~~

All batch methods support concurrent processing to speed up large operations:

.. code-block:: python

    # Scrape 100 URLs with 20 concurrent requests
    results = scrape_url(urls, max_concurrent=20)
    
    # Search multiple queries concurrently
    queries = ["AI research", "machine learning", "data science"]
    results = search_web(queries, max_concurrent=3)

Custom Formats and Options
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Specify different output formats and extraction options:

.. code-block:: python

    # Get both markdown and HTML content
    result = scrape_url(
        "https://example.com",
        formats=["markdown", "html"],
        only_main_content=False,
        include_tags=["article", "main"],
        exclude_tags=["nav", "footer"]
    )
    
    # Access different formats
    print(result["markdown"])  # Markdown content
    print(result["html"])      # HTML content

Complex Crawling Scenarios
~~~~~~~~~~~~~~~~~~~~~~~~~~

Advanced crawling with path filtering:

.. code-block:: python

    # Crawl documentation site with specific constraints
    results = crawl_website(
        "https://docs.example.com",
        limit=100,
        max_depth=3,
        include_paths=["/docs/*", "/api/*", "/tutorials/*"],
        exclude_paths=["/docs/deprecated/*", "/docs/v1/*"],
        formats=["markdown", "html"]
    )
    
    # Filter results by content type
    api_docs = [r for r in results if "/api/" in r["url"]]
    tutorials = [r for r in results if "/tutorials/" in r["url"]]

Schema-Based vs Prompt-Based Extraction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Using JSON schemas for structured extraction:**

.. code-block:: python

    # Define precise data structure
    product_schema = {
        "name": "string",
        "price": "number",
        "rating": "number",
        "availability": "boolean",
        "features": ["string"],
        "specifications": {
            "dimensions": "string",
            "weight": "string",
            "color": "string"
        }
    }
    
    result = extract_data("https://shop.example.com/product", schema=product_schema)
    product_data = result["extracted_data"]

**Using natural language prompts:**

.. code-block:: python

    # Extract with natural language
    result = extract_data(
        "https://news.example.com/article",
        prompt="Extract the article headline, author name, publication date, and key topics discussed"
    )
    
    article_data = result["extracted_data"]
    print(f"Headline: {article_data['headline']}")
    print(f"Author: {article_data['author']}")

Error Handling
--------------

The integration handles errors gracefully by returning Scenario objects with error information:

.. code-block:: python

    results = scrape_url(["https://valid-url.com", "https://invalid-url.com"])
    
    for result in results:
        if result.get("scrape_status") == "error":
            print(f"Error scraping {result['url']}: {result['error']}")
        else:
            print(f"Successfully scraped {result['url']}")

Integration with EDSL Workflows
--------------------------------

The firecrawl integration seamlessly integrates with other EDSL components:

Using with Surveys
~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from edsl import QuestionFreeText, Survey
    from edsl.scenarios.firecrawl_scenario import scrape_url
    
    # Scrape content to create scenarios
    scenarios = scrape_url([
        "https://news1.com/article1",
        "https://news2.com/article2"
    ])
    
    # Create survey questions about the content
    q1 = QuestionFreeText(
        question_name="summary",
        question_text="Summarize the main points of this article: {{ content }}"
    )
    
    q2 = QuestionFreeText(
        question_name="sentiment",
        question_text="What is the overall sentiment of this article?"
    )
    
    survey = Survey(questions=[q1, q2])
    
    # Run survey with scraped content as scenarios
    results = survey.by(scenarios).run()

Content Analysis Pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from edsl.scenarios.firecrawl_scenario import search_web, extract_data
    
    # 1. Search for relevant content
    search_results = search_web("climate change research 2024", limit=10)
    
    # 2. Extract structured data from search results
    extraction_schema = {
        "findings": "string",
        "methodology": "string", 
        "publication_date": "string",
        "authors": ["string"]
    }
    
    urls = [result["url"] for result in search_results if result["search_status"] == "success"]
    extracted_data = extract_data(urls, schema=extraction_schema)
    
    # 3. Use in EDSL survey for analysis
    survey = Survey([
        QuestionFreeText(
            question_name="significance",
            question_text="Rate the significance of these findings: {{ extracted_data }}"
        )
    ])
    
    analysis_results = survey.by(extracted_data).run()

Distributed Processing
----------------------

For large-scale operations, use the request/response pattern for distributed processing:

.. code-block:: python

    from edsl.scenarios.firecrawl_scenario import (
        create_scrape_request, 
        create_search_request,
        execute_request
    )
    
    # Create serializable requests (can be sent to workers, APIs, etc.)
    requests = [
        create_scrape_request("https://example1.com"),
        create_scrape_request("https://example2.com"),
        create_search_request("machine learning tutorials")
    ]
    
    # Execute requests (potentially on different machines/processes)
    results = []
    for request in requests:
        result = execute_request(request)
        results.append(result)

Best Practices
--------------

Performance Optimization
~~~~~~~~~~~~~~~~~~~~~~~~

1. **Use appropriate concurrency limits** - Start with defaults and adjust based on your needs and rate limits
2. **Filter early** - Use include/exclude paths in crawling to avoid unnecessary requests
3. **Choose optimal formats** - Only request formats you actually need
4. **Batch operations** - Process multiple URLs/queries together when possible

Rate Limiting
~~~~~~~~~~~~~

1. **Respect rate limits** - Firecrawl has rate limits based on your plan
2. **Adjust concurrency** - Lower max_concurrent values if you hit rate limits
3. **Monitor costs** - Each request consumes Firecrawl credits

Content Quality
~~~~~~~~~~~~~~~

1. **Use only_main_content=True** - Filters out navigation, ads, and other noise
2. **Specify include/exclude tags** - Fine-tune content extraction
3. **Choose appropriate formats** - Markdown for text analysis, HTML for detailed parsing

Error Resilience
~~~~~~~~~~~~~~~~

1. **Check status fields** - Always check scrape_status, search_status, etc.
2. **Handle partial failures** - Some URLs in a batch may fail while others succeed
3. **Implement retries** - For critical operations, implement retry logic for failed requests

Cost Management
~~~~~~~~~~~~~~~

1. **Use URL mapping first** - Discover URLs with map_website_urls before full crawling
2. **Set reasonable limits** - Use limit and max_depth parameters to control crawl scope
3. **Cache results** - Store results locally to avoid re-scraping the same content

Troubleshooting
---------------

Common Issues
~~~~~~~~~~~~~

**"FIRECRAWL_API_KEY not found" error:**
    - Ensure your API key is set as an environment variable or in a .env file
    - Verify the key is valid and active at https://firecrawl.dev

**Rate limit errors:**
    - Reduce max_concurrent parameter
    - Check your Firecrawl plan limits
    - Implement delays between requests if needed

**Empty or poor quality content:**
    - Try only_main_content=False for more content
    - Adjust include_tags/exclude_tags parameters
    - Some sites may have anti-scraping measures

**Slow performance:**
    - Increase max_concurrent for batch operations
    - Use URL mapping to discover URLs faster than full crawling
    - Consider using search instead of crawling for content discovery

**Memory usage with large crawls:**
    - Use limit parameter to control crawl size
    - Process results in batches rather than storing everything in memory
    - Consider using the request/response pattern for distributed processing

Getting Help
~~~~~~~~~~~~

- Check the `Firecrawl documentation <https://docs.firecrawl.dev>`_ for API-specific issues
- Review EDSL documentation for Scenario and ScenarioList usage
- Ensure your firecrawl-py package is up to date: ``pip install --upgrade firecrawl-py``

API Reference
-------------

Convenience Functions
~~~~~~~~~~~~~~~~~~~~~

.. autofunction:: edsl.scenarios.firecrawl_scenario.scrape_url
.. autofunction:: edsl.scenarios.firecrawl_scenario.crawl_website
.. autofunction:: edsl.scenarios.firecrawl_scenario.search_web
.. autofunction:: edsl.scenarios.firecrawl_scenario.map_website_urls
.. autofunction:: edsl.scenarios.firecrawl_scenario.extract_data

Classes
~~~~~~~

.. autoclass:: edsl.scenarios.firecrawl_scenario.FirecrawlScenario
   :members:

.. autoclass:: edsl.scenarios.firecrawl_scenario.FirecrawlRequest
   :members:

Request Creation Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autofunction:: edsl.scenarios.firecrawl_scenario.create_scrape_request
.. autofunction:: edsl.scenarios.firecrawl_scenario.create_search_request
.. autofunction:: edsl.scenarios.firecrawl_scenario.create_extract_request
.. autofunction:: edsl.scenarios.firecrawl_scenario.create_crawl_request
.. autofunction:: edsl.scenarios.firecrawl_scenario.create_map_request
.. autofunction:: edsl.scenarios.firecrawl_scenario.execute_request