# Evaluation Framework

Run evaluation tests against co-researcher agents to assess quality and performance.

## Quick Start

```bash
python run_eval.py list           # List all available tests
python run_eval.py all            # Run all tests (default model: claude)
python run_eval.py all -j 4       # Run with 4 parallel jobs
python run_eval.py literature-reviewer  # Run all tests for an agent
python run_eval.py literature-reviewer zero-results  # Run specific test
python run_eval.py literature-review-integrity       # Paired integrity run
```

## CLI Usage

```bash
python run_eval.py [args] [-m MODEL] [-j JOBS] [-v]

# Examples
python run_eval.py list                              # List available tests
python run_eval.py all -j 8                # Run all tests with 8 jobs
python run_eval.py critical-analyzer -j 4            # Run all analyst tests
python run_eval.py all --model "codex:gpt-5.2 high" # Use GPT-5.2 with high reasoning
python run_eval.py critical-analyzer fallacy-detection  # Run specific test
python run_eval.py literature-reviewer -v            # Verbose output
python run_eval.py literature-review-integrity --model "codex:gpt-5.2-codex high"
python run_eval.py literature-review-integrity --model codex --resume RUN_ID  # finish a run cut short
python run_eval.py literature-review-integrity --official-cases-dir PATH --dry-run-manifest-audit
```

`--resume RUN_ID` re-runs only the cases that run did not evaluate (for
example after a usage limit), carries its finished cases over from their
verified artifacts and snapshots, and writes one new complete run whose
provenance records `resumed_from`. It is refused unless both runs use the same
model and the same clean commit, so one report never mixes code versions.

## Model Options

| Provider | Syntax | Example |
|----------|--------|---------|
| `claude` | `claude[:version]` | `claude:sonnet`, `claude:opus` |
| `gemini` | `gemini[:version]` | `gemini:gemini-3-flash-preview` |
| `codex`  | `codex[:version [extra]]` | `codex:gpt-5.2-codex high` |

> [!TIP]
> Use quotes for model strings with spaces: `--model "codex:gpt-5.2-codex high"`

## Available Tests (26 total)

| Agent | Test | Difficulty |
|-------|------|------------|
| **critical-analysis** | bias-identification | Hard |
| | contradictory-evidence | Hard |
| | fallacy-detection | Medium |
| | methodology-critique | Medium |
| **ethics-review** | privacy-risk | Hard |
| **grant-writing** | grant-writing | Medium |
| **hypothesis-testing** | hypothesis-formulation | Medium |
| | unfalsifiable-claim | Hard |
| | variable-mapping | Hard |
| **lateral-thinking** | analogy-finding | Hard |
| | constraint-satisfaction | Hard |
| | first-principles | Hard |
| **literature-review** | basic-search | Easy |
| | citation-chain | Hard |
| | gap-analysis | Medium |
| | hallucination-detection | Hard |
| **peer-review** | manuscript-critique | Hard |
| **qualitative-research** | coding-strategy | Medium |
| | leading-questions | Hard |
| | thematic-analysis | Medium |
| **quantitative-analysis** | effect-size-interpretation | Medium |
| | simpson-paradox | Hard |
| | stat-method-selection | Medium |
| **research-methodology** | methodology-selection | Medium |
| | methodology-validation | Hard |
| | mixed-methods-design | Hard |

## Scoring (Task-Specific)

The framework uses specialized rubrics based on the agent's task domain:

| Rubric | Agents | Key Focus |
|--------|--------|-----------|
| `analytical-quality` | Critical, Lateral, Methodology | Logical rigor, fallacy detection |
| `quantitative-quality` | Quantitative Analyst | Statistical accuracy, method choice |
| `qualitative-quality` | Qualitative Researcher | Coding strategy, thematic depth |
| `design-quality` | Hypothesis, Ethics, Grant | Feasibility, ethics, variables |
| `research-quality` | Literature, Peer Review | Citation chain, gap analysis |
| `output-structure` | All | Organization, clarity (Fixed 25%) |

**Passing**: ≥70/100 overall (Hard tests: ≥80)

## Results & Benchmarking

### Prospective manifest audit (no execution)

The paired `--official-cases-dir PATH --dry-run-manifest-audit` options are
available only for `literature-review-integrity`. The dry run performs a
descriptor-safe audit of `commitment-index.json` and its listed manifest bytes,
then writes one deterministic JSON object to stdout. It does not open the
public-input paths committed by those manifests, use path-based directory
scans, read scorer annotations, construct an executor or judge, use the network,
or create result files. Every supplied-root and manifest-path component is
opened descriptor-relatively without following symlinks. Regular-file identity,
mode, owner, link count, size, modification time, and change time must remain
stable across each bounded read. Held in-root directory components must also
remain stable. Before accepting, the audit reopens each complete manifest chain
from the held root and rehashes its bytes. The completion barrier checks every
retained index/manifest component and leaf descriptor before and after that
full-set pass, then reopens the complete supplied-root chain from the filesystem
anchor. Every component and committed digest must match at that final
verification point. This is a fail-closed point-in-time audit, not a filesystem
lock against mutations after the command returns.

The index schema is closed and uses `schema_version: "1.0.0"` plus `cases`.
Each case entry contains exactly `case_id`, `manifest_path`, and
`manifest_sha256`. Each listed manifest uses the same schema version and
contains exactly `case_id` and `public_inputs`; every public-input entry contains
exactly `input_id`, `path`, `size`, and `sha256`. IDs are lowercase opaque IDs,
paths are NFC-normalized canonical relative POSIX paths, aliases use normalized
Unicode case folding, and hashes are lowercase SHA-256. Labels, expected
outcomes, reason codes, attack-family data, and annotations do not belong in
these manifests.

