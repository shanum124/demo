import json
import sqlite3
from pathlib import Path
from ai_services.schemas.mock_schemas import MockTest

class MockStore:
    def __init__(self, path: Path):
        self.path = str(path)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS mocks (test_id TEXT PRIMARY KEY, object_json TEXT NOT NULL)")

    def write(self, test: MockTest) -> dict:
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR REPLACE INTO mocks VALUES (?, ?)", (test.test_id, test.model_dump_json()))
        return {"success": True, "test_id": test.test_id}

    def get(self, test_id: str) -> MockTest | None:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT object_json FROM mocks WHERE test_id=?", (test_id,)).fetchone()
        return MockTest.model_validate(json.loads(row[0])) if row else None
