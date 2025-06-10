import os
import logging
import json
from typing import List, Dict, Any
import httpx
import anyio
from bs4 import BeautifulSoup
import re

SERP_KEY = os.getenv("SERPAPI_KEY")
SEARCH_URL = "https://serpapi.com/search.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SupplierSearchError(RuntimeError):
    """Exception raised when supplier search fails."""
    pass


async def _serpapi(query: str, k: int) -> List[Dict[str, Any]]:
    """Search suppliers using SerpAPI."""
    params = {
        "q": f"{query} suppliers wholesale",
        "api_key": SERP_KEY,
        "engine": "google",
        "num": min(k, 10)  # SerpAPI typically returns up to 10 results
    }
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(SEARCH_URL, params=params)
        
        if response.status_code != 200:
            raise SupplierSearchError(f"SerpAPI returned {response.status_code}")
        
        data = response.json()
        
        # Extract organic results
        organic_results = data.get("organic_results", [])
        suppliers = []
        
        for result in organic_results[:k]:
            supplier = {
                "name": result.get("title", "Unknown Supplier"),
                "url": result.get("link", ""),
                "description": result.get("snippet", ""),
                "source": "serpapi"
            }
            suppliers.append(supplier)
        
        logger.info(f"Found {len(suppliers)} suppliers via SerpAPI for query: {query}")
        return suppliers
        
    except httpx.TimeoutException:
        raise SupplierSearchError("SerpAPI request timed out")
    except Exception as e:
        if isinstance(e, SupplierSearchError):
            raise
        raise SupplierSearchError(f"SerpAPI error: {str(e)}")


async def _fallback_search(query: str, k: int) -> List[Dict[str, Any]]:
    """Fallback search using direct Google search scraping."""
    search_query = f"{query} suppliers wholesale"
    google_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        async with httpx.AsyncClient(timeout=10, headers=headers) as client:
            response = await client.get(google_url)
        
        if response.status_code != 200:
            raise SupplierSearchError(f"Google search returned {response.status_code}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        suppliers = []
        
        # Find search result divs (Google's structure may change)
        result_divs = soup.find_all('div', class_=['g', 'tF2Cxc'])[:k]
        
        for div in result_divs:
            # Extract title and URL
            title_elem = div.find('h3')
            link_elem = div.find('a')
            snippet_elem = div.find('span', class_=['st', 'aCOpRe'])
            
            if title_elem and link_elem:
                # Clean URL (remove Google redirect)
                url = link_elem.get('href', '')
                if url.startswith('/url?q='):
                    url = url.split('/url?q=')[1].split('&')[0]
                
                supplier = {
                    "name": title_elem.get_text(strip=True),
                    "url": url,
                    "description": snippet_elem.get_text(strip=True) if snippet_elem else "",
                    "source": "fallback"
                }
                suppliers.append(supplier)
        
        logger.info(f"Found {len(suppliers)} suppliers via fallback search for query: {query}")
        return suppliers
        
    except Exception as e:
        if isinstance(e, SupplierSearchError):
            raise
        raise SupplierSearchError(f"Fallback search error: {str(e)}")


async def find_suppliers_async(query: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Async version of find_suppliers for use within async contexts.
    
    Args:
        query: Search query for suppliers
        k: Maximum number of suppliers to return (default: 5)
    
    Returns:
        List of supplier dictionaries with keys: name, url, description, source
    
    Raises:
        SupplierSearchError: If search fails
    """
    if not query or not query.strip():
        raise SupplierSearchError("Query cannot be empty")
    
    # Check API key availability at runtime to support environment variable mocking
    current_api_key = os.getenv("SERPAPI_KEY")
    
    try:
        if current_api_key:
            logger.info(f"Using SerpAPI for query: {query}")
            return await _serpapi(query.strip(), k)
        else:
            logger.info(f"Using fallback search for query: {query}")
            return await _fallback_search(query.strip(), k)
    except Exception as e:
        logger.error(f"Supplier search failed for query '{query}': {str(e)}")
        # Re-raise the specific error instead of wrapping it
        raise


def find_suppliers(query: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Find suppliers for a given query (sync version).
    
    Args:
        query: Search query for suppliers
        k: Maximum number of suppliers to return (default: 5)
    
    Returns:
        List of supplier dictionaries with keys: name, url, description, source
    
    Raises:
        SupplierSearchError: If search fails
    """
    if not query or not query.strip():
        raise SupplierSearchError("Query cannot be empty")
    
    # Check API key availability at runtime to support environment variable mocking
    current_api_key = os.getenv("SERPAPI_KEY")
    
    try:
        if current_api_key:
            logger.info(f"Using SerpAPI for query: {query}")
            return anyio.run(_serpapi, query.strip(), k)
        else:
            logger.info(f"Using fallback search for query: {query}")
            return anyio.run(_fallback_search, query.strip(), k)
    except Exception as e:
        logger.error(f"Supplier search failed for query '{query}': {str(e)}")
        # Re-raise the specific error instead of wrapping it
        raise 