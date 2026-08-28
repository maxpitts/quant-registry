#!/usr/bin/env python3
"""discover.py — find candidate packages on GitHub and write third-party manifests.

WHY FILTERS, NOT JUST STARS
---------------------------
Sorting GitHub by stars for "quantitative-finance" returns, in the top ten: two curated link
lists (awesome-quant, 29k stars), a book's companion notebooks (20k), and an LLM wrapper (64k).
None is a package. Star count measures attention, not whether a thing can be depended on, so the
rules below encode what actually disqualifies a candidate. Every rejection is logged with its
reason — a silent filter is one nobody can argue with, and this one should be arguable.

Everything written here is an UNAFFILIATED listing: no pinned commit and no performance block,
because the author did not submit it and the registry does not speak for them.

    python3 discover.py --dry-run          show what it would add and what it rejected, and why
    python3 discover.py --min-stars 500    actually write manifests
"""
from __future__ import annotations

import argparse, glob, json, os, re, sys, time, urllib.parse, urllib.request

SEARCH = "https://api.github.com/search/repositories"
TOK = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

TOPICS = ["quantitative-finance", "algorithmic-trading", "trading-strategies",
          "quantitative-trading", "backtesting", "market-making", "options-trading",
          "portfolio-optimization", "technical-analysis", "systematic-trading"]

# GitHub reports NOASSERTION when it cannot identify a licence file. A registry that indexes
# code people may run must not guess at licensing, so both that and a missing licence are hard
# rejections rather than a "review later" tier.
BAD_LICENSE = {None, "", "NOASSERTION", "other", "OTHER"}

ASSET_HINTS = [
    ("crypto",  r"crypto|bitcoin|binance|defi|dex|cex|coinbase|ethereum"),
    ("option",  r"\boption|greeks|volatility surface|implied vol|derivativ"),
    ("future",  r"\bfutures?\b|cme\b|contango"),
    ("fx",      r"\bforex\b|\bfx\b|currency pair"),
    ("rates",   r"\brates?\b|yield curve|treasur|bond"),
]
# Order matters: the first match wins, so the most specific patterns come first. A repo that is
# both "backtesting" and "trading-bot" is a harness, because that's the thing you run others in.
KIND_HINTS = [
    ("harness",   r"backtest|research framework|simulat|walk.?forward|event.?driven engine"),
    ("execution", r"trading.?bot|market.?mak|order (routing|execution)|exchange connector|live trading|broker"),
    ("risk",      r"portfolio optim|risk (model|management|parity)|efficient frontier|allocation|var\b|drawdown model"),
    ("feature",   r"technical.?analysis|indicator|feature|ta-lib|signal library"),
    ("data",      r"market data|data (feed|source|provider|pipeline)|scraper|ingest"),
    ("model",     r"machine.?learning|deep.?learning|forecast|predict|neural|reinforcement"),
    ("strategy",  r"strateg|alpha|signal"),
]


def gh(url: str):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "quant-registry-discover",
        **({"Authorization": "Bearer " + TOK} if TOK else {})})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)


def clean_summary(text: str, limit: int = 120) -> str:
    """Normalise a repo description into a one-line summary that survives a YAML round trip.

    Two traps here, both hit on real data:

    1. json.dumps escapes astral-plane characters (emoji) as UTF-16 SURROGATE PAIRS -- two escape
       sequences for one character -- and YAML does not recombine surrogates when parsing them.
       A string Python truncated to exactly 120 characters therefore came back as 122 and failed
       validation. Writing with ensure_ascii=False avoids the escaping entirely; the files are
       UTF-8 anyway, and they become readable instead of a wall of escapes.
    2. Repo descriptions carry decoration -- leading emoji, "[updating...]" banners, newlines.
       None of it survives usefully on a one-line card, so it is stripped rather than truncated
       around.
    """
    t = re.sub(r"\s+", " ", (text or "")).strip()
    t = re.sub(r"^[\W_]*\[[^\]]{0,40}\]\s*", "", t)          # leading "[updating ...]" banners
    t = t.lstrip("#*-\u2013\u2014\u2022|>~ ").strip()
    if len(t) <= limit:
        return t
    cut = t[:limit - 1]
    sp = cut.rfind(" ")
    if sp > limit * 0.6:                                       # prefer a word boundary
        cut = cut[:sp]
    return cut.rstrip(" ,.;:-") + "\u2026"


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)[:48] or "package"


def classify(repo: dict) -> str:
    blob = " ".join([repo.get("description") or "", " ".join(repo.get("topics") or []),
                     repo.get("name") or ""]).lower()
    for kind, pat in KIND_HINTS:
        if re.search(pat, blob):
            return kind
    return "harness"


def assets(repo: dict) -> list[str]:
    blob = " ".join([repo.get("description") or "", " ".join(repo.get("topics") or [])]).lower()
    out = [a for a, pat in ASSET_HINTS if re.search(pat, blob)]
    return out or ["equity"]        # equity is the honest default for an unlabelled quant repo


