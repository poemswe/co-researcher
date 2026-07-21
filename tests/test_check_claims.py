# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pytest",
# ]
# ///

import importlib.util
import json
import pathlib
import sys
import time

import pytest

_SCRIPTS = (pathlib.Path(__file__).resolve().parent.parent
            / "skills/literature-review/scripts")
sys.path.insert(0, str(_SCRIPTS))
_SCRIPT = _SCRIPTS / "check_claims.py"
_spec = importlib.util.spec_from_file_location("check_claims", _SCRIPT)
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)

_SOURCE = (
    "We enrolled 814 adult patients across 12 regional hospitals. "
    "Thirty-day readmissions fell 18% in the treatment arm relative to "
    "usual care, a difference that persisted after adjustment. Mortality "
    "did not differ between groups at 90 days. Adherence averaged 71% "
    "and declined over the follow-up period.")


def _ws(tmp_path, papers):
  for pid, files in papers.items():
    d = tmp_path / "papers" / pid
    d.mkdir(parents=True)
    for name, text in files.items():
      (d / name).write_text(text, encoding="utf-8")
  return tmp_path


def _entry(claim="Readmissions fell 18% in the treatment arm of the trial.",
           paper_id="p1",
           citation="Patel, 2022",
           quote="Thirty-day readmissions fell 18% in the treatment arm "
                 "relative to usual care",
           **kw):
  return {"claim": claim, "paper_id": paper_id,
          "citation": citation, "supporting_quote": quote, **kw}


# --- normalize_text ---

def test_normalize_collapses_whitespace_and_case():
  assert cc.normalize_text("The  Treatment\n ARM") == "the treatment arm"


def test_normalize_dehyphenates_linebreak_artifacts():
  assert "readmission" in cc.normalize_text("read-\nmission rates")


def test_normalize_maps_ligatures_and_curly_quotes():
  assert cc.normalize_text("ﬁndings “matter”") == (
      'findings "matter"')


def test_normalize_strips_soft_hyphens_and_dashes():
  assert cc.normalize_text("state­of—the–art") == (
      "stateof-the-art")


# --- find_quote ---

def test_find_quote_exact_after_normalization():
  src = cc.normalize_text(_SOURCE)
  q = cc.normalize_text("Mortality did not differ between groups at 90 days.")
  r = cc.find_quote(q, src)
  assert r["method"] == "exact" and r["coverage"] == 1.0


def test_find_quote_fuzzy_survives_noise():
  noisy = cc.normalize_text(
      _SOURCE.replace("treatment arm", "treat-\nment arm")
             .replace("fell", "feﬂl" if False else "fell"))
  q = cc.normalize_text("readmissions fell 18% in the treatment arm "
                        "relative to usual care")
  r = cc.find_quote(q, noisy)
  assert r["coverage"] >= cc._QUOTE_MATCH_THRESHOLD


def test_find_quote_rejects_heavy_rewrite():
  src = cc.normalize_text(_SOURCE)
  q = cc.normalize_text("hospital returns dropped by nearly a fifth for "
                        "exercised patients in this cohort")
  r = cc.find_quote(q, src)
  assert r["coverage"] < cc._QUOTE_MATCH_THRESHOLD


def test_find_quote_reports_best_window_on_failure():
  src = cc.normalize_text(_SOURCE)
  q = cc.normalize_text("we surveyed 814 nurses across twelve county clinics "
                        "during the enrollment window")
  r = cc.find_quote(q, src)
  assert r["coverage"] < cc._QUOTE_MATCH_THRESHOLD
  assert r["window"]


def test_find_quote_per_sentence_fallback_spans_artifact():
  broken = _SOURCE.replace(
      "usual care, a difference that persisted after adjustment. Mortality",
      "usual care. RUNNING HEADER PAGE 7. Mortality")
  src = cc.normalize_text(broken)
  q = cc.normalize_text(
      "Thirty-day readmissions fell 18% in the treatment arm relative to "
      "usual care. Mortality did not differ between groups at 90 days.")
  r = cc.find_quote(q, src)
  assert r["method"] in ("per_sentence", "fuzzy", "exact")
  assert r["coverage"] >= cc._QUOTE_MATCH_THRESHOLD


