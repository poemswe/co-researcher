import json
import pathlib
import re
import subprocess

from test_eval_run_reports import _ScriptCollector


ROOT = pathlib.Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "evals/index.html"


def _main_script(tmp_path):
  collector = _ScriptCollector()
  collector.feed(DASHBOARD.read_text(encoding="utf-8"))
  script = next(s for s in collector.scripts if "GITHUB_RAW_URL" in s)
  path = tmp_path / "dashboard.js"
  path.write_text(script, encoding="utf-8")
  return path


def _node(tmp_path, body):
  driver = r"""
    const fs = require('fs');
    const vm = require('vm');
    const context = {
      window: {addEventListener() {}, location: {search: ''}},
      document: {body: {}, getElementById() { return null; },
                 querySelectorAll() { return []; }},
      URLSearchParams, TextDecoder, console,
    };
    vm.createContext(context);
    vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
  """ + body
  completed = subprocess.run(
      ["node", "-e", driver, str(_main_script(tmp_path))],
      check=False, capture_output=True, text=True)
  assert completed.returncode == 0, completed.stderr + completed.stdout
  return completed.stdout


def test_trend_series_places_each_score_at_its_own_run(tmp_path):
  history = [
      {"model": "codex:a", "timestamp": "2025-12-30T22:18:44Z", "average_score": 83.2},
      {"model": "claude:opus", "timestamp": "2025-12-30T22:16:50Z", "average_score": 85.8},
      {"model": "gemini:b", "timestamp": "2026-01-26T00:30:30Z", "average_score": 93.6},
      {"model": "gemini:b", "timestamp": "2026-01-26T05:10:37Z", "average_score": 92.7},
  ]
  output = _node(tmp_path, f"""
    const result = context.trendSeries({json.dumps(history)});
    console.log(JSON.stringify(result));
  """)

  result = json.loads(output)
  assert result["labels"] == ["2025-12-30", "2025-12-30", "2026-01-26", "2026-01-26"]
  assert {series["model"]: series["data"] for series in result["series"]} == {
      "claude:opus": [85.8, None, None, None],
      "codex:a": [None, 83.2, None, None],
      "gemini:b": [None, None, 93.6, 92.7],
  }


def test_search_matches_names_not_agent_output(tmp_path):
  output = _node(tmp_path, r"""
    const item = (header, tests, output) => ({
      style: {},
      querySelector(sel) { return sel === '.accordion-header' ? {textContent: header} : null; },
      querySelectorAll(sel) {
        return sel === '.test-case-header' ? tests.map(t => ({textContent: t})) : [];
      },
      innerText: header + ' ' + tests.join(' ') + ' ' + output,
    });
    const items = [
      item('critical analysis', ['Fallacy Detection'], 'mentions lateral thinking in passing'),
      item('lateral thinking', ['Analogy Finding'], ''),
      item('peer review', ['Manuscript Critique'], ''),
    ];
    context.document.getElementById = () => ({value: 'lateral'});
    context.document.querySelectorAll = () => items;
    context.filterTests();
    console.log(JSON.stringify(items.map(i => i.style.display)));
    context.document.getElementById = () => ({value: 'analogy'});
    context.filterTests();
    console.log(JSON.stringify(items.map(i => i.style.display)));
  """)

  first, second = (json.loads(line) for line in output.strip().splitlines())
  assert first == ["none", "block", "none"]
  assert second == ["none", "block", "none"]


def test_search_box_reacts_to_pasted_text():
  html = DASHBOARD.read_text(encoding="utf-8")
  search = re.search(r'<input[^>]*id="testSearch"[^>]*>', html, re.S).group(0)
  assert 'oninput="filterTests()"' in search
  assert "onkeyup" not in search


def test_leaderboard_keeps_a_run_note_and_escapes_it(tmp_path):
  runs = [
      {"model": "codex:a", "timestamp": "2025-12-30T22:18:44Z", "average_score": 83.2,
       "tests_passed": 20, "tests_run": 22, "note": "Effort label <unverified>."},
      {"model": "claude:opus", "timestamp": "2025-12-30T22:16:50Z", "average_score": 85.8,
       "tests_passed": 25, "tests_run": 25},
  ]
  output = _node(tmp_path, f"""
    const entries = context.leaderboardEntries({json.dumps(runs)});
    console.log(JSON.stringify(entries));
    console.log(context.leaderboardNoteHtml(entries.find(e => e.model === 'codex:a').note));
    console.log(JSON.stringify(context.leaderboardNoteHtml(undefined)));
  """)

  entries_line, note_html, empty = output.strip().splitlines()
  entries = {e["model"]: e for e in json.loads(entries_line)}
  assert entries["codex:a"]["note"] == "Effort label <unverified>."
  assert entries["claude:opus"]["note"] is None
  assert "&lt;unverified&gt;" in note_html and "<unverified>" not in note_html
  assert json.loads(empty) == ""


