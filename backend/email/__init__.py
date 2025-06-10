"""Email handling module for outgoing RFQs and incoming quote parsing."""

from .outgoing import send_rfq
from .parser import extract_offer

__all__ = ["send_rfq", "extract_offer"] 