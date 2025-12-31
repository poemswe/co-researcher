#!/usr/bin/env python3
import argparse
import sys
import json
import concurrent.futures
import threading
from datetime import datetime, timezone
from pathlib import Path

from lib.core import (
    discover_tests,
    execute_agent,
    evaluate_output,
    generate_report,
    generate_summary,
    parse_test_case,
)

EVALS_DIR = Path(__file__).parent
TEST_CASES_DIR = EVALS_DIR / "test-cases"
RESULTS_DIR = EVALS_DIR / "results"
PRINT_LOCK = threading.Lock()


def run_test(agent: str, test: str, model: str, verbose: bool = False):
    test_file = TEST_CASES_DIR / agent / f"test-{test}.md"
    if not test_file.exists():
        with PRINT_LOCK:
            print(f"Test not found: {agent}/{test}")
        return None
    
    tc = parse_test_case(test_file)
    report = _execute_single_test(tc, model, verbose)
    if report:
        generate_summary(RESULTS_DIR)
    return report


def _execute_single_test(tc, model: str, verbose: bool):
    try:
        with PRINT_LOCK:
            print(f"[{tc.agent}] {tc.name} started...")

        result = execute_agent(tc.agent, tc.task_prompt, tc.timeout, model)
        
        if not result.success:
            with PRINT_LOCK:
                print(f"[{tc.agent}] {tc.name} failed: {result.error}")
            return None
        
        report = evaluate_output(tc, result.output, model)
        report_path = generate_report(report, RESULTS_DIR, model)
        
        status = "PASS" if report.passed else "FAIL"
        
        with PRINT_LOCK:
            print(f"\n{status} [{tc.agent}] {tc.name}")
            print(f"   Score: {report.overall_score:.0f}/100")
            print(f"   Time: {result.duration:.1f}s")
            score_str = ", ".join(f"{name}: {score}" for name, score in report.scores.items())
            print(f"   Scores: {score_str}")
            print(f"   Report: {report_path.relative_to(RESULTS_DIR)}")
            if verbose:
                 print(f"   Output: {result.output[:100]}...")

        return report
    except Exception as e:
        import traceback
        with PRINT_LOCK:
            print(f"[{tc.agent}] {tc.name} EXCEPTION: {e}")
            traceback.print_exc()
        return None


def run_agent_tests(agent: str, model: str, verbose: bool = False, jobs: int = 1):
    agent_dir = TEST_CASES_DIR / agent
    if not agent_dir.exists():
        print(f"Agent not found: {agent}")
        return []
    
    tests = []
    for test_file in sorted(agent_dir.glob("test-*.md")):
        tests.append(parse_test_case(test_file))
        
    reports = _run_tests_parallel(tests, model, verbose, jobs)
    if reports:
        generate_summary(RESULTS_DIR)
    return reports


def run_all_tests(model: str, verbose: bool = False, jobs: int = 1):
    tests = discover_tests(TEST_CASES_DIR)
    print(f"Starting {len(tests)} tests with {jobs} parallel jobs...")
    
    reports = _run_tests_parallel(tests, model, verbose, jobs)
    
    if reports:
        summary_path = generate_summary(RESULTS_DIR)
        print(f"\nSummary: {summary_path.relative_to(RESULTS_DIR)}")
    
    return reports


def _run_tests_parallel(tests, model, verbose, jobs):
    reports = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = [executor.submit(_execute_single_test, tc, model, verbose) for tc in tests]
        
        for future in concurrent.futures.as_completed(futures):
            if report := future.result():
                reports.append(report)
                
    return reports


def list_tests():
    print("\nAvailable Tests\n")
    for agent_dir in sorted(TEST_CASES_DIR.iterdir()):
        if not agent_dir.is_dir() or agent_dir.name.startswith("."):
            continue
        tests = [f.stem.replace("test-", "") for f in sorted(agent_dir.glob("test-*.md"))]
        if tests:
            print(f"  {agent_dir.name}")
            for test in tests:
                print(f"    - {test}")
            print()


