"""Quote agent for automated RFQ processes and response handling."""

import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
import anyio
import imapclient
import psycopg2
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
    return psycopg2.connect(DB_DSN)


async def store_offer(offer_data: Dict[str, Any], supplier_info: Dict[str, str], spec: str) -> Optional[int]:
    """Store extracted offer in the database using OfferManager."""
    try:
        offer_id = await OfferManager.store_offer(offer_data, supplier_info, spec)
        logger.info(f"Stored offer {offer_id} from {supplier_info.get('name')} for spec: {spec}")
        return offer_id
    except Exception as e:
        logger.error(f"Failed to store offer: {e}")
        return None


def prefilter_suppliers_by_price(suppliers: List[Dict[str, str]], spec: str, max_suppliers: int = 3) -> List[Dict[str, str]]:
    """
    Prefilter suppliers using price hunting before sending RFQs.
    
    Args:
        suppliers: List of supplier dictionaries
        spec: Product specification  
        max_suppliers: Maximum number of suppliers to return
        
    Returns:
        List of suppliers ordered by cheapest list price
    """
    try:
        # Get API key from environment (optional)
        serpapi_key = os.getenv("SERPAPI_KEY")
        
        # Scrape catalog prices
        logger.info(f"Price hunting for '{spec}' before sending RFQs...")
        
        # Use mock results for now (in production, use real scraping)
        # This allows testing without API dependencies
        if os.getenv("USE_MOCK_PRICING", "true").lower() == "true":
            price_results = get_mock_results(spec)
        else:
            price_results = scrape_catalogs(spec, max_results=10, serpapi_key=serpapi_key)
        
        if not price_results:
            logger.warning("No price results found, using original supplier order")
            return suppliers[:max_suppliers]
        
        logger.info(f"Found {len(price_results)} price results:")
        for supplier, url, price in price_results[:5]:  # Log top 5
            logger.info(f"  {supplier}: ${price:.2f}")
        
        # Create a mapping of price results by supplier name
        price_map = {}
        for supplier_name, url, price in price_results:
            # Normalize supplier names for matching
            normalized_name = supplier_name.lower().replace(' ', '').replace('-', '')
            price_map[normalized_name] = {
                'price': price,
                'url': url,
                'original_name': supplier_name
            }
        
        # Match suppliers with price data and sort by price
        enriched_suppliers = []
        unmatched_suppliers = []
        
        for supplier in suppliers:
            normalized_supplier = supplier['name'].lower().replace(' ', '').replace('-', '')
            
            # Try to find price match
            matched_price = None
            for price_name in price_map:
                if (price_name in normalized_supplier or 
                    normalized_supplier in price_name or
                    any(word in price_name for word in normalized_supplier.split() if len(word) > 3)):
                    matched_price = price_map[price_name]
                    break
            
            if matched_price:
                supplier_with_price = supplier.copy()
                supplier_with_price['list_price'] = matched_price['price']
                supplier_with_price['price_source'] = matched_price['url']
                enriched_suppliers.append(supplier_with_price)
                logger.info(f"Matched {supplier['name']} with price ${matched_price['price']:.2f}")
            else:
                unmatched_suppliers.append(supplier)
        
        # Sort enriched suppliers by price (cheapest first)
        enriched_suppliers.sort(key=lambda x: x['list_price'])
        
        # Combine sorted price-matched suppliers with unmatched ones
        final_suppliers = enriched_suppliers + unmatched_suppliers
        
        # Return top N suppliers
        selected_suppliers = final_suppliers[:max_suppliers]
        
        logger.info(f"Selected {len(selected_suppliers)} suppliers ordered by price:")
        for i, supplier in enumerate(selected_suppliers, 1):
            price_info = f"${supplier['list_price']:.2f}" if 'list_price' in supplier else "No price data"
            logger.info(f"  {i}. {supplier['name']} - {price_info}")
        
        return selected_suppliers
        
    except Exception as e:
        logger.error(f"Price prefiltering failed: {e}")
        logger.info("Falling back to original supplier list")
        return suppliers[:max_suppliers]


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
    
    MAX_COUNTER_ROUNDS = 3
    COUNTER_DISCOUNT_PERCENTAGE = 5  # 5% reduction per counter
    
    def __init__(self, db_connection):
        self.db = db_connection
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
        Complete quote process: find suppliers, hunt prices, send RFQs, collect responses.
        
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
            "suppliers_after_price_filter": 0,
            "rfqs_sent": 0,
            "offers_received": 0,
            "suppliers": [],
            "filtered_suppliers": [],
            "offers": []
        }
        
        try:
            # Step 1: Find suppliers using async version
            logger.info(f"Finding suppliers for: {spec}")
            suppliers = await find_suppliers_async(spec, k=max_suppliers * 2)  # Get more for filtering
            results["suppliers_found"] = len(suppliers)
            results["suppliers"] = suppliers
            
            if not suppliers:
                logger.warning("No suppliers found")
                return results
            
            # Step 2: NEW - Price hunt and prefilter suppliers
            logger.info("🎯 Price hunting to find cheapest suppliers...")
            filtered_suppliers = prefilter_suppliers_by_price(suppliers, spec, max_suppliers)
            results["suppliers_after_price_filter"] = len(filtered_suppliers)
            results["filtered_suppliers"] = filtered_suppliers
            
            # Step 3: Send RFQs to filtered suppliers
            logger.info(f"Sending RFQs to {len(filtered_suppliers)} price-filtered suppliers")
            sent_emails = await self.send_rfqs(spec, filtered_suppliers)
            results["rfqs_sent"] = len(sent_emails)
            
            if not sent_emails:
                logger.warning("No RFQs were sent successfully")
                return results
            
            # Step 4: Monitor for responses
            logger.info(f"Monitoring inbox for {poll_duration} seconds")
            offers = await _poll_inbox(spec, filtered_suppliers, poll_duration)
            results["offers_received"] = len(offers)
            results["offers"] = offers
            
            return results
            
        except SupplierSearchError as e:
            logger.error(f"Supplier search failed: {e}")
            raise QuoteAgentError(f"Failed to find suppliers: {e}")
        except Exception as e:
            logger.error(f"Quote process failed: {e}")
            raise QuoteAgentError(f"Quote process failed: {e}")

    def process_quote(self, offer_id: int) -> Dict:
        """Process a quote and determine if counter offer is needed"""
        try:
            # Get offer details
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT o.id, o.supplier_id, o.price, o.status, o.counter_round,
                       s.name as supplier_name, s.email as supplier_email,
                       p.name as product_name, p.list_price
                FROM offers o
                JOIN suppliers s ON o.supplier_id = s.id
                JOIN products p ON o.product_id = p.id
                WHERE o.id = %s
            """, (offer_id,))
            
            offer = cursor.fetchone()
            if not offer:
                return {"status": "error", "message": "Offer not found"}
                
            # Calculate target price (5% below list price)
            target_price = Decimal(str(offer['list_price'])) * Decimal('0.95')
            
            # If price is already below target, accept it
            if offer['price'] <= target_price:
                return self._accept_offer(offer_id)
                
            # If we've reached max counter rounds, mark as needs_user
            if offer['counter_round'] >= self.MAX_COUNTER_ROUNDS:
                return self._mark_needs_user(offer_id)
                
            # Calculate counter price
            counter_price = offer['price'] * Decimal(str(1 - self.COUNTER_DISCOUNT_PERCENTAGE / 100))
            
            # Send counter offer
            return self._send_counter_offer(offer_id, counter_price, offer)
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
            
    def _accept_offer(self, offer_id: int) -> Dict:
        """Accept an offer"""
        cursor = self.db.cursor()
        cursor.execute("""
            UPDATE offers
            SET status = 'ordered'
            WHERE id = %s
            RETURNING id
        """, (offer_id,))
        self.db.commit()
        return {"status": "ordered", "message": "Offer accepted"}
        
    def _mark_needs_user(self, offer_id: int) -> Dict:
        """Mark an offer as needing user input"""
        cursor = self.db.cursor()
        cursor.execute("""
            UPDATE offers
            SET status = 'needs_user'
            WHERE id = %s
            RETURNING id
        """, (offer_id,))
        self.db.commit()
        return {"status": "needs_user", "message": "Maximum counter rounds reached"}
        
    def _send_counter_offer(self, offer_id: int, counter_price: Decimal, offer: Dict) -> Dict:
        """Send a counter offer to the supplier"""
        try:
            # Update offer status
            cursor = self.db.cursor()
            cursor.execute("""
                UPDATE offers
                SET status = 'countered',
                    counter_price = %s
                WHERE id = %s
                RETURNING id
            """, (counter_price, offer_id))
            self.db.commit()
            
            # Prepare email content
            email_content = self._prepare_counter_email(
                supplier_name=offer['supplier_name'],
                product_name=offer['product_name'],
                original_price=offer['price'],
                counter_price=counter_price,
                discount_percentage=self.COUNTER_DISCOUNT_PERCENTAGE
            )
            
            # Send email (implement your email sending logic here)
            # send_email(offer['supplier_email'], "Counter Offer", email_content)
            
            return {
                "status": "countered",
                "message": "Counter offer sent",
                "counter_price": float(counter_price)
            }
            
        except Exception as e:
            self.db.rollback()
            return {"status": "error", "message": str(e)}
            
    def _prepare_counter_email(self, **kwargs) -> str:
        """Prepare counter offer email content"""
        with open('backend/email_templates/counter_offer.txt', 'r') as f:
            template = f.read()
            
        # Replace placeholders
        for key, value in kwargs.items():
            template = template.replace(f"{{{key}}}", str(value))
            
        return template
        
    def process_supplier_response(self, offer_id: int, response_text: str) -> Dict:
        """Process supplier's response to a counter offer"""
        try:
            # Check if response indicates final offer
            is_final = bool(re.search(r'final\s+offer|best\s+price|cannot\s+go\s+lower', 
                                    response_text.lower()))
            
            cursor = self.db.cursor()
            if is_final:
                cursor.execute("""
                    UPDATE offers
                    SET status = 'final'
                    WHERE id = %s
                    RETURNING id
                """, (offer_id,))
                status = "final"
            else:
                cursor.execute("""
                    UPDATE offers
                    SET status = 'open'
                    WHERE id = %s
                    RETURNING id
                """, (offer_id,))
                status = "open"
                
            self.db.commit()
            return {"status": status, "message": "Response processed"}
            
        except Exception as e:
            self.db.rollback()
            return {"status": "error", "message": str(e)}


def run_quote(spec: str, k: int = 3, poll_duration: int = 60) -> None:
    """
    Synchronous wrapper for running the complete quote process.
    
    Args:
        spec: Product specification to quote
        k: Number of suppliers to contact
        poll_duration: How long to wait for responses
    """
    async def _run():
        agent = QuoteAgent(get_db_connection())
        results = await agent.process_quotes(spec, k, poll_duration)
        
        # Print results
        print(f"\n🔍 Quote Process Results for: '{spec}'")
        print("=" * 60)
        print(f"Suppliers found: {results['suppliers_found']}")
        print(f"Suppliers after price filtering: {results['suppliers_after_price_filter']}")
        print(f"RFQs sent: {results['rfqs_sent']}")
        print(f"Offers received: {results['offers_received']}")
        
        if results['filtered_suppliers']:
            print(f"\n🎯 Price-filtered suppliers (cheapest first):")
            for i, supplier in enumerate(results['filtered_suppliers'], 1):
                price_info = f"${supplier['list_price']:.2f}" if 'list_price' in supplier else "No price data"
                print(f"  {i}. {supplier['name']} - {price_info}")
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