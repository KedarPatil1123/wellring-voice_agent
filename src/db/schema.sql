-- =============================================================================
-- WellRing PostgreSQL Schema
-- =============================================================================
-- Based on ER Diagram (designed Jun 2026)
--
-- Tables:
--   1. users          — Stores elderly user & caregiver information
--   2. assessments    — Stores health assessments and scoring results
--   3. alerts         — Stores all alert / notification records
--   4. conversations  — Stores conversation history between user and Riley
--   5. health_history — Stores symptom history for escalation & trend analysis
--
-- Relationships (all 1:N):
--   users        → assessments
--   assessments  → alerts
--   users        → conversations
--   users        → health_history
-- =============================================================================

-- Enable pg_trgm for full-text symptom search (optional, nice to have)
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------------------------------------------------------------------------
-- 1. USERS
-- ---------------------------------------------------------------------------
-- Stores both elderly users AND caregivers.
-- A caregiver row links back to the elderly user via 'caregiver_for_user_id'.

CREATE TABLE IF NOT EXISTS users (
    user_id         UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT            NOT NULL,
    age             INTEGER         CHECK (age > 0 AND age < 150),
    role            TEXT            NOT NULL DEFAULT 'elderly'
                                    CHECK (role IN ('elderly', 'caregiver')),

    -- Contact info
    phone           TEXT,
    email           TEXT,

    -- Medical baseline
    medical_conditions  TEXT[],          -- e.g. ARRAY['diabetes', 'hypertension']
    medications         TEXT[],

    -- Caregiver link: if this user IS a caregiver, point to their elderly user
    caregiver_for_user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,

    -- Caregiver contact (denormalised for fast alert lookup)
    caregiver_name  TEXT,
    caregiver_phone TEXT,
    caregiver_email TEXT,

    -- Timestamps
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_caregiver_for ON users(caregiver_for_user_id);


-- ---------------------------------------------------------------------------
-- 2. ASSESSMENTS
-- ---------------------------------------------------------------------------
-- Each voice interaction that triggers a health risk assessment.
-- Maps directly to what POST /assess returns.

CREATE TABLE IF NOT EXISTS assessments (
    assessment_id   UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID            NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Input captured from Vapi / frontend
    intent          TEXT            NOT NULL DEFAULT 'health_issue',
    symptoms        TEXT[]          NOT NULL DEFAULT '{}',
    severity        TEXT            NOT NULL
                                    CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    confidence      NUMERIC(4,3)    NOT NULL DEFAULT 1.000
                                    CHECK (confidence >= 0 AND confidence <= 1),

    -- Scoring engine output
    score           INTEGER         NOT NULL,
    base_score      INTEGER         NOT NULL,
    risk_level      TEXT            NOT NULL
                                    CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    category        TEXT            NOT NULL,  -- e.g. 'CARDIAC', 'NEUROLOGICAL', 'FALL'
    action          TEXT            NOT NULL,  -- e.g. 'notify_caregiver_and_emergency_services'
    message         TEXT            NOT NULL,
    steps           TEXT[]          NOT NULL DEFAULT '{}',
    breakdown       TEXT[]          NOT NULL DEFAULT '{}',

    -- Vapi metadata
    vapi_call_id    TEXT,
    recording_url   TEXT,

    -- Timestamp
    assessed_at     TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_assessments_user_id   ON assessments(user_id);
CREATE INDEX IF NOT EXISTS idx_assessments_risk_level ON assessments(risk_level);
CREATE INDEX IF NOT EXISTS idx_assessments_assessed_at ON assessments(assessed_at DESC);
-- Symptom look-up: supports @> (contains) queries
CREATE INDEX IF NOT EXISTS idx_assessments_symptoms ON assessments USING GIN(symptoms);


-- ---------------------------------------------------------------------------
-- 3. ALERTS
-- ---------------------------------------------------------------------------
-- Every notification fired after an assessment (SMS, call, email, push, etc.)
-- One assessment can trigger multiple alerts (e.g. SMS + email simultaneously).

CREATE TABLE IF NOT EXISTS alerts (
    alert_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id   UUID            NOT NULL REFERENCES assessments(assessment_id) ON DELETE CASCADE,

    alert_type      TEXT            NOT NULL
                                    CHECK (alert_type IN (
                                        'sms', 'call', 'email', 'push',
                                        'emergency_services', 'in_app'
                                    )),
    status          TEXT            NOT NULL DEFAULT 'pending'
                                    CHECK (status IN ('pending', 'sent', 'delivered', 'failed')),

    -- Who was notified
    recipient_name  TEXT,
    recipient_phone TEXT,
    recipient_email TEXT,

    -- Optional raw payload / error
    payload         JSONB,
    error_message   TEXT,

    -- Timestamps
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    sent_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_alerts_assessment_id ON alerts(assessment_id);
CREATE INDEX IF NOT EXISTS idx_alerts_status        ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_alert_type    ON alerts(alert_type);


-- ---------------------------------------------------------------------------
-- 4. CONVERSATIONS
-- ---------------------------------------------------------------------------
-- Stores each voice/text conversation turn with Riley.
-- A conversation is a session; each message is a row.

CREATE TABLE IF NOT EXISTS conversations (
    conversation_id UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID            NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Link to the assessment triggered mid-session (nullable)
    assessment_id   UUID            REFERENCES assessments(assessment_id) ON DELETE SET NULL,

    -- Vapi session identifiers
    vapi_call_id    TEXT,
    channel         TEXT            NOT NULL DEFAULT 'web'
                                    CHECK (channel IN ('web', 'phone', 'whatsapp')),

    -- Conversation payload
    role            TEXT            NOT NULL
                                    CHECK (role IN ('user', 'assistant', 'system')),
    content         TEXT            NOT NULL,

    -- Audio
    audio_url       TEXT,
    duration_secs   INTEGER,

    -- Timestamp
    spoken_at       TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_id      ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_vapi_call_id ON conversations(vapi_call_id);
CREATE INDEX IF NOT EXISTS idx_conversations_spoken_at    ON conversations(spoken_at DESC);


-- ---------------------------------------------------------------------------
-- 5. HEALTH_HISTORY
-- ---------------------------------------------------------------------------
-- Aggregated daily/weekly symptom log for trend analysis & escalation scoring.
-- The scoring engine reads this table to apply the history multiplier.

CREATE TABLE IF NOT EXISTS health_history (
    health_id       UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID            NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- The symptom key (matches scoring engine keys, e.g. 'chest_pain')
    symptom         TEXT            NOT NULL,

    -- Aggregate window
    window_start    TIMESTAMPTZ     NOT NULL,
    window_end      TIMESTAMPTZ     NOT NULL,
    occurrence_count INTEGER        NOT NULL DEFAULT 1,

    -- Peak severity observed in this window
    peak_severity   TEXT            CHECK (peak_severity IN ('low', 'medium', 'high', 'critical')),
    peak_risk_level TEXT            CHECK (peak_risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),

    -- Link to triggering assessment (most recent in window)
    last_assessment_id UUID         REFERENCES assessments(assessment_id) ON DELETE SET NULL,

    -- Escalation flag: set when count crosses threshold
    escalation_flagged BOOLEAN      NOT NULL DEFAULT FALSE,

    -- Timestamps
    recorded_at     TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_health_history_user_id  ON health_history(user_id);
CREATE INDEX IF NOT EXISTS idx_health_history_symptom  ON health_history(symptom);
CREATE INDEX IF NOT EXISTS idx_health_history_window   ON health_history(user_id, symptom, window_start DESC);


-- ---------------------------------------------------------------------------
-- Trigger: auto-update users.updated_at on row change
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();
