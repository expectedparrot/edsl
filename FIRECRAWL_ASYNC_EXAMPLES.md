# FirecrawlScenario: Async Batch Processing

The FirecrawlScenario class now supports async batch processing for efficient concurrent operations on multiple URLs or search queries.

## 🚀 Key Benefits

- **Concurrent Processing**: Process multiple URLs/queries simultaneously
- **Configurable Concurrency**: Control the number of simultaneous requests
- **Error Handling**: Individual failures don't stop the entire batch
- **Performance**: Significant speedup for larger batches

## 📖 Usage Examples

### 1. Batch Scraping URLs

```python
import asyncio
from edsl.scenarios.firecrawl_scenario import scrape_urls_batch

async def scrape_multiple_sites():
    urls = [
        'https://www.cnn.com',
        'https://www.bbc.com', 
        'https://www.reuters.com',
        'https://www.npr.org'
    ]
    
    # Scrape all URLs concurrently (max 3 at once)
    results = await scrape_urls_batch(urls, max_concurrent=3)
    
    for result in results:
        print(f"URL: {result.get('url')}")
        print(f"Status: {result.get('scrape_status')}")
        print(f"Title: {result.get('title', 'No title')}")
        print(f"Content length: {len(result.get('content', ''))}")
        print("---")

# Run the async function
asyncio.run(scrape_multiple_sites())
```

### 2. Batch Search Queries

```python
import asyncio
from edsl.scenarios.firecrawl_scenario import search_queries_batch

async def search_multiple_topics():
    queries = [
        'python web scraping',
        'machine learning tutorials',
        'data science tools',
        'AI research papers'
    ]
    
    # Search all queries concurrently
    results = await search_queries_batch(queries, limit=3, max_concurrent=2)
    
    print(f"Total search results: {len(results)}")
    
    for result in results:
        print(f"Query: {result.get('search_query')}")
        print(f"Title: {result.get('title')}")
        print(f"URL: {result.get('url')}")
        print("---")

asyncio.run(search_multiple_topics())
```

### 3. Batch Data Extraction

```python
import asyncio
from edsl.scenarios.firecrawl_scenario import extract_data_batch

async def extract_from_multiple_urls():
    urls = [
        'https://company1.com/about',
        'https://company2.com/about', 
        'https://company3.com/about'
    ]
    
    prompt = "Extract the company name, description, and founding year"
    
    # Extract data from all URLs concurrently
    results = await extract_data_batch(
        urls, 
        prompt=prompt, 
        max_concurrent=2
    )
    
    for result in results:
        print(f"URL: {result.get('url')}")
        print(f"Status: {result.get('extract_status')}")
        print(f"Extracted: {result.get('extracted_data')}")
        print("---")

asyncio.run(extract_from_multiple_urls())
```

## ⚙️ Method Reference

### Class Methods

```python
from edsl.scenarios.firecrawl_scenario import FirecrawlScenario

firecrawl = FirecrawlScenario()

# Async batch methods
await firecrawl.scrape_batch(urls, max_concurrent=5, **kwargs)
await firecrawl.search_batch(queries, max_concurrent=3, **kwargs) 
await firecrawl.extract_batch(urls, prompt=None, schema=None, max_concurrent=3, **kwargs)
```

### Convenience Functions

```python
from edsl.scenarios.firecrawl_scenario import (
    scrape_urls_batch,
    search_queries_batch, 
    extract_data_batch
)

# Direct async functions
results = await scrape_urls_batch(urls, max_concurrent=5)
results = await search_queries_batch(queries, max_concurrent=3)
results = await extract_data_batch(urls, prompt="...", max_concurrent=3)
```

## 🎯 Performance Tips

1. **Optimal Concurrency**: Start with `max_concurrent=3-5` for most use cases
2. **Rate Limiting**: Respect API rate limits by adjusting concurrency
3. **Error Handling**: Check individual result status for failed requests
4. **Batch Size**: Process 10-50 URLs per batch for best performance
5. **Memory Usage**: Large batches consume more memory

## 📊 Performance Comparison

```python
import asyncio
import time
from edsl.scenarios.firecrawl_scenario import scrape_url, scrape_urls_batch

async def performance_test():
    urls = ['https://example.com'] * 8  # 8 identical URLs
    
    # Serial processing
    start = time.time()
    serial_results = [scrape_url(url) for url in urls]
    serial_time = time.time() - start
    
    # Async batch processing  
    start = time.time()
    async_results = await scrape_urls_batch(urls, max_concurrent=4)
    async_time = time.time() - start
    
    print(f"Serial: {serial_time:.2f}s")
    print(f"Async:  {async_time:.2f}s") 
    print(f"Speedup: {serial_time/async_time:.2f}x")

asyncio.run(performance_test())
```

## 🔧 Error Handling

Individual failures don't stop the batch. Check each result:

```python
results = await scrape_urls_batch(urls)

for result in results:
    if result.get('scrape_status') == 'success':
        # Process successful result
        content = result.get('content', '')
    else:
        # Handle error
        error = result.get('error', 'Unknown error')
        url = result.get('url', 'Unknown URL')
        print(f"Failed to scrape {url}: {error}")
```
