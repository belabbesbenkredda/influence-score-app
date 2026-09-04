"""What changed between rubric v1 and v2, for the items scored under both.

Two errors were being corrected: ethos scored as fairness rather than as the
speaker's standing with their audience, and one topic per item rather than
proportional shares. This prints the effect of each, so the change can be
argued with rather than taken on trust.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from psi import db  # noqa: E402


def run() -> None:
    with db.db() as con:
        pairs = db.rows(con, """
            SELECT v1.item_id, o.name AS outlet, o.type, substr(i.title,1,52) AS title,
                   v1.logos l1, v1.ethos e1, v1.pathos p1, v1.d d1,
                   v2.logos l2, v2.ethos e2, v2.pathos p2, v2.d d2
            FROM scores v1
            JOIN scores2 v2 ON v2.item_id = v1.item_id AND v2.prompt_version = 'score_v2'
            JOIN items i ON i.item_id = v1.item_id
            JOIN outlets o ON o.outlet_id = i.outlet_id""")
        if not pairs:
            print("  no items scored under both versions yet")
            return

        n = len(pairs)
        def mean(k):
            return sum(r[k] for r in pairs) / n
        print(f"  {n} items scored under both rubrics\n")
        print(f"  {'':16s} {'v1':>6s} {'v2':>6s} {'change':>8s}")
        for label, a, b in (("logos", "l1", "l2"), ("ethos", "e1", "e2"), ("pathos", "p1", "p2"), ("D (0-30)", "d1", "d2")):
            print(f"  {label:16s} {mean(a):6.2f} {mean(b):6.2f} {mean(b)-mean(a):+8.2f}")

        print("\n  Ethos change by outlet type (the error was suppressing partisan voices):")
        by_type = {}
        for r in pairs:
            by_type.setdefault(r["type"], []).append(r["e2"] - r["e1"])
        for t, deltas in sorted(by_type.items(), key=lambda kv: -sum(kv[1]) / len(kv[1])):
            print(f"    {t:16s} {sum(deltas)/len(deltas):+5.2f}  (n={len(deltas)})")

        print("\n  Largest ethos gains — outlets the old rubric penalised for partisanship:")
        for r in sorted(pairs, key=lambda r: -(r["e2"] - r["e1"]))[:10]:
            print(f"    {r['e1']:2d} -> {r['e2']:2d}  {r['outlet'][:24]:24s} {r['title']}")

        print("\n  Largest ethos falls:")
        for r in sorted(pairs, key=lambda r: (r["e2"] - r["e1"]))[:5]:
            print(f"    {r['e1']:2d} -> {r['e2']:2d}  {r['outlet'][:24]:24s} {r['title']}")

        # topic coverage: single label vs proportional mass
        print("\n  Topic coverage: v1 item counts vs v2 proportional mass")
        v1 = {r["topic"]: r["n"] for r in db.rows(con, "SELECT topic, COUNT(*) n FROM scores GROUP BY topic")}
        v2 = {r["topic"]: r["m"] for r in db.rows(con,
              "SELECT topic, SUM(share) m FROM item_topics WHERE prompt_version='score_v2' GROUP BY topic")}
        t1, t2 = sum(v1.values()) or 1, sum(v2.values()) or 1
        keys = sorted(set(v1) | set(v2), key=lambda k: -(v2.get(k, 0) / t2))
        print(f"    {'topic':26s} {'v1 %':>7s} {'v2 %':>7s} {'change':>8s}")
        for k in keys:
            a, b = 100 * v1.get(k, 0) / t1, 100 * v2.get(k, 0) / t2
            print(f"    {k:26s} {a:6.1f}% {b:6.1f}% {b-a:+7.1f}")
        print(f"\n    topics per item: v1 1.00, v2 {sum(v2.values()) / len(set(r['item_id'] for r in pairs)):.2f}")


if __name__ == "__main__":
    run()
