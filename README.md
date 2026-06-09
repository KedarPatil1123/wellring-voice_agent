# WellRing Voice Agent Platform

An AI-powered, voice-first health assistant for elderly people. WellRing listens, understands, and responds in real-time over the phone or web, utilizing a clinical scoring engine to detect emergencies and instantly alert caregivers.

## 🌟 Architecture Overview

WellRing has evolved into a production-ready cloud platform:

- **Voice Orchestration (Vapi):** Handles real-time WebRTC/telephony, utilizing **Deepgram** for ultra-fast Speech-to-Text and **Cartesia** for natural, low-latency Text-to-Speech.
- **Intelligence (Gemini 1.5 Flash):** Replaced local LLMs with Google's Gemini API for flawless symptom extraction (using Structured Outputs) and empathetic conversational generation.
- **Scoring Engine (FastAPI):** A decoupled backend that receives `AssessRequest` function calls from Vapi to calculate clinical risk (Low, Medium, High, Critical).
- **Caregiver Dashboard (React + Vite):** A modern frontend where caregivers can view patient status, review assessment history, and even call the agent directly via the embedded Vapi Web SDK.
- **Alerts (Twilio):** Automatically dispatches SMS or WhatsApp messages to caregivers when a high or critical risk is detected.

## 📂 Project Structure

```text
wellring-voice_agent/
├── frontend/              ← React Caregiver Dashboard
│   ├── src/pages/         ← Dashboard, Patients, History
│   ├── src/components/    ← UI Components (including Vapi VoiceWidget)
│   └── package.json       
├── src/                   ← FastAPI Backend & Scoring Engine
│   ├── main.py            ← Entrypoint (`POST /assess`)
│   ├── notifications.py   ← Twilio / WhatsApp dispatch
│   └── scoring_engine/    ← Risk calculation logic
├── vapi_assistant.json    ← Vapi cloud blueprint
├── voice_health.py        ← Local hardware testing script (Gemini)
├── .github/workflows/     ← CI/CD pipeline
└── render.yaml            ← Backend deployment config
```

## 🚀 Setup Instructions

### 1. Backend API (FastAPI)

1. Clone the repository and create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the environment template:
   ```bash
   cp .env.example .env
   ```
   *Fill in your Gemini API key and Twilio credentials.*
4. Start the server:
   ```bash
   uvicorn src.main:app --reload --port 8000
   ```

### 2. Frontend Dashboard (React)

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Copy the environment template:
   ```bash
   cp .env.example .env
   ```
   *Fill in your Vapi Client Key and Assistant ID.*
4. Start the development server:
   ```bash
   npm run dev
   ```

### 3. Vapi Cloud Setup

To enable the actual voice calling functionality:
1. Go to the [Vapi Dashboard](https://dashboard.vapi.ai/).
2. Click **Create Assistant** and select **Import JSON**.
3. Upload the `vapi_assistant.json` file from the root of this repository.
4. Add your **Gemini** and **Cartesia** API keys to the Vapi Provider Settings.
5. (Optional) Link a Twilio phone number to accept incoming phone calls.

## 🚨 Emergency Detection

The system automatically detects critical keywords during the conversation:
- Chest pain
- Difficulty breathing
- Fallen down
- Unconscious
- Stroke symptoms

On detection, the Gemini model is instructed to immediately instruct the patient to call emergency services (112/911), while the backend simultaneously dispatches a critical SMS/WhatsApp alert to the assigned caregiver.
