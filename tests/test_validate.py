"""Every rule that keeps this registry from becoming a place people advertise fake returns."""
import os, sys, tempfile, textwrap
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import validate as V

GOOD = """
name: {name}
namespace: acme
version: 1.0.0
kind: strategy
summary: A summary.
repo: https://github.com/acme/x
license: MIT
commit: a1b2c3d4e5f60718293a4b5c6d7e8f9012345678
asset_classes: [equity]
"""

fails = []
def run(label, body, want_ok=None, want_err=None, name="thing", ns="acme"):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "packages", ns); os.makedirs(p)
    fp = os.path.join(p, f"{name}.yaml"); open(fp, "w").write(textwrap.dedent(body))
    cwd = os.getcwd(); os.chdir(d)
    try:
        errs = V.check(os.path.relpath(fp, d))
    finally:
        os.chdir(cwd)
    if want_ok:
        ok = not errs
        detail = "" if ok else f"  unexpected: {errs}"
    else:
        ok = any(want_err.lower() in e.lower() for e in errs)
        detail = "" if ok else f"  got: {errs}"
    print(f"  {'ok  ' if ok else 'FAIL'} {label}{detail}")
    if not ok: fails.append(label)

print("baseline")
run("valid minimal manifest", GOOD.format(name="thing"), want_ok=True)

print("\nidentity + integrity")
run("uppercase name rejected", GOOD.format(name="Thing").replace("name: Thing","name: Thing"),
    want_err="lowercase", name="Thing")
run("non-semver version", GOOD.format(name="thing").replace("1.0.0","v1"), want_err="semver")
run("branch instead of SHA", GOOD.format(name="thing").replace(
    "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678","main"), want_err="40-char SHA")
run("unknown kind", GOOD.format(name="thing").replace("kind: strategy","kind: vibes"),
    want_err="kind must be one of")
run("http repo rejected", GOOD.format(name="thing").replace("https://","http://"),
    want_err="https")
run("unknown asset class", GOOD.format(name="thing").replace("[equity]","[beanie_babies]"),
    want_err="unknown asset_class")

print("\nclaims of external validation")
run("'audited' rejected", GOOD.format(name="thing") + "description: Fully audited results.\n",
    want_err="verifies nothing")
run("'guaranteed' rejected", GOOD.format(name="thing").replace(
    "summary: A summary.","summary: Guaranteed returns every month."), want_err="verifies nothing")

print("\nperformance provenance — the rules that matter")
run("sharpe with no period", GOOD.format(name="thing") + textwrap.dedent("""
    performance:
      tier: self_reported
      universe: SPX
      sharpe: 2.4
    """), want_err="without a period")
run("sharpe with no universe", GOOD.format(name="thing") + textwrap.dedent("""
    performance:
      tier: self_reported
      period: 2020/2025
      sharpe: 2.4
    """), want_err="without a universe")
run("bad tier", GOOD.format(name="thing") + textwrap.dedent("""
    performance:
      tier: trust_me
    """), want_err="tier must be one of")
run("reproducible needs a command", GOOD.format(name="thing") + textwrap.dedent("""
    performance:
      tier: reproducible
      period: 2020/2025
      universe: SPX
      sharpe: 1.1
    """), want_err="reproduce.command")
run("live_record needs a record URL", GOOD.format(name="thing") + textwrap.dedent("""
    performance:
      tier: live_record
      period: 2025/present
      universe: SPX
      sharpe: 1.1
    """), want_err="resolvable https `record` URL")
run("full self_reported passes", GOOD.format(name="thing") + textwrap.dedent("""
    performance:
      tier: self_reported
      period: 2020/2025
      universe: SPX
      sharpe: 1.1
    """), want_ok=True)
run("no performance block is fine", GOOD.format(name="thing"), want_ok=True)

print("\npath integrity")
run("filename must match name field", GOOD.format(name="thing"),
    want_err="must live at", name="different")

print("\nunaffiliated (third-party) listings")
UNAFF = """
name: thing
namespace: acme
version: 1.0.0
kind: harness
summary: A summary.
repo: https://github.com/acme/x
license: MIT
asset_classes: [equity]
unaffiliated: true
submitted_by: maxpitts
"""
run("valid third-party listing", UNAFF, want_ok=True)
run("needs submitted_by", UNAFF.replace("submitted_by: maxpitts",""), want_err="require submitted_by")
run("must not pin a commit", UNAFF + "commit: a1b2c3d4e5f60718293a4b5c6d7e8f9012345678\n",
    want_err="must NOT pin a commit")
run("must not carry performance", UNAFF + "performance:\n  tier: self_reported\n",
    want_err="must NOT carry a performance block")
run("author-submitted still needs a SHA", UNAFF.replace("unaffiliated: true","unaffiliated: false"),
    want_err="40-char SHA")


print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILURES: {fails}"))
sys.exit(1 if fails else 0)
