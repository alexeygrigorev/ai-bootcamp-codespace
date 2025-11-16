"""
Wikipedia API Tools

Tools for searching and retrieving Wikipedia content.
"""

import requests
from typing import List, Dict, Any


def search_wikipedia(query: str) -> List[Dict[str, Any]]:
    """
    Search Wikipedia for pages matching the query.
    
    Args:
        query: Search term (spaces will be converted to "+" for URL)
        
    Returns:
        List of search results, each containing:
        - title: Page title
        - snippet: Text snippet from the page
        - pageid: Wikipedia page ID
    """
    try:
        # Convert spaces to "+" for URL encoding
        search_term = query.replace(" ", "+")
        
        # Wikipedia API search endpoint
        url = f"https://en.wikipedia.org/w/api.php?action=query&format=json&list=search&srsearch={search_term}"
        
        # Add User-Agent header (best practice for Wikipedia API)
        headers = {
            'User-Agent': 'WikipediaAgent/1.0 (Educational Agent)'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        search_results = data.get('query', {}).get('search', [])
        
        # Format results
        results = []
        for item in search_results:
            results.append({
                "title": item.get('title', ''),
                "snippet": item.get('snippet', ''),
                "pageid": item.get('pageid', ''),
                "size": item.get('size', 0),
                "wordcount": item.get('wordcount', 0)
            })
        
        return results
    except Exception as e:
        return [{"error": f"Error searching Wikipedia: {str(e)}"}]


def get_wikipedia_page(title: str) -> str:
    """
    Get the raw content of a Wikipedia page.
    
    Args:
        title: Wikipedia page title (exact match - spaces are converted to underscores for URL)
        
    Returns:
        Raw page content in wikitext format, or error message if page not found
    """
    try:
        # Wikipedia expects underscores for spaces in URLs
        # Convert spaces to underscores (standard Wikipedia URL format)
        encoded_title = title.replace(" ", "_")
        
        # Wikipedia raw content endpoint
        # Format: https://en.wikipedia.org/w/index.php?title=PAGE_TITLE&action=raw
        url = f"https://en.wikipedia.org/w/index.php?title={encoded_title}&action=raw"
        
        # Add User-Agent header (best practice for Wikipedia API)
        headers = {
            'User-Agent': 'WikipediaAgent/1.0 (Educational Agent)'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        return response.text
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return f"Error: Wikipedia page '{title}' not found. Please verify the page title from search results."
        return f"Error fetching page '{title}': HTTP {e.response.status_code}"
    except Exception as e:
        return f"Error fetching page '{title}': {str(e)}"

