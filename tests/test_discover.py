"""Filters, classification, and the YAML round trip that broke on real data."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import discover as D
import yaml

fails = []
def ck(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"   got {got!r} want {want!r}"))
    if not ok: fails.append(label)

def repo(fn, stars=1000, lic="MIT", desc="", topics=None, archived=False, fork=False, pushed="2026-08-01"):
    return {"full_name": fn, "name": fn.split("/")[1], "html_url": "https://github.com/" + fn,
            "stargazers_count": stars, "license": ({"spdx_id": lic} if lic else None),
            "description": desc, "topics": topics or [], "archived": archived, "fork": fork,
            "pushed_at": pushed}

print("rejection filters (cases taken from live GitHub results)")
ck("curated link list",   D.reject(repo("w/awesome-quant", 29244, "MIT", "Curated list of awesome libraries", ["awesome"]), 300, 365), "curated link list, not a package")
ck("no licence",          D.reject(repo("a/b", 5000, None), 300, 365), "unusable licence (None)")
ck("NOASSERTION licence", D.reject(repo("a/b", 5000, "NOASSERTION"), 300, 365), "unusable licence (NOASSERTION)")
ck("book companion",      D.reject(repo("s/ml4t", 20697, "MIT", "Code for Machine Learning for Trading 3rd edition"), 300, 365), "book/course companion")
ck("fork",                D.reject(repo("a/b", 5000, "MIT", fork=True), 300, 365), "fork")
ck("archived",            D.reject(repo("a/b", 5000, "MIT", archived=True), 300, 365), "archived")
ck("under star floor",    D.reject(repo("a/b", 10, "MIT"), 300, 365), "under 300 stars")
ck("healthy repo passes", D.reject(repo("q/lean", 21380, "Apache-2.0", "Algorithmic trading engine"), 300, 365), None)

print("\nkind classification")
ck("backtester -> harness",   D.classify(repo("k/bt", desc="Backtest trading strategies in Python")), "harness")
ck("bot -> execution",        D.classify(repo("j/jesse", desc="An advanced crypto trading bot")), "execution")
ck("optimiser -> risk",       D.classify(repo("g/gs", desc="Toolkit for risk management and derivatives")), "risk")
ck("indicators -> feature",   D.classify(repo("t/ta", desc="Python wrapper for TA-Lib technical analysis library")), "feature")
ck("strategies -> strategy",  D.classify(repo("f/fs", desc="Free trading strategies for the bot", topics=["trading-strategies"])), "strategy")

print("\nasset inference")
ck("crypto detected",  D.assets(repo("a/b", desc="binance and coinbase market making")), ["crypto"])
ck("options detected", D.assets(repo("a/b", desc="option greeks and implied vol surface")), ["option"])
ck("equity default",   D.assets(repo("a/b", desc="a generic quant library")), ["equity"])

print("\nsummary survives the YAML round trip")
# The real failure: json.dumps writes emoji as UTF-16 surrogate PAIRS and YAML does not recombine
# them, so a 120-char Python string parsed back as 122 and failed validation.
hard = "[\U0001F525updating ...] AI 自动量化 AI-powered Quantitative Investment Research Platform. \U0001F4C3 docs: https://example.com/x/y/z"
s = D.clean_summary(hard)
back = yaml.safe_load("summary: " + json.dumps(s, ensure_ascii=False))["summary"]
ck("round-trip length preserved", len(back), len(s))
ck("within the 120 limit", len(back) <= 120, True)
ck("leading banner stripped", s.startswith("["), False)
long_emoji = "\U0001F680 \U0001F525 " + "x" * 300
ck("emoji-heavy truncation <= 120", len(yaml.safe_load("summary: " + json.dumps(D.clean_summary(long_emoji), ensure_ascii=False))["summary"]) <= 120, True)
ck("whitespace collapsed", D.clean_summary("  a\n\n b  "), "a b")

print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILURES: {fails}"))
sys.exit(1 if fails else 0)
