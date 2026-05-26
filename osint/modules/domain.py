import urllib.request as ur
import json
import subprocess

def _whois(domain: str) -> dict:
    try:
        result = subprocess.run(
            ["whois", domain],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.splitlines()
        data = {}
        important_keys = [
            "registrar", "creation date", "expiry date", "updated date",
            "registrant organization", "registrant country", "name server",
            "registry expiry date", "registrar registration expiration date"
        ]
        for line in lines:
            if ":" in line:
                k, _, v = line.partition(":")
                k = k.strip().lower()
                v = v.strip()
                if any(ik in k for ik in important_keys) and v:
                    data[k] = v
        return data
    except subprocess.TimeoutExpired:
        return {"error": "whois timeout"}
    except Exception as e:
        return {"error": str(e)}

def _crtsh(domain: str) -> list:
    try:
        import urllib.parse, socket
        socket.setdefaulttimeout(8)
        url = f"https://crt.sh/?q=%.{urllib.parse.quote(domain)}&output=json"
        req = ur.Request(url, headers={"User-Agent": "NEXUS-OSINT/1.0"})
        res = ur.urlopen(req, timeout=8)
        certs = json.loads(res.read())
        subdomains = set()
        for c in certs:
            name = c.get("name_value", "")
            for sub in name.splitlines():
                sub = sub.strip().lstrip("*.")
                if sub and domain in sub:
                    subdomains.add(sub)
        return sorted(list(subdomains))[:20]
    except Exception as e:
        return []

def _dns(domain: str) -> dict:
    try:
        import socket
        a_record = socket.gethostbyname(domain)
        return {"a_record": a_record}
    except Exception as e:
        return {"error": str(e)}

def run(query: str) -> dict:
    whois_data = _whois(query)
    subdomains = _crtsh(query)
    dns_data = _dns(query)

    return {
        "domain": query,
        "whois": whois_data,
        "dns": dns_data,
        "subdomains_from_certs": subdomains,
        "subdomain_count": len(subdomains),
        "source": "whois cli + crt.sh + DNS",
        "legal_note": "All data from public registries and certificate transparency logs.",
    }
