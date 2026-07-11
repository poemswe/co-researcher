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
           quote="Thirty-day readmissions fell 18% in the treatment arm "
                 "relative to usual care",
           **kw):
  return {"claim": claim, "paper_id": paper_id,
          "supporting_quote": quote, **kw}


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
      "usual care, a difference",
      "usual care. RUNNING HEADER PAGE 7. A difference")
  src = cc.normalize_text(broken)
  q = cc.normalize_text(
      "Thirty-day readmissions fell 18% in the treatment arm relative to "
      "usual care. Mortality did not differ between groups at 90 days.")
  r = cc.find_quote(q, src)
  assert r["method"] in ("per_sentence", "fuzzy", "exact")
  assert r["coverage"] >= cc._QUOTE_MATCH_THRESHOLD


def test_find_quote_per_sentence_reports_matching_window():
  src = cc.normalize_text(_SOURCE.replace(
      "usual care, a difference",
      "usual care. RUNNING HEADER PAGE 7. A difference"))
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
      quote="Mortality did not differ between groups at 90 days and "
            "adherence declined over follow-up"), ws)
  assert r["status"] == "needs_review"
  assert "42" in r["anchors"]["numbers_missing"]


def test_number_free_claim_with_real_quote_is_verified(tmp_path):
  ws = _ws(tmp_path, {"p1": {"fulltext.md": _SOURCE}})
  r = cc.check_entry(_entry(
      claim="Adherence to the program declined over the follow-up period.",
      quote="Adherence averaged 71% and declined over the follow-up period"),
      ws)
  assert r["status"] == "verified"


def test_title_quote_on_abstract_is_needs_review(tmp_path):
  abs_md = ("# Effects of Structured Exercise on Hospital Readmission\n\n"
            "We enrolled 814 patients and measured 30-day readmission.")
  ws = _ws(tmp_path, {"p1": {"abstract.md": abs_md}})
  r = cc.check_entry(_entry(
      claim="Exercise affects hospital readmission outcomes broadly.",
      quote="Effects of Structured Exercise on Hospital Readmission"), ws)
  assert r["status"] == "needs_review"
  assert r["quote_is_title"] is True
  assert r["source_scope"] == "abstract"


def test_background_role_skips_quote_check(tmp_path):
  ws = _ws(tmp_path, {"p1": {"fulltext.md": _SOURCE}})
  r = cc.check_entry(_entry(quote="", role="background"), ws)
  assert r["status"] == "background"


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


# --- main ---

def _run_main(tmp_path, entries, synthesis=None):
  ws = _ws(tmp_path, {"p1": {"fulltext.md": _SOURCE}})
  claims_file = tmp_path / "claims.json"
  claims_file.write_text(json.dumps(entries))
  argv = ["--claims", str(claims_file), "--workspace", str(ws)]
  if synthesis is not None:
    syn = tmp_path / "synthesis.md"
    syn.write_text(synthesis)
    argv += ["--synthesis", str(syn)]
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


def test_main_exit_one_on_uncovered_claim(tmp_path, capsys):
  code = _run_main(tmp_path, [_entry()],
                   synthesis="An uncovered cited finding here (Lee, 2021). "
                             "Readmissions fell 18% in the treatment arm of "
                             "the trial (Patel, 2022).")
  out = json.loads(capsys.readouterr().out)
  assert code == 1
  assert out["uncovered_claim"] == 1
  assert out["coverage_checked"] is True


def test_main_rejects_malformed_claims(tmp_path):
  ws = _ws(tmp_path, {"p1": {"fulltext.md": _SOURCE}})
  bad = tmp_path / "claims.json"
  bad.write_text(json.dumps({"not": "a list"}))
  with pytest.raises(SystemExit):
    cc.main(["--claims", str(bad), "--workspace", str(ws)])


if __name__ == "__main__":
  sys.exit(pytest.main([__file__, "-v"]))
