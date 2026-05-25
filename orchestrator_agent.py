import os, json, urllib.request, time


SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

TOOLS = {
    "jina":   "Fetch and extract content from a specific URL. Use when user provides a URL.",
    "search": "Search live web. Use for: latest/new/recent/current/today/2024/2025 queries, prices, news, any tool or product released recently. ALWAYS prefer over ask for anything that could have changed in last 6 months.",
    "image":  "Generate an image from a text description.",
    "deploy": "Write and run Python automation script via GitHub Actions. Use for scraping, monitoring, form filling.",
    "ask":    "Answer using LLM reasoning. Use ONLY for timeless topics: math, theory, stable concepts. NEVER for recent events.",
}

DIFFICULTY_ROUTES = {
    "easy":   ["groq", "cerebras"],
    "medium": ["gemini", "nvidia"],
    "hard":   ["github_models", "nvidia"],
}

# ── Groq LLM call ─────────────────────────────────────────────────
def _groq(messages: list, max_tokens=800) -> str:
    payload = json.dumps({
        "model": "llama-3.3-70b",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.1
    }).encode()
    req = urllib.request.Request(
        "https://api.cerebras.ai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {os.getenv('CEREBRAS_API_KEY', '')}",
            "Content-Type": "application/json"
        }
    )
    try:
        res = urllib.request.urlopen(req, timeout=15)
        data = json.loads(res.read())
        return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"[GROQ_DEBUG] status={e.code} body={body[:300]}")
        return f'{{"error": "{e}"}}' 
    except Exception as e:
        print(f"[GROQ_DEBUG] unexpected={e}")
        return f'{{"error": "{e}"}}'  

# ── Supabase logging ──────────────────────────────────────────────
def _log(query_type, plan, tool_used, success, failure_reason="", result_preview=""):
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

def _load_failures() -> list:
    try:
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/orchestrator_log?success=eq.false&order=created_at.desc&limit=10",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        )
        res = urllib.request.urlopen(req, timeout=6)
        rows = json.loads(res.read())
        return [f"Query type {r.get('query_type')} failed with {r.get('tool_used')}: {r.get('failure_reason','')}" for r in rows]
    except Exception as e:
        print(f"[ANALYZE DEBUG] raw={str(raw)[:200]} err={e}")
        return []

# ── Phase 1: PARSE ────────────────────────────────────────────────
PARSE_PROMPT = """You are Phase 1 of an AI orchestrator. Your job: understand the user query.

Query: {query}

Decide:
1. Is this query clear enough to act on?
2. What is the user actually asking for?
3. What is the tense? (past=historical, present=current/live, future=planning)

Return ONLY JSON:
{{
  "understood": true/false,
  "clarification": "question to ask if not understood",
  "intent": "one line description of what user wants",
  "tense": "past|present|future",
  "keywords": ["key", "terms", "extracted"]
}}"""

def phase_parse(query: str, agent_log: list) -> dict:
    t0 = time.time()
    agent_log.append({"agent": "Orchestrator", "action": "PARSE", "status": "running"})

    raw = _groq([{"role": "user", "content": PARSE_PROMPT.format(query=query)}], max_tokens=300)
    try:
        clean = raw.replace("```json","").replace("```","").strip()
        result = json.loads(clean)
    except:
        result = {"understood": True, "intent": query, "tense": "present", "keywords": []}

    elapsed = round(time.time() - t0, 2)
    agent_log[-1].update({"status": "done", "duration": elapsed})
    return result

