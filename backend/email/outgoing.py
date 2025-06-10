"""Outgoing email functionality for sending RFQs to suppliers."""

import os
import logging
from email.message import EmailMessage
from typing import Optional
import aiosmtplib

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    """Exception raised when email sending fails."""
    pass


def get_smtp_config() -> dict:
    """Get SMTP configuration from environment variables."""
    config = {
        "SMTP_HOST": os.getenv("SMTP_HOST", "localhost"),
        "SMTP_PORT": os.getenv("SMTP_PORT", "1025"),
        "SMTP_USER": os.getenv("SMTP_USER", "test@example.com"),
        "SMTP_PASS": os.getenv("SMTP_PASS", "")
    }
    return config


async def send_rfq(to: str, spec: str, sender_name: Optional[str] = None) -> None:
    """
    Send an RFQ (Request for Quote) email to a supplier.
    
    Args:
        to: Supplier email address
        spec: Product specification to quote for
        sender_name: Optional sender name for personalization
    
    Raises:
        EmailSendError: If email sending fails
    """
    if not to or not spec:
        raise EmailSendError("Recipient email and specification are required")
    
    smtp_config = get_smtp_config()
    
    # Create email message
    msg = EmailMessage()
    msg["From"] = smtp_config["SMTP_USER"]
    msg["To"] = to
    msg["Subject"] = f"RFQ: {spec[:50]}..." if len(spec) > 50 else f"RFQ: {spec}"
    
    # Email body with professional format
    sender_signature = f"\n\nBest regards,\n{sender_name}" if sender_name else "\n\nBest regards,\nProcurement Team"
    
    email_body = f"""Dear Supplier,

We are interested in obtaining a quote for the following specification:

{spec}

Please provide:
- Unit price and currency
- Minimum order quantity
- Lead time for delivery
- Any additional terms or conditions

We look forward to your competitive quote.{sender_signature}

---
This is an automated RFQ. Please reply with your quote details.
"""
    
    msg.set_content(email_body)
    
    try:
        # Send email using aiosmtplib
        await aiosmtplib.send(
            msg,
            hostname=smtp_config["SMTP_HOST"],
            port=int(smtp_config["SMTP_PORT"]),
            username=smtp_config["SMTP_USER"] if smtp_config["SMTP_PASS"] else None,
            password=smtp_config["SMTP_PASS"] if smtp_config["SMTP_PASS"] else None,
            use_tls=False,  # MailHog doesn't use TLS
            start_tls=False
        )
        
        logger.info(f"RFQ sent successfully to {to} for spec: {spec[:30]}...")
        
    except Exception as e:
        error_msg = f"Failed to send RFQ to {to}: {str(e)}"
        logger.error(error_msg)
        raise EmailSendError(error_msg) from e 