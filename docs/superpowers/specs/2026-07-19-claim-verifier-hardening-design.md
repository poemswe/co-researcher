# Minimal Fail-Closed Claim Verifier Design

**Date:** 2026-07-21

**Status:** Revised after written review

## Goal

Reject altered quotes, wrong or ambiguous source identities, and untraced quantitative assertions. Accept valid Unicode names, compound surnames, and uniquely resolvable formatted references.

The verifier proves authenticity and traceability. Semantic entailment remains out of scope.

## Design rule

Keep the existing CLI, files, and control flow. Add only the helpers needed to enforce four invariants. Do not introduce a new framework, passage manifest, parser dependency, or class hierarchy.

## Invariant 1: quoted wording is authentic

`find_quote` may accept a normalized exact match or a fuzzy alignment whose every edit is harmless.

- A Unicode-aware predicate treats every `str.isalnum()` character as meaningful. `%`, comparison operators, and statistical symbols are meaningful too.
- Any meaningful quote-side edit fails.
- A source-side insertion passes only if the complete insertion matches punctuation and whitespace, a page marker, a literal running-header marker ending in a page number, or an author-year header.
- Pipe-delimited gaps always fail because normalized text no longer carries enough layout information to distinguish a header from prose.
- Multi-sentence matches use increasing, non-overlapping spans. Every intervening gap must pass the same complete-gap classifier.
- Nearby trimmed negation makes even an exact substring fail closed.

Two small helpers implement the rule: `_has_meaningful_text(text)` and `_is_structured_artifact_gap(text)`.

## Invariant 2: each claim has one trusted identity

Before checking its quote, each claim must resolve to exactly one corpus record.

- `paper_id` matches exactly one record.
- The record contains a trusted first author, year, and `role` of `evidence` or `background`. A null or invalid role is an invalid binding.
- The declared claim role equals the corpus role.
- An author-year citation matches the trusted first author and year.
- A numeric citation resolves through the ordered bibliography to the same corpus record.

### Author matching

Tokenize names with Unicode letter predicates. Apply NFKC, `casefold()`, and consistent punctuation-to-space folding to keys.

Build natural-order surname aliases from the last raw whitespace component before folding punctuation. `O'Connor` and `Smith-Jones` therefore yield `o connor` and `smith jones`. Include recognized preceding particles. Comma-form metadata uses the complete text before the comma.

Parenthetical and narrative citation parsing accepts uppercase Unicode letters and scripts without case. Lowercase prose words still invalidate strings such as `(In the final sample, 2020)`.

### Numeric reference matching

Resolve an embedded DOI exactly and require one corpus match. Without a DOI, normalize the reference and each corpus title into Unicode case-folded alphanumeric tokens, then match a corpus title as a complete token sequence inside the reference. Return a record only when exactly one corpus title matches. Zero or several matches fail.

## Invariant 3: coverage grounds identities, roles, and numbers

`coverage_gaps` builds a small ledger for each citation identity in each synthesis sentence. Only claims that passed identity and quote verification enter the ledger.

Each ledger stores the matched claims' roles and non-year numbers. A sentence passes only when:

- every parsed citation identity has a matching ledger;
- every non-year sentence number appears in every cited identity's ledger; and
- a background ledger covers no quantitative assertion.

Several claims may jointly supply one identity's numbers. Approximate text matching remains a candidate selector; it cannot override the identity, role, or number checks. Added number-free assertions remain outside mechanical entailment checking.

## Invariant 4: entry failures are machine-readable

Malformed top-level JSON or missing required fields remain usage errors. Identity failures are entry results, not early `sys.exit` calls.

Add the status and top-level count `invalid_binding`. Every invalid binding includes one `reason_code`:

- `paper_not_in_corpus`
- `paper_ambiguous`
- `corpus_metadata_missing`
- `role_mismatch`
- `citation_unparseable`
- `citation_identity_mismatch`
- `reference_not_found`
- `reference_ambiguous`

Quote and coverage failures also receive concise reason codes such as `quote_altered`, `quote_gap_unrecognized`, `coverage_identity_missing`, `coverage_number_missing`, and `coverage_role_invalid`.

`invalid_binding`, `fabricated_quote`, `uncovered_claim`, `needs_review`, and existing source or quote errors return nonzero. Valid entries in the same run still appear in the JSON report.

## Minimal implementation shape

Keep `check_claims.py` as one module. Change only these seams:

1. Replace ASCII meaningful-text checks and permissive gap checks with the two authenticity helpers.
2. Make author tokenization, normalization, and surname aliasing Unicode- and compound-aware.
3. Make reference lookup collect candidates and require one match.
4. Change citation binding from process-level exits to one result per entry.
5. Pass verified entry results, including role and numbers, into coverage.
6. Add `invalid_binding` and `reason_code` to reporting.

No other refactor belongs in this change.

## Tests

Write failing regressions before production edits:

1. Accented-Latin and Cyrillic quote edits fail.
2. Real page/header artifacts pass; substantive pipe or marker gaps fail.
3. Added synthesis numbers fail per citation identity; several claims can jointly ground them.
4. Background claims cannot cover numbered sentences.
5. Accented-Latin, Cyrillic, and caseless-script author citations parse and bind.
6. Apostrophe-, hyphen-, particle-, and comma-form surnames bind.
7. DOI, bare-title, formatted-title, missing-title, and ambiguous-title references behave deterministically.
8. Null corpus roles and role mismatches produce `invalid_binding` results.
9. One invalid binding does not suppress valid results from the same run.

Deterministic property-style tests also assert that Unicode alphanumeric quote edits never authenticate, covered sentence numbers exist in every cited ledger, and reference lookup returns one record or fails.

Completion requires focused tests, adversarial evaluations, the real PDF extraction test, Python compilation, diff and workflow checks, and the full repository suite.

## Compatibility

CLI arguments and claim fields stay unchanged. Existing report fields remain; `invalid_binding` and `reason_code` are additive. Legacy corpus records without authors or roles must be rebuilt or completed before verification.
