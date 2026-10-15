# Validating a review offline

Run the shared validation engine directly from any working directory (Python
3.10 or newer; no package installation is required):

```bash
python3 /path/to/co-researcher/skills/literature-review/scripts/validate_review.py \
  --workspace /path/to/review/example
```

This command is always offline. It never resolves citations over the network.
When a nonempty bibliography has no explicit `--citation-report`, the report
records `citation_resolution_unavailable` as a warning; it does not claim that
the bibliography is verified. An empty bibliography makes that dimension not
applicable. To score a prior offline resolver result, supply its immutable JSON
report explicitly:

```bash
python3 /path/to/co-researcher/skills/literature-review/scripts/validate_review.py \
  --workspace /path/to/review/example \
  --citation-report /path/to/citation-report.json \
  --output /path/outside/review/integrity-report.md
```

Standard output is always the complete compact JSON validation report. An
optional `.json` output is byte-for-byte identical to stdout; `.md` produces a
human-readable audit report. The output must be a new file outside the entire
submitted workspace. Other suffixes, existing files, symlinks, and unsafe path
traversal are refused.

The report identifies engine and validator versions, the target Git commit and
tracked dirty state when available, and both the workspace-manifest hash and
the supplied citation-report hash. Its combined manifest hash commits to both
inputs (or to an explicit null citation-report marker), so provenance can be
audited without network access. Ignored and untracked files do not affect the
Git dirty marker.

Exit codes are `0` for `valid` or `valid_with_warnings`, `1` for `invalid`, and
`2` when usage or an input/output safety problem prevents construction of a
validation report. Exit `2` means the review was not validated and must be
treated as an invalid delivery by an enclosing workflow.
