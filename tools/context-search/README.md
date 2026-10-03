# Context search

Local hybrid search through pinned [QMD](https://github.com/tobi/qmd). Requires Node.js >=22 and access to the private [context repository](https://github.com/milesrack/gqh-systematic-track-context).

## Setup

```sh
node tools/context-sync.mjs --no-refresh
node tools/context.mjs setup
```

Setup installs the locked CLI, downloads local models and builds the index. Python research dependencies remain under uv.

## Retrieval

```sh
node tools/context.mjs query 'intent: Find participant constraints.
lex: forced selling inventory
vec: traders who must reduce exposure' -c notes --json -n 5
node tools/context.mjs search 'FDXS' -c notes --json -n 5
node tools/context.mjs get '<returned-document-uri>'
```

`query` combines keyword and semantic search with reranking. `search` is keyword-only; `vsearch` is semantic-only. Use explicit query terms to avoid expansion drift. `get` accepts document URIs, IDs and `:start:count` line ranges. Other QMD arguments pass through.

## Refresh

```sh
node tools/context-sync.mjs  # pull clean main, then refresh
node tools/context.mjs refresh  # index local edits
```

Sync refuses dirty, non-main, unrelated or unpublished checkouts. Submit context edits through its PR template. Refresh processes additions, changes and removals.

## Storage

The canonical checkout is `.agent-work/shared/`. Search collections are `notes/**/*.md`, `library/*/text/**/*.{md,txt}` and `sources/*/*-starter/**/*.md`. Originals, audio and provenance remain preserved but unindexed. New modules need only refresh.

Models and indexes are local in `.agent-work/.cache/`; CLI dependencies are in ignored `node_modules/`. `GQH_CONTEXT_DIR` selects a standalone library and stores its cache there.

On the tested macOS package, model inference requires Metal access even with `QMD_FORCE_CPU=1`. Keyword search works in a restricted sandbox. If refresh fails, disclose stale coverage and search source files directly.
