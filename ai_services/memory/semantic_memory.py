from datetime import datetime, timezone
from ai_services.schemas.orchestrator_schemas import SemanticProfile, PacingProfile, WeaknessEntry, MasteryEntry
from ai_services.schemas.mock_schemas import QuestionResult

class SemanticMemory:
    MASTERY_THRESHOLD = 0.8
    def __init__(self, redis_client): self.redis = redis_client
    def _key(self, user_id): return f"profile:{user_id}"
    async def get_profile(self, user_id: str) -> SemanticProfile:
        value = self.redis.get(self._key(user_id))
        if value:
            import json
            return SemanticProfile.model_validate(json.loads(value))
        return SemanticProfile(user_id=user_id)
    async def reducer(self, user_id: str) -> SemanticProfile:
        profile = await self.get_profile(user_id)
        events = self.redis.lrange(f"telemetry:{user_id}", 0, -1) or []
        import json
        weaknesses = {x.node_id: x for x in profile.current_weaknesses}
        mastered = {x.node_id: x for x in profile.mastered_topics}
        for raw in events:
            event = json.loads(raw)
            payload = event.get("payload", {})
            node_id = payload.get("node_id")
            if not node_id: continue
            if event.get("event_type") == "micro_challenge_result":
                confidence = weaknesses.get(node_id, WeaknessEntry(node_id=node_id, confidence=0.5, last_seen=datetime.now(timezone.utc))).confidence
                confidence = min(1.0, confidence + (0.1 if payload.get("correct") else -0.15))
                entry = WeaknessEntry(node_id=node_id, confidence=confidence, last_seen=datetime.now(timezone.utc))
                if confidence >= self.MASTERY_THRESHOLD: mastered[node_id] = MasteryEntry(node_id=node_id, confidence=confidence, last_verified=entry.last_seen); weaknesses.pop(node_id, None)
                else: weaknesses[node_id] = entry
        profile.current_weaknesses, profile.mastered_topics = list(weaknesses.values()), list(mastered.values())
        profile.last_updated, profile.profile_version = datetime.now(timezone.utc), profile.profile_version + 1
        self.redis.set(self._key(user_id), profile.model_dump_json())
        return profile
    async def update_pacing(self, profile: SemanticProfile, results: list[QuestionResult]) -> PacingProfile:
        average = sum(r.time_spent_s for r in results) / len(results) if results else 0
        tendency = "rushed" if average < 30 else "deliberate" if average > 90 else "balanced"
        return PacingProfile(avg_seconds_per_question=average, tendency=tendency)
