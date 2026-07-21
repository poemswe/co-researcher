# Claim Verifier Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make claim verification fail closed for altered evidence, ambiguous identities, and ungrounded quantitative assertions while accepting valid international and compound author names.

**Architecture:** Keep `check_claims.py` as one module and change six existing seams. Two small helpers classify meaningful edits and structured PDF gaps; existing citation, reference, binding, coverage, and report functions gain deterministic fail-closed behavior.

**Tech Stack:** Python 3.10+ standard library, pytest, `uv`, GitHub Actions YAML.

## Global Constraints

- Keep existing CLI arguments and required `claims.json` fields unchanged.
- Treat ambiguity as a nonzero failure.
- Preserve authenticity-only scope; do not add semantic entailment, embeddings, or topic scoring.
- Keep two-space Python indentation and standard-library-only production code.
- Write each regression before its production fix and observe the expected failure.
- Preserve unrelated working-tree changes.

## File map

- Modify `skills/literature-review/scripts/check_claims.py`: all verifier behavior and report changes.
- Modify `tests/test_check_claims.py`: deterministic unit and integration regressions.
- Modify `tests/eval_check_claims.py`: Unicode alteration and structured-gap adversarial cases.
- Modify `skills/literature-review/SKILL.md`: fail-closed binding and coverage reason guidance.
- Modify `skills/academic-writing/SKILL.md`: mention invalid bindings and quantitative background rejection.
- Verify `.github/workflows/tests.yml`: existing workflow runs the complete and adversarial suites; no structural change expected.

---

### Task 1: Fail-closed quote authenticity

**Files:**
- Modify: `tests/test_check_claims.py`
- Modify: `tests/eval_check_claims.py`
- Modify: `skills/literature-review/scripts/check_claims.py:45-230`

**Interfaces:**
- Produces: `_has_meaningful_text(text: str) -> bool`
- Produces: `_is_structured_artifact_gap(text: str) -> bool`
- Preserves: `find_quote(quote: str, source: str) -> dict`

- [ ] **Step 1: Add failing Unicode, substantive-gap, and overlap tests**

Add these tests to `tests/test_check_claims.py`:

```python
@pytest.mark.parametrize(("source", "quote"), [
    ("The café intervention reduced admissions across the cohort.",
     "The cafè intervention reduced admissions across the cohort."),
    ("Вмешательство снизило смертность среди участников исследования.",
     "Вмешательство повысило смертность среди участников исследования."),
])
def test_find_quote_rejects_unicode_alphanumeric_edits(source, quote):
  result = cc.find_quote(cc.normalize_text(quote), cc.normalize_text(source))
  assert result["method"] is None


def test_find_quote_rejects_substantive_pipe_gap():
  source = cc.normalize_text(
      "Readmissions fell across the treatment cohort. "
      "| treatment caused severe adverse events | "
      "Mortality remained unchanged during follow-up.")
  quote = cc.normalize_text(
      "Readmissions fell across the treatment cohort. "
      "Mortality remained unchanged during follow-up.")
  assert cc.find_quote(quote, source)["method"] is None


def test_per_sentence_match_cannot_reuse_one_source_span():
  sentence = "Readmissions fell across the treatment cohort at follow-up."
  source = cc.normalize_text(sentence)
  quote = cc.normalize_text(f"{sentence} {sentence}")
  assert cc.find_quote(quote, source)["method"] is None
```

Add the Cyrillic substitution and substantive pipe omission to `NEGATIVES` in `tests/eval_check_claims.py`.

- [ ] **Step 2: Run the new tests and confirm RED**

Run:

```bash
env UV_CACHE_DIR=/tmp/co-researcher-uv-cache uv run tests/test_check_claims.py \
  -q -k 'unicode_alphanumeric_edits or substantive_pipe_gap or reuse_one_source_span'
```

Expected: all new tests fail because Unicode edits, pipe gaps, and overlapping sentence spans currently authenticate.

- [ ] **Step 3: Implement the minimal authenticity helpers**

Replace `_MEANINGFUL_RE` and `_allowed_source_gap` with:

