import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
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
    primary_dimension: Optional[str] = None
    primary_threshold: Optional[int] = None
    rubric_weights: dict[str, int] = field(default_factory=dict)
    file_path: Optional[Path] = None


@dataclass
class AgentResult:
    success: bool
    output: str
    duration_seconds: float
    error: Optional[str] = None


@dataclass
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


def parse_test_case(file_path: Path) -> TestCase:
    content = file_path.read_text()

    name_match = re.search(r"#\s*Test Case:\s*(.+)", content)
    name = name_match.group(1).strip() if name_match else file_path.stem

    agent_match = re.search(r"\*\*Agent\*\*:\s*(\S+)", content)
    agent = agent_match.group(1) if agent_match else "unknown"

    difficulty_match = re.search(r"\*\*Difficulty\*\*:\s*(\S+)", content)
    difficulty = difficulty_match.group(1) if difficulty_match else "Medium"

    focus_match = re.search(r"\*\*Focus\*\*:\s*(.+)", content)
    focus = focus_match.group(1).strip() if focus_match else ""

    prompt_match = re.search(r"##\s*Task Prompt\s*\n+```\n?(.*?)```", content, re.DOTALL)
    task_prompt = prompt_match.group(1).strip() if prompt_match else ""

    must_include = extract_checklist(content, "Must Include") or extract_checklist(content, "Must Identify")
    should_include = extract_checklist(content, "Should Include")
    should_not_include = extract_checklist(content, "Should Not Include")

    threshold_match = re.search(r"Overall Score:\s*[≥>=]+\s*(\d+)", content)
    passing_threshold = int(threshold_match.group(1)) if threshold_match else 70

    primary_match = re.search(r"(\w+\s*Quality):\s*[≥>=]+\s*(\d+)/100\s*\(primary", content, re.IGNORECASE)
    if primary_match:
        primary_dimension = primary_match.group(1).strip()
        primary_threshold = int(primary_match.group(2))
    else:
        primary_match = re.search(r"(\w+\s*Quality):\s*[≥>=]+\s*(\d+)/100", content, re.IGNORECASE)
        if primary_match:
            primary_dimension = primary_match.group(1).strip()
            primary_threshold = int(primary_match.group(2))
        else:
            primary_dimension = None
            primary_threshold = None

    rubric_weights = {}
    weights_section = re.search(r"##\s*Rubric Weights\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
    if weights_section:
        for line in weights_section.group(1).split("\n"):
            weight_match = re.search(r"(\w+\s*Quality):\s*(\d+)%", line)
            if weight_match:
                rubric_weights[weight_match.group(1).strip().lower().replace(" ", "_")] = int(weight_match.group(2))

    if not rubric_weights:
        rubric_weights = {"research_quality": 33, "reasoning_quality": 34, "output_structure": 33}

    return TestCase(
        name=name,
        agent=agent,
        difficulty=difficulty,
        focus=focus,
        task_prompt=task_prompt,
        must_include=must_include,
        should_include=should_include,
        should_not_include=should_not_include,
        passing_threshold=passing_threshold,
        primary_dimension=primary_dimension,
        primary_threshold=primary_threshold,
        rubric_weights=rubric_weights,
        file_path=file_path,
    )


def extract_checklist(content: str, section_name: str) -> list[str]:
    pattern = rf"###\s*{section_name}\s*\n(.*?)(?=\n###|\n##|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return []

    items = []
    for line in match.group(1).split("\n"):
        item_match = re.search(r"-\s*\[.\]\s*(.+)", line)
        if item_match:
            items.append(item_match.group(1).strip())
    return items


def discover_tests(test_dir: Path, agent_filter: Optional[str] = None, test_filter: Optional[str] = None) -> list[TestCase]:
    tests = []

    for agent_dir in sorted(test_dir.iterdir()):
        if not agent_dir.is_dir() or agent_dir.name.startswith("."):
            continue

        if agent_filter and agent_dir.name != agent_filter:
            continue

        for test_file in sorted(agent_dir.glob("test-*.md")):
            test_name = test_file.stem.replace("test-", "")

            if test_filter and test_name != test_filter:
                continue

            try:
                test_case = parse_test_case(test_file)
                tests.append(test_case)
            except Exception as e:
                print(f"Warning: Failed to parse {test_file}: {e}", file=sys.stderr)

    return tests


def find_model_cli(model: str = "claude") -> Optional[str]:
    import shutil
    import os
    
    home = Path.home()
    
    if model == "claude":
        if shutil.which("claude"):
            return "claude"
        claude_paths = [
            home / ".claude" / "local" / "claude",
            home / ".local" / "bin" / "claude",
            Path("/usr/local/bin/claude"),
        ]
        for path in claude_paths:
            if path.exists() and os.access(path, os.X_OK):
                return str(path)
    
    elif model == "gemini":
        if shutil.which("gemini"):
            return "gemini"
        gemini_paths = [
            Path("/usr/local/bin/gemini"),
            home / ".local" / "bin" / "gemini",
        ]
        for path in gemini_paths:
            if path.exists() and os.access(path, os.X_OK):
                return str(path)
    
    return None


def build_cli_command(model: str, cli_path: str, prompt: str) -> list[str]:
    if model == "claude":
        return [cli_path, "--print", "-p", prompt]
    elif model == "gemini":
        return [cli_path, "-p", prompt]
    return [cli_path, prompt]


def load_agent_methodology(agent_name: str) -> str:
    evals_dir = Path(__file__).parent.parent
    agents_dir = evals_dir.parent / "agents"
    agent_file = agents_dir / f"{agent_name}.md"
    
    if agent_file.exists():
        content = agent_file.read_text()
        if "---" in content:
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return parts[2].strip()
        return content
    return ""


def execute_agent(agent_name: str, prompt: str, timeout: int = 300, model: str = "claude") -> AgentResult:
    import time
    import tempfile
    start = time.time()

    methodology = load_agent_methodology(agent_name)
    
    if methodology:
        full_prompt = f"""You are the {agent_name} agent.

## Your Methodology and Output Format
{methodology}

## Task to Execute
{prompt}

Follow your methodology above and produce output in the specified format."""
    else:
        full_prompt = f"""You are the {agent_name} agent from the co-researcher plugin.

Execute this task using your expertise:

{prompt}

Provide a complete, thorough response following your agent's methodology and output format."""

    cli_path = find_model_cli(model)
    if not cli_path:
        return AgentResult(
            success=False,
            output="",
            duration_seconds=0,
            error=f"{model} CLI not found. Install it first.",
        )

    try:
        cmd = build_cli_command(model, cli_path, full_prompt)
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
            )

        duration = time.time() - start

        if result.returncode != 0:
            return AgentResult(
                success=False,
                output="",
                duration_seconds=duration,
                error=result.stderr or f"Exit code: {result.returncode}",
            )

        return AgentResult(
            success=True,
            output=result.stdout,
            duration_seconds=duration,
        )

    except subprocess.TimeoutExpired:
        return AgentResult(
            success=False,
            output="",
            duration_seconds=timeout,
            error=f"Timeout after {timeout} seconds",
        )
    except FileNotFoundError:
        return AgentResult(
            success=False,
            output="",
            duration_seconds=0,
            error=f"{model} CLI not found. Make sure it's installed and in PATH.",
        )
    except Exception as e:
        return AgentResult(
            success=False,
            output="",
            duration_seconds=time.time() - start,
            error=str(e),
        )


