#!/usr/bin/env python3
"""Build and query a local full-text/call-edge index of curated firmware facts."""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(os.environ.get("M30_KNOWLEDGE_SOURCE", ROOT / "docs/knowledge/facts.jsonl"))
DATABASE = Path(os.environ.get("M30_KNOWLEDGE_DB", ROOT / "analysis/local-evidence/knowledge.sqlite"))


def records():
    for line_number, line in enumerate(SOURCE.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{SOURCE}:{line_number}: {exc}")


def connect():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def build():
    rows = list(records())
    functions = [r for r in rows if r["type"] == "function"]
    states = [r for r in rows if r["type"] == "state"]
    edges = [r for r in rows if r["type"] == "edge"]
    if len(functions) + len(states) + len(edges) != len(rows):
        raise SystemExit("unknown record type in facts.jsonl")
    entity_ids = [r["id"] for r in functions + states]
    if len(entity_ids) != len(set(entity_ids)):
        raise SystemExit("duplicate function/state id in facts.jsonl")
    known_ids = set(entity_ids)
    dangling = sorted({endpoint for r in edges for endpoint in (r["source"], r["target"])
                       if endpoint not in known_ids})
    if dangling:
        raise SystemExit("edge endpoint not defined as a function/state: " + ", ".join(dangling))
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
            DROP TABLE IF EXISTS states;
            DROP TABLE IF EXISTS functions;
            CREATE TABLE functions (
              id TEXT PRIMARY KEY, module TEXT NOT NULL, variant TEXT NOT NULL,
              sha256 TEXT NOT NULL, address TEXT NOT NULL, symbol TEXT NOT NULL,
              isa TEXT NOT NULL, status TEXT NOT NULL, summary TEXT NOT NULL,
              evidence TEXT NOT NULL, reproduce TEXT NOT NULL
            );
            CREATE TABLE edges (
              source TEXT NOT NULL, target TEXT NOT NULL, kind TEXT NOT NULL,
              message_id TEXT NOT NULL DEFAULT '', evidence TEXT NOT NULL,
              PRIMARY KEY (source, target, kind, message_id)
            );
            CREATE TABLE states (
              id TEXT PRIMARY KEY, module TEXT NOT NULL, variant TEXT NOT NULL,
              sha256 TEXT NOT NULL, address TEXT NOT NULL, symbol TEXT NOT NULL,
              width_bits INTEGER NOT NULL, summary TEXT NOT NULL, evidence TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE fact_search USING fts5(
              id UNINDEXED, kind UNINDEXED, searchable, tokenize='unicode61'
            );
        """)
        for r in functions:
            db.execute("INSERT INTO functions VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                r["id"], r["module"], r["variant"], r["sha256"], r["address"],
                r["symbol"], r["isa"], r["status"], r["summary"], r["evidence"], r["reproduce"]))
            db.execute("INSERT INTO fact_search VALUES (?,?,?)", (
                r["id"], "function", " ".join((r["id"], r["module"], r["variant"], r["address"],
                                   r["symbol"], r["isa"], r["status"], r["summary"],
                                   r["evidence"], r["reproduce"]))))
        for r in states:
            db.execute("INSERT INTO states VALUES (?,?,?,?,?,?,?,?,?)", (
                r["id"], r["module"], r["variant"], r["sha256"], r["address"],
                r["symbol"], r["width_bits"], r["summary"], r["evidence"]))
            db.execute("INSERT INTO fact_search VALUES (?,?,?)", (
                r["id"], "state", " ".join((r["id"], r["module"], r["variant"],
                                               r["address"], r["symbol"], r["summary"], r["evidence"]))))
        for r in edges:
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
    print(f"Indexed {len(functions)} functions, {len(states)} state fields, and {len(edges)} edges into {DATABASE}")


def search(query: str):
    terms = re.findall(r"[\w]+", query, flags=re.UNICODE)
    if not terms:
        raise SystemExit("search query must contain at least one word or address")
    # OR keeps mixed queries useful when terms describe different nodes in a
    # call path; bm25 ranks functions matching the greatest number of terms.
    match = " OR ".join('"' + t.replace('"', '""') + '"' for t in terms)
    with connect() as db:
        rows = db.execute("""
            SELECT fact_search.id, fact_search.kind, snippet(fact_search, 2, '[', ']', '…', 16) AS excerpt,
                   coalesce(f.address, s.address) AS address,
                   coalesce(f.symbol, s.symbol) AS symbol,
                   coalesce(f.module, s.module) AS module,
                   coalesce(f.status, 'observed-state') AS status
            FROM fact_search
            LEFT JOIN functions f USING (id) LEFT JOIN states s USING (id)
            WHERE fact_search MATCH ? ORDER BY bm25(fact_search) LIMIT 30
        """, (match,)).fetchall()
    for row in rows:
        print(f"{row['address']} {row['symbol']} [{row['kind']} / {row['module']} / {row['status']}]\n  {row['excerpt']}\n  {row['id']}")
    if not rows:
        print("No matching indexed functions.")


def resolve(db, key):
    row = db.execute("""SELECT * FROM functions WHERE lower(id)=lower(?)
                         OR lower(address)=lower(?) OR lower(symbol)=lower(?) LIMIT 1""",
                     (key, key, key)).fetchone()
    if row is None:
        row = db.execute("""SELECT * FROM states WHERE lower(id)=lower(?)
                             OR lower(address)=lower(?) OR lower(symbol)=lower(?) LIMIT 1""",
                         (key, key, key)).fetchone()
    if row is None:
        try:
            address = f"0x{(int(key, 0) & ~1):08x}"
            row = db.execute("SELECT * FROM functions WHERE lower(address)=lower(?)", (address,)).fetchone()
            if row is None:
                row = db.execute("SELECT * FROM states WHERE lower(address)=lower(?)", (address,)).fetchone()
        except ValueError:
            pass
    return row


def show(key):
    with connect() as db:
        row = resolve(db, key)
        if row is None:
            raise SystemExit(f"function/state not indexed: {key}")
        for field in row.keys():
            print(f"{field}: {row[field]}")
        for edge in db.execute("""SELECT kind, message_id, target AS other FROM edges WHERE source=?
                                  UNION ALL SELECT kind, message_id, source AS other FROM edges WHERE target=?""",
                               (row["id"], row["id"])):
            print(f"edge: {edge['kind']} {edge['message_id']} {edge['other']}")


def trace(start, target):
    with connect() as db:
        a, b = resolve(db, start), resolve(db, target)
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
    p = sub.add_parser("show", help="show a function by address, symbol, or stable id")
    p.add_argument("function")
    p = sub.add_parser("trace", help="find a directed path through indexed call/message edges")
    p.add_argument("start")
    p.add_argument("target")
    args = parser.parse_args()
    if args.command == "rebuild":
        build()
    elif args.command == "search":
        search(args.query)
    elif args.command == "show":
        show(args.function)
    else:
        trace(args.start, args.target)


if __name__ == "__main__":
    main()
