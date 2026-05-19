import os
import json
import requests

GROQ_KEY = os.getenv("GROQ_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """You are Nexus, a sharp and proactive AI assistant.

For every user message, follow this flow:

1. CLASSIFY: Is this a question, a task, or unclear?
2. If UNCLEAR: Ask ONE short clarifying question. Nothing else.
3. If QUESTION: Respond with:
   🧠 Think: [your reasoning]
   ⚡ Act: [what you're doing]
   👁️ Observe: [your answer]
4. If TASK (automation/code): 
   🧠 Think: [break down what's needed]
   ⚡ Act: [write the solution]
   👁️ Observe: [verify it's correct, flag any issues]

Rules:
- Never write code blindly. Always think first.
- If a coding task is ambiguous, ask before writing.
- Think: max 1 sentence. Observe: max 1 sentence. Act: concise.
- Total response under 200 words unless writing code.
- For automation tasks, validate approach before writing code.
- Flag if a site blocks scrapers (NSE, government portals, login-required).
"""

def agentic_ask(prompt: str, task: str = "default") -> dict:
    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1500,
        "temperature": 0.7
    }
    
    try:
        res = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
        res.raise_for_status()
        data = res.json()
        response = data["choices"][0]["message"]["content"]
        return {"response": response, "provider": "groq-llama3", "task": task}
    except Exception as e:
        return {"response": str(e), "provider": "groq-llama3", "task": task, "error": True}
