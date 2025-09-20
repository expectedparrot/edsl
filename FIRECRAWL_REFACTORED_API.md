# FirecrawlScenario: Smart Unified API

The FirecrawlScenario class has been refactored to provide a clean, intuitive API that automatically detects whether you're working with single items or batches.

## 🎯 Key Benefits

- **Smart Detection**: Automatically detects single vs batch operations
- **Unified Methods**: Same method name for single and batch operations
- **Consistent Returns**: Single items return `Scenario`, batches return `ScenarioList`
- **Async Under the Hood**: Batch operations use async for performance
- **Backward Compatible**: Legacy async functions still available

## 📖 New Unified API

### Scraping URLs

```python
from edsl.scenarios.firecrawl_scenario import FirecrawlScenario, scrape_url

firecrawl = FirecrawlScenario()

# Single URL - returns Scenario
result = firecrawl.scrape('https://www.cnn.com')
print(type(result))  # <class 'edsl.scenarios.scenario.Scenario'>

# Multiple URLs - returns ScenarioList  
urls = ['https://www.cnn.com', 'https://www.bbc.com', 'https://example.com']
results = firecrawl.scrape(urls, max_concurrent=3)
print(type(results))  # <class 'edsl.scenarios.scenario_list.ScenarioList'>

# Convenience function works the same way
single = scrape_url('https://example.com')
batch = scrape_url(['https://example.com', 'https://httpbin.org/html'])
```

### Searching the Web

```python
from edsl.scenarios.firecrawl_scenario import FirecrawlScenario, search_web

firecrawl = FirecrawlScenario()

# Single query - returns ScenarioList (search always returns multiple results)
results = firecrawl.search('python programming', limit=3)
print(type(results))  # <class 'edsl.scenarios.scenario_list.ScenarioList'>

# Multiple queries - returns combined ScenarioList
queries = ['python programming', 'machine learning', 'data science']
results = firecrawl.search(queries, limit=2, max_concurrent=2)
print(type(results))  # <class 'edsl.scenarios.scenario_list.ScenarioList'>

# Convenience function
results = search_web(['AI research', 'deep learning'], limit=1)
```

### Extracting Data

```python
from edsl.scenarios.firecrawl_scenario import FirecrawlScenario, extract_data

firecrawl = FirecrawlScenario()

# Single URL - returns Scenario
result = firecrawl.extract(
    'https://company.com/about', 
    prompt='Extract company name and description'
)
print(type(result))  # <class 'edsl.scenarios.scenario.Scenario'>

# Multiple URLs - returns ScenarioList
urls = [
    'https://company1.com/about',
    'https://company2.com/about', 
    'https://company3.com/about'
]
results = firecrawl.extract(
    urls,
    prompt='Extract company name and description',
    max_concurrent=2
)
print(type(results))  # <class 'edsl.scenarios.scenario_list.ScenarioList'>

# Convenience function
results = extract_data(urls, prompt='Extract key info')
```

## 🔧 Method Reference

### Class Methods

```python
from edsl.scenarios.firecrawl_scenario import FirecrawlScenario

firecrawl = FirecrawlScenario()

# Smart methods (detect single vs batch automatically)
firecrawl.scrape(url_or_urls, max_concurrent=5, **kwargs)
firecrawl.search(query_or_queries, max_concurrent=3, **kwargs)
firecrawl.extract(url_or_urls, prompt=None, schema=None, max_concurrent=3, **kwargs)

# Traditional methods (unchanged)
firecrawl.crawl(url, **kwargs)  # Always returns ScenarioList
firecrawl.map_urls(url, **kwargs)  # Always returns ScenarioList
```

### Convenience Functions

```python
from edsl.scenarios.firecrawl_scenario import (
    scrape_url,      # Single URL or list of URLs
    search_web,      # Single query or list of queries  
    extract_data,    # Single URL or list of URLs
    crawl_website,   # Single URL (unchanged)
    map_website_urls # Single URL (unchanged)
)

# All support both single and batch operations
scrape_url('https://example.com')  # Returns Scenario
scrape_url(['https://example.com', 'https://other.com'])  # Returns ScenarioList

search_web('python')  # Returns ScenarioList
search_web(['python', 'javascript'])  # Returns ScenarioList

extract_data('https://example.com', prompt='...')  # Returns Scenario
extract_data(['https://example.com', 'https://other.com'], prompt='...')  # Returns ScenarioList
```

## 📊 Return Types Summary

| Method | Single Input | Batch Input |
|--------|-------------|-------------|
| `scrape()` | `Scenario` | `ScenarioList` |
| `search()` | `ScenarioList` | `ScenarioList` |
| `extract()` | `Scenario` | `ScenarioList` |
| `crawl()` | `ScenarioList` | N/A |
| `map_urls()` | `ScenarioList` | N/A |

## 🚀 Performance Examples

```python
import time
from edsl.scenarios.firecrawl_scenario import scrape_url

# Performance comparison
urls = ['https://example.com'] * 5

# Serial processing (old way)
start = time.time()
results = [scrape_url(url) for url in urls]
serial_time = time.time() - start

# Batch processing (new way)
start = time.time()
results = scrape_url(urls, max_concurrent=3)
batch_time = time.time() - start

print(f"Serial: {serial_time:.2f}s")
print(f"Batch:  {batch_time:.2f}s")
print(f"Speedup: {serial_time/batch_time:.2f}x")
```

## 🔄 Migration Guide

### Old Way (Deprecated)
```python
# Old async batch functions
from edsl.scenarios.firecrawl_scenario import scrape_urls_batch
import asyncio

results = asyncio.run(scrape_urls_batch(urls, max_concurrent=3))
```

### New Way (Recommended)
```python
# New smart methods
from edsl.scenarios.firecrawl_scenario import scrape_url

results = scrape_url(urls, max_concurrent=3)  # Much simpler!
```

## ⚙️ Configuration

```python
firecrawl = FirecrawlScenario()

# Configure concurrency for batch operations
results = firecrawl.scrape(urls, max_concurrent=5)
results = firecrawl.search(queries, max_concurrent=3)
results = firecrawl.extract(urls, max_concurrent=2)

# All other parameters work the same
results = firecrawl.scrape(
    urls,
    formats=['markdown', 'html'],
    only_main_content=True,
    max_concurrent=4
)
```

## 🎉 Summary

The refactored API provides:
- **Simpler Code**: One method for single and batch operations
- **Better Performance**: Automatic async batch processing
- **Type Safety**: Predictable return types
- **Flexibility**: Configurable concurrency levels
- **Backward Compatibility**: Legacy functions still work

No more choosing between `scrape()` and `scrape_batch()` - just use `scrape()` with whatever you have!
