import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
HYPOTHESIS_SKILL = ROOT / "skills/hypothesis-testing/SKILL.md"
QUANT_SKILL = ROOT / "skills/quantitative-analysis/SKILL.md"
SCORER_CASE = (
    ROOT / "evals/test-cases/hypothesis-testing/test-outcome-scorer.md")


def _section(text, start, end):
  return text[text.index(start):text.index(end)]


def test_hypothesis_protocol_tests_the_scorer_before_freezing_the_plan():
  skill = HYPOTHESIS_SKILL.read_text(encoding="utf-8")
  step = _section(skill, "6. **Falsification Criteria**", "</protocol>")

  assert "at least 5 real outputs" in step
  assert "tie-break rule" in step
  assert "both scores" in step


def test_hypothesis_output_format_reports_the_scorer_check():
  skill = HYPOTHESIS_SKILL.read_text(encoding="utf-8")

  assert "**Scorer Check**" in _section(
      skill, "<output_format>", "</output_format>")


def test_quantitative_inspection_compares_scores_with_raw_outputs():
  skill = QUANT_SKILL.read_text(encoding="utf-8")
  step = _section(skill, "1. **Data Inspection**", "2. **Assumption")

  assert "raw outputs" in step
  assert "both scores" in step


def test_scorer_eval_case_targets_hypothesis_testing():
  case = SCORER_CASE.read_text(encoding="utf-8")

  assert "- **Implementation Skill**: hypothesis-testing" in case
  assert "tie-break rule" in _section(case, "### Must Include", "### Should")
