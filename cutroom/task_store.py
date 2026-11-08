"""Durable per-project task checkpoints; a failed child never erases siblings."""
import json
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import time


class TaskStore:
    def __init__(self, folder, identity):
        self.path = Path(folder) / "tasks.sqlite3"
        self.identity = json.dumps(identity, sort_keys=True, separators=(",", ":"))
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS tasks (identity TEXT, id TEXT, kind TEXT, "
                       "status TEXT, attempts INTEGER DEFAULT 0, result TEXT, error TEXT, updated REAL, "
                       "PRIMARY KEY(identity,id))")

    def recover_running(self):
        with self.connect() as db:
            db.execute("UPDATE tasks SET status='pending' WHERE identity=? AND status='running'", (self.identity,))

    @staticmethod
    def snapshot(folder):
        path=Path(folder)/'tasks.sqlite3'
        if not path.exists():return []
        db=sqlite3.connect(f'file:{path}?mode=ro',uri=True,timeout=5)
        db.row_factory=sqlite3.Row
        try:
            return [dict(row) for row in db.execute('SELECT id,kind,status,attempts,error,updated FROM tasks '
                'WHERE identity=(SELECT identity FROM tasks ORDER BY updated DESC LIMIT 1) ORDER BY id')]
        finally:
            db.close()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def ensure(self, ident, kind):
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO tasks(identity,id,kind,status,updated) VALUES(?,?,?,'pending',?)",
                       (self.identity, ident, kind, time.time()))

    def get(self, ident):
        with self.connect() as db:
            row = db.execute("SELECT id,kind,status,attempts,result,error,updated FROM tasks WHERE identity=? AND id=?",
                             (self.identity, ident)).fetchone()
        if row is None:
            return None
        value = dict(row)
        value["result"] = json.loads(value["result"]) if value["result"] is not None else None
        return value

    def set(self, ident, status, result=None, error=None):
        if status not in {"pending", "running", "complete", "failed", "rejected", "duplicate"}:
            raise ValueError("Unknown task status")
        with self.connect() as db:
            db.execute("UPDATE tasks SET status=?, result=?, error=?, attempts=attempts+?, updated=? "
                       "WHERE identity=? AND id=?", (status, json.dumps(result, ensure_ascii=False) if result is not None else None,
                       str(error)[-1200:] if error else None, int(status == "running"), time.time(), self.identity, ident))

    def list(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT id,kind,status,attempts,error,updated FROM tasks "
                                                   "WHERE identity=? ORDER BY id", (self.identity,))]

    def run(self, studio, job, ident, kind, operation):
        self.ensure(ident, kind)
        old = self.get(ident)
        if old["status"] == "complete":
            return old["result"]
        for attempt in range(2):
            studio.check_cancel(job["id"])
            self.set(ident, "running")
            try:
                result = operation()
                studio.check_cancel(job["id"])
                self.set(ident, "complete", result=result)
                return result
            except Exception as exc:
                from .resources import ResourcePause
                if isinstance(exc,ResourcePause):
                    self.set(ident,'pending')
                    raise
                try:
                    studio.check_cancel(job["id"])
                except Exception:
                    self.set(ident, "pending")
                    raise
                self.set(ident, "failed", error=exc)
                if attempt:
                    raise
                studio.event(job, f"Retrying only {ident}; other saved tasks are unchanged.")
