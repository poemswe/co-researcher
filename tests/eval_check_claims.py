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
  header = "\n\nJournal of Fixture Studies  |  Vol. 12  |  2026\n\n"
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
  assert "Journal of Fixture Studies" in inject_headers("x" * 900)


def test_apply_pdf_noise_composes_all_three():
  noised = apply_pdf_noise(FIXTURE_DOCS["doc_a"])
  assert "ﬁ" in noised or "ﬂ" in noised
  assert "Journal of Fixture Studies" in noised
  assert "-\n" in noised


if __name__ == "__main__":
  sys.exit(pytest.main([__file__, "-v"]))
