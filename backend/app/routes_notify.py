from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict
from ..notifications.push import send_push

router = APIRouter()

class NotificationRequest(BaseModel):
    title: str
    body: str
    data: Optional[Dict] = None

@router.post("/notify")
async def send_notification(request: NotificationRequest):
    """Send a push notification"""
    try:
        success = send_push(
            title=request.title,
            body=request.body,
            data=request.data
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to send notification"
            )
            
        return {"status": "success", "message": "Notification sent"}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        ) 