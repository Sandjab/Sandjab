"""Throwaway CI probe: why does the profile star-history come back empty?

Replicates the exact HTTP request cartouche makes to /stargazers
(star+json media type, API-version pin, Bearer token) but SURFACES the
status / rate-limit headers / body instead of swallowing errors the way
`fetch.py`'s `except HTTPError: continue` does. Run under the CI
GITHUB_TOKEN to see what that token actually gets back.
"""

import json
import os
import urllib.error
import urllib.request

API = "https://api.github.com"
UA = "cartouche-diag/0"
TOKEN = os.environ.get("GITHUB_TOKEN")
HANDLE = "Sandjab"

RL_KEYS = [
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-RateLimit-Used",
    "X-RateLimit-Reset",
    "X-RateLimit-Resource",
    "Retry-After",
]


def req(url: str, accept: str = "application/vnd.github+json"):
    headers = {
        "Accept": accept,
        "User-Agent": UA,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    r = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


print(f"token present: {bool(TOKEN)}")

status, hd, body = req(f"{API}/rate_limit")
print(f"\n=== /rate_limit -> {status} ===")
try:
    res = json.loads(body)["resources"]
    for k in ("core", "search", "graphql"):
        if k in res:
            print(f"  {k}: {res[k]}")
except Exception as ex:  # noqa: BLE001
    print("  parse error:", ex, body[:200])

status, hd, body = req(f"{API}/users/{HANDLE}/repos?per_page=100&sort=updated")
print(f"\n=== /users/{HANDLE}/repos -> {status} ===")
repos = json.loads(body) if status == 200 else []
starred = [r for r in repos if not r["fork"] and r["stargazers_count"] > 0]
print(f"  own starred repos: {[(r['name'], r['stargazers_count']) for r in starred]}")

print("\n=== per-repo /stargazers (Accept: star+json) ===")
for r in starred:
    name = r["name"]
    status, hd, body = req(
        f"{API}/repos/{HANDLE}/{name}/stargazers",
        accept="application/vnd.github.star+json",
    )
    rl = {k: hd.get(k) for k in RL_KEYS if hd.get(k) is not None}
    n = None
    if status == 200:
        try:
            items = json.loads(body)
            n = len(items)
            n = f"{n} items, first has starred_at={('starred_at' in items[0]) if items else 'n/a'}"
        except Exception:  # noqa: BLE001
            n = "unparseable"
    print(f"  {name:16s} status={status} -> {n}")
    print(f"      rate: {rl}")
    if status != 200:
        print(f"      body: {body[:400]!r}")
