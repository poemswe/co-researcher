# Research Smoke Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a required offline research smoke test and an opt-in Codex CLI smoke test from `docs/superpowers/specs/2026-07-17-research-smoke-tests-design.md`.

**Architecture:** Keep smoke tests separate from scored evals. `tests/test_research_smoke.py` proves the local evidence scripts and research scaffold contract with a fixture workspace. `scripts/codex_smoke_research.py` proves the installed Codex path only when a developer explicitly enables it.

**Tech Stack:** Python 3.10+ stdlib, pytest, existing `skills/literature-review/scripts/*.py` CLIs, Codex CLI for the optional smoke. Run tests with `uv run pytest`.

---

## File Map

- Create `tests/test_research_smoke.py`: required offline smoke plus default-skip coverage for the optional Codex smoke script.
- Create `scripts/codex_smoke_research.py`: opt-in Codex CLI integration smoke.
- Modify `README.md`: document the two smoke-test commands and their reliability split.
- Do not modify `evals/`: scored model-quality evals stay separate.
- Do not modify `.github/workflows/tests.yml` unless the current branch already intends to add it. A new `tests/test_research_smoke.py` file is discovered by the existing `python -m pytest -q` workflow.

## Global Constraints

- Keep the deterministic smoke offline: no OpenAlex, Europe PMC, Crossref, arXiv, Codex, or model call.
- Stage only the files named in each task. The worktree may contain unrelated user edits.
- Use subprocesses for the script smoke so CLI argument parsing and exit codes are covered.
- Keep the optional Codex smoke skipped by default with exit `0`.
- The optional smoke may depend on local Codex auth only when `CO_RESEARCHER_CODEX_SMOKE=1`.

---

### Task 1: Add the Required Offline Research Smoke

**Files:**
- Create: `tests/test_research_smoke.py`

- [ ] **Step 1: Write the offline smoke tests**

Create `tests/test_research_smoke.py` with this content:

