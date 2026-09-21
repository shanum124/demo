import sqlite3
from pathlib import Path

class PYQStore:
    def __init__(self, path: Path):
        self.path = str(path)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS pyqs (pyq_id TEXT PRIMARY KEY, node_ids TEXT, year INTEGER, marks REAL, difficulty_tag TEXT, dna_tags TEXT, full_text TEXT)")

    def put(self, record: dict) -> None:
        import json
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR REPLACE INTO pyqs VALUES (?, ?, ?, ?, ?, ?, ?)", (record["pyq_id"], json.dumps(record.get("node_ids", [])), record.get("year", 0), record.get("marks", 0), record.get("difficulty_tag", "medium"), json.dumps(record.get("dna_tags", [])), record.get("full_text", "")))

    def fetch(self, ids: list[str], fields: list[str] | None = None) -> list[dict]:
        import json
        if not ids: return []
        allowed = {"pyq_id", "node_ids", "year", "marks", "difficulty_tag", "dna_tags", "full_text"}
        selected = [f for f in (fields or ["pyq_id", "node_ids", "year", "marks", "difficulty_tag", "dna_tags"]) if f in allowed]
        selected = selected or ["pyq_id"]
        placeholders = ",".join("?" for _ in ids)
        with sqlite3.connect(self.path) as db:
            rows = db.execute(f"SELECT pyq_id,node_ids,year,marks,difficulty_tag,dna_tags,full_text FROM pyqs WHERE pyq_id IN ({placeholders})", ids).fetchall()
        names = ["pyq_id", "node_ids", "year", "marks", "difficulty_tag", "dna_tags", "full_text"]
        result = []
        for row in rows:
            item = dict(zip(names, row))
            item["node_ids"] = json.loads(item["node_ids"] or "[]")
            item["dna_tags"] = json.loads(item["dna_tags"] or "[]")
            result.append({key: item[key] for key in selected})
        return result
