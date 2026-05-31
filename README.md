# WellRing Voice Agent 

An AI-powered voice health assistant for elderly people that listens, understands, and responds in real-time.

## What it does
- Listens to the elderly person's voice
-  Understands using Llama 3
- Detects emergencies and triggers ALERT
-  Speaks the response back out loud
-  Saves every recording numbered (recording1.wav, recording2.wav...)

## Project Structure

wellring-voice_agent/
├── voice_health.py        ← Main voice agent
├── tests/
│   ├── test_llama.py      ← Tests Llama 3
│   ├── test_mic.py        ← Tests microphone
│   ├── test_mic_whisper.py← Tests Whisper STT
│   └── test_piper.py      ← Tests Piper TTS
├── audios/                ← Recorded audio files
├── .github/workflows/     ← CI/CD pipeline
├── requirements.txt       ← Python dependencies
└── README.md

## Setup Instructions

### Prerequisites
- Python 3.9+
- Git
- Ollama (download from ollama.com)
- ffmpeg (download from gyan.dev/ffmpeg/builds)

### Installation

**1. Clone the repo:**
**2. Create virtual environment:**
**3. Install dependencies:**
**4. Download Llama 3:**

**5. Download Piper voice model:**
- Go to https://rhasspy.github.io/piper-samples/
- Download `en_US-ryan-high.onnx` and `en_US-ryan-high.onnx.json`
- Place both files in the project root folder

### Run the voice agent:

Press ENTER to speak. The agent will listen, respond and speak back.

## Emergency Detection
The agent automatically detects emergency keywords:
- Chest pain
- Difficulty breathing
- Fallen down
- Unconscious
- Stroke
- Bleeding

On detection it immediately responds with:
ALERT - Please call emergency services immediately on 112