def evaluate_output(test_case: TestCase, agent_output: str, timeout: int = 300, model: str = "claude") -> EvaluationReport:
    import time

    report = EvaluationReport(
        test_case=test_case,
        agent_result=AgentResult(success=True, output=agent_output, duration_seconds=0),
    )

    rubrics_text = ""
    evals_dir = test_case.file_path.parent.parent if test_case.file_path else Path("evals")
    rubrics_dir = evals_dir / "rubrics"

    if rubrics_dir.exists():
        for rubric_file in rubrics_dir.glob("*.md"):
            rubrics_text += f"\n\n--- {rubric_file.stem} ---\n"
            rubrics_text += rubric_file.read_text()

    judge_prompt = f"""You are an impartial evaluation judge. Score this agent output against the test case criteria.

## Test Case
**Agent**: {test_case.agent}
**Task**: {test_case.task_prompt}

**Must Include Behaviors**:
{chr(10).join(f"- {item}" for item in test_case.must_include)}

**Should Include Behaviors**:
{chr(10).join(f"- {item}" for item in test_case.should_include)}

**Should NOT Include**:
{chr(10).join(f"- {item}" for item in test_case.should_not_include)}

**Rubric Weights**: {test_case.rubric_weights}

## Rubrics Reference
{rubrics_text}

## Agent Output to Evaluate
{agent_output}

## Your Task
Score the output on three dimensions (0-100 each):

1. **Research Quality**: Source credibility, comprehensiveness, accuracy, citation quality
2. **Reasoning Quality**: Logical coherence, bias detection, methodology critique, alternatives
3. **Output Structure**: Organization, completeness, clarity, visual communication

For each dimension, provide:
- Score (0-100)
- Brief justification

Then provide:
- Which "Must Include" behaviors were MET
- Which "Must Include" behaviors were MISSED
- Overall weighted score
- PASS/FAIL determination (threshold: {test_case.passing_threshold})

Format your response EXACTLY as:
```
RESEARCH_QUALITY: [score]
REASONING_QUALITY: [score]
OUTPUT_STRUCTURE: [score]
MUST_INCLUDE_MET: [comma-separated list or "none"]
MUST_INCLUDE_MISSED: [comma-separated list or "none"]
OVERALL_SCORE: [weighted score]
RESULT: [PASS or FAIL]
```

Then provide detailed justification."""

    cli_path = find_model_cli(model)
    if not cli_path:
        report.judge_output = f"{model} CLI not found"
        return report

    try:
        cmd = build_cli_command(model, cli_path, judge_prompt)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            report.judge_output = f"Judge error: {result.stderr}"
            return report

        judge_output = result.stdout
        report.judge_output = judge_output

        rq_match = re.search(r"RESEARCH_QUALITY:\s*(\d+)", judge_output)
        if rq_match:
            report.research_quality = int(rq_match.group(1))

        reas_match = re.search(r"REASONING_QUALITY:\s*(\d+)", judge_output)
        if reas_match:
            report.reasoning_quality = int(reas_match.group(1))

        os_match = re.search(r"OUTPUT_STRUCTURE:\s*(\d+)", judge_output)
        if os_match:
            report.output_structure = int(os_match.group(1))

        overall_match = re.search(r"OVERALL_SCORE:\s*([\d.]+)", judge_output)
        if overall_match:
            report.overall_score = float(overall_match.group(1))
        else:
            weights = test_case.rubric_weights
            rq_w = weights.get("research_quality", 33)
            reas_w = weights.get("reasoning_quality", 34)
            os_w = weights.get("output_structure", 33)
            report.overall_score = (
                report.research_quality * rq_w +
                report.reasoning_quality * reas_w +
                report.output_structure * os_w
            ) / 100

        met_match = re.search(r"MUST_INCLUDE_MET:\s*(.+?)(?=\n|$)", judge_output)
        if met_match and met_match.group(1).strip().lower() != "none":
            report.must_include_met = [x.strip() for x in met_match.group(1).split(",") if x.strip()]

        missed_match = re.search(r"MUST_INCLUDE_MISSED:\s*(.+?)(?=\n|$)", judge_output)
        if missed_match and missed_match.group(1).strip().lower() != "none":
            report.must_include_missed = [x.strip() for x in missed_match.group(1).split(",") if x.strip()]

        result_match = re.search(r"RESULT:\s*(PASS|FAIL)", judge_output, re.IGNORECASE)
        if result_match:
            report.passed = result_match.group(1).upper() == "PASS"
        else:
            report.passed = report.overall_score >= test_case.passing_threshold

    except subprocess.TimeoutExpired:
        report.judge_output = f"Judge timeout after {timeout} seconds"
    except FileNotFoundError:
        report.judge_output = "claude CLI not found"
    except Exception as e:
        report.judge_output = f"Judge error: {e}"

    return report


