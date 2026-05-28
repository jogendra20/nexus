import os
import json
import requests
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
        "You are an Elite Python Automation Engineer for GitHub Actions (ubuntu-latest).\n"
        "Output ONLY raw Python code. No markdown. No explanation. No preamble.\n"
        "First line must be a Python import or statement.\n"
        "Always include: run_id = os.environ.get('RUN_ID', '')\n"
        "Scripts must finish within 5 minutes.\n"
        "Wrap everything in try/except and print errors to stdout.\n"
        "\n--- STEALTH & JS STRATEGY ---\n"
        "1. For JS-heavy/CAPTCHA sites: Use 'scrapling' with 'browserforge' fingerprints.\n"
        "2. For TLS/Cloudflare bypass: Use 'curl_cffi' (requests-compatible).\n"
        "3. NEVER use 'playwright_stealth' (not installed). Use 'scrapling' built-in stealth.\n"
        "4. Always mimic real headers: User-Agent, Accept-Language, Referer.\n"
        "5. IMPORTANT: If a VERIFIED RECIPE matches the task in the skill reference, copy it exactly.\n"
    )
    if skill:
        return base + '\n# SKILL REFERENCE - follow these patterns exactly:\n' + skill
    return base

GROQ_KEY = os.getenv("GROQ_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_MODELS_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

def call_llm(prompt, system, model="llama-3.3-70b-versatile", provider="groq"):
    if provider == "groq":
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    elif provider == "github":
        url = "https://models.inference.ai.azure.com/chat/completions"
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Content-Type": "application/json"}
    elif provider == "openrouter":
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"}
    
    payload = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}], "temperature": 0.2}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=60)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error: {str(e)}"

def agentic_ask(prompt: str, task: str = "default") -> dict:
    is_code = task in ("automation", "code", "deploy")
    if is_code:
        system = get_automation_prompt()
        draft_code = call_llm(prompt, system, model="gpt-4o", provider="github")
        review_prompt = f"Review this automation code for: 1. Bot detection risks 2. Logic errors 3. Missing imports. Output only 'PASSED' or the corrected full code.\nCode:\n{draft_code}"
        review_system = "You are a Senior Security Auditor."
        final_code = call_llm(review_prompt, review_system, model="o1-mini", provider="github")
        if "import" in final_code or "from" in final_code:
            return {"response": final_code}
        return {"response": draft_code}
    
    system = "You are Nexus, a sharp AI assistant. Keep it concise."
    response = call_llm(prompt, system)
    return {"response": response}