def reject(repo: dict, min_stars: int, max_stale_days: int) -> str | None:
    """Return a human-readable reason to skip, or None to accept."""
    name = (repo.get("name") or "").lower()
    full = (repo.get("full_name") or "").lower()
    desc = (repo.get("description") or "").lower()
    topics = [t.lower() for t in (repo.get("topics") or [])]
    lic = (repo.get("license") or {}).get("spdx_id")

    if repo.get("fork"):     return "fork"
    if repo.get("archived"): return "archived"
    if lic in BAD_LICENSE:   return f"unusable licence ({lic})"
    if (repo.get("stargazers_count") or 0) < min_stars:
        return f"under {min_stars} stars"
    # curated link lists: enormous star counts, zero installable content
    if "awesome" in name or "awesome" in topics or re.search(r"curated list|awesome list", desc):
        return "curated link list, not a package"
    # book / course companions: the code exists to accompany prose, not to be depended on
    if re.search(r"\b(book|course|tutorial|lecture|chapter|edition|handbook|cookbook)\b", desc + " " + name):
        return "book/course companion"
    if re.search(r"^(learn|study|practice|demo|example|test|sample)[-_]", name):
        return "demo/learning repo"
    p = repo.get("pushed_at") or ""
    if p:
        try:
            age = (time.time() - time.mktime(time.strptime(p[:10], "%Y-%m-%d"))) / 86400
            if age > max_stale_days:
                return f"stale ({int(age)}d since last push)"
        except ValueError:
            pass
    return None


def manifest(repo: dict, submitted_by: str) -> dict:
    owner, name = repo["full_name"].split("/", 1)
    return {
        "name": slugify(name), "namespace": slugify(owner),
        "version": "0.0.0",           # unknown until the author submits; never invented
        "kind": classify(repo),
        "summary": clean_summary(repo.get("description") or repo["full_name"]),
        "repo": repo["html_url"], "license": repo["license"]["spdx_id"],
        "asset_classes": assets(repo),
        "unaffiliated": True, "submitted_by": submitted_by,
        "description": ("Indexed automatically from GitHub topic search. Not submitted by its "
                        "author and not endorsed by anyone. Kind and asset classes are inferred "
                        "from the repo's own description and topics, so they may be wrong — open "
                        "a PR to correct them."),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-stars", type=int, default=300)
    ap.add_argument("--max-stale-days", type=int, default=365)
    ap.add_argument("--per-topic", type=int, default=30)
    ap.add_argument("--submitted-by", default="maxpitts")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    have = set()
    for f in glob.glob("packages/**/*.yaml", recursive=True):
        m = re.search(r"repo:\s*(\S+)", open(f).read())
        if m:
            have.add(m.group(1).rstrip("/").lower())

    seen, accepted, rejected = set(), [], []
    for t in TOPICS:
        q = urllib.parse.urlencode({"q": f"topic:{t} stars:>={a.min_stars}",
                                    "sort": "stars", "order": "desc", "per_page": a.per_topic})
        try:
            items = gh(f"{SEARCH}?{q}").get("items", [])
        except Exception as e:                                  # noqa: BLE001
            print(f"  topic {t}: search failed ({e})", file=sys.stderr)
            continue
        for r in items:
            if r["full_name"] in seen:
                continue
            seen.add(r["full_name"])
            if r["html_url"].rstrip("/").lower() in have:
                rejected.append((r["full_name"], "already in the registry")); continue
            why = reject(r, a.min_stars, a.max_stale_days)
            (rejected.append((r["full_name"], why)) if why else accepted.append(r))
        time.sleep(2 if not TOK else 0.7)                       # search API is rate-limited hard

    print(f"\nscanned {len(seen)} repos across {len(TOPICS)} topics")
    print(f"  accepted {len(accepted)}   rejected {len(rejected)}\n")
    by_reason: dict[str, int] = {}
    for _, why in rejected:
        by_reason[why] = by_reason.get(why, 0) + 1
    print("rejections by reason:")
    for why, n in sorted(by_reason.items(), key=lambda x: -x[1]):
        print(f"  {n:>4}  {why}")

    print("\nwould add:" if a.dry_run else "\nwriting:")
    for r in sorted(accepted, key=lambda x: -(x.get("stargazers_count") or 0)):
        m = manifest(r, a.submitted_by)
        print(f"  {m['namespace']}/{m['name']:<32} {m['kind']:<10} "
              f"{r['license']['spdx_id']:<14} {r.get('stargazers_count'):>7,}*")
        if not a.dry_run:
            d = os.path.join("packages", m["namespace"])
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, m["name"] + ".yaml"), "w") as f:
                # JSON is a subset of YAML, so json.dumps gives correctly quoted scalars, lists and
                # booleans without needing pyyaml here and without hand-rolling escaping.
                for k, v in m.items():
                    # ensure_ascii=False: keep real UTF-8 rather than surrogate-pair \u escapes,
                    # which YAML mis-counts on the way back in (see clean_summary).
                    f.write(f"{k}: {json.dumps(v, ensure_ascii=False)}\n")
    if a.dry_run:
        print("\n(dry run — nothing written. Drop --dry-run to write manifests, then run validate.py)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