def test_find_quote_per_sentence_reports_matching_window():
  src = cc.normalize_text(_SOURCE.replace(
      "usual care, a difference that persisted after adjustment. Mortality",
      "usual care. RUNNING HEADER PAGE 7. Mortality"))
  q = cc.normalize_text(
      "Thirty-day readmissions fell 18% in the treatment arm relative to "
      "usual care. Mortality did not differ between groups at 90 days.")
  r = cc.find_quote(q, src)
  if r["method"] == "per_sentence":
    assert "mortality" in r["window"] or "readmissions" in r["window"]


def test_find_quote_no_fallback_when_a_sentence_is_tiny():
  src = cc.normalize_text(_SOURCE)
  q = cc.normalize_text(
      "It fell. Completely invented assertion about nurse staffing ratios "
      "across regional county clinics in the third quarter.")
  r = cc.find_quote(q, src)
  assert r["method"] is None


def test_find_quote_rejects_swapped_number():
  src = cc.normalize_text(_SOURCE)
  q = cc.normalize_text("Thirty-day readmissions fell 28% in the treatment "
                        "arm relative to usual care")
  assert cc.find_quote(q, src)["method"] is None


def test_find_quote_accepts_genuine_number_in_quote():
  src = cc.normalize_text(_SOURCE)
  q = cc.normalize_text("Thirty-day readmissions fell 18% in the treatment "
                        "arm relative to usual care")
  assert cc.find_quote(q, src)["method"] is not None


def test_find_quote_rejects_deleted_negation():
  src = cc.normalize_text(
      "Mortality did not differ between groups at 90 days in the cohort.")
  q = cc.normalize_text(
      "Mortality did differ between groups at 90 days in the cohort.")
  assert cc.find_quote(q, src)["method"] is None


def test_find_quote_rejects_deleted_percent_sign():
  src = cc.normalize_text(
      "The rate was 18% among treated patients across the entire cohort.")
  q = cc.normalize_text(
      "The rate was 18 among treated patients across the entire cohort.")
  assert cc.find_quote(q, src)["method"] is None


def test_find_quote_rejects_word_substitution():
  src = cc.normalize_text(
      "We enrolled 814 adult patients across 12 regional hospitals.")
  q = cc.normalize_text(
      "We enrolled 814 adult weights across 12 regional hospitals.")
  assert cc.find_quote(q, src)["method"] is None


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


def test_find_quote_perf_budget():
  src = cc.normalize_text(("filler sentence about methodology and cohorts. "
                           * 2000) + _SOURCE)
  assert len(src) > 80_000
  q = cc.normalize_text("adherence averaged 71% and declined over the "
                        "follow-up period")
  t0 = time.monotonic()
  for _ in range(40):
    cc.find_quote(q, src)
  assert time.monotonic() - t0 < 30


# --- anchors ---

def test_numbers_grounded_ignores_unaligned_neighbor(tmp_path):
  source = cc.normalize_text(
      "Readmissions fell 18% in the treatment arm here. "
      "Table 2 then lists 28 baseline covariates for the cohort.")
  q = cc.normalize_text(
      "Readmissions fell 28% in the treatment arm here")
  assert cc.find_quote(q, source)["method"] is None


def test_numbers_grounded_rejects_digit_subset_of_larger_number():
  source = cc.normalize_text(
      "We observed a rate of 108 percent decline across cohort members here.")
  q = cc.normalize_text(
      "We observed a rate of 18 percent decline across cohort members here")
  assert cc.find_quote(q, source)["method"] is None


def test_numbers_grounded_rejects_leading_digit_in_source():
  source = cc.normalize_text(
      "We saw 118 percent across the enrolled cohort here today.")
  q = cc.normalize_text(
      "We saw 18 percent across the enrolled cohort here today")
  assert cc.find_quote(q, source)["method"] is None


def test_numbers_grounded_rejects_trailing_digit_in_source():
  source = cc.normalize_text(
      "The rate was 181 percent across the enrolled cohort now here.")
  q = cc.normalize_text(
      "The rate was 18 percent across the enrolled cohort now here")
  assert cc.find_quote(q, source)["method"] is None


def test_numbers_grounded_rejects_fractional_part_of_source_decimal():
  source = cc.normalize_text(
      "The score was 12.5 points across the whole study cohort today.")
  q = cc.normalize_text(
      "The score was 2.5 points across the whole study cohort today")
  assert cc.find_quote(q, source)["method"] is None


