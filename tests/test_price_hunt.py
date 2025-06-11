"""Tests for price hunting and catalog scraping functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Tuple
import requests
import json

from pricing.scrape_catalogs import (
    scrape_catalogs, 
    get_mock_results, 
    CatalogScraper, 
    PriceResult
)
from backend.agents.quote_agent import prefilter_suppliers_by_price


class TestMockResults:
    """Test the mock price results functionality."""
    
    def test_get_mock_results_tote_bags(self):
        """Test mock results for tote bags."""
        results = get_mock_results("eco tote bags")
        
        assert len(results) == 3  # Should return top 3
        assert all(len(result) == 3 for result in results)  # (supplier, url, price)
        
        # Should be sorted by price
        prices = [result[2] for result in results]
        assert prices == sorted(prices)
        
        # Should contain relevant suppliers
        suppliers = [result[0] for result in results]
        assert any("4imprint" in supplier for supplier in suppliers)
    
    def test_get_mock_results_non_bag_product(self):
        """Test mock results for non-bag products."""
        results = get_mock_results("custom water bottles")
        
        # Should return empty for non-matching products
        assert len(results) == 0
    
    def test_get_mock_results_promotional_items(self):
        """Test mock results for promotional items."""
        results = get_mock_results("promotional items")
        
        assert len(results) > 0
        # Should be sorted by price
        prices = [result[2] for result in results]
        assert prices == sorted(prices)


class TestCatalogScraper:
    """Test the main catalog scraper functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.scraper = CatalogScraper()
    
    def test_scraper_initialization(self):
        """Test scraper initialization."""
        assert self.scraper.serpapi_key is None
        assert self.scraper.session is not None
        assert 'User-Agent' in self.scraper.session.headers
    
    def test_scraper_with_api_key(self):
        """Test scraper initialization with API key."""
        scraper = CatalogScraper(serpapi_key="test-key")
        assert scraper.serpapi_key == "test-key"
    
    @patch('requests.get')
    def test_serpapi_scraping_success(self, mock_get):
        """Test successful SerpAPI scraping."""
        # Mock SerpAPI response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "shopping_results": [
                {
                    "title": "Eco Tote Bag",
                    "price": "$5.99",
                    "source": "Amazon",
                    "link": "https://amazon.com/eco-tote"
                },
                {
                    "title": "Canvas Tote",
                    "price": "$8.50",
                    "source": "Walmart", 
                    "link": "https://walmart.com/canvas-tote"
                }
            ]
        }
        mock_get.return_value = mock_response
        
        scraper = CatalogScraper(serpapi_key="test-key")
        results = scraper._scrape_serpapi_shopping("eco tote bags")
        
        assert len(results) == 2
        assert results[0].supplier == "Amazon"
        assert results[0].list_price == 5.99
        assert results[1].supplier == "Walmart"
        assert results[1].list_price == 8.50
    
    @patch('requests.get')
    def test_serpapi_scraping_failure(self, mock_get):
        """Test SerpAPI scraping failure handling."""
        mock_get.side_effect = requests.RequestException("API Error")
        
        scraper = CatalogScraper(serpapi_key="test-key")
        results = scraper._scrape_serpapi_shopping("eco tote bags")
        
        assert results == []
    
    def test_serpapi_no_api_key(self):
        """Test SerpAPI scraping without API key."""
        results = self.scraper._scrape_serpapi_shopping("eco tote bags")
        assert results == []
    
    @patch('requests.Session.get')
    def test_4imprint_scraping_success(self, mock_get):
        """Test successful 4imprint scraping with mock HTML."""
        mock_html = """
        <html>
            <div class="product-item">
                <h3 class="product-title">Eco Tote Bag</h3>
                <span class="price">$6.99</span>
                <a href="/product/eco-tote-1">View Product</a>
            </div>
            <div class="product-item">
                <h2 class="product-name">Canvas Bag</h2>
                <div class="price-display">$9.50</div>
                <a href="/product/canvas-bag-2">View Details</a>
            </div>
        </html>
        """
        
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = mock_html.encode('utf-8')
        mock_get.return_value = mock_response
        
        results = self.scraper._scrape_4imprint("tote bags")
        
        # Should find at least one product
        assert len(results) >= 1
        # Verify price extraction worked
        prices = [r.list_price for r in results if r.list_price > 0]
        assert len(prices) >= 1
    
    @patch('requests.Session.get')
    def test_4imprint_scraping_failure(self, mock_get):
        """Test 4imprint scraping failure handling."""
        mock_get.side_effect = requests.RequestException("Network Error")
        
        results = self.scraper._scrape_4imprint("tote bags")
        assert results == []
    
    @patch('requests.Session.get')
    def test_customink_scraping_success(self, mock_get):
        """Test successful CustomInk scraping."""
        mock_html = """
        <html>
            <div class="product-card">
                <h4 class="product-title">Custom Tote Bag</h4>
                <span>Starting at $12.99</span>
                <a href="/products/custom-tote">Customize</a>
            </div>
        </html>
        """
        
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = mock_html.encode('utf-8')
        mock_get.return_value = mock_response
        
        results = self.scraper._scrape_customink("custom tote bags")
        
        # Should handle the scraping attempt
        assert isinstance(results, list)
    
    @patch('pricing.scrape_catalogs.CatalogScraper._scrape_serpapi_shopping')
    @patch('pricing.scrape_catalogs.CatalogScraper._scrape_static_retailers')
    def test_scrape_catalogs_integration(self, mock_static, mock_serp):
        """Test the main scrape_catalogs function integration."""
        # Mock results from different sources
        mock_serp.return_value = [
            PriceResult("Amazon", "https://amazon.com/product1", 5.99, "USD"),
            PriceResult("Walmart", "https://walmart.com/product2", 7.50, "USD")
        ]
        
        mock_static.return_value = [
            PriceResult("4imprint", "https://4imprint.com/product3", 6.25, "USD"),
            PriceResult("CustomInk", "https://customink.com/product4", 8.99, "USD")
        ]
        
        scraper = CatalogScraper(serpapi_key="test-key")
        results = scraper.scrape_catalogs("eco tote bags", max_results=3)
        
        # Should return results sorted by price
        assert len(results) == 3  # Limited by max_results
        assert results[0].list_price == 5.99  # Amazon (cheapest)
        assert results[1].list_price == 6.25  # 4imprint
        assert results[2].list_price == 7.50  # Walmart


