"""Stage runner for the PSI Influence Engine.

    python run.py <stage>     one stage: outlets | reach | salience | sample | score | aggregate | report
    python run.py all         every stage in order (scoring is resume-safe)
    python run.py status      row counts per table

Set PSI_API_KEY for scoring. Everything before `score` runs without it.
"""
from __future__ import annotations

import importlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

STAGES = ["outlets", "reach", "salience", "sample", "signals", "score", "aggregate", "report"]


def run_stage(name: str) -> None:
    mod = importlib.import_module(f"psi.{name}")
    t0 = time.time()
    print(f"\n=== Stage: {name} ===")
    mod.run()
    print(f"=== {name} done in {time.time() - t0:.1f}s ===")


def status() -> None:
    from psi import db

    with db.db() as con:
        for t in ["outlets", "reach", "type_weights", "mip", "mip_raw", "items", "fetch_log", "item_signals",
                  "scores", "scores2", "item_topics", "item_scores", "outlet_scores"]:
            n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"{t:15s} {n}")


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in {"-h", "--help"}:
        print(__doc__)
        return 0
    target = argv[1]
    if target == "status":
        status()
        return 0
    if target == "all":
        for s in STAGES:
            run_stage(s)
        return 0
    if target not in STAGES:
        print(f"unknown stage {target!r}; choose from {STAGES + ['all', 'status']}")
        return 2
    run_stage(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