def test_numbers_grounded_accepts_genuine_decimal():
  source = cc.normalize_text(
      "The model reached 96.5% sensitivity across the abstract set here.")
  q = cc.normalize_text(
      "The model reached 96.5% sensitivity across the abstract set here")
  assert cc.find_quote(q, source)["method"] is not None


def test_exact_path_rejects_number_substring_of_source():
  src = cc.normalize_text(
      "The team reported 118 percent improvement in the treated arm here now.")
  q = cc.normalize_text(
      "18 percent improvement in the treated arm here now")
  assert q in src
  assert cc.find_quote(q, src)["method"] is None


def test_grounding_rejects_sign_flip():
  src = cc.normalize_text(
      "The correlation was -18 across the full study cohort measured here now.")
  q = cc.normalize_text(
      "The correlation was 18 across the full study cohort measured here now")
  assert cc.find_quote(q, src)["method"] is None


def test_grounding_accepts_matching_sign():
  src = cc.normalize_text(
      "The correlation was -18 across the full study cohort measured here now.")
  q = cc.normalize_text(
      "The correlation was -18 across the full study cohort measured here now")
  assert cc.find_quote(q, src)["method"] is not None


def test_grounding_rejects_leading_decimal_mismatch():
  src = cc.normalize_text(
      "The effect size was .5 across the full study cohort measured today here.")
  q = cc.normalize_text(
      "The effect size was 5 across the full study cohort measured today here")
  assert cc.find_quote(q, src)["method"] is None


def test_numbers_grounded_accepts_number_next_to_noise(tmp_path):
  source = cc.normalize_text(
      "We observed a rate of 18 % decline across cohort members here today.")
  q = cc.normalize_text(
      "We observed a rate of 18% decline across cohort members here today")
  assert cc.find_quote(q, source)["method"] is not None


def test_per_sentence_rejects_distant_stitched_sentences():
  source = cc.normalize_text(
      "The cohort enrolled many adult patients across regional sites here. "
      + ("intervening filler sentence about methodology and design work. " * 25)
      + "Mortality did not differ between the two study groups at follow up.")
  q = cc.normalize_text(
      "The cohort enrolled many adult patients across regional sites here. "
      "Mortality did not differ between the two study groups at follow up.")
  assert cc.find_quote(q, source)["method"] is None


def test_per_sentence_rejects_nearby_substantive_omission():
  source = cc.normalize_text(
      "Readmissions fell across the enrolled treatment cohort at follow up. "
      "The apparent difference disappeared after covariate adjustment. "
      "Mortality did not differ between the two study groups at follow up.")
  q = cc.normalize_text(
      "Readmissions fell across the enrolled treatment cohort at follow up. "
      "Mortality did not differ between the two study groups at follow up.")
  assert cc.find_quote(q, source)["method"] is None


def test_artifact_marker_cannot_hide_substantive_negation():
  source = cc.normalize_text(
      "The intervention journal did not reduce mortality across the cohort.")
  q = cc.normalize_text(
      "The intervention reduce mortality across the cohort")
  assert cc.find_quote(q, source)["method"] is None


def test_author_year_running_header_is_accepted():
  source = cc.normalize_text(
      "The intervention reduced hos Smith et al. 2026 pital readmissions "
      "among adult patients across all regional sites.")
  q = cc.normalize_text(
      "The intervention reduced hospital readmissions among adult patients "
      "across all regional sites.")
  assert cc.find_quote(q, source)["method"] == "fuzzy"


def test_extract_numbers_keeps_stats_drops_years():
  nums = cc.extract_numbers("In 2022, 814 patients showed an 18% drop "
                            "(p<0.01)")
  assert "814" in nums and "18" in nums and "0.01" in nums
  assert "2022" not in nums


def test_extract_words_drops_stoplist_and_filler():
  words = cc.extract_words("The study results suggest readmission rates "
                           "declined")
  assert "readmission" in words
  assert "study" not in words and "results" not in words


# --- sanitize + load_source ---

def test_sanitize_id_matches_read_paper_behavior():
  assert cc.sanitize_id("10.1/patel2022") == "10.1_patel2022"
  assert cc.sanitize_id("..evil") == "_evil"
  assert cc.sanitize_id("a b:c") == "a_b_c"
  assert cc.sanitize_id("") == "_"


