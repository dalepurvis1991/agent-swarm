"""Tests for offer management functionality."""

import pytest
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime

from backend.app.offers import OfferManager, OfferError, store_offer


class TestOfferManager:
    """Test OfferManager class functionality."""
    
    def test_validate_offer_data_valid(self):
        """Test offer data validation with valid data."""
        valid_offer = {
            "price": 25.50,
            "currency": "USD",
            "lead_time": 14,
            "lead_time_unit": "days"
        }
        
        # Should not raise exception
        OfferManager._validate_offer_data(valid_offer)
    
    def test_validate_offer_data_invalid_price(self):
        """Test offer data validation with invalid price."""
        invalid_offers = [
            {"price": "not a number", "currency": "USD"},
            {"price": -10.0, "currency": "USD"},
            {"price": None, "currency": "USD"}  # None is allowed
        ]
        
        # First two should raise errors
        with pytest.raises(OfferError, match="Price must be a valid number"):
            OfferManager._validate_offer_data(invalid_offers[0])
        
        with pytest.raises(OfferError, match="Price cannot be negative"):
            OfferManager._validate_offer_data(invalid_offers[1])
        
        # None price should be allowed
        OfferManager._validate_offer_data(invalid_offers[2])
    
    def test_validate_offer_data_invalid_lead_time(self):
        """Test offer data validation with invalid lead time."""
        invalid_offers = [
            {"price": 25.0, "currency": "USD", "lead_time": "not a number"},
            {"price": 25.0, "currency": "USD", "lead_time": -5}
        ]
        
        with pytest.raises(OfferError, match="Lead time must be a valid integer"):
            OfferManager._validate_offer_data(invalid_offers[0])
        
        with pytest.raises(OfferError, match="Lead time cannot be negative"):
            OfferManager._validate_offer_data(invalid_offers[1])
    
    def test_validate_offer_data_not_dict(self):
        """Test offer data validation with non-dictionary input."""
        with pytest.raises(OfferError, match="Offer data must be a dictionary"):
            OfferManager._validate_offer_data("not a dict")
    
    @pytest.mark.asyncio
    async def test_store_offer_success(self):
        """Test successful offer storage."""
        offer_data = {
            "price": 25.50,
            "currency": "USD",
            "lead_time": 14,
            "lead_time_unit": "days",
            "email_body": "Test email content",
            "from_email": "supplier@example.com"
        }
        
        supplier_info = {
            "name": "Test Supplier",
            "email": "supplier@example.com"
        }
        
        spec = "eco-friendly tote bags"
        
        # Mock database connection and cursor
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = [123]  # Return offer ID
        
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        
        with patch('backend.app.offers.get_connection', return_value=mock_conn):
            offer_id = await OfferManager.store_offer(offer_data, supplier_info, spec)
            
            assert offer_id == 123
            mock_cursor.execute.assert_called_once()
            mock_conn.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_store_offer_invalid_spec(self):
        """Test offer storage with invalid specification."""
        offer_data = {"price": 25.0, "currency": "USD"}
        supplier_info = {"name": "Test Supplier"}
        
        with pytest.raises(OfferError, match="Specification cannot be empty"):
            await OfferManager.store_offer(offer_data, supplier_info, "")
        
        with pytest.raises(OfferError, match="Specification cannot be empty"):
            await OfferManager.store_offer(offer_data, supplier_info, "   ")
    
    @pytest.mark.asyncio
    async def test_store_offer_database_error(self):
        """Test offer storage with database error."""
        offer_data = {"price": 25.0, "currency": "USD"}
        supplier_info = {"name": "Test Supplier"}
        spec = "test product"
        
        # Mock database connection to raise error
        with patch('backend.app.offers.get_connection') as mock_get_conn:
            mock_get_conn.side_effect = Exception("Database connection failed")
            
            with pytest.raises(OfferError, match="Failed to store offer"):
                await OfferManager.store_offer(offer_data, supplier_info, spec)
    
    @pytest.mark.asyncio
    async def test_get_offers_by_spec_success(self):
        """Test successful retrieval of offers by specification."""
        spec = "tote bags"
        
        mock_offers = [
            {
                "id": 1,
                "supplier_name": "Supplier A",
                "supplier_email": "a@example.com",
                "spec": "eco tote bags",
                "price": 25.50,
                "currency": "USD",
                "lead_time": 14,
                "lead_time_unit": "days",
                "created_at": datetime.now()
            },
            {
                "id": 2,
                "supplier_name": "Supplier B", 
                "supplier_email": "b@example.com",
                "spec": "canvas tote bags",
                "price": 22.00,
                "currency": "USD",
                "lead_time": 21,
                "lead_time_unit": "days",
                "created_at": datetime.now()
            }
        ]
        
        # Mock database connection and cursor
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = mock_offers
        
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        
        with patch('backend.app.offers.get_connection', return_value=mock_conn):
            offers = await OfferManager.get_offers_by_spec(spec)
            
            assert len(offers) == 2
            assert offers[0]["supplier_name"] == "Supplier A"
            assert offers[1]["supplier_name"] == "Supplier B"
            mock_cursor.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_offers_by_spec_with_limit(self):
        """Test retrieval of offers by specification with limit."""
        spec = "tote bags"
        limit = 1
        
        mock_offers = [{"id": 1, "supplier_name": "Supplier A"}]
        
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = mock_offers
        
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        
        with patch('backend.app.offers.get_connection', return_value=mock_conn):
            offers = await OfferManager.get_offers_by_spec(spec, limit)
            
            assert len(offers) == 1
            # Verify the LIMIT clause was added
            call_args = mock_cursor.execute.call_args[0]
            assert "LIMIT" in call_args[0]
            assert limit in call_args[1]
    
    @pytest.mark.asyncio
    async def test_get_offers_by_spec_empty_spec(self):
        """Test retrieval with empty specification."""
        with pytest.raises(OfferError, match="Specification cannot be empty"):
            await OfferManager.get_offers_by_spec("")
    
    @pytest.mark.asyncio
    async def test_get_offers_by_supplier_success(self):
        """Test successful retrieval of offers by supplier."""
        supplier_email = "supplier@example.com"
        
        mock_offers = [
            {"id": 1, "supplier_email": "supplier@example.com", "spec": "product A"},
            {"id": 2, "supplier_email": "supplier@example.com", "spec": "product B"}
        ]
        
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = mock_offers
        
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        
        with patch('backend.app.offers.get_connection', return_value=mock_conn):
            offers = await OfferManager.get_offers_by_supplier(supplier_email)
            
            assert len(offers) == 2
            assert all(offer["supplier_email"] == supplier_email for offer in offers)
    
    @pytest.mark.asyncio
    async def test_get_offer_by_id_success(self):
        """Test successful retrieval of offer by ID."""
        offer_id = 123
        
        mock_offer = {
            "id": offer_id,
            "supplier_name": "Test Supplier",
            "spec": "test product",
            "price": 25.50
        }
        
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = mock_offer
        
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        
        with patch('backend.app.offers.get_connection', return_value=mock_conn):
            offer = await OfferManager.get_offer_by_id(offer_id)
            
            assert offer is not None
            assert offer["id"] == offer_id
            assert offer["supplier_name"] == "Test Supplier"
    
    @pytest.mark.asyncio
    async def test_get_offer_by_id_not_found(self):
        """Test retrieval of non-existent offer by ID."""
        offer_id = 999
        
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        
        with patch('backend.app.offers.get_connection', return_value=mock_conn):
            offer = await OfferManager.get_offer_by_id(offer_id)
            
            assert offer is None
    
    @pytest.mark.asyncio
    async def test_get_offer_by_id_invalid_id(self):
        """Test retrieval with invalid offer ID."""
        invalid_ids = [0, -1, "not_an_int", None]
        
        for invalid_id in invalid_ids:
            with pytest.raises(OfferError, match="Offer ID must be a positive integer"):
                await OfferManager.get_offer_by_id(invalid_id)
    
    @pytest.mark.asyncio
    async def test_update_offer_status_success(self):
        """Test successful offer status update."""
        offer_id = 123
        status = "accepted"
        
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = [offer_id]  # Return updated offer ID
        
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        
        with patch('backend.app.offers.get_connection', return_value=mock_conn):
            result = await OfferManager.update_offer_status(offer_id, status)
            
            assert result is True
            mock_cursor.execute.assert_called_once()
            mock_conn.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_offer_status_not_found(self):
        """Test status update for non-existent offer."""
        offer_id = 999
        status = "accepted"
        
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        
        with patch('backend.app.offers.get_connection', return_value=mock_conn):
            result = await OfferManager.update_offer_status(offer_id, status)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_offer_statistics_success(self):
        """Test successful retrieval of offer statistics."""
        mock_stats = {
            "total_offers": 10,
            "unique_suppliers": 5,
            "unique_specs": 3,
            "avg_price": 25.75,
            "min_price": 10.00,
            "max_price": 50.00,
            "avg_lead_time": 14.5
        }
        
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = mock_stats
        
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        
        with patch('backend.app.offers.get_connection', return_value=mock_conn):
            stats = await OfferManager.get_offer_statistics()
            
            assert stats["total_offers"] == 10
            assert stats["unique_suppliers"] == 5
            assert stats["avg_price"] == 25.75


class TestConvenienceFunctions:
    """Test convenience functions for backward compatibility."""
    
    @pytest.mark.asyncio
    async def test_store_offer_convenience_function(self):
        """Test the convenience store_offer function."""
        offer_data = {"price": 25.0, "currency": "USD"}
        supplier_info = {"name": "Test Supplier"}
        spec = "test product"
        
        with patch.object(OfferManager, 'store_offer', return_value=123) as mock_store:
            result = await store_offer(offer_data, supplier_info, spec)
            
            assert result == 123
            mock_store.assert_called_once_with(offer_data, supplier_info, spec) 