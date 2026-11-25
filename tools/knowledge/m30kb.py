#!/usr/bin/env python3
"""Build and query a local full-text/call-edge index of curated firmware facts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(os.environ.get("M30_KNOWLEDGE_SOURCE", ROOT / "docs/knowledge/facts.jsonl"))
DATABASE = Path(os.environ.get("M30_KNOWLEDGE_DB", ROOT / "analysis/local-evidence/knowledge.sqlite"))
REQUIRED_FIELDS = {
    "function": ("id", "module", "variant", "sha256", "address", "symbol",
                 "isa", "status", "summary", "evidence", "reproduce"),
    "state": ("id", "module", "variant", "sha256", "address", "symbol",
              "width_bits", "summary", "evidence"),
    "edge": ("source", "target", "kind", "evidence"),
    "experiment": ("id", "module", "variant", "address", "status",
                   "summary", "evidence", "reproduce"),
    "hypothesis": ("id", "variant", "status", "summary", "evidence"),
}


def records():
    for line_number, line in enumerate(SOURCE.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{SOURCE}:{line_number}: {exc}")


def validate_rows(rows):
    """Fail early with a record-level error when a fact misses indexed fields."""
    for record_number, row in enumerate(rows, 1):
        kind = row.get("type")
        if kind not in REQUIRED_FIELDS:
            raise ValueError(f"fact record {record_number}: unknown type {kind!r}")
        missing = [field for field in REQUIRED_FIELDS[kind] if field not in row]
        if missing:
            identifier = row.get("id", row.get("source", "<no id>"))
            raise ValueError(
                f"fact record {record_number} ({identifier}): missing required fields: "
                + ", ".join(missing)
            )


def connect():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def fact_id(row):
    """Return a curated id or a stable id for an id-less edge record."""
    if "id" in row:
        return row["id"]
    canonical = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "edge:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build():
    rows = list(records())
    try:
        validate_rows(rows)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    facts = rows
    edges = [r for r in rows if r["type"] == "edge"]
    fact_ids = [fact_id(r) for r in facts]
    if len(fact_ids) != len(set(fact_ids)):
        raise SystemExit("duplicate fact id in facts.jsonl")
    graph_node_ids = {r["id"] for r in rows if r["type"] in ("function", "state")}
    trace_edges = [r for r in edges if r["source"] in graph_node_ids
                   and r["target"] in graph_node_ids]
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=DATABASE.name + ".", suffix=".tmp", dir=DATABASE.parent
    )
    os.close(descriptor)
    temporary_database = Path(temporary_name)
    db = sqlite3.connect(temporary_database)
    try:
        db.executescript("""
            DROP TABLE IF EXISTS fact_search;
            DROP TABLE IF EXISTS edges;
            DROP TABLE IF EXISTS facts;
            CREATE TABLE facts (
              id TEXT PRIMARY KEY, kind TEXT NOT NULL, module TEXT NOT NULL,
              variant TEXT NOT NULL, sha256 TEXT NOT NULL, address TEXT NOT NULL,
              symbol TEXT NOT NULL, isa TEXT NOT NULL, width_bits INTEGER,
              status TEXT NOT NULL, summary TEXT NOT NULL, evidence TEXT NOT NULL,
              reproduce TEXT NOT NULL, payload TEXT NOT NULL
            );
            CREATE TABLE edges (
              source TEXT NOT NULL, target TEXT NOT NULL, kind TEXT NOT NULL,
              message_id TEXT NOT NULL DEFAULT '', evidence TEXT NOT NULL,
              PRIMARY KEY (source, target, kind, message_id)
            );
            CREATE VIRTUAL TABLE fact_search USING fts5(
              id UNINDEXED, kind UNINDEXED, searchable, tokenize='unicode61'
            );
        """)
        for r in facts:
            payload = json.dumps(r, ensure_ascii=False, sort_keys=True)
            db.execute("INSERT INTO facts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                fact_id(r), r["type"], r.get("module", ""), r.get("variant", ""),
                r.get("sha256", ""), r.get("address", ""), r.get("symbol", ""),
                r.get("isa", ""), r.get("width_bits"), r.get("status", ""),
                r.get("summary", ""), r["evidence"], r.get("reproduce", ""), payload))
            searchable = " ".join(str(value) for value in r.values() if value is not None)
            db.execute("INSERT INTO fact_search VALUES (?,?,?)", (
                fact_id(r), r["type"], searchable))
        for r in trace_edges:
            db.execute("INSERT INTO edges VALUES (?,?,?,?,?)", (
                r["source"], r["target"], r["kind"], r.get("message_id", ""), r["evidence"]))
        db.commit()
    except Exception:
        db.close()
        temporary_database.unlink(missing_ok=True)
        raise
    finally:
        if db:
            db.close()
    os.replace(temporary_database, DATABASE)
    print(f"Indexed {len(facts)} facts and {len(trace_edges)} traceable edges into {DATABASE}")


def search(query: str):
    terms = re.findall(r"[\w]+", query, flags=re.UNICODE)
    if not terms:
        raise SystemExit("search query must contain at least one word or address")
    # OR keeps mixed queries useful when terms describe different nodes in a
    # call path; bm25 ranks records matching the greatest number of terms.
    match = " OR ".join('"' + t.replace('"', '""') + '"' for t in terms)
    with connect() as db:
        rows = db.execute("""
            SELECT fact_search.id, fact_search.kind, snippet(fact_search, 2, '[', ']', '…', 16) AS excerpt,
                   f.address, f.symbol, f.module, f.status
            FROM fact_search
            LEFT JOIN facts f USING (id)
            WHERE fact_search MATCH ? ORDER BY bm25(fact_search) LIMIT 30
        """, (match,)).fetchall()
    for row in rows:
        print(f"{row['address']} {row['symbol']} [{row['kind']} / {row['module']} / {row['status']}]\n  {row['excerpt']}\n  {row['id']}")
    if not rows:
        print("No matching indexed facts.")


def resolve(db, key, graph_node_only=False):
    graph_filter = " AND kind IN ('function', 'state')" if graph_node_only else ""
    row = db.execute(f"""SELECT * FROM facts WHERE (lower(id)=lower(?)
                         OR (address != '' AND lower(address)=lower(?))
                         OR (symbol != '' AND lower(symbol)=lower(?)))
                         {graph_filter} LIMIT 1""",
                     (key, key, key)).fetchone()
    if row is None:
        try:
            address = f"0x{(int(key, 0) & ~1):08x}"
            row = db.execute(f"SELECT * FROM facts WHERE lower(address)=lower(?) {graph_filter}",
                             (address,)).fetchone()
        except ValueError:
            pass
    return row


def show(key):
    with connect() as db:
        row = resolve(db, key)
        if row is None:
            raise SystemExit(f"fact not indexed: {key}")
        payload = json.loads(row["payload"])
        if "id" not in payload:
            print(f"fact_id: {row['id']}")
        for field, value in payload.items():
            print(f"{field}: {value}")
        for edge in db.execute("""SELECT kind, message_id, target AS other FROM edges WHERE source=?
                                  UNION ALL SELECT kind, message_id, source AS other FROM edges WHERE target=?""",
                               (row["id"], row["id"])):
            print(f"edge: {edge['kind']} {edge['message_id']} {edge['other']}")


def trace(start, target):
    with connect() as db:
        a, b = resolve(db, start, graph_node_only=True), resolve(db, target, graph_node_only=True)
        if a is None or b is None:
            raise SystemExit(f"unindexed endpoint: {start if a is None else target}")
        route = db.execute("""
            WITH RECURSIVE walk(node, route, depth) AS (
              SELECT ?, ?, 0
              UNION ALL
              SELECT e.target, walk.route || char(10) || e.kind || ' ' || e.message_id || ' ' || e.target,
                     walk.depth + 1
              FROM walk JOIN edges e ON e.source=walk.node
              WHERE walk.depth < 20 AND instr(walk.route, e.target)=0
            )
            SELECT route FROM walk WHERE node=? ORDER BY depth LIMIT 1
        """, (a["id"], a["id"], b["id"])).fetchone()
        if route is None:
            print("No indexed path.")
        else:
            print(route["route"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("rebuild", help="rebuild ignored SQLite FTS/edge database from curated JSONL")
    p = sub.add_parser("search", help="full-text search summaries and evidence")
    p.add_argument("query")
    p = sub.add_parser("show", help="show a fact by address, symbol, or stable id")
    p.add_argument("fact")
    p = sub.add_parser("trace", help="find a directed path through indexed call/message edges")
    p.add_argument("start")
    p.add_argument("target")
    args = parser.parse_args()
    if args.command == "rebuild":
        build()
    elif args.command == "search":
        search(args.query)
    elif args.command == "show":
        show(args.fact)
    else:
        trace(args.start, args.target)


if __name__ == "__main__":
    main()
