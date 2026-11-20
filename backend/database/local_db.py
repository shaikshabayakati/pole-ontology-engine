import json
import sqlite3
from contextlib import closing
from pathlib import Path


class LocalDatabase:
    """Persist the store's records and commit each graph update atomically."""

    KEYS = {
        "documents": "doc_id", "chunks": "chunk_id", "nodes": "id",
        "edges": "id", "reviews": "review_id", "audit": "log_id",
    }

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS records ("
                "collection TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, "
                "PRIMARY KEY (collection, id))"
            )

    def load(self):
        records = {collection: {} for collection in self.KEYS}
        with closing(sqlite3.connect(self.path)) as db:
            for collection, key, payload in db.execute(
                "SELECT collection, id, payload FROM records ORDER BY rowid"
            ):
                records[collection][key] = json.loads(payload)
        return records

    def write(self, changes, removals=()):
        rows = [
            (collection, entry[self.KEYS[collection]], json.dumps(entry, ensure_ascii=False))
            for collection, entries in changes.items() for entry in entries
        ]
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executemany("DELETE FROM records WHERE collection = ? AND id = ?", removals)
            db.executemany(
                "INSERT INTO records(collection, id, payload) VALUES(?, ?, ?) "
                "ON CONFLICT(collection, id) DO UPDATE SET payload = excluded.payload",
                rows,
            )
