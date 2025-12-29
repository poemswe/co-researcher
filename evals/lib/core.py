import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class TestCase:
    name: str
    agent: str
    difficulty: str
    focus: str
    task_prompt: str
    must_include: list[str] = field(default_factory=list)
    should_include: list[str] = field(default_factory=list)
    should_not_include: list[str] = field(default_factory=list)
    passing_threshold: int = 70
    rubric_weights: dict[str, int] = field(default_factory=dict)
    file_path: Optional[Path] = None
    timeout: Optional[int] = None  # Per-test timeout override


@dataclass(slots=True)
class AgentResult:
    success: bool
    output: str
    duration_seconds: float
    error: Optional[str] = None


@dataclass(slots=True)
class EvaluationReport:
    test_case: TestCase
    agent_result: AgentResult
    research_quality: int = 0
    reasoning_quality: int = 0
    output_structure: int = 0
    overall_score: float = 0.0
    passed: bool = False
    judge_output: str = ""
    must_include_met: list[str] = field(default_factory=list)
    must_include_missed: list[str] = field(default_factory=list)
    report_path: Optional[Path] = None


EVALS_DIR = Path(__file__).parent.parent
DEFAULT_WEIGHTS = {"research_quality": 33, "reasoning_quality": 34, "output_structure": 33}

CLI_CONFIG = {
    "claude": {
        "base": ["--print", "--verbose"],
        "tools": ["--tools", "WebSearch,WebFetch,Read"],
        "prompt_style": "flag",
    },
    "gemini": {
        "base": [],
        "tools": ["--yolo"],
        "prompt_style": "positional",
    },
    "codex": {
        "base": ["exec", "--full-auto"],
        "tools": [],
        "prompt_style": "positional",
    },
}


