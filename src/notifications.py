"""
notifications.py
================
Stubs for sending SMS (Twilio) and Email (SendGrid) alerts
for HIGH and CRITICAL risk levels.
"""

import logging
from typing import Dict, Any
import datetime
from src.repository import save_alert

logger = logging.getLogger(__name__)

# In a real implementation, we would load these from environment variables
TWILIO_ACCOUNT_SID = "mock_twilio_sid"
TWILIO_AUTH_TOKEN = "mock_twilio_token"
CAREGIVER_PHONE = "+1234567890"
SYSTEM_PHONE = "+0987654321"

def send_sms_alert(interaction_id: int, risk_level: str, message: str) -> bool:
    """
    Mock function to send an SMS alert to the caregiver.
    """
    logger.info(f"🚨 [SMS ALERT to {CAREGIVER_PHONE}] {risk_level}: {message}")
    
    # Mock Twilio API call here
    # client.messages.create(body=message, from_=SYSTEM_PHONE, to=CAREGIVER_PHONE)
    
    # Log the alert
    save_alert(
        assessment_id=interaction_id,
        alert_type=risk_level,
        status="sent",
        recipient_phone=CAREGIVER_PHONE
    )
    
    return True

def trigger_alerts_if_needed(interaction_id: int, risk_level: str, message: str):
    """
    Determines if an alert needs to be sent based on risk level.
    """
    if risk_level in ["HIGH", "CRITICAL"]:
        send_sms_alert(interaction_id, risk_level, message)
