import os
import json
import requests
from typing import Dict, Optional
from firebase_admin import messaging
import firebase_admin
from firebase_admin import credentials

class PushNotificationService:
    def __init__(self):
        # Initialize Firebase Admin SDK
        cred = credentials.Certificate(os.getenv('FIREBASE_CREDENTIALS_PATH'))
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
            
    def send_push(self, title: str, body: str, data: Optional[Dict] = None) -> bool:
        """
        Send a push notification using Firebase Cloud Messaging
        
        Args:
            title: Notification title
            body: Notification body text
            data: Optional data payload
            
        Returns:
            bool: True if notification was sent successfully
        """
        try:
            # Create message
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data or {},
                topic='offers'  # Send to all subscribed devices
            )
            
            # Send message
            response = messaging.send(message)
            print(f'Successfully sent message: {response}')
            return True
            
        except Exception as e:
            print(f'Error sending push notification: {e}')
            return False
            
    def send_expo_push(self, token: str, title: str, body: str, data: Optional[Dict] = None) -> bool:
        """
        Send a push notification using Expo Push Notification Service
        
        Args:
            token: Expo push token
            title: Notification title
            body: Notification body text
            data: Optional data payload
            
        Returns:
            bool: True if notification was sent successfully
        """
        try:
            # Prepare message
            message = {
                'to': token,
                'sound': 'default',
                'title': title,
                'body': body,
                'data': data or {}
            }
            
            # Send message
            response = requests.post(
                'https://exp.host/--/api/v2/push/send',
                json=message,
                headers={
                    'Accept': 'application/json',
                    'Accept-encoding': 'gzip, deflate',
                    'Content-Type': 'application/json'
                }
            )
            
            response.raise_for_status()
            return True
            
        except Exception as e:
            print(f'Error sending Expo push notification: {e}')
            return False

# Create global instance
push_service = PushNotificationService()

def send_push(title: str, body: str, data: Optional[Dict] = None) -> bool:
    """Global function to send push notifications"""
    return push_service.send_push(title, body, data) 