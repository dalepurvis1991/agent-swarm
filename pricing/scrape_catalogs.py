"""Price hunting and catalog scraping for supplier prefiltering.

This module scrapes various sources to find list prices for products,
allowing the quote agent to prioritize the cheapest suppliers.
"""

import logging
import re
import requests
from typing import List, Tuple, Optional, Dict, Any
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import json
import time

logger = logging.getLogger(__name__)


class PriceResult:
    """Represents a price result from catalog scraping."""
    
    def __init__(self, supplier: str, url: str, list_price: float, currency: str = "USD", title: str = ""):
        self.supplier = supplier
        self.url = url
        self.list_price = list_price
        self.currency = currency
        self.title = title
    
    def __repr__(self):
        return f"PriceResult(supplier='{self.supplier}', price={self.list_price} {self.currency})"


class CatalogScraper:
    """Main catalog scraper that coordinates multiple data sources."""
    
    def __init__(self, serpapi_key: Optional[str] = None):
        """Initialize the scraper with optional SerpAPI key."""
        self.serpapi_key = serpapi_key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def scrape_catalogs(self, specification: str, max_results: int = 10) -> List[PriceResult]:
        """
        Scrape multiple sources for price information.
        
        Args:
            specification: Product specification to search for
            max_results: Maximum number of results to return
            
        Returns:
            List of PriceResult objects sorted by price ascending
        """
        all_results = []
        
        try:
            # 1. SerpAPI Shopping (if API key available)
            if self.serpapi_key:
                serp_results = self._scrape_serpapi_shopping(specification)
                all_results.extend(serp_results)
                logger.info(f"Found {len(serp_results)} results from SerpAPI")
            
            # 2. Static retailer scrapers
            retailer_results = self._scrape_static_retailers(specification)
            all_results.extend(retailer_results)
            logger.info(f"Found {len(retailer_results)} results from static retailers")
            
            # 3. Sort by price and return top results
            sorted_results = sorted(all_results, key=lambda x: x.list_price)
            final_results = sorted_results[:max_results]
            
            logger.info(f"Returning {len(final_results)} price results for '{specification}'")
            return final_results
            
        except Exception as e:
            logger.error(f"Error scraping catalogs: {e}")
            return []
    
    def _scrape_serpapi_shopping(self, specification: str) -> List[PriceResult]:
        """Scrape Google Shopping via SerpAPI."""
        if not self.serpapi_key:
            return []
        
        try:
            params = {
                'engine': 'google_shopping',
                'q': specification,
                'api_key': self.serpapi_key,
                'num': 20,
                'hl': 'en',
                'gl': 'us'
            }
            
            response = requests.get('https://serpapi.com/search', params=params)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get('shopping_results', []):
                try:
                    # Extract price
                    price_str = item.get('price', '').replace('$', '').replace(',', '')
                    if not price_str:
                        continue
                    
                    price = float(re.findall(r'\d+\.?\d*', price_str)[0])
                    
                    result = PriceResult(
                        supplier=item.get('source', 'Unknown'),
                        url=item.get('link', ''),
                        list_price=price,
                        currency='USD',
                        title=item.get('title', '')
                    )
                    results.append(result)
                    
                except (ValueError, IndexError, TypeError) as e:
                    logger.warning(f"Failed to parse SerpAPI result: {e}")
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"SerpAPI scraping failed: {e}")
            return []
    
    def _scrape_static_retailers(self, specification: str) -> List[PriceResult]:
        """Scrape static retailer websites."""
        results = []
        
        # Retailer 1: 4imprint (promotional products)
        imprint_results = self._scrape_4imprint(specification)
        results.extend(imprint_results)
        
        # Retailer 2: Custom Ink (custom apparel/bags)
        customink_results = self._scrape_customink(specification)
        results.extend(customink_results)
        
        return results
    
    def _scrape_4imprint(self, specification: str) -> List[PriceResult]:
        """Scrape 4imprint.com for promotional products."""
        try:
            # Search 4imprint
            search_url = f"https://www.4imprint.com/search?qrs={specification.replace(' ', '+')}"
            
            response = self.session.get(search_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            results = []
            
            # Find product containers (these selectors may need updating)
            products = soup.find_all('div', class_=re.compile(r'product|item'))[:5]  # Limit to first 5
            
            for product in products:
                try:
                    # Extract title
                    title_elem = product.find(['h2', 'h3', 'a'], class_=re.compile(r'title|name'))
                    title = title_elem.get_text(strip=True) if title_elem else "4imprint Product"
                    
                    # Extract price
                    price_elem = product.find(['span', 'div'], class_=re.compile(r'price|cost'))
                    if not price_elem:
                        continue
                    
                    price_text = price_elem.get_text(strip=True)
                    price_match = re.search(r'\$?(\d+\.?\d*)', price_text)
                    if not price_match:
                        continue
                    
                    price = float(price_match.group(1))
                    
                    # Extract link
                    link_elem = product.find('a', href=True)
                    url = urljoin(search_url, link_elem['href']) if link_elem else search_url
                    
                    result = PriceResult(
                        supplier="4imprint",
                        url=url,
                        list_price=price,
                        currency="USD",
                        title=title
                    )
                    results.append(result)
                    
                except Exception as e:
                    logger.warning(f"Failed to parse 4imprint product: {e}")
                    continue
            
            logger.info(f"Scraped {len(results)} results from 4imprint")
            return results
            
        except Exception as e:
            logger.error(f"4imprint scraping failed: {e}")
            return []
    
    def _scrape_customink(self, specification: str) -> List[PriceResult]:
        """Scrape CustomInk for custom products."""
        try:
            # Note: CustomInk might require more complex interaction
            # This is a simplified version that looks for basic product info
            
            search_url = f"https://www.customink.com/search?q={specification.replace(' ', '+')}"
            
            response = self.session.get(search_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            results = []
            
            # Find product containers (these selectors may need updating)
            products = soup.find_all('div', class_=re.compile(r'product|item|card'))[:5]  # Limit to first 5
            
            for product in products:
                try:
                    # Extract title
                    title_elem = product.find(['h2', 'h3', 'h4', 'a'], class_=re.compile(r'title|name'))
                    title = title_elem.get_text(strip=True) if title_elem else "CustomInk Product"
                    
                    # Extract price (might be "starting at" price)
                    price_elem = product.find(['span', 'div'], string=re.compile(r'\$\d+'))
                    if not price_elem:
                        # Try finding any element with price pattern
                        price_elem = product.find(string=re.compile(r'\$\d+\.?\d*'))
                    
                    if not price_elem:
                        continue
                    
                    price_text = str(price_elem)
                    price_match = re.search(r'\$(\d+\.?\d*)', price_text)
                    if not price_match:
                        continue
                    
                    price = float(price_match.group(1))
                    
                    # Extract link
                    link_elem = product.find('a', href=True)
                    url = urljoin(search_url, link_elem['href']) if link_elem else search_url
                    
                    result = PriceResult(
                        supplier="CustomInk",
                        url=url,
                        list_price=price,
                        currency="USD",
                        title=title
                    )
                    results.append(result)
                    
                except Exception as e:
                    logger.warning(f"Failed to parse CustomInk product: {e}")
                    continue
            
            logger.info(f"Scraped {len(results)} results from CustomInk")
            return results
            
        except Exception as e:
            logger.error(f"CustomInk scraping failed: {e}")
            return []


def scrape_catalogs(specification: str, max_results: int = 3, serpapi_key: Optional[str] = None) -> List[Tuple[str, str, float]]:
    """
    Main function to scrape catalogs and return cheapest suppliers.
    
    Args:
        specification: Product specification to search for
        max_results: Maximum number of results to return (default 3)
        serpapi_key: Optional SerpAPI key for Google Shopping
        
    Returns:
        List of tuples (supplier, url, list_price) sorted by price ascending
    """
    scraper = CatalogScraper(serpapi_key=serpapi_key)
    results = scraper.scrape_catalogs(specification, max_results=max_results)
    
    # Convert to tuple format as specified
    return [(r.supplier, r.url, r.list_price) for r in results]


# Convenience function for testing
def get_mock_results(specification: str) -> List[Tuple[str, str, float]]:
    """Get mock price results for testing without hitting real APIs."""
    mock_data = [
        ("4imprint", "https://www.4imprint.com/product/tote-bag-1", 5.99),
        ("CustomInk", "https://www.customink.com/products/tote-eco", 7.50),
        ("Alibaba", "https://alibaba.com/product/eco-tote", 3.25),
        ("DHgate", "https://dhgate.com/wholesale/tote", 2.80),
        ("Amazon Business", "https://amazon.com/b2b/tote-bags", 8.99),
    ]
    
    # Filter based on specification keywords
    spec_lower = specification.lower()
    relevant_results = []
    
    for supplier, url, price in mock_data:
        if any(keyword in spec_lower for keyword in ['tote', 'bag', 'eco', 'promotional']):
            relevant_results.append((supplier, url, price))
    
    # Sort by price and return top 3
    sorted_results = sorted(relevant_results, key=lambda x: x[2])
    return sorted_results[:3]


if __name__ == "__main__":
    # Test the scraper
    results = scrape_catalogs("eco tote bags", max_results=5)
    print(f"Found {len(results)} price results:")
    for supplier, url, price in results:
        print(f"  {supplier}: ${price:.2f} - {url}") 