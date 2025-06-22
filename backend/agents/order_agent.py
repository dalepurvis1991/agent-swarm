from typing import Dict, Optional
import json
from datetime import datetime
import os
from ..database import get_db
from ..notifications.push import send_push

class OrderAgent:
    def __init__(self, db_connection):
        self.db = db_connection
        
    def send_purchase_order(self, offer_id: int) -> Dict:
        """Process a purchase order for an accepted offer"""
        try:
            # Get offer details
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT o.id, o.supplier_id, o.price, o.product_id,
                       s.name as supplier_name, s.email as supplier_email,
                       p.name as product_name, p.specification
                FROM offers o
                JOIN suppliers s ON o.supplier_id = s.id
                JOIN products p ON o.product_id = p.id
                WHERE o.id = %s
            """, (offer_id,))
            
            offer = cursor.fetchone()
            if not offer:
                return {"status": "error", "message": "Offer not found"}
                
            # Generate PO number
            po_number = f"PO-{datetime.now().strftime('%Y%m%d')}-{offer_id:04d}"
            
            # Prepare PO email content
            email_content = self._prepare_po_email(
                po_number=po_number,
                supplier_name=offer['supplier_name'],
                product_name=offer['product_name'],
                price=offer['price'],
                specification=offer['specification']
            )
            
            # Send email (implement your email sending logic here)
            # send_email(offer['supplier_email'], f"Purchase Order {po_number}", email_content)
            
            # Update offer status
            cursor.execute("""
                UPDATE offers
                SET status = 'ordered',
                    po_number = %s,
                    ordered_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id
            """, (po_number, offer_id))
            self.db.commit()
            
            # Send push notification
            send_push(
                title="Purchase Order Sent",
                body=f"PO {po_number} has been sent to {offer['supplier_name']}",
                data={
                    "type": "po_sent",
                    "offer_id": offer_id,
                    "po_number": po_number
                }
            )
            
            return {
                "status": "success",
                "message": "Purchase order sent",
                "po_number": po_number
            }
            
        except Exception as e:
            self.db.rollback()
            return {"status": "error", "message": str(e)}
            
    def _prepare_po_email(self, **kwargs) -> str:
        """Prepare purchase order email content"""
        with open('backend/email_templates/po.txt', 'r') as f:
            template = f.read()
            
        # Replace placeholders
        for key, value in kwargs.items():
            template = template.replace(f"{{{key}}}", str(value))
            
        return template 