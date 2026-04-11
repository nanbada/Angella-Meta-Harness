# Angella Harness Wiki Schema

This wiki is the tracked knowledge layer that sits between raw control-plane evidence and operator-facing answers.

## Quality & Objectivity Rules

To ensure knowledge is robust and resistant to AI bias, every primary wiki page (Concepts, Components, SOPs) should aim to include:

- **Confidence Levels**: Tag claims or patterns as `confidence: high | medium | low` based on the volume of supporting evidence.
- **Counter-arguments**: Explicitly document why a certain pattern might *not* work or where it has failed in the past.
- **Data Gaps**: Identify what is currently unknown or unverified about the topic.

## Ingest Pipeline (Raw → Source → Wiki)

1. **Raw Inbox (`knowledge/sources/raw/`)**:
   - Dump point for clippings, PDFs, images, and links.
2. **Resolution Phase**:
   - **Media**: Images/diagrams must be analyzed and have a corresponding `.md` source page with a textual summary (OCR/Visual-to-Text).
   - **Links**: External URLs should be resolved to full content (transcripts/summaries) and archived in `knowledge/sources/`.
3. **Classification & Synthesis**:
   - `angella-archivist` processes resolved sources into structured `knowledge/components/`, `knowledge/concepts/`, or `knowledge/sops/` pages.
   - New pages are marked `explored: false` until reviewed or verified by a run.

## Layers
... (rest of the file)

1. Raw evidence
   - `.cache/angella/control-plane/**`
   - immutable run summaries, telemetry, failures, queue artifacts
2. Wiki
   - `knowledge/**`
   - tracked markdown owned by Angella
3. Schema
   - this file
   - conventions for ingest, query, lint, and linking

## Entry Points

- `knowledge/index.md`
  - content-oriented entrypoint
  - read first when searching broadly
- `telemetry/logs/harness_activity.md`
  - chronological entrypoint
  - read when recent changes matter
- `knowledge/sources/index.md`
  - raw-source registry for tracked docs, control-plane evidence mirrors, and saved query pages
- `docs/PARITY.md`
  - product-truth behavioral checklist

## Component Pages

- `knowledge/components/<component>.md`
- each page should summarize:
  - contract
  - related SOPs / skills
  - recent accepted runs
  - recent verification-only runs
  - current open failures

## Source Pages

- `knowledge/sources/<source-id>.md`
- each page should summarize:
  - source type
  - source path
  - compact summary
  - backlinks into tracked wiki

## Query Pages

- `knowledge/queries/<date>-<slug>.md`
- each page should include:
  - original query
  - answer summary
  - cited paths
  - generated artifacts
  - save reason

## Linking Rules

- prefer tracked wiki links over raw `.cache` links
- link component pages to related `knowledge/sops/` and `knowledge/skills/`
- link component pages to related source pages when recent run evidence exists
- link saved query pages back into index/log/source pages
- keep `docs/**` links as reference material, not as primary knowledge pages

## Log Rules

- `telemetry/logs/harness_activity.md` is append-only
- each event should use a stable marker so sync is idempotent
- event kinds:
  - accepted
  - verification
  - parity
  - lint
  - lint-audit
  - query

## Addendum Rules

- reuse the existing run-scoped addendum pattern for promoted SOP/skill pages
- never duplicate the same fingerprinted addendum
- prefer compact summaries over raw output dumps

## Search Rules

- builtin search indexes only tracked wiki pages and selected markdown docs
- optional `qmd` provider may be used when explicitly requested and installed
- no embedding/vector dependency in v1
- search snippets must include compaction telemetry

## Lint Rules

- detect orphan component/skill/sop/query/source pages
- detect broken relative links
- detect missing index/log registration
- detect stale component-page summaries
- detect schema/policy drift
- detect parity lane/evidence drift

## Non-Goals

- do not auto-ingest personal PKM vaults in v1
- do not treat estimated token savings as billing truth
- do not replace the existing control-plane evidence model
- do not default to local-only routing
- do not auto-install `qmd`
- do not behave like a commercial/enterprise observability platform