def test_load_source_prefers_fulltext_then_abstract(tmp_path):
  ws = _ws(tmp_path, {"p1": {"fulltext.md": "full", "abstract.md": "abs"},
                      "p2": {"abstract.md": "abs only"}})
  assert cc.load_source(ws, "p1") == ("full", "fulltext")
  assert cc.load_source(ws, "p2") == ("abs only", "abstract")
  assert cc.load_source(ws, "nope") is None


def test_load_source_rejects_traversal(tmp_path):
  outside = tmp_path / "secret.md"
  outside.write_text("secret")
  ws = _ws(tmp_path / "w", {"p1": {"fulltext.md": "x"}})
  assert cc.load_source(ws, "../secret.md") is None
  assert cc.load_source(ws, "..") is None


# --- check_entry verdicts ---

def test_verified_when_quote_real_and_numbers_present(tmp_path):
  ws = _ws(tmp_path, {"p1": {"fulltext.md": _SOURCE}})
  r = cc.check_entry(_entry(), ws)
  assert r["status"] == "verified"
  assert r["source_scope"] == "fulltext"
  assert "18" in r["anchors"]["numbers_found"]


def test_needs_review_when_claim_has_unanchored_number(tmp_path):
  ws = _ws(tmp_path, {"p1": {"fulltext.md": _SOURCE}})
  r = cc.check_entry(_entry(
      claim="The trial enrolled 814 patients and reduced readmissions by 22%.",
      quote="We enrolled 814 adult patients across 12 regional hospitals."),
      ws)
  assert r["status"] == "needs_review"
  assert "814" in r["anchors"]["numbers_found"]
  assert "22" in r["anchors"]["numbers_missing"]


def test_fabricated_quote_hard_fails(tmp_path):
  ws = _ws(tmp_path, {"p1": {"fulltext.md": _SOURCE}})
  r = cc.check_entry(_entry(
      quote="we surveyed 814 nurses across twelve county clinics during "
            "the second enrollment window"), ws)
  assert r["status"] == "fabricated_quote"
  assert r["best_window"]


def test_no_quote_and_too_short_hard_fail(tmp_path):
  ws = _ws(tmp_path, {"p1": {"fulltext.md": _SOURCE}})
  assert cc.check_entry(_entry(quote=""), ws)["status"] == "no_quote"
  assert cc.check_entry(_entry(quote="the treatment arm"),
                        ws)["status"] == "quote_too_short"


def test_needs_review_when_claim_numbers_absent_from_quote(tmp_path):
  ws = _ws(tmp_path, {"p1": {"fulltext.md": _SOURCE}})
  r = cc.check_entry(_entry(
      claim="Readmissions dropped 42% among 300 enrolled veterans.",
      quote="Mortality did not differ between groups at 90 days. Adherence "
            "averaged 71% and declined over the follow-up period."), ws)
  assert r["status"] == "needs_review"
  assert "42" in r["anchors"]["numbers_missing"]


def test_number_free_claim_with_real_quote_is_verified(tmp_path):
  ws = _ws(tmp_path, {"p1": {"fulltext.md": _SOURCE}})
  r = cc.check_entry(_entry(
      claim="Adherence to the program declined over the follow-up period.",
      quote="Adherence averaged 71% and declined over the follow-up period"),
      ws)
  assert r["status"] == "verified"


def test_boundary_negation_is_needs_review(tmp_path):
  source = ("The intervention did not reduce mortality among adults across "
            "the full follow-up period in this regional cohort.")
  ws = _ws(tmp_path, {"p1": {"fulltext.md": source}})
  r = cc.check_entry(_entry(
      claim="The intervention reduced mortality among adults.",
      quote="reduce mortality among adults across the full follow-up period "
            "in this regional cohort"), ws)
  assert r["status"] == "needs_review"
  assert r["context_risks"] == ["leading_negation_context"]


def test_title_quote_on_abstract_is_needs_review(tmp_path):
  abs_md = ("# Effects of Structured Exercise Programs on Hospital "
            "Readmission Rates in Adults\n\n"
            "We enrolled 814 patients and measured 30-day readmission.")
  ws = _ws(tmp_path, {"p1": {"abstract.md": abs_md}})
  r = cc.check_entry(_entry(
      claim="Exercise affects hospital readmission outcomes broadly.",
      quote="Effects of Structured Exercise Programs on Hospital "
            "Readmission Rates in Adults"), ws)
  assert r["status"] == "needs_review"
  assert r["quote_is_title"] is True
  assert r["source_scope"] == "abstract"


