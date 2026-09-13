"""The world model: one SQLite file, written only by the orchestrator.

Single-writer discipline (finding F8). Agents read and return structured
output; nothing else touches this store. Standard library only.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable

DEFAULT_DB = Path(__file__).parent / "data" / "founder_os.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  payload TEXT NOT NULL DEFAULT '{}',
  source_url TEXT NOT NULL,
  source_name TEXT NOT NULL DEFAULT '',
  dated_at TEXT,
  observed_at TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 0.5
);
CREATE INDEX IF NOT EXISTS idx_signals_kind ON signals(kind);

CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  one_line TEXT NOT NULL DEFAULT '',
  audience TEXT NOT NULL DEFAULT '',
  mechanic TEXT NOT NULL DEFAULT '',
  monetization TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'shipped',
  payload TEXT NOT NULL DEFAULT '{}',
  source_url TEXT NOT NULL DEFAULT '',
  dated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_products_status ON products(status);

CREATE TABLE IF NOT EXISTS ideas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  cycle_id INTEGER,
  genome TEXT NOT NULL,
  descriptor TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  island INTEGER NOT NULL DEFAULT 0,
  generation INTEGER NOT NULL DEFAULT 0,
  operator TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'alive',
  killed_at_gate TEXT,
  kill_reason TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ideas_status ON ideas(status);
CREATE INDEX IF NOT EXISTS idx_ideas_desc ON ideas(descriptor);

CREATE TABLE IF NOT EXISTS verdicts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  idea_id INTEGER NOT NULL,
  gate TEXT NOT NULL,
  passed INTEGER NOT NULL,
  score REAL,
  detail TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_verdicts_idea ON verdicts(idea_id);

CREATE TABLE IF NOT EXISTS scores (
  idea_id INTEGER PRIMARY KEY,
  originality REAL, quality REAL, novelty REAL,
  buildability REAL, unit_economics REAL, distribution REAL, timing REAL,
  viability REAL, survival REAL, founder_score REAL,
  elo_novelty REAL, elo_viability REAL, lcb REAL,
  weights_version TEXT, detail TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS comparisons (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  head TEXT NOT NULL,
  a_id INTEGER NOT NULL,
  b_id INTEGER NOT NULL,
  winner INTEGER,
  swapped INTEGER NOT NULL DEFAULT 0,
  rationale TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS cycles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  config TEXT NOT NULL DEFAULT '{}',
  budget_usd REAL DEFAULT 0,
  spent_usd REAL DEFAULT 0,
  generated INTEGER DEFAULT 0,
  survived INTEGER DEFAULT 0,
  halted_reason TEXT,
  task_ledger TEXT NOT NULL DEFAULT '{}',
  progress_ledger TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS probes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  idea_id INTEGER NOT NULL,
  kind TEXT NOT NULL,
  hypothesis TEXT NOT NULL,
  falsifier TEXT NOT NULL DEFAULT '',
  budget_usd REAL NOT NULL DEFAULT 0,
  approved_by_human INTEGER NOT NULL DEFAULT 0,
  result TEXT, verdict TEXT, created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class Store:
    def __init__(self, path: str | Path = DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path))
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()

    def close(self) -> None:
        self.db.commit()
        self.db.close()

    # -- signals ----------------------------------------------------------

    def add_signal(self, kind: str, title: str, source_url: str, *,
                   body: str = "", payload: dict | None = None,
                   source_name: str = "", dated_at: str | None = None,
                   confidence: float = 0.5) -> int:
        if not source_url:
            raise ValueError("a signal without a source_url never enters the store")
        cur = self.db.execute(
            "INSERT INTO signals (kind,title,body,payload,source_url,source_name,"
            "dated_at,observed_at,confidence) VALUES (?,?,?,?,?,?,?,?,?)",
            (kind, title, body, json.dumps(payload or {}), source_url,
             source_name, dated_at, _now(), confidence))
        self.db.commit()
        return int(cur.lastrowid)

    def signals(self, kind: str | None = None,
                before: str | None = None) -> list[dict[str, Any]]:
        q, args = "SELECT * FROM signals", []
        where = []
        if kind:
            where.append("kind = ?"); args.append(kind)
        if before:
            where.append("(dated_at IS NULL OR dated_at < ?)"); args.append(before)
        if where:
            q += " WHERE " + " AND ".join(where)
        return [_row(r) for r in self.db.execute(q, args)]

    # -- products ---------------------------------------------------------

    def add_product(self, name: str, **kw) -> int:
        cur = self.db.execute(
            "INSERT INTO products (name,one_line,audience,mechanic,monetization,"
            "status,payload,source_url,dated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (name, kw.get("one_line", ""), kw.get("audience", ""),
             kw.get("mechanic", ""), kw.get("monetization", ""),
             kw.get("status", "shipped"), json.dumps(kw.get("payload", {})),
             kw.get("source_url", ""), kw.get("dated_at")))
        self.db.commit()
        return int(cur.lastrowid)

    def products(self, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            rows = self.db.execute("SELECT * FROM products WHERE status=?", (status,))
        else:
            rows = self.db.execute("SELECT * FROM products")
        return [_row(r) for r in rows]

    # -- ideas ------------------------------------------------------------

    def add_idea(self, g, cycle_id: int | None = None) -> int:
        cur = self.db.execute(
            "INSERT INTO ideas (cycle_id,genome,descriptor,title,island,generation,"
            "operator,status,created_at) VALUES (?,?,?,?,?,?,?,'alive',?)",
            (cycle_id, g.to_json(), g.descriptor, g.title, g.island,
             g.generation, g.operator, _now()))
        self.db.commit()
        return int(cur.lastrowid)

    def kill_idea(self, idea_id: int, gate: str, reason: str) -> None:
        self.db.execute(
            "UPDATE ideas SET status='killed', killed_at_gate=?, kill_reason=? WHERE id=?",
            (gate, reason, idea_id))
        self.db.commit()

    def set_status(self, idea_id: int, status: str) -> None:
        self.db.execute("UPDATE ideas SET status=? WHERE id=?", (status, idea_id))
        self.db.commit()

    def ideas(self, status: str | None = None,
              cycle_id: int | None = None) -> list[dict[str, Any]]:
        q, args, where = "SELECT * FROM ideas", [], []
        if status:
            where.append("status = ?"); args.append(status)
        if cycle_id is not None:
            where.append("cycle_id = ?"); args.append(cycle_id)
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY id"
        return [_row(r) for r in self.db.execute(q, args)]

    def idea(self, idea_id: int) -> dict[str, Any] | None:
        r = self.db.execute("SELECT * FROM ideas WHERE id=?", (idea_id,)).fetchone()
        return _row(r) if r else None

    def living_descriptors(self) -> set[str]:
        return {r["descriptor"] for r in
                self.db.execute("SELECT descriptor FROM ideas WHERE status!='killed'")}

    # -- verdicts / scores ------------------------------------------------

    def add_verdict(self, idea_id: int, gate: str, passed: bool,
                    score: float | None = None, detail: dict | None = None) -> None:
        self.db.execute(
            "INSERT INTO verdicts (idea_id,gate,passed,score,detail,created_at) "
            "VALUES (?,?,?,?,?,?)",
            (idea_id, gate, int(passed), score, json.dumps(detail or {}), _now()))
        self.db.commit()

    def verdicts(self, idea_id: int) -> list[dict[str, Any]]:
        return [_row(r) for r in self.db.execute(
            "SELECT * FROM verdicts WHERE idea_id=? ORDER BY id", (idea_id,))]

    def set_scores(self, idea_id: int, **kw) -> None:
        cols = ("originality", "quality", "novelty", "buildability",
                "unit_economics", "distribution", "timing", "viability",
                "survival", "founder_score", "elo_novelty", "elo_viability",
                "lcb", "weights_version", "detail")
        vals = [kw.get(c) for c in cols]
        vals[-1] = json.dumps(kw.get("detail", {}))
        self.db.execute(
            f"INSERT OR REPLACE INTO scores (idea_id,{','.join(cols)}) "
            f"VALUES ({','.join('?' * (len(cols) + 1))})", [idea_id] + vals)
        self.db.commit()

    def scores(self, idea_id: int) -> dict[str, Any] | None:
        r = self.db.execute("SELECT * FROM scores WHERE idea_id=?", (idea_id,)).fetchone()
        return _row(r) if r else None

    # -- comparisons ------------------------------------------------------

    def add_comparison(self, head: str, a_id: int, b_id: int,
                       winner: int | None, swapped: bool = False,
                       rationale: str = "") -> None:
        self.db.execute(
            "INSERT INTO comparisons (head,a_id,b_id,winner,swapped,rationale) "
            "VALUES (?,?,?,?,?,?)",
            (head, a_id, b_id, winner, int(swapped), rationale))
        self.db.commit()

    def comparisons(self, head: str | None = None) -> list[dict[str, Any]]:
        if head:
            rows = self.db.execute("SELECT * FROM comparisons WHERE head=?", (head,))
        else:
            rows = self.db.execute("SELECT * FROM comparisons")
        return [_row(r) for r in rows]

    # -- cycles -----------------------------------------------------------

    def start_cycle(self, config: dict, budget_usd: float) -> int:
        cur = self.db.execute(
            "INSERT INTO cycles (started_at,config,budget_usd) VALUES (?,?,?)",
            (_now(), json.dumps(config), budget_usd))
        self.db.commit()
        return int(cur.lastrowid)

    def update_cycle(self, cycle_id: int, **kw) -> None:
        if not kw:
            return
        sets, args = [], []
        for k, v in kw.items():
            sets.append(f"{k}=?")
            args.append(json.dumps(v) if isinstance(v, (dict, list)) else v)
        args.append(cycle_id)
        self.db.execute(f"UPDATE cycles SET {','.join(sets)} WHERE id=?", args)
        self.db.commit()

    def cycle(self, cycle_id: int) -> dict[str, Any] | None:
        r = self.db.execute("SELECT * FROM cycles WHERE id=?", (cycle_id,)).fetchone()
        return _row(r) if r else None

    # -- probes -----------------------------------------------------------

    def add_probe(self, idea_id: int, kind: str, hypothesis: str,
                  falsifier: str, budget_usd: float) -> int:
        cur = self.db.execute(
            "INSERT INTO probes (idea_id,kind,hypothesis,falsifier,budget_usd,"
            "created_at) VALUES (?,?,?,?,?,?)",
            (idea_id, kind, hypothesis, falsifier, budget_usd, _now()))
        self.db.commit()
        return int(cur.lastrowid)

    def probes(self) -> list[dict[str, Any]]:
        return [_row(r) for r in self.db.execute("SELECT * FROM probes ORDER BY id")]


def _row(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    for k in ("payload", "detail", "config", "task_ledger", "progress_ledger", "result"):
        if k in d and isinstance(d[k], str) and d[k]:
            try:
                d[k] = json.loads(d[k])
            except (ValueError, TypeError):
                pass
    return d
