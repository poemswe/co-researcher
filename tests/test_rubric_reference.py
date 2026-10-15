import collections
import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parents[1]
CASES = ROOT / "evals/test-cases"
REFERENCE = CASES / "README.md"
SHORT_NAMES = {
    "Analytical": "analytical-quality",
    "Research": "research-quality",
    "Quantitative": "quantitative-quality",
    "Qualitative": "qualitative-quality",
    "Design": "design-quality",
    "Output": "output-structure",
    "Reasoning": "reasoning-quality",
}
MATRIX_ROW = re.compile(
    r"^\| \[[^\]]+\]\(([^)]+)\) \| (\w+) \((\d+)%\) \| (\w+) \((\d+)%\) \| ([\w-]+) \|$",
    re.M)
PROFILE_LINE = re.compile(
    r"^- \*\*(Primary|Secondary|Tertiary)\*\*: ([a-z-]+) \((\d+)%\)", re.M)


def _profiles():
  """Rubric profile of every broad case file, keyed by path under CASES."""
  profiles = {}
  for path in sorted(CASES.glob("*/test-*.md")):
    text = path.read_text(encoding="utf-8")
    block = text[text.index("## Rubric Profile"):text.index("## Task Prompt")]
    profiles[path.relative_to(CASES).as_posix()] = [
        (rubric, int(weight)) for _, rubric, weight in PROFILE_LINE.findall(block)]
  return profiles


def _matrix():
  text = REFERENCE.read_text(encoding="utf-8")
  section = text[text.index("## Test-Rubric Mapping Matrix"):]
  section = section[:section.index("\n---")]
  return {
      path: ([(SHORT_NAMES[p], int(pw)), (SHORT_NAMES[s], int(sw))], agent)
      for path, p, pw, s, sw, agent in MATRIX_ROW.findall(section)}


def test_matrix_has_one_row_per_case_file_with_its_profile():
  profiles = _profiles()
  matrix = _matrix()

  assert sorted(matrix) == sorted(profiles)
  for path, (rubrics, _) in matrix.items():
    assert rubrics == profiles[path][:2], path


def test_per_test_entries_state_the_case_file_profile():
  profiles = _profiles()
  text = REFERENCE.read_text(encoding="utf-8")
  links = dict(re.findall(r"^\| \[([^\]]+)\]\(([^)]+)\)", text, re.M))
  entries = re.findall(
      r"^### \d+\. ([^\n]+)\n(?:- [^\n]*\n)*?- \*\*Rubric Profile\*\*: ([^\n]+)",
      text, re.M)

  assert sorted(links[title] for title, _ in entries) == sorted(profiles)
  for title, stated in entries:
    expected = ", ".join(
        f"{rubric.replace('-', ' ').title()} ({weight}%)"
        for rubric, weight in profiles[links[title]])
    assert stated == expected, title


def test_used_for_lists_count_the_cases_that_use_each_rubric():
  profiles = _profiles()
  matrix = _matrix()
  per_agent = collections.Counter(agent for _, agent in matrix.values())
  text = REFERENCE.read_text(encoding="utf-8")
  reference = text[text.index("## Rubric Reference"):text.index("## Scoring Scale")]

  for short, rubric in SHORT_NAMES.items():
    heading = re.search(rf"^### \d+\. {short}\w* (Quality|Structure)", reference, re.M)
    block = reference[heading.end():]
    block = block[:block.index("\n### ")] if "\n### " in block else block
    used = collections.Counter(
        matrix[path][1] for path, profile in profiles.items()
        if rubric in (name for name, _ in profile))
    expected = [
        f"- {agent} (all {count} tests)" if count == per_agent[agent]
        else f"- {agent} ({count} of {per_agent[agent]} tests)"
        for agent, count in used.items()]

    listed = re.findall(r"^- [\w-]+ \((?:all \d+|\d+ of \d+) tests\)$", block, re.M)
    if expected:
      assert sorted(listed) == sorted(expected), short
    else:
      assert "**Used For**: No current test case" in block, short