```python
_MEANINGFUL_SYMBOLS = frozenset("%<>=≤≥±")
_PAGE_GAP_RE = re.compile(
    r"(?:running\s+header\s+)?(?:page\s+)?\d+(?:\s+of\s+\d+)?$")
_AUTHOR_HEADER_RE = re.compile(
    r"(?P<author>.+?\bet\s+al\.?)\s+(?:19|20)\d{2}(?:\s+\d+)?$")


def _has_meaningful_text(text: str) -> bool:
  return any(char.isalnum() or char in _MEANINGFUL_SYMBOLS for char in text)


def _is_structured_artifact_gap(text: str) -> bool:
  gap = text.strip(" \t\n.,;:()[]{}-–—")
  if not _has_meaningful_text(gap):
    return True
  if "|" in gap or len(gap) > 180 or _GAP_POLARITY_RE.search(gap):
    return False
  if _PAGE_GAP_RE.fullmatch(gap):
    return True
  header = _AUTHOR_HEADER_RE.fullmatch(gap)
  return bool(header and _valid_author_label(header.group("author")))
```

Update `_authentic_alignment` to call `_has_meaningful_text` for quote-side edits and `_is_structured_artifact_gap` for source insertions. Update per-sentence matching to require:

```python
non_overlapping = all(ends[i] <= starts[i + 1]
                      for i in range(len(per) - 1))
if (non_overlapping and span <= 3 * len(quote)
    and all(_is_structured_artifact_gap(gap) for gap in gaps)):
```

- [ ] **Step 4: Run quote and adversarial tests and confirm GREEN**

Run:

```bash
env UV_CACHE_DIR=/tmp/co-researcher-uv-cache uv run tests/test_check_claims.py -q
env UV_CACHE_DIR=/tmp/co-researcher-uv-cache uv run tests/eval_check_claims.py -q
```

Expected: all claim tests and all adversarial evaluations pass.

- [ ] **Step 5: Commit the quote-authenticity task**

```bash
git add skills/literature-review/scripts/check_claims.py \
  tests/test_check_claims.py tests/eval_check_claims.py
git commit -m "fix: fail closed on altered claim quotes"
```

---

### Task 2: Unicode and compound author identities

**Files:**
- Modify: `tests/test_check_claims.py`
- Modify: `skills/literature-review/scripts/check_claims.py:330-375,525-610`

**Interfaces:**
- Produces: `_name_tokens(text: str) -> list[str]`
- Preserves: `_author_key(author: str) -> str`
- Preserves: `_name_aliases(name: str) -> set[str]`
- Preserves: `citation_keys(text: str) -> set[str]`

- [ ] **Step 1: Add failing author parsing and binding tests**

Add:

```python
@pytest.mark.parametrize(("rendered", "expected"), [
    ("García (2022)", "author:garcía:2022"),
    ("Иванов (2022)", "author:иванов:2022"),
    ("王 (2022)", "author:王:2022"),
])
def test_unicode_narrative_author_citations(rendered, expected):
  assert cc.citation_keys(rendered) == {expected}


@pytest.mark.parametrize(("rendered", "expected"), [
    ("(García, 2022)", "author:garcía:2022"),
    ("(Иванов, 2022)", "author:иванов:2022"),
    ("(王, 2022)", "author:王:2022"),
])
def test_unicode_parenthetical_author_citations(rendered, expected):
  assert cc.citation_keys(rendered) == {expected}


@pytest.mark.parametrize(("name", "citation"), [
    ("Mary O'Connor", "O'Connor, 2022"),
    ("Mary Smith-Jones", "Smith-Jones, 2022"),
    ("Ludwig van der Berg", "van der Berg, 2022"),
])
def test_compound_corpus_surname_binds(name, citation):
  key = next(iter(cc.citation_keys(citation)))
  assert cc._author_year_binding_matches(
      key, {"authors": [name], "year": 2022})
```

Keep `test_coverage_ignores_comma_year_prose_parenthetical` unchanged as the false-positive guard.

- [ ] **Step 2: Run the author tests and confirm RED**

Run:

```bash
env UV_CACHE_DIR=/tmp/co-researcher-uv-cache uv run tests/test_check_claims.py \
  -q -k 'unicode_narrative or compound_corpus or comma_year_prose'
```

Expected: Unicode and compound cases fail; the prose case remains passing.

- [ ] **Step 3: Implement Unicode tokenization and raw surname selection**

Add and use:

```python
_LETTER = r"[^\W\d_]"
_NAME_TOKEN = rf"{_LETTER}+(?:['’\-]{_LETTER}+)*"
_NAME_TOKEN_RE = re.compile(_NAME_TOKEN, re.UNICODE)


def _name_tokens(text: str) -> list[str]:
  return _NAME_TOKEN_RE.findall(unicodedata.normalize("NFKC", text))


def _author_key(author: str) -> str:
  author = unicodedata.normalize("NFKC", author).casefold().replace("&", " and ")
  pieces = [re.sub(r"['’\-]+", " ", token) for token in _name_tokens(author)]
  return re.sub(r"\s+", " ", " ".join(pieces)).strip()
```