@cache
def load_file(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def load_template(name: str) -> str:
    return strip_frontmatter(load_file(EVALS_DIR / "prompts" / f"{name}.md"))


def strip_frontmatter(content: str) -> str:
    return content.split("---", 2)[2].strip() if content.count("---") >= 2 else content


def rx(pattern: str, text: str, default="", flags=0) -> str:
    return m.group(1).strip() if (m := re.search(pattern, text, flags)) else default


def rx_int(pattern: str, text: str, default=0) -> int:
    return int(m.group(1)) if (m := re.search(pattern, text)) else default


def rx_list(pattern: str, text: str) -> list[str]:
    return [x.strip() for x in m.group(1).split(",") if x.strip()] if (m := re.search(pattern, text)) and m.group(1).lower() != "none" else []


def checklist(content: str, section: str) -> list[str]:
    if not (m := re.search(rf"###\s*{section}\s*\n(.*?)(?=\n###|\n##|\Z)", content, re.DOTALL)):
        return []
    return [m.group(1).strip() for line in m.group(1).split("\n") if (m := re.search(r"-\s*\[.\]\s*(.+)", line))]


def parse_test_case(path: Path) -> TestCase:
    c = path.read_text()
    
    # Parse task_prompt (renamed to content in the diff, but keeping original name for now)
    task_prompt = rx(r"## Task Prompt\s*```([^`]+)```", c, flags=re.DOTALL) or rx(r"## Task Prompt\s*\n(.+?)(?=\n##)", c, flags=re.DOTALL)
    
    # Parse rubric weights
    weights = {m.group(1).lower().replace(" ", "_"): int(m.group(2)) for m in re.finditer(r"(\w+ Quality):\s*(\d+)%", c)}
    if not weights: # Try new format from diff
        weights = {k.lower().replace(" ", "_"): v for k, v in (
            (m.group(1), int(m.group(2))) for m in re.finditer(r"-\s*([^:]+):\s*(\d+)%", rx(r"## Rubric Weights\s*\n(.*?)(?=\n##|\Z)", c, re.DOTALL))
        )} if rx(r"## Rubric Weights", c) else DEFAULT_WEIGHTS.copy()
    
    # Parse per-test timeout if specified
    timeout_override = rx_int(r"-\s*\*\*Timeout\*\*:\s*(\d+)", c) or None

    return TestCase(
        name=rx(r"#\s*Test Case:\s*(.+)", c, path.stem),
        agent=rx(r"Agent[*`]*:\s*[*`]*([\w-]+)[*`]*", c, "unknown"),
        difficulty=rx(r"Difficulty[*`]*:\s*[*`]*(\w+)[*`]*", c, "Medium"),
        focus=rx(r"Focus[*`]*:\s*[*`]*(.*?)[*`]*(?:\n|$)", c),
        task_prompt=task_prompt or rx(r"##\s*Task Prompt\s*\n+```\n?(.*?)```", c, flags=re.DOTALL),
        must_include=checklist(c, "Must Include") or checklist(c, "Must Identify"),
        should_include=checklist(c, "Should Include"),
        should_not_include=checklist(c, "Should Not Include"),
        passing_threshold=rx_int(r"Overall Score:\s*[≥>=]+\s*(\d+)", c, 70),
        rubric_weights=weights or DEFAULT_WEIGHTS.copy(),
        file_path=path,
        timeout=timeout_override,
    )


def discover_tests(test_dir: Path, agent: Optional[str] = None, test: Optional[str] = None) -> list[TestCase]:
    tests = []
    for d in sorted(test_dir.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or (agent and d.name != agent):
            continue
        for f in sorted(d.glob("test-*.md")):
            if test and f.stem.replace("test-", "") != test:
                continue
            try:
                tests.append(parse_test_case(f))
            except Exception as e:
                print(f"Warning: {f}: {e}", file=sys.stderr)
    return tests


def find_cli(provider: str) -> Optional[str]:
    if shutil.which(provider):
        return provider
    home = Path.home()
    paths = {
        "claude": [".claude/local/claude", ".local/bin/claude", "/usr/local/bin/claude"],
        "gemini": ["/usr/local/bin/gemini", ".local/bin/gemini"],
        "codex": [".codex/bin/codex", ".local/bin/codex", "/usr/local/bin/codex"],
    }
    for p in paths.get(provider, []):
        path = home / p if not p.startswith("/") else Path(p)
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
    return None


def run_cli(model: str, prompt: str, timeout: int = 600, cwd: Optional[str] = None) -> tuple[bool, str, str]:
    provider, version = (model.split(":", 1) + [None])[:2]
    provider = provider.lower()
    
    if not (cli := find_cli(provider)):
        return False, "", f"{model} CLI not found"
    
    config = CLI_CONFIG.get(provider, {"base": [], "tools": [], "prompt_style": "flag"})
    cmd = [cli, *config["base"]]
    if version:
        cmd += ["--model", version]
    cmd += config["tools"]
    
    stdin_input = None
    if config["prompt_style"] == "positional":
        stdin_input = prompt
    else:
        cmd += ["-p", prompt]
    
    try:
        r = subprocess.run(cmd, input=stdin_input, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return (r.returncode == 0, r.stdout, r.stderr or f"Exit {r.returncode}")
    except subprocess.TimeoutExpired:
        return False, "", f"Timeout {timeout}s"
    except Exception as e:
        return False, "", str(e)


def execute_agent(agent_name: str, prompt: str, timeout: int = 600, model: str = "claude", eval_mode: bool = True) -> AgentResult:
    start = time.time()
    methodology = strip_frontmatter(load_file(EVALS_DIR.parent / "agents" / f"{agent_name}.md"))
    
    # In eval mode, add conciseness instruction
    if eval_mode and methodology:
        methodology = f"{methodology}\n\n**EVAL MODE**: Provide focused, concise output. Prioritize core analysis over exhaustive detail."
    
    tmpl = "agent_prompt" if methodology else "agent_prompt_fallback"
    full_prompt = load_template(tmpl).replace("{agent_name}", agent_name).replace("{methodology}", methodology).replace("{prompt}", prompt)
    
    ok, out, err = run_cli(model, full_prompt, timeout)
    return AgentResult(ok, out, time.time() - start, err or None)


def evaluate_output(tc: TestCase, output: str, timeout: int = 600, model: str = "claude") -> EvaluationReport:
    rpt = EvaluationReport(tc, AgentResult(True, output, 0))
    
    rubrics = "\n".join(f"\n--- {f.stem} ---\n{f.read_text()}" for f in (tc.file_path.parent.parent / "rubrics").glob("*.md")) if tc.file_path else ""
    
    prompt = load_template("judge_prompt").format(
        agent=tc.agent, task_prompt=tc.task_prompt,
        must_include="\n".join(f"- {i}" for i in tc.must_include),
        should_include="\n".join(f"- {i}" for i in tc.should_include),
        should_not_include="\n".join(f"- {i}" for i in tc.should_not_include),
        rubric_weights=tc.rubric_weights, rubrics_text=rubrics,
        agent_output=output, passing_threshold=tc.passing_threshold,
    )
    
    ok, out, err = run_cli(model, prompt, timeout)
    if not ok:
        rpt.judge_output = f"Judge error: {err}"
        return rpt
    
    rpt.judge_output = out
    rpt.research_quality = rx_int(r"RESEARCH_QUALITY[*`]*\s*[:=]\s*(\d+)", out)
    rpt.reasoning_quality = rx_int(r"REASONING_QUALITY[*`]*\s*[:=]\s*(\d+)", out)
    rpt.output_structure = rx_int(r"OUTPUT_STRUCTURE[*`]*\s*[:=]\s*(\d+)", out)
    
    if m := re.search(r"OVERALL_SCORE[*`]*\s*[:=]\s*([\d.]+)", out):
        rpt.overall_score = float(m.group(1))
    else:
        w = tc.rubric_weights
        rpt.overall_score = (rpt.research_quality * w.get("research_quality", 33) + rpt.reasoning_quality * w.get("reasoning_quality", 34) + rpt.output_structure * w.get("output_structure", 33)) / 100
    
    rpt.must_include_met = rx_list(r"MUST_INCLUDE_MET:\s*(.+?)(?=\n|$)", out)
    rpt.must_include_missed = rx_list(r"MUST_INCLUDE_MISSED:\s*(.+?)(?=\n|$)", out)
    rpt.passed = m.group(1).upper() == "PASS" if (m := re.search(r"RESULT:\s*(PASS|FAIL)", out, re.I)) else rpt.overall_score >= tc.passing_threshold
    return rpt


def generate_report(rpt: EvaluationReport, out_dir: Path, model: str = "claude") -> Path:
    tc, ar, w = rpt.test_case, rpt.agent_result, rpt.test_case.rubric_weights
    name = tc.file_path.stem.replace("test-", "") if tc.file_path else tc.name
    model_slug = model.split(":")[0].lower()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Flat naming: {model}_{agent}_{test}.md
    filename = f"{model_slug}_{tc.agent}_{name}.md"
    
    # Write to latest/ (overwrite)
    latest_dir = out_dir / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    latest_path = latest_dir / filename
    
    # Also archive to history/ with timestamp
    history_dir = out_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    history_filename = f"{timestamp}_{filename}"
    history_path = history_dir / history_filename
    
    rpt.report_path = latest_path
    
    content = f"""# Evaluation Report: {tc.name}

**Date**: {datetime.now():%Y-%m-%d %H:%M:%S}  **Model**: {model}  **Agent**: {tc.agent}
**Test**: {name}  **Difficulty**: {tc.difficulty}  **Status**: {"ERROR ⚠" if not ar.success else "PASS ✓" if rpt.passed else "FAIL ✗"}

## Scores
| Dimension | Score | Weight |
|-----------|-------|--------|
| Research | {rpt.research_quality}/100 | {w.get("research_quality", 33)}% |
| Reasoning | {rpt.reasoning_quality}/100 | {w.get("reasoning_quality", 34)}% |
| Structure | {rpt.output_structure}/100 | {w.get("output_structure", 33)}% |
| **Overall** | **{rpt.overall_score:.1f}/100** | |

## Must-Include
**Met**: {", ".join(rpt.must_include_met) or "None"}  **Missed**: {", ".join(rpt.must_include_missed) or "None"}

## Execution
**Duration**: {ar.duration_seconds:.1f}s  **Success**: {"Yes" if ar.success else "No"}{f"  **Error**: {ar.error}" if ar.error else ""}

## Output
```
{ar.output}
```

## Judge
{rpt.judge_output}
"""

    # Write to both locations
    latest_path.write_text(content)
    history_path.write_text(content)
    
    return latest_path


def generate_summary(reports: list[EvaluationReport], out_dir: Path, model: str = "claude") -> Path:
    n = len(reports)
    ok = sum(r.passed and r.agent_result.success for r in reports)
    fail = sum(not r.passed and r.agent_result.success for r in reports)
    err = sum(not r.agent_result.success for r in reports)
    avg = sum(r.overall_score for r in reports if r.agent_result.success) / max(1, n - err)
    
    agents: dict = {}
    for r in reports:
        a = agents.setdefault(r.test_case.agent, {"n": 0, "ok": 0, "fail": 0, "err": 0, "scores": []})
        a["n"] += 1
        a["err" if not r.agent_result.success else "ok" if r.passed else "fail"] += 1
        if r.agent_result.success:
            a["scores"].append(r.overall_score)
    
    # Write to latest/
    latest_dir = out_dir / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    path = latest_dir / "index.md"
    path.write_text(f"""# Evaluation Report
**Date**: {datetime.now():%Y-%m-%d %H:%M:%S}  **Tests**: {n}  **Model**: {model}

| Status | Count | % |
|--------|-------|---|
| PASS | {ok} | {ok/n*100:.0f}% |
| FAIL | {fail} | {fail/n*100:.0f}% |
| ERROR | {err} | {err/n*100:.0f}% |

**Avg**: {avg:.0f}/100

## Agents
| Agent | Tests | Pass | Fail | Err | Avg |
|-------|-------|------|------|-----|-----|
{"".join(f"| {a} | {s['n']} | {s['ok']} | {s['fail']} | {s['err']} | {sum(s['scores'])/len(s['scores']) if s['scores'] else 0:.0f} |" + chr(10) for a, s in sorted(agents.items()))}
## Results
| Agent | Test | Score | Status |
|-------|------|-------|--------|
{"".join(f"| {r.test_case.agent} | {r.test_case.file_path.stem if r.test_case.file_path else r.test_case.name} | {'-' if not r.agent_result.success else f'{r.overall_score:.0f}'} | {'ERR' if not r.agent_result.success else 'PASS' if r.passed else 'FAIL'} |" + chr(10) for r in reports)}
## Details
{"".join(f"- [{r.test_case.agent}/{r.test_case.file_path.stem if r.test_case.file_path else r.test_case.name}]({r.report_path.name})" + chr(10) for r in reports if r.report_path)}
""")
    return path
