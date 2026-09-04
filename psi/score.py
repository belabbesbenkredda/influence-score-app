"""Stage 5 — Score items (topic + Logos/Ethos/Pathos) with the Claude API.

One call per item, model `claude-sonnet-5` (override with PSI_SCORE_MODEL),
strict JSON via structured outputs, concurrency <= 5, retries with backoff,
resume-safe (already-scored items are skipped). Raw JSON, model, prompt
version, token usage and cost are stored per item.

Note on temperature: the brief asks for temperature 0. Sonnet 5 rejects the
`temperature` parameter (HTTP 400), so it is omitted; structured output plus
a fixed rubric is the reproducibility lever we have.

Requires PSI_API_KEY. Without it the stage stops with a clear message and
appends the error to RUNLOG.md, as the brief asks.
"""
from __future__ import annotations

import json
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from psi import db

MODEL = os.environ.get("PSI_SCORE_MODEL", "claude-sonnet-5")
PROMPT_VERSION = os.environ.get("PSI_PROMPT_VERSION", "score_v2")
PROMPT_PATH = db.ROOT / "psi" / "prompts" / f"{PROMPT_VERSION}.md"
CONCURRENCY = 5
MAX_RETRIES = 4
MAX_WORDS = 6000            # items longer than this are truncated and flagged text_truncated=1
MAX_SPEND_USD = float(os.environ.get("PSI_MAX_SPEND", "20"))
EFFORT = os.environ.get("PSI_SCORE_EFFORT", "medium")
LIMIT = int(os.environ.get("PSI_SCORE_LIMIT", "0"))   # 0 = no limit; handy for smoke tests

# USD per million tokens: input, output, cache write (5m), cache read
PRICES = {
    "claude-sonnet-5": (2.00, 10.00, 2.50, 0.20),
    "claude-opus-5": (5.00, 25.00, 6.25, 0.50),
    "claude-haiku-4-5": (1.00, 5.00, 1.25, 0.10),
}

_lock = threading.Lock()
_spent = {"usd": 0.0}


def cost_usd(model: str, usage) -> float:
    p = PRICES.get(model) or PRICES["claude-sonnet-5"]
    cw = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cr = getattr(usage, "cache_read_input_tokens", 0) or 0
    return (usage.input_tokens * p[0] + usage.output_tokens * p[1] + cw * p[2] + cr * p[3]) / 1e6


def build_schema(topics: list[str]) -> dict:
    """v1 returns one topic; v2 returns proportional shares across topics."""
    lep = {k: {"type": "integer", "enum": list(range(11))} for k in ("logos", "ethos", "pathos")}
    if PROMPT_VERSION == "score_v1":
        return {"type": "object",
                "properties": {"topic": {"type": "string", "enum": topics}, **lep, "justification": {"type": "string"}},
                "required": ["topic", "logos", "ethos", "pathos", "justification"], "additionalProperties": False}
    return {
        "type": "object",
        "properties": {
            "topics": {
                "type": "array",
                "description": ("How the item's substance divides across topics, as proportions summing to about 1.0. "
                                "Include only topics with a share of 0.05 or more; most items have two to four."),
                "items": {"type": "object",
                          "properties": {"topic": {"type": "string", "enum": topics},
                                         "share": {"type": "number"}},
                          "required": ["topic", "share"], "additionalProperties": False},
            },
            **lep,
            "justification": {"type": "string"},
        },
        "required": ["topics", "logos", "ethos", "pathos", "justification"],
        "additionalProperties": False,
    }


def build_system(rubric: str, mip_rows: list[dict]) -> str:
    lines = ["", "## Topic ids (from Gallup 'Most Important Problem', %s)" % (mip_rows[0]["survey_date"] if mip_rows else "n/a"), ""]
    for r in mip_rows:
        lines.append(f"- `{r['topic']}` — {r['label']}. Gallup categories: {r['gallup_categories']}")
    return rubric.rstrip() + "\n" + "\n".join(lines) + "\n"