Define `_SURNAME_TOKEN = _NAME_TOKEN` and rebuild `_SURNAME` from it. Make `_valid_author_label` use `_name_tokens`; accept a non-particle token only when its first letter is uppercase or uncased:

```python
first = next(char for char in token if char.isalpha())
if first.islower():
  return False
```

Call `_valid_author_label` for narrative matches as well as parenthetical matches.

Rewrite `_name_aliases` so the surname comes from raw components:

```python
raw_parts = name.strip().split()
end = len(raw_parts)
if end > 1 and len(_author_key(raw_parts[-1]).replace(" ", "")) <= 2:
  end -= 1
surname_parts = [raw_parts[end - 1]]
cursor = end - 2
while cursor >= 0 and _author_key(raw_parts[cursor]) in _NAME_PARTICLES:
  surname_parts.insert(0, raw_parts[cursor])
  cursor -= 1
surname = _author_key(" ".join(surname_parts))
```

Keep comma-form surnames as `_author_key(name.split(",", 1)[0])`.

- [ ] **Step 4: Run the focused and complete claim tests**

Run:

```bash
env UV_CACHE_DIR=/tmp/co-researcher-uv-cache uv run tests/test_check_claims.py -q
```

Expected: every claim test passes, including prose-parenthetical exclusions.

- [ ] **Step 5: Commit the author-identity task**

```bash
git add skills/literature-review/scripts/check_claims.py tests/test_check_claims.py
git commit -m "fix: support trusted Unicode author identities"
```

---

### Task 3: Unique references and per-entry binding failures

**Files:**
- Modify: `tests/test_check_claims.py`
- Modify: `skills/literature-review/scripts/check_claims.py:375-420,665-780`

**Interfaces:**
- Changes: `_reference_record(item, records) -> tuple[dict | None, str | None]`
- Changes: `validate_citation_bindings(...) -> list[dict | None]`
- Adds report status: `invalid_binding`

- [ ] **Step 1: Add failing reference, role, and mixed-result tests**

Add:

```python
def test_formatted_reference_binds_by_embedded_title(tmp_path):
  refs = ["Patel, P. (2022). A Paper. Journal of Evidence, 4(2), 1-9."]
  assert _run_main(tmp_path, [_entry(citation="[1]")], references=refs) == 0


def test_unmatched_doi_does_not_fall_back_to_title(tmp_path, capsys):
  refs = [{"doi": "10.9/wrong", "title": "A Paper"}]
  code = _run_main(tmp_path, [_entry(citation="[1]")], references=refs)
  report = json.loads(capsys.readouterr().out)
  assert code == 1
  assert report["results"][0]["reason_code"] == "reference_not_found"


def test_ambiguous_reference_title_is_invalid_binding(tmp_path, capsys):
  corpus = [
      {"key": "one", "ids": {"pmcid": "p1"}, "title": "A Paper",
       "authors": ["Priya Patel"], "year": 2022, "role": "evidence"},
      {"key": "two", "ids": {"pmcid": "p2"}, "title": "A Paper",
       "authors": ["Priya Patel"], "year": 2022, "role": "evidence"},
  ]
  code = _run_main(tmp_path, [_entry(citation="[1]")], corpus=corpus,
                   references=["Patel (2022). A Paper."])
  report = json.loads(capsys.readouterr().out)
  assert code == 1
  assert report["results"][0]["reason_code"] == "reference_ambiguous"


@pytest.mark.parametrize(("trusted_role", "declared_role", "reason"), [
    (None, "evidence", "corpus_metadata_missing"),
    ("evidence", "background", "role_mismatch"),
])
def test_untrusted_or_mismatched_role_is_reported(
    tmp_path, capsys, trusted_role, declared_role, reason):
  corpus = [{"key": "paper-one", "ids": {"pmcid": "p1"},
             "title": "A Paper", "authors": ["Priya Patel"],
             "year": 2022, "role": trusted_role}]
  code = _run_main(tmp_path, [_entry(role=declared_role)], corpus=corpus)
  report = json.loads(capsys.readouterr().out)
  assert code == 1
  assert report["invalid_binding"] == 1
  assert report["results"][0]["reason_code"] == reason


def test_invalid_binding_does_not_suppress_valid_results(tmp_path, capsys):
  entries = [_entry(), _entry(citation="Lee, 2021")]
  code = _run_main(tmp_path, entries)
  report = json.loads(capsys.readouterr().out)
  assert code == 1
  assert [result["status"] for result in report["results"]] == [
      "verified", "invalid_binding"]
```