def test_background_role_verifies_real_quote(tmp_path):
  ws = _ws(tmp_path, {"p1": {"fulltext.md": _SOURCE}})
  r = cc.check_entry(_entry(role="background"), ws)
  assert r["status"] == "background"
  assert r["matched"] == "exact"


def test_background_role_does_not_skip_source_or_quote_failures(tmp_path):
  ws = _ws(tmp_path, {"p1": {"fulltext.md": _SOURCE}})
  assert cc.check_entry(_entry(quote="", role="background"), ws)["status"] == (
      "no_quote")
  assert cc.check_entry(
      _entry(paper_id="ghost", role="background"), ws)["status"] == (
          "source_missing")


def test_source_missing_hard_fails(tmp_path):
  ws = _ws(tmp_path, {"p1": {"fulltext.md": _SOURCE}})
  assert cc.check_entry(_entry(paper_id="ghost"),
                        ws)["status"] == "source_missing"


# --- coverage ---

def test_coverage_flags_uncited_claimless_sentence():
  synthesis = ("Readmissions fell 18% in the treatment arm (Patel, 2022). "
               "Mortality was unchanged at 90 days [2]. "
               "This section has no citation and is ignored.")
  claims = [_entry()]
  gaps = cc.coverage_gaps(synthesis, claims)
  assert len(gaps) == 1
  assert "Mortality" in gaps[0]


def test_coverage_matches_lightly_edited_claim():
  synthesis = "Thirty-day readmissions fell by 18% in the arm (Patel, 2022)."
  claims = [_entry(claim="Readmissions fell by 18% in the arm.")]
  assert cc.coverage_gaps(synthesis, claims) == []


def test_coverage_requires_claim_citation_to_match_sentence_source():
  synthesis = ("Readmissions fell 18% in the treatment arm of the trial "
               "(DifferentAuthor, 2024).")
  assert cc.coverage_gaps(synthesis, [_entry()]) == [synthesis]


def test_coverage_requires_trace_for_each_source_in_multi_citation():
  synthesis = ("Readmissions fell 18% in the treatment arm of the trial "
               "(Patel, 2022; Lee, 2021).")
  assert cc.coverage_gaps(synthesis, [_entry()]) == [synthesis]
  claims = [_entry(), _entry(citation="Lee, 2021")]
  assert cc.coverage_gaps(synthesis, claims) == []


def test_citation_identity_normalizes_ampersand_and_narrative_and():
  synthesis = ("Smith and Jones (2020) found readmissions fell 18% in the "
               "treatment arm of the trial.")
  claims = [_entry(
      claim="Readmissions fell 18% in the treatment arm of the trial.",
      citation="Smith & Jones, 2020")]
  assert cc.coverage_gaps(synthesis, claims) == []


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


def test_coverage_ignores_non_citation_parenthetical_years():
  synthesis = ("Usage has grown rapidly (since 2020). Readmissions fell 18% "
               "in the treatment arm of the trial (Patel, 2022).")
  claims = [_entry()]
  assert cc.coverage_gaps(synthesis, claims) == []


def test_coverage_paper_id_needs_word_boundary():
  synthesis = "The group1 cohort improved substantially over baseline."
  claims = [_entry(paper_id="p1")]
  assert cc.coverage_gaps(synthesis, claims) == []


def test_coverage_detects_lowercase_particle_surnames():
  synthesis = ("Outcomes improved across the cohort (van der Berg, 2020). "
               "Readmissions fell 18% in the treatment arm of the trial "
               "(Patel, 2022).")
  claims = [_entry()]
  gaps = cc.coverage_gaps(synthesis, claims)
  assert len(gaps) == 1
  assert "van der Berg" in gaps[0]


def test_coverage_short_claim_cannot_blanket_cover():
  synthesis = ("Diabetes management systems in agriculture reduced costs "
               "across all surveyed farms (Wong, 2023).")
  claims = [_entry(claim="diabetes")]
  gaps = cc.coverage_gaps(synthesis, claims)
  assert len(gaps) == 1


def test_coverage_detects_narrative_author_year():
  synthesis = ("Patel (2022) found readmissions fell 18% in the treatment "
               "arm of the trial. An uncovered narrative claim here from "
               "Lee et al. (2021).")
  claims = [_entry(claim="Readmissions fell 18% in the treatment arm of "
                         "the trial.")]
  gaps = cc.coverage_gaps(synthesis, claims)
  assert len(gaps) == 1
  assert "Lee et al." in gaps[0]


