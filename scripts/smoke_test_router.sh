#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

docker compose exec -T router python -c '
import json
import os
import urllib.request

router_key = os.environ["ROUTER_API_KEY"]
payload = {
    "model": "auto",
    "messages": [{"role": "user", "content": "Reply with a short greeting."}],
}
request = urllib.request.Request(
    "http://127.0.0.1:8000/v1/chat/completions",
    data=json.dumps(payload).encode(),
    headers={
        "Authorization": f"Bearer {router_key}",
        "Content-Type": "application/json",
    },
)
with urllib.request.urlopen(request, timeout=120) as response:
    result = json.load(response)
content = result["choices"][0]["message"]["content"]
if not isinstance(content, str) or not content.strip():
    raise SystemExit("Router smoke test returned an empty assistant response")
print("Router to LiteLLM smoke test passed")
print(content)
'
