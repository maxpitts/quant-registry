# Package manifest

One YAML file per package under `packages/<namespace>/<name>.yaml`. Adding a package is a pull
request against this repo. Nothing else is required of you, and nothing here is hosted by us.

## The registry indexes, it does not host

Your code stays in your repo, under your account, under your license. This registry stores a
pointer, a description, and a checksum — a few KB per package.

That is not a cost-saving dodge; it is the design. Hosting weights is what makes an open registry
unfundable (petabytes of egress with no revenue is why every ownerless model mirror ends up
torrent-based). Indexing instead means this thing costs approximately nothing to run forever,
which is the only version of "owned by nobody" that survives its author losing interest. It also
means the registry never possesses anyone's code, so there is nothing to seize, subpoena, or
quietly de-list — a fork of this repo is a complete, working registry.

Homebrew, pkg.go.dev and the Arch AUR all work this way for the same reasons.

## Fields

| field | required | notes |
|---|---|---|
| `name` | yes | lowercase, `[a-z0-9-]`, unique within namespace |
| `namespace` | yes | your GitHub handle or org |
| `version` | yes | semver |
| `kind` | yes | `strategy`, `model`, `feature`, `risk`, `execution`, `data`, `harness` |
| `summary` | yes | one line, <=120 chars |
| `repo` | yes | https URL to the source |
| `license` | yes | SPDX identifier |
| `commit` | yes | full 40-char SHA the manifest describes |
| `asset_classes` | yes | `equity`, `option`, `future`, `fx`, `crypto`, `rates` |
| `timeframes` | no | `tick`, `1m`, `5m`, `1h`, `1d`, `1w` |
| `requires` | no | free-text dependency list |
| `performance` | no | **see below — this is the field that decides whether this registry is worth anything** |
| `record` | no | URL to an append-only timestamped out-of-sample record |

## The performance field

Any registry that lets people publish trading strategies is one bad decision away from being a
place people advertise fake returns. The decision is how you treat self-reported numbers.

The rule here: **every performance claim carries its provenance, and the provenance is rendered as
prominently as the number.** There are exactly three tiers and the validator enforces them.

- `self_reported` — the author ran a backtest and typed the result. This is the default and it is
  displayed as *unverified* everywhere it appears. It is not evidence. It is a claim.
- `reproducible` — the manifest includes a `reproduce` block: a command, a data source, and a
  period. Someone else can run it and get the same number. Still in-sample, but falsifiable.
- `live_record` — a `record` URL to an append-only log where signals were timestamped *before*
  the outcome was known. This is the only tier that means anything.

A package may omit `performance` entirely. That is respectable and common: a volatility estimator
or an execution algo has no return to report, and most of the genuinely useful contributions here
will be in that category.

What the validator refuses: a Sharpe ratio without a period, returns without a universe, any
`live_record` tier without a resolvable `record` URL, and any claim of verification by the registry
itself. The registry verifies nothing. It records who claimed what, and when.
