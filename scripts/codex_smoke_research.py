#!/usr/bin/env python3
"""Opt-in end-to-end smoke test for the installed Codex research path."""

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import tempfile


QUESTION = "Does structured exercise reduce hospital readmissions?"


def _parser():
  parser = argparse.ArgumentParser(
      description="Run the optional Codex research scaffold smoke test.")
  parser.add_argument(
      "--keep-workdir", action="store_true",
      help="keep the temporary research workspace for debugging")
  return parser


def _project_files(workdir):
  return sorted(workdir.glob("research/*/project.json"))


def main(argv=None):
  args = _parser().parse_args(argv)
  if os.environ.get("CO_RESEARCHER_CODEX_SMOKE") != "1":
    print("skipped: set CO_RESEARCHER_CODEX_SMOKE=1 to run Codex smoke")
    return 0

  codex = shutil.which("codex")
  if codex is None:
    print("Codex smoke failed: codex executable not found")
    return 2

  repo = pathlib.Path(__file__).resolve().parents[1]
  workdir = pathlib.Path(tempfile.mkdtemp(prefix="co-researcher-codex-smoke-"))
  prompt = f"""Use the Co-Researcher repository at {repo}.
Run `.codex/co-researcher-codex bootstrap` and follow the bootstrap rules.
Run a plan-only research smoke test for:
\"{QUESTION}\"
Do not perform live literature retrieval. Initialize the research project
scaffold only. Work in the current temporary directory and do not modify the
repository checkout."""
  try:
    result = subprocess.run(
        [codex, "exec", "-C", str(workdir), "--add-dir", str(repo),
         "--sandbox", "workspace-write", "--ephemeral", prompt],
        capture_output=True, text=True, check=False)
    projects = _project_files(workdir)
    if result.returncode != 0:
      print(f"Codex smoke failed (exit {result.returncode}).")
      if result.stderr.strip():
        print(result.stderr.strip())
      if result.stdout.strip():
        print(result.stdout.strip())
      return 1
    if len(projects) != 1:
      print("Codex smoke failed: expected exactly one research project.json")
      return 1
    project = json.loads(projects[0].read_text(encoding="utf-8"))
    required = {"question", "phase", "next_action", "decisions"}
    if not required <= project.keys():
      missing = ", ".join(sorted(required - project.keys()))
      print(f"Codex smoke failed: project.json missing {missing}")
      return 1
    if project["question"] != QUESTION or not project["decisions"]:
      print("Codex smoke failed: project.json has invalid scaffold state")
      return 1
    print(f"Codex smoke passed: {projects[0]}")
    return 0
  finally:
    if args.keep_workdir:
      print(f"Codex smoke workdir: {workdir}")
    else:
      shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
  raise SystemExit(main())