# ── Phase 2: ANALYZE ──────────────────────────────────────────────
ANALYZE_PROMPT = """You are Phase 2 of an AI orchestrator. Your job: plan the response quality and tool.

User intent: {intent}
Tense: {tense}
Keywords: {keywords}
Past failures to avoid: {failures}

Available tools:
{tools}

Rules:
- If tense is present/past AND keywords suggest live data → use search
- If user provides a URL → use jina
- If keywords contain: new, latest, recent, current, today, 2024, 2025, best → MUST use search
- If question is timeless concept/theory/math → use ask
- If user wants image/picture/draw/generate → use image
- If user wants automation/scraping/monitoring script → use deploy

Difficulty scoring:
- easy: simple factual, single tool, short answer
- medium: requires 2 tools OR complex formatting OR current data
- hard: multi-step reasoning, multi-tool chain, deep analysis

Return ONLY JSON:
{{
  "tool_plan": [
    {{"tool": "tool_name", "input": "exact input for tool", "reason": "why"}}
  ],
  "difficulty": "easy|medium|hard",
  "query_type": "short_label",
  "output_format": "points|code|mixed",
  "preferred_providers": ["provider1", "provider2"]
}}"""

def phase_analyze(parse_result: dict, query: str, agent_log: list) -> dict:
    t0 = time.time()
    agent_log.append({"agent": "Planner", "action": "ANALYZE", "status": "running"})

    failures = _load_failures()
    tools_desc = "\n".join([f"- {k}: {v}" for k, v in TOOLS.items()])

    raw = _groq([{"role": "user", "content": ANALYZE_PROMPT.format(
        intent=parse_result.get("intent", query),
        tense=parse_result.get("tense", "present"),
        keywords=parse_result.get("keywords", []),
        failures="\n".join(failures) if failures else "None",
        tools=tools_desc
    )}], max_tokens=500)

    try:
        clean = raw.replace("```json","").replace("```","").strip()
        result = json.loads(clean)
    except:
        result = {
            "tool_plan": [{"tool": "ask", "input": query, "reason": "fallback"}],
            "difficulty": "easy",
            "query_type": "unknown",
            "output_format": "points",
            "preferred_providers": ["groq"]
        }

    elapsed = round(time.time() - t0, 2)
    agent_log[-1].update({"status": "done", "duration": elapsed})
    return result

# ── Phase 3: ROUTE + EXECUTE ──────────────────────────────────────
FORMAT_PROMPT = """You are a response formatter. Format this raw content for the user.

User asked: {query}
Raw content: {raw}
Output format: {fmt}

Rules:
- ALWAYS use bullet points (•), never paragraphs
- Maximum 8 bullet points
- Each point: max 2 lines
- Bold key terms using **term**
- If content contains code: wrap in ```language\ncode\n```
- If content is a list of items: one item per bullet
- Start directly with content, no preamble like "Here is..." or "Sure!"
- If tense is present/live: start with a freshness note like "• **As of now:** ..."

Return ONLY the formatted response. No JSON. No explanation."""

def phase_route(analyze_result: dict, parse_result: dict, query: str, router, agent_log: list) -> dict:
    t0 = time.time()
    difficulty = analyze_result.get("difficulty", "easy")
    query_type = analyze_result.get("query_type", "unknown")
    fmt = analyze_result.get("output_format", "points")
    steps = analyze_result.get("tool_plan", [{"tool": "ask", "input": query, "reason": "fallback"}])

    last_output = ""

    for step in steps:
        tool = step.get("tool", "ask")
        tool_input = step.get("input", query)

        # Auto inject previous output
        if last_output:
            if "{previous}" in tool_input:
                tool_input = tool_input.replace("{previous}", last_output[:6000])
            else:
                tool_input = f"{tool_input}\n\nContext from previous step:\n{last_output[:6000]}"

        agent_log.append({"agent": _agent_name(tool), "action": tool.upper(), "status": "running"})
        step_t0 = time.time()

        try:
            output = _execute_tool(tool, tool_input, router, difficulty, agent_log)
        except Exception as e:
            output = f"__ERROR__{e}"

        step_elapsed = round(time.time() - step_t0, 2)

        if output.startswith("__ERROR__"):
            error = output.replace("__ERROR__", "")
            agent_log[-1].update({"status": "failed", "duration": step_elapsed})
            _log(query_type, steps, tool, False, failure_reason=error)
            # Fallback to ask
            agent_log.append({"agent": "Groq", "action": "FALLBACK", "status": "running"})
            fb_t0 = time.time()
            output = _execute_tool("ask", query, router, difficulty, agent_log)
            agent_log[-1].update({"status": "done", "duration": round(time.time()-fb_t0, 2)})
            _log(query_type, steps, "ask", True, result_preview=output[:200])
        else:
            agent_log[-1].update({"status": "done", "duration": step_elapsed})
            _log(query_type, steps, tool, True, result_preview=output[:200])

        # Special types — return immediately
        if isinstance(output, str) and output.startswith("__IMAGE__"):
            return {"type": "image", "content": output.replace("__IMAGE__", ""), "difficulty": difficulty, "agent_log": agent_log}
        if isinstance(output, str) and output.startswith("__DEPLOY__"):
            return {"type": "deploy", "content": output.replace("__DEPLOY__", ""), "difficulty": difficulty, "agent_log": agent_log}

        last_output = output

    # Format output
    agent_log.append({"agent": "Formatter", "action": "FORMAT", "status": "running"})
    fmt_t0 = time.time()
    formatted = _groq([{"role": "user", "content": FORMAT_PROMPT.format(
        query=query,
        raw=last_output[:6000],
        fmt=fmt
    )}], max_tokens=1000)
    agent_log[-1].update({"status": "done", "duration": round(time.time()-fmt_t0, 2)})

    total = round(time.time() - t0, 2)
    return {
        "type": "text",
        "content": formatted,
        "difficulty": difficulty,
        "query_type": query_type,
        "agent_log": agent_log,
        "total_duration": total
    }

