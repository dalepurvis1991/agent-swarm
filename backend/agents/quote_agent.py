"""Quote agent for automated RFQ processes and response handling."""

import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
import anyio
import imapclient
import psycopg
import re

from backend.suppliers import find_suppliers, SupplierSearchError
from backend.suppliers.serp import find_suppliers_async
from backend.email.outgoing import send_rfq, EmailSendError
from backend.email.parser import extract_offer

logger = logging.getLogger(__name__)


class QuoteAgentError(Exception):
    """Exception raised when quote agent operations fail."""
    pass


def get_imap_config() -> Dict[str, str]:
    """Get IMAP configuration from environment variables."""
    return {
        "IMAP_HOST": os.getenv("IMAP_HOST", "localhost"),
        "IMAP_PORT": os.getenv("IMAP_PORT", "1143"),
        "IMAP_USER": os.getenv("IMAP_USER", "test@example.com"),
        "IMAP_PASS": os.getenv("IMAP_PASS", "")
    }


def get_db_connection():
    """Get database connection using existing configuration."""
    from backend.app.db import DB_DSN
    return psycopg.connect(DB_DSN)


def store_offer(offer_data: Dict[str, Any], supplier_info: Dict[str, str], spec: str) -> None:
    """Store extracted offer in the database."""
    try:
        with get_db_connection() as conn:
            conn.execute("""
                INSERT INTO supplier_offers 
                (supplier_name, supplier_email, spec, price, currency, lead_time, lead_time_unit, email_body)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                supplier_info.get("name", "Unknown"),
                offer_data.get("from_email", supplier_info.get("url", "")),
                spec,
                offer_data.get("price"),
                offer_data.get("currency"),
                offer_data.get("lead_time"),
                offer_data.get("lead_time_unit"),
                offer_data.get("email_body", "")
            ))
            logger.info(f"Stored offer from {supplier_info.get('name')} for spec: {spec}")
    except Exception as e:
        logger.error(f"Failed to store offer: {e}")


async def _poll_inbox(spec: str, suppliers: List[Dict[str, str]], max_duration: int = 300) -> List[Dict[str, Any]]:
    """
    Poll email inbox for supplier responses.
    
    Args:
        spec: Product specification being quoted
        suppliers: List of suppliers that were contacted
        max_duration: Maximum time to poll in seconds
        
    Returns:
        List of extracted offers
    """
    offers = []
    start_time = asyncio.get_event_loop().time()
    
    # Note: This is a simplified version for MailHog testing
    # In production, you'd use proper IMAP with SSL and authentication
    logger.info(f"Starting inbox polling for spec: {spec}")
    logger.info("Note: This is a demo version - in production, implement proper IMAP polling")
    
    # For now, we'll just simulate the polling process
    # In a real implementation, you would:
    # 1. Connect to IMAP server
    # 2. Search for new emails
    # 3. Extract offers from matching emails
    # 4. Store offers in database
    
    while (asyncio.get_event_loop().time() - start_time) < max_duration:
        try:
            # Simulate checking for new emails
            await asyncio.sleep(10)  # Check every 10 seconds
            logger.info(f"Checking for new responses... ({len(offers)} offers found so far)")
            
            # In a real implementation, this is where you'd:
            # - Connect to IMAP
            # - Search for UNSEEN emails
            # - Parse and extract offers
            # - Store in database
            
        except Exception as e:
            logger.error(f"Error polling inbox: {e}")
            break
    
    logger.info(f"Inbox polling completed. Found {len(offers)} offers.")
    return offers


def sanitize_email_name(name: str) -> str:
    """Convert supplier name to email-safe format."""
    # Remove common business suffixes and clean up
    name = name.lower()
    name = re.sub(r'\b(co|ltd|llc|inc|corp|company|solutions?|supply|wholesale)\b', '', name)
    name = re.sub(r'[^a-z0-9\s]', '', name)  # Remove special chars
    name = re.sub(r'\s+', '-', name.strip())  # Replace spaces with hyphens
    name = name.strip('-')  # Remove leading/trailing hyphens
    return name if name else "supplier"


class QuoteAgent:
    """Agent for managing automated quote requests and responses."""
    
    def __init__(self):
        self.suppliers = []
        self.offers = []
    
    async def send_rfqs(self, spec: str, suppliers: List[Dict[str, str]]) -> List[str]:
        """Send RFQ emails to a list of suppliers."""
        sent_emails = []
        
        for supplier in suppliers:
            try:
                # Generate email address from supplier name
                clean_name = sanitize_email_name(supplier['name'])
                email_address = f"{clean_name}@example.com"
                
                await send_rfq(email_address, spec)
                sent_emails.append(email_address)
                logger.info(f"RFQ sent to {supplier['name']} at {email_address}")
                
            except EmailSendError as e:
                logger.error(f"Failed to send RFQ to {supplier['name']}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error sending RFQ to {supplier['name']}: {e}")
        
        return sent_emails
    
    async def process_quotes(self, spec: str, max_suppliers: int = 3, poll_duration: int = 60) -> Dict[str, Any]:
        """
        Complete quote process: find suppliers, send RFQs, collect responses.
        
        Args:
            spec: Product specification to quote
            max_suppliers: Maximum number of suppliers to contact
            poll_duration: How long to wait for responses (seconds)
            
        Returns:
            Dictionary with process results
        """
        results = {
            "spec": spec,
            "suppliers_found": 0,
            "rfqs_sent": 0,
            "offers_received": 0,
            "suppliers": [],
            "offers": []
        }
        
        try:
            # Step 1: Find suppliers using async version
            logger.info(f"Finding suppliers for: {spec}")
            suppliers = await find_suppliers_async(spec, k=max_suppliers)
            results["suppliers_found"] = len(suppliers)
            results["suppliers"] = suppliers
            
            if not suppliers:
                logger.warning("No suppliers found")
                return results
            
            # Step 2: Send RFQs
            logger.info(f"Sending RFQs to {len(suppliers)} suppliers")
            sent_emails = await self.send_rfqs(spec, suppliers)
            results["rfqs_sent"] = len(sent_emails)
            
            if not sent_emails:
                logger.warning("No RFQs were sent successfully")
                return results
            
            # Step 3: Monitor for responses
            logger.info(f"Monitoring inbox for {poll_duration} seconds")
            offers = await _poll_inbox(spec, suppliers, poll_duration)
            results["offers_received"] = len(offers)
            results["offers"] = offers
            
            return results
            
        except SupplierSearchError as e:
            logger.error(f"Supplier search failed: {e}")
            raise QuoteAgentError(f"Failed to find suppliers: {e}")
        except Exception as e:
            logger.error(f"Quote process failed: {e}")
            raise QuoteAgentError(f"Quote process failed: {e}")


def run_quote(spec: str, k: int = 3, poll_duration: int = 60) -> None:
    """
    Synchronous wrapper for running the complete quote process.
    
    Args:
        spec: Product specification to quote
        k: Number of suppliers to contact
        poll_duration: How long to wait for responses
    """
    async def _run():
        agent = QuoteAgent()
        results = await agent.process_quotes(spec, k, poll_duration)
        
        # Print results
        print(f"\n🔍 Quote Process Results for: '{spec}'")
        print("=" * 60)
        print(f"Suppliers found: {results['suppliers_found']}")
        print(f"RFQs sent: {results['rfqs_sent']}")
        print(f"Offers received: {results['offers_received']}")
        
        if results['suppliers']:
            print(f"\n📧 Suppliers contacted:")
            for i, supplier in enumerate(results['suppliers'], 1):
                print(f"  {i}. {supplier['name']}")
                print(f"     URL: {supplier['url']}")
                print(f"     Source: {supplier['source']}")
        
        if results['offers']:
            print(f"\n💰 Offers received:")
            for i, offer in enumerate(results['offers'], 1):
                price_info = f"{offer['currency']}{offer['price']}" if offer['price'] else "No price"
                lead_info = f"{offer['lead_time']} {offer['lead_time_unit']}" if offer['lead_time'] else "No lead time"
                print(f"  {i}. {price_info}, Lead time: {lead_info}")
        else:
            print(f"\n⏳ No offers received yet. In a real scenario, offers would be")
            print(f"   processed automatically as they arrive via email.")
        
        return results
    
    try:
        return anyio.run(_run)
    except Exception as e:
        logger.error(f"Quote process failed: {e}")
        print(f"❌ Quote process failed: {e}")
        raise 