- [ ] **Step 2: Run the new binding tests and confirm RED**

Run:

```bash
env UV_CACHE_DIR=/tmp/co-researcher-uv-cache uv run tests/test_check_claims.py \
  -q -k 'formatted_reference or unmatched_doi or ambiguous_reference or trusted_role or mixed_binding'
```

Expected: formatted references, structured failures, and mixed reporting fail under the current early-exit implementation.

- [ ] **Step 3: Make reference lookup unique and fail closed**

Implement a token normalizer and unique-result helper:

```python
def _normalized_tokens(text: str) -> str:
  folded = unicodedata.normalize("NFKC", text).casefold()
  return " ".join("".join(char if char.isalnum() else " "
                          for char in folded).split())


def _unique_match(matches: list[dict]) -> tuple[dict | None, str | None]:
  if not matches:
    return None, "reference_not_found"
  if len(matches) != 1:
    return None, "reference_ambiguous"
  return matches[0], None
```

For DOI-bearing items, collect exact DOI matches and return `_unique_match(matches)` without title fallback. For title-only items, compare complete token sequences with:

```python
reference = f" {_normalized_tokens(title)} "
matches = [record for record in records
           if (needle := _normalized_tokens(record.get("title") or ""))
           and f" {needle} " in reference]
return _unique_match(matches)
```

Store `(record, reason_code)` for every numeric bibliography position.

- [ ] **Step 4: Convert binding exits into per-entry results**

Keep top-level shape validation in `validate_entries`, but move citation parsing and trusted metadata checks into `validate_citation_bindings`. Return one binding object or error result per entry:

```python
def _invalid_binding(entry: dict, reason_code: str) -> dict:
  return {"claim": entry.get("claim"), "paper_id": entry.get("paper_id"),
          "citation": entry.get("citation"),
          "supporting_quote": entry.get("supporting_quote"),
          "status": "invalid_binding", "reason_code": reason_code,
          "source_scope": None, "quote_match_ratio": None,
          "matched": None, "best_window": None,
          "quote_is_title": False, "context_risks": [], "anchors": None}
```

Require corpus role membership in `{"evidence", "background"}` before comparing it with the declared role. In `main`, run `check_entry` only for successful bindings and append invalid-binding results for failures. Add `invalid_binding` to counts and `_HARD_FAILS`.

- [ ] **Step 5: Run binding and full claim tests and confirm GREEN**

Run:

```bash
env UV_CACHE_DIR=/tmp/co-researcher-uv-cache uv run tests/test_check_claims.py -q
```

Expected: all claim tests pass; no identity mismatch aborts the report.

- [ ] **Step 6: Commit the identity-binding task**

```bash
git add skills/literature-review/scripts/check_claims.py tests/test_check_claims.py
git commit -m "fix: fail closed on ambiguous claim bindings"
```

---

### Task 4: Per-citation quantitative coverage ledger

**Files:**
- Modify: `tests/test_check_claims.py`
- Modify: `skills/literature-review/scripts/check_claims.py:620-670,735-765`

**Interfaces:**
- Changes: `coverage_gaps(synthesis: str, claims: list, results: list) -> list[dict]`
- Consumes: verified/background results from Task 3

- [ ] **Step 1: Add failing number, role, and multi-claim tests**

Add:

```python
def _trusted_results(claims):
  return [{"status": "background" if claim.get("role") == "background"
           else "verified"} for claim in claims]


def test_coverage_rejects_added_number_for_each_identity():
  synthesis = "Readmissions fell 99% in the treatment arm (Patel, 2022)."
  claims = [_entry(claim="Readmissions fell in the treatment arm.")]
  gaps = cc.coverage_gaps(synthesis, claims, _trusted_results(claims))
  assert gaps[0]["reason_code"] == "coverage_number_missing"


def test_background_cannot_cover_numbered_sentence():
  synthesis = "Readmissions fell 18% in the treatment arm (Patel, 2022)."
  claims = [_entry(role="background")]
  gaps = cc.coverage_gaps(synthesis, claims, _trusted_results(claims))
  assert gaps[0]["reason_code"] == "coverage_role_invalid"


def test_multiple_claims_jointly_ground_sentence_numbers():
  synthesis = ("Thirty-day readmissions fell 18% in the treatment arm, and "
               "ninety-day mortality fell 4% during follow-up (Patel, 2022).")
  claims = [
      _entry(claim="Thirty-day readmissions fell 18% in the treatment arm"),
      _entry(claim="ninety-day mortality fell 4% during follow-up"),
  ]
  assert cc.coverage_gaps(
      synthesis, claims, _trusted_results(claims)) == []
```