def item_prompt(item: dict) -> tuple[str, bool]:
    text = item["text"] or ""
    if item.get("content_basis") == "summary_only":
        text = ("[THIS IS A HEADLINE AND SUMMARY ONLY — the outlet's full article is paywalled. "
                "Score what is present; a summary carries less argument than an article, and that is a fact "
                "about our access, not about the outlet.]\n\n") + text
    ws = text.split()
    truncated = False
    if len(ws) > MAX_WORDS:
        text = " ".join(ws[:MAX_WORDS]) + "\n\n[TEXT TRUNCATED AT %d WORDS]" % MAX_WORDS
        truncated = True
    return f"TITLE: {item['title'] or '(untitled)'}\nPUBLISHED: {item['published_at'] or 'unknown'}\n\nTEXT:\n{text}", truncated


def score_one(client, item: dict, system_blocks, schema: dict) -> dict:
    import anthropic

    user_text, truncated = item_prompt(item)
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=2048,
                system=system_blocks,
                messages=[{"role": "user", "content": user_text}],
                output_config={"format": {"type": "json_schema", "schema": schema}, "effort": EFFORT},
            )
            if resp.stop_reason == "refusal":
                raise RuntimeError(f"refusal: {getattr(resp, 'stop_details', None)}")
            raw = next(b.text for b in resp.content if b.type == "text")
            data = json.loads(raw)
            for k in ("logos", "ethos", "pathos"):
                data[k] = max(0, min(10, int(data[k])))
            if PROMPT_VERSION == "score_v1":
                shares = {data["topic"]: 1.0}
            else:
                shares = {}
                for t in data["topics"]:
                    share = float(t["share"])
                    if share < 0.05:          # the rubric's floor, enforced here since the schema cannot
                        continue
                    shares[t["topic"]] = shares.get(t["topic"], 0.0) + share
                if len(shares) > 6:           # keep the six largest
                    shares = dict(sorted(shares.items(), key=lambda kv: -kv[1])[:6])
                total = sum(shares.values())
                if total <= 0:
                    raise ValueError("topic shares sum to zero")
                shares = {k: v / total for k, v in shares.items()}   # normalise to exactly 1
            usage = resp.usage
            usd = cost_usd(MODEL, usage)
            return {
                "item_id": item["item_id"], "shares": shares, "logos": data["logos"], "ethos": data["ethos"],
                "pathos": data["pathos"], "d": data["logos"] + data["ethos"] + data["pathos"],
                "justification": data["justification"][:600], "raw_json": raw, "model": resp.model,
                "prompt_version": PROMPT_VERSION, "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
                "cache_read_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
                "cache_write_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
                "cost_usd": usd, "text_truncated": int(truncated), "scored_at": datetime.now(timezone.utc).isoformat(),
            }
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError) as exc:
            last_exc = exc
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                last_exc = exc
            else:
                raise
        except (json.JSONDecodeError, StopIteration, KeyError, ValueError, RuntimeError) as exc:
            last_exc = exc
        delay = min(2 ** attempt + random.uniform(0, 1), 30)
        time.sleep(delay)
    raise RuntimeError(f"gave up after {MAX_RETRIES} attempts: {type(last_exc).__name__}: {last_exc}")