def generate_report(report: EvaluationReport, output_dir: Path, model: str = "claude") -> Path:
    agent_dir = output_dir / report.test_case.agent
    agent_dir.mkdir(parents=True, exist_ok=True)

    test_name = report.test_case.file_path.stem if report.test_case.file_path else report.test_case.name
    report_path = agent_dir / f"{test_name}.md"

    status = "PASS ✓" if report.passed else "FAIL ✗"
    if not report.agent_result.success:
        status = "ERROR ⚠"

    content = f"""# Evaluation Report: {report.test_case.name}

**Date**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Model**: {model}
**Agent**: {report.test_case.agent}
**Test**: {test_name}
**Difficulty**: {report.test_case.difficulty}
**Status**: {status}

## Scores

| Dimension | Score | Weight |
|-----------|-------|--------|
| Research Quality | {report.research_quality}/100 | {report.test_case.rubric_weights.get("research_quality", 33)}% |
| Reasoning Quality | {report.reasoning_quality}/100 | {report.test_case.rubric_weights.get("reasoning_quality", 34)}% |
| Output Structure | {report.output_structure}/100 | {report.test_case.rubric_weights.get("output_structure", 33)}% |
| **Overall** | **{report.overall_score:.1f}/100** | |

## Must-Include Behaviors

**Met**: {", ".join(report.must_include_met) if report.must_include_met else "None identified"}

**Missed**: {", ".join(report.must_include_missed) if report.must_include_missed else "None"}

## Agent Execution

**Duration**: {report.agent_result.duration_seconds:.1f}s
**Success**: {"Yes" if report.agent_result.success else "No"}
{f"**Error**: {report.agent_result.error}" if report.agent_result.error else ""}

## Agent Output

```
{report.agent_result.output[:5000]}{"..." if len(report.agent_result.output) > 5000 else ""}
```

## Judge Evaluation

{report.judge_output}
"""

    report_path.write_text(content)
    return report_path