def generate_run_id() -> str:
    """Generate unique run ID: run_YYYYMMDD_HHMMSS"""
    return datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")


def extract_model_version(model: str) -> str:
    """Extract detailed model version"""
    version_map = {
        "claude": "claude-3.5-sonnet",
        "codex": "gpt-5.2-xhigh",
        "gemini": "gemini-3-flash-preview"
    }
    # Handle versioned models like "codex:gpt-5.2 xhigh"
    if ":" in model:
        return model.split(":", 1)[1].strip()
    return version_map.get(model, model)


def extract_difficulty(test_path: Path) -> str:
    """Extract difficulty from test file"""
    import re
    if test_path and test_path.exists():
        content = test_path.read_text()
        if match := re.search(r"difficulty:\s*(\w+)", content, re.IGNORECASE):
            return match.group(1).capitalize()
    return "Medium"


def extract_justification(judge_output: str) -> str:
    import re
    
    if match := re.search(r"OVERALL_JUSTIFICATION:\s*(.+?)(?=\n\n|\nRESULT:|$)", judge_output, re.DOTALL):
        justification = match.group(1).strip()
        if not justification.startswith(("ANALYTICAL", "OUTPUT", "RESEARCH", "DESIGN")):
            return justification
    
    for pattern in [r"REASONING:\s*(.+?)(?=\n\n|\n[A-Z_]+:|$)", 
                    r"JUSTIFICATION:\s*(.+?)(?=\n\n|\n[A-Z_]+:|$)"]:
        if match := re.search(pattern, judge_output, re.DOTALL):
            return match.group(1).strip()
    
    return ""