def run() -> None:
    api_key = os.environ.get("PSI_API_KEY")
    if not api_key:
        msg = "PSI_API_KEY is not set. Scoring stopped after Stage 4 (everything before scoring is done)."
        with open(db.ROOT / "RUNLOG.md", "a", encoding="utf-8") as f:
            f.write(f"\n## {datetime.now(timezone.utc).isoformat()} — Stage 5 blocked\n\n{msg}\n")
        raise SystemExit(msg)
    import anthropic

    client = anthropic.Anthropic(api_key=api_key, max_retries=2, timeout=180.0)
    rubric = PROMPT_PATH.read_text(encoding="utf-8")

    with db.db() as con:
        mip_rows = db.rows(con, "SELECT * FROM mip WHERE country=? ORDER BY mip_share DESC", (db.COUNTRY,))
        # labels live in data/mip_table.csv; join them in for the prompt
        labels = {}
        import csv
        with open(db.DATA / "mip_table.csv", newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                labels[r["topic"]] = r["label"]
        for r in mip_rows:
            r["label"] = labels.get(r["topic"], r["topic"])
        todo = db.rows(con, """SELECT i.* FROM items i
                               LEFT JOIN scores2 s ON s.item_id=i.item_id AND s.prompt_version=?
                               WHERE i.country=? AND s.item_id IS NULL
                                 AND i.word_count >= (CASE WHEN i.content_basis='summary_only' THEN 28 ELSE 300 END)
                               ORDER BY i.outlet_id, i.published_at""", (PROMPT_VERSION, db.COUNTRY))
        already = con.execute("SELECT COUNT(*), COALESCE(SUM(cost_usd),0) FROM scores2 WHERE prompt_version=?",
                              (PROMPT_VERSION,)).fetchone()
    if not mip_rows:
        raise SystemExit("No MIP topics in DB; run `python run.py salience` first.")
    if os.environ.get("PSI_SCORE_LIMIT"):
        todo = todo[: int(os.environ["PSI_SCORE_LIMIT"])]
        print(f"  PSI_SCORE_LIMIT: scoring only the first {len(todo)} items")
    topics = [r["topic"] for r in mip_rows]
    schema = build_schema(topics)
    system_blocks = [{"type": "text", "text": build_system(rubric, mip_rows), "cache_control": {"type": "ephemeral"}}]
    print(f"  model={MODEL} effort={EFFORT} prompt={PROMPT_VERSION}; {already[0]} already scored (${already[1]:.2f}); {len(todo)} to score")
    if LIMIT:
        todo = todo[:LIMIT]
        print(f"  PSI_SCORE_LIMIT={LIMIT}: scoring only the first {len(todo)} items")
    if not todo:
        return

    done, failed = 0, 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futs = {}
        for it in todo:
            futs[pool.submit(score_one, client, it, system_blocks, schema)] = it
        for fut in as_completed(futs):
            it = futs[fut]
            try:
                rec = fut.result()
            except Exception as exc:
                failed += 1
                print(f"    FAIL {it['item_id']} ({it['outlet_id']}): {str(exc)[:160]}")
                continue
            with _lock:
                _spent["usd"] += rec["cost_usd"]
                spent = _spent["usd"]
            shares = rec.pop("shares")
            with db.db() as con:
                db.upsert(con, "scores2", rec, ["item_id", "prompt_version"])
                con.execute("DELETE FROM item_topics WHERE item_id=? AND prompt_version=?", (rec["item_id"], PROMPT_VERSION))
                for topic, share in shares.items():
                    db.upsert(con, "item_topics", {"item_id": rec["item_id"], "prompt_version": PROMPT_VERSION,
                                                   "topic": topic, "share": round(share, 4)},
                              ["item_id", "prompt_version", "topic"])
            done += 1
            if done % 25 == 0:
                print(f"    {done}/{len(todo)} scored, ${spent:.2f} this run, {time.time()-t0:.0f}s")
            if spent + already[1] > MAX_SPEND_USD:
                print(f"  spend guard hit (${spent + already[1]:.2f} > ${MAX_SPEND_USD}); cancelling remaining items")
                for f2 in futs:
                    f2.cancel()
                break

    with db.db() as con:
        n, total = con.execute("SELECT COUNT(*), COALESCE(SUM(cost_usd),0) FROM scores2 WHERE prompt_version=?",
                               (PROMPT_VERSION,)).fetchone()
        db.set_meta(con, "score_run", {"at": datetime.now(timezone.utc).isoformat(), "model": MODEL, "effort": EFFORT,
                                       "prompt_version": PROMPT_VERSION, "scored_this_run": done, "failed": failed,
                                       "spend_this_run_usd": round(_spent["usd"], 4), "spend_total_usd": round(total, 4)})
    print(f"  scored {done} (failed {failed}) in {time.time()-t0:.0f}s; ${_spent['usd']:.2f} this run; {n} total scored, ${total:.2f} total spend")


if __name__ == "__main__":
    run()
