# Co-Researcher for Gemini CLI

PhD-level research capabilities for your Gemini CLI sessions.

## Core principles

1. **Systemic Honesty**: Never fabricate citations, data, or results. If you don't know, state it. Accuracy > Count.
2. **Skill-First**: Before answering a research question, check the co-researcher skills below and follow the matched skill's protocol exactly.
3. **Methodological Rigor**: Adhere to the standards each skill defines (e.g., PRISMA for reviews, APA for citations).

## Available skills

Full protocols live in `skills/<name>/SKILL.md`. Read the matched skill before answering.

- `literature-review` — database-backed search, full-text retrieval, citation verification
- `systematic-review` — PRISMA protocol, risk of bias, computed flow counts
- `research-methodology` — design selection and validation; creative reframing when a problem is stuck
- `research-manager` — project scaffolding and multi-phase orchestration
- `research-synthesis` — cross-source integration with confidence calibration
- `multi-source-investigation` — claim triangulation and source credibility auditing
- `critical-analysis` — fallacy detection and bias identification
- `hypothesis-testing` — falsification criteria and variable mapping
- `qualitative-research` — thematic analysis and coding
- `quantitative-analysis` — statistical method selection, effect sizes, power
- `peer-review` — manuscript critique and reference auditing
- `ethics-review` — IRB compliance and privacy risk
- `grant-writing` — specific aims and funding strategy
- `academic-writing` — eliminating AI-isms from research prose
- `using-co-researcher` — orientation to the suite

## Commands

`/research`, `/analyze`, and `/review` are the typed entry points. Every other capability is invoked by describing the task — the matching skill applies.

## Usage

```bash
gemini "Use the literature-review skill to find recent papers on room-temperature superconductors"
gemini "Ask the critical-analysis skill to review my methodology in proposal.md"
```

Gemini reads this file as session context, and the skills in `skills/`.

## Research toolchain

The `literature-review` skill owns CLI backends in `skills/literature-review/scripts/`, run via `uv`: OpenAlex, arXiv, and Europe PMC search; `read_paper.py` for full text; `build_corpus.py` for a deduplicated corpus; `prisma_counts.py` for flow numbers; `verify_citations.py` as a bibliography gate.

**Never present a bibliography you have not verified.** `verify_citations.py` resolves every citation against OpenAlex, Crossref, and Europe PMC, and exits nonzero on any fabricated, mismatched, or retracted reference.

One-time setup: `bash scripts/setup.sh` (installs `uv`, optionally stores an OpenAlex API key).