```python
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pytest",
# ]
# ///

import json
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "literature-review" / "scripts"


def _write_json(path: pathlib.Path, payload) -> pathlib.Path:
  path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
  return path


def _run_script(name: str, *args: str) -> subprocess.CompletedProcess:
  return subprocess.run(
      [sys.executable, str(SCRIPTS / name), *args],
      cwd=ROOT,
      capture_output=True,
      text=True,
      check=False)


def test_research_evidence_gates_accept_minimal_fixture(tmp_path):
  workspace = tmp_path / "review" / "exercise-readmissions"
  paper_dir = workspace / "papers" / "p1"
  paper_dir.mkdir(parents=True)
  paper_dir.joinpath("fulltext.md").write_text(
      "Structured Exercise and Hospital Readmission\n\n"
      "We enrolled 814 adult patients across 12 regional hospitals. "
      "Thirty-day readmissions fell 18% in the treatment arm relative to "
      "usual care, a difference that persisted after adjustment.",
      encoding="utf-8")

  _write_json(workspace / "corpus.json", [
      {
          "key": "p1",
          "ids": {"doi": "10.1000/smoke"},
          "title": "Structured Exercise and Hospital Readmission",
          "year": 2022,
          "authors": ["Anita Patel"],
          "found_via": "fixture",
          "screening": {
              "status": "included",
              "stage": "full_text",
              "reason": None,
          },
          "fulltext": "fulltext",
          "role": "evidence",
      },
      {
          "key": "excluded",
          "ids": {"doi": "10.1000/excluded"},
          "title": "Excluded Fixture Record",
          "year": 2021,
          "authors": ["Blake Chen"],
          "found_via": "fixture",
          "screening": {
              "status": "excluded",
              "stage": "title",
              "reason": "wrong population",
          },
          "fulltext": None,
          "role": None,
      },
  ])
  _write_json(workspace / "claims.json", [{
      "claim": "Structured exercise reduced thirty-day readmissions by 18%.",
      "paper_id": "p1",
      "citation": "Patel, 2022",
      "supporting_quote": (
          "Thirty-day readmissions fell 18% in the treatment arm relative "
          "to usual care, a difference that persisted after adjustment."),
  }])
  (workspace / "synthesis.md").write_text(
      "Structured exercise reduced thirty-day readmissions by 18% "
      "(Patel, 2022).",
      encoding="utf-8")

  claims = _run_script(
      "check_claims.py",
      "--claims", str(workspace / "claims.json"),
      "--workspace", str(workspace),
      "--synthesis", str(workspace / "synthesis.md"))
  assert claims.returncode == 0, claims.stderr + claims.stdout
  claim_report = json.loads(claims.stdout)
  assert claim_report["verified"] == 1
  assert claim_report["uncovered_claim"] == 0
  assert claim_report["results"][0]["status"] == "verified"

  prisma = _run_script(
      "prisma_counts.py",
      "--corpus", str(workspace / "corpus.json"))
  assert prisma.returncode == 0, prisma.stderr + prisma.stdout
  prisma_report = json.loads(prisma.stdout)
  assert prisma_report["after_dedup"] == 2
  assert prisma_report["included"] == 1
  assert prisma_report["in_synthesis"] == 1


def test_research_project_scaffold_is_parseable(tmp_path):
  slug = "structured-exercise-readmissions"
  project_dir = tmp_path / "research" / slug
  project_dir.mkdir(parents=True)
  _write_json(project_dir / "project.json", {
      "question": "Does structured exercise reduce hospital readmissions?",
      "methodology": "plan-only smoke",
      "phase": "scoping",
      "workspaces": {"review": f"review/{slug}/"},
      "decisions": [{
          "date": "2026-07-17",
          "decision": "Initialize smoke-test scaffold.",
          "why": "Exercise the research-manager persistence contract.",
      }],
      "next_action": "Review the scaffolded task list.",
  })
  (project_dir / "research-tasks.md").write_text(
      "- [ ] Search strategy\n"
      "- [ ] Screening\n"
      "- [ ] Synthesis\n",
      encoding="utf-8")

  project = json.loads((project_dir / "project.json").read_text(
      encoding="utf-8"))
  assert project["question"]
  assert project["phase"] == "scoping"
  assert project["decisions"]
  assert project["next_action"]
  assert "- [ ]" in (project_dir / "research-tasks.md").read_text(
      encoding="utf-8")
```

- [ ] **Step 2: Run the new deterministic smoke**

Run:

```bash
uv run pytest tests/test_research_smoke.py -q
```

Expected:

```text
..                                                                       [100%]
2 passed
```

If `check_claims.py` exits nonzero because the fixture no longer matches its citation contract, fix the fixture data, not the production script.

- [ ] **Step 3: Commit**

```bash
git add tests/test_research_smoke.py
git commit -m "test: add offline research smoke"
```

---

### Task 2: Pin the Optional Codex Smoke Default-Skip Behavior

**Files:**
- Modify: `tests/test_research_smoke.py`
- Create later: `scripts/codex_smoke_research.py`

- [ ] **Step 1: Add the failing test**

Append this test to `tests/test_research_smoke.py`:

```python
def test_codex_smoke_script_skips_by_default(monkeypatch):
  monkeypatch.delenv("CO_RESEARCHER_CODEX_SMOKE", raising=False)
  result = subprocess.run(
      [sys.executable, str(ROOT / "scripts" / "codex_smoke_research.py")],
      cwd=ROOT,
      capture_output=True,
      text=True,
      check=False)
  assert result.returncode == 0
  assert "skipped" in result.stdout.lower()
  assert "CO_RESEARCHER_CODEX_SMOKE=1" in result.stdout
```

- [ ] **Step 2: Run the new test to verify it fails**

Run:

