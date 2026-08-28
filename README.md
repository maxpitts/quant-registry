# Quant Registry

An open, ownerless index of trading models, strategies, features, risk modules and execution algos.
Like a package registry: you publish a manifest, the registry makes your work findable, and your
code stays in your repo under your license.

## It indexes, it does not host

Your code never moves. The registry stores a pointer, a description and a pinned commit — a few KB
per package.

This is the design, not a shortcut. Hosting is what makes an open registry unfundable, and it's
also what makes one capturable: a registry that holds everyone's code is a thing that can be
bought, subpoenaed, or quietly made to prefer one vendor. This one can't, because it holds nothing.
Fork it and you have a complete working registry. Homebrew, pkg.go.dev and the AUR all work this
way for the same reasons.

## The honest problem, stated up front

Most registries of trading strategies become places people advertise fake returns. That is the
default outcome and avoiding it is the main design constraint here.

The reason it happens is that a backtest is trivially forgeable and a good one is indistinguishable
from a bad one at a glance. So the rule is: **every performance number carries its provenance, and
the provenance is displayed as prominently as the number.**

| tier | what it means | how it renders |
|---|---|---|
| `self_reported` | the author ran a backtest and typed the result | **Unverified — author's own backtest** |
| `reproducible` | ships a command anyone can run to get the same number | Reproducible |
| `live_record` | signals timestamped in an append-only log *before* the outcome | Live record |

`index.json` carries `verified_by_registry: false` on every package, permanently. The registry
verifies nothing. It records who claimed what, and when.

The validator refuses a Sharpe without a period, returns without a universe, a `live_record` tier
without a resolvable record URL, and any wording that implies the registry vouched for you.

## Not everything here has a return

The most useful contributions probably won't. A volatility estimator, a slippage model, a regime
classifier, a feature library, an execution algo — none of these have a P&L to report, and none of
them get worse when other people use them.

That non-rival layer is where an open registry has a real advantage, because sharing costs the
author nothing. Strategies are welcome too; just be aware that a strategy someone is willing to
publish is usually one that stopped working at size, and the registry will not pretend otherwise.

## Publishing

1. Fork this repo
2. Add `packages/<your-handle>/<name>.yaml` (see `schema/MANIFEST.md`)
3. `python3 validate.py packages/` until it's clean
4. Open a PR

CI validates every manifest. On merge, `index.json` rebuilds automatically.

## Layout

```
packages/<namespace>/<name>.yaml   the manifests — one PR each
validate.py                        the gate; enforces provenance rules
build_index.py                     manifests -> index.json for the site
schema/MANIFEST.md                 field reference
tests/test_validate.py             17 tests over every rule
```

## Licence and disclaimer

Registry code MIT; the index is CC0. Each package is under its own licence, in its own repo.

Nothing in this registry is investment advice, and nothing in it has been tested by anyone but its
author. Trading involves substantial risk of loss.
