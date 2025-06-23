"""Offer management and database operations for supplier quotes.

This module handles all database operations related to supplier offers,
including storing, retrieving, updating, and managing offer data.
"""

import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import psycopg
from psycopg.rows import dict_row

from backend.app.db import get_connection

logger = logging.getLogger(__name__)


class OfferError(Exception):
    """Exception raised for offer-related errors."""
    pass


class OfferManager:
    """Manager class for supplier offer operations."""
    
    @staticmethod
    def _validate_offer_data(offer_data: Dict[str, Any]) -> None:
        """Validate offer data before database operations."""
        required_fields = ['price', 'currency']
        
        # Check for basic data integrity
        if not isinstance(offer_data, dict):
            raise OfferError("Offer data must be a dictionary")
        
        # Validate price if provided
        if offer_data.get('price') is not None:
            try:
                price = float(offer_data['price'])
                if price < 0:
                    raise OfferError("Price cannot be negative")
            except (ValueError, TypeError):
                raise OfferError("Price must be a valid number")
        
        # Validate lead_time if provided
        if offer_data.get('lead_time') is not None:
            try:
                lead_time = int(offer_data['lead_time'])
                if lead_time < 0:
                    raise OfferError("Lead time cannot be negative")
            except (ValueError, TypeError):
                raise OfferError("Lead time must be a valid integer")
    
    @staticmethod
    async def store_offer(offer_data: Dict[str, Any], supplier_info: Dict[str, str], spec: str) -> Optional[int]:
        """Store a new offer in the database."""
        try:
            OfferManager._validate_offer_data(offer_data)
            
            with get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    # Insert offer
                    insert_query = """
                        INSERT INTO offers (
                            supplier_name, supplier_email, supplier_contact,
                            product_spec, price, currency, lead_time, minimum_order,
                            product_description, notes, status, created_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        ) RETURNING id
                    """
                    
                    cursor.execute(insert_query, (
                        supplier_info.get('name', ''),
                        supplier_info.get('email', ''),
                        supplier_info.get('contact', ''),
                        spec,
                        offer_data.get('price'),
                        offer_data.get('currency', 'USD'),
                        offer_data.get('lead_time'),
                        offer_data.get('minimum_order'),
                        offer_data.get('product_description', ''),
                        offer_data.get('notes', ''),
                        'pending',
                        datetime.now()
                    ))
                    
                    result = cursor.fetchone()
                    conn.commit()
                    
                    if result:
                        logger.info(f"Successfully stored offer with ID: {result['id']}")
                        return result['id']
                    
        except psycopg.Error as e:
            logger.error(f"Database error storing offer: {e}")
            raise OfferError(f"Failed to store offer: {e}")
        except Exception as e:
            logger.error(f"Unexpected error storing offer: {e}")
            raise OfferError(f"Failed to store offer: {e}")
        
        return None
    
    @staticmethod
    async def get_offers_by_spec(spec: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve offers for a specific product specification."""
        try:
            with get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    query = """
                        SELECT * FROM offers 
                        WHERE product_spec = %s 
                        ORDER BY created_at DESC 
                        LIMIT %s
                    """
                    cursor.execute(query, (spec, limit))
                    offers = cursor.fetchall()
                    
                    return [dict(offer) for offer in offers]
                    
        except psycopg.Error as e:
            logger.error(f"Database error retrieving offers: {e}")
            raise OfferError(f"Failed to retrieve offers: {e}")
    
    @staticmethod
    async def get_offer_by_id(offer_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a specific offer by ID."""
        try:
            with get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    query = "SELECT * FROM offers WHERE id = %s"
                    cursor.execute(query, (offer_id,))
                    offer = cursor.fetchone()
                    
                    return dict(offer) if offer else None
                    
        except psycopg.Error as e:
            logger.error(f"Database error retrieving offer: {e}")
            raise OfferError(f"Failed to retrieve offer: {e}")
    
    @staticmethod
    async def update_offer_status(offer_id: int, status: str, notes: str = None) -> bool:
        """Update the status of an offer."""
        valid_statuses = ['pending', 'accepted', 'rejected', 'expired']
        
        if status not in valid_statuses:
            raise OfferError(f"Invalid status. Must be one of: {valid_statuses}")
        
        try:
            with get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    query = """
                        UPDATE offers 
                        SET status = %s, notes = COALESCE(%s, notes), updated_at = %s
                        WHERE id = %s
                    """
                    cursor.execute(query, (status, notes, datetime.now(), offer_id))
                    conn.commit()
                    
                    return cursor.rowcount > 0
                    
        except psycopg.Error as e:
            logger.error(f"Database error updating offer status: {e}")
            raise OfferError(f"Failed to update offer status: {e}")
    
    @staticmethod
    async def delete_offer(offer_id: int) -> bool:
        """Delete an offer from the database."""
        try:
            with get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    query = "DELETE FROM offers WHERE id = %s"
                    cursor.execute(query, (offer_id,))
                    conn.commit()
                    
                    return cursor.rowcount > 0
                    
        except psycopg.Error as e:
            logger.error(f"Database error deleting offer: {e}")
            raise OfferError(f"Failed to delete offer: {e}")
    
    @staticmethod
    async def get_offers_summary(spec: str = None) -> Dict[str, Any]:
        """Get summary statistics for offers."""
        try:
            with get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    base_query = """
                        SELECT 
                            COUNT(*) as total_offers,
                            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_offers,
                            COUNT(CASE WHEN status = 'accepted' THEN 1 END) as accepted_offers,
                            COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected_offers,
                            AVG(price) as avg_price,
                            MIN(price) as min_price,
                            MAX(price) as max_price
                        FROM offers
                    """
                    
                    if spec:
                        query = base_query + " WHERE product_spec = %s"
                        cursor.execute(query, (spec,))
                    else:
                        cursor.execute(base_query)
                    
                    result = cursor.fetchone()
                    return dict(result) if result else {}
                    
        except psycopg.Error as e:
            logger.error(f"Database error getting offers summary: {e}")
            raise OfferError(f"Failed to get offers summary: {e}")
    
    @staticmethod
    async def search_offers(
        search_term: str = None,
        status: str = None,
        min_price: float = None,
        max_price: float = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search offers with various filters."""
        try:
            with get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    conditions = []
                    params = []
                    
                    base_query = "SELECT * FROM offers WHERE 1=1"
                    
                    if search_term:
                        conditions.append("(product_spec ILIKE %s OR supplier_name ILIKE %s OR product_description ILIKE %s)")
                        search_pattern = f"%{search_term}%"
                        params.extend([search_pattern, search_pattern, search_pattern])
                    
                    if status:
                        conditions.append("status = %s")
                        params.append(status)
                    
                    if min_price is not None:
                        conditions.append("price >= %s")
                        params.append(min_price)
                    
                    if max_price is not None:
                        conditions.append("price <= %s")
                        params.append(max_price)
                    
                    if conditions:
                        query = base_query + " AND " + " AND ".join(conditions)
                    else:
                        query = base_query
                    
                    query += " ORDER BY created_at DESC LIMIT %s"
                    params.append(limit)
                    
                    cursor.execute(query, params)
                    offers = cursor.fetchall()
                    
                    return [dict(offer) for offer in offers]
                    
        except psycopg.Error as e:
            logger.error(f"Database error searching offers: {e}")
            raise OfferError(f"Failed to search offers: {e}")
