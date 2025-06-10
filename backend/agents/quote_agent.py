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
from backend.app.offers import OfferManager

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
        logger.info(f"Stored offer {offer_id} from {supplier_info.get('name')} for spec: {spec}")
        return offer_id
    except Exception as e:
        logger.error(f"Failed to store offer: {e}")
        return None


async def _poll_inbox(spec: str, suppliers: List[Dict[str, str]], max_duration: int = 300) -> List[Dict[str, Any]]:
    """
    Poll email inbox for supplier responses using IMAP.
    
    Args:
        spec: Product specification being quoted
        suppliers: List of suppliers that were contacted
        max_duration: Maximum time to poll in seconds
        
    Returns:
        List of extracted offers
    """
    offers = []
    start_time = asyncio.get_event_loop().time()
    processed_uids = set()  # Track processed emails to avoid duplicates
    
    logger.info(f"Starting IMAP inbox polling for spec: {spec}")
    
    # Get IMAP configuration
    imap_config = get_imap_config()
    imap_host = imap_config["IMAP_HOST"]
    imap_port = int(imap_config["IMAP_PORT"])
    imap_user = imap_config["IMAP_USER"]
    imap_pass = imap_config["IMAP_PASS"]
    
    # Extract supplier email addresses for filtering
    supplier_emails = set()
    for supplier in suppliers:
        clean_name = sanitize_email_name(supplier['name'])
        supplier_emails.add(f"{clean_name}@example.com")
    
    logger.info(f"Monitoring for responses from: {', '.join(supplier_emails)}")
    
    while (asyncio.get_event_loop().time() - start_time) < max_duration:
        try:
            # Connect to IMAP server
            # Note: For MailHog, we use non-SSL connection
            # In production, use SSL/TLS connections
            with imapclient.IMAPClient(imap_host, port=imap_port, ssl=False) as server:
                try:
                    # Login to the server
                    if imap_user and imap_pass:
                        server.login(imap_user, imap_pass)
                    
                    # Select the INBOX folder
                    server.select_folder('INBOX')
                    
                    # Search for unread messages
                    # In production, you might want to search by date range or subject
                    message_ids = server.search(['UNSEEN'])
                    
                    logger.info(f"Found {len(message_ids)} unread messages")
                    
                    for msg_id in message_ids:
                        if msg_id in processed_uids:
                            continue  # Skip already processed messages
                        
                        try:
                            # Fetch the message
                            response = server.fetch(msg_id, ['RFC822'])
                            email_message = response[msg_id][b'RFC822'].decode('utf-8', errors='ignore')
                            
                            # Extract sender email from the raw message
                            from_match = re.search(r'From:.*?([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', email_message)
                            from_email = from_match.group(1) if from_match else ""
                            
                            # Check if this email is from one of our contacted suppliers
                            if from_email in supplier_emails or any(email in from_email for email in supplier_emails):
                                logger.info(f"Processing response from supplier: {from_email}")
                                
                                try:
                                    # Extract offer data from the email
                                    offer_data = extract_offer(email_message)
                                    offer_data["from_email"] = from_email
                                    
                                    # Find matching supplier info
                                    supplier_info = None
                                    for supplier in suppliers:
                                        clean_name = sanitize_email_name(supplier['name'])
                                        expected_email = f"{clean_name}@example.com"
                                        if from_email == expected_email:
                                            supplier_info = supplier
                                            break
                                    
                                    if supplier_info is None:
                                        supplier_info = {"name": from_email.split("@")[0].replace("-", " ").title()}
                                    
                                    # Store the offer in the database
                                    if offer_data.get("price") is not None:  # Only store if we found pricing
                                        offer_id = await store_offer(offer_data, supplier_info, spec)
                                        if offer_id:
                                            offer_data["offer_id"] = offer_id
                                            offers.append(offer_data)
                                            logger.info(f"Stored offer {offer_id} from {supplier_info['name']}")
                                        else:
                                            logger.warning(f"Failed to store offer from {supplier_info['name']}")
                                    else:
                                        logger.info(f"No pricing found in email from {from_email}, skipping storage")
                                    
                                    # Mark as processed
                                    processed_uids.add(msg_id)
                                    
                                    # Mark the email as read
                                    server.add_flags(msg_id, [imapclient.SEEN])
                                    
                                except Exception as e:
                                    logger.error(f"Error processing email from {from_email}: {e}")
                            else:
                                # Mark non-supplier emails as read to avoid reprocessing
                                server.add_flags(msg_id, [imapclient.SEEN])
                        
                        except Exception as e:
                            logger.error(f"Error processing message {msg_id}: {e}")
                            continue
                    
                except imapclient.IMAPClientError as e:
                    logger.error(f"IMAP client error: {e}")
                except Exception as e:
                    logger.error(f"IMAP connection error: {e}")
            
            # Wait before next poll
            await asyncio.sleep(10)  # Check every 10 seconds
            logger.info(f"Checking for new responses... ({len(offers)} offers found so far)")
            
        except Exception as e:
            logger.error(f"Error in inbox polling cycle: {e}")
            await asyncio.sleep(10)  # Wait before retrying
    
    logger.info(f"IMAP inbox polling completed. Found {len(offers)} offers.")
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