import sqlite3
from pathlib import Path

class MarkdownStore:
    def __init__(self, path: Path, root: Path | None = None):
        self.path, self.root = str(path), root or path.parent / "markdown"
        self.root.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS markdown_versions (doc_id TEXT, version INTEGER, section TEXT, patch TEXT, PRIMARY KEY(doc_id, version))")

    def write_patch(self, doc_id: str, section: str, patch: str) -> int:
        if len(patch.encode()) > 50_000: raise ValueError("markdown patch exceeds 50KB")
        with sqlite3.connect(self.path) as db:
            version = db.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM markdown_versions WHERE doc_id=?", (doc_id,)).fetchone()[0]
            db.execute("INSERT INTO markdown_versions VALUES (?, ?, ?, ?)", (doc_id, version, section, patch))
        return version

    def read(self, doc_id: str) -> str:
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT section,patch FROM markdown_versions WHERE doc_id=? ORDER BY version", (doc_id,)).fetchall()
        return "\n\n".join(f"## {section}\n{patch}" for section, patch in rows)
