from osint.validator import validate
from osint.cache import get_cached, set_cache
from osint.modules import ip, phone, domain, company, username

MODULE_MAP = {
    "ip":       ip,
    "phone":    phone,
    "domain":   domain,
    "company":  company,
    "username": username,
}

def dispatch(query_type: str, query: str, modules: list = None) -> dict:
    # 1. Validate — legal guardrail first
    is_valid, reason = validate(query_type, query)
    if not is_valid:
        return {
            "error": reason,
            "legal_block": True,
            "query_type": query_type,
            "query": query,
        }

    # 2. Check cache
    cached = get_cached(query_type, query)
    if cached:
        cached["cached"] = True
        return cached

    # 3. Run module
    module = MODULE_MAP.get(query_type)
    if not module:
        return {"error": f"No module for type: {query_type}"}

    result = module.run(query)
    result["query_type"] = query_type
    result["query"] = query
    result["cached"] = False

    # 4. Cache result
    if "error" not in result:
        set_cache(query_type, query, result)

    return result