def test_coverage_narrative_year_only_needs_a_surname():
  synthesis = "Adoption grew rapidly (2020) and then plateaued sharply."
  assert cc.coverage_gaps(synthesis, [_entry()]) == []


def test_coverage_detects_citation_with_page_locator():
  synthesis = "A distinct unsupported finding appears here (Smith, 2020, p. 4)."
  assert cc.coverage_gaps(synthesis, []) == [synthesis]


@pytest.mark.parametrize("rendered, expected", [
    ("[1, 2]", {"number:1", "number:2"}),
    ("[1-3]", {"number:1", "number:2", "number:3"}),
    ("[1\u20133]", {"number:1", "number:2", "number:3"}),
])
def test_grouped_numeric_citations_expand(rendered, expected):
  assert cc.citation_keys(rendered) == expected
  synthesis = f"An unsupported grouped finding appears in this sentence {rendered}."
  assert cc.coverage_gaps(synthesis, []) == [synthesis]


def test_grouped_numeric_citation_requires_every_source_trace():
  synthesis = ("Readmissions fell 18% in the treatment arm of the trial "
               "[1, 2].")
  claims = [_entry(citation="[1]")]
  assert cc.coverage_gaps(synthesis, claims) == [synthesis]
  claims.append(_entry(citation="[2]"))
  assert cc.coverage_gaps(synthesis, claims) == []


def test_coverage_ignores_capitalized_non_citation_year_parenthetical():
  synthesis = "The sample was assembled in stages (Data collected in 2020)."
  assert cc.coverage_gaps(synthesis, []) == []


def test_coverage_ignores_comma_year_prose_parenthetical():
  synthesis = "Enrollment closed after the final wave (In the final sample, 2020)."
  assert cc.coverage_gaps(synthesis, []) == []


# --- main ---

def _run_main(tmp_path, entries, synthesis=None, corpus=None, references=None):
  ws = _ws(tmp_path, {"p1": {"fulltext.md": _SOURCE}})
  if corpus is None:
    corpus = [{"key": "paper-one", "ids": {"pmcid": "p1"},
               "title": "A Paper", "authors": ["Priya Patel"], "year": 2022,
               "role": "evidence"}]
  (ws / "corpus.json").write_text(json.dumps(corpus))
  claims_file = tmp_path / "claims.json"
  claims_file.write_text(json.dumps(entries))
  argv = ["--claims", str(claims_file), "--workspace", str(ws)]
  if synthesis is not None:
    syn = tmp_path / "synthesis.md"
    syn.write_text(synthesis)
    argv += ["--synthesis", str(syn)]
  if references is not None:
    refs = tmp_path / "refs.json"
    refs.write_text(json.dumps(references))
    argv += ["--references", str(refs)]
  return cc.main(argv)


def test_main_exit_zero_all_verified(tmp_path, capsys):
  code = _run_main(tmp_path, [_entry()])
  out = json.loads(capsys.readouterr().out)
  assert code == 0
  assert out["verified"] == 1 and out["total"] == 1
  assert out["coverage_checked"] is False


def test_main_exit_one_on_fabrication(tmp_path, capsys):
  code = _run_main(tmp_path, [_entry(
      quote="entirely invented passage about nurses and county clinics "
            "spanning multiple enrollment windows")])
  assert code == 1
  assert json.loads(capsys.readouterr().out)["fabricated_quote"] == 1


def test_main_exit_one_on_needs_review(tmp_path, capsys):
  code = _run_main(tmp_path, [_entry(
      claim="Readmissions fell 23% in the treatment arm of the trial.")])
  assert code == 1
  assert json.loads(capsys.readouterr().out)["needs_review"] == 1


def test_main_exit_one_on_uncovered_claim(tmp_path, capsys):
  code = _run_main(tmp_path, [_entry()],
                   synthesis="An uncovered cited finding here (Lee, 2021). "
                             "Readmissions fell 18% in the treatment arm of "
                             "the trial (Patel, 2022).")
  out = json.loads(capsys.readouterr().out)
  assert code == 1
  assert out["uncovered_claim"] == 1
  assert out["coverage_checked"] is True


@pytest.mark.parametrize("synthesis", ["", "No citations appear in this draft."])
def test_main_rejects_empty_or_citation_free_synthesis(tmp_path, synthesis):
  with pytest.raises(SystemExit, match="synthesis file"):
    _run_main(tmp_path, [_entry()], synthesis=synthesis)