Update existing direct `coverage_gaps` calls to pass `_trusted_results(claims)` and compare gap `sentence` fields.

- [ ] **Step 2: Run coverage tests and confirm RED**

Run:

```bash
env UV_CACHE_DIR=/tmp/co-researcher-uv-cache uv run tests/test_check_claims.py \
  -q -k 'coverage or background_cannot or jointly_ground'
```

Expected: new tests fail because the current function discards result status, role, and sentence numbers.

- [ ] **Step 3: Implement the ledger**

Build trusted claim data by zipping claims and results and retaining only `verified` and `background` statuses. For each synthesis sentence and citation key, collect text-matching claims with that key. Emit one gap object per failed identity:

```python
{"sentence": sentence.strip(), "citation_key": key,
 "reason_code": reason_code}
```

Use this precedence:

```python
if not matching:
  reason = "coverage_identity_missing"
elif sentence_numbers and any(item["role"] == "background"
                              for item in matching):
  reason = "coverage_role_invalid"
elif sentence_numbers - set().union(*(item["numbers"] for item in matching)):
  reason = "coverage_number_missing"
else:
  continue
```

In `main`, pass entry results to `coverage_gaps` and translate each gap into `uncovered_claim` with its `reason_code` and citation identity.

- [ ] **Step 4: Run claim tests and adversarial evaluations**

Run:

```bash
env UV_CACHE_DIR=/tmp/co-researcher-uv-cache uv run tests/test_check_claims.py -q
env UV_CACHE_DIR=/tmp/co-researcher-uv-cache uv run tests/eval_check_claims.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the coverage task**

```bash
git add skills/literature-review/scripts/check_claims.py \
  tests/test_check_claims.py tests/eval_check_claims.py
git commit -m "fix: ground synthesis numbers per citation"
```

---

### Task 5: Documentation and complete verification

**Files:**
- Modify: `skills/literature-review/SKILL.md`
- Modify: `skills/academic-writing/SKILL.md`
- Verify: `.github/workflows/tests.yml`

**Interfaces:**
- Documents: additive `invalid_binding` count and `reason_code`
- Documents: background citations cannot cover quantitative statements

- [ ] **Step 1: Update protocol guidance**

Add concise guidance to the claim-verification sections:

```markdown
`invalid_binding` means the claim did not resolve to one trusted corpus record;
fix the corpus metadata or citation instead of retrying quote matching. Background
entries may cover number-free context only. Every number in a cited synthesis
sentence must appear in verified matching claims for each cited identity.
```

- [ ] **Step 2: Run static checks**

Run:

```bash
git diff --check
python3 -m py_compile skills/literature-review/scripts/check_claims.py \
  skills/literature-review/scripts/build_corpus.py
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/tests.yml"); puts "workflow yaml: ok"'
```

Expected: no diff or compilation errors and `workflow yaml: ok`.

- [ ] **Step 3: Run focused suites**

Run:

```bash
env UV_CACHE_DIR=/tmp/co-researcher-uv-cache uv run tests/test_build_corpus.py -q
env UV_CACHE_DIR=/tmp/co-researcher-uv-cache uv run tests/test_check_claims.py -q
env UV_CACHE_DIR=/tmp/co-researcher-uv-cache uv run tests/eval_check_claims.py -q
env UV_CACHE_DIR=/tmp/co-researcher-uv-cache uv run tests/test_read_paper.py -q
```

Expected: every focused suite passes.

- [ ] **Step 4: Run the complete repository suite**

Run:

```bash
env UV_CACHE_DIR=/tmp/co-researcher-uv-cache \
  uv run --with pytest --with pymupdf4llm --with python-dotenv pytest -q
```

Expected: all repository tests pass with zero failures.

- [ ] **Step 5: Commit documentation**

```bash
git add skills/literature-review/SKILL.md skills/academic-writing/SKILL.md \
  .github/workflows/tests.yml
git commit -m "docs: explain fail-closed claim verification"
```
