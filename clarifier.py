import os
import json
import urllib.request

CLARIFY_SYSTEM = """You are a prompt quality analyzer for a personal AI assistant.

Given a user prompt, decide:
1. Is it CLEAR enough to answer accurately?
2. Is it VAGUE but can be improved with context?
3. Is it TOO VAGUE and needs a clarifying question?

Rules:
- If prompt has clear intent + enough detail → ENHANCE it silently
- If prompt has clear intent but missing one key detail → ENHANCE with reasonable assumption
- If prompt is too short or ambiguous to even guess intent → CLARIFY

Return ONLY a JSON object. No explanation. No markdown.

Format:
{
  "action": "enhance" or "clarify",
  "result": "enhanced prompt here" or "one clarifying question here",
  "reason": "one line why"
}

Examples:
Input: "analyse nse"
Output: {"action": "clarify", "result": "Which NSE stock or sector do you want me to analyze, and for what purpose (intraday/swing/news)?", "reason": "Too vague — no stock, no timeframe, no goal"}

Input: "top gainers today"
Output: {"action": "enhance", "result": "Fetch the top 5 NSE gainers for today including stock name, price, and percentage change. Format as a clean list.", "reason": "Clear intent, added specifics for better output"}

Input: "summarize arxiv papers on rl"
Output: {"action": "enhance", "result": "Search arxiv for the 3 most recent papers on reinforcement learning. For each paper provide title, authors, and a 2-sentence summary.", "reason": "Clear intent, added structure and count"}"""


def analyze_prompt(prompt: str, router) -> dict:
    """
    Returns:
      {"action": "enhance", "result": <enhanced_prompt>}
      {"action": "clarify", "result": <question>}
      {"action": "passthrough", "result": <original>}  -- on failure
    """
    if len(prompt.split()) > 20:
        # Long detailed prompts don't need clarification
        return {"action": "passthrough", "result": prompt}

    analysis_prompt = CLARIFY_SYSTEM + f"\n\nUser prompt: {prompt}"

    try:
        result = router.ask(analysis_prompt, task="reasoning", difficulty="easy")
        text = result.get("response", "").strip()
        text = text.replace("```json", "").replace("```", "").strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            return {"action": "passthrough", "result": prompt}
        data = json.loads(text[start:end])
        if data.get("action") not in ("enhance", "clarify"):
            return {"action": "passthrough", "result": prompt}
        return data
    except Exception as e:
        print(f"[Clarifier] failed: {e}")
        return {"action": "passthrough", "result": prompt}
