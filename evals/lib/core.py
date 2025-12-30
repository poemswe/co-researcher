import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache
from pathlib import Path

EVALS_DIR = Path(__file__).parent.parent
CLI_CONFIG = {
    "claude": {"base": ["--print", "--verbose"], "tools": ["--tools", "WebSearch,WebFetch,Read"]},
    "gemini": {"base": [], "tools": ["--yolo"], "stdin": True},
    "codex": {"base": ["exec", "--full-auto"], "tools": [], "stdin": True},
}


@dataclass(slots=True)
class TestCase:
    name: str
    agent: str
    task_prompt: str
    rubric_profile: dict
    must_include: list[str] = field(default_factory=list)
    file_path: Path | None = None
    timeout: int = 600


@dataclass(slots=True)
class AgentResult:
    success: bool
    output: str
    duration: float
    error: str | None = None


@dataclass(slots=True)
class EvaluationReport:
    test_case: TestCase
    agent_result: AgentResult
    scores: dict[str, int] = field(default_factory=dict)
    overall_score: float = 0.0
    passed: bool = False
    must_include_met: list[str] = field(default_factory=list)
    must_include_missed: list[str] = field(default_factory=list)
    judge_output: str = ""
    report_path: Path | None = None


@cache
def load_template(name: str) -> str:
    return (EVALS_DIR / "prompts" / f"{name}.md").read_text()


def rx(pattern: str, text: str, default="") -> str:
    return m.group(1).strip() if (m := re.search(pattern, text, re.DOTALL)) else default


def rx_int(pattern: str, text: str, default=0) -> int:
    return int(m.group(1)) if (m := re.search(pattern, text)) else default


def rx_list(pattern: str, text: str) -> list[str]:
    if not (m := re.search(pattern, text)):
        return []
    return [x.strip() for x in m.group(1).split(",") if x.strip() and x.lower() != "none"]


def parse_test_case(path: Path) -> TestCase:
    content = path.read_text()
    
    rubric_profile = {}
    if section := rx(r"## Rubric Profile\s*\n(.*?)(?=\n##|\Z)", content):
        for line in section.split('\n'):
            if m := re.match(r'-\s*\*\*([^*]+)\*\*:\s*([\w-]+)\s*\((\d+)%\)', line):
                tier, rubric, weight = m.groups()
                rubric_profile[tier.lower()] = {"rubric": rubric, "weight": int(weight)}
    
    if not rubric_profile:
        raise ValueError(f"{path.name}: Missing required ## Rubric Profile section")
    
    task_prompt = (
        rx(r"## Task Prompt\s*```([^`]+)```", content) or
        rx(r"## Task Prompt\s*\n(.+?)(?=\n##)", content)
    )
    
    must_include = []
    if section := rx(r"###\s*Must (?:Include|Identify)\s*\n(.*?)(?=\n###|\n##|\Z)", content):
        must_include = [m.group(1).strip() for line in section.split('\n') 
                       if (m := re.search(r'-\s*\[.\]\s*(.+)', line))]
    
    # Use filename as authoritative source for test name
    name = path.stem.replace("test-", "").replace("-", " ").title()

    return TestCase(
        name=name,
        agent=rx(r"\*\*Agent\*\*:\s*([\w-]+)", content),
        task_prompt=task_prompt,
        rubric_profile=rubric_profile,
        must_include=must_include,
        file_path=path,
        timeout=rx_int(r"Timeout\*\*:\s*(\d+)", content) or 600,
    )


def find_cli(provider: str) -> Path | None:
    paths = {
        "claude": ["/usr/local/bin/claude", os.path.expanduser("~/.claude/local/claude")],
        "gemini": ["/usr/local/bin/gemini", os.path.expanduser("~/.gemini/bin/gemini")],
        "codex": ["/usr/local/bin/codex", os.path.expanduser("~/.codex/bin/codex")],
    }
    return next((Path(p) for p in paths.get(provider, []) if Path(p).exists()), None)


