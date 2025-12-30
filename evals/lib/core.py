import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc
from functools import cache
from pathlib import Path

EVALS_DIR = Path(__file__).parent.parent
CLI_CONFIG = {
    "claude": {"base": ["--print", "--verbose"], "tools": ["--tools", "WebSearch,WebFetch,Read"]},
    "gemini": {"base": [], "tools": ["--yolo"], "stdin": True},
    "codex": {"base": ["--search", "--enable", "web_search_request", "exec", "--full-auto"], "tools": [], "stdin": True},
    "gpt": {"base": ["--search", "--enable", "web_search_request", "exec", "--full-auto"], "tools": [], "stdin": True},
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
    
    # v2.0 fields for granular transparency
    rubric_breakdown: dict = field(default_factory=dict)
    agent_output: str = ""
    execution_metadata: dict = field(default_factory=dict)

    @property
    def agent(self) -> str:
        return self.test_case.agent


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
        "codex": ["/usr/local/bin/codex", os.path.expanduser("~ ~/.codex/bin/codex")],
        "gpt": ["/usr/local/bin/codex", os.path.expanduser("~/.codex/bin/codex")],
    }
    return next((Path(p) for p in paths.get(provider, []) if Path(p).exists()), None)


def run_cli(model: str, prompt: str, timeout: int = 600) -> tuple[bool, str, str]:
    parts = model.split(":")
    provider = parts[0].lower()
    model_str = parts[1] if len(parts) > 1 else None
    
    # Support "gpt-5.2-code high" or "gpt-5.2-code:high"
    version = model_str
    extra = parts[2] if len(parts) > 2 else None
    if not extra and version and " " in version:
        version, extra = version.rsplit(" ", 1)
    
    if not (cli := find_cli(provider)):
        return False, "", f"{provider} CLI not found"
    
    config = CLI_CONFIG[provider]
    cmd = [str(cli), *config["base"]]
    
    if version:
        cmd += ["--model", version]
    if extra and provider == "codex":
        cmd += ["-c", f"reasoning=\"{extra}\""]
        
    cmd += config["tools"]
    
    stdin_input = prompt if config.get("stdin") else None
    if stdin_input:
        # For CLIs that read from stdin (e.g., Codex exec), pass '-' to signal stdin mode
        cmd += ["-"]
    else:
        cmd += ["-p", prompt]
    
    try:
        result = subprocess.run(cmd, input=stdin_input, capture_output=True, text=True, timeout=timeout)
        err = (result.stderr + "\n" + result.stdout).strip() if result.returncode != 0 else ""
        return result.returncode == 0, result.stdout, err or f"Exit {result.returncode}"
    except subprocess.TimeoutExpired:
        return False, "", f"Timeout after {timeout}s"
    except Exception as e:
        return False, "", str(e)


def execute_agent(agent: str, prompt: str, timeout: int = 600, model: str = "claude") -> AgentResult:
    start = time.time()
    
    agent_file = EVALS_DIR.parent / "agents" / f"{agent}.md"
    if not agent_file.exists():
        print(f"WARNING: No agent file for {agent}, using fallback prompt")
        methodology = ""
    else:
        methodology = agent_file.read_text()
    
    tools = []
    if methodology:
        # Extract tools from frontmatter
        if m := re.search(r"tools:\s*\n((?:\s*-\s*\w+\s*\n)+)", agent_file.read_text()):
            tools = [t.strip("- ").strip() for t in m.group(1).split("\n") if t.strip()]
        
        methodology += "\n\n**EVAL MODE**: Provide focused, concise output."
    
    full_prompt = load_template("agent_prompt" if methodology else "agent_prompt_fallback")
    full_prompt = full_prompt.replace("{agent_name}", agent)
    full_prompt = full_prompt.replace("{provider}", model.split(":")[0])
    full_prompt = full_prompt.replace("{methodology}", methodology)
    full_prompt = full_prompt.replace("{tools}", ", ".join(tools) if tools else "None")
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

    # v2.0: Populate agent output and metadata BEFORE judge (so it's captured even if judge fails)
    rpt.agent_output = output
    rpt.execution_metadata = {
        "duration_seconds": rpt.agent_result.duration,
        "source": "automated_run"
    }

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
    
    # v2.0: Extract rubric breakdown with reasoning
    for key, name, weight in score_keys:
        score = rpt.scores.get(name, 0)
        reasoning = rx(rf"{key}_REASONING:\s*(.+?)(?=\n\n|\n[A-Z_]+:|$)", judge_out)
        rpt.rubric_breakdown[name] = {
            "weight": weight,
            "score": score,
            "reasoning": reasoning or f"Score: {score}/100"
        }
    
    return rpt


def generate_report(rpt: EvaluationReport, out_dir: Path, model: str = "claude") -> Path:
    tc, ar = rpt.test_case, rpt.agent_result
    model_slug = model.split(":")[0].lower()
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    
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


def generate_summary(out_dir: Path) -> Path:
    latest_dir = out_dir / "latest"
    reports_data = []
    
    for file in latest_dir.glob("*.md"):
        if file.name == "index.md":
            continue
            
        content = file.read_text()
        reports_data.append({
            "agent": rx(r"\*\*Agent\*\*:\s*([^\n]+)", content),
            "name": rx(r"# Evaluation Report:\s*([^\n]+)", content),
            "status": rx(r"\*\*Status\*\*:\s*(PASS|FAIL)", content),
            "score": rx(r"Overall.*?(\d+(?:\.\d+)?)/100", content) or "0",
            "model": rx(r"\*\*Model\*\*:\s*([^\n]+)", content).strip(),
            "file": file.name
        })
    
    reports_data.sort(key=lambda x: (x["model"], x["agent"], x["name"]))
    
    n = len(reports_data)
    ok = sum(1 for r in reports_data if r["status"] == "PASS")
    avg = sum(float(r["score"]) for r in reports_data if r["score"]) / n if n > 0 else 0
    
    results_table = "\n".join(
        f"| {r['model']} | {r['agent']} | {r['name']} | "
        f"{'PASS' if r['status'] == 'PASS' else 'FAIL'} | {float(r['score']):.0f} | "
        f"[{r['file']}]({r['file']}) |"
        for r in reports_data
    )
    
    content = f"""# Evaluation Summary

**Date**: {datetime.now(UTC):%Y-%m-%d %H:%M:%S}  
**Tests**: {n}  
**Pass Rate**: {ok}/{n} ({ok/n*100 if n > 0 else 0:.0f}%)  
**Average Score**: {avg:.1f}/100

## Results
| Model | Agent | Test | Status | Score | Report |
|-------|-------|------|--------|-------|--------|
{results_table}
"""
    
    path = latest_dir / "index.md"
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
