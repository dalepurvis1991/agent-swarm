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
import os
from serpapi import GoogleSearch
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Product:
    name: str
    price: float
    supplier: str
    url: str


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
    
    def __init__(self, serpapi_key: str):
        """Initialize the scraper with optional SerpAPI key."""
        self.serpapi_key = serpapi_key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def search_products(self, query: str) -> List[Product]:
        """Search for products using SerpAPI shopping results"""
        try:
            search = GoogleSearch({
                "engine": "google_shopping",
                "q": query,
                "api_key": self.serpapi_key
            })
            results = search.get_dict()
            
            products = []
            for item in results.get("shopping_results", []):
                products.append(Product(
                    name=item.get("title", ""),
                    price=float(item.get("price", "0").replace("$", "").replace(",", "")),
                    supplier=item.get("source", ""),
                    url=item.get("link", "")
                ))
                
            return products
            
        except Exception as e:
            print(f"Error searching products: {e}")
            return []
            
    def scrape_static_catalog(self, html_content: str) -> List[Product]:
        """Scrape products from a static HTML catalog"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            products = []
            
            # Example selectors - adjust based on actual HTML structure
            for item in soup.select('.product-item'):
                name = item.select_one('.product-name').text.strip()
                price = float(item.select_one('.product-price').text.strip().replace('$', '').replace(',', ''))
                supplier = item.select_one('.supplier-name').text.strip()
                url = item.select_one('a')['href']
                
                products.append(Product(
                    name=name,
                    price=price,
                    supplier=supplier,
                    url=url
                ))
                
            return products
            
        except Exception as e:
            print(f"Error scraping static catalog: {e}")
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


def prefilter_suppliers_by_price(products: List[Product], top_n: int = 3) -> List[Product]:
    """Filter and sort suppliers by price, keeping only the top N cheapest"""
    # Sort by price
    sorted_products = sorted(products, key=lambda x: x.price)
    
    # Keep only unique suppliers (take first occurrence of each supplier)
    seen_suppliers = set()
    unique_supplier_products = []
    
    for product in sorted_products:
        if product.supplier not in seen_suppliers:
            seen_suppliers.add(product.supplier)
            unique_supplier_products.append(product)
            
    # Return top N
    return unique_supplier_products[:top_n]


if __name__ == "__main__":
    scraper = CatalogScraper(os.getenv("SERPAPI_KEY"))
    
    # Search for products
    products = scraper.search_products("industrial widgets")
    
    # Pre-filter suppliers
    top_suppliers = prefilter_suppliers_by_price(products, top_n=3)
    
    # Print results
    for product in top_suppliers:
        print(f"{product.supplier}: ${product.price} - {product.name}") 