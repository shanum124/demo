import sqlite3
from pathlib import Path

class SyllabusStore:
    def __init__(self, path: Path):
        self.path = str(path)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS syllabus_nodes (node_id TEXT PRIMARY KEY, title TEXT, parent_id TEXT)")

    def put_nodes(self, nodes: list[dict]) -> None:
        with sqlite3.connect(self.path) as db:
            db.executemany("INSERT OR REPLACE INTO syllabus_nodes VALUES (?, ?, ?)", [(n["node_id"], n["title"], n.get("parent_id")) for n in nodes])

    def graph(self, node_id: str | None = None, depth: int = 2) -> dict:
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT node_id,title,parent_id FROM syllabus_nodes").fetchall()
        nodes = {row[0]: {"node_id": row[0], "title": row[1], "parent_id": row[2]} for row in rows}
        if node_id and node_id in nodes:
            allowed = {node_id}
            for _ in range(depth):
                allowed |= {key for key, value in nodes.items() if value["parent_id"] in allowed}
            nodes = {key: value for key, value in nodes.items() if key in allowed}
        return {"nodes": list(nodes.values()), "edges": [{"from": v["parent_id"], "to": k} for k, v in nodes.items() if v["parent_id"] in nodes]}
