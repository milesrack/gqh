# Context search

Pinned [QMD](https://github.com/tobi/qmd) CLI for private research context. Requires Node.js >=22; the Python research environment continues to use uv.

```sh
node tools/context-sync.mjs --no-refresh
node tools/context.mjs setup
node tools/context.mjs query 'participants forced to reduce exposure' -c notes --json -n 5
node tools/context.mjs search 'NNQ' -c literature --json -n 5
node tools/context.mjs get 'qmd://notes/strategy-ideas/etf-trend-handoff.md'
node tools/context-sync.mjs
```

Setup installs the locked CLI, indexes the library and embeds its texts. The first embedding/query downloads local models. Refresh processes additions, changes and removals. `query` performs hybrid retrieval; `search` is keyword-only; `vsearch` is semantic-only. All other arguments pass through to QMD, including `status`, `doctor`, line ranges and `--full-path`.

The private [context repository](https://github.com/milesrack/gqh-systematic-track-context) is cloned at `.agent-work/shared/`; it is independent of strategy Git history. `context-sync.mjs` refuses dirty, non-main, unrelated or unpublished checkouts. It fast-forwards context, then refreshes QMD. Edit context on a feature branch and submit a PR there; synchronisation never commits or merges edits.

The context checkout holds all notes, reference bodies, raw transcripts/audio, source captures and provenance, shared privately with written consent. QMD indexes `notes/**/*.md` as `notes`, `library/*/text/**/*.{md,txt}` as `literature` and `sources/*/*-starter/**/*.md` as `starter`. New modules need only refresh. Originals, audio, manifests and scratch runs are excluded from search, while remaining preserved in the context repository. Generated configuration, index and models live in `.agent-work/.cache/`; installed packages stay in ignored `node_modules/`. No model API credentials are needed; cloning requires GitHub access.

Teammates clone the entire context through the sync command and rebuild their own index. For a standalone context library:

```sh
GQH_CONTEXT_DIR=/path/to/context node tools/context.mjs setup
GQH_CONTEXT_DIR=/path/to/context node tools/context.mjs query 'liquidity pressure' --json -n 5
```

An explicit `GQH_CONTEXT_DIR` indexes only that library and stores its generated cache there. The launcher regenerates absolute paths at each destination. Each machine maintains its own index. Do not commit credentials or market data.

Model commands require permitted hardware access. The tested macOS package still requests a Metal context under `QMD_FORCE_CPU=1`; restrictive sandboxes therefore need permitted local Metal access. Keyword search works without it. A failed refresh is incomplete coverage; disclose the failure. Retrieval does not verify a claim or establish strategy novelty.