def generate_summary(reports: list[EvaluationReport], output_dir: Path) -> Path:
    index_path = output_dir / "index.md"

    total = len(reports)
    passed = sum(1 for r in reports if r.passed and r.agent_result.success)
    failed = sum(1 for r in reports if not r.passed and r.agent_result.success)
    errors = sum(1 for r in reports if not r.agent_result.success)
    avg_score = sum(r.overall_score for r in reports if r.agent_result.success) / max(1, total - errors)

    agents = {}
    for r in reports:
        if r.test_case.agent not in agents:
            agents[r.test_case.agent] = {"tests": 0, "passed": 0, "failed": 0, "errors": 0, "scores": []}
        agents[r.test_case.agent]["tests"] += 1
        if not r.agent_result.success:
            agents[r.test_case.agent]["errors"] += 1
        elif r.passed:
            agents[r.test_case.agent]["passed"] += 1
            agents[r.test_case.agent]["scores"].append(r.overall_score)
        else:
            agents[r.test_case.agent]["failed"] += 1
            agents[r.test_case.agent]["scores"].append(r.overall_score)

    content = f"""# Co-Researcher Evaluation Report

**Date**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Total Tests**: {total}

## Overview

| Status | Count | Percentage |
|--------|-------|------------|
| PASS | {passed} | {passed/total*100:.1f}% |
| FAIL | {failed} | {failed/total*100:.1f}% |
| ERROR | {errors} | {errors/total*100:.1f}% |

**Average Score**: {avg_score:.1f}/100

## Per-Agent Results

| Agent | Tests | Passed | Failed | Errors | Avg Score |
|-------|-------|--------|--------|--------|-----------|
"""

    for agent, stats in sorted(agents.items()):
        avg = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0
        content += f"| {agent} | {stats['tests']} | {stats['passed']} | {stats['failed']} | {stats['errors']} | {avg:.0f} |\n"

    content += """
## Test Results

| Agent | Test | Score | Status |
|-------|------|-------|--------|
"""

    for r in reports:
        test_name = r.test_case.file_path.stem if r.test_case.file_path else r.test_case.name
        if not r.agent_result.success:
            status = "ERROR"
            score = "-"
        else:
            status = "PASS" if r.passed else "FAIL"
            score = f"{r.overall_score:.0f}"
        content += f"| {r.test_case.agent} | {test_name} | {score} | {status} |\n"

    content += """
## Detailed Reports

"""
    for r in reports:
        test_name = r.test_case.file_path.stem if r.test_case.file_path else r.test_case.name
        content += f"- [{r.test_case.agent}/{test_name}]({r.test_case.agent}/{test_name}.md)\n"

    index_path.write_text(content)
    return index_path
