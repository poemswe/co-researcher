#!/usr/bin/env python3
import argparse
import sys
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


def run_test(agent: str, test: str, model: str, verbose: bool = False):
    test_file = TEST_CASES_DIR / agent / f"test-{test}.md"
    if not test_file.exists():
        print(f"❌ Test not found: {agent}/{test}")
        return None
    
    tc = parse_test_case(test_file)
    
    print(f"📝 {tc.name}")
    print(f"🔄 Executing agent...")
    
    result = execute_agent(tc.agent, tc.task_prompt, tc.timeout, model)
    
    if not result.success:
        print(f"❌ Agent failed: {result.error}")
        return None
    
    print(f"✅ Agent completed in {result.duration:.1f}s")
    
    if verbose:
        print(f"📄 Output: {result.output[:200]}...")
    
    print(f"🔍 Evaluating...")
    report = evaluate_output(tc, result.output, model)
    
    report_path = generate_report(report, RESULTS_DIR, model)
    
    status = "PASS ✅" if report.passed else "FAIL ❌"
    print(f"{status} Score: {report.overall_score:.0f}/100")
    
    score_str = ", ".join(f"{name}: {score}" for name, score in report.scores.items())
    print(f"   {score_str}")
    print(f"📁 Report: {report_path.relative_to(RESULTS_DIR)}")
    
    return report


def run_agent_tests(agent: str, model: str, verbose: bool = False):
    agent_dir = TEST_CASES_DIR / agent
    if not agent_dir.exists():
        print(f"❌ Agent not found: {agent}")
        return []
    
    test_files = sorted(agent_dir.glob("test-*.md"))
    reports = []
    
    for i, test_file in enumerate(test_files, 1):
        test_name = test_file.stem.replace("test-", "")
        print(f"\n[{i}/{len(test_files)}] 🧪 {agent}/{test_name} (model: {model})")
        
        if report := run_test(agent, test_name, model, verbose):
            reports.append(report)
    
    return reports


def run_all_tests(model: str, verbose: bool = False):
    tests = discover_tests(TEST_CASES_DIR)
    reports = []
    
    for i, tc in enumerate(tests, 1):
        test_name = tc.name.lower().replace(" ", "-")
        print(f"\n[{i}/{len(tests)}] 🧪 {tc.agent}/{test_name} (model: {model})")
        
        result = execute_agent(tc.agent, tc.task_prompt, tc.timeout, model)
        if not result.success:
            print(f"❌ Failed: {result.error}")
            continue
        
        print(f"✅ Completed in {result.duration:.1f}s")
        
        report = evaluate_output(tc, result.output, model)
        status = "PASS ✅" if report.passed else "FAIL ❌"
        print(f"{status} {report.overall_score:.0f}/100")
        
        generate_report(report, RESULTS_DIR, model)
        reports.append(report)
    
    if reports:
        summary_path = generate_summary(reports, RESULTS_DIR, model)
        print(f"\n📊 Summary: {summary_path.relative_to(RESULTS_DIR)}")
    
    return reports


def list_tests():
    print("\n📋 Available Tests\n")
    
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
    
    args = parser.parse_args()
    
    if not args.args:
        parser.print_help()
        return
    
    command = args.args[0]
    
    if command == "list":
        list_tests()
    elif command == "all":
        run_all_tests(args.model, args.verbose)
    elif len(args.args) == 1:
        run_agent_tests(command, args.model, args.verbose)
    elif len(args.args) == 2:
        run_test(args.args[0], args.args[1], args.model, args.verbose)
    else:
        print(f"❌ Unknown command: {' '.join(args.args)}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