def save_benchmark_v2(reports, model: str, run_id: str):
    """Save to both overview and detail files (v2.0 schema)"""
    detail_dir = EVALS_DIR / "test_results_detail"
    detail_dir.mkdir(exist_ok=True)
    
    # 1. Create detail file
    detail_file = detail_dir / f"{run_id}.json"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    detail_data = {
        "run_id": run_id,
        "timestamp": timestamp,
        "model": model,
        "model_version": extract_model_version(model),
        "test_results": []
    }
    
    for rpt in reports:
        if not rpt:
            continue
        
        test_id = f"{model.split(':')[0]}_{rpt.test_case.agent}_{rpt.test_case.name.lower().replace(' ', '-')}_{run_id.split('_')[-2]}"
        
        test_result = {
            "id": test_id,
            "agent": rpt.test_case.agent,
            "test_case": rpt.test_case.name.lower().replace(" ", "-"),
            "test_name": rpt.test_case.name,
            "difficulty": extract_difficulty(rpt.test_case.file_path),
            "score": round(rpt.overall_score, 1),
            "passed": rpt.passed,
            "threshold": 70,
            "rubrics": {
                name: {"weight": data["weight"], "score": data["score"]}
                for name, data in rpt.rubric_breakdown.items()
            },
            "agent_output": rpt.agent_output,
            "judge_output": {
                "evaluation": extract_justification(rpt.judge_output),
                "rubric_breakdown": rpt.rubric_breakdown,
                "must_include_analysis": {
                    "met": rpt.must_include_met,
                    "missed": rpt.must_include_missed,
                    "details": f"Covered {len(rpt.must_include_met)}/{len(rpt.must_include_met) + len(rpt.must_include_missed)} required elements"
                },
                "overall_justification": extract_justification(rpt.judge_output)
            },
            "execution_metadata": rpt.execution_metadata
        }
        detail_data["test_results"].append(test_result)
    
    detail_file.write_text(json.dumps(detail_data, indent=2))
    
    # 2. Update overview file
    overview_file = EVALS_DIR / "benchmark_overview.json"
    overview = {"schema_version": "2.0", "runs": [], "summary_stats": {}}
    
    if overview_file.exists():
        overview = json.loads(overview_file.read_text())
    
    scores = [r.overall_score for r in reports if r]
    avg_score = sum(scores) / len(scores) if scores else 0
    passed_count = sum(1 for r in reports if r and r.passed)
    total_count = len([r for r in reports if r])
    
    run_entry = {
        "run_id": run_id,
        "timestamp": timestamp,
        "model": model,
        "model_version": detail_data["model_version"],
        "tests_run": total_count,
        "tests_passed": passed_count,
        "average_score": round(avg_score, 1),
        "scores_by_agent": {},
        "pass_rate": round((passed_count / total_count * 100), 1) if total_count > 0 else 0,
        "detail_file": f"test_results_detail/{run_id}.json"
    }
    
    for r in reports:
        if r:
            agent_name = r.test_case.agent
            if agent_name not in run_entry["scores_by_agent"]:
                run_entry["scores_by_agent"][agent_name] = []
            run_entry["scores_by_agent"][agent_name].append(round(r.overall_score, 1))
    
    overview["runs"].append(run_entry)
    
    # Update summary stats
    all_models = sorted(set(run["model"] for run in overview["runs"]))
    all_agents = set()
    for run in overview["runs"]:
        all_agents.update(run["scores_by_agent"].keys())
    
    total_passed = sum(run["tests_passed"] for run in overview["runs"])
    total_run = sum(run["tests_run"] for run in overview["runs"])
    
    overview["summary_stats"] = {
        "total_runs": len(overview["runs"]),
        "models": all_models,
        "agents": sorted(list(all_agents)),
        "overall_pass_rate": round((total_passed / total_run * 100), 1) if total_run > 0 else 0
    }
    
    overview_file.write_text(json.dumps(overview, indent=2))
    
    # Print summary
    print(f"\n✅ Benchmark saved (v2.0)")
    print(f"   Detail: {detail_file.name}")
    print(f"   Overview: {overview_file.name} ({len(overview['runs'])} runs)")
    print(f"   Arena Dashboard: file://{EVALS_DIR.absolute()}/arena.html")
    
    # Trend
    if len(overview["runs"]) > 1:
        prev = overview["runs"][-2]
        delta = run_entry["average_score"] - prev["average_score"]
        trend = "↑" if delta > 0 else "↓" if delta < 0 else "→"
        print(f"   Score trend: {prev['average_score']:.1f} {trend} {run_entry['average_score']:.1f} ({delta:+.1f})")


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("args", nargs="*", help="[list|all|agent|agent test]")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-m", "--model", default="claude", help="Model (default: claude)")
    parser.add_argument("-j", "--jobs", type=int, default=1, help="Parallel jobs (default: 1)")
    parser.add_argument("--check-prompts", action="store_true", help="Validate all agent prompt files exist")
    parser.add_argument("--no-benchmark", action="store_true", help="Skip saving to benchmark_history.json")
    
    args = parser.parse_args()
    
    if args.check_prompts:
        agents = [d.name for d in TEST_CASES_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")]
        missing = []
        for agent in sorted(agents):
            agent_file = EVALS_DIR.parent / "agents" / f"{agent}.md"
            if not agent_file.exists():
                missing.append(agent)
                print(f"MISSING: {agent_file}")
            else:
                print(f"OK: {agent_file}")
        if missing:
            print(f"\nFound {len(missing)} missing agent files.")
            sys.exit(1)
        else:
            print("\nAll agent prompt files identified.")
        return

    if not args.args:
        parser.print_help()
        return
    
    command = args.args[0]
    
    if command == "list":
        list_tests()
    elif command == "all":
        run_id = generate_run_id()
        reports = run_all_tests(args.model, args.verbose, args.jobs)
        if reports and not args.no_benchmark:
            save_benchmark_v2(reports, args.model, run_id)
    elif len(args.args) == 1:
        run_id = generate_run_id()
        reports = run_agent_tests(command, args.model, args.verbose, args.jobs)
        if reports and not args.no_benchmark:
            save_benchmark_v2(reports, args.model, run_id)
    elif len(args.args) == 2:
        run_id = generate_run_id()
        report = run_test(args.args[0], args.args[1], args.model, args.verbose)
        if report and not args.no_benchmark:
            save_benchmark_v2([report], args.model, run_id)
    else:
        print(f"Unknown command: {' '.join(args.args)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
