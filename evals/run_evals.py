from __future__ import annotations

import json
import time
from pathlib import Path

from datapilot import AgenticAnalyst, DataWorkspace
from datapilot.sample_data import build_sample_tables


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    cases = json.loads((root / "evals" / "cases.json").read_text(encoding="utf-8"))
    analyst = AgenticAnalyst(DataWorkspace(build_sample_tables()))
    results = []

    for case in cases:
        started = time.perf_counter()
        try:
            result = analyst.analyze(case["question"])
            sql_lower = result.sql.lower()
            columns_lower = " ".join(result.columns).lower()
            terms_pass = all(term.lower() in sql_lower for term in case["required_terms"])
            columns_pass = any(term.lower() in columns_lower for term in case["expected_columns_any"])
            results.append(
                {
                    "id": case["id"],
                    "success": terms_pass and columns_pass and bool(result.rows),
                    "terms_pass": terms_pass,
                    "columns_pass": columns_pass,
                    "non_empty": bool(result.rows),
                    "attempts": result.attempts,
                    "latency_seconds": round(time.perf_counter() - started, 2),
                    "sql": result.sql,
                }
            )
        except Exception as exc:
            results.append({"id": case["id"], "success": False, "error": str(exc)})

    output_dir = root / "eval_results"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "latest.json"
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    passed = sum(item["success"] for item in results)
    print(f"Passed {passed}/{len(results)} cases. Results: {output_path}")
    raise SystemExit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()

