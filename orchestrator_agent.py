import os, json, urllib.request, time

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

TOOLS = {
    "jina":   "Fetch and extract content from a specific URL. Use when user provides a URL.",
    "search": "Search live web. Use for: latest/new/recent/current/today/2024/2025 queries, prices, news, any tool or product released recently. ALWAYS prefer over ask for anything that could have changed in last 6 months.",
    "image":  "Generate an image from a text description.",
    "deploy": "Write and run Python automation script via GitHub Actions. Use for scraping, monitoring, form filling.",
    "osint": "Gather public intelligence on IP, phone, domain, company, or username. Use for: investigate/lookup/research/check/who is/what is [company/domain/IP/username/phone]. Always legal — public data only.",
    "ask":    "Answer using LLM reasoning. Use ONLY for timeless topics: math, theory, stable concepts. NEVER for recent events.",
}

DIFFICULTY_ROUTES = {
    "easy":   ["cerebras", "groq"],
    "medium": ["gemini", "nvidia"],
    "hard":   ["github_models", "nvidia"],
}

_router_ref = None

def _groq(messages: list, max_tokens=800) -> str:
    global _router_ref
    prompt = ""
    for m in messages:
        if m["role"] == "system":
            prompt = m["content"] + "\n\n" + prompt
        else:
            prompt += m["content"]
    if _router_ref is not None:
        for provider in ["cerebras", "groq", "nvidia", "mistral"]:
            if provider in _router_ref.providers:
                try:
                    result = _router_ref.providers[provider].ask(prompt, "default")
                    if isinstance(result, str):
                        if result: return result
                    elif isinstance(result, dict):
                        response = result.get("response", "")
                        if response: return response
                except Exception as e:
                    print(f"[LLM] {provider} failed: {e}")
                    continue
    return '{"error": "no provider available"}'

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
        print(f"[Failures] load error: {e}")
        return []

PARSE_PROMPT = """You are Phase 1 of an AI orchestrator. Your job: understand the user query.

Query: {query}

Return ONLY JSON:
{{
  "understood": true,
  "intent": "one line description of what user wants",
  "tense": "past|present|future",
  "keywords": ["key", "terms"]
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
    agent_log[-1].update({"status": "done", "duration": round(time.time()-t0, 2)})
    return result

ANALYZE_PROMPT = """You are Phase 2 of an AI orchestrator. Plan the tool to use.

User intent: {intent}
Tense: {tense}
Keywords: {keywords}
Past failures: {failures}

Tools:
{tools}

Rules:
- keywords like new/latest/recent/current/today/news/price → MUST use search
- URL in query → use jina
- timeless/math/theory → use ask
- image/draw/generate → use image
- scrape/automate/monitor → use deploy

