import os
import base64
import requests
from datetime import datetime

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_OWNER = "jogendra20"
GITHUB_REPO  = "Automate"
BRANCH       = "main"
BASE_URL     = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

def push_script(code: str, filename: str = None) -> dict:
    if not filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"scripts/auto_{ts}.py"

    sha = None
    check = requests.get(f"{BASE_URL}/contents/{filename}", headers=HEADERS)
    if check.status_code == 200:
        sha = check.json().get("sha")

    content_b64 = base64.b64encode(code.encode()).decode()

    payload = {
        "message": f"auto: {filename} via Nexus",
        "content": content_b64,
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha

    response = requests.put(
        f"{BASE_URL}/contents/{filename}",
        headers=HEADERS,
        json=payload
    )

    if response.status_code in (200, 201):
        return {"success": True, "filename": filename, "url": response.json()["content"]["html_url"]}
    else:
        return {"success": False, "error": response.json()}

def delete_file(filepath: str) -> dict:
    check = requests.get(f"{BASE_URL}/contents/{filepath}", headers=HEADERS)
    if check.status_code != 200:
        return {"success": False, "error": "File not found"}
    sha = check.json().get("sha")
    response = requests.delete(
        f"{BASE_URL}/contents/{filepath}",
        headers=HEADERS,
        json={"message": f"cleanup: {filepath}", "sha": sha, "branch": BRANCH}
    )
    if response.status_code == 200:
        return {"success": True}
    return {"success": False, "error": response.text}

def trigger_workflow(script_path: str, task: str = "", difficulty: str = "easy", provider: str = "unknown") -> dict:
    payload = {
        "ref": BRANCH,
        "inputs": {
            "script_path": script_path,
            "task": task,
            "difficulty": difficulty,
            "provider": provider
        }
    }
    response = requests.post(
        f"{BASE_URL}/actions/workflows/automate.yml/dispatches",
        headers=HEADERS,
        json=payload
    )
    if response.status_code == 204:
        return {"success": True}
    else:
        return {"success": False, "error": response.text, "status_code": response.status_code}
