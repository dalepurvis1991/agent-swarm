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
from decimal import Decimal

from backend.suppliers import find_suppliers, SupplierSearchError
from backend.suppliers.serp import find_suppliers_async
from backend.email_templates.outgoing import send_rfq, EmailSendError
from backend.email_templates.parser import extract_offer
from backend.app.offers import OfferManager
from pricing import scrape_catalogs, get_mock_results

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


async def store_offer(offer_data: Dict[str, Any], supplier_info: Dict[str, str], spec: str) -> Optional[int]:
    """Store extracted offer in the database using OfferManager."""
    try:
        offer_id = await OfferManager.store_offer(offer_data, supplier_info, spec)
        logger.info(f"Stored offer with ID: {offer_id}")
        return offer_id
    except Exception as e:
        logger.error(f"Failed to store offer: {e}")
        return None


async def process_rfq(spec: str, k: int = 3, poll_duration: int = 30) -> List[Dict[str, Any]]:
    """Process RFQ by finding suppliers, sending requests, and collecting responses."""
    logger.info(f"Processing RFQ for: {spec}")
    
    try:
        # Find suppliers
        logger.info("Finding suppliers...")
        suppliers = await find_suppliers_async(spec, k=k)
        
        if not suppliers:
            logger.warning("No suppliers found")
            return []
        
        logger.info(f"Found {len(suppliers)} suppliers")
        
        # Send RFQ emails
        logger.info("Sending RFQ emails...")
        sent_count = 0
        for supplier in suppliers:
            try:
                await send_rfq(supplier, spec)
                sent_count += 1
                logger.info(f"Sent RFQ to {supplier.get('name', 'Unknown')}")
            except EmailSendError as e:
                logger.error(f"Failed to send RFQ to {supplier.get('name', 'Unknown')}: {e}")
        
        if sent_count == 0:
            logger.warning("No RFQ emails were sent successfully")
            return []
        
        logger.info(f"Successfully sent {sent_count} RFQ emails")
        
        # Poll for responses
        logger.info(f"Polling for responses for {poll_duration} seconds...")
        await asyncio.sleep(poll_duration)
        
        # Check for email responses
        offers = await check_email_responses(spec)
        logger.info(f"Collected {len(offers)} offers")
        
        return offers
        
    except Exception as e:
        logger.error(f"Error processing RFQ: {e}")
        raise QuoteAgentError(f"Failed to process RFQ: {e}")


async def check_email_responses(spec: str) -> List[Dict[str, Any]]:
    """Check email for supplier responses and extract offers."""
    offers = []
    
    try:
        config = get_imap_config()
        
        # Connect to IMAP server
        with imapclient.IMAPClient(config["IMAP_HOST"], port=int(config["IMAP_PORT"])) as server:
            server.login(config["IMAP_USER"], config["IMAP_PASS"])
            server.select_folder('INBOX')
            
            # Search for recent emails
            messages = server.search(['UNSEEN'])
            
            for msg_id in messages:
                try:
                    # Fetch email content
                    msg_data = server.fetch([msg_id], ['RFC822'])
                    raw_email = msg_data[msg_id][b'RFC822']
                    
                    # Extract offer from email
                    offer_data = extract_offer(raw_email.decode('utf-8'))
                    
                    if offer_data:
                        # Store offer in database
                        supplier_info = {
                            'name': offer_data.get('supplier_name', 'Unknown'),
                            'email': offer_data.get('supplier_email', ''),
                            'contact': offer_data.get('contact_person', '')
                        }
                        
                        offer_id = await store_offer(offer_data, supplier_info, spec)
                        if offer_id:
                            offer_data['id'] = offer_id
                            offers.append(offer_data)
                        
                        # Mark as read
                        server.add_flags([msg_id], ['\\Seen'])
                        
                except Exception as e:
                    logger.error(f"Error processing email {msg_id}: {e}")
                    continue
                    
    except Exception as e:
        logger.error(f"Error checking email responses: {e}")
    
    return offers


async def get_mock_offers(spec: str, k: int = 3) -> List[Dict[str, Any]]:
    """Generate mock offers for testing purposes."""
    logger.info(f"Generating {k} mock offers for: {spec}")
    
    mock_offers = []
    for i in range(k):
        offer = {
            'id': f'mock_{i+1}',
            'supplier_name': f'Mock Supplier {i+1}',
            'supplier_email': f'supplier{i+1}@example.com',
            'price': round(10.0 + (i * 2.5), 2),
            'currency': 'USD',
            'lead_time': 7 + (i * 3),
            'minimum_order': 100 * (i + 1),
            'product_description': f'Mock product for {spec}',
            'created_at': datetime.now().isoformat()
        }
        mock_offers.append(offer)
    
    return mock_offers


# Main execution function
async def main():
    """Main function for testing the quote agent."""
    logging.basicConfig(level=logging.INFO)
    
    spec = "eco-friendly tote bags"
    k = 3
    poll_duration = 30
    
    try:
        offers = await process_rfq(spec, k, poll_duration)
        
        if offers:
            print(f"\nReceived {len(offers)} offers:")
            for offer in offers:
                print(f"- {offer.get('supplier_name', 'Unknown')}: ${offer.get('price', 'N/A')} {offer.get('currency', '')}")
        else:
            print("No offers received. Using mock data for demonstration:")
            mock_offers = await get_mock_offers(spec, k)
            for offer in mock_offers:
                print(f"- {offer['supplier_name']}: ${offer['price']} {offer['currency']}")
                
    except QuoteAgentError as e:
        logger.error(f"Quote agent error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
