---
title: "AI Personal Knowledge Base (PKB) Guides - Spisak & Karpathy"
source_type: "external_research"
author: "ChatGPT, Grok, Nick Spisak (@NickSpisak_)"
date: "2026-04-09"
tags: ["pkm", "second-brain", "llm-wiki", "compounding"]
---

# Source: AI Personal Knowledge Base (PKB) Guides

This source integrates insights from Nick Spisak's "Second Brain" architecture (based on Andrej Karpathy's ideas) and supplementary guides from ChatGPT and Grok.

## Core Architecture (The 3-Folder Rule)
1. **raw/**: Immutable data lake. Original sources (PDFs, transcripts, notes).
2. **wiki/**: Refined, semi-structured knowledge graph. AI-generated and distilled.
3. **outputs/**: Reasoning results, query reports, and new insights.

## Knowledge Compounding Loop
- Every query result saved in `outputs/` should be evaluated for "compounding" back into the `wiki/`.
- This ensures the AI gets "smarter" with every interaction.

## Maintenance (The Archivist's Duty)
- **Health Checks**: Regular scans for contradictions, source-less claims, and orphan nodes.
- **Incremental Updates**: Avoid full wiki rewrites; use diffs and versioning.
- **Source Hierarchy**: 1. Raw (Truth) -> 2. Processed -> 3. Wiki (Derived).

## Strategic Enhancements for Angella
- **Hybrid RAG**: Combine flat Markdown files with Vector DB (FAISS/Chroma) for high-performance retrieval.
- **Graph RAG**: Map relationships between components and SOPs using Obsidian-style bidirectional links.
- **Self-Healing**: Automated scripts to detect stale knowledge or gaps in documentation.

## References
- Spisak's Original Concept: [X Post](https://x.com/NickSpisak_/status/2040448463540830705)