```bash
uv run pytest tests/test_research_smoke.py::test_codex_smoke_script_skips_by_default -q
```

Expected: FAIL because `scripts/codex_smoke_research.py` does not exist.

- [ ] **Step 3: Do not commit yet**

Leave the failing test unstaged until Task 3 implements the script.

---

### Task 3: Add the Optional Codex Smoke Script

**Files:**
- Create: `scripts/codex_smoke_research.py`
- Modify: `tests/test_research_smoke.py`

- [ ] **Step 1: Create the script**

Create `scripts/codex_smoke_research.py` with this content:

```python
#!/usr/bin/env python3
"""Optional end-to-end smoke for the Co-Researcher Codex path."""

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile


PROMPT = """Use the Co-Researcher repository at {repo_path}.
Run `.codex/co-researcher-codex bootstrap` and follow the bootstrap rules.

Run a plan-only research smoke test for:
"Does structured exercise reduce hospital readmissions?"

Do not perform live literature retrieval. Initialize the research project
scaffold only. Write `research/structured-exercise-readmissions/project.json`
and `research/structured-exercise-readmissions/research-tasks.md` in the
current working directory. The project JSON must include `question`, `phase`,
`next_action`, and `decisions`.
"""


def _project_jsons(workdir: pathlib.Path) -> list[pathlib.Path]:
  research_dir = workdir / "research"
  if not research_dir.exists():
    return []
  return sorted(research_dir.glob("*/project.json"))


def _valid_project(path: pathlib.Path) -> tuple[bool, str]:
  try:
    data = json.loads(path.read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError) as err:
    return False, f"cannot read project JSON: {err}"
  for field in ("question", "phase", "next_action", "decisions"):
    if field not in data:
      return False, f"missing {field!r}"
  if not isinstance(data["decisions"], list):
    return False, "'decisions' must be a list"
  tasks = path.with_name("research-tasks.md")
  if not tasks.exists():
    return False, "missing research-tasks.md"
  return True, ""


def _run_codex(codex: str, workdir: pathlib.Path, repo: pathlib.Path,
               timeout: int, model: str | None) -> subprocess.CompletedProcess:
  output_file = workdir / "codex-last-message.txt"
  cmd = [
      codex,
      "exec",
      "--cd", str(workdir),
      "--add-dir", str(repo),
      "--sandbox", "workspace-write",
      "--ask-for-approval", "never",
      "--skip-git-repo-check",
      "--output-last-message", str(output_file),
  ]
  if model:
    cmd.extend(["--model", model])
  cmd.append("-")
  return subprocess.run(
      cmd,
      input=PROMPT.format(repo_path=repo),
      capture_output=True,
      text=True,
      timeout=timeout,
      check=False)


def _execute(args) -> int:
  if os.environ.get("CO_RESEARCHER_CODEX_SMOKE") != "1":
    print("skipped: set CO_RESEARCHER_CODEX_SMOKE=1 to run Codex smoke")
    return 0

  codex = shutil.which("codex")
  if codex is None:
    print("ERROR: codex CLI not found on PATH", file=sys.stderr)
    return 1

  repo = pathlib.Path(__file__).resolve().parent.parent
  workdir = pathlib.Path(tempfile.mkdtemp(prefix="co-researcher-codex-smoke-"))
  try:
    result = _run_codex(codex, workdir, repo, args.timeout, args.model)
    if result.returncode != 0:
      print(f"ERROR: Codex exited {result.returncode}", file=sys.stderr)
      print(result.stderr, file=sys.stderr)
      print(result.stdout)
      print(f"workdir: {workdir}")
      return result.returncode

    for project_json in _project_jsons(workdir):
      valid, error = _valid_project(project_json)
      if valid:
        print(f"Codex smoke passed: {project_json}")
        return 0
      print(f"invalid project at {project_json}: {error}", file=sys.stderr)

    print("ERROR: Codex did not create research/<slug>/project.json",
          file=sys.stderr)
    print(result.stderr, file=sys.stderr)
    print(result.stdout)
    print(f"workdir: {workdir}")
    return 1
  finally:
    if args.keep_workdir:
      print(f"kept workdir: {workdir}")
    else:
      shutil.rmtree(workdir, ignore_errors=True)


def main(argv=None) -> int:
  parser = argparse.ArgumentParser(
      description="Run the optional Co-Researcher Codex smoke test.")
  parser.add_argument("--keep-workdir", action="store_true",
                      help="Keep the temporary Codex workdir for debugging.")
  parser.add_argument("--timeout", type=int, default=600,
                      help="Codex subprocess timeout in seconds.")
  parser.add_argument("--model",
                      help="Optional Codex model override.")
  return _execute(parser.parse_args(argv))


if __name__ == "__main__":
  sys.exit(main())
```