class TestPricePrefiltering:
    """Test the supplier prefiltering functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sample_suppliers = [
            {
                "name": "ABC Trading Co",
                "url": "https://abctrading.com",
                "source": "search_engine"
            },
            {
                "name": "4imprint",
                "url": "https://4imprint.com/corporate",
                "source": "supplier_directory"
            },
            {
                "name": "CustomInk Solutions",
                "url": "https://customink.com/business",
                "source": "search_engine"
            },
            {
                "name": "DHgate Wholesale",
                "url": "https://dhgate.com/supplier123",
                "source": "marketplace"
            }
        ]
    
    @patch.dict('os.environ', {'USE_MOCK_PRICING': 'true'})
    def test_prefilter_suppliers_by_price_mock(self):
        """Test supplier prefiltering with mock pricing data."""
        result = prefilter_suppliers_by_price(
            self.sample_suppliers, 
            "eco tote bags", 
            max_suppliers=3
        )
        
        assert len(result) <= 3
        assert isinstance(result, list)
        
        # Check if suppliers with price data are prioritized
        suppliers_with_prices = [s for s in result if 'list_price' in s]
        suppliers_without_prices = [s for s in result if 'list_price' not in s]
        
        # Suppliers with price data should come first and be sorted by price
        if len(suppliers_with_prices) > 1:
            prices = [s['list_price'] for s in suppliers_with_prices]
            assert prices == sorted(prices)
    
    @patch('backend.agents.quote_agent.scrape_catalogs')
    @patch.dict('os.environ', {'USE_MOCK_PRICING': 'false'})
    def test_prefilter_suppliers_real_scraping(self, mock_scrape):
        """Test supplier prefiltering with real scraping (mocked)."""
        # Mock scrape_catalogs return
        mock_scrape.return_value = [
            ("4imprint", "https://4imprint.com/product1", 5.99),
            ("CustomInk", "https://customink.com/product2", 7.50),
            ("Unknown Supplier", "https://unknown.com/product3", 3.25)
        ]
        
        result = prefilter_suppliers_by_price(
            self.sample_suppliers,
            "eco tote bags",
            max_suppliers=2
        )
        
        assert len(result) <= 2
        mock_scrape.assert_called_once()
    
    @patch.dict('os.environ', {'USE_MOCK_PRICING': 'true'})
    def test_prefilter_suppliers_no_price_data(self):
        """Test prefiltering when no price data is available."""
        with patch('backend.agents.quote_agent.get_mock_results') as mock_results:
            mock_results.return_value = []
            
            result = prefilter_suppliers_by_price(
                self.sample_suppliers,
                "unknown product",
                max_suppliers=2
            )
            
            # Should fall back to original list
            assert len(result) == 2
            assert result[0]['name'] == self.sample_suppliers[0]['name']
    
    @patch.dict('os.environ', {'USE_MOCK_PRICING': 'true'})
    def test_prefilter_suppliers_exception_handling(self):
        """Test that exceptions in prefiltering are handled gracefully."""
        with patch('backend.agents.quote_agent.get_mock_results') as mock_results:
            mock_results.side_effect = Exception("Scraping failed")
            
            result = prefilter_suppliers_by_price(
                self.sample_suppliers,
                "eco tote bags",
                max_suppliers=2
            )
            
            # Should fall back to original list (first 2 suppliers)
            assert len(result) == 2
            # When there's an exception, it should return the first N suppliers from original list
            original_names = [s['name'] for s in self.sample_suppliers[:2]]
            result_names = [s['name'] for s in result]
            assert result_names == original_names


class TestMainScrapeFunction:
    """Test the main scrape_catalogs function."""
    
    @patch('pricing.scrape_catalogs.CatalogScraper')
    def test_scrape_catalogs_function(self, mock_scraper_class):
        """Test the main scrape_catalogs function."""
        # Mock scraper instance
        mock_scraper = Mock()
        mock_scraper.scrape_catalogs.return_value = [
            PriceResult("Supplier1", "https://url1.com", 5.99),
            PriceResult("Supplier2", "https://url2.com", 7.50)
        ]
        mock_scraper_class.return_value = mock_scraper
        
        results = scrape_catalogs("eco tote bags", max_results=5, serpapi_key="test-key")
        
        # Should return tuple format
        assert len(results) == 2
        assert results[0] == ("Supplier1", "https://url1.com", 5.99)
        assert results[1] == ("Supplier2", "https://url2.com", 7.50)
        
        # Should initialize scraper with API key
        mock_scraper_class.assert_called_once_with(serpapi_key="test-key")
        mock_scraper.scrape_catalogs.assert_called_once_with("eco tote bags", max_results=5)
    
    def test_scrape_catalogs_no_api_key(self):
        """Test scrape_catalogs function without API key."""
        with patch('pricing.scrape_catalogs.CatalogScraper') as mock_scraper_class:
            mock_scraper = Mock()
            mock_scraper.scrape_catalogs.return_value = []
            mock_scraper_class.return_value = mock_scraper
            
            results = scrape_catalogs("test product")
            
            assert results == []
            mock_scraper_class.assert_called_once_with(serpapi_key=None)


class TestPriceResult:
    """Test the PriceResult class."""
    
    def test_price_result_creation(self):
        """Test creating a PriceResult object."""
        result = PriceResult(
            supplier="Test Supplier",
            url="https://test.com",
            list_price=9.99,
            currency="USD",
            title="Test Product"
        )
        
        assert result.supplier == "Test Supplier"
        assert result.url == "https://test.com"
        assert result.list_price == 9.99
        assert result.currency == "USD"
        assert result.title == "Test Product"
    
    def test_price_result_repr(self):
        """Test PriceResult string representation."""
        result = PriceResult("Test Supplier", "https://test.com", 9.99)
        repr_str = repr(result)
        
        assert "Test Supplier" in repr_str
        assert "9.99" in repr_str
        assert "USD" in repr_str


class TestIntegration:
    """Integration tests for the complete price hunting workflow."""
    
    @patch.dict('os.environ', {'USE_MOCK_PRICING': 'true'})
    def test_full_price_hunting_workflow(self):
        """Test the complete price hunting workflow."""
        suppliers = [
            {"name": "4imprint", "url": "https://4imprint.com", "source": "directory"},
            {"name": "CustomInk", "url": "https://customink.com", "source": "search"},
            {"name": "Random Supplier", "url": "https://random.com", "source": "search"}
        ]
        
        # Test the complete workflow
        result = prefilter_suppliers_by_price(suppliers, "eco tote bags", max_suppliers=2)
        
        assert len(result) <= 2
        assert isinstance(result, list)
        
        # Should prioritize suppliers with price data
        for supplier in result:
            if 'list_price' in supplier:
                assert isinstance(supplier['list_price'], (int, float))
                assert supplier['list_price'] > 0
    
    def test_edge_cases(self):
        """Test edge cases in price hunting."""
        # Empty supplier list
        result = prefilter_suppliers_by_price([], "eco tote bags", max_suppliers=3)
        assert result == []
        
        # Zero max_suppliers
        suppliers = [{"name": "Test", "url": "https://test.com", "source": "test"}]
        result = prefilter_suppliers_by_price(suppliers, "eco tote bags", max_suppliers=0)
        assert len(result) == 0
        
        # Special characters in spec
        result = prefilter_suppliers_by_price(suppliers, "eco-tote_bags@#$", max_suppliers=1)
        assert len(result) <= 1 