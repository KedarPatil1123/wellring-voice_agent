from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, TIMESTAMP, func
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    age = Column(Integer, nullable=True)
    role = Column(String(50)) # 'patient' or 'caregiver'
    phone = Column(String(50), nullable=True)
    emergency_contact = Column(String(50), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    assessments = relationship('Assessment', back_populates='user', cascade="all, delete-orphan")
    conversations = relationship('Conversation', back_populates='user', cascade="all, delete-orphan")
    health_histories = relationship('HealthHistory', back_populates='user', cascade="all, delete-orphan")


class Assessment(Base):
    __tablename__ = 'assessments'
    
    assessment_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete="CASCADE"), nullable=False)
    symptoms = Column(Text, nullable=True)
    risk_level = Column(String(50)) # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    score = Column(Integer, nullable=True)
    severity = Column(String(50), nullable=True)
    confidence = Column(Float, nullable=True)
    action = Column(Text, nullable=True)
    message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    user = relationship('User', back_populates='assessments')
    alerts = relationship('Alert', back_populates='assessment', cascade="all, delete-orphan")
    health_histories = relationship('HealthHistory', back_populates='assessment')


class Alert(Base):
    __tablename__ = 'alerts'
    
    alert_id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey('assessments.assessment_id', ondelete="CASCADE"), nullable=False)
    alert_type = Column(String(50)) # 'HIGH_RISK', 'CRITICAL', 'EMERGENCY'
    status = Column(String(50), default='pending') # 'pending', 'sent', 'failed'
    recipient_phone = Column(String(50), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    assessment = relationship('Assessment', back_populates='alerts')


class Conversation(Base):
    __tablename__ = 'conversation'
    
    conversation_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete="CASCADE"), nullable=False)
    message = Column(Text, nullable=True)
    direction = Column(String(50)) # 'inbound' or 'outbound'
    audio_path = Column(Text, nullable=True)
    timestamp = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    user = relationship('User', back_populates='conversations')


class HealthHistory(Base):
    __tablename__ = 'health_history'
    
    health_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete="CASCADE"), nullable=False)
    assessment_id = Column(Integer, ForeignKey('assessments.assessment_id', ondelete="SET NULL"), nullable=True)
    symptom = Column(Text, nullable=True)
    frequency = Column(String(100), nullable=True)
    recorded_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    user = relationship('User', back_populates='health_histories')
    assessment = relationship('Assessment', back_populates='health_histories')
