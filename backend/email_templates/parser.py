"""Email parser for extracting offer information from supplier quote responses."""

import re
import email
import logging
from typing import Dict, Optional, Any
from email.message import EmailMessage

logger = logging.getLogger(__name__)

# Regex patterns for extracting pricing and timing information
PRICE_PATTERN = re.compile(r'([£$€¥¢]?)\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', re.IGNORECASE)
CURRENCY_PATTERN = re.compile(r'([£$€¥¢])|(?:\b(GBP|USD|EUR|JPY|CNY)\b)', re.IGNORECASE)
LEAD_TIME_PATTERN = re.compile(r'(\d+)\s*(day|week|month)s?', re.IGNORECASE)

# Keywords that might indicate pricing context
PRICE_KEYWORDS = [
    'price', 'cost', 'quote', 'total', 'amount', 'per unit', 'each',
    'wholesale', 'bulk', 'minimum', 'maximum'
]

# Keywords that might indicate lead time context
TIME_KEYWORDS = [
    'lead time', 'delivery', 'ship', 'available', 'ready', 'turnaround',
    'production time', 'manufacturing time'
]


def extract_email_body(raw_email: str) -> str:
    """Extract plain text body from raw email string."""
    try:
        msg = email.message_from_string(raw_email)
        
        # Try to get plain text body
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode('utf-8', errors='replace')
        else:
            if msg.get_content_type() == "text/plain":
                payload = msg.get_payload(decode=True)
                if payload:
                    return payload.decode('utf-8', errors='replace')
        
        # Fallback: try to get any text content without decoding
        body = msg.get_body(preferencelist=('plain', 'html'))
        if body:
            content = body.get_content()
            if content:
                return content
        
        # Last resort: get payload as string, but preserve the original if decoding fails
        payload = msg.get_payload()
        if isinstance(payload, bytes):
            return payload.decode('utf-8', errors='replace')
        elif isinstance(payload, str):
            return payload
        
        # If all else fails, extract text from the raw email after headers
        lines = raw_email.split('\n')
        body_started = False
        body_lines = []
        
        for line in lines:
            if body_started:
                body_lines.append(line)
            elif line.strip() == '':  # Empty line indicates start of body
                body_started = True
        
        return '\n'.join(body_lines)
        
    except Exception as e:
        logger.warning(f"Failed to parse email body: {e}")
        # Fallback: extract everything after the first empty line
        lines = raw_email.split('\n')
        body_started = False
        body_lines = []
        
        for line in lines:
            if body_started:
                body_lines.append(line)
            elif line.strip() == '':
                body_started = True
        
        return '\n'.join(body_lines) if body_lines else raw_email


def extract_price_info(text: str) -> Dict[str, Optional[Any]]:
    """Extract price and currency information from text."""
    price_info = {"price": None, "currency": None}
    
    # First, try to find price with currency symbol together
    price_matches = list(PRICE_PATTERN.finditer(text))
    
    for match in price_matches:
        currency_symbol = match.group(1)  # Currency symbol from price pattern
        price_str = match.group(2)  # Number part
        
        try:
            clean_price = price_str.replace(',', '')
            price_value = float(clean_price)
            
            # Basic validation: reasonable price range
            if 0.01 <= price_value <= 1000000:
                price_info["price"] = price_value
                if currency_symbol:
                    price_info["currency"] = currency_symbol
                break
        except ValueError:
            continue
    
    # If no currency found in price pattern, look for separate currency indicators
    if price_info["price"] is not None and price_info["currency"] is None:
        currency_matches = CURRENCY_PATTERN.findall(text)
        if currency_matches:
            # Take the first currency found
            for currency_match in currency_matches:
                currency = currency_match[0] if currency_match[0] else currency_match[1]
                if currency:
                    price_info["currency"] = currency
                    break
    
    return price_info


def extract_lead_time_info(text: str) -> Dict[str, Optional[Any]]:
    """Extract lead time information from text."""
    lead_time_info = {"lead_time": None, "lead_time_unit": None}
    
    # Look for lead time patterns
    lead_match = LEAD_TIME_PATTERN.search(text)
    if lead_match:
        try:
            lead_time_info["lead_time"] = int(lead_match.group(1))
            lead_time_info["lead_time_unit"] = lead_match.group(2).lower()
        except ValueError:
            pass
    
    return lead_time_info


def extract_offer(raw_email: str) -> Dict[str, Any]:
    """
    Extract offer information from a raw email string.
    
    Args:
        raw_email: Raw email content as string
        
    Returns:
        Dictionary containing extracted offer information:
        - price: Extracted price as float, or None
        - currency: Currency symbol/code, or None  
        - lead_time: Lead time number, or None
        - lead_time_unit: Lead time unit (day/week/month), or None
        - email_body: Full email body text
        - subject: Email subject line
        - from_email: Sender email address
    """
    try:
        # Parse email headers
        msg = email.message_from_string(raw_email)
        subject = msg.get('Subject', '')
        from_email = msg.get('From', '')
        
        # Extract email body
        body = extract_email_body(raw_email)
        
        # Extract price information
        price_info = extract_price_info(body)
        
        # Extract lead time information
        lead_time_info = extract_lead_time_info(body)
        
        # Combine all extracted information
        offer = {
            "price": price_info["price"],
            "currency": price_info["currency"],
            "lead_time": lead_time_info["lead_time"],
            "lead_time_unit": lead_time_info["lead_time_unit"],
            "email_body": body,
            "subject": subject,
            "from_email": from_email
        }
        
        logger.info(f"Extracted offer: price={offer['price']}, lead_time={offer['lead_time']} {offer['lead_time_unit']}")
        
        return offer
        
    except Exception as e:
        logger.error(f"Failed to extract offer from email: {e}")
        return {
            "price": None,
            "currency": None,
            "lead_time": None,
            "lead_time_unit": None,
            "email_body": raw_email,
            "subject": "",
            "from_email": ""
        } 