- [ ] **Step 2: Run the default-skip test**

Run:

```bash
uv run pytest tests/test_research_smoke.py::test_codex_smoke_script_skips_by_default -q
```

Expected:

```text
.                                                                        [100%]
1 passed
```

- [ ] **Step 3: Run the full smoke test file**

Run:

```bash
uv run pytest tests/test_research_smoke.py -q
```

Expected:

```text
...                                                                      [100%]
3 passed
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_research_smoke.py scripts/codex_smoke_research.py
git commit -m "test: add optional Codex research smoke"
```

---

### Task 4: Document Smoke Commands

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a smoke-test section**

In `README.md`, after the Evaluation Framework quick-start command block and before `### Features`, add:

````markdown
### Smoke Tests

Run the offline research smoke before merging changes that touch research workflow, evidence gates, or Codex setup:

```bash
uv run pytest tests/test_research_smoke.py
```

The offline smoke uses fixture data only. It does not call scholarly APIs, Codex, or a model.

Run the real Codex smoke only from a machine with an authenticated Codex CLI:

```bash
CO_RESEARCHER_CODEX_SMOKE=1 uv run scripts/codex_smoke_research.py
```

The Codex smoke initializes a plan-only research workspace in a temporary directory and verifies `research/<slug>/project.json`. It is opt-in because it shells out to Codex and may take longer than unit tests.
````

When editing Markdown, keep the nested code fences valid.

- [ ] **Step 2: Run the documented deterministic command**

Run:

```bash
uv run pytest tests/test_research_smoke.py -q
```

Expected: 3 passed.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document research smoke tests"
```

---

### Task 5: Final Verification

**Files:**
- Verify only unless a preceding task exposed a real bug.

- [ ] **Step 1: Run the focused smoke and related evidence tests**

Run:

```bash
uv run pytest tests/test_research_smoke.py tests/test_check_claims.py tests/test_prisma_counts.py -q
```

Expected: exit code `0`, with no `FAILED` or `ERROR` summary lines.

- [ ] **Step 2: Run the optional smoke skip path as a command**

Run:

```bash
uv run scripts/codex_smoke_research.py
```

Expected stdout contains:

```text
skipped: set CO_RESEARCHER_CODEX_SMOKE=1 to run Codex smoke
```

Expected exit code: `0`.

- [ ] **Step 3: Check the staged/untracked state before any final commit**

Run:

```bash
git status --short
```

Expected: only intentional files from Tasks 1-4 should be modified by this work. Existing unrelated files may still appear; do not stage or revert them.

- [ ] **Step 4: Optional manual Codex smoke**

Run only when the developer has local Codex auth and wants the real integration check:

```bash
CO_RESEARCHER_CODEX_SMOKE=1 uv run scripts/codex_smoke_research.py --keep-workdir
```

Expected: the command exits `0` and prints `Codex smoke passed: .../research/<slug>/project.json`.

If it fails because Codex auth is missing, report that as an environment limitation. Do not weaken the deterministic smoke to compensate.
