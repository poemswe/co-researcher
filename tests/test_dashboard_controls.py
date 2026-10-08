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
