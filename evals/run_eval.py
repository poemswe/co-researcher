#!/usr/bin/env python3
import sys

# Evaluation entrypoints are read-only until a selected command explicitly
# publishes output; imports must not create cache artifacts during an audit.
sys.dont_write_bytecode = True

import argparse
import json
import tempfile
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
REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_CASES_DIR = EVALS_DIR / "test-cases"
RESULTS_DIR = EVALS_DIR / "results"
PRINT_LOCK = threading.Lock()
INTEGRITY_CAPABILITY = "literature-review-integrity"


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

        result = execute_agent(
            tc.implementation_skill, tc.task_prompt, tc.timeout, model)
        
        if not result.success:
            with PRINT_LOCK:
                print(f"[{tc.agent}] {tc.name} failed: {result.error}")
            return None
        
        report = evaluate_output(tc, result, model)
        if report.judge_output.startswith("Judge error:"):
            with PRINT_LOCK:
                print(f"[{tc.agent}] {tc.name} failed: {report.judge_output}")
            return None
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


def _test_slug(name: str) -> str:
    return name.lower().replace(" ", "-")


def run_all_tests(model: str, verbose: bool = False, jobs: int = 1,
                  skip=frozenset()):
    tests = [tc for tc in discover_tests(TEST_CASES_DIR)
             if (tc.agent, _test_slug(tc.name)) not in skip]
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
        if agent_dir.name == INTEGRITY_CAPABILITY:
            tests = [
                path.parent.name
                for path in sorted(
                    agent_dir.rglob("case.json"),
                    key=lambda value: value.relative_to(
                        agent_dir).as_posix().encode("utf-8"))
                if path.is_file()
            ]
        else:
            tests = [f.stem.replace("test-", "") for f in sorted(agent_dir.glob("test-*.md"))]
        if tests:
            print(f"  {agent_dir.name}")
            for test in tests:
                print(f"    - {test}")
            print()


def run_literature_integrity(model: str, resume: str | None = None):
    """Run the integrity eval; ``resume`` carries a prior run's finished cases."""
    from lib.literature_integrity import (
        LiteratureIntegrityRunner,
        ModelExecutionError,
        OperationalIntegrityEvalResult,
        ProductionModelExecutor,
        ProductionQualityJudge,
        load_adversarial_scores,
        load_cases,
    )
    from lib.run_reports import (
        CombinedRunResult, load_completed_cases, write_run_report)
    from review_integrity.reporting import ENGINE_VERSION, VALIDATOR_VERSIONS
    from validate_review import git_provenance

    target_commit, target_dirty = git_provenance(EVALS_DIR.parent)
    provenance = {
        "target_commit": target_commit,
        "target_dirty": target_dirty,
        "engine_version": ENGINE_VERSION,
        "validator_versions": dict(VALIDATOR_VERSIONS),
    }
    carried = []
    resolved_models = set()
    if resume is not None:
        prior, carried = load_completed_cases(RESULTS_DIR, resume)
        prior_provenance = prior.get("provenance") or {}
        if (prior["model"] != model or target_commit is None or target_dirty
                or prior_provenance.get("target_commit") != target_commit
                or prior_provenance.get("target_dirty") is not False):
            raise RuntimeError(
                f"cannot resume {resume}: a resumed run must use the same "
                "model and the same clean commit as the run it continues")
        resolved_models.update(prior_provenance.get("resolved_models", []))
        provenance["resumed_from"] = prior["run_id"]
    carried_ids = {case_id for case_id, *_rest in carried}
    all_cases = load_cases(TEST_CASES_DIR / INTEGRITY_CAPABILITY)
    cases = tuple(case for case in all_cases if case.case_id not in carried_ids)
    run_id = generate_run_id()
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    executor = ProductionModelExecutor(model, EVALS_DIR.parent)
    runner = LiteratureIntegrityRunner(
        executor,
        ProductionQualityJudge(model),
        scorecard_directory=TEST_CASES_DIR / INTEGRITY_CAPABILITY,
    )
    completed = []
    execution_errors = []
    for case in cases:
        try:
            completed.append((case, runner.run_case(case)))
        except ModelExecutionError as exc:
            execution_errors.append(
                {"case_id": case.case_id, "message": str(exc)})
            print(f"{case.case_id}: not evaluated: {exc}")
    if not completed and not carried:
        raise RuntimeError(
            "no case completed; every model call failed, so no report was "
            "written")
    adversarial_scores = {
        case_id: score for case_id, _result, score, _snapshots in carried
        if score is not None}
    if completed:
        adversarial_scores.update(load_adversarial_scores(
            TEST_CASES_DIR / INTEGRITY_CAPABILITY,
            {case.case_id: result for case, result in completed},
            domains={case.case_id: case.domain for case, _result in completed},
            fixture_preserved=runner.fixture_preserved,
        ))
    results_by_case = {
        case_id: result for case_id, result, _score, _snapshots in carried}
    results_by_case.update(
        (case.case_id, result) for case, result in completed)
    snapshots = {
        case_id: case_snapshots
        for case_id, _result, _score, case_snapshots in carried
        if case_snapshots}
    snapshots.update(
        (case.case_id, runner.snapshots[case.case_id])
        for case, _result in completed if case.case_id in runner.snapshots)
    ordered = tuple(
        (case, results_by_case[case.case_id]) for case in all_cases
        if case.case_id in results_by_case)
    provenance["resolved_models"] = sorted(
        resolved_models | executor.resolved_models)
    combined = CombinedRunResult.from_results(
        run_id=run_id,
        timestamp=timestamp,
        model=model,
        results=tuple((case.case_id, result) for case, result in ordered),
        adversarial_scores=adversarial_scores,
        provenance=provenance,
        execution_errors=execution_errors,
    )
    run_directory = write_run_report(combined, RESULTS_DIR, snapshots=snapshots)
    results = tuple(result for _case, result in ordered)
    for case, result in ordered:
        if isinstance(result, OperationalIntegrityEvalResult):
            failure = result.operational_failure
            print(
                f"{case.case_id}: integrity=N/A status=invalid quality=N/A "
                f"repairs={len(result.repair_rounds)} "
                f"operational_failure={failure.reason_code.value} "
                f"artifact={failure.artifact}"
            )
            continue
        final = result.system_final
        quality = final.quality.quality_score
        quality_text = "ERROR" if quality is None else f"{quality:.1f}"
        print(
            f"{case.case_id}: integrity={final.integrity.integrity_score:.1f} "
            f"status={final.integrity.status.value} quality={quality_text} "
            f"repairs={len(result.repair_rounds)}"
        )
    print(f"Run artifacts: {run_directory}")
    return results