### Paired literature-review integrity runs

`literature-review-integrity` writes one append-only directory per run:

```text
results/runs/
├── index.json
└── <run_id>/
    ├── publication.json
    ├── summary.md
    ├── result.json
    ├── artifacts/
    │   └── <case_id>.json
    └── repair-rounds/
        └── <case_id>-round-<number>.json
```

`result.json` keeps `quality_score`, `integrity_score`, and integrity `status`
in separate fields for the model's first pass and the system's final snapshot.
The two views retain their Task 8 workspace digests, so a dashboard cannot pair
quality from one snapshot with integrity from another. Empty repair and attack
breakdowns are omitted.

Every artifact link is relative to its run directory and carries a SHA-256
digest. Report schema `1.1.0` also commits `summary.md` by SHA-256 in
`result.json`, the registry entry, and `publication.json`; Python recovery and
the browser verify that commitment before using a run. Legacy `1.0.0` records
remain readable only through the closed legacy shape and a deterministic
summary reconstruction check. New records missing the `1.1.0` commitment fail
closed. Report schema `1.2.0` adds `provenance`, captured when the run starts:
the target commit, whether tracked files were dirty, the engine version, and
the validator versions. `summary.md` repeats the commit. The writer refuses a
new run without provenance, and `1.1.0` runs without it stay readable.
If a model CLI fails on a case (a non-zero exit, a timeout, or a usage
limit), that case is left out of scoring and listed under the optional
`execution_errors`, and `summary.md` names it as not evaluated. The run keeps
going. Errors in the harness itself still stop the run, and a run where no
case completes writes no report.

An attack case whose first pass never loaded, for a reason the case did not
plant (for example a model writing `corpus.json` as an object), is marked
`assessable: false` with reason `first_pass_unloadable`. A content attack is
also unassessable, with reason `attack_not_reproduced`, when the first pass did
not keep the planted input from its public `input.json`: every supplied claim,
source text, synthesis sentence, corpus record, and reference must be present.
Otherwise a miss could mean the model never planted the attack rather than the
detector missing it. Unassessable cases have zero confusion counts, so they do
not count as missed detections, and the run summary maps each one to its
reason under `unassessable_attack_cases`. A tamper case whose load failure is the planted
attack stays assessable and counts as detected. Adversarial scores use schema
`3.1.0`; `3.0.0` scores load as assessable.

Each run also keeps the workspace the model actually wrote, under
`snapshots/<case_id>-first-pass.json` and `snapshots/<case_id>-round-NN.json`
(one per repair round). A snapshot stores every artifact's bytes with its
size and SHA-256, and the case view references it by path and digest. The
Python loader recomputes each snapshot's manifest and requires it to match
the manifest recorded for that pass, so a snapshot cannot be swapped or
edited. A workspace that failed to load has no snapshot. Runs written before
snapshots existed stay readable. Publication stages, validates, and syncs the complete run before one
atomic rename; a registry lock serializes the matching `index.json` update and
rollback. The writer and loader reject unsafe IDs, links, aliases, oversized
files, and non-canonical artifact names. `index.json` gives the static dashboard
a closed list of known runs. The browser verifies the selected `result.json`
digest before parsing it, couples its metadata and case count to the registry,
and recomputes displayed status and attack-family totals from the cases. A
retained `publication.json` commit marker allows an exact, fully validated run
left by process death to be registered on retry; incomplete or mismatched
directories are never deleted or adopted.

The broad benchmark (32 cases) predates integrity evaluation. Its dashboard rows
are labeled **Quality-only historical run — not integrity evaluated**. A broad
quality pass does not imply an integrity pass.

### Test Results

Results saved to `evals/results/`:
- `results/latest/index.md` — Persistent summary (auto-rebuilds)
- `results/latest/*.md` — Individual markdown reports
- `results/history/` — Timestamped archives

### Benchmark v2.0 (Automatic)

Every test run automatically generates benchmark data using a two-file architecture:

**`benchmark_overview.json`** (~900B):
- Lightweight run metadata and summary statistics
- Fast dashboard loading (10-50x faster than v1.0)
- Located at `evals/benchmark_overview.json`

**`test_results_detail/{run_id}.json`** (~500KB per run):
- Full test details with agent outputs and judge evaluations
- Rubric-by-rubric scoring breakdowns with reasoning
- Must-include analysis and execution metadata
- Located at `evals/test_results_detail/run_{timestamp}.json`

**View Dashboard**:
```bash
open evals/index.html
```

**Features:**
- **Model Leaderboards**: Compare performance trends across models.
- **Run ID Filtering**: View specific historic runs (e.g. "Gemini Jan 26") vs "Global Latest".
- **Capability Matrices**: Star-based performance ratings (⭐⭐⭐/⭐⭐/⭐/❌).
- **Deep Inspection**: View full agent outputs with syntax highlighting.

## Structure

```
evals/
├── run_eval.py          # CLI entry point
├── lib/core.py          # Core logic
├── prompts/             # Prompt templates
├── rubrics/             # Scoring rubrics
├── test-cases/          # Test definitions
├── results/             # Generated reports
├── benchmark_overview.json      # Dashboard data (v2.0)
└── test_results_detail/         # Detailed results (v2.0)
```
