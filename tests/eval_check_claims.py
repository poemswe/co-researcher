# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pytest",
# ]
# ///

"""Eval harness for check_claims.py quote verification.

Fixture-bound regression insurance and boundary probe — NOT field
validation. Positives are verbatim fixture sentences whose SOURCE is
passed through modeled pymupdf4llm noise; negatives are same-topic
paraphrases, cross-document sentences, and fabrications. Real-paper
numbers are recorded in the PR per the spec's real-run gate.
"""

import re
import sys

import pytest

FIXTURE_DOCS = {
    "doc_a": (
        "Effects of Structured Exercise on Hospital Readmission\n\n"
        "We enrolled 814 adult patients across 12 regional hospitals between "
        "March and November. Participants were randomized to a structured "
        "exercise program or usual care after discharge. The primary outcome "
        "was 30-day readmission; secondary outcomes included mortality and "
        "self-reported quality of life measured at 90 days.\n\n"
        "Thirty-day readmissions fell 18% in the treatment arm relative to "
        "usual care, a difference that persisted after adjustment for age and "
        "comorbidity burden. Mortality did not differ between groups at 90 "
        "days. Adherence to the exercise protocol averaged 71% and declined "
        "over the follow-up period.\n\n"
        "These findings suggest that a low-cost structured exercise program "
        "can meaningfully reduce short-term readmission risk in a general "
        "inpatient population, although effects on longer-term outcomes "
        "remain uncertain."
    ),
    "doc_b": (
        "Language Models for Title and Abstract Screening\n\n"
        "We evaluated three large language models on 5240 abstracts drawn "
        "from seven published systematic reviews. Each model screened every "
        "abstract against the original inclusion criteria, and decisions were "
        "compared with the published consensus of two human reviewers.\n\n"
        "The best-performing model achieved 96% sensitivity and 89% "
        "specificity, misclassifying 43 abstracts that both human reviewers "
        "had included. Ensemble voting across the three models raised "
        "specificity to 94% at the cost of a 2-point drop in sensitivity. "
        "Screening the full corpus cost under 4 dollars per thousand "
        "abstracts.\n\n"
        "Model errors clustered in reviews with vague eligibility criteria, "
        "suggesting that screening performance depends as much on protocol "
        "clarity as on model capability."
    ),
    "doc_unicode": (
        "Вмешательство снизило смертность среди участников исследования."
    ),
    "doc_pipe": (
        "Readmissions fell across the treatment cohort. "
        "| treatment caused severe adverse events | "
        "Mortality remained unchanged during follow-up."
    ),
}


def hyphenate_linebreaks(text, every=60):
  out, count = [], 0
  for word in text.split(" "):
    count += len(word) + 1
    if count > every and len(word) > 6:
      mid = len(word) // 2
      out.append(word[:mid] + "-\n" + word[mid:])
      count = 0
    else:
      out.append(word)
  return " ".join(out)


def ligate(text):
  return text.replace("fi", "ﬁ").replace("fl", "ﬂ")


def inject_headers(text, every=400):
  header = "\n\nRUNNING HEADER PAGE 7\n\n"
  chunks = [text[i:i + every] for i in range(0, len(text), every)]
  return header.join(chunks)


def apply_pdf_noise(text):
  return inject_headers(ligate(hyphenate_linebreaks(text)))


def test_hyphenate_splits_long_words_across_linebreaks():
  noised = hyphenate_linebreaks("aaaa " * 12 + "readmission rates", every=40)
  assert "-\n" in noised


def test_ligate_substitutes_ligature_codepoints():
  assert "ﬁ" in ligate("significant findings")


def test_inject_headers_inserts_running_header():
  assert "RUNNING HEADER PAGE 7" in inject_headers("x" * 900)


def test_apply_pdf_noise_composes_all_three():
  noised = apply_pdf_noise(FIXTURE_DOCS["doc_a"])
  assert "ﬁ" in noised or "ﬂ" in noised
  assert "RUNNING HEADER PAGE 7" in noised
  assert "-\n" in noised


import importlib.util
import pathlib

_SCRIPTS = (pathlib.Path(__file__).resolve().parent.parent
            / "skills/literature-review/scripts")
_ccspec = importlib.util.spec_from_file_location(
    "check_claims", _SCRIPTS / "check_claims.py")
cc = importlib.util.module_from_spec(_ccspec)
_ccspec.loader.exec_module(cc)


def _sentences(doc):
  body = doc.split("\n\n", 1)[1]
  return [s.strip() for s in re.split(r"(?<=[.!?])\s+", body)
          if len(s.split()) >= 8]


POSITIVES = [(s, "doc_a") for s in _sentences(FIXTURE_DOCS["doc_a"])] + \
            [(s, "doc_b") for s in _sentences(FIXTURE_DOCS["doc_b"])]

NEGATIVE_PARAPHRASES = [
    ("Hospital returns dropped by nearly a fifth for exercising patients "
     "compared with standard discharge care", "doc_a"),
    ("Roughly seventy percent of participants kept up the exercise routine "
     "though engagement waned as months passed", "doc_a"),
    ("The strongest system correctly flagged over nine in ten eligible "
     "abstracts while wrongly excluding a few dozen", "doc_b"),
    ("Combining the three systems improved precision while sacrificing a "
     "small amount of recall in screening", "doc_b"),
]

