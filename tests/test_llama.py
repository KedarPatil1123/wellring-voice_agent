import ollama

response = ollama.chat(
    model="llama3",
    messages=[
        {
            "role": "system",
            "content": """You are a health assistant for elderly people.

STRICT RULES - follow these exactly:
1. If the user mentions ANY of these words: chest pain, heart, breathing, fallen, unconscious, bleeding, stroke - you MUST start your reply with: ALERT - Please call emergency services immediately on 112
2. After the alert, then ask follow up questions calmly
3. Always speak in very simple short sentences
4. Never use difficult medical words
5. Be warm and caring like a family member"""
        },
        {
            "role": "user",
            "content": "I have been having chest pain since morning"
        }
    ]
)

print(response['message']['content'])