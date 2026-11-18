# Searchable reverse-engineering knowledge

Human-readable explanations stay in `docs/findings-*.md`. Discrete function
facts and verified relationships are also recorded as JSONL in
`docs/knowledge/facts.jsonl`; this is the portable, reviewable source for the
search index. Raw decompiler output is vendor-derived, so it stays under the
Git-ignored `analysis/local-evidence/` directory and is not committed.

Build/query the local SQLite FTS5 index with Python's standard library:

```sh
python3 tools/knowledge/m30kb.py rebuild
python3 tools/knowledge/m30kb.py search 'mode 4 0x304'
python3 tools/knowledge/m30kb.py show 0x405151a0
python3 tools/knowledge/m30kb.py trace 0x405151a0 0x60110ddc
```

The initial records cover the mode-4 callback through the `0x304` engine
dispatcher, plus the three effective RAM bytes written by its handler. Each
function/state record includes input hash, variant, address, concise behavior,
and evidence link. Typed graph edges distinguish direct calls, message sends,
dispatcher routing, and state writes. Search
results are only as complete as the curated records; an absent result is not
evidence that a firmware reference does not exist. Add records only after
checking the relevant binary and link each one to a finding with its evidence
limits. This keeps Ghidra's mechanically decompiled output separate from
semantically reviewed facts.