def run_cli(model: str, prompt: str, timeout: int = 600) -> tuple[bool, str, str]:
    provider = model.split(":")[0].lower()
    version = model.split(":")[1] if ":" in model else None
    
    if not (cli := find_cli(provider)):
        return False, "", f"{provider} CLI not found"
    
    config = CLI_CONFIG[provider]
    cmd = [str(cli), *config["base"]]
    if version:
        cmd += ["--model", version]
    cmd += config["tools"]
    
    stdin_input = prompt if config.get("stdin") else None
    if not stdin_input:
        cmd += ["-p", prompt]
    
    try:
        result = subprocess.run(cmd, input=stdin_input, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout, result.stderr or f"Exit {result.returncode}"
    except subprocess.TimeoutExpired:
        return False, "", f"Timeout after {timeout}s"
    except Exception as e:
        return False, "", str(e)


def execute_agent(agent: str, prompt: str, timeout: int = 600, model: str = "claude") -> AgentResult:
    start = time.time()
    
    agent_file = EVALS_DIR.parent / "agents" / f"{agent}.md"
    methodology = agent_file.read_text() if agent_file.exists() else ""
    
    if methodology.count("---") >= 2:
        methodology = methodology.split("---", 2)[2].strip()
    
    if methodology:
        methodology += "\n\n**EVAL MODE**: Provide focused, concise output."
    
    full_prompt = load_template("agent_prompt" if methodology else "agent_prompt_fallback")
    full_prompt = full_prompt.replace("{agent_name}", agent)
    full_prompt = full_prompt.replace("{methodology}", methodology)
    full_prompt = full_prompt.replace("{prompt}", prompt)
    
    success, output, error = run_cli(model, full_prompt, timeout)
    return AgentResult(success, output, time.time() - start, error if not success else None)


def evaluate_output(tc: TestCase, output: str, model: str = "claude") -> EvaluationReport:
    rpt = EvaluationReport(tc, AgentResult(True, output, 0))
    
    rubrics_dir = EVALS_DIR / "rubrics"
    rubric_texts = []
    dimensions = []
    score_keys = []
    
    for tier, spec in sorted(tc.rubric_profile.items()):
        rubric_name = spec["rubric"]
        weight = spec["weight"]
        rubric_file = rubrics_dir / f"{rubric_name}.md"
        
        if rubric_file.exists():
            rubric_texts.append(f"\n--- {rubric_name} ({weight}%) ---\n{rubric_file.read_text()}")
        
        display_name = rubric_name.replace("-", " ").title()
        key = rubric_name.replace("-", "_").upper()
        dimensions.append(f"{tier.capitalize()}) **{display_name}** ({weight}%)")
        score_keys.append((key, rubric_name, weight))
    
    prompt = load_template("judge_prompt").format(
        agent=tc.agent,
        task_prompt=tc.task_prompt,
        must_include="\n".join(f"- {i}" for i in tc.must_include) or "None",
        should_include="None",
        should_not_include="None",
        rubric_weights={},
        rubrics_text="\n".join(rubric_texts),
        rubric_dimensions="\n".join(dimensions),
        score_format="\n".join(f"{k}: [score]" for k, _, _ in score_keys),
        agent_output=output,
        passing_threshold=70,
    )

    # Strip YAML frontmatter if present
    if prompt.startswith("---"):
        prompt = re.sub(r"^---.*?---\n", "", prompt, flags=re.DOTALL)

    success, judge_out, error = run_cli(model, prompt, 600)
    if not success:
        rpt.judge_output = f"Judge error: {error}"
        return rpt
    
    rpt.judge_output = judge_out
    
    for key, name, weight in score_keys:
        rpt.scores[name] = rx_int(rf"{key}[*`]*\s*[:=]\s*(\d+)", judge_out)
    
    if overall := rx(r"OVERALL_SCORE[*`]*\s*[:=]\s*([\d.]+)", judge_out):
        rpt.overall_score = float(overall)
    else:
        total = sum(rpt.scores.get(name, 0) * weight for _, name, weight in score_keys)
        total_weight = sum(weight for _, _, weight in score_keys)
        rpt.overall_score = total / total_weight if total_weight > 0 else 0
    
    rpt.must_include_met = rx_list(r"MUST_INCLUDE_MET:\s*(.+?)(?=\n|$)", judge_out)
    rpt.must_include_missed = rx_list(r"MUST_INCLUDE_MISSED:\s*(.+?)(?=\n|$)", judge_out)
    
    result = rx(r"RESULT:\s*(PASS|FAIL)", judge_out)
    rpt.passed = result.upper() == "PASS" if result else rpt.overall_score >= 70
    
    return rpt


def generate_report(rpt: EvaluationReport, out_dir: Path, model: str = "claude") -> Path:
    tc, ar = rpt.test_case, rpt.agent_result
    model_slug = model.split(":")[0].lower()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    filename = f"{model_slug}_{tc.agent}_{tc.name.lower().replace(' ', '-')}.md"
    
    latest_dir = out_dir / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    latest_path = latest_dir / filename
    
    history_dir = out_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    history_path = history_dir / f"{timestamp}_{filename}"
    
    score_rows = "\n".join(
        f"| {name.replace('-', ' ').title()} | {score}/100 |"
        for name, score in rpt.scores.items()
    )
    
    content = f"""# Evaluation Report: {tc.name}

**Agent**: {tc.agent}  
**Model**: {model}  
**Status**: {"PASS" if rpt.passed else "FAIL"}  
**Duration**: {ar.duration:.1f}s

## Scores
| Rubric | Score |
|--------|-------|
{score_rows}
| **Overall** | **{rpt.overall_score:.1f}/100** |

## Must-Include
**Met**: {", ".join(rpt.must_include_met) or "None"}  
**Missed**: {", ".join(rpt.must_include_missed) or "None"}

## Output
```
{ar.output[:5000]}
```

## Judge Evaluation
{rpt.judge_output}
"""
    
    latest_path.write_text(content)
    history_path.write_text(content)
    rpt.report_path = latest_path
    
    return latest_path


def generate_summary(reports: list[EvaluationReport], out_dir: Path, model: str = "claude") -> Path:
    n = len(reports)
    ok = sum(r.passed for r in reports)
    fail = n - ok
    avg = sum(r.overall_score for r in reports) / n if n > 0 else 0
    
    path = out_dir / "latest" / "index.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    
    results_table = "\n".join(
        f"| {r.test_case.agent} | {r.test_case.name} | "
        f"{'PASS' if r.passed else 'FAIL'} | {r.overall_score:.0f} | "
        f"[{r.report_path.name}]({r.report_path.name}) |"
        for r in reports if r.report_path
    )
    
    content = f"""# Evaluation Summary

**Date**: {datetime.now():%Y-%m-%d %H:%M:%S}  
**Model**: {model}  
**Tests**: {n}  
**Pass Rate**: {ok}/{n} ({ok/n*100:.0f}%)  
**Average Score**: {avg:.1f}/100

## Results
| Agent | Test | Status | Score | Report |
|-------|------|--------|-------|--------|
{results_table}
"""
    
    path.write_text(content)
    return path


def discover_tests(test_dir: Path, agent_filter: str | None = None) -> list[TestCase]:
    tests = []
    for file in test_dir.rglob("*.md"):
        if agent_filter and agent_filter not in str(file.parent):
            continue
        try:
            tests.append(parse_test_case(file))
        except Exception:
            pass
    return sorted(tests, key=lambda t: (t.agent, t.name))
