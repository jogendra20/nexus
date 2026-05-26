import urllib.request as ur
import json

def run(query: str) -> dict:
    """
    Legal: public IP metadata only.
    Source: ipinfo.io (free tier, no auth needed for basic data)
    Returns: ASN, org, city, region, country, carrier, is_datacenter
    Never returns: precise location, personal data
    """
    try:
        url = f"https://ipinfo.io/{query}/json"
        req = ur.Request(url, headers={"User-Agent": "NEXUS-OSINT/1.0"})
        res = ur.urlopen(req, timeout=8)
        data = json.loads(res.read())

        # Filter: return only safe public fields
        return {
            "source": "ipinfo.io",
            "ip": data.get("ip"),
            "org": data.get("org"),          # ASN + org name
            "city": data.get("city"),         # approximate
            "region": data.get("region"),
            "country": data.get("country"),
            "timezone": data.get("timezone"),
            "hostname": data.get("hostname"),
            "legal_note": (
                "City-level approximation only. "
                "No precise location. Public ASN data."
            ),
        }
    except Exception as e:
        return {"error": str(e), "source": "ipinfo.io"}
