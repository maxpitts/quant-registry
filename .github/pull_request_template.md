## Adding / updating a package

- [ ] Manifest is at `packages/<namespace>/<name>.yaml` and `<namespace>` is my GitHub handle
- [ ] `commit` is a full 40-char SHA (not a branch or tag — those can move after review)
- [ ] The repo is public and the license in the manifest matches the license in the repo
- [ ] If I quoted a performance number, it has a `period` and a `universe`

### If your package quotes performance, read this

The registry does not verify anything and will never claim to. Your tier is displayed next to every
number you publish:

- `self_reported` — shown as **unverified**. Fine, and it's the honest default.
- `reproducible` — you supplied a command someone else can run.
- `live_record` — you have an append-only log where signals were timestamped before the outcome.

Overstating your tier is the one thing that gets a package removed. Understating it costs you
nothing. If you're unsure, use `self_reported`.