def test_releases_sort_newest_first_and_scope_runs_and_models(tmp_path):
  overview = {
      "runs": [
          {"run_id": "a", "model": "claude:opus", "release": "1.0.0"},
          {"run_id": "b", "model": "codex:x", "release": "1.0.0"},
          {"run_id": "c", "model": "gemini:y", "release": "2.0.0"},
          {"run_id": "d", "model": "claude:opus-5-5", "release": "2.7.0"},
          {"run_id": "e", "model": "codex:z low", "release": "2.7.0"},
          {"run_id": "f", "model": "old:model"},
      ],
      "summary_stats": {"models": ["claude:opus", "claude:opus-5-5", "codex:x",
                                   "codex:z low", "gemini:y", "old:model"]},
  }
  output = _node(tmp_path, f"""
    const overview = {json.dumps(overview)};
    console.log(JSON.stringify(context.releaseList(overview.runs)));
    const scoped = context.scopeToRelease(overview, '2.7.0');
    console.log(JSON.stringify([scoped.runs.map(r => r.run_id), scoped.summary_stats.models]));
    console.log(JSON.stringify(overview.runs.length));
    console.log(JSON.stringify(context.scopeToRelease(overview, 'unreleased').runs.map(r => r.run_id)));
  """)

  releases, scoped, untouched, unreleased = (
      json.loads(line) for line in output.strip().splitlines())
  assert releases == ["2.7.0", "2.0.0", "1.0.0", "unreleased"]
  assert scoped == [["d", "e"], ["claude:opus-5-5", "codex:z low"]]
  assert untouched == 6
  assert unreleased == ["f"]


def _adversarial(family, metrics, assessable=True, reason=None):
  return {"attack_family": family, "assessable": assessable,
          "unassessable_reason": reason,
          "reason_metrics": {code: {"true_positive": tp, "false_positive": fp,
                                    "false_negative": fn}
                             for code, (tp, fp, fn) in metrics.items()}}


def test_detection_rows_show_caught_missed_and_controls(tmp_path):
  report = {"cases": [
      {"case_id": "integrity-case-001", "attack_family": "unicode-substitution",
       "first_pass": {"status": "invalid"}, "final": {"status": "valid"},
       "adversarial_score": _adversarial("unicode-substitution", {
           "fabricated_quote": (1, 0, 0), "coverage_claim_missing": (0, 1, 0)})},
      {"case_id": "integrity-case-014", "attack_family": "overstated-finding",
       "first_pass": {"status": "valid"}, "final": {"status": "valid"},
       "adversarial_score": _adversarial("overstated-finding", {
           "coverage_claim_missing": (0, 0, 1)})},
      {"case_id": "integrity-case-010", "attack_family": "missing-artifact",
       "first_pass": None, "final": None,
       "adversarial_score": _adversarial("missing-artifact", {
           "artifact_missing": (0, 0, 1)}, False, "first_pass_unloadable")},
      {"case_id": "synthetic-valid", "first_pass": {"status": "valid_with_warnings"},
       "final": {"status": "valid_with_warnings"}},
  ]}
  output = _node(tmp_path, f"""
    console.log(JSON.stringify(context.integrityDetectionRows({json.dumps(report)})));
  """)

  rows = json.loads(output)
  assert rows == [
      {"case_id": "integrity-case-001", "family": "unicode-substitution",
       "expected": ["fabricated_quote"], "outcome": "caught",
       "follow_on": ["coverage_claim_missing"], "unassessable_reason": None,
       "first_pass": "invalid", "final": "valid"},
      {"case_id": "integrity-case-014", "family": "overstated-finding",
       "expected": ["coverage_claim_missing"], "outcome": "missed",
       "follow_on": [], "unassessable_reason": None,
       "first_pass": "valid", "final": "valid"},
      {"case_id": "integrity-case-010", "family": "missing-artifact",
       "expected": ["artifact_missing"], "outcome": "not_assessable",
       "follow_on": [], "unassessable_reason": "first_pass_unloadable",
       "first_pass": None, "final": None},
      {"case_id": "synthetic-valid", "family": None, "expected": [],
       "outcome": "control", "follow_on": [], "unassessable_reason": None,
       "first_pass": "valid_with_warnings", "final": "valid_with_warnings"},
  ]


def test_detection_table_escapes_and_labels_outcomes(tmp_path):
  rows = [
      {"case_id": "c<1>", "family": "f", "expected": ["fabricated_quote"],
       "outcome": "missed", "follow_on": [], "unassessable_reason": None,
       "first_pass": "valid", "final": "valid"},
      {"case_id": "ctl", "family": None, "expected": [], "outcome": "control",
       "follow_on": [], "unassessable_reason": None,
       "first_pass": "invalid", "final": "valid"},
  ]
  output = _node(tmp_path, f"""
    console.log(context.integrityDetectionTableHtml({json.dumps(rows)}));
  """)

  assert "c&lt;1&gt;" in output and "c<1>" not in output
  assert "Missed" in output and "Control" in output
  assert "1 of 1 assessable attacks caught" not in output
  assert "0 of 1 assessable attacks caught" in output