def test_main_summary_flags_unresolved_source_quote_errors(tmp_path, capsys):
  code = _run_main(tmp_path, [_entry(paper_id="ghost")])
  assert code == 1
  assert "unresolved source/quote" in capsys.readouterr().err


def test_main_rejects_malformed_claims(tmp_path):
  ws = _ws(tmp_path, {"p1": {"fulltext.md": _SOURCE}})
  bad = tmp_path / "claims.json"
  bad.write_text(json.dumps({"not": "a list"}))
  with pytest.raises(SystemExit):
    cc.main(["--claims", str(bad), "--workspace", str(ws)])


@pytest.mark.parametrize("entries", [
    [],
    [{"claim": "x"}],
    [{"claim": 42, "paper_id": "p1", "citation": "Patel, 2022",
      "supporting_quote": "a sufficiently long supporting quotation here"}],
])
def test_main_rejects_empty_or_incomplete_claims(tmp_path, entries):
  with pytest.raises(SystemExit):
    _run_main(tmp_path, entries)


def test_main_rejects_author_year_that_does_not_match_paper(tmp_path):
  with pytest.raises(SystemExit, match="does not match"):
    _run_main(tmp_path, [_entry(citation="DifferentAuthor, 2024")])


def test_main_rejects_legacy_corpus_without_authors(tmp_path):
  corpus = [{"key": "paper-one", "ids": {"pmcid": "p1"},
             "title": "A Paper", "year": 2022, "role": "evidence"}]
  with pytest.raises(SystemExit, match="has no authors"):
    _run_main(tmp_path, [_entry()], corpus=corpus)


def test_main_binds_numeric_citation_through_ordered_references(tmp_path):
  corpus = [
      {"key": "paper-one", "ids": {"pmcid": "p1", "doi": "10.1/one"},
       "title": "A Paper", "authors": ["Priya Patel"], "year": 2022,
       "role": "evidence"},
      {"key": "paper-two", "ids": {"pmcid": "p2", "doi": "10.1/two"},
       "title": "Other Paper", "authors": ["Laura Lee"], "year": 2021,
       "role": "evidence"},
  ]
  refs = [{"doi": "10.1/one", "title": "A Paper"},
          {"doi": "10.1/two", "title": "Other Paper"}]
  assert _run_main(tmp_path, [_entry(citation="[1]")],
                   corpus=corpus, references=refs) == 0
  with pytest.raises(SystemExit, match="numeric citation does not match"):
    _run_main(tmp_path / "bad", [_entry(citation="[2]")],
              corpus=corpus, references=refs)


def test_main_requires_references_for_numeric_citation(tmp_path):
  with pytest.raises(SystemExit, match="--references"):
    _run_main(tmp_path, [_entry(citation="[1]")])


def test_coverage_is_satisfied_by_verified_background_trace():
  synthesis = "The intervention cut readmissions by 18% in the arm (Patel, 2022)."
  claims = [{"claim": "The intervention cut readmissions by 18% in the arm.",
             "paper_id": "p1", "citation": "Patel, 2022",
             "supporting_quote": "A real supporting passage long enough here",
             "role": "background"}]
  gaps = cc.coverage_gaps(synthesis, claims)
  assert gaps == []


def test_main_rejects_role_that_disagrees_with_corpus(tmp_path):
  with pytest.raises(SystemExit, match="role does not match"):
    _run_main(tmp_path, [_entry(role="background")])


def test_main_accepts_verified_background_trace(tmp_path, capsys):
  corpus = [{"key": "paper-one", "ids": {"pmcid": "p1"},
             "title": "A Paper", "authors": ["Priya Patel"], "year": 2022,
             "role": "background"}]
  synthesis = ("Readmissions fell 18% in the treatment arm of the trial "
               "(Patel, 2022).")
  assert _run_main(tmp_path, [_entry(role="background")], synthesis=synthesis,
                   corpus=corpus) == 0
  assert json.loads(capsys.readouterr().out)["background"] == 1


def test_coverage_detects_parenthetical_year_suffix():
  synthesis = ("Outcomes improved markedly overall (Smith, 2020a). "
               "A second distinct finding was reported (Lee et al., 2021b).")
  gaps = cc.coverage_gaps(synthesis, [])
  assert len(gaps) == 2


