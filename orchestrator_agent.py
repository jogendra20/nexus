import os, json, urllib.request

GROQ_KEY = os.getenv("GROQ_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

TOOLS = {
    "jina":   "Fetch and extract content from a URL. Use when user gives a URL or wants content from a website.",
    "search": "Search live web for current data, prices, news, scores. Use for anything time-sensitive.",
    "image":  "Generate an image from a text description.",
    "deploy": "Write and run a Python automation script via GitHub Actions. Use for scraping, form filling, monitoring.",
    "ask":    "Answer using LLM reasoning. Use for explanations, coding help, analysis, general questions.",
}

PLAN_PROMPT = """You are an orchestrator for a personal AI system.

Available tools:
{tools}

Past failures to avoid:
{failures}

User query: {query}

Your job:
1. Decide which tool(s) to use, in order.
2. If the query is unclear or missing info, return clarify.
3. Return ONLY a JSON object. No explanation. No markdown.

Return format:
{{
  "action": "plan" | "clarify",
  "clarification": "question to ask user if action=clarify",
  "steps": [
    {{"tool": "tool_name", "input": "exact input for this tool", "reason": "why"}}
  ],
  "query_type": "short label like: price_lookup, web_scrape, image_gen, code_help"
}}"""

JUDGE_PROMPT = """You are judging if an AI tool response was good.

User query: {query}
Tool used: {tool}
Tool output: {output}

Was this a good answer? Reply ONLY with JSON:
{{"good": true/false, "reason": "brief reason"}}"""

def _groq(messages: list, max_tokens=500) -> str:
    payload = json.dumps({
        "model": "llama-3.1-8b-instant",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.1
    }).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json"
        }
    )
    try:
        res = urllib.request.urlopen(req, timeout=15)
        data = json.loads(res.read())
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f'{{"error": "{e}"}}'

def _load_failures(query_type: str = None) -> list:
    """Load past failures from Supabase to inform planning."""
    try:
        url = f"{SUPABASE_URL}/rest/v1/orchestrator_log?success=eq.false&order=created_at.desc&limit=10"
        if query_type:
            url += f"&query_type=eq.{query_type}"
        req = urllib.request.Request(url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        })
        res = urllib.request.urlopen(req, timeout=6)
        rows = json.loads(res.read())
        return [
            f"Query type '{r.get('query_type')}' failed with tool '{r.get('tool_used')}': {r.get('failure_reason', '')}"
            for r in rows
        ]
    except:
        return []

def _log(query_type: str, plan: list, tool_used: str, success: bool,
         failure_reason: str = "", result_preview: str = ""):
    """Log result to Supabase."""
    try:
        payload = json.dumps({
            "query_type": query_type,
            "plan": plan,
            "tool_used": tool_used,
            "success": success,
            "failure_reason": failure_reason,
            "result_preview": result_preview[:200]
        }).encode()
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/orchestrator_log",
            data=payload,
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            },
            method="POST"
        )
        urllib.request.urlopen(req, timeout=6)
    except:
        pass

def _judge(query: str, tool: str, output: str) -> bool:
    """Ask LLM if the result was good."""
    prompt = JUDGE_PROMPT.format(
        query=query, tool=tool,
        output=output[:500]
    )
    raw = _groq([{"role": "user", "content": prompt}], max_tokens=100)
    try:
        clean = raw.replace("```json","").replace("```","").strip()
        result = json.loads(clean)
        return result.get("good", False), result.get("reason", "")
    except:
        return True, ""  # assume good if judge fails