def _agent_name(tool: str) -> str:
    names = {
        "jina": "Jina", "search": "Search",
        "image": "HuggingFace", "deploy": "GitHub Actions",
        "ask": "Groq"
    }
    return names.get(tool, tool.title())

def _execute_tool(tool: str, tool_input: str, router, difficulty: str, agent_log: list) -> str:
    try:
        if tool == "jina":
            result = router.providers["jina"].ask(tool_input)
            return result.get("response", "")

        elif tool == "search":
            result = router.providers["search"].search(tool_input, max_results=5)
            raw = result.get("results", "No results")
            summary = router.providers["groq"].ask(
                f"Summarize for: {tool_input}\n\n{str(raw)[:4000]}\n\nBe factual and concise.",
                "default"
            )
            return summary.get("response", str(raw))

        elif tool == "image":
            result = router.generate_image(tool_input)
            if "image_b64" in result:
                return f"__IMAGE__data:image/jpeg;base64,{result['image_b64']}"
            return f"__IMAGE__{result.get('image_url', '')}"

        elif tool == "deploy":
            return f"__DEPLOY__{tool_input}"

        elif tool == "ask":
            # Route by difficulty
            providers = DIFFICULTY_ROUTES.get(difficulty, ["groq"])
            for p in providers:
                if p in router.providers:
                    try:
                        result = router.providers[p].ask(tool_input, "default") if p in ("groq","cerebras","nvidia","gemini","mistral","openrouter") else router.providers[p].ask(tool_input)
                        return result.get("response", "")
                    except:
                        continue
            return router.ask(tool_input).get("response", "No response")

        return "Unknown tool"
    except Exception as e:
        return f"__ERROR__{e}"

# ── Main entry point ──────────────────────────────────────────────
def run(query: str, router, history: list = None) -> dict:
    agent_log = []
    t0 = time.time()

    # Phase 1: Parse
    parse_result = phase_parse(query, agent_log)

    if not parse_result.get("understood", True):
        return {
            "type": "clarify",
            "content": parse_result.get("clarification", "Can you clarify what you need?"),
            "agent_log": agent_log,
            "difficulty": "easy"
        }

    # Phase 2: Analyze
    analyze_result = phase_analyze(parse_result, query, agent_log)

    # Phase 3: Route + Execute
    result = phase_route(analyze_result, parse_result, query, router, agent_log)
    result["total_duration"] = round(time.time() - t0, 2)
    result["phases"] = {
        "parse": parse_result,
        "analyze": analyze_result
    }
    return result
