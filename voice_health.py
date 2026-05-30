
import ollama

system_prompt = """You are a health assistant for elderly people.

STRICT RULES:
1. If the user mentions chest pain, heart, breathing, fallen, unconscious, bleeding, stroke - start with: ALERT - Please call emergency services immediately on 112
2. After alert, ask follow up questions calmly
3. Always speak in very simple short sentences
4. Never use difficult medical words
5. Be warm and caring like a family member"""

print("Voice Health Assistant Ready!")
print("Type your message below\n")

while True:
    user_text = input("You: ")
    
    if user_text.lower() == "quit":
        print("Goodbye! Stay safe!")
        break
    
    response = ollama.chat(
        model="llama3",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ]
    )
    
    print(f"\nAssistant: {response['message']['content']}\n")