def test_title_quote_on_fulltext_is_needs_review(tmp_path):
  ft = ("# A Controlled Study of Structured Exercise for Hospital "
        "Readmission in Adults\n\nWe enrolled 814 patients in the trial.")
  ws = _ws(tmp_path, {"p1": {"fulltext.md": ft}})
  r = cc.check_entry(_entry(
      claim="Exercise affects hospital readmission outcomes broadly.",
      quote="A Controlled Study of Structured Exercise for Hospital "
            "Readmission in Adults"), ws)
  assert r["quote_is_title"] is True
  assert r["status"] == "needs_review"


def test_bold_pdf_title_quote_is_needs_review(tmp_path):
  ft = ("**A Controlled Study of Structured Exercise for Hospital "
        "Readmission in Adults**\n\nWe enrolled 814 patients in the trial.")
  ws = _ws(tmp_path, {"p1": {"fulltext.md": ft}})
  r = cc.check_entry(_entry(
      claim="Exercise affects hospital readmission outcomes broadly.",
      quote="A Controlled Study of Structured Exercise for Hospital "
            "Readmission in Adults"), ws)
  assert r["quote_is_title"] is True
  assert r["status"] == "needs_review"


def test_multiline_bold_pdf_title_after_frontmatter_is_needs_review(tmp_path):
  ft = ("Downloaded from publisher.example\n\n"
        "**A Controlled Study of Structured Exercise for\n"
        "Hospital Readmission in Adults**\n\n"
        "We enrolled 814 patients in the trial.")
  ws = _ws(tmp_path, {"p1": {"fulltext.md": ft}})
  r = cc.check_entry(_entry(
      claim="Exercise affects hospital readmission outcomes broadly.",
      quote="A Controlled Study of Structured Exercise for Hospital "
            "Readmission in Adults"), ws)
  assert r["quote_is_title"] is True
  assert r["status"] == "needs_review"


def _num_sentence(num):
  return ("The measured outcome reached %s across the enrolled study cohort "
          "during the follow up observation window here today now" % num)


def _random_number(rng):
  kind = rng.choice(["int", "int", "decimal", "signed", "comma"])
  if kind == "int":
    return str(rng.randint(1, 999))
  if kind == "decimal":
    return "%d.%d" % (rng.randint(0, 99), rng.randint(1, 9))
  if kind == "signed":
    return "-%d" % rng.randint(1, 99)
  return "{:,}".format(rng.randint(1000, 9_999_999))


def _fabricate(num, rng):
  digits = [c for c in num if c.isdigit()]
  for _ in range(20):
    mut = rng.choice(["digit", "drop", "add", "sign", "dot"])
    if mut == "digit" and digits:
      i = rng.randrange(len(num))
      if num[i].isdigit():
        cand = num[:i] + str((int(num[i]) + rng.randint(1, 8)) % 10) + num[i + 1:]
      else:
        continue
    elif mut == "drop" and len(digits) > 1:
      i = next(j for j, c in enumerate(num) if c.isdigit())
      cand = num[:i] + num[i + 1:]
    elif mut == "add":
      cand = str(rng.randint(1, 9)) + num
    elif mut == "sign":
      cand = num[1:] if num.startswith("-") else "-" + num
    elif mut == "dot":
      cand = num + ".%d" % rng.randint(1, 9) if "." not in num else num.replace(".", "")
    else:
      continue
    if _norm(cand) != _norm(num) and any(c.isdigit() for c in cand):
      return cand
  return None


def _norm(tok):
  return tok.replace(",", "")


def test_fuzz_number_grounding():
  rng = __import__("random").Random(1234)
  verified_genuine = flagged_fabricated = 0
  for _ in range(2000):
    num = _random_number(rng)
    src = cc.normalize_text(_num_sentence(num))
    genuine = cc.normalize_text(_num_sentence(num))
    assert cc.find_quote(genuine, src)["method"] is not None, (
        "genuine rejected: %r" % num)
    verified_genuine += 1
    fab = _fabricate(num, rng)
    if fab is None:
      continue
    quote = cc.normalize_text(_num_sentence(fab))
    assert cc.find_quote(quote, src)["method"] is None, (
        "fabricated verified: source %r quote %r" % (num, fab))
    flagged_fabricated += 1
  assert verified_genuine == 2000
  assert flagged_fabricated > 1500


if __name__ == "__main__":
  sys.exit(pytest.main([__file__, "-v"]))
