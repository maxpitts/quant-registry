#!/usr/bin/env python3
"""validate.py — gatekeeper for the registry.

Runs on every pull request. Its job is not to judge whether a strategy is good — that is not
knowable from a manifest and pretending otherwise would be the whole problem. Its job is to make
sure every claim in the registry carries its provenance, so a reader can tell a backtest someone
typed in from a record that was timestamped before the outcome was known.

    python3 validate.py packages/            validate every manifest
    python3 validate.py packages/foo/bar.yaml
"""
from __future__ import annotations

import glob, os, re, sys

try:
    import yaml
except ImportError:
    sys.exit("needs pyyaml:  pip3 install pyyaml")

KINDS = {"strategy", "model", "feature", "risk", "execution", "data", "harness"}
ASSETS = {"equity", "option", "future", "fx", "crypto", "rates"}
TIMEFRAMES = {"tick", "1m", "5m", "15m", "1h", "4h", "1d", "1w"}
TIERS = {"self_reported", "reproducible", "live_record"}
REQUIRED = ["name", "namespace", "version", "kind", "summary", "repo", "license",
            "asset_classes"]
# `commit` is required for author-submitted packages only. See the unaffiliated rules below.
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")

# Words that assert someone else vouched for the numbers. The registry vouches for nothing, and a
# manifest that implies otherwise is the exact failure this project has to avoid.
FORBIDDEN = re.compile(
    r"\b(verified by|audited|guaranteed|risk[- ]free|certified|endorsed by)\b", re.I)


def check(path: str) -> list[str]:
    errs: list[str] = []
    def bad(m): errs.append(m)

    try:
        d = yaml.safe_load(open(path)) or {}
    except Exception as e:
        return [f"unparseable YAML: {e}"]
    if not isinstance(d, dict):
        return ["manifest must be a YAML mapping"]

    for f in REQUIRED:
        if not d.get(f):
            bad(f"missing required field: {f}")
    if errs:
        return errs

    if not NAME_RE.match(str(d["name"])):
        bad(f"name must be lowercase [a-z0-9-]: {d['name']!r}")
    if not NAME_RE.match(str(d["namespace"])):
        bad(f"namespace must be lowercase [a-z0-9-]: {d['namespace']!r}")
    if not SEMVER_RE.match(str(d["version"])):
        bad(f"version must be semver: {d['version']!r}")
    # ---- listing provenance: did the author submit this, or are we indexing it? -----------
    # A third-party listing is how a registry stops being empty on day one, but it must never
    # read as though the upstream author participated. Three rules follow from that, and each
    # exists because the alternative would be the registry speaking for someone.
    unaff = bool(d.get("unaffiliated"))
    if unaff:
        if not d.get("submitted_by"):
            bad("unaffiliated listings require submitted_by (who added it, since the author did not)")
        if d.get("commit"):
            bad("unaffiliated listings must NOT pin a commit — the pin exists to record which "
                "revision a submitter vouched for, and nobody vouched for this one")
        if d.get("performance"):
            bad("unaffiliated listings must NOT carry a performance block — the registry does not "
                "get to publish numbers on behalf of an author who never submitted them")
    else:
        if not SHA_RE.match(str(d.get("commit", ""))):
            bad("commit must be a full 40-char SHA — a tag or branch can be moved after review")
    if d["kind"] not in KINDS:
        bad(f"kind must be one of {sorted(KINDS)}: {d['kind']!r}")
    if len(str(d["summary"])) > 120:
        bad(f"summary is {len(str(d['summary']))} chars, max 120")
    if not str(d["repo"]).startswith("https://"):
        bad("repo must be an https URL")

    # path must match the manifest, or the index and the tree disagree
    want = os.path.join("packages", str(d["namespace"]), str(d["name"]) + ".yaml")
    if os.path.normpath(path).replace(os.sep, "/") != want:
        bad(f"file must live at {want}")

    ac = d.get("asset_classes") or []
    if not isinstance(ac, list) or not ac:
        bad("asset_classes must be a non-empty list")
    else:
        for a in ac:
            if a not in ASSETS:
                bad(f"unknown asset_class {a!r}; allowed {sorted(ASSETS)}")
    for t in d.get("timeframes") or []:
        if t not in TIMEFRAMES:
            bad(f"unknown timeframe {t!r}; allowed {sorted(TIMEFRAMES)}")

    blob = " ".join(str(d.get(k, "")) for k in ("summary", "description"))
    for m in FORBIDDEN.finditer(blob):
        # The rule is about CLAIMS, not vocabulary. "not endorsed by anyone" is exactly the kind
        # of honest disclaimer this registry wants, and an earlier version of this check rejected
        # its own auto-generated manifests for containing the word. Look back a short window for a
        # negation before treating a match as an assertion.
        lead = blob[max(0, m.start() - 22):m.start()].lower()
        if re.search(r"\b(not|never|no|neither|nor|without|isn'?t|aren'?t|hasn'?t|haven'?t)\b[\s\w]{0,12}$", lead):
            continue
        bad(f"claims external validation ({m.group(0)!r}) — the registry verifies nothing "
            f"and manifests may not imply that it does")
        break

    # ---- the performance rules: every number carries its provenance ----------------------
    p = d.get("performance")
    if p is not None:
        if not isinstance(p, dict):
            bad("performance must be a mapping")
            return errs
        tier = p.get("tier")
        if tier not in TIERS:
            bad(f"performance.tier must be one of {sorted(TIERS)}, got {tier!r}")
        has_number = any(k in p for k in ("sharpe", "cagr", "return", "win_rate", "max_drawdown"))
        if has_number:
            if not p.get("period"):
                bad("performance quotes a number without a period — a Sharpe with no window "
                    "is not a claim anyone can check")
            if not p.get("universe"):
                bad("performance quotes a number without a universe")
        if tier == "reproducible" and not (p.get("reproduce") or {}).get("command"):
            bad("tier 'reproducible' requires performance.reproduce.command")
        if tier == "live_record":
            r = d.get("record")
            if not r or not str(r).startswith("https://"):
                bad("tier 'live_record' requires a resolvable https `record` URL — that tier is "
                    "the only one that means anything, so it does not get to be unfalsifiable")
    return errs


def main() -> int:
    args = sys.argv[1:] or ["packages/"]
    files: list[str] = []
    for a in args:
        files += sorted(glob.glob(os.path.join(a, "**", "*.yaml"), recursive=True)) \
            if os.path.isdir(a) else [a]
    if not files:
        print("no manifests found")
        return 0
    total = 0
    for f in files:
        errs = check(f)
        total += len(errs)
        print(("FAIL " if errs else "ok   ") + f)
        for e in errs:
            print(f"       - {e}")
    print(f"\n{len(files)} manifest(s), {total} problem(s)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
