-- Schema for WellRing Voice Agent

-- 1. Users Table (stores both patients and caregivers for MVP)
CREATE TABLE IF NOT EXISTS Users (
    user_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    age INT,
    role VARCHAR(50) CHECK (role IN ('patient', 'caregiver')),
    phone VARCHAR(50),
    emergency_contact VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Assessments Table (Core health evaluation record)
CREATE TABLE IF NOT EXISTS Assessments (
    assessment_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    symptoms TEXT,
    risk_level VARCHAR(50) CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    score INT,
    severity VARCHAR(50),
    confidence FLOAT,
    action TEXT,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);

-- 3. Alerts Table (Notification records)
CREATE TABLE IF NOT EXISTS Alerts (
    alert_id SERIAL PRIMARY KEY,
    assessment_id INT NOT NULL,
    alert_type VARCHAR(50) CHECK (alert_type IN ('HIGH_RISK', 'CRITICAL', 'EMERGENCY')),
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
    recipient_phone VARCHAR(50), -- Improvement: Added recipient contact
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assessment_id) REFERENCES Assessments(assessment_id) ON DELETE CASCADE
);

-- 4. Conversation Table (Audit trail of voice/text interactions)
CREATE TABLE IF NOT EXISTS Conversation (
    conversation_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    message TEXT,
    direction VARCHAR(50) CHECK (direction IN ('inbound', 'outbound')),
    audio_path TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);

-- 5. Health_History Table (Long-term symptom tracking)
CREATE TABLE IF NOT EXISTS Health_History (
    health_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    assessment_id INT, -- Improvement: Linked back to Assessment to avoid duplication
    symptom TEXT,
    frequency VARCHAR(100),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Improvement: Added timestamp
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (assessment_id) REFERENCES Assessments(assessment_id) ON DELETE SET NULL
);
