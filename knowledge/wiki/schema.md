# LLM-Wiki Operations Schema

This document defines the conventions for how the Angella Agent manages the `knowledge/wiki` and `knowledge/raw` directories.

## Architecture
- `knowledge/raw/`: Immutable source materials (articles, logs, notes). The agent READS these but never modifies them.
- `knowledge/wiki/`: The LLM-maintained directory of markdown files. The agent creates and updates these.
- `knowledge/wiki/index.md`: The central Table of Contents and routing hub.
- `knowledge/wiki/log.md`: The chronological, append-only log of agent actions.

## 1. Ingest Operation
When a new file is added to `raw/` or standard execution yields a key learning:
1. **Analyze:** Read the source material.
2. **Synthesize:** Write a new conceptual markdown page in `wiki/` (or update an existing one).
3. **Index:** Add a reference to the page in `wiki/index.md` with a one-sentence summary.
4. **Log:** Append to `wiki/log.md` using the format `## [YYYY-MM-DD HH:MM] ingest | Title`.

## 2. Query Operation
When answering complex questions or exploring past context:
1. **Discover:** Start by reading `wiki/index.md`.
2. **Navigate:** Read the specific pages linked around the topic.
3. **Compound:** If the query uncovers a new connection between two isolated concepts, write a new synthesis page into the wiki! Don't just answer in chat.
4. **Log:** Append to `wiki/log.md` via `## [YYYY-MM-DD HH:MM] query | Subject`.

## 3. Lint Operation
When the user asks to "audit the wiki":
- Read the index.
- Search for orphan files (files not in the index) and add them.
- Find contradictory statements and annotate them.
- Log the lint action in `log.md`.
