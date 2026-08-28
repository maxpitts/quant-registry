#!/usr/bin/env python3
"""build_index.py — collapse every manifest into one index.json the site can read.

Same reason openwatch has metrics.py: the browser should never walk the tree. One fetch, one file,
and the file stays small because manifests are kilobytes.
"""
from __future__ import annotations
import datetime as dt, glob, json, sys, yaml

TIER_LABEL = {
    "self_reported": "Unverified — author's own backtest",
    "reproducible":  "Reproducible — includes a command to re-run",
    "live_record":   "Live record — signals timestamped before the outcome",
    None:            "No performance claimed",
}


def main() -> int:
    out, kinds, tiers = [], {}, {}
    for f in sorted(glob.glob("packages/**/*.yaml", recursive=True)):
        d = yaml.safe_load(open(f)) or {}
        p = d.get("performance") or {}
        tier = p.get("tier") if p else None
        # The label ships WITH the number, in the same object. A site can't render one without
        # the other by accident, which is the only way this stays honest at a glance.
        out.append({
            "id": f"{d.get('namespace')}/{d.get('name')}",
            "namespace": d.get("namespace"), "name": d.get("name"),
            "version": d.get("version"), "kind": d.get("kind"),
            "summary": d.get("summary"), "repo": d.get("repo"),
            "license": d.get("license"), "commit": d.get("commit"),
            "asset_classes": d.get("asset_classes") or [],
            "timeframes": d.get("timeframes") or [],
            "record": d.get("record"),
            # rendered as a badge; a reader must never mistake an index entry for a submission
            "listing": ("third_party_index" if d.get("unaffiliated") else "author_submitted"),
            "submitted_by": d.get("submitted_by"),
            "performance": ({**p, "tier_label": TIER_LABEL[tier]} if p else None),
            "verified_by_registry": False,   # always. the registry verifies nothing, by design.
            "manifest": f,
        })
        kinds[d.get("kind")] = kinds.get(d.get("kind"), 0) + 1
        tiers[str(tier)] = tiers.get(str(tier), 0) + 1

    idx = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "n": len(out), "by_kind": dict(sorted(kinds.items())),
           "by_tier": dict(sorted(tiers.items())),
           "disclaimer": ("This registry indexes packages; it does not host, test, endorse or "
                          "verify them. Performance figures are claims made by their authors. "
                          "Nothing here is investment advice."),
           "packages": sorted(out, key=lambda x: x["id"])}
    json.dump(idx, open("index.json", "w"), indent=1)
    print(f"index.json: {len(out)} packages  kinds={kinds}  tiers={tiers}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
