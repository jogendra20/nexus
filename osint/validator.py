import re
from typing import Tuple

PRIVATE_IP_PATTERNS = [
    r'^10\.',
    r'^192\.168\.',
    r'^172\.(1[6-9]|2[0-9]|3[01])\.',
    r'^127\.',
    r'^0\.',
    r'^169\.254\.',
    r'^::1$',
    r'^localhost$',
]

VALID_TYPES = ["ip", "phone", "domain", "company", "username"]

LEGAL_SCOPE = {
    "ip":       "ASN, org, city (approximate), carrier. No precise location.",
    "phone":    "Carrier, region, line type only. No real-time location ever.",
    "domain":   "WHOIS, DNS, subdomains from public certificate logs only.",
    "company":  "MCA public registry, NSE public data, public news only.",
    "username": "Public profile existence check only. No private data.",
}

def validate(query_type: str, query: str) -> Tuple[bool, str]:
    if query_type not in VALID_TYPES:
        return False, f"Invalid type '{query_type}'. Allowed: {VALID_TYPES}"

    query = query.strip()
    if not query:
        return False, "Query cannot be empty."

    if len(query) > 500:
        return False, "Query too long. Max 500 chars."

    # IP-specific: block private ranges
    if query_type == "ip":
        for pattern in PRIVATE_IP_PATTERNS:
            if re.match(pattern, query, re.IGNORECASE):
                return False, (
                    "Private/internal IP addresses are blocked. "
                    "OSINT only works on public IPs. "
                    "Legal scope: " + LEGAL_SCOPE["ip"]
                )
        # Basic IP format check
        ipv4 = re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', query)
        if not ipv4:
            return False, "Invalid IP format. Use IPv4 format: x.x.x.x"

    # Phone: must have country code
    if query_type == "phone":
        if not query.startswith("+"):
            return False, "Phone must include country code. Example: +919876543210"
        if not re.match(r'^\+\d{7,15}$', query.replace(" ", "").replace("-", "")):
            return False, "Invalid phone format. Use E.164: +919876543210"

    # Domain: basic sanity
    if query_type == "domain":
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}$', query):
            return False, "Invalid domain format. Example: example.com"

    return True, "ok"
