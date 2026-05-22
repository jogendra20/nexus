import requests as _requests

def load_skill(name):
    try:
        url = f'https://raw.githubusercontent.com/jogendra20/Automate/main/skills/{name}.md'
        r = _requests.get(url, timeout=8)
        if r.status_code == 200:
            return r.text
    except:
        pass
    return ''

def get_automation_prompt():
    skill = load_skill('playwright')
    base = (
        'You are a Python code generator for GitHub Actions ubuntu-latest.\n'
        'Output ONLY raw Python code. No markdown. No explanation. No preamble.\n'
        'First line must be a Python import or statement.\n'
        'Always include: run_id = os.environ.get("RUN_ID", "")\n'
        'Scripts must finish within 5 minutes.\n'
        'Wrap everything in try/except and print errors to stdout.\n'
        'IMPORTANT: If the skill reference contains a VERIFIED RECIPE that matches the task, copy it exactly. Do not modify selectors, URLs, or structure.\n'
        'NEVER import playwright_stealth or stealth_sync — this module is not available.\n'
        'For simple HTML sites use requests+beautifulsoup4, NOT Playwright.\n'
    )
    if skill:
        return base + '\n# SKILL REFERENCE - follow these patterns exactly:\n' + skill
    return base


AUTOMATION_PROMPT = """You are a Python code generator running inside GitHub Actions ubuntu-latest.
Output ONLY raw Python code. No markdown fences. No explanation. No preamble.
The very first line must be a Python import or statement.

Available packages: requests, pandas, beautifulsoup4, yfinance, lxml, playwright, scrapling, json, os, sys, re, datetime
Always print results to stdout.
For NSE top gainers use: https://api.tickertape.in/stocks/screener/filter\?sortBy\=change_percent\&sortOrder\=desc\&limit\=10
Never use nseindia.com directly — it blocks scrapers.
Scripts must finish within 5 minutes.
Wrap everything in try/except and print errors to stdout.
"""
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
    
    is_code = task in ("automation", "code", "deploy")
    system = get_automation_prompt() if is_code else SYSTEM_PROMPT
    max_tok = 1500 if is_code else 400

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tok,
        "temperature": 0.3 if is_code else 0.7
    }
    
    try:
        res = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
        res.raise_for_status()
        data = res.json()
        response = data["choices"][0]["message"]["content"]
        return {"response": response, "provider": "groq-llama3", "task": task}
    except Exception as e:
        return {"response": str(e), "provider": "groq-llama3", "task": task, "error": True}
