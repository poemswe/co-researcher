#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

EVALS_DIR = Path(__file__).parent
TEST_CASES_DIR = EVALS_DIR / "test-cases"
RESULTS_DIR = EVALS_DIR / "results"

from lib import (
    discover_tests,
    execute_agent,
    evaluate_output,
    generate_report,
)
from lib.core import generate_summary


def list_tests():
    print("\n📋 Available Tests\n")
    
    agents = {}
    for agent_dir in sorted(TEST_CASES_DIR.iterdir()):
        if not agent_dir.is_dir() or agent_dir.name.startswith("."):
            continue
        agents[agent_dir.name] = []
        for test_file in sorted(agent_dir.glob("test-*.md")):
            test_name = test_file.stem.replace("test-", "")
            agents[agent_dir.name].append(test_name)
    
    for agent, tests in agents.items():
        print(f"  {agent}")
        for test in tests:
            print(f"    - {test}")
        print()
    
    total = sum(len(t) for t in agents.values())
    print(f"Total: {total} tests across {len(agents)} agents\n")


def run_test(agent: str, test: str, verbose: bool = False, model: str = "claude", index: int = 1, total: int = 1):
    progress = f"[{index}/{total}] " if total > 1 else ""
    print(f"\n{progress}🧪 Running: {agent}/{test} (model: {model})")
    
    tests = discover_tests(TEST_CASES_DIR, agent=agent, test=test)
    
    if not tests:
        print(f"   ❌ Test not found: {agent}/{test}")
        return None
        
    test_case = tests[0]
    print(f"   📝 {test_case.name} ({test_case.difficulty})")
    print(f"   🔄 Executing agent...")
    
    agent_result = execute_agent(test_case.agent, test_case.task_prompt, model=model)
    
    if not agent_result.success:
        print(f"   ❌ Agent execution failed: {agent_result.error}")
    else:
        print(f"   ✅ Agent completed in {agent_result.duration_seconds:.1f}s")
        if verbose:
            print(f"   📄 Output preview: {agent_result.output[:200]}...")
    
    print(f"   🔍 Evaluating with LLM judge...")
    report = evaluate_output(test_case, agent_result.output, model=model)
    report.agent_result = agent_result
    
    status = "PASS ✅" if report.passed else "FAIL ❌"
    print(f"   {status} Score: {report.overall_score:.0f}/100")
    print(f"      Research: {report.research_quality}, Reasoning: {report.reasoning_quality}, Structure: {report.output_structure}")
    
    report_path = generate_report(report, RESULTS_DIR, model=model)
    print(f"   📁 Report: {report_path.relative_to(EVALS_DIR)}")
    
    return report


def run_agent_tests(agent: str, verbose: bool = False, model: str = "claude"):
    print(f"\n🔬 Running all tests for: {agent} (model: {model})")
    
    tests = discover_tests(TEST_CASES_DIR, agent=agent)
    
    if not tests:
        print(f"   ❌ No tests found for agent: {agent}")
        return []
    
    print(f"   Found {len(tests)} test(s)")
    
    reports = []
    for i, test_case in enumerate(tests, 1):
        test_name = test_case.file_path.stem.replace("test-", "") if test_case.file_path else test_case.name
        report = run_test(agent, test_name, verbose, model, index=i, total=len(tests))
        if report:
            reports.append(report)
    
    return reports


def run_all_tests(verbose: bool = False, model: str = "claude"):
    print(f"\n🚀 Running full evaluation suite (model: {model})\n")
    
    tests = discover_tests(TEST_CASES_DIR)
    print(f"Found {len(tests)} test(s) to run\n")
    
    reports = []
    current_agent = None
    total_tests = len(tests)
    
    for i, test_case in enumerate(tests, 1):
        if test_case.agent != current_agent:
            current_agent = test_case.agent
            print(f"\n{'='*50}")
            print(f"Agent: {current_agent}")
            print(f"{'='*50}")
        
        test_name = test_case.file_path.stem.replace("test-", "") if test_case.file_path else test_case.name
        report = run_test(test_case.agent, test_name, verbose, model, index=i, total=total_tests)
        if report:
            reports.append(report)
    
    if reports:
        print(f"\n{'='*50}")
        print("📊 Generating Summary Report")
        print(f"{'='*50}")
        
        summary_path = generate_summary(reports, RESULTS_DIR)
        print(f"\n📁 Summary: {summary_path.relative_to(EVALS_DIR)}")
        
        passed = sum(1 for r in reports if r.passed and r.agent_result.success)
        failed = sum(1 for r in reports if not r.passed and r.agent_result.success)
        errors = sum(1 for r in reports if not r.agent_result.success)
        avg = sum(r.overall_score for r in reports if r.agent_result.success) / max(1, len(reports) - errors)
        
        print(f"\n📈 Results: {passed} passed, {failed} failed, {errors} errors")
        print(f"📊 Average Score: {avg:.0f}/100")
        
        overall_status = "PASS ✅" if failed == 0 and errors == 0 else "FAIL ❌"
        print(f"\n{overall_status} Overall: {passed}/{len(reports)} tests passed\n")
    
    return reports


def main():
    parser = argparse.ArgumentParser(
        description="Run co-researcher agent evaluations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_eval.py list                                List all available tests
  python run_eval.py all                                 Run all tests with Claude (default)
  python run_eval.py all --model claude:sonnet           Run with Claude Sonnet
  python run_eval.py all --model gemini:2.5-pro          Run with Gemini 2.5 Pro
  python run_eval.py all --model gemini:flash            Run with Gemini Flash
  python run_eval.py literature-reviewer basic-search    Run specific test
        """
    )
    
    parser.add_argument(
        "args",
        nargs="*",
        help="'list', 'all', '<agent>', or '<agent> <test>'"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show verbose output including agent responses"
    )
    
    parser.add_argument(
        "-m", "--model",
        default="claude",
        help="Model to use (default: claude). Format: provider or provider:version. Examples: claude, claude:sonnet, claude:opus, gemini, gemini:2.5-pro, gemini:flash"
    )
    
    args = parser.parse_args()
    
    if not args.args:
        parser.print_help()
        sys.exit(0)
    
    command = args.args[0]
    
    if command == "list":
        list_tests()
    elif command == "all":
        run_all_tests(verbose=args.verbose, model=args.model)
    elif len(args.args) == 1:
        run_agent_tests(command, verbose=args.verbose, model=args.model)
    elif len(args.args) == 2:
        run_test(args.args[0], args.args[1], verbose=args.verbose, model=args.model)
    else:
        print(f"Unknown command: {' '.join(args.args)}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
