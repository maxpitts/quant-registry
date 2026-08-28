#!/usr/bin/env python3
"""enrich.py — attach public GitHub facts to each manifest, at build time.

WHY AT BUILD TIME AND NOT IN THE BROWSER
----------------------------------------
The obvious way to show stars and a last-updated date is to call the GitHub API from the page.
That fails at exactly the moment it matters: api.github.com allows 60 unauthenticated requests per
hour PER VIEWER IP, so a page listing 200 packages breaks on the first visitor and breaks worst
when the registry is busiest. Worse, it would leak every reader's browsing to a third party.

So the Action does it once, authenticated (5,000/hr with GITHUB_TOKEN), and bakes the answers into
index.json. Readers then fetch one static file from a CDN. This is the same reason metrics.py
exists in openwatch: derive on the server, serve something small and dumb.

Degrades cleanly: no token, or the API down, and packages keep every field they already had.
"""
from __future__ import annotations

import json, os, re, sys, time, urllib.error, urllib.request

API = "https://api.github.com/repos/"
TOK = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def slug(repo_url: str) -> str | None:
    m = re.match(r"https://github\.com/([^/]+)/([^/#?]+)", (repo_url or "").rstrip("/"))
    return f"{m.group(1)}/{m.group(2)}" if m else None


def fetch(path: str):
    req = urllib.request.Request(API + path, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "quant-registry-indexer",
        **({"Authorization": "Bearer " + TOK} if TOK else {}),
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def enrich(pkgs: list[dict]) -> tuple[int, int]:
    ok = miss = 0
    for p in pkgs:
        s = slug(p.get("repo", ""))
        if not s:
            miss += 1
            continue
        try:
            d = fetch(s)
            p["gh"] = {
                "slug": s,
                "stars": d.get("stargazers_count"),
                "forks": d.get("forks_count"),
                "open_issues": d.get("open_issues_count"),
                "pushed_at": d.get("pushed_at"),
                "default_branch": d.get("default_branch") or "main",
                "topics": d.get("topics") or [],
                "archived": bool(d.get("archived")),
                "description": d.get("description"),
                "language": d.get("language"),
            }
            ok += 1
        except urllib.error.HTTPError as e:
            # 404 usually means the repo was renamed or deleted. Record it rather than dropping the
            # package silently — a dead link in a registry should be visible, not invisible.
            p["gh"] = {"slug": s, "error": f"HTTP {e.code}"}
            miss += 1
        except Exception as e:                                    # noqa: BLE001
            p["gh"] = {"slug": s, "error": type(e).__name__}
            miss += 1
        time.sleep(0.12 if TOK else 1.2)                          # be a polite client
    return ok, miss


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "index.json"
    idx = json.load(open(path))
    if not TOK:
        print("enrich: no GITHUB_TOKEN — unauthenticated (60/hr). Fine locally, set it in CI.")
    ok, miss = enrich(idx.get("packages", []))
    idx["enriched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(idx, open(path, "w"), indent=1)
    print(f"enrich: {ok} enriched, {miss} unresolved -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