NEGATIVE_CROSS_DOC = [(s, "doc_b") for s, _ in POSITIVES[:1]] + \
                     [(s, "doc_a") for s, d in POSITIVES if d == "doc_b"][:1]

NEGATIVE_FABRICATIONS = [
    ("We surveyed 814 nurses across twelve county clinics during the "
     "second enrollment window of the study", "doc_a"),
    ("The ensemble misclassified 512 abstracts drawn from nineteen "
     "Cochrane reviews of surgical interventions", "doc_b"),
]

NEGATIVE_NEAR_MISS = [
    ("Thirty-day readmissions fell 28% in the treatment arm relative to "
     "usual care, a difference that persisted after adjustment for age "
     "and comorbidity burden", "doc_a"),
    ("The best-performing model achieved 96% sensitivity and 79% "
     "specificity, misclassifying 43 abstracts that both human reviewers "
     "had included", "doc_b"),
    ("Thirty-day readmissions fell 28% in the treatment arm relative to "
     "usual care, a difference that persisted after adjustment for "
     "weight and comorbidity burden", "doc_a"),
    ("The best-performing model achieved 96% sensitivity and 79% "
     "specificity, misclassifying 44 abstracts that both human reviewers "
     "had included", "doc_b"),
]

NEGATIVES = (NEGATIVE_PARAPHRASES + NEGATIVE_CROSS_DOC +
             NEGATIVE_FABRICATIONS + NEGATIVE_NEAR_MISS + [
                 ("Вмешательство повысило смертность среди участников исследования.",
                  "doc_unicode"),
                 ("Readmissions fell across the treatment cohort. "
                  "Mortality remained unchanged during follow-up.",
                  "doc_pipe"),
             ])


def _verify(quote, doc_key):
  noised = cc.normalize_text(apply_pdf_noise(FIXTURE_DOCS[doc_key]))
  return cc.find_quote(cc.normalize_text(quote), noised)


def test_eval_positives_all_verify_through_pdf_noise():
  false_positives = [(q, r["coverage"]) for q, d in POSITIVES
                     if (r := _verify(q, d))["method"] is None]
  rate = len(false_positives) / len(POSITIVES)
  print(f"\nEVAL positives: {len(POSITIVES)} quotes, "
        f"FP(rejected genuine)={len(false_positives)} ({rate:.0%})")
  assert false_positives == [], false_positives


def test_eval_negatives_all_caught():
  false_negatives = [(q, r["coverage"]) for q, d in NEGATIVES
                     if (r := _verify(q, d))["method"] is not None]
  print(f"EVAL negatives: {len(NEGATIVES)} quotes, "
        f"FN(passed fabricated)={len(false_negatives)}")
  for q, d in NEGATIVES:
    cov = _verify(q, d)["coverage"]
    print(f"  cov={cov:.3f} {q[:60]!r}")
  for q, d in NEGATIVE_PARAPHRASES + NEGATIVE_CROSS_DOC + NEGATIVE_FABRICATIONS:
    cov = _verify(q, d)["coverage"]
    assert cov < 0.85, (q, cov)
  assert false_negatives == []


def test_eval_word_only_distortion_is_rejected():
  src = cc.normalize_text(FIXTURE_DOCS["doc_a"])
  distorted = cc.normalize_text(
      "We enrolled 814 adult weights across 12 regional hospitals between "
      "March and November")
  r = cc.find_quote(distorted, src)
  assert r["method"] is None


def test_eval_anchor_fire_rates(tmp_path):
  ws = tmp_path
  for key, doc in FIXTURE_DOCS.items():
    d = ws / "papers" / key
    d.mkdir(parents=True)
    (d / "fulltext.md").write_text(doc, encoding="utf-8")
  on_target = [
      {"claim": "Readmissions fell 18% in the treatment arm.",
       "paper_id": "doc_a",
       "citation": "Patel, 2022",
       "supporting_quote": "Thirty-day readmissions fell 18% in the "
                           "treatment arm relative to usual care"},
      {"claim": "The best model reached 96% sensitivity on abstracts.",
       "paper_id": "doc_b",
       "citation": "Lee, 2023",
       "supporting_quote": "The best-performing model achieved 96% "
                           "sensitivity and 89% specificity"},
  ]
  off_target = [
      {"claim": "Mortality dropped 40% among 512 enrolled veterans.",
       "paper_id": "doc_a",
       "citation": "Patel, 2022",
       "supporting_quote": "Mortality did not differ between groups at 90 "
                           "days. Adherence to the exercise protocol "
                           "averaged 71%"},
      {"claim": "Screening 9000 abstracts cost 62 dollars in total.",
       "paper_id": "doc_b",
       "citation": "Lee, 2023",
       "supporting_quote": "Model errors clustered in reviews with vague "
                           "eligibility criteria, suggesting that screening"},
  ]
  on_fired = sum(cc.check_entry(e, ws)["status"] == "needs_review"
                 for e in on_target)
  off_fired = sum(cc.check_entry(e, ws)["status"] == "needs_review"
                  for e in off_target)
  print(f"EVAL anchors: needs_review on-target {on_fired}/{len(on_target)}, "
        f"off-target {off_fired}/{len(off_target)}")
  assert on_fired == 0
  assert off_fired == len(off_target)


if __name__ == "__main__":
  sys.exit(pytest.main([__file__, "-v"]))