def generate_run_id() -> str:
    """Generate unique run ID: run_YYYYMMDD_HHMMSS_microseconds."""
    return datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S_%f")


def extract_model_version(model: str) -> str:
    """Return the requested version, or cli-default when none was given."""
    if ":" in model:
        return model.split(":", 1)[1].strip()
    return "cli-default"


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


def _local_path_prefixes():
    temp = Path(tempfile.gettempdir())
    prefixes = [
        (str(REPO_ROOT), "<repo>"),
        (str(temp.resolve()), "<tmp>"),
        (str(temp), "<tmp>"),
        (str(Path.home()), "~"),
    ]
    return sorted(set(prefixes), key=lambda item: len(item[0]), reverse=True)


def redact_local_paths(value, prefixes=None):
    prefixes = prefixes or _local_path_prefixes()
    if isinstance(value, str):
        for prefix, placeholder in prefixes:
            value = value.replace(prefix, placeholder)
        return value
    if isinstance(value, dict):
        return {key: redact_local_paths(item, prefixes) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_local_paths(item, prefixes) for item in value]
    return value


def plugin_release() -> str:
    plugin = json.loads((REPO_ROOT / ".claude-plugin/plugin.json").read_text())
    return plugin["version"]


def save_benchmark_v2(reports, model: str, run_id: str, previous_results=()):
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
        "release": plugin_release(),
        "test_results": []
    }
    
    for rpt in reports:
        if not rpt:
            continue
        
        test_id = f"{model.split(':')[0]}_{rpt.test_case.agent}_{rpt.test_case.name.lower().replace(' ', '-')}_{run_id.split('_')[-2]}"
        
        test_result = {
            "id": test_id,
            "agent": rpt.test_case.agent,
            "implementation_skill": rpt.test_case.implementation_skill,
            "test_case": _test_slug(rpt.test_case.name),
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
    detail_data["test_results"] = [*previous_results, *detail_data["test_results"]]
    
    detail_file.write_text(json.dumps(redact_local_paths(detail_data), indent=2))
    
    # 2. Update overview file
    overview_file = EVALS_DIR / "benchmark_overview.json"
    overview = {"schema_version": "2.0", "runs": [], "summary_stats": {}}
    
    if overview_file.exists():
        overview = json.loads(overview_file.read_text())
    
    results = detail_data["test_results"]
    scores = [result["score"] for result in results]
    avg_score = sum(scores) / len(scores) if scores else 0
    passed_count = sum(1 for result in results if result["passed"])
    total_count = len(results)
    
    run_entry = {
        "run_id": run_id,
        "timestamp": timestamp,
        "model": model,
        "model_version": detail_data["model_version"],
        "release": detail_data["release"],
        "tests_run": total_count,
        "tests_passed": passed_count,
        "average_score": round(avg_score, 1),
        "scores_by_agent": {},
        "pass_rate": round((passed_count / total_count * 100), 1) if total_count > 0 else 0,
        "detail_file": f"test_results_detail/{run_id}.json"
    }
    
    for result in results:
        run_entry["scores_by_agent"].setdefault(result["agent"], []).append(result["score"])

    overview["runs"] = [run for run in overview["runs"] if run["run_id"] != run_id]
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
    print(f"   Evals dashboard: file://{EVALS_DIR.absolute()}/index.html")
    
    # Trend
    if len(overview["runs"]) > 1:
        prev = overview["runs"][-2]
        delta = run_entry["average_score"] - prev["average_score"]
        trend = "↑" if delta > 0 else "↓" if delta < 0 else "→"
        print(f"   Score trend: {prev['average_score']:.1f} {trend} {run_entry['average_score']:.1f} ({delta:+.1f})")


def main(argv=None):
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "args", nargs="*",
        help="[list|all|literature-review-integrity|agent|agent test]",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-m", "--model", default="claude", help="Model (default: claude)")
    parser.add_argument("-j", "--jobs", type=int, default=1, help="Parallel jobs (default: 1)")
    parser.add_argument("--check-prompts", action="store_true", help="Validate all agent prompt files exist")
    parser.add_argument("--no-benchmark", action="store_true", help="Skip saving to benchmark_history.json")
    parser.add_argument(
        "--official-cases-dir", type=Path, metavar="PATH",
        help=("Runtime-supplied committed cases (literature integrity "
              "manifest audit only)"),
    )
    parser.add_argument(
        "--resume", metavar="RUN_ID",
        help="Re-run only the cases RUN_ID did not evaluate and write one "
             "complete run (same model required; integrity also requires the "
             "same clean commit)")
    parser.add_argument(
        "--dry-run-manifest-audit", action="store_true",
        help="Verify committed manifests without executing or scoring cases",
    )
    
    args = parser.parse_args(argv)

    audit_requested = (
        args.official_cases_dir is not None or args.dry_run_manifest_audit)
    if args.resume is not None and (
            audit_requested or args.check_prompts
            or args.args not in ([INTEGRITY_CAPABILITY], ["all"])):
        parser.error(
            "--resume is only valid for an all or literature-review-integrity run")
    if audit_requested:
        if (
            args.check_prompts
            or len(args.args) != 1
            or args.args[0] != INTEGRITY_CAPABILITY
        ):
            parser.error(
                "official manifest audit options are only valid for "
                "literature-review-integrity")
        if args.official_cases_dir is None:
            parser.error(
                "--dry-run-manifest-audit requires --official-cases-dir PATH")
        if not args.dry_run_manifest_audit:
            parser.error(
                "--official-cases-dir requires --dry-run-manifest-audit; "
                "runtime-supplied case execution is not implemented")
    
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

    if audit_requested:
        from lib.committed_manifest_audit import (
            ManifestAuditError,
            audit_committed_manifests,
        )
        try:
            audit = audit_committed_manifests(args.official_cases_dir)
        except ManifestAuditError as exc:
            print(f"manifest audit failed: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(
            audit, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False))
        return 0
    
    if command == "list":
        list_tests()
    elif command == INTEGRITY_CAPABILITY:
        run_literature_integrity(args.model, resume=args.resume)
    elif command == "all":
        previous = []
        if args.resume is not None:
            detail_file = EVALS_DIR / "test_results_detail" / f"{args.resume}.json"
            if not detail_file.is_file():
                print(f"cannot resume {args.resume}: no such broad run", file=sys.stderr)
                sys.exit(2)
            prior = json.loads(detail_file.read_text())
            if prior["model"] != args.model:
                print(f"cannot resume {args.resume}: a resumed run must use the "
                      f"same model ({prior['model']})", file=sys.stderr)
                sys.exit(2)
            previous = prior["test_results"]
        run_id = args.resume or generate_run_id()
        done = {(result["agent"], result["test_case"]) for result in previous}
        reports = run_all_tests(args.model, args.verbose, args.jobs, skip=done)
        if (reports or previous) and not args.no_benchmark:
            save_benchmark_v2(reports, args.model, run_id, previous_results=previous)
        total = len(discover_tests(TEST_CASES_DIR))
        missing = total - len(previous) - len(reports)
        if missing:
            print(f"\n{missing} of {total} tests did not run. Resume with: "
                  f"run_eval.py all -m \"{args.model}\" --resume {run_id}")
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
    raise SystemExit(main())
