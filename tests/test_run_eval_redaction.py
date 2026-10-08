import json
import pathlib
import sys
import tempfile
import types


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))

import run_eval  # noqa: E402


def _report(output):
  test_case = types.SimpleNamespace(
      agent="literature-review", implementation_skill="literature-review",
      name="Gap Analysis", file_path=None)
  return types.SimpleNamespace(
      test_case=test_case, overall_score=88.0, passed=True,
      rubric_breakdown={"research-quality": {"weight": 70, "score": 90}},
      agent_output=output, judge_output=f"REASONING: saw {output}",
      must_include_met=[], must_include_missed=[],
      execution_metadata={"cwd": str(ROOT)})


def test_redact_local_paths_replaces_repo_temp_and_home_recursively():
  home = pathlib.Path.home()
  temp = pathlib.Path(tempfile.gettempdir()).resolve()
  value = {
      "paths": [f"{ROOT}/review/x/protocol.md", f"{temp}/run-1/claims.json",
                f"{home}/Desktop/notes.md"],
      "nested": {"text": "no local path here"},
      "score": 88.0,
  }

  assert run_eval.redact_local_paths(value) == {
      "paths": ["<repo>/review/x/protocol.md", "<tmp>/run-1/claims.json",
                "~/Desktop/notes.md"],
      "nested": {"text": "no local path here"},
      "score": 88.0,
  }


def test_saved_benchmark_detail_contains_no_local_paths(tmp_path, monkeypatch):
  monkeypatch.setattr(run_eval, "EVALS_DIR", tmp_path)
  output = f"See [protocol.md]({ROOT}/review/gap/protocol.md) in {pathlib.Path.home()}."

  run_eval.save_benchmark_v2([_report(output)], "claude:opus", "run_20261008_000000")

  detail = (tmp_path / "test_results_detail/run_20261008_000000.json").read_text()
  assert str(pathlib.Path.home()) not in detail
  saved = json.loads(detail)["test_results"][0]
  assert saved["agent_output"] == "See [protocol.md](<repo>/review/gap/protocol.md) in ~."
  assert saved["execution_metadata"] == {"cwd": "<repo>"}


def test_model_version_is_never_invented_for_an_unversioned_model():
  assert run_eval.extract_model_version("claude") == "cli-default"
  assert run_eval.extract_model_version("codex") == "cli-default"
  assert run_eval.extract_model_version("claude:claude-opus-5-5") == "claude-opus-5-5"
  assert run_eval.extract_model_version("codex:gpt-5.2 xhigh") == "gpt-5.2 xhigh"


def test_codex_reasoning_effort_uses_the_codex_config_key(monkeypatch):
  from lib import core
  seen = {}

  def fake_run(cmd, **kwargs):
    seen["cmd"] = cmd
    return types.SimpleNamespace(returncode=0, stdout="ok", stderr="")

  monkeypatch.setattr(core, "find_cli", lambda provider: pathlib.Path("/bin/" + provider))
  monkeypatch.setattr(core.subprocess, "run", fake_run)
  core.run_cli("codex:gpt-6-astra xhigh", "prompt")

  cmd = seen["cmd"]
  assert cmd[cmd.index("--model") + 1] == "gpt-6-astra"
  assert cmd[cmd.index("-c") + 1] == 'model_reasoning_effort="xhigh"'
