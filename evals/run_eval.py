#!/usr/bin/env python3
import argparse
import sys
import concurrent.futures
import threading
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


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("args", nargs="*", help="[list|all|agent|agent test]")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-m", "--model", default="claude", help="Model (default: claude)")
    parser.add_argument("-j", "--jobs", type=int, default=1, help="Parallel jobs (default: 1)")
    
    args = parser.parse_args()
    
    if not args.args:
        parser.print_help()
        return
    
    command = args.args[0]
    
    if command == "list":
        list_tests()
    elif command == "all":
        run_all_tests(args.model, args.verbose, args.jobs)
    elif len(args.args) == 1:
        run_agent_tests(command, args.model, args.verbose, args.jobs)
    elif len(args.args) == 2:
        run_test(args.args[0], args.args[1], args.model, args.verbose)
    else:
        print(f"Unknown command: {' '.join(args.args)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
