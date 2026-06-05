# Database Schema

The system supports both SQLite and Supabase PostgreSQL.

## `interactions`

Logs every health assessment.

| Column | Type | Description |
|---|---|---|
| `id` | BigInt / Integer | Primary Key |
| `user_id` | Text / UUID | Reference to the `users` table |
| `timestamp` | Timestamptz | ISO-8601 UTC time of assessment |
| `intent` | Text | Captured intent (e.g., `health_issue`) |
| `symptoms` | JSONB / Text | List of extracted symptoms |
| `severity` | Text | Extracted severity (`low`, `critical`, etc.) |
| `confidence` | Float / Real | LLM extraction confidence (0.0 - 1.0) |
| `score` | Integer | Calculated risk score |
| `risk_level` | Text | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `category` | Text | Primary symptom category |
| `action` | Text | Taken action (e.g., `notify_caregiver`) |
| `message` | Text | Response message given to user |

## `alerts_log`

Tracks external notifications sent (e.g., SMS).

| Column | Type | Description |
|---|---|---|
| `id` | BigInt / Integer | Primary Key |
| `interaction_id` | BigInt / Integer | Foreign Key to `interactions` |
| `timestamp` | Timestamptz | ISO-8601 UTC time sent |
| `risk_level` | Text | Risk level that triggered the alert |
| `notification_type`| Text | e.g., `SMS` |
| `status` | Text | `sent`, `mock`, `failed` |

## `users`

Stores patient profiles and caregiver contacts.

| Column | Type | Description |
|---|---|---|
| `id` | UUID / Text | Primary Key |
| `name` | Text | Patient Name |
| `age` | Integer | Patient Age |
| `medical_conditions`| Text / Array | Known prior conditions |
| `caregiver_name` | Text | Name of primary caregiver |
| `caregiver_phone` | Text | SMS contact number (+1234567890) |
