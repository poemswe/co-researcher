# Evidence for "Every Claim Traced"

This directory holds the evidence behind the [technical write-up](https://coresearcher.poemswe.com/paper/write-up/) that is not already in `evals/published/runs/`. A [plain-language summary](https://coresearcher.poemswe.com/paper/) sits in front of it. The two release runs on 5802823 stay where the dashboard reads them.

## Runs

`runs/` holds the five earlier runs in Table 3, copied with `evals/publish_integrity_runs.py`. Each keeps its `result.json`, first-pass and repair snapshots, and repair rounds.

| Run | Writer | Commit | Used for |
|---|---|---|---|
| `run_20261007_143121_203203` | Claude Opus | eca0b37 | Tables 3 and 5, Figures 4 to 6, §4.3 original scorecard (6/15), §5.2 invented schema and `supporting` role |
| `run_20261007_192519_559605` | GPT Codex | eca0b37 | Tables 3 and 5, Figures 4 to 6, §4.3 original scorecard (4/15) |
| `run_20261008_015639_166787` | Claude Opus | 21c3777 | Tables 3 to 6, Figures 4 to 6, §5.3 |
| `run_20261008_070048_889834` | GPT Codex | 21c3777 | Tables 3 to 5, Figures 4 and 5, §5.2 controls that failed to load |
| `run_20261008_155105_866156` | GPT Codex | 154c26f | Tables 3 and 5, Figures 4 and 5, §5.1 annotated-bibliography control |

Some Codex snapshots contain temporary file paths that Codex wrote into its own syntheses. They are left as recorded.

## Judge re-scores

`rejudge/rejudge.jsonl` holds the 65 extra quality-judge scores behind Table 6: three re-scores of each first-pass and repaired synthesis for the 10 repaired cases on 21c3777, and five of the clean control. They were produced by `rejudge/rejudge.py` with the production judge and `claude:opus`. Each record keeps the snapshot label, repeat index, score and text length. Raw judge responses, resolved model strings, timestamps and prompt hashes were not recorded.

`python3 rejudge/table6.py` groups the scores by byte-identical synthesis and prints the Table 6 values: 15 texts, 4 or 8 judgments each, pooled standard deviation 9.6, median range 18.6 and maximum range 38.5, and for the clean control 6 judgments, standard deviation 1.0 and range 2.9 on 5,090 characters. The judge was invoked as `claude:opus`, and the resolved model behind that alias was not recorded.

## Counterexamples

`counterexamples/base` is the repaired case 001 workspace. The four other folders each change it in one way, and each `-report.json` was produced at fc9061c, whose gate code is unchanged since cb54321, the version §3 describes. All four return `valid` with integrity 100 and no findings. Later gate versions catch some of them: since #60, a claim whose negation or direction reverses its quote is `needs_review`, so `polarity-reversal` now fails. The saved reports keep the fc9061c result. Each workspace has an empty bibliography, so the citation-resolution check is not applicable.

| Folder | Edit | Gap (§3, §7) |
|---|---|---|
| `polarity-reversal` | claim and sentence say "found a change"; the quote says "found no change" | claim compared with its quote only on numbers |
| `uncited-qualitative` | adds "This treatment conclusively cures dementia." | uncited sentences checked only for numbers |
| `background-role` | gives a cited qualitative finding a background role | role check applies only to numeric sentences |
| `number-swap` | source, quote and claim say 40 adults and 60 children; the sentence says 60 adults and 40 children | numbers compared as multisets |

Rerun one with:

```
python skills/literature-review/scripts/validate_review.py --workspace evals/published/paper/counterexamples/polarity-reversal --synthetic-fixture
```

## Release results

§5.1, Table 4, the case 009 repair in §5.2 and the Opus clean control in §5.1 come from the two release runs in `evals/published/runs/`.

## Not in this package

- The usage-limit failures and earlier attempts behind each Codex `--resume`. Each final run names the run it resumed from in `resumed_from`.
- The workspaces from the Codex controls on 21c3777 that failed to load. Their reports record the load failure, and commit 9b51b90 records the diagnosis.
- Runs from before eca0b37 that Figure 7 draws on, including the first live run and the Haiku runs. Figure 7 cites the commit that fixed each failure.
