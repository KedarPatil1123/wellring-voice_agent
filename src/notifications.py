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
from typing import Dict, Any
from src.database import log_alert

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Credentials — loaded from environment (never hardcoded)
# ---------------------------------------------------------------------------
TWILIO_ACCOUNT_SID  = os.environ.get("TWILIO_ACCOUNT_SID",  "mock_twilio_sid")
TWILIO_AUTH_TOKEN   = os.environ.get("TWILIO_AUTH_TOKEN",   "mock_twilio_token")
TWILIO_FROM_PHONE   = os.environ.get("TWILIO_FROM_PHONE",   "+1234567890")
CAREGIVER_PHONE     = os.environ.get("CAREGIVER_PHONE",     "+0987654321")
USE_TWILIO          = os.environ.get("USE_TWILIO",           "false").lower() == "true"


def send_sms_alert(interaction_id: int, risk_level: str, message: str) -> bool:
    """
    Send an SMS alert to the caregiver.
    Uses real Twilio if USE_TWILIO=true, otherwise logs a mock.
    """
    if USE_TWILIO:
        try:
            from twilio.rest import Client
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=f"[WellRing ALERT] {risk_level}: {message}",
                from_=TWILIO_FROM_PHONE,
                to=CAREGIVER_PHONE,
            )
            logger.info(f"[SMS SENT to {CAREGIVER_PHONE}] {risk_level}: {message}")
        except Exception as e:
            logger.error(f"[SMS FAILED] {e}")
            return False
    else:
        logger.info(f"🚨 [SMS MOCK to {CAREGIVER_PHONE}] {risk_level}: {message}")

    log_alert(
        interaction_id=interaction_id,
        timestamp=datetime.datetime.utcnow().isoformat() + "Z",
        risk_level=risk_level,
        notification_type="SMS",
        status="sent" if USE_TWILIO else "mock",
    )
    return True


def trigger_alerts_if_needed(interaction_id: int, risk_level: str, message: str):
    """
    Determines if an alert needs to be sent based on risk level.
    Fires for HIGH and CRITICAL only.
    """
    if risk_level in ["HIGH", "CRITICAL"]:
        send_sms_alert(interaction_id, risk_level, message)
