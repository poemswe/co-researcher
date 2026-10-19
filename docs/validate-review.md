# Validating a review offline

Run the shared validation engine directly from any working directory (Python
3.10 or newer; no package installation is required):

```bash
python3 /path/to/co-researcher/skills/literature-review/scripts/validate_review.py \
  --workspace /path/to/review/example
```

This command is always offline. It never resolves citations over the network,
so it scores the report that `verify_citations.py` wrote earlier. A nonempty
bibliography with no `--citation-report` is invalid, and so is any cited paper
that no `refs.json` entry identifies by DOI or title. Without both checks an
agent could cite a corpus record it invented and never have it looked up.
Supply the resolver report explicitly:

```bash
python3 /path/to/co-researcher/skills/literature-review/scripts/validate_review.py \
  --workspace /path/to/review/example \
  --citation-report /path/to/citation-report.json \
  --output /path/outside/review/integrity-report.md
```

Each source text that claims are checked against needs the receipt
`read_paper.py` wrote beside it (`fulltext.receipt.json` or
`abstract.receipt.json`). A missing or unreadable receipt, or text whose
sha256 no longer matches it, fails as `manifest_mismatch`. A receipt shows the
text came from a fetch and was not edited afterwards. An agent could still
write a receipt by hand, so it is a tripwire and not proof.

To check where the text came from, re-fetch every receipted source and compare
it to the workspace copy:

```bash
uv run skills/literature-review/scripts/read_paper.py --recheck \
  --workspace /path/to/review/example
```

Recheck trusts nothing in the receipt except the paper id, and the id must
match the paper's directory name. It runs the full fetch chain for that id again
and compares the result to the workspace copy. Each receipt gets one JSON line
whose `result` is one of these:

- `match`: the same route returned the same bytes.
- `mismatch`: the text differs, or the workspace file is gone.
- `unavailable`: the chain now ends at a different route or at none, or the fetch failed.
- `unverifiable`: the text came from a user PDF, which has no public copy to
  compare against.
- `unreadable_receipt`: the receipt cannot be parsed or names another paper.

Any result other than `match` exits 1. A match on `oa_pdf` shows only that
OpenAlex points at the same file, so it is as good as that host. A mismatch can also come
from a publisher correction or a different PDF extractor version, so read the
two texts before calling it forged. The check needs the network, which is why
it stays outside the offline validator.

A cited paper whose `corpus.json` record has no DOI, PMID, PMCID or arXiv id
gets a `source_unregistered` warning. A web page an agent published during the
run has none of these, so check each flagged source by hand before relying on
it. A cited record's DOI also has to appear among the DOIs the citation report
verified, or the paper gets the same warning naming that DOI, so an invented
DOI written into `corpus.json` does not clear it. PMID, PMCID and arXiv ids
are not resolved yet and are still taken as written. A cited source imported
from the user's library that no registry knows gets the same warning on
`refs.json` in place of a critical `citation_identity_mismatch`. That applies
only when its corpus record came from the library, has no identifier, and its
paper directory holds a `user_pdf` receipt. The warning cannot be repaired and
does not lower the score.

Fixtures built from invented papers cannot resolve or be fetched. For those,
pass `--synthetic-fixture`, which skips both checks, restores the old warning,
and records `citation_resolution.source` as `waived` so the report shows it
was used.

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