Return ONLY JSON:
{{
  "tool_plan": [{{"tool": "search", "input": "exact query", "reason": "why"}}],
  "difficulty": "easy",
  "query_type": "news_query",
  "output_format": "points",
  "preferred_providers": ["cerebras"]
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
    except Exception as e:
        print(f"[ANALYZE DEBUG] failed: {e} | raw={raw[:200]}")
        result = {
            "tool_plan": [{"tool": "ask", "input": query, "reason": "fallback"}],
            "difficulty": "easy",
            "query_type": "unknown",
            "output_format": "points",
            "preferred_providers": ["cerebras"]
        }
    # Hard override: force search for live data queries
    intent_lower = parse_result.get("intent", query).lower()
    keywords = parse_result.get("keywords", [])
    # OSINT force — check before search override
    force_osint = any(w in intent_lower for w in [
        "investigate", "lookup", "look up", "research", "who is", "what is",
        "check ip", "check phone", "check domain", "check username",
        "osint", "intel on", "intelligence on", "find info", "gather info",
        "track", "trace", "recon", "reconnaissance"
    ])
    if force_osint and result.get("tool_plan", [{}])[0].get("tool") not in ["osint"]:
        # Detect what type of osint
        import re
        osint_type = "company"  # default
        osint_query = query
        if re.search(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', query):
            osint_type = "ip"
        elif re.search(r'\+\d{7,15}', query.replace(" ","").replace("-","")):
            osint_type = "phone"
        elif re.search(r'\b[a-zA-Z0-9][a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}\b', query) and "/" not in query:
            osint_type = "domain"
        elif any(w in intent_lower for w in ["username", "profile", "account", "handle", "@"]):
            osint_type = "username"
        print(f"[ANALYZE] forcing osint/{osint_type} for: {intent_lower[:60]}")
        result["tool_plan"] = [{"tool": "osint", "input": json.dumps({"type": osint_type, "query": osint_query}), "reason": "forced_osint"}]
        result["query_type"] = f"osint_{osint_type}"

    force_search = any(w in intent_lower for w in [
        "latest", "recent", "current", "today", "news", "price",
        "live", "now", "2024", "2025", "2026", "trending"
    ]) or any(w in str(keywords).lower() for w in [
        "latest", "recent", "news", "price", "current"
    ])
    if force_search and result.get("tool_plan", [{}])[0].get("tool") != "search":
        print(f"[ANALYZE] forcing search for: {intent_lower[:60]}")
        result["tool_plan"] = [{"tool": "search", "input": query, "reason": "forced_live"}]
        result["query_type"] = "live_query"

    agent_log[-1].update({"status": "done", "duration": round(time.time()-t0, 2)})
    return result

FORMAT_PROMPT = """Format this content for the user.
User asked: {query}
Raw content: {raw}
- Use bullet points
- Max 8 bullets
- Bold key terms
- No preamble
Return ONLY formatted response."""

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
        if last_output:
            tool_input = f"{tool_input}\n\nContext: {last_output[:3000]}"
        agent_log.append({"agent": _agent_name(tool), "action": tool.upper(), "status": "running"})
        step_t0 = time.time()
        try:
            output = _execute_tool(tool, tool_input, router, difficulty, agent_log)
        except Exception as e:
            output = f"__ERROR__{e}"
        step_elapsed = round(time.time()-step_t0, 2)
        if output.startswith("__ERROR__"):
            error = output.replace("__ERROR__","")
            agent_log[-1].update({"status": "failed", "duration": step_elapsed})
            _log(query_type, steps, tool, False, failure_reason=error)
            agent_log.append({"agent": "Cerebras", "action": "FALLBACK", "status": "running"})
            fb_t0 = time.time()
            output = _execute_tool("ask", query, router, difficulty, agent_log)
            agent_log[-1].update({"status": "done", "duration": round(time.time()-fb_t0, 2)})
            _log(query_type, steps, "ask", True, result_preview=output[:200])
        else:
            agent_log[-1].update({"status": "done", "duration": step_elapsed})
            _log(query_type, steps, tool, True, result_preview=output[:200])
        if isinstance(output, str) and output.startswith("__IMAGE__"):
            return {"type": "image", "content": output.replace("__IMAGE__",""), "difficulty": difficulty, "agent_log": agent_log}
        if isinstance(output, str) and output.startswith("__DEPLOY__"):
            return {"type": "deploy", "content": output.replace("__DEPLOY__",""), "difficulty": difficulty, "agent_log": agent_log}
        last_output = output
    agent_log.append({"agent": "Formatter", "action": "FORMAT", "status": "running"})
    fmt_t0 = time.time()
    formatted = _groq([{"role": "user", "content": FORMAT_PROMPT.format(query=query, raw=last_output[:6000], fmt=fmt)}], max_tokens=1000)
    agent_log[-1].update({"status": "done", "duration": round(time.time()-fmt_t0, 2)})
    return {
        "type": "text",
        "content": formatted,
        "difficulty": difficulty,
        "query_type": query_type,
        "agent_log": agent_log,
        "total_duration": round(time.time()-t0, 2)
    }

def _agent_name(tool: str) -> str:
    return {"jina":"Jina","search":"Search","image":"HuggingFace","deploy":"GitHub Actions","ask":"Cerebras","osint":"OSINT"}.get(tool, tool.title())

def _execute_tool(tool: str, tool_input: str, router, difficulty: str, agent_log: list) -> str:
    try:
        if tool == "jina":
            result = router.providers["jina"].ask(tool_input)
            return result.get("response", "")
        elif tool == "search":
            result = router.providers["search"].search(tool_input, max_results=5)
            raw = result.get("results","No results") if isinstance(result, dict) else str(result)
            summary = router.providers["cerebras"].ask(
                f"Summarize for: {tool_input}\n\n{str(raw)[:4000]}\n\nBe factual and concise.", "default"
            )
            return summary.get("response", str(raw))
        elif tool == "image":
            result = router.generate_image(tool_input)
            if "image_b64" in result:
                return f"__IMAGE__data:image/jpeg;base64,{result['image_b64']}"
            return f"__IMAGE__{result.get('image_url', '')}"
        elif tool == "osint":
            import json as _json
            try:
                params = _json.loads(tool_input) if tool_input.startswith("{") else {"type": "company", "query": tool_input}
            except:
                params = {"type": "company", "query": tool_input}
            from osint.dispatcher import dispatch
            osint_result = dispatch(params.get("type","company"), params.get("query", tool_input))
            if osint_result.get("legal_block"):
                return f"OSINT blocked: {osint_result.get('error','')}"
            # Format result as readable text for LLM
            lines = [f"OSINT INTELLIGENCE — {params.get('type','').upper()} · {params.get('query','')}"]
            lines.append("=" * 50)
            skip = {"query_type","query","cached","legal_note","source","arjun_note"}
            for k, v in osint_result.items():
                if k in skip:
                    continue
                if isinstance(v, list):
                    if v:
                        lines.append(f"{k.upper()}: {', '.join(str(x) for x in v[:5])}")
                elif isinstance(v, dict):
                    for dk, dv in v.items():
                        if dv:
                            lines.append(f"{dk}: {dv}")
                elif v is not None:
                    lines.append(f"{k.upper()}: {v}")
            if osint_result.get("legal_note"):
                lines.append(f"LEGAL: {osint_result['legal_note']}")
            if osint_result.get("arjun_note"):
                lines.append(f"TRADING NOTE: {osint_result['arjun_note']}")
            return "\n".join(lines)

        elif tool == "deploy":
            return f"__DEPLOY__{tool_input}"
        elif tool == "ask":
            providers = DIFFICULTY_ROUTES.get(difficulty, ["cerebras"])
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

def run(query: str, router, history: list = None) -> dict:
    global _router_ref
    _router_ref = router
    agent_log = []
    t0 = time.time()
    parse_result = phase_parse(query, agent_log)
    if not parse_result.get("understood", True):
        return {"type": "clarify", "content": parse_result.get("clarification", "Can you clarify?"), "agent_log": agent_log, "difficulty": "easy"}
    analyze_result = phase_analyze(parse_result, query, agent_log)
    result = phase_route(analyze_result, parse_result, query, router, agent_log)
    result["total_duration"] = round(time.time()-t0, 2)
    result["phases"] = {"parse": parse_result, "analyze": analyze_result}
    return result
