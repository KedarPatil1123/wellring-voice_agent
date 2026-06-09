"""
notifications.py
================
Stubs for sending SMS (Twilio) and Email (SendGrid) alerts
for HIGH and CRITICAL risk levels.

Credentials are loaded from environment variables (via .env file).
Set USE_TWILIO=true to enable real SMS dispatch.
"""

import logging
import os
import datetime
from typing import Dict, Any, Optional
from src.database import log_alert
from src.users import get_caregiver_phone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Credentials — loaded from environment (never hardcoded)
# ---------------------------------------------------------------------------
TWILIO_ACCOUNT_SID  = os.environ.get("TWILIO_ACCOUNT_SID",  "mock_twilio_sid")
TWILIO_AUTH_TOKEN   = os.environ.get("TWILIO_AUTH_TOKEN",   "mock_twilio_token")
TWILIO_FROM_PHONE   = os.environ.get("TWILIO_FROM_PHONE",   "+1234567890")
CAREGIVER_PHONE     = os.environ.get("CAREGIVER_PHONE",     "+0987654321")
USE_TWILIO          = os.environ.get("USE_TWILIO",           "false").lower() == "true"
USE_WHATSAPP        = os.environ.get("USE_WHATSAPP",         "false").lower() == "true"


def send_sms_alert(interaction_id: int, response_data: dict, to_phone: str) -> bool:
    """
    Send an SMS alert to the caregiver.
    Uses real Twilio if USE_TWILIO=true, otherwise logs a mock.
    """
    risk_level = response_data.get("risk_level", "UNKNOWN")
    score = response_data.get("score", 0)
    symptoms = response_data.get("symptoms", [])
    action = response_data.get("action", "unknown")
    
    body = f"🚨 WELLRING ALERT\nRisk: {risk_level}\nScore: {score}\nSymptoms: {', '.join(symptoms)}\nAction: {action}\nCheck dashboard: https://wellring-frontend.vercel.app"

    if USE_TWILIO:
        try:
            from twilio.rest import Client
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            
            # Format numbers for WhatsApp if enabled
            msg_from = f"whatsapp:{TWILIO_FROM_PHONE}" if USE_WHATSAPP and not TWILIO_FROM_PHONE.startswith("whatsapp:") else TWILIO_FROM_PHONE
            msg_to = f"whatsapp:{to_phone}" if USE_WHATSAPP and not to_phone.startswith("whatsapp:") else to_phone
            
            client.messages.create(
                body=body,
                from_=msg_from,
                to=msg_to,
            )
            msg_type = "WHATSAPP" if USE_WHATSAPP else "SMS"
            logger.info(f"[{msg_type} SENT to {to_phone}] {risk_level}")
        except Exception as e:
            logger.error(f"[SMS FAILED] {e}")
            return False
    else:
        logger.info(f"🚨 [SMS MOCK to {to_phone}]\n{body}")

    log_alert(
        interaction_id=interaction_id,
        timestamp=datetime.datetime.utcnow().isoformat() + "Z",
        risk_level=risk_level,
        notification_type="SMS",
        status="sent" if USE_TWILIO else "mock",
    )
    return True


def trigger_alerts_if_needed(interaction_id: int, response_data: dict, user_id: Optional[str] = None):
    """
    Determines if an alert needs to be sent based on risk level.
    Fires for HIGH and CRITICAL only. Routes to the user's caregiver.
    """
    risk_level = response_data.get("risk_level", "LOW")
    if risk_level in ["HIGH", "CRITICAL"]:
        phone = get_caregiver_phone(user_id, CAREGIVER_PHONE)
        send_sms_alert(interaction_id, response_data, to_phone=phone)


def send_whatsapp_reminder(to_phone: str, body: str) -> bool:
    """
    Send a WhatsApp reminder notification.
    Uses Twilio's WhatsApp API if USE_TWILIO=true, otherwise logs a mock.
    """
    if USE_TWILIO:
        try:
            from twilio.rest import Client
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            
            msg_from = f"whatsapp:{TWILIO_FROM_PHONE}" if not TWILIO_FROM_PHONE.startswith("whatsapp:") else TWILIO_FROM_PHONE
            msg_to = f"whatsapp:{to_phone}" if not to_phone.startswith("whatsapp:") else to_phone
            
            client.messages.create(
                body=body,
                from_=msg_from,
                to=msg_to,
            )
            logger.info(f"[WHATSAPP SENT to {to_phone}] Reminder: {body[:30]}...")
            return True
        except Exception as e:
            logger.error(f"[WHATSAPP FAILED] {e}")
            return False
    else:
        logger.info(f"🚨 [WHATSAPP MOCK to {to_phone}]\n{body}")
        return True