def _execute_tool(tool: str, input_text: str, router) -> str:
    """Execute a single tool and return its output."""
    try:
        if tool == "jina":
            result = router.providers["jina"].ask(input_text)
            return result.get("response", "")

        elif tool == "search":
            result = router.providers["search"].search(input_text, max_results=5)
            raw = result.get("results", "No results")
            # Summarize with Groq
            summary = router.providers["groq"].ask(
                f"Summarize these search results for: {input_text}\n\n{str(raw)[:3000]}\n\nBe concise and direct.",
                "default"
            )
            return summary.get("response", str(raw))

        elif tool == "image":
            result = router.generate_image(input_text)
            if "image_b64" in result:
                return f"__IMAGE__data:image/jpeg;base64,{result['image_b64']}"
            return f"__IMAGE__{result.get('image_url', '')}"

        elif tool == "deploy":
            # Returns run_id for polling
            return f"__DEPLOY__{input_text}"

        elif tool == "ask":
            result = router.ask(input_text, task="default")
            return result.get("response", "No response")

        return "Unknown tool"
    except Exception as e:
        return f"__ERROR__{e}"

def run(query: str, router, history: list = None) -> dict:
    """
    Main orchestrator entry point.
    Returns: {type: clarify|image|deploy|text, content: str, ask_user: str|None}
    """
    # Build tool descriptions
    tools_desc = "\n".join([f"- {k}: {v}" for k, v in TOOLS.items()])

    # Load past failures
    failures = _load_failures()
    failures_desc = "\n".join(failures) if failures else "None"

    # Build plan
    plan_raw = _groq([{
        "role": "user",
        "content": PLAN_PROMPT.format(
            tools=tools_desc,
            failures=failures_desc,
            query=query
        )
    }], max_tokens=600)

    try:
        clean = plan_raw.replace("```json","").replace("```","").strip()
        plan = json.loads(clean)
    except:
        # Plan parsing failed — fall back to ask
        plan = {"action": "plan", "steps": [{"tool": "ask", "input": query, "reason": "fallback"}], "query_type": "unknown"}

    # Clarification needed
    if plan.get("action") == "clarify":
        return {
            "type": "clarify",
            "content": plan.get("clarification", "Can you clarify what you need?"),
            "ask_user": plan.get("clarification")
        }

    steps = plan.get("steps", [])
    query_type = plan.get("query_type", "unknown")

    if not steps:
        steps = [{"tool": "ask", "input": query, "reason": "fallback"}]

    # Execute steps
    last_output = ""
    for step in steps:
        tool = step.get("tool", "ask")
        tool_input = step.get("input", query)

        # Inject previous step output if chaining
        if last_output and "{previous}" in tool_input:
            tool_input = tool_input.replace("{previous}", last_output[:500])

        output = _execute_tool(tool, tool_input, router)

        # Check for errors
        if output.startswith("__ERROR__"):
            error = output.replace("__ERROR__", "")
            _log(query_type, steps, tool, False, failure_reason=error)

            # Try next tool in list if available
            remaining = [s for s in steps if s["tool"] != tool]
            if remaining:
                fallback_tool = remaining[0]["tool"]
                output = _execute_tool(fallback_tool, tool_input, router)
                _log(query_type, steps, fallback_tool, True, result_preview=output)
                last_output = output
            else:
                last_output = f"All tools failed for: {query}"
            continue

        # Special types — return immediately
        if output.startswith("__IMAGE__"):
            _log(query_type, steps, tool, True, result_preview="image generated")
            return {"type": "image", "content": output.replace("__IMAGE__", "")}

        if output.startswith("__DEPLOY__"):
            _log(query_type, steps, tool, True, result_preview="deploy triggered")
            return {"type": "deploy", "content": output.replace("__DEPLOY__", "")}

        # Judge output quality
        good, reason = _judge(query, tool, output)
        if not good:
            _log(query_type, steps, tool, False, failure_reason=reason, result_preview=output)
            # Retry with ask as fallback
            fallback = _execute_tool("ask", query, router)
            _log(query_type, steps, "ask", True, result_preview=fallback)
            last_output = fallback
        else:
            _log(query_type, steps, tool, True, result_preview=output)
            last_output = output

    return {"type": "text", "content": last_output}
