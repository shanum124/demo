import json
from datetime import datetime, timezone
from ai_services.schemas.orchestrator_schemas import EpisodicTurn

class EpisodicMemory:
    TOKEN_CAP = 6000
    def __init__(self, redis_client, thread_id: str):
        self.redis, self.thread_id = redis_client, thread_id
        self.key = f"episodic:{thread_id}"

    def count_tokens(self, turns: list[dict]) -> int:
        try:
            import tiktoken
            encoder = tiktoken.get_encoding("cl100k_base")
            return sum(len(encoder.encode(t.get("content", ""))) for t in turns)
        except Exception:
            return sum(len(t.get("content", "").split()) for t in turns)

    def get_window(self) -> list[EpisodicTurn]:
        values = self.redis.lrange(self.key, 0, -1) or []
        return [EpisodicTurn.model_validate(json.loads(v)) for v in values]

    def add_turn(self, role: str, content: str) -> list[EpisodicTurn]:
        turn = {"role": role, "content": content, "ts": datetime.now(timezone.utc).isoformat()}
        self.redis.rpush(self.key, json.dumps(turn))
        values = [json.loads(v) for v in (self.redis.lrange(self.key, 0, -1) or [])]
        while values and self.count_tokens(values) > self.TOKEN_CAP:
            evicted = values.pop(0)
            self.redis.rpush("summarize_queue", json.dumps({"thread_id": self.thread_id, "turn": evicted}))
        self.redis.delete(self.key)
        for value in values: self.redis.rpush(self.key, json.dumps(value))
        return [EpisodicTurn.model_validate(value) for value in values]
