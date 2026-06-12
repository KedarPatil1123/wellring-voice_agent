import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from db_session import SessionLocal
from models import User, Assessment, Alert, Conversation, HealthHistory

logger = logging.getLogger(__name__)

def get_symptom_history(user_id: int, days: int = 3) -> Dict[str, int]:
    """Returns frequency of symptoms over the last N days for a user."""
    counts = {}
    with SessionLocal() as db:
        cutoff = datetime.utcnow() - timedelta(days=days)
        histories = db.query(HealthHistory).filter(
            HealthHistory.user_id == user_id,
            HealthHistory.recorded_at >= cutoff
        ).all()
        for h in histories:
            if h.symptom:
                counts[h.symptom] = counts.get(h.symptom, 0) + 1
    return counts

def save_assessment(
    user_id: int, 
    symptoms: List[str], 
    risk_level: Optional[str], 
    score: Optional[int], 
    severity: Optional[str], 
    confidence: Optional[float], 
    action: Optional[str], 
    message: Optional[str]
) -> int:
    """Saves assessment and updates health history. Returns assessment_id."""
    with SessionLocal() as db:
        try:
            assessment = Assessment(
                user_id=user_id,
                symptoms=",".join(symptoms) if symptoms else "",
                risk_level=risk_level,
                score=score,
                severity=severity,
                confidence=confidence,
                action=action,
                message=message
            )
            db.add(assessment)
            db.commit()
            db.refresh(assessment)

            # Insert into health history
            if symptoms:
                for sym in symptoms:
                    hh = HealthHistory(
                        user_id=user_id,
                        assessment_id=assessment.assessment_id,
                        symptom=sym,
                        frequency="occurrence"
                    )
                    db.add(hh)
                db.commit()
                
            return assessment.assessment_id
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save assessment: {e}")
            raise

def save_alert(assessment_id: int, alert_type: str, status: str = "sent", recipient_phone: str = "") -> int:
    """Saves alert log. Returns alert_id."""
    with SessionLocal() as db:
        try:
            alert = Alert(
                assessment_id=assessment_id,
                alert_type=alert_type,
                status=status,
                recipient_phone=recipient_phone
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)
            return alert.alert_id
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save alert: {e}")
            raise

def save_conversation(user_id: int, message: str, direction: str, audio_path: str = "") -> int:
    """Saves conversation message. Returns conversation_id."""
    with SessionLocal() as db:
        try:
            conv = Conversation(
                user_id=user_id,
                message=message,
                direction=direction,
                audio_path=audio_path
            )
            db.add(conv)
            db.commit()
            db.refresh(conv)
            return conv.conversation_id
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save conversation: {e}")
            raise
