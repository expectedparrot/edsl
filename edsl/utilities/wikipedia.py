import asyncio
import aiohttp
import time
import re
from typing import List

def clean_text(text):
    """Clean text by jinja2 braces
    If the text contains {{ or }} then replace it with the empty string
    """
    return re.sub(r'({{.*?}})', '', text)


async def fetch_wikipedia_content_async(search_terms: List[str], concurrency_limit=20):
    """
    Asynchronously fetch Wikipedia content for multiple search terms.
    
    Args:
        search_terms (list): List of search terms to look up on Wikipedia
        concurrency_limit (int): Maximum number of concurrent requests
        
    Returns:
        list: List of dictionaries containing search results
    """
    async def fetch_wiki_search(session, search_term):
        """Search for a Wikipedia page"""
        search_url = "https://en.wikipedia.org/w/api.php"
        search_params = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": search_term,
            "utf8": "1"
        }
        
        async with session.get(search_url, params=search_params) as response:
            search_data = await response.json()
            
            if "query" in search_data and search_data["query"]["search"]:
                return {
                    "search_term": search_term,
                    "title": search_data["query"]["search"][0]["title"],
                    "found": True
                }
            else:
                return {
                    "search_term": search_term,
                    "found": False
                }

    async def fetch_wiki_content(session, page_title):
        """Fetch content of a Wikipedia page"""
        content_url = "https://en.wikipedia.org/w/api.php"
        content_params = {
            "action": "query",
            "format": "json",
            "titles": page_title,
            "prop": "extracts|pageimages|categories|links|info",
            "explaintext": "1",
            "exsectionformat": "plain",
            "inprop": "url",
            "pithumbsize": "100",   # Get a small thumbnail if available
            "cllimit": "20",        # Limit to 20 categories
            "plimit": "20",         # Limit to 20 links
            "redirects": "1"        # Follow redirects
        }
        
        async with session.get(content_url, params=content_params) as response:
            content_data = await response.json()
            page_id = list(content_data["query"]["pages"].keys())[0]
            
            if page_id != "-1":  # -1 indicates page not found
                page_data = content_data["query"]["pages"][page_id]
                
                result = {
                    "title": page_data.get("title", ""),
                    "page_id": page_id,
                    "content": clean_text(page_data.get("extract", "")),
                    "url": page_data.get("fullurl", ""),
                    "last_modified": page_data.get("touched", "")
                }
                
                # Add categories if available
                if "categories" in page_data:
                    result["categories"] = [cat["title"].replace("Category:", "") 
                                          for cat in page_data["categories"]]
                
                # Add links if available
                if "links" in page_data:
                    result["links"] = [link["title"] for link in page_data["links"]]
                
                # Add thumbnail if available
                if "thumbnail" in page_data:
                    result["thumbnail"] = page_data["thumbnail"].get("source", "")
                
                return result
            else:
                return {
                    "title": page_title,
                    "error": "Page not found"
                }

    async def process_wiki_item(session, search_term):
        """Process a single search term to get Wikipedia content"""
        search_result = await fetch_wiki_search(session, search_term)
        
        if search_result["found"]:
            content_result = await fetch_wiki_content(session, search_result["title"])
            
            # Create a complete result
            result = {
                "search_term": search_term,
                "status": "Success",
                **content_result
            }
            
            return result
        else:
            return {
                "search_term": search_term,
                "status": "Not found"
            }

    start_time = time.time()
    
    # Create a ClientSession that will be used for all requests
    async with aiohttp.ClientSession(
        headers={"User-Agent": "WikiBatchFetcher/1.0 (your@email.com)"}
    ) as session:
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(concurrency_limit)
        
        async def bounded_process(search_term):
            async with semaphore:
                return await process_wiki_item(session, search_term)
        
        # Create tasks for all search terms
        tasks = [bounded_process(term) for term in search_terms]
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks)
    
    end_time = time.time()
    
    # Log summary statistics
    success_count = sum(1 for r in results if r.get("status") == "Success")
    #print(f"Processed {len(search_terms)} search terms in {end_time - start_time:.2f} seconds")
    #print(f"Successfully retrieved {success_count} pages")
    
    return results

def fetch_wikipedia_content(search_terms, concurrency_limit=20):
    """
    Synchronous wrapper for the async function to fetch Wikipedia content
    
    Args:
        search_terms (list): List of search terms to look up on Wikipedia
        concurrency_limit (int): Maximum number of concurrent requests
        
    Returns:
        list: List of dictionaries containing search results
    """
    return asyncio.run(
        fetch_wikipedia_content_async(
            search_terms=search_terms, 
            concurrency_limit=concurrency_limit
        )
    )

# Example usage
if __name__ == "__main__":
    # Example search terms
    search_terms = [
        "Tommy Tuberville",
        "Albert Einstein",
        "Marie Curie"
    ]
    
    # Call the function
    results = fetch_wikipedia_content(
        search_terms=search_terms,
        concurrency_limit=20
    )
    
    # Print a sample of the results
    for result in results:
        print(f"\nSearch term: {result['search_term']}")
        print(f"Status: {result['status']}")
        if result['status'] == 'Success':
            print(f"Title: {result['title']}")
            print(f"URL: {result['url']}")
            print(f"Content length: {len(result['content'])} characters")
            if 'categories' in result:
                print(f"Categories: {', '.join(result['categories'][:3])}...")