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
    async def store_offer(
        offer_data: Dict[str, Any], 
        supplier_info: Dict[str, str], 
        spec: str
    ) -> int:
        """
        Store a supplier offer in the database.
        
        Args:
            offer_data: Dictionary containing offer details (price, currency, etc.)
            supplier_info: Dictionary containing supplier details (name, email, etc.)
            spec: Product specification that was quoted
            
        Returns:
            int: The ID of the newly created offer
            
        Raises:
            OfferError: If offer data is invalid or database operation fails
        """
        try:
            # Validate input data
            OfferManager._validate_offer_data(offer_data)
            
            if not spec or not spec.strip():
                raise OfferError("Specification cannot be empty")
            
            # Extract supplier information
            supplier_name = supplier_info.get("name", "Unknown Supplier")
            supplier_email = offer_data.get("from_email") or supplier_info.get("email", "")
            
            # Connect to database and insert offer
            with get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO supplier_offers 
                    (supplier_name, supplier_email, spec, price, currency, 
                     lead_time, lead_time_unit, email_body, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    RETURNING id
                """, (
                    supplier_name,
                    supplier_email,
                    spec.strip(),
                    offer_data.get("price"),
                    offer_data.get("currency"),
                    offer_data.get("lead_time"),
                    offer_data.get("lead_time_unit"),
                    offer_data.get("email_body", "")
                ))
                
                offer_id = cursor.fetchone()[0]
                conn.commit()
                
                logger.info(f"Stored offer {offer_id} from {supplier_name} for spec: {spec}")
                return offer_id
                
        except psycopg.Error as e:
            logger.error(f"Database error storing offer: {e}")
            raise OfferError(f"Failed to store offer in database: {e}")
        except Exception as e:
            logger.error(f"Unexpected error storing offer: {e}")
            raise OfferError(f"Failed to store offer: {e}")
    
    @staticmethod
    async def get_offers_by_spec(spec: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieve all offers for a specific product specification.
        
        Args:
            spec: Product specification to search for
            limit: Maximum number of offers to return (optional)
            
        Returns:
            List of offer dictionaries
            
        Raises:
            OfferError: If database operation fails
        """
        try:
            if not spec or not spec.strip():
                raise OfferError("Specification cannot be empty")
            
            with get_connection() as conn:
                conn.row_factory = dict_row
                cursor = conn.cursor()
                
                query = """
                    SELECT id, supplier_name, supplier_email, spec, price, currency,
                           lead_time, lead_time_unit, email_body, created_at, parsed_at
                    FROM supplier_offers
                    WHERE spec ILIKE %s
                    ORDER BY created_at DESC
                """
                
                params = [f"%{spec.strip()}%"]
                
                if limit:
                    query += " LIMIT %s"
                    params.append(limit)
                
                cursor.execute(query, params)
                offers = cursor.fetchall()
                
                logger.info(f"Retrieved {len(offers)} offers for spec: {spec}")
                return offers
                
        except psycopg.Error as e:
            logger.error(f"Database error retrieving offers: {e}")
            raise OfferError(f"Failed to retrieve offers: {e}")
        except Exception as e:
            logger.error(f"Unexpected error retrieving offers: {e}")
            raise OfferError(f"Failed to retrieve offers: {e}")
    
    @staticmethod
    async def get_offers_by_supplier(supplier_email: str) -> List[Dict[str, Any]]:
        """
        Retrieve all offers from a specific supplier.
        
        Args:
            supplier_email: Email address of the supplier
            
        Returns:
            List of offer dictionaries
            
        Raises:
            OfferError: If database operation fails
        """
        try:
            if not supplier_email or not supplier_email.strip():
                raise OfferError("Supplier email cannot be empty")
            
            with get_connection() as conn:
                conn.row_factory = dict_row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, supplier_name, supplier_email, spec, price, currency,
                           lead_time, lead_time_unit, email_body, created_at, parsed_at
                    FROM supplier_offers
                    WHERE supplier_email = %s
                    ORDER BY created_at DESC
                """, (supplier_email.strip(),))
                
                offers = cursor.fetchall()
                
                logger.info(f"Retrieved {len(offers)} offers from supplier: {supplier_email}")
                return offers
                
        except psycopg.Error as e:
            logger.error(f"Database error retrieving supplier offers: {e}")
            raise OfferError(f"Failed to retrieve supplier offers: {e}")
        except Exception as e:
            logger.error(f"Unexpected error retrieving supplier offers: {e}")
            raise OfferError(f"Failed to retrieve supplier offers: {e}")
    
    @staticmethod
    async def get_offer_by_id(offer_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific offer by its ID.
        
        Args:
            offer_id: Unique identifier of the offer
            
        Returns:
            Offer dictionary or None if not found
            
        Raises:
            OfferError: If database operation fails
        """
        try:
            if not isinstance(offer_id, int) or offer_id <= 0:
                raise OfferError("Offer ID must be a positive integer")
            
            with get_connection() as conn:
                conn.row_factory = dict_row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, supplier_name, supplier_email, spec, price, currency,
                           lead_time, lead_time_unit, email_body, created_at, parsed_at
                    FROM supplier_offers
                    WHERE id = %s
                """, (offer_id,))
                
                offer = cursor.fetchone()
                
                if offer:
                    logger.info(f"Retrieved offer {offer_id}")
                else:
                    logger.warning(f"Offer {offer_id} not found")
                
                return offer
                
        except psycopg.Error as e:
            logger.error(f"Database error retrieving offer {offer_id}: {e}")
            raise OfferError(f"Failed to retrieve offer: {e}")
        except Exception as e:
            logger.error(f"Unexpected error retrieving offer {offer_id}: {e}")
            raise OfferError(f"Failed to retrieve offer: {e}")
    
    @staticmethod
    async def update_offer_status(offer_id: int, status: str, notes: str = "") -> bool:
        """
        Update the status of an offer (for future workflow management).
        
        Args:
            offer_id: Unique identifier of the offer
            status: New status (e.g., 'pending', 'accepted', 'rejected')
            notes: Optional notes about the status change
            
        Returns:
            bool: True if update was successful, False otherwise
            
        Raises:
            OfferError: If database operation fails
        """
        try:
            if not isinstance(offer_id, int) or offer_id <= 0:
                raise OfferError("Offer ID must be a positive integer")
            
            if not status or not status.strip():
                raise OfferError("Status cannot be empty")
            
            # Note: This assumes we'll add status and notes columns in future migration
            # For now, we'll update the parsed_at timestamp as a placeholder
            with get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE supplier_offers 
                    SET parsed_at = NOW()
                    WHERE id = %s
                    RETURNING id
                """, (offer_id,))
                
                result = cursor.fetchone()
                
                if result:
                    conn.commit()
                    logger.info(f"Updated status for offer {offer_id} to {status}")
                    return True
                else:
                    logger.warning(f"Offer {offer_id} not found for status update")
                    return False
                
        except psycopg.Error as e:
            logger.error(f"Database error updating offer status: {e}")
            raise OfferError(f"Failed to update offer status: {e}")
        except Exception as e:
            logger.error(f"Unexpected error updating offer status: {e}")
            raise OfferError(f"Failed to update offer status: {e}")
    
    @staticmethod
    async def get_offer_statistics() -> Dict[str, Any]:
        """
        Get statistics about offers in the system.
        
        Returns:
            Dictionary containing offer statistics
            
        Raises:
            OfferError: If database operation fails
        """
        try:
            with get_connection() as conn:
                conn.row_factory = dict_row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_offers,
                        COUNT(DISTINCT supplier_email) as unique_suppliers,
                        COUNT(DISTINCT spec) as unique_specs,
                        AVG(price) as avg_price,
                        MIN(price) as min_price,
                        MAX(price) as max_price,
                        AVG(lead_time) as avg_lead_time
                    FROM supplier_offers
                    WHERE price IS NOT NULL
                """)
                
                stats = cursor.fetchone()
                
                # Convert Decimal to float for JSON serialization
                if stats:
                    for key, value in stats.items():
                        if hasattr(value, '__float__'):
                            stats[key] = float(value)
                
                logger.info("Retrieved offer statistics")
                return stats or {}
                
        except psycopg.Error as e:
            logger.error(f"Database error retrieving statistics: {e}")
            raise OfferError(f"Failed to retrieve statistics: {e}")
        except Exception as e:
            logger.error(f"Unexpected error retrieving statistics: {e}")
            raise OfferError(f"Failed to retrieve statistics: {e}")


# Convenience functions for backward compatibility
async def store_offer(offer_data: Dict[str, Any], supplier_info: Dict[str, str], spec: str) -> int:
    """Convenience function for storing offers."""
    return await OfferManager.store_offer(offer_data, supplier_info, spec)


async def get_offers_by_spec(spec: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Convenience function for retrieving offers by specification."""
    return await OfferManager.get_offers_by_spec(spec, limit)


async def get_offers_by_supplier(supplier_email: str) -> List[Dict[str, Any]]:
    """Convenience function for retrieving offers by supplier."""
    return await OfferManager.get_offers_by_supplier(supplier_email) 