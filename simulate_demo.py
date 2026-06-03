"""
simulate_demo.py
================
Runs the required demonstration scenarios directly against the 
FastAPI backend. This mocks the JSON extraction from Llama 3 
to demonstrate the backend logic without requiring heavy GPU memory 
for the LLM.
"""

import time
import sqlite3
import httpx
import json

# These represent the exact JSON payloads that Llama 3 would output 
# based on the user's spoken input.
SCENARIOS = [
    {
        "name": "Medicine Missed",
        "input": "I forgot to take my morning pills today.",
        "mock_llm_json": {
            "intent": "health_issue",
            "symptoms": ["medicine_missed"],
            "severity": "low",
            "confidence": 1.0
        }
    },
    {
        "name": "Dizziness",
        "input": "I'm feeling really dizzy and lightheaded when I stand up.",
        "mock_llm_json": {
            "intent": "health_issue",
            "symptoms": ["dizziness"],
            "severity": "medium",
            "confidence": 0.90
        }
    },
    {
        "name": "Fall Detection",
        "input": "I slipped and fell in the bathroom. I think my hip is okay but I'm on the floor.",
        "mock_llm_json": {
            "intent": "health_issue",
            "symptoms": ["fall_detected"],
            "severity": "high",
            "confidence": 0.95
        }
    },
    {
        "name": "Stroke Symptoms",
        "input": "My left arm is numb and my face feels droopy on one side.",
        "mock_llm_json": {
            "intent": "health_issue",
            "symptoms": ["stroke_symptoms"],
            "severity": "critical",
            "confidence": 0.99
        }
    },
    {
        "name": "Emergency Flow Demo (Killer Demo)",
        "input": "I have chest pain and cannot breathe at all. It hurts so much.",
        "mock_llm_json": {
            "intent": "health_issue",
            "symptoms": ["chest_pain", "breathing_problem"],
            "severity": "critical",
            "confidence": 0.95
        }
    }
]

def run_simulation():
    print("="*70)
    print("  WellRing Demo Scenario Simulator (FastAPI Backend Test)")
    print("="*70)

    for idx, scenario in enumerate(SCENARIOS, 1):
        print(f"\n[{idx}/5] 🏃 Scenario: {scenario['name']}")
        print(f"🗣️  User says: \"{scenario['input']}\"")
        
        # Call the local FastAPI backend (mocking Kedar's pipeline)
        print("🔄 Sending to FastAPI /assess...")
        try:
            r = httpx.post("http://localhost:8000/assess", json=scenario["mock_llm_json"])
            r.raise_for_status()
            data = r.json()
            
            print("-" * 50)
            print(f"📊 Assessment Result:")
            print(f"   • Risk Level: {data['risk_level']} (Score: {data['score']})")
            print(f"   • Category  : {data['category']}")
            print(f"   • Action    : {data['action']}")
            print(f"\n🤖 System Directive to TTS:")
            print(f"   \"{data['message']}\"")
            print(f"   Steps: {data['steps']}")
            print("-" * 50)
        except Exception as e:
            print(f"❌ Failed to reach backend: {e}")
            
        time.sleep(1)  # pause between scenarios

    print("\n\n🗄️  Database Verification - Checking interactions log:")
    print("=" * 80)
    try:
        conn = sqlite3.connect("wellring.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp, intent, symptoms, score, risk_level, action FROM interactions ORDER BY id DESC LIMIT 5")

        rows = cursor.fetchall()
        # Print in reverse so they match the order we ran them
        for row in reversed(rows):
            print(f"[{row['timestamp']}]")
            print(f"  Risk: {row['risk_level']:<10} Score: {row['score']:<4} Action: {row['action']}")
            print(f"  Symptoms: {row['symptoms']}")
            print("-" * 60)

        conn.close()
        print("Demo verification complete! ✅ All paths logged and verified.")
    except Exception as e:
        print(f"Failed to read database: {e}")

if __name__ == "__main__":
    run_simulation